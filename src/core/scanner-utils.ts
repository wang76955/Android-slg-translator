import type { TextItem } from "./types"

/**
 * ? JSON ?????????????
 * ???????? JS ????
 */
export function extractTexts(obj: any, prefix = ""): TextItem[] {
  const texts: TextItem[] = []
  if (typeof obj === "string") {
    if (/^\d+$/.test(obj)) return texts
    if (/^https?:\/\//.test(obj)) return texts
    if (/^\{[\w.]+\}$/.test(obj)) return texts
    if (/^%[\w.]+%$/.test(obj)) return texts
    texts.push({ keyPath: prefix, text: obj })
  } else if (Array.isArray(obj)) {
    obj.forEach((item, i) => texts.push(...extractTexts(item, `${prefix}[${i}]`)))
  } else if (obj !== null && typeof obj === "object") {
    for (const key of Object.keys(obj)) {
      const newPrefix = prefix ? `${prefix}.${key}` : key
      texts.push(...extractTexts(obj[key], newPrefix))
    }
  }
  return texts
}

/**
 * ?????????? JSON???????
 */
export function applyTranslations(obj: any, translations: Map<string, string>, prefix = ""): any {
  if (typeof obj === "string") {
    return translations.get(prefix) ?? obj
  }
  if (Array.isArray(obj)) {
    return obj.map((item, i) => applyTranslations(item, translations, `${prefix}[${i}]`))
  }
  if (obj !== null && typeof obj === "object") {
    const result: Record<string, any> = {}
    for (const key of Object.keys(obj)) {
      const newPrefix = prefix ? `${prefix}.${key}` : key
      result[key] = applyTranslations(obj[key], translations, newPrefix)
    }
    return result
  }
  return obj
}
