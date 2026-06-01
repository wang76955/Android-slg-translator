import type { TextItem, FileType } from "./types"

// ============== 格式检测 ==============

/** 根据内容检测文本格式 */
export function detectTextFormat(content: string, fileType: FileType): "json" | "xml" | "rpyc" | "csv" | "text" {
  if (fileType === "json") return "json"
  if (fileType === "xml" || fileType === "strings") return "xml"
  if (fileType === "rpyc" || fileType === "rpy") return "rpyc"
  if (fileType === "csv") return "csv"

  // 内容检测
  const trimmed = content.trim()
  if (trimmed.startsWith("{")) return "json"
  if (trimmed.startsWith("<")) return "xml"
  if (trimmed.startsWith("[")) return "json"
  if (content.includes(",") && content.includes("\n")) return "csv"

  return "text"
}

// ============== 主提取入口 ==============

export function extractTexts(content: string, fileType: FileType, prefix = "", sourceLang?: string): TextItem[] {
  const format = detectTextFormat(content, fileType)

  switch (format) {
    case "json":
      try {
        const data = JSON.parse(content)
        return extractTextsFromJson(data, prefix, sourceLang)
      } catch {
        return extractTextsFromPlainText(content, prefix, sourceLang)
      }
    case "xml":
      return extractTextsFromXml(content, prefix, sourceLang)
    case "rpyc":
      return extractTextsFromRpyc(content, prefix, sourceLang)
    case "csv":
      return extractTextsFromCsv(content, prefix, sourceLang)
    case "text":
    default:
      return extractTextsFromPlainText(content, prefix, sourceLang)
  }
}

// ============== JSON 提取 ==============

export function extractTextsFromJson(obj: any, prefix = "", sourceLang?: string): TextItem[] {
  const texts: TextItem[] = []
  if (typeof obj === "string") {
    if (/^\d+$/.test(obj)) return texts
    if (/^https?:\/\//.test(obj)) return texts
    if (/^\{[\w.]+\}$/.test(obj)) return texts
    if (/^%[\w.]+%$/.test(obj)) return texts
    if (obj.trim().length === 0) return texts
    if (!shouldTranslate(obj, sourceLang)) return texts
    texts.push({ keyPath: prefix, text: obj })
  } else if (Array.isArray(obj)) {
    obj.forEach((item, i) => texts.push(...extractTextsFromJson(item, `${prefix}[${i}]`, sourceLang)))
  } else if (obj !== null && typeof obj === "object") {
    for (const key of Object.keys(obj)) {
      const newPrefix = prefix ? `${prefix}.${key}` : key
      texts.push(...extractTextsFromJson(obj[key], newPrefix, sourceLang))
    }
  }
  return texts
}

// ============== XML 提取 ==============

export function extractTextsFromXml(xmlContent: string, prefix = "", sourceLang?: string): TextItem[] {
  const texts: TextItem[] = []
  const lines = xmlContent.split("\n")
  let idx = 0

  for (const line of lines) {
    idx++
    // 提取 XML 标签间的文本内容: <tag>text</tag>
    const matches = line.matchAll(/>(.*?)<\//g)
    for (const m of matches) {
      const text = m[1].trim()
      if (text && shouldTranslate(text, sourceLang)) {
        texts.push({ keyPath: `${prefix}[line${idx}]`, text })
      }
    }

    // Android strings.xml: <string name="key">text</string>
    const stringMatch = line.match(/<string\s+name="([^"]+)">(.*?)<\/string>/)
    if (stringMatch) {
      const text = stringMatch[2].trim()
      if (text && shouldTranslate(text, sourceLang)) {
        texts.push({ keyPath: `${prefix}.${stringMatch[1]}`, text })
      }
    }

    // 属性值: android:text="..."
    const attrMatches = line.matchAll(/(?:android:|app:)?text="([^"]*)"/g)
    for (const m of attrMatches) {
      if (m[1] && shouldTranslate(m[1], sourceLang)) {
        texts.push({ keyPath: `${prefix}[attr${idx}]`, text: m[1] })
      }
    }
  }

  return texts
}

