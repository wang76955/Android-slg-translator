// === 平台无关核心类型定义 ===
// 这些类型在 Desktop (Electron) 和未来的 Android 版中共用

export interface TextItem {
  keyPath: string
  text: string
}

export interface ScanResult {
  filePath: string
  relativePath: string
  texts: TextItem[]
  rawData: any
}

export interface TranslationResult {
  keyPath: string
  sourceText: string
  translatedText: string
}

export interface BatchTranslateInput {
  texts: TextItem[]
  sourceLang: string
  targetLang: string
  glossary?: GlossaryEntry[]
  apiKey: string
  baseURL: string
  model: string
}

export interface GlossaryEntry {
  source: string
  target: string
}

export interface AiProvider {
  id: string
  name: string
  baseURL: string
  models: AiModel[]
}

export interface AiModel {
  id: string
  name: string
  supportsJsonMode: boolean
}

export interface ExportResult {
  filePath: string
  translated: any
}

// 进度回调
export type ProgressCallback = (current: number, total: number, phase: 'scanning' | 'translating' | 'exporting') => void
