import { registerPlugin } from "@capacitor/core"

export interface ApkEntry {
  name: string
  size: number
  compressedSize: number
}

export interface FileManagerPluginDef {
  checkPermission(): Promise<{ granted: boolean }>
  requestPermission(): Promise<{ granted: boolean }>
  pickApkFile(): Promise<{ uri: string }>
  listApkEntries(options: { uri: string }): Promise<{ entries: ApkEntry[]; totalJsonFiles: number }>
  readApkEntry(options: { uri: string; entryName: string }): Promise<{ content: string; name: string }>
  pickOutputDir(): Promise<{ uri: string }>
  writeFileToDir(options: { dirUri: string; fileName: string; content: string }): Promise<{ success: boolean }>
  createDirectory(options: { dirUri: string; dirName: string }): Promise<{ success: boolean; uri: string }>
}

const FileManager = registerPlugin<FileManagerPluginDef>("FileManager", {
  web: () => import("../core/web-filemanager").then(m => m.WebFileManager),
})

export default FileManager