// ============== Ren'Py RPYC 提取 ==============

/**
 * 从 RPC2 解压后的文本中提取可翻译字符串
 * RPC2 解压后的数据是 Python pickle 序列化格式，包含大量 AST 节点
 * 我们用启发式方式从中提取文本
 */
export function extractTextsFromRpyc(decodedContent: string, prefix = "", sourceLang?: string): TextItem[] {
  if (looksLikeRenPySource(decodedContent)) {
    return extractTextsFromRenPySource(decodedContent, prefix, sourceLang)
  }

  const texts: TextItem[] = []
  const seen = new Set<string>()
  let idx = 0

  idx = appendRenPyAstVisibleTexts(decodedContent, texts, seen, prefix, sourceLang, idx)

  const translateRegex = /\bold\s+["']([^"']+)["']/g
  let match: RegExpExecArray | null
  while ((match = translateRegex.exec(decodedContent)) !== null) {
    const text = match[1].trim()
    if (text.length >= 2 && shouldTranslate(text, sourceLang) && !seen.has(text)) {
      seen.add(text)
      texts.push({ keyPath: `${prefix}tl_${idx++}`, text })
    }
  }

  return texts
}

function appendRenPyAstVisibleTexts(
  content: string,
  texts: TextItem[],
  seen: Set<string>,
  prefix: string,
  sourceLang: string | undefined,
  startIndex: number,
): number {
  let index = startIndex
  const markerRegex = /\b(?:renpy\.ast\.)?(Say|Menu)\b/gi
  const markers = Array.from(content.matchAll(markerRegex))

  for (let markerIndex = 0; markerIndex < markers.length; markerIndex++) {
    const marker = markers[markerIndex]
    const markerName = marker[1].toLowerCase()
    const segmentStart = marker.index ?? 0
    const segmentEnd = markers[markerIndex + 1]?.index ?? content.length
    const segment = content.slice(segmentStart, segmentEnd)
    const candidates = extractQuotedOrEscapedTexts(segment)
      .map((text) => text.trim())
      .filter((text) => text.length >= 2 && shouldTranslate(text, sourceLang))

    const visibleTexts = markerName === "say" || markerName === "menu"
      ? candidates
      : []

    for (const text of visibleTexts) {
      if (seen.has(text)) continue
      seen.add(text)
      texts.push({ keyPath: `${prefix}ast_${index++}`, text })
    }
  }

  return index
}

