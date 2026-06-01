import { registerPlugin } from "@capacitor/core"

export interface FileEntry {
  name: string
  path: string
  isDirectory: boolean
  size: number
  lastModified: number
}

export interface FileManagerPluginDef {
  checkPermission(): Promise<{ granted: boolean }>
  requestPermission(): Promise<{ granted: boolean }>
  listDirectory(options: { path: string }): Promise<{ entries: FileEntry[] }>
  readFile(options: { path: string }): Promise<{ content: string }>
  writeFile(options: { path: string; content: string }): Promise<{ success: boolean }>
  backupFile(options: { path: string }): Promise<{ backupPath: string }>
  fileExists(options: { path: string }): Promise<{ exists: boolean }>
}

const FileManager = registerPlugin<FileManagerPluginDef>("FileManager", {
  web: () => import("../core/web-filemanager").then(m => m.WebFileManager),
})

export default FileManager
