import React, { useState, useEffect, useCallback } from "react"
import FileManager from "../core/filemanager"
import type { FileEntry } from "../core/filemanager"

interface Props {
  onSelectDirectory: (path: string) => void
  selectedPath: string | null
}

const BASE_DIR = "/storage/emulated/0/Android/data"

const FileBrowser: React.FC<Props> = ({ onSelectDirectory, selectedPath }) => {
  const [currentPath, setCurrentPath] = useState(BASE_DIR)
  const [entries, setEntries] = useState<FileEntry[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadDirectory = useCallback(async (path: string) => {
    setLoading(true)
    setError(null)
    try {
      const result = await FileManager.listDirectory({ path })
      const sorted = result.entries.sort((a, b) => {
        if (a.isDirectory !== b.isDirectory)
          return a.isDirectory ? -1 : 1
        return a.name.localeCompare(b.name)
      })
      setEntries(sorted)
    } catch (e: any) {
      setError(e.message || "无法加载目录")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadDirectory(currentPath) }, [currentPath, loadDirectory])

  const navigateTo = (entry: FileEntry) => {
    if (entry.isDirectory) setCurrentPath(entry.path)
  }

  const goBack = () => {
    const parts = currentPath.split("/")
    if (parts.length > 4) {
      parts.pop()
      setCurrentPath(parts.join("/"))
    }
  }

  const buildCrumbs = () => {
    const parts = currentPath.split("/")
    const dataIndex = parts.indexOf("data")
    if (dataIndex < 0) return [{ label: "Android/data", path: BASE_DIR }]
    const crumbs = []
    for (let i = dataIndex; i < parts.length; i++) {
      crumbs.push({ label: parts[i], path: parts.slice(0, i + 1).join("/") })
    }
    return crumbs
  }

  const crumbs = buildCrumbs()

  return (
    <div className="border border-slate-200 rounded-xl bg-white overflow-hidden">
      <div className="flex items-center gap-1 px-4 py-2 border-b border-slate-100 bg-slate-50 text-xs overflow-x-auto whitespace-nowrap">
        {crumbs.map((crumb, i) => (
          <React.Fragment key={i}>
            {i > 0 && <span className="text-slate-300 shrink-0">/</span>}
            <button onClick={() => setCurrentPath(crumb.path)}
              className={`shrink-0 ${i === crumbs.length - 1 ? "text-slate-800 font-medium" : "text-blue-500 hover:text-blue-700"}`}>
              {crumb.label}
            </button>
          </React.Fragment>
        ))}
      </div>

      {crumbs.length > 1 && (
        <button onClick={goBack} className="w-full flex items-center gap-2 px-4 py-2 text-sm text-slate-500 hover:bg-slate-50 border-b border-slate-100">
          ← 返回上一级
        </button>
      )}

      <div className="max-h-80 overflow-y-auto">
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <div className="animate-spin w-6 h-6 border-2 border-blue-400 border-t-transparent rounded-full" />
          </div>
        ) : error ? (
          <div className="p-4 text-sm text-red-500 text-center">{error}</div>
        ) : entries.length === 0 ? (
          <div className="p-4 text-sm text-slate-400 text-center">该目录下没有文件</div>
        ) : (
          <div className="divide-y divide-slate-50">
            {entries.map((entry, i) => (
              <div key={i}
                onClick={() => entry.isDirectory && navigateTo(entry)}
                className={`flex items-center gap-3 px-4 py-2.5 ${entry.isDirectory ? "hover:bg-blue-50 cursor-pointer" : ""}`}>
                <span className="text-lg shrink-0">{entry.isDirectory ? "📁" : "📄"}</span>
                <span className="text-sm text-slate-700 truncate flex-1">{entry.name}</span>
                {entry.isDirectory && (
                  <button onClick={(e) => { e.stopPropagation(); onSelectDirectory(entry.path) }}
                    className={`text-xs px-3 py-1 rounded-full shrink-0 ${selectedPath === entry.path ? "bg-blue-500 text-white" : "bg-slate-100 text-slate-500 hover:bg-blue-100"}`}>
                    {selectedPath === entry.path ? "已选择" : "选择"}
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {selectedPath && (
        <div className="px-4 py-2 bg-green-50 border-t border-green-100 text-xs text-green-700 break-all">
          已选择：{selectedPath}
        </div>
      )}
    </div>
  )
}

export default FileBrowser
