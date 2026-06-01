import type { FileManagerPluginDef } from "./filemanager"

function notAvailable(name: string): never {
  throw new Error("FileManager." + name + "() 仅在 Android 设备上可用")
}

export const WebFileManager: FileManagerPluginDef = {
  async checkPermission() { return { granted: false } },
  async requestPermission() { return { granted: false } },
  async pickApkFile() { notAvailable("pickApkFile") },
  async listApkEntries() { notAvailable("listApkEntries") },
  async readFileContent() { notAvailable("readFileContent") },
  async readApkEntry() { notAvailable("readApkEntry") },
  async pickOutputDir() { notAvailable("pickOutputDir") },
  async writeFileToDir() { notAvailable("writeFileToDir") },
  async createDirectory() { notAvailable("createDirectory") },
}
