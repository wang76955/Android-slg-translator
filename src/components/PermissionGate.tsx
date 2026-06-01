import React, { useState, useEffect } from "react"
import FileManager from "../core/filemanager"

interface Props {
  onGranted: () => void
}

const PermissionGate: React.FC<Props> = ({ onGranted }) => {
  const [granted, setGranted] = useState(false)
  const [checking, setChecking] = useState(true)

  useEffect(() => { checkPermission() }, [])

  const checkPermission = async () => {
    setChecking(true)
    try {
      const result = await FileManager.checkPermission()
      setGranted(result.granted)
      if (result.granted) onGranted()
    } catch (e) { console.error(e) }
    finally { setChecking(false) }
  }

  const handleRequest = async () => {
    try {
      const result = await FileManager.requestPermission()
      setGranted(result.granted)
      if (result.granted) onGranted()
    } catch (e) { console.error(e) }
  }

  if (checking) {
    return <div className="flex items-center justify-center min-h-screen bg-gray-50"><p className="text-slate-500 text-sm">正在检查权限...</p></div>
  }

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-50 p-6">
      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-8 max-w-md w-full text-center">
        <div className="text-5xl mb-4">📁</div>
        <h1 className="text-xl font-bold text-slate-800 mb-2">SLG 文本翻译</h1>
        <p className="text-sm text-slate-500 mb-6">
          本应用需要获取「所有文件访问权限」才能浏览游戏目录并翻译文本文件。
        </p>
        <button onClick={handleRequest}
          className="w-full py-3 bg-blue-500 text-white rounded-xl font-medium hover:bg-blue-600 active:bg-blue-700 transition-colors">
          前往授权
        </button>
        <button onClick={checkPermission}
          className="w-full py-3 mt-3 border border-slate-200 text-slate-600 rounded-xl text-sm hover:bg-slate-50 transition-colors">
          我已授权，检查状态
        </button>
      </div>
    </div>
  )
}

export default PermissionGate
