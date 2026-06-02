import { beforeEach, describe, expect, it, vi } from "vitest"

const fileManagerMock = {
  loadTranslationCache: vi.fn(),
  saveTranslationCache: vi.fn(),
}

vi.mock("./filemanager", () => ({ default: fileManagerMock }))

describe("translation cache migration", () => {
  beforeEach(() => {
    vi.resetModules()
    fileManagerMock.loadTranslationCache.mockReset()
    fileManagerMock.saveTranslationCache.mockReset()
    globalThis.localStorage = createMemoryStorage()
  })

  it("migrates legacy localStorage cache entries into native storage", async () => {
    const cache = await import("./translation-cache")
    const context = cache.buildCacheContext("en", "zh", "model-a")
    const cacheKey = `slg-translator-cache:${context}|${hashString("Hello")}`

    localStorage.setItem(cacheKey, JSON.stringify({
      sourceText: "Hello",
      translatedText: "你好",
      updatedAt: 1,
    }))

    fileManagerMock.loadTranslationCache.mockResolvedValue({ data: "{}" })
    fileManagerMock.saveTranslationCache.mockResolvedValue({ success: true })

    await cache.loadCache()

    expect(cache.readCachedTranslation(context, "Hello")).toBe("你好")

    await cache.persistCache()

    expect(fileManagerMock.saveTranslationCache).toHaveBeenCalledOnce()
    expect(fileManagerMock.saveTranslationCache.mock.calls[0][0].data).toContain("你好")
  })
})

function createMemoryStorage(): Storage {
  const store = new Map<string, string>()
  return {
    get length() { return store.size },
    clear: () => store.clear(),
    getItem: (key: string) => store.get(key) ?? null,
    key: (index: number) => Array.from(store.keys())[index] ?? null,
    removeItem: (key: string) => { store.delete(key) },
    setItem: (key: string, value: string) => { store.set(key, String(value)) },
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
