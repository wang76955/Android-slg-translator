import React, { useEffect, useRef } from "react"

export interface LogEntry {
  timestamp: string
  message: string
  type: "info" | "success" | "error" | "progress"
}

interface Props {
  current: number
  total: number
  logs: LogEntry[]
  status: "idle" | "translating" | "done" | "error"
  result: { success: boolean; count: number; error?: string } | null
}

const ProgressLog: React.FC<Props> = ({ current, total, logs, status, result }) => {
  const progressPct = total > 0 ? Math.round((current / total) * 100) : 0
  const logEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [logs])

  const badgeColor = (type: string) => {
    switch (type) {
      case "success": return "text-green-400"
      case "error": return "text-red-400"
      case "progress": return "text-blue-400"
      default: return "text-slate-300"
    }
  }

  return (
    <div>
      {status === "translating" && (
        <div className="mb-3">
          <div className="flex justify-between text-xs text-slate-500 mb-1">
            <span>翻译进度</span>
            <span>{current} / {total}</span>
          </div>
          <div className="w-full h-2.5 bg-slate-100 rounded-full overflow-hidden">
            <div className="h-full bg-blue-400 rounded-full transition-all duration-300"
              style={{ width: progressPct + "%" }} />
          </div>
        </div>
      )}

      {logs.length > 0 && (
        <div className="bg-slate-900 rounded-lg p-3 max-h-48 overflow-y-auto text-xs font-mono">
          {logs.map((log, i) => (
            <div key={i} className="mb-1 last:mb-0 leading-relaxed">
              <span className="text-slate-500">{log.timestamp}</span>
              {" "}<span className={badgeColor(log.type)}>{log.message}</span>
            </div>
          ))}
          <div ref={logEndRef} />
        </div>
      )}

      {result && result.success && (
        <div className="mt-3 p-3 bg-green-50 border border-green-200 rounded-lg">
          <p className="text-sm text-green-700 font-medium">翻译完成</p>
          <p className="text-xs text-green-600 mt-1">
            共翻译 {result.count} 条文本，原始文件已备份为 .bak
          </p>
        </div>
      )}
      {result && !result.success && (
        <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-sm text-red-700 font-medium">翻译失败</p>
          <p className="text-xs text-red-600 mt-1">{result.error}</p>
        </div>
      )}
    </div>
  )
}

export default ProgressLog
