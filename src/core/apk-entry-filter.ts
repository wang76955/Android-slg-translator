import type { ApkEntry } from "./filemanager"

const BINARY_EXTENSIONS = new Set([
  "png", "jpg", "jpeg", "gif", "webp", "bmp", "ico",
  "mp3", "wav", "ogg", "aac", "flac", "m4a",
  "mp4", "webm", "avi", "mkv", "mov",
  "ttf", "otf", "woff", "woff2",
])

export function filterTranslatableApkEntries(
  entries: ApkEntry[],
  includeAndroidXml: boolean,
  sourceLang?: string,
): ApkEntry[] {
  return entries.filter((entry) => shouldIncludeApkEntry(entry, includeAndroidXml, sourceLang))
}

export function shouldIncludeApkEntry(
  entry: ApkEntry,
  includeAndroidXml: boolean,
  sourceLang?: string,
): boolean {
  const normalizedName = entry.name.replace(/\\/g, "/")
  const ext = normalizedName.split(".").pop()?.toLowerCase() || ""

  if (normalizedName.includes("/x-renpy/x-common/")) return false
  if (BINARY_EXTENSIONS.has(ext)) return false

  if (entry.fileType === "rpyc" || entry.fileType === "rpy") {
    return isSourceLanguageTranslationDir(normalizedName, sourceLang)
  }
  if (includeAndroidXml && isAndroidUiXml(entry, normalizedName)) return true

  return false
}

function isAndroidUiXml(entry: ApkEntry, normalizedName: string): boolean {
  if (entry.fileType !== "xml" && entry.fileType !== "strings") return false
  if (normalizedName.endsWith("AndroidManifest.xml")) return false
  if (normalizedName.startsWith("res/values/") || normalizedName.includes("/res/values/")) return true
  if (normalizedName.startsWith("res/layout/") || normalizedName.includes("/res/layout/")) return true
  return false
}

function isSourceLanguageTranslationDir(normalizedName: string, sourceLang?: string): boolean {
  const languageDir = getRenpyTranslationLanguageDir(normalizedName)
  if (!languageDir) return true
  if (!sourceLang) return true

  return getSourceLanguageAliases(sourceLang).has(normalizeLanguageName(languageDir))
}

function getRenpyTranslationLanguageDir(normalizedName: string): string | null {
  const parts = normalizedName.split("/")
  const translationIndex = parts.findIndex((part) => part === "tl" || part === "x-tl")
  if (translationIndex === -1) return null

  return parts[translationIndex + 1] || null
}

function getSourceLanguageAliases(sourceLang: string): Set<string> {
  const aliases: Record<string, string[]> = {
    zh: [
      "zh", "cn", "chinese", "schinese", "tchinese", "simplified_chinese",
      "traditional_chinese", "zh_cn", "zh_hans", "zh_tw", "zh_hant",
    ],
    en: ["en", "eng", "english", "none"],
    ja: ["ja", "jp", "jpn", "japanese"],
    ko: ["ko", "kr", "kor", "korean"],
    fr: ["fr", "fre", "fra", "french"],
    de: ["de", "ger", "deu", "german"],
    ru: ["ru", "rus", "russian"],
    pt: ["pt", "por", "portuguese", "brazilian", "brazilian_portuguese", "pt_br"],
    th: ["th", "tha", "thai"],
    vi: ["vi", "vie", "vietnamese"],
  }

  return new Set((aliases[sourceLang] || [sourceLang]).map(normalizeLanguageName))
}

function normalizeLanguageName(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/^x[-_]/, "")
    .replace(/[\s-]+/g, "_")
}
