import React, { useState } from "react"
import FileManager from "../core/filemanager"
import { extractTexts } from "../core/scanner-utils"

interface ScanFileInfo {
  uri: string
  relativePath: string
  textCount: number
}

interface Props {
  directoryPath: string   // 现在是 SAF URI
  onScanComplete: (files: ScanFileInfo[], totalTexts: number) => void
  scanResult: { files: ScanFileInfo[]; totalTexts: number } | null
}

const ScanResultPanel: React.FC<Props> = ({ directoryPath, onScanComplete, scanResult }) => {
  const [scanning, setScanning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleScan = async () => {
    setScanning(true)
    setError(null)
    try {
      const files: ScanFileInfo[] = []
      const jsonFiles = await findJsonFiles(directoryPath)
      let totalTexts = 0
      for (const f of jsonFiles) {
        try {
          const { content } = await FileManager.readFileUri({ uri: f.uri })
          const data = JSON.parse(content)
          const texts = extractTexts(data)
          files.push({ uri: f.uri, relativePath: f.relativePath, textCount: texts.length })
          totalTexts += texts.length
        } catch {}
      }
      onScanComplete(files, totalTexts)
    } catch (e: any) {
      setError(e.message || "扫描失败")
    } finally {
      setScanning(false)
    }
  }

  return (
    <div className="border border-slate-200 rounded-xl bg-white p-4">
      <h2 className="text-sm font-semibold text-slate-700 mb-3">目录扫描</h2>
      <p className="text-xs text-slate-500 mb-3 break-all">路径：{directoryPath}</p>

      {!scanResult ? (
        <button onClick={handleScan} disabled={scanning}
          className="w-full py-2.5 bg-blue-500 text-white rounded-lg text-sm font-medium hover:bg-blue-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
          {scanning ? "正在扫描..." : "扫描此目录"}
        </button>
      ) : (
        <div>
          <div className="bg-green-50 border border-green-200 rounded-lg p-3 mb-3">
            <p className="text-sm text-green-700 font-medium">扫描完成</p>
            <p className="text-xs text-green-600 mt-1">
              发现 {scanResult.files.length} 个 JSON 文件，共 {scanResult.totalTexts} 条文本
            </p>
          </div>
          <div className="max-h-48 overflow-y-auto border border-slate-100 rounded-lg divide-y divide-slate-50 mb-3">
            {scanResult.files.slice(0, 50).map((f, i) => (
              <div key={i} className="flex items-center justify-between px-3 py-1.5 text-xs">
                <span className="text-slate-600 truncate mr-2">{f.relativePath}</span>
                <span className="text-slate-400 shrink-0">{f.textCount} 条</span>
              </div>
            ))}
            {scanResult.files.length > 50 && (
              <div className="px-3 py-1.5 text-xs text-slate-400 text-center">
                ...还有 {scanResult.files.length - 50} 个文件
              </div>
            )}
          </div>

          <button onClick={handleScan} disabled={scanning}
            className="w-full py-2 border border-slate-200 text-slate-500 rounded-lg text-xs hover:bg-slate-50 transition-colors">
            重新扫描
          </button>
        </div>
      )}

      {error && (
        <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-xs text-red-600">{error}</p>
        </div>
      )}
    </div>
  )
}

interface JsonFileInfo {
  uri: string
  relativePath: string
}

async function findJsonFiles(dirUri: string, baseUri?: string, maxDepth = 5, depth = 0): Promise<JsonFileInfo[]> {
  if (depth > maxDepth) return []
  const files: JsonFileInfo[] = []
  const base = baseUri || dirUri
  try {
    const { entries } = await FileManager.listDirectoryUri({ uri: dirUri })
    for (const entry of entries) {
      if (entry.isDirectory) {
        try {
          const sub = await FileManager.openSubDirectory({ parentUri: dirUri, dirName: entry.name })
          files.push(...await findJsonFiles(sub.uri, base, maxDepth, depth + 1))
        } catch {}
      } else if (entry.name.endsWith(".json")) {
        const fullUri = entry.uri || dirUri + "/" + entry.name
        files.push({
          uri: fullUri,
          relativePath: fullUri.replace(base + "/", "").replace(base, ""),
        })
      }
    }
  } catch {}
  return files
}

export default ScanResultPanel
export type { ScanFileInfo }
