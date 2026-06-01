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
): ApkEntry[] {
  return entries.filter((entry) => shouldIncludeApkEntry(entry, includeAndroidXml))
}

export function shouldIncludeApkEntry(entry: ApkEntry, includeAndroidXml: boolean): boolean {
  const normalizedName = entry.name.replace(/\\/g, "/")
  const ext = normalizedName.split(".").pop()?.toLowerCase() || ""

  if (normalizedName.includes("/x-renpy/x-common/")) return false
  if (BINARY_EXTENSIONS.has(ext)) return false

  if (entry.fileType === "rpyc" || entry.fileType === "rpy") return true
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
