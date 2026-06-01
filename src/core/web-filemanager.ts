import type { FileManagerPluginDef, FileEntry } from "./filemanager"

function notAvailable(name: string): never {
  throw new Error("FileManager." + name + "() 仅在 Android 设备上可用")
}

export const WebFileManager: FileManagerPluginDef = {
  async checkPermission() { return { granted: false } },
  async requestPermission() { return { granted: false } },
  async listDirectory() { notAvailable("listDirectory") },
  async readFile() { notAvailable("readFile") },
  async writeFile() { notAvailable("writeFile") },
  async backupFile() { notAvailable("backupFile") },
  async fileExists() { notAvailable("fileExists") },
}
