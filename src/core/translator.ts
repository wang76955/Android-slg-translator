import OpenAI from "openai"
import type { TextItem, GlossaryEntry, ProgressCallback } from "./types"
import { getLocalTranslation } from "./local-translation"

import { buildCacheContext, readCachedTranslation, writeCachedTranslation, loadCache, persistCache } from "./translation-cache"
const LANG_MAP: Record<string, string> = {
  zh: "Chinese",
  en: "English",
  ja: "Japanese",
  ko: "Korean",
  fr: "French",
  de: "German",
}

const MAX_CONCURRENT = 4
const DEFAULT_BATCH_SIZE = 80
const MAX_BATCH_CHARS = 6000
const MAX_MEMORY_CACHE_ENTRIES = 5000

interface CacheRecord {
  sourceText: string
  translatedText: string
  updatedAt: number
}

export interface ProtectedText {
  text: string
  placeholders: string[]
}

interface PreparedTextItem extends UniqueTextItem {
  protectedText: ProtectedText
}

interface BatchRetryResult {
  translations: Map<number, string>
  splitCount: number
  failedCount: number
}

export interface UniqueTextItem extends TextItem {
  duplicateKeys: string[]
}

export interface TranslateOptions {
  texts: TextItem[]
  sourceLang: string
  targetLang: string
  baseURL: string
  apiKey: string
  model: string
  glossary?: GlossaryEntry[]
  batchSize?: number
  onProgress?: ProgressCallback
}

export function collectUniqueTranslatableTexts(texts: TextItem[]): UniqueTextItem[] {
  const textMap = new Map<string, UniqueTextItem>()

  for (const item of texts) {
    const normalizedText = item.text.trim()
    if (!normalizedText) continue

    const existing = textMap.get(normalizedText)
    if (existing) {
      existing.duplicateKeys.push(item.keyPath)
      continue
    }

    textMap.set(normalizedText, {
      keyPath: item.keyPath,
      text: item.text,
      duplicateKeys: [],
    })
  }

  return Array.from(textMap.values())
}

export function buildCompactTranslationPayload(batchTexts: TextItem[]): string {
  return JSON.stringify(batchTexts.map((item) => item.text))
}

export function protectTextForTranslation(text: string): ProtectedText {
  const placeholders: string[] = []
  const protectedText = text.replace(
    /(\{[^{}\n]{1,80}\}|\[[A-Za-z_][\w.]{0,80}\]|%\d*\$?[sdif]|%[sdif]|\$\{[^}\n]{1,80}\})/g,
    (placeholder) => {
      const token = `__PH${placeholders.length}__`
      placeholders.push(placeholder)
      return token
    },
  )

  return { text: protectedText, placeholders }
}

export function restoreProtectedText(translatedText: string, protectedText: ProtectedText): string {
  return protectedText.placeholders.reduce(
    (result, placeholder, index) => result.replaceAll(`__PH${index}__`, placeholder),
    translatedText,
  )
}

