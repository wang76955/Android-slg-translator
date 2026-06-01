import OpenAI from "openai"
import type { TextItem, GlossaryEntry, ProgressCallback } from "./types"

const LANG_MAP: Record<string, string> = {
  zh: "Chinese",
  en: "English",
  ja: "Japanese",
  ko: "Korean",
  fr: "French",
  de: "German",
}

const MAX_CONCURRENT = 5
const DEFAULT_BATCH_SIZE = 200
const MAX_BATCH_CHARS = 12000
const CACHE_PREFIX = "slg-translator-cache:"
const MAX_MEMORY_CACHE_ENTRIES = 5000
const memoryCache = new Map<string, CacheRecord>()

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

  if (!apiKey) {
    return { translations: new Map(), successCount: 0, error: "API Key is missing" }
  }

  if (texts.length === 0) {
    return { translations: new Map(), successCount: 0 }
  }

  const client = new OpenAI({
    apiKey,
    baseURL,
    dangerouslyAllowBrowser: true,
    timeout: 30000,
    maxRetries: 2,
  })

  const supportsJson = !model.includes("reasoner") && !model.includes("pro")
  const translations = new Map<string, string>()
  const uniqueTexts = collectUniqueTranslatableTexts(texts)
  const cacheContext = buildCacheContext(sourceLang, targetLang, model, glossary)
  const uncachedTexts: UniqueTextItem[] = []

  for (const item of uniqueTexts) {
    const cachedTranslation = readCachedTranslation(cacheContext, item.text)
    if (cachedTranslation) {
      setTranslationForAllKeys(translations, item, cachedTranslation)
    } else {
      uncachedTexts.push(item)
    }
  }

  onProgress?.(translations.size, texts.length, "translating")

  if (uncachedTexts.length === 0) {
    return { translations, successCount: translations.size }
  }

  let hasError = false
  const allBatches = createTranslationBatches(uncachedTexts.map(prepareTextItem), batchSize)

  for (let start = 0; start < allBatches.length; start += MAX_CONCURRENT) {
    const concurrentBatches = allBatches.slice(start, start + MAX_CONCURRENT)

    const results = await Promise.allSettled(
      concurrentBatches.map((batch) =>
        translateOneBatch(client, model, batch, sourceLang, targetLang, glossary, supportsJson),
      ),
    )

    for (let i = 0; i < results.length; i++) {
      const result = results[i]
      const batch = concurrentBatches[i]

      if (result.status === "fulfilled") {
        for (const [index, translatedText] of result.value.entries()) {
          const item = batch[index]
          if (!item || !translatedText) continue

          setTranslationForAllKeys(translations, item, translatedText)
          writeCachedTranslation(cacheContext, item.text, translatedText)
        }
      } else {
        hasError = true
      }
    }

    onProgress?.(translations.size, texts.length, "translating")
  }

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
    `You are a professional game localization translator. Translate ${srcName} text to ${tgtName}. ` +
    "Keep __PH0__ style placeholder tokens unchanged. Preserve line breaks and formatting."

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

function buildCacheContext(
  sourceLang: string,
  targetLang: string,
  model: string,
  glossary?: GlossaryEntry[],
): string {
  const glossarySignature = glossary?.length
    ? glossary.map((entry) => `${entry.source}=${entry.target}`).sort().join("|")
    : ""

  return `${sourceLang}|${targetLang}|${model}|${hashString(glossarySignature)}`
}

function buildCacheKey(context: string, sourceText: string): string {
  return `${CACHE_PREFIX}${context}|${hashString(sourceText)}`
}

function readCachedTranslation(context: string, sourceText: string): string | null {
  const cacheKey = buildCacheKey(context, sourceText)
  const memoryRecord = memoryCache.get(cacheKey)
  if (memoryRecord?.sourceText === sourceText) {
    return memoryRecord.translatedText
  }

  const storage = getLocalStorage()
  if (!storage) return null

  try {
    const rawRecord = storage.getItem(cacheKey)
    if (!rawRecord) return null

    const record = JSON.parse(rawRecord) as CacheRecord
    if (record.sourceText !== sourceText || !record.translatedText) return null

    rememberInMemory(cacheKey, record)
    return record.translatedText
  } catch {
    return null
  }
}

function writeCachedTranslation(context: string, sourceText: string, translatedText: string): void {
  const cacheKey = buildCacheKey(context, sourceText)
  const record: CacheRecord = {
    sourceText,
    translatedText,
    updatedAt: Date.now(),
  }

  rememberInMemory(cacheKey, record)

  const storage = getLocalStorage()
  if (!storage) return

  try {
    storage.setItem(cacheKey, JSON.stringify(record))
  } catch {
    // Storage quota can be small in WebView. The memory cache still helps this run.
  }
}

function rememberInMemory(cacheKey: string, record: CacheRecord): void {
  memoryCache.set(cacheKey, record)

  if (memoryCache.size <= MAX_MEMORY_CACHE_ENTRIES) return

  const oldestKey = memoryCache.keys().next().value
  if (oldestKey) {
    memoryCache.delete(oldestKey)
  }
}

function getLocalStorage(): Storage | null {
  try {
    if (typeof globalThis.localStorage === "undefined") return null
    return globalThis.localStorage
  } catch {
    return null
  }
}

function hashString(value: string): string {
  let hash = 2166136261
  for (let i = 0; i < value.length; i++) {
    hash ^= value.charCodeAt(i)
    hash = Math.imul(hash, 16777619)
  }
  return (hash >>> 0).toString(36)
}
