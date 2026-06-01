import React, { useState, useEffect } from "react"
import FileManager from "../core/filemanager"

interface Props {
  onGranted: () => void
}

const PermissionGate: React.FC<Props> = ({ onGranted }) => {
  const [granted, setGranted] = useState(false)
  const [checking, setChecking] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [requesting, setRequesting] = useState(false)

  useEffect(() => { checkPermission() }, [])

  const checkPermission = async () => {
    setChecking(true)
    setError(null)
    try {
      const result = await FileManager.checkPermission()
      setGranted(result.granted)
      if (result.granted) onGranted()
    } catch (e: any) {
      setError(e?.message || "检查权限失败")
    }
    finally { setChecking(false) }
  }

  const handleRequest = async () => {
    setError(null)
    setRequesting(true)
    try {
      await FileManager.requestPermission()
    } catch (e: any) {
      setError(e?.message || "无法打开系统设置，请在系统设置中手动开启权限")
    }
    setRequesting(false)
  }

  if (checking) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <p className="text-slate-500 text-sm">正在检查权限...</p>
      </div>
    )
  }

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-50 p-6">
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-8 max-w-md w-full">
        <div className="text-5xl mb-4 text-center">📁</div>
        <h1 className="text-xl font-bold text-slate-800 mb-2 text-center">SLG 文本翻译</h1>
        <p className="text-sm text-slate-500 mb-6 text-center">
          本应用需要获取「所有文件访问权限」才能浏览游戏目录并翻译文本文件
        </p>

        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 mb-6 text-sm text-amber-800 space-y-2">
          <p className="font-medium">授权步骤：</p>
          <ol className="list-decimal list-inside space-y-1 text-amber-700">
            <li>点击下方按钮跳转到系统设置</li>
            <li>找到「所有文件访问权限」或「管理所有文件」</li>
            <li>开启开关，允许 SLG 文本翻译访问</li>
            <li>返回本 App，点击「我已授权，检查状态」</li>
          </ol>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">
            {error}
          </div>
        )}

        <button onClick={handleRequest} disabled={requesting}
          className="w-full py-3 bg-blue-500 text-white rounded-xl font-medium
            hover:bg-blue-600 active:bg-blue-700 disabled:opacity-50 transition-colors mb-3">
          {requesting ? "正在打开..." : "前往系统设置"}
        </button>

        <button onClick={checkPermission}
          className="w-full py-3 border border-slate-200 text-slate-600 rounded-xl text-sm
            hover:bg-slate-50 transition-colors">
          我已授权，检查状态
        </button>
      </div>
    </div>
  )
}

export default PermissionGate