export async function translateBatch(options: TranslateOptions): Promise<{
  translations: Map<string, string>
  successCount: number
  error?: string
}> {
  const {
    texts,
    sourceLang,
    targetLang,
    baseURL,
    apiKey,
    model,
    glossary,
    batchSize = DEFAULT_BATCH_SIZE,
    onProgress,
  } = options

  await loadCache()
  if (texts.length === 0) {
    return { translations: new Map(), successCount: 0 }
  }

  const supportsJson = !model.includes("reasoner") && !model.includes("pro")
  const translations = new Map<string, string>()
  const uniqueTexts = collectUniqueTranslatableTexts(texts)
  const cacheContext = buildCacheContext(sourceLang, targetLang, model, glossary)
  const uncachedTexts: UniqueTextItem[] = []
  let cachedCount = 0
  let localRuleCount = 0

  for (const item of uniqueTexts) {
    const localTranslation = getLocalTranslation(item.text, sourceLang, targetLang)
    if (localTranslation) {
      setTranslationForAllKeys(translations, item, localTranslation)
      writeCachedTranslation(cacheContext, item.text, localTranslation)
      localRuleCount += 1 + item.duplicateKeys.length
      continue
    }

    const cachedTranslation = readCachedTranslation(cacheContext, item.text)
    if (cachedTranslation) {
      setTranslationForAllKeys(translations, item, cachedTranslation)
      cachedCount += 1 + item.duplicateKeys.length
    } else {
      uncachedTexts.push(item)
    }
  }

  onProgress?.(translations.size, texts.length, "translating", { cachedCount, localRuleCount })

  if (uncachedTexts.length === 0) {
    await persistCache()
    return { translations, successCount: translations.size }
  }

  if (!apiKey) {
    await persistCache()
    return {
      translations,
      successCount: translations.size,
      error: `API Key is missing; translated ${translations.size}/${texts.length} items with local rules/cache`,
    }
  }

  const client = new OpenAI({
    apiKey,
    baseURL,
    dangerouslyAllowBrowser: true,
    timeout: 30000,
    maxRetries: 2,
  })

  let hasError = false
  const allBatches = createTranslationBatches(uncachedTexts.map(prepareTextItem), batchSize)
  let nextBatchIndex = 0
  let completedBatches = 0
  let failedBatches = 0
  let splitBatches = 0
  const startedAt = Date.now()

  const workerCount = Math.min(MAX_CONCURRENT, allBatches.length)
  const workers = Array.from({ length: workerCount }, async () => {
    while (nextBatchIndex < allBatches.length) {
      const batchIndex = nextBatchIndex++
      const batch = allBatches[batchIndex]

      try {
        const result = await translateOneBatchWithFallback(
          client,
          model,
          batch,
          sourceLang,
          targetLang,
          glossary,
          supportsJson,
        )
        splitBatches += result.splitCount
        failedBatches += result.failedCount
        if (result.failedCount > 0) hasError = true

        for (const [index, translatedText] of result.translations.entries()) {
          const item = batch[index]
          if (!item || !translatedText) continue

          setTranslationForAllKeys(translations, item, translatedText)
          writeCachedTranslation(cacheContext, item.text, translatedText)
        }
      } catch {
        hasError = true
        failedBatches += 1
      }

      completedBatches += 1
      onProgress?.(translations.size, texts.length, "translating", {
        cachedCount,
        localRuleCount,
        completedBatches,
        totalBatches: allBatches.length,
        currentBatch: batchIndex + 1,
        batchSize: batch.length,
        failedBatches,
        splitBatches,
        estimatedSecondsRemaining: estimateSecondsRemaining(startedAt, completedBatches, allBatches.length),
      })
    }
  })

  await Promise.all(workers)
  await persistCache()

  return {
    translations,
    successCount: translations.size,
    ...(hasError ? { error: `Translated ${translations.size}/${texts.length} items; some batches failed` } : {}),
  }
}

function prepareTextItem(item: UniqueTextItem): PreparedTextItem {
  return {
    ...item,
    protectedText: protectTextForTranslation(item.text),
  }
}

function createTranslationBatches(texts: PreparedTextItem[], maxItems: number): PreparedTextItem[][] {
  const batches: PreparedTextItem[][] = []
  let currentBatch: PreparedTextItem[] = []
  let currentChars = 0

  for (const item of texts) {
    const itemChars = item.protectedText.text.length
    const wouldExceedItems = currentBatch.length >= maxItems
    const wouldExceedChars = currentBatch.length > 0 && currentChars + itemChars > MAX_BATCH_CHARS

    if (wouldExceedItems || wouldExceedChars) {
      batches.push(currentBatch)
      currentBatch = []
      currentChars = 0
    }

    currentBatch.push(item)
    currentChars += itemChars
  }

  if (currentBatch.length > 0) {
    batches.push(currentBatch)
  }

  return batches
}

async function translateOneBatchWithFallback(
  client: OpenAI,
  model: string,
  batchTexts: PreparedTextItem[],
  sourceLang: string,
  targetLang: string,
  glossary?: GlossaryEntry[],
  supportsJson?: boolean,
  depth = 0,
): Promise<BatchRetryResult> {
  try {
    return {
      translations: await translateOneBatch(client, model, batchTexts, sourceLang, targetLang, glossary, supportsJson),
      splitCount: 0,
      failedCount: 0,
    }
  } catch {
    if (batchTexts.length <= 1 || depth >= 4) {
      return {
        translations: new Map(),
        splitCount: 0,
        failedCount: 1,
      }
    }

    const midpoint = Math.ceil(batchTexts.length / 2)
    const left = batchTexts.slice(0, midpoint)
    const right = batchTexts.slice(midpoint)
    const leftResult = await translateOneBatchWithFallback(
      client,
      model,
      left,
      sourceLang,
      targetLang,
      glossary,
      supportsJson,
      depth + 1,
    )
    const rightResult = await translateOneBatchWithFallback(
      client,
      model,
      right,
      sourceLang,
      targetLang,
      glossary,
      supportsJson,
      depth + 1,
    )

    const translations = new Map<number, string>()
    for (const [index, translatedText] of leftResult.translations.entries()) {
      translations.set(index, translatedText)
    }
    for (const [index, translatedText] of rightResult.translations.entries()) {
      translations.set(index + midpoint, translatedText)
    }

    return {
      translations,
      splitCount: 1 + leftResult.splitCount + rightResult.splitCount,
      failedCount: leftResult.failedCount + rightResult.failedCount,
    }
  }
}

