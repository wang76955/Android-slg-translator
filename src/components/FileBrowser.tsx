import React, { useState, useCallback } from "react"
import FileManager from "../core/filemanager"
import type { FileEntry } from "../core/filemanager"

interface Props {
  onSelectDirectory: (uri: string, name: string) => void
  selectedUri: string | null
}

const FileBrowser: React.FC<Props> = ({ onSelectDirectory, selectedUri }) => {
  const [currentUri, setCurrentUri] = useState<string | null>(null)
  const [currentName, setCurrentName] = useState("")
  const [entries, setEntries] = useState<FileEntry[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handlePickDir = async () => {
    setError(null)
    setLoading(true)
    try {
      const result = await FileManager.pickDirectory()
      setCurrentUri(result.uri)
      setCurrentName(result.name)
      await loadEntries(result.uri)
    } catch (e: any) {
      if (e.message !== "User cancelled") {
        setError(e.message || "选择目录失败")
      }
    } finally {
      setLoading(false)
    }
  }

  const loadEntries = async (uri: string) => {
    try {
      const result = await FileManager.listDirectoryUri({ uri })
      const sorted = result.entries.sort((a, b) => {
        if (a.isDirectory !== b.isDirectory)
          return a.isDirectory ? -1 : 1
        return a.name.localeCompare(b.name)
      })
      setEntries(sorted)
    } catch (e: any) {
      setError(e.message || "无法加载目录")
    }
  }

  const handleEntryClick = async (entry: FileEntry) => {
    if (!entry.isDirectory) return
    setLoading(true)
    setError(null)
    try {
      const result = await FileManager.openSubDirectory({
        parentUri: currentUri!,
        dirName: entry.name,
      })
      setCurrentUri(result.uri)
      setCurrentName(entry.name)
      await loadEntries(result.uri)
    } catch (e: any) {
      setError(e.message || "无法打开目录")
    } finally {
      setLoading(false)
    }
  }

  const handleSelectThisDir = () => {
    if (currentUri) {
      onSelectDirectory(currentUri, currentName)
    }
  }

  const handleBack = async () => {
    // SAF doesn't easily support going up the tree,
    // so just reopen picker
    handlePickDir()
  }

  return (
    <div className="border border-slate-200 rounded-xl bg-white overflow-hidden">
      {/* 顶部 */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-slate-50 border-b border-slate-100">
        <span className="text-sm font-medium text-slate-700 truncate mr-2">
          {currentName || "未选择目录"}
        </span>
        <button onClick={handlePickDir}
          className="text-xs px-3 py-1.5 bg-blue-500 text-white rounded-lg hover:bg-blue-600 shrink-0">
          {currentUri ? "更换目录" : "选择目录"}
        </button>
      </div>

      {/* 目录内容 */}
      {currentUri && (
        <>
          <div className="max-h-80 overflow-y-auto">
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <div className="animate-spin w-6 h-6 border-2 border-blue-400 border-t-transparent rounded-full" />
              </div>
            ) : error ? (
              <div className="p-4 text-sm text-red-500 text-center">{error}</div>
            ) : entries.length === 0 ? (
              <div className="p-4 text-sm text-slate-400 text-center">
                {currentName === "data" ? (
                  <div className="space-y-2">
                    <p>此目录无法直接浏览</p>
                    <p className="text-xs">
                      请点击「选择目录」，通过系统文件选择器找到游戏的实际数据目录
                    </p>
                    <button onClick={handlePickDir}
                      className="mt-2 px-4 py-2 bg-blue-500 text-white rounded-lg text-sm hover:bg-blue-600">
                      重新选择
                    </button>
                  </div>
                ) : (
                  "该目录下没有文件"
                )}
              </div>
            ) : (
              <div className="divide-y divide-slate-50">
                {entries.map((entry, i) => (
                  <div key={i}
                    onClick={() => handleEntryClick(entry)}
                    className={`flex items-center gap-3 px-4 py-2.5 ${entry.isDirectory ? "hover:bg-blue-50 cursor-pointer" : ""}`}>
                    <span className="text-lg shrink-0">
                      {entry.isDirectory ? "📁" : "📄"}
                    </span>
                    <span className="text-sm text-slate-700 truncate flex-1">{entry.name}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* 选择此目录按钮 */}
          <div className="px-4 py-2 border-t border-slate-100">
            <button onClick={handleSelectThisDir}
              className={`w-full py-2 rounded-lg text-sm font-medium transition-colors ${
                selectedUri === currentUri
                  ? "bg-green-500 text-white"
                  : "bg-blue-500 text-white hover:bg-blue-600"
              }`}>
              {selectedUri === currentUri ? "已选择此目录 ✓" : "选择此目录"}
            </button>
          </div>
        </>
      )}

      {/* 未选择时 */}
      {!currentUri && !loading && (
        <div className="p-8 text-center">
          <p className="text-sm text-slate-400 mb-4">
            点击上方按钮，使用系统文件选择器浏览到游戏的数据目录
          </p>
        </div>
      )}
    </div>
  )
}

export default FileBrowser
