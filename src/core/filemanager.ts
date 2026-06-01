import { registerPlugin } from "@capacitor/core"

/** 文件类型常量 */
export type FileType =
  | "json" | "xml" | "rpyc" | "csv" | "yaml"
  | "properties" | "lua" | "html" | "markdown" | "ini"
  | "text" | "strings" | "bytes" | "dat" | "rpy" | "unknown"

export interface ApkEntry {
  name: string
  size: number
  compressedSize: number
  /** 检测到的文件类型 */
  fileType: FileType
}

export interface FileManagerPluginDef {
  checkPermission(): Promise<{ granted: boolean }>
  requestPermission(): Promise<{ granted: boolean }>
  pickApkFile(): Promise<{ uri: string }>
  /** 扫描 APK 内所有可翻译文本文件，返回按类型分类的条目 */
  listApkEntries(options: { uri: string }): Promise<{ entries: ApkEntry[]; totalFiles: number }>
  /** 读取文件内容，根据类型自动处理（RPC2 解压等） */
  readFileContent(options: { uri: string; entryName: string }): Promise<{ content: string; fileType: FileType; fileExt: string }>
  /** 向后兼容 */
  readApkEntry(options: { uri: string; entryName: string }): Promise<{ content: string; name: string }>
  pickOutputDir(): Promise<{ uri: string }>
  getDefaultOutputDir(): Promise<{ uri: string; path: string }>
  writeFileToDir(options: { dirUri: string; fileName: string; content: string }): Promise<{ success: boolean }>
  createDirectory(options: { dirUri: string; dirName: string }): Promise<{ success: boolean; uri: string }>
}

const FileManager = registerPlugin<FileManagerPluginDef>("FileManager", {
  web: () => import("../core/web-filemanager").then(m => m.WebFileManager),
})

export default FileManager