async function translateOneBatch(
  client: OpenAI,
  model: string,
  batchTexts: PreparedTextItem[],
  sourceLang: string,
  targetLang: string,
  glossary?: GlossaryEntry[],
  supportsJson?: boolean,
): Promise<Map<number, string>> {
  const translations = new Map<number, string>()
  const systemPrompt = buildSystemPrompt(sourceLang, targetLang, glossary, supportsJson)
  const responseInstruction = supportsJson
    ? "Return a JSON object exactly like {\"translations\":[\"...\"]} with translations in the same order:\n"
    : "Return a JSON array with translations in the same order:\n"
  const userContent =
    "Translate this JSON array. " +
    responseInstruction +
    buildCompactTranslationPayload(batchTexts.map((item) => ({ ...item, text: item.protectedText.text })))

  const completion = await client.chat.completions.create({
    model,
    messages: [
      { role: "system", content: systemPrompt },
      { role: "user", content: userContent },
    ],
    temperature: 0.3,
    ...(supportsJson ? { response_format: { type: "json_object" } as const } : {}),
  })

  const resultText = completion.choices[0]?.message?.content
  if (!resultText) throw new Error("API returned empty content")

  const resultJson = parseTranslationResponse(resultText)
  for (let index = 0; index < batchTexts.length; index++) {
    const translatedText = resultJson[index]
    if (typeof translatedText === "string" && translatedText.trim()) {
      translations.set(index, restoreProtectedText(translatedText, batchTexts[index].protectedText))
    }
  }

  return translations
}

export function parseTranslationResponse(resultText: string): string[] {
  const parsed = JSON.parse(extractJsonPayload(resultText))

  if (Array.isArray(parsed)) {
    return parsed.map((item) => String(item ?? ""))
  }

  if (Array.isArray(parsed.translations)) {
    return parsed.translations.map((item: unknown) => String(item ?? ""))
  }

  return Object.keys(parsed)
    .sort((left, right) => Number(left) - Number(right))
    .map((key) => String(parsed[key] ?? ""))
}

function extractJsonPayload(resultText: string): string {
  const trimmed = resultText.trim()
  const fencedMatch = trimmed.match(/^```(?:json)?\s*([\s\S]*?)\s*```$/)
  if (fencedMatch) return fencedMatch[1].trim()

  const objectStart = trimmed.indexOf("{")
  const objectEnd = trimmed.lastIndexOf("}")
  if (objectStart >= 0 && objectEnd > objectStart) {
    return trimmed.slice(objectStart, objectEnd + 1)
  }

  const arrayStart = trimmed.indexOf("[")
  const arrayEnd = trimmed.lastIndexOf("]")
  if (arrayStart >= 0 && arrayEnd > arrayStart) {
    return trimmed.slice(arrayStart, arrayEnd + 1)
  }

  return trimmed
}

function setTranslationForAllKeys(
  translations: Map<string, string>,
  item: UniqueTextItem,
  translatedText: string,
): void {
  translations.set(item.keyPath, translatedText)
  for (const duplicateKey of item.duplicateKeys) {
    translations.set(duplicateKey, translatedText)
  }
}

function buildSystemPrompt(
  sourceLang: string,
  targetLang: string,
  glossary?: GlossaryEntry[],
  supportsJson?: boolean,
): string {
  const srcName = LANG_MAP[sourceLang] ?? sourceLang
  const tgtName = LANG_MAP[targetLang] ?? targetLang

  let prompt =
    `Translate game dialogue ${srcName}->${tgtName}. ` +
    "Keep __PH0__ tokens, line breaks, and formatting."

  if (glossary && glossary.length > 0) {
    prompt += "\nUse these terms consistently:\n"
    for (const entry of glossary) {
      prompt += `${entry.source}=${entry.target}\n`
    }
  }

  if (supportsJson) {
    prompt += "\nReturn only JSON: {\"translations\":[\"...\"]}"
  }

  return prompt
}

function estimateSecondsRemaining(startedAt: number, completed: number, total: number): number | undefined {
  if (completed <= 0 || total <= completed) return undefined

  const elapsedSeconds = (Date.now() - startedAt) / 1000
  const secondsPerBatch = elapsedSeconds / completed
  return Math.max(1, Math.round(secondsPerBatch * (total - completed)))
}