function extractQuotedOrEscapedTexts(segment: string): string[] {
  const texts: string[] = []
  const quoteRegex = /(["'])((?:[^"']|\\.)+?)\1/g
  let match: RegExpExecArray | null

  while ((match = quoteRegex.exec(segment)) !== null) {
    texts.push(match[2])
  }

  if (texts.length > 0) return texts

  const unicodeRegex = /(?:\\u[\da-fA-F]{4}){2,}/g
  while ((match = unicodeRegex.exec(segment)) !== null) {
    try {
      texts.push(match[0].replace(/\\u([\da-fA-F]{4})/g, (_, code) =>
        String.fromCharCode(parseInt(code, 16))
      ))
    } catch {
      // 忽略解码失败
    }
  }

  return texts
}

function looksLikeRenPySource(content: string): boolean {
  return content.split("\n").some((line) => {
    const trimmed = line.trim()
    return /^menu\s*:/.test(trimmed) ||
      /^(['"])(?:[^"'\\]|\\.)+\1\s*:/.test(trimmed) ||
      /^(?:[A-Za-z_]\w*\s+)?(['"])(?:[^"'\\]|\\.)+\1\s*$/.test(trimmed)
  })
}

function extractTextsFromRenPySource(content: string, prefix = "", sourceLang?: string): TextItem[] {
  const texts: TextItem[] = []
  const seen = new Set<string>()
  let index = 0

  const lines = content.split("\n")
  for (let lineNumber = 0; lineNumber < lines.length; lineNumber++) {
    const trimmed = lines[lineNumber].trim()
    if (!trimmed || trimmed.startsWith("#")) continue

    const optionMatch = trimmed.match(/^(['"])((?:[^"'\\]|\\.)+)\1\s*:/)
    const dialogueMatch = trimmed.match(/^(?:(?:[A-Za-z_]\w*|\w+\.[A-Za-z_]\w*)\s+)?(['"])((?:[^"'\\]|\\.)+)\1\s*(?:#.*)?$/)
    const text = optionMatch?.[2] ?? dialogueMatch?.[2]

    if (text && shouldTranslate(text, sourceLang) && !seen.has(text)) {
      seen.add(text)
      texts.push({ keyPath: `${prefix}rpy_${index++}`, text })
    }
  }

  return texts
}

// ============== CSV 提取 ==============

export function extractTextsFromCsv(csvContent: string, prefix = "", sourceLang?: string): TextItem[] {
  const texts: TextItem[] = []
  const lines = csvContent.split("\n")

  for (let row = 0; row < lines.length; row++) {
    const line = lines[row].trim()
    if (!line) continue

    // 简单 CSV 解析（跳过表头）
    if (row === 0) continue

    const cells = parseCsvLine(line)
    for (let col = 0; col < cells.length; col++) {
      const text = cells[col].trim()
      if (text && shouldTranslate(text, sourceLang)) {
        texts.push({ keyPath: `${prefix}[r${row}c${col}]`, text })
      }
    }
  }

  return texts
}

function parseCsvLine(line: string): string[] {
  const result: string[] = []
  let current = ""
  let inQuotes = false

  for (let i = 0; i < line.length; i++) {
    const ch = line[i]
    if (ch === '"') {
      inQuotes = !inQuotes
    } else if (ch === "," && !inQuotes) {
      result.push(current)
      current = ""
    } else {
      current += ch
    }
  }
  result.push(current)
  return result
}

// ============== 纯文本提取 ==============

export function extractTextsFromPlainText(textContent: string, prefix = "", sourceLang?: string): TextItem[] {
  const texts: TextItem[] = []
  const lines = textContent.split("\n")

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim()
    if (!line) continue

    // 跳过只有数字/URL 的行
    if (/^\d+$/.test(line)) continue
    if (/^https?:\/\//.test(line)) continue
    if (/^[{}[\]]+$/.test(line)) continue
    if (line.length < 2) continue

    if (shouldTranslate(line, sourceLang)) {
      texts.push({ keyPath: `${prefix}[L${i + 1}]`, text: line })
    }
  }

  return texts
}

// ============== 工具函数 ==============

function shouldTranslate(text: string, sourceLang?: string): boolean {
  if (!text || text.length < 2) return false
  const trimmed = text.trim()
  if (isNonDialogueTechnicalString(trimmed)) return false
  if (/^\d+$/.test(text)) return false
  if (/^https?:\/\//.test(text)) return false
  if (/^\{[\w.]+\}$/.test(text)) return false
  if (/^%[\w.]+%$/.test(text)) return false
  if (/^[0-9a-fA-F]{8,}$/.test(text)) return false  // 哈希值
  if (!matchesSourceLanguage(trimmed, sourceLang)) return false
  return true
}

function matchesSourceLanguage(text: string, sourceLang?: string): boolean {
  if (!sourceLang || sourceLang === "auto") return true

  if (sourceLang === "zh") return /[\u3400-\u9fff]/.test(text)
  if (sourceLang === "ja") return /[\u3040-\u30ff\u3400-\u9fff]/.test(text)
  if (sourceLang === "ko") return /[\uac00-\ud7af]/.test(text)
  if (sourceLang === "en") return /[A-Za-z]/.test(text)

  return true
}

function isNonDialogueTechnicalString(text: string): boolean {
  if (/^[A-Za-z0-9_./:-]+$/.test(text)) return true
  if (/[/\\][A-Za-z0-9_. -]+[/\\]/.test(text)) return true
  if (/^[A-Za-z_][\w.:-]*$/.test(text)) return true
  if (/\.(rpy|rpyc|rpym|py|png|jpg|jpeg|webp|ogg|mp3|wav|ttf|otf|json|xml)$/i.test(text)) return true
  return false
}

// ============== 翻译结果重组 ==============

/**
 * 将翻译结果应用到原始内容上，保持原格式
 */
export function applyTranslations(
  originalContent: string,
  translations: Map<string, string>,
  fileType: FileType
): string {
  const format = detectTextFormat(originalContent, fileType)

  switch (format) {
    case "json":
      return applyTranslationsToJson(originalContent, translations)
    case "xml":
      return applyTranslationsToXml(originalContent, translations)
    case "csv":
      return applyTranslationsToCsv(originalContent, translations)
    case "rpyc":
    case "text":
    default:
      return applyTranslationsToPlainText(originalContent, translations)
  }
}

export function applyTranslationsToJson(jsonContent: string, translations: Map<string, string>): string {
  try {
    const data = JSON.parse(jsonContent)
    const result = applyTranslationsToObject(data, translations, "")
    return JSON.stringify(result, null, 2)
  } catch {
    return jsonContent
  }
}

function applyTranslationsToObject(obj: any, translations: Map<string, string>, prefix = ""): any {
  if (typeof obj === "string") {
    return translations.get(prefix) ?? obj
  }
  if (Array.isArray(obj)) {
    return obj.map((item, i) => applyTranslationsToObject(item, translations, `${prefix}[${i}]`))
  }
  if (obj !== null && typeof obj === "object") {
    const result: Record<string, any> = {}
    for (const key of Object.keys(obj)) {
      const newPrefix = prefix ? `${prefix}.${key}` : key
      result[key] = applyTranslationsToObject(obj[key], translations, newPrefix)
    }
    return result
  }
  return obj
}

export function applyTranslationsToXml(xmlContent: string, translations: Map<string, string>): string {
  let result = xmlContent

  // 替换 <string name="key">text</string>
  result = result.replace(
    /(<string\s+name="([^"]+)">)(.*?)(<\/string>)/g,
    (match, open, key, text, close) => {
      const translated = translations.get(key) || translations.get(text.trim()) || text
      return open + translated + close
    }
  )

  // 替换标签间文本
  result = result.replace(
    /(>)([^<]+)(<\/)/g,
    (match, open, text, close) => {
      const trimmed = text.trim()
      if (trimmed && translations.has(trimmed)) {
        return open + translations.get(trimmed) + close
      }
      return match
    }
  )

  return result
}

export function applyTranslationsToCsv(csvContent: string, translations: Map<string, string>): string {
  const lines = csvContent.split("\n")
  const result: string[] = [lines[0]] // 保留表头

  for (let row = 1; row < lines.length; row++) {
    const line = lines[row].trim()
    if (!line) { result.push(""); continue }

    const cells = parseCsvLine(line)
    const translated = cells.map((cell, col) => {
      const trimmed = cell.trim()
      const translatedText = translations.get(`[r${row}c${col}]`)
      return translatedText || cell
    })

    result.push(translated.map(escapeCsvCell).join(","))
  }

  return result.join("\n")
}

function escapeCsvCell(cell: string): string {
  if (cell.includes(",") || cell.includes('"') || cell.includes("\n")) {
    return '"' + cell.replace(/"/g, '""') + '"'
  }
  return cell
}

export function applyTranslationsToPlainText(textContent: string, translations: Map<string, string>): string {
  const lines = textContent.split("\n")
  const result = lines.map((line, i) => {
    const trimmed = line.trim()
    if (trimmed && translations.has(trimmed)) {
      const key = `[L${i + 1}]`
      return translations.get(key) || translations.get(trimmed) || line
    }
    // 逐个匹配所有翻译
    for (const [original, translated] of translations) {
      if (line.includes(original)) {
        return line.replace(original, translated)
      }
    }
    return line
  })
  return result.join("\n")
}
