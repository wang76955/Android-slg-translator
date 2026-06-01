import OpenAI from "openai"
import type { TextItem, GlossaryEntry, ProgressCallback } from "./types"

const LANG_MAP: Record<string, string> = {
  zh: "����", en: "English", ja: "�ձ��Z",
  ko: "???", fr: "Fran?ais", de: "Deutsch"
}

const MAX_CONCURRENT = 5  // 最大并行请求数（提高并发）

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

/**
 * �Ż���������������
 * ���ԣ������������ܺϲ����Զ�����С����
 */
export async function translateBatch(options: TranslateOptions): Promise<{
  translations: Map<string, string>
  successCount: number
  error?: string
}> {
  const {
    texts, sourceLang, targetLang, baseURL, apiKey, model,
    glossary, batchSize = 100, onProgress
  } = options

  if (!apiKey) {
    return { translations: new Map(), successCount: 0, error: "API Key δ����" }
  }

  const client = new OpenAI({
    apiKey,
    baseURL,
    dangerouslyAllowBrowser: true,
    timeout: 30000,
    maxRetries: 2,
  })


  const textMap = new Map<string, TextItem[]>()
  for (const t of texts) {
    const key = t.text.trim()
    if (!textMap.has(key)) {
      textMap.set(key, [])
    }
    textMap.get(key)!.push(t)
  }
  const uniqueTexts = Array.from(textMap.entries()).map(([text, items]) => ({
    text: items[0].text,
    keyPath: items[0].keyPath,
    duplicateKeys: items.slice(1).map(i => i.keyPath),
  }))
  const dedupSaved = texts.length - uniqueTexts.length
  const allTexts = dedupSaved > 0 ? (uniqueTexts as any) : texts


    if (texts.length === 0) {
    return { translations: new Map(), successCount: 0 }
  }

  const supportsJson = !model.includes("reasoner") && !model.includes("pro")
  const translations = new Map<string, string>()
  let successCount = 0
  let hasError = false
  const totalBatches = Math.ceil(texts.length / batchSize)

  // ������������
  interface Batch {
    batchTexts: TextItem[]
    batchKeys: string[]
    index: number
  }

  const allBatches: Batch[] = []
  for (let b = 0; b < totalBatches; b++) {
    const batchTexts = texts.slice(b * batchSize, (b + 1) * batchSize)
    const batchKeys = batchTexts.map(t => t.keyPath)
    allBatches.push({ batchTexts, batchKeys, index: b })
  }

  // 并行执行批次（控制并发数 MAX_CONCURRENT）
  for (let start = 0; start < allBatches.length; start += MAX_CONCURRENT) {
    const concurrentBatches = allBatches.slice(start, start + MAX_CONCURRENT)

    const results = await Promise.allSettled(
      concurrentBatches.map(batch =>
        translateOneBatch(
          client, model, batch.batchTexts, batch.batchKeys,
          sourceLang, targetLang, glossary, supportsJson
        )
      )
    )

    for (let i = 0; i < results.length; i++) {
      const result = results[i]
      const batchIndex = concurrentBatches[i].index

      if (result.status === "fulfilled") {
        for (const [key, value] of result.value) {
          translations.set(key, value)
          successCount++
          // 传播翻译结果到重复的 keyPath
          const batchItem = concurrentBatches[i].batchTexts.find(t => t.keyPath === key)
          if (batchItem?.duplicateKeys) {
            for (const dk of batchItem.duplicateKeys) {
              translations.set(dk, value)
            }
          }
        }
      } else {
        hasError = true
      }
    }

    // ���Ȼص������µ���һ��ʧ�ܵ�����λ�ã�
    const completedUpTo = Math.min((start + MAX_CONCURRENT) * batchSize, texts.length)
    onProgress?.(completedUpTo, texts.length, "translating")
  }

  return {
    translations,
    successCount,
    ...(hasError ? { error: `�ɹ� ${successCount}/${texts.length} ������������ʧ��` } : {}),
  }
}

/** ���뵥������ */
async function translateOneBatch(
  client: OpenAI,
  model: string,
  batchTexts: TextItem[],
  batchKeys: string[],
  sourceLang: string,
  targetLang: string,
  glossary?: GlossaryEntry[],
  supportsJson?: boolean
): Promise<Map<string, string>> {
  const translations = new Map<string, string>()

  const systemPrompt = buildSystemPrompt(sourceLang, targetLang, glossary, supportsJson)

  const userContent =
    "Translate the following text items. Return a JSON object where each key is the keyPath and value is the translation:\n\n" +
    JSON.stringify(Object.fromEntries(batchTexts.map(t => [t.keyPath, t.text])), null, 2)

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
  if (!resultText) throw new Error("API ���ؿս��")

  // ���� JSON ��Ӧ
  const resultJson = JSON.parse(resultText)
  for (const key of batchKeys) {
    if (resultJson[key]) {
      translations.set(key, resultJson[key])
    }
  }

  return translations
}

function buildSystemPrompt(
  sourceLang: string, targetLang: string,
  glossary?: GlossaryEntry[],
  supportsJson?: boolean
): string {
  const srcName = LANG_MAP[sourceLang] ?? sourceLang
  const tgtName = LANG_MAP[targetLang] ?? targetLang

  let prompt = "You are a professional game localization translator. Translate the following " +
    srcName + " text to " + tgtName + "."

  if (glossary && glossary.length > 0) {
    prompt += "\n\nIMPORTANT: Maintain consistency for these terms:\n"
    for (const g of glossary) {
      prompt += "- " + g.source + " -> " + g.target + "\n"
    }
  }

  prompt +=
    "\nRules:\n" +
    "1. Keep all HTML/XML tags, format strings (%s, {0}, etc.), and special characters unchanged\n" +
    "2. Keep all variable placeholders like {name}, ${}, %d unchanged\n" +
    "3. Ensure proper context for game UI, quests, skills, and items\n" +
    "4. Maintain the original meaning and tone"

  if (supportsJson) {
    prompt += "\n5. Return ONLY a valid JSON object with keyPath -> translation mappings"
  }

  return prompt
}
