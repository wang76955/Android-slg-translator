import OpenAI from 'openai'
import type { TextItem, GlossaryEntry, ProgressCallback } from './types'

/**
 * 核心翻译引擎 - 支持 OpenAI / DeepSeek / 任意兼容 API
 * 平台无关：只需 fetch/HTTP 能力
 */

const LANG_MAP: Record<string, string> = {
  zh: '中文', en: 'English', ja: '日本語',
  ko: '한국어', fr: 'Français', de: 'Deutsch'
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

/**
 * 批量翻译文本
 * 支持流式进度反馈
 */
export async function translateBatch(options: TranslateOptions): Promise<{
  translations: Map<string, string>
  successCount: number
  error?: string
}> {
  const {
    texts, sourceLang, targetLang, baseURL, apiKey, model,
    glossary, batchSize = 20, onProgress
  } = options

  if (!apiKey) {
    return { translations: new Map(), successCount: 0, error: 'API Key 未设置' }
  }

  const client = new OpenAI({
    apiKey,
    baseURL,
  })

  const supportsJson = !model.includes('reasoner')
  const translations = new Map<string, string>()
  let successCount = 0

  // 分批次翻译
  const totalBatches = Math.ceil(texts.length / batchSize)

  for (let b = 0; b < totalBatches; b++) {
    const batchTexts = texts.slice(b * batchSize, (b + 1) * batchSize)
    const batch: TextItem[] = []
    const batchKeys: string[] = []

    // 收集未翻译的文本
    for (const t of batchTexts) {
      batch.push(t)
      batchKeys.push(t.keyPath)
    }

    if (batch.length === 0) continue

    try {
      const systemPrompt = buildSystemPrompt(sourceLang, targetLang, glossary, supportsJson)

      const userContent =
        'Translate the following text items. Return a JSON object where each key is the keyPath and value is the translation:\n\n' +
        JSON.stringify(Object.fromEntries(batch.map(t => [t.keyPath, t.text])), null, 2)

      const completion = await client.chat.completions.create({
        model,
        messages: [
          { role: 'system', content: systemPrompt },
          { role: 'user', content: userContent },
        ],
        temperature: 0.3,
        ...(supportsJson ? { response_format: { type: 'json_object' } as const } : {}),
      })

      const resultText = completion.choices[0]?.message?.content
      if (!resultText) throw new Error('API 返回空结果')

      // 解析 JSON 响应
      const resultJson = JSON.parse(resultText)
      for (const key of batchKeys) {
        if (resultJson[key]) {
          translations.set(key, resultJson[key])
          successCount++
        }
      }
    } catch (err: any) {
      console.error('Batch ' + (b + 1) + '/' + totalBatches + ' failed:', err.message)
    }

    onProgress?.(Math.min((b + 1) * batchSize, texts.length), texts.length, 'translating')
  }

  return { translations, successCount }
}

function buildSystemPrompt(
  sourceLang: string, targetLang: string,
  glossary?: GlossaryEntry[],
  supportsJson: boolean
): string {
  const srcName = LANG_MAP[sourceLang] ?? sourceLang
  const tgtName = LANG_MAP[targetLang] ?? targetLang

  let prompt = 'You are a professional game localization translator. Translate the following ' +
    srcName + ' text to ' + tgtName + '.'

  // 术语表
  if (glossary && glossary.length > 0) {
    prompt += '\n\nIMPORTANT: Maintain consistency for these terms:\n'
    for (const g of glossary) {
      prompt += '- ' + g.source + ' -> ' + g.target + '\n'
    }
  }

  prompt +=
    '\nRules:\n' +
    '1. Keep all HTML/XML tags, format strings (%s, {0}, etc.), and special characters unchanged\n' +
    '2. Keep all variable placeholders like {name}, ${}, %d unchanged\n' +
    '3. Ensure proper context for game UI, quests, skills, and items\n' +
    '4. Maintain the original meaning and tone'

  if (supportsJson) {
    prompt += '\n5. Return ONLY a valid JSON object with keyPath -> translation mappings'
  }

  return prompt
}
