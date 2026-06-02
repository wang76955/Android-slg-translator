import FileManager from './filemanager'

const CACHE_PREFIX = 'slg-translator-cache:'

interface CacheRecord {
  sourceText: string
  translatedText: string
  updatedAt: number
}

type CacheStore = Record<string, CacheRecord>

let cacheStore: CacheStore = {}
let cacheLoaded = false
let pendingWrite = false

function hashString(value: string): string {
  let hash = 2166136261
  for (let i = 0; i < value.length; i++) {
    hash ^= value.charCodeAt(i)
    hash = Math.imul(hash, 16777619)
  }
  return (hash >>> 0).toString(36)
}

export function buildCacheContext(
  sourceLang: string,
  targetLang: string,
  model: string,
  glossary?: Array<{ source: string; target: string }>,
): string {
  const glossarySignature = glossary?.length
    ? glossary.map((entry) => entry.source + '=' + entry.target).sort().join('|')
    : ''
  return sourceLang + '|' + targetLang + '|' + model + '|' + hashString(glossarySignature)
}

function buildCacheKey(context: string, sourceText: string): string {
  return CACHE_PREFIX + context + '|' + hashString(sourceText)
}

export async function loadCache(): Promise<void> {
  if (cacheLoaded) return
  try {
    const result = await FileManager.loadTranslationCache()
    if (result.data && result.data !== '{}') {
      cacheStore = JSON.parse(result.data)
    }
  } catch {
    cacheStore = {}
  }

  migrateLegacyLocalStorageCache()
  cacheLoaded = true
}

export async function persistCache(): Promise<void> {
  if (!cacheLoaded || !pendingWrite || Object.keys(cacheStore).length === 0) return
  try {
    await FileManager.saveTranslationCache({ data: JSON.stringify(cacheStore) })
    pendingWrite = false
  } catch {
    // silent
  }
}

export function readCachedTranslation(context: string, sourceText: string): string | null {
  const cacheKey = buildCacheKey(context, sourceText)
  const record = cacheStore[cacheKey]
  if (record && record.sourceText === sourceText) {
    return record.translatedText
  }
  return null
}

export function writeCachedTranslation(context: string, sourceText: string, translatedText: string): void {
  const cacheKey = buildCacheKey(context, sourceText)
  cacheStore[cacheKey] = { sourceText, translatedText, updatedAt: Date.now() }
  pendingWrite = true
}

export function hasPendingWrite(): boolean {
  return pendingWrite
}

export function clearPendingFlag(): void {
  pendingWrite = false
}

export function cacheSize(): number {
  return Object.keys(cacheStore).length
}

function migrateLegacyLocalStorageCache(): void {
  const storage = getLocalStorage()
  if (!storage) return

  for (let index = 0; index < storage.length; index++) {
    const cacheKey = storage.key(index)
    if (!cacheKey?.startsWith(CACHE_PREFIX) || cacheStore[cacheKey]) continue

    try {
      const rawRecord = storage.getItem(cacheKey)
      if (!rawRecord) continue

      const record = JSON.parse(rawRecord) as CacheRecord
      if (!record.sourceText || !record.translatedText) continue

      cacheStore[cacheKey] = {
        sourceText: record.sourceText,
        translatedText: record.translatedText,
        updatedAt: record.updatedAt || Date.now(),
      }
      pendingWrite = true
    } catch {
      // Ignore invalid legacy entries.
    }
  }
}

function getLocalStorage(): Storage | null {
  try {
    if (typeof globalThis.localStorage === 'undefined') return null
    return globalThis.localStorage
  } catch {
    return null
  }
}
