/// <reference types="vite/client" />

interface FileEntry {
  name: string
  path: string
  isDirectory: boolean
  size: number
  lastModified: number
}

interface FileManagerPlugin {
  checkPermission(): Promise<{ granted: boolean }>
  requestPermission(): Promise<{ granted: boolean }>
  listDirectory(options: { path: string }): Promise<{ entries: FileEntry[] }>
  readFile(options: { path: string }): Promise<{ content: string }>
  writeFile(options: { path: string; content: string }): Promise<{ success: boolean }>
  backupFile(options: { path: string }): Promise<{ backupPath: string }>
  fileExists(options: { path: string }): Promise<{ exists: boolean }>
}

interface TranslationResult {
  success: boolean
  count: number
  error?: string
}

interface ScanSummary {
  files: ScanFileInfo[]
  totalTexts: number
}

interface ScanFileInfo {
  path: string
  relativePath: string
  textCount: number
}

declare global {
  interface Window {
    FileManager?: FileManagerPlugin
  }
}

export {}
