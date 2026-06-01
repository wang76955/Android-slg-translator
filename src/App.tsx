import React, { useState, useCallback, useRef } from "react"
import PermissionGate from "./components/PermissionGate"
import TranslationConfig from "./components/TranslationConfig"
import type { LogEntry } from "./components/ProgressLog"
import ProgressLog from "./components/ProgressLog"
import FileManager from "./core/filemanager"
import type { ApkEntry } from "./core/filemanager"
import { extractTexts, applyTranslations } from "./core/scanner-utils"
import { translateBatch } from "./core/translator"
import { AI_PROVIDERS } from "./core/providers"

function getTimestamp(): string {
  return new Date().toTimeString().slice(0, 8)
}

const App: React.FC = () => {
  const [step, setStep] = useState<"permission" | "main">("permission")

  // APK
  const [apkUri, setApkUri] = useState<string | null>(null)
  const [apkName, setApkName] = useState("")
  const [jsonFiles, setJsonFiles] = useState<ApkEntry[]>([])
  const [scanning, setScanning] = useState(false)

  // 输出目录
  const [outputDirUri, setOutputDirUri] = useState<string | null>(null)

  // 翻译配置
  const [sourceLang, setSourceLang] = useState("zh")
  const [targetLang, setTargetLang] = useState("en")
  const [providerId, setProviderId] = useState("openai")
  const [selectedModel, setSelectedModel] = useState(AI_PROVIDERS[0].models[0].id)
  const [apiKey, setApiKey] = useState("")
  const [customBaseURL, setCustomBaseURL] = useState("")

  // 翻译进度
  const [translating, setTranslating] = useState(false)
  const [progress, setProgress] = useState({ current: 0, total: 0 })
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [result, setResult] = useState<{ success: boolean; count: number; error?: string } | null>(null)
  const logsRef = useRef<LogEntry[]>([])

  const addLog = useCallback((message: string, type: LogEntry["type"] = "info") => {
    const entry: LogEntry = { timestamp: getTimestamp(), message, type }
    logsRef.current = [...logsRef.current, entry]
    setLogs(logsRef.current)
  }, [])

  // 选择 APK
  const handlePickApk = async () => {
    try {
      const result = await FileManager.pickApkFile()
      setApkUri(result.uri)
      setApkName(result.uri.split("/").pop() || "Unknown.apk")
      setJsonFiles([])
      setResult(null)
      setLogs([])
      // 扫描 APK
      setScanning(true)
      addLog("正在解析 APK 文件...", "info")
      const entries = await FileManager.listApkEntries({ uri: result.uri })
      setJsonFiles(entries.entries)
      addLog(`发现 ${entries.totalJsonFiles} 个 JSON 文件`, "success")
      setScanning(false)
    } catch (e: any) {
      if (e.message !== "User cancelled") {
        addLog(`选择文件失败: ${e.message}`, "error")
      }
      setScanning(false)
    }
  }

  // 选择输出目录
  const handlePickOutput = async () => {
    try {
      const result = await FileManager.pickOutputDir()
      setOutputDirUri(result.uri)
      addLog("输出目录已选择", "success")
    } catch (e: any) {
      if (e.message !== "User cancelled") {
        addLog(`选择目录失败: ${e.message}`, "error")
      }
    }
  }

  // 开始翻译
  const handleTranslate = async () => {
    if (!apkUri || !outputDirUri || !apiKey || jsonFiles.length === 0) return

    setTranslating(true)
    setResult(null)
    setProgress({ current: 0, total: jsonFiles.length })
    logsRef.current = []
    setLogs([])

    const baseURL = providerId === "custom"
      ? customBaseURL
      : AI_PROVIDERS.find(p => p.id === providerId)?.baseURL || ""

    const outputDirName = "SLG-Translator-Output"
    let totalTranslated = 0
    let hasError = false

    // 创建输出目录结构
    try {
      await FileManager.createDirectory({ dirUri: outputDirUri, dirName: outputDirName })
    } catch (_) {}

    addLog(`开始翻译 ${jsonFiles.length} 个文件...`, "info")

    for (let i = 0; i < jsonFiles.length; i++) {
      const entry = jsonFiles[i]
      addLog(`[${i + 1}/${jsonFiles.length}] ${entry.name}`, "progress")

      try {
        // 1. 从 APK 读取文件
        const { content } = await FileManager.readApkEntry({ uri: apkUri, entryName: entry.name })
        const data = JSON.parse(content)
        const texts = extractTexts(data)

        if (texts.length === 0) {
          addLog("  无文本需要翻译，跳过", "info")
          setProgress({ current: i + 1, total: jsonFiles.length })
          continue
        }

        // 2. 调用 AI 翻译
        addLog(`  翻译 ${texts.length} 条文本...`, "info")
        const { translations, successCount } = await translateBatch({
          texts, sourceLang, targetLang, baseURL, apiKey,
          model: selectedModel, batchSize: 20,
        })

        if (successCount === 0) {
          addLog("  翻译失败，跳过", "error")
          hasError = true
          setProgress({ current: i + 1, total: jsonFiles.length })
          continue
        }

        // 3. 写入翻译后的文件到输出目录
        const translatedData = applyTranslations(data, translations)
        const outputContent = JSON.stringify(translatedData, null, 2)

        // 保持目录结构
        const parts = entry.name.split("/")
        let currentDirUri = outputDirUri
        for (let p = 0; p < parts.length - 1; p++) {
          try {
            const dirResult = await FileManager.createDirectory({
              dirUri: currentDirUri,
              dirName: parts[p],
            })
            if (dirResult.success) {
              currentDirUri = dirResult.uri
            }
          } catch (_) {}
        }

        await FileManager.writeFileToDir({
          dirUri: outputDirUri,
          fileName: parts[parts.length - 1],
          content: outputContent,
        })

        addLog(`  完成 (${successCount} 条)`, "success")
        totalTranslated += successCount
      } catch (e: any) {
        addLog(`  错误: ${e.message}`, "error")
        hasError = true
      }

      setProgress({ current: i + 1, total: jsonFiles.length })
    }

    setTranslating(false)

    if (totalTranslated > 0) {
      addLog(`全部完成！共翻译 ${totalTranslated} 条文本`, "success")
      setResult({ success: true, count: totalTranslated })
    } else {
      addLog("未成功翻译任何文本", "error")
      setResult({ success: false, count: 0, error: "未成功翻译任何文本" })
    }
  }

  const handlePermissionGranted = () => setStep("main")

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <header className="bg-white border-b border-slate-200 px-4 py-3 shrink-0">
        <h1 className="text-base font-bold text-slate-800">SLG 文本翻译</h1>
        <p className="text-xs text-slate-400 mt-0.5">选择 APK → 自动解析 → AI 翻译 → 导出</p>
      </header>

      <main className="flex-1 overflow-y-auto p-4 space-y-4 safe-bottom">
        {step === "permission" && (
          <PermissionGate onGranted={handlePermissionGranted} />
        )}

        {step === "main" && (
          <>
            {/* 第一步：选择 APK */}
            <div className="border border-slate-200 rounded-xl bg-white p-4">
              <h2 className="text-sm font-semibold text-slate-700 mb-3">1. 选择游戏 APK</h2>
              <button onClick={handlePickApk} disabled={scanning}
                className="w-full py-3 bg-blue-500 text-white rounded-xl text-sm font-medium
                  hover:bg-blue-600 disabled:opacity-50 transition-colors">
                {apkUri ? "重新选择 APK" : "选择 APK 文件"}
              </button>

              {apkUri && (
                <div className="mt-3 bg-green-50 border border-green-200 rounded-lg p-3">
                  <p className="text-xs text-green-700 break-all">已选择：{apkName}</p>
                  <p className="text-xs text-green-600 mt-1">
                    {jsonFiles.length > 0
                      ? `发现 ${jsonFiles.length} 个 JSON 文件`
                      : scanning ? "正在解析..." : ""}
                  </p>
                </div>
              )}

              {jsonFiles.length > 0 && (
                <div className="mt-3 max-h-40 overflow-y-auto border border-slate-100 rounded-lg divide-y divide-slate-50">
                  {jsonFiles.map((f, i) => (
                    <div key={i} className="flex items-center justify-between px-3 py-1.5 text-xs">
                      <span className="text-slate-600 truncate mr-2">{f.name}</span>
                      <span className="text-slate-400 shrink-0">{(f.size / 1024).toFixed(1)} KB</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* 第二步：选择输出目录 */}
            {jsonFiles.length > 0 && (
              <div className="border border-slate-200 rounded-xl bg-white p-4">
                <h2 className="text-sm font-semibold text-slate-700 mb-3">2. 选择输出目录</h2>
                <button onClick={handlePickOutput}
                  className="w-full py-2.5 border border-blue-300 text-blue-600 rounded-lg text-sm font-medium
                    hover:bg-blue-50 transition-colors">
                  {outputDirUri ? "更换输出目录" : "选择输出目录"}
                </button>
                {outputDirUri && (
                  <p className="mt-2 text-xs text-green-600">已选择输出目录 ✓</p>
                )}
              </div>
            )}

            {/* 第三步：翻译设置 */}
            {outputDirUri && jsonFiles.length > 0 && (
              <>
                <div className="border border-slate-200 rounded-xl bg-white p-4">
                  <h2 className="text-sm font-semibold text-slate-700 mb-3">3. 翻译设置</h2>
                  <TranslationConfig
                    sourceLang={sourceLang} targetLang={targetLang}
                    onSourceLangChange={setSourceLang} onTargetLangChange={setTargetLang}
                    providerId={providerId} onProviderChange={setProviderId}
                    selectedModel={selectedModel} onModelChange={setSelectedModel}
                    apiKey={apiKey} onApiKeyChange={setApiKey}
                    customBaseURL={customBaseURL} onCustomBaseURLChange={setCustomBaseURL}
                  />
                </div>

                <button onClick={handleTranslate} disabled={translating || !apiKey}
                  className="w-full py-3 bg-blue-500 text-white rounded-xl text-sm font-medium
                    hover:bg-blue-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
                  {translating ? "翻译中..." : "开始翻译"}
                </button>

                {(translating || logs.length > 0) && (
                  <ProgressLog
                    current={progress.current} total={progress.total}
                    logs={logs}
                    status={translating ? "translating" : result ? "done" : "idle"}
                    result={result}
                  />
                )}
              </>
            )}
          </>
        )}
      </main>

      <footer className="bg-white border-t border-slate-200 px-4 py-2 text-center text-xs text-slate-400 shrink-0">
        SLG 文本翻译工具 · Android 版
      </footer>
    </div>
  )
}

export default App
