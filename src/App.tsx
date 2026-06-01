import React, { useState, useCallback, useRef } from "react"
import PermissionGate from "./components/PermissionGate"
import FileBrowser from "./components/FileBrowser"
import ScanResultPanel from "./components/ScanResultPanel"
import type { ScanFileInfo } from "./components/ScanResultPanel"
import TranslationConfig from "./components/TranslationConfig"
import ProgressLog from "./components/ProgressLog"
import type { LogEntry } from "./components/ProgressLog"
import FileManager from "./core/filemanager"
import { extractTexts, applyTranslations } from "./core/scanner-utils"
import { translateBatch } from "./core/translator"
import { AI_PROVIDERS } from "./core/providers"

type AppStep = "permission" | "browse" | "translate"

function getTimestamp(): string {
  const d = new Date()
  return d.toTimeString().slice(0, 8)
}

const App: React.FC = () => {
  const [step, setStep] = useState<AppStep>("permission")

  // 文件浏览
  const [selectedDir, setSelectedDir] = useState<string | null>(null)

  // 扫描结果
  const [scanResult, setScanResult] = useState<{ files: ScanFileInfo[]; totalTexts: number } | null>(null)

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

  const progressRef = useRef({ current: 0, total: 0 })
  const logsRef = useRef<LogEntry[]>([])
  const abortRef = useRef(false)

  const addLog = useCallback((message: string, type: LogEntry["type"] = "info") => {
    const entry: LogEntry = { timestamp: getTimestamp(), message, type }
    logsRef.current = [...logsRef.current, entry]
    setLogs(logsRef.current)
  }, [])

  const handlePermissionGranted = () => {
    setStep("browse")
  }

  const handleSelectDirectory = (path: string) => {
    setSelectedDir(path)
    setScanResult(null)
    setResult(null)
    setLogs([])
  }

  const handleScanComplete = (files: ScanFileInfo[], totalTexts: number) => {
    setScanResult({ files, totalTexts })
  }

  const handleProviderChange = (id: string) => {
    setProviderId(id)
    const provider = AI_PROVIDERS.find(p => p.id === id)
    if (provider) {
      setSelectedModel(provider.models[0].id)
    }
  }

  const handleTranslate = async () => {
    if (!selectedDir || !scanResult || !apiKey) return

    setTranslating(true)
    setResult(null)
    progressRef.current = { current: 0, total: scanResult.files.length }
    setProgress({ current: 0, total: scanResult.files.length })
    logsRef.current = []
    setLogs([])
    abortRef.current = false

    addLog("开始翻译...", "info")

    const baseURL = providerId === "custom"
      ? customBaseURL
      : AI_PROVIDERS.find(p => p.id === providerId)?.baseURL || ""

    let totalTranslated = 0
    let hasError = false

    for (let i = 0; i < scanResult.files.length; i++) {
      if (abortRef.current) break

      const file = scanResult.files[i]
      addLog(`[${i + 1}/${scanResult.files.length}] ${file.relativePath}`, "progress")

      try {
        // 1. 读取文件
        const { content } = await FileManager.readFile({ path: file.path })
        const data = JSON.parse(content)
        const texts = extractTexts(data)

        if (texts.length === 0) {
          addLog("  无文本需要翻译，跳过", "info")
          progressRef.current = { current: i + 1, total: scanResult.files.length }
          setProgress(progressRef.current)
          continue
        }

        // 2. 调用翻译
        addLog(`  正在翻译 ${texts.length} 条文本...`, "info")
        const { translations, successCount } = await translateBatch({
          texts,
          sourceLang,
          targetLang,
          baseURL,
          apiKey,
          model: selectedModel,
          batchSize: 20,
        })

        if (successCount === 0) {
          addLog("  翻译失败，跳过", "error")
          hasError = true
          progressRef.current = { current: i + 1, total: scanResult.files.length }
          setProgress(progressRef.current)
          continue
        }

        // 3. 备份原始文件
        addLog("  正在备份原始文件...", "info")
        await FileManager.backupFile({ path: file.path })
        addLog("  备份完成", "success")

        // 4. 应用翻译并写入
        const translatedData = applyTranslations(data, translations)
        await FileManager.writeFile({
          path: file.path,
          content: JSON.stringify(translatedData, null, 2),
        })
        addLog(`  翻译完成，已写入 (${successCount} 条)`, "success")
        totalTranslated += successCount

      } catch (e: any) {
        addLog(`  错误: ${e.message || "未知错误"}`, "error")
        hasError = true
      }

      progressRef.current = { current: i + 1, total: scanResult.files.length }
      setProgress(progressRef.current)
    }

    setTranslating(false)

    if (totalTranslated > 0) {
      addLog(`全部完成！共翻译 ${totalTranslated} 条文本`, "success")
      setResult({ success: true, count: totalTranslated })
    } else {
      addLog("翻译失败：未成功翻译任何文本", "error")
      setResult({ success: false, count: 0, error: "未成功翻译任何文本" })
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <header className="bg-white border-b border-slate-200 px-4 py-3 shrink-0">
        <h1 className="text-base font-bold text-slate-800">SLG 文本翻译</h1>
        <p className="text-xs text-slate-400 mt-0.5">Android 版 - 浏览目录 → 翻译文本 → 备份覆盖</p>
      </header>

      <main className="flex-1 overflow-y-auto p-4 space-y-4 safe-bottom">
        {step === "permission" && (
          <PermissionGate onGranted={handlePermissionGranted} />
        )}

        {step === "browse" && (
          <>
            <div className="space-y-1">
              <h2 className="text-sm font-semibold text-slate-700">1. 选择游戏数据目录</h2>
              <p className="text-xs text-slate-400">浏览到游戏存放在 /Android/data/ 下的目录</p>
            </div>

            <FileBrowser
              onSelectDirectory={handleSelectDirectory}
              selectedPath={selectedDir}
            />

            {selectedDir && (
              <>
                <ScanResultPanel
                  directoryPath={selectedDir}
                  onScanComplete={handleScanComplete}
                  scanResult={scanResult}
                />

                {scanResult && scanResult.totalTexts > 0 && (
                  <>
                    <div className="space-y-1">
                      <h2 className="text-sm font-semibold text-slate-700">3. 翻译设置</h2>
                    </div>

                    <div className="border border-slate-200 rounded-xl bg-white p-4">
                      <TranslationConfig
                        sourceLang={sourceLang}
                        targetLang={targetLang}
                        onSourceLangChange={setSourceLang}
                        onTargetLangChange={setTargetLang}
                        providerId={providerId}
                        onProviderChange={handleProviderChange}
                        selectedModel={selectedModel}
                        onModelChange={setSelectedModel}
                        apiKey={apiKey}
                        onApiKeyChange={setApiKey}
                        customBaseURL={customBaseURL}
                        onCustomBaseURLChange={setCustomBaseURL}
                      />
                    </div>

                    <button onClick={handleTranslate} disabled={translating || !apiKey}
                      className="w-full py-3 bg-blue-500 text-white rounded-xl text-sm font-medium
                        hover:bg-blue-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
                      {translating ? "翻译中..." : "开始翻译"}
                    </button>

                    {(translating || logs.length > 0) && (
                      <ProgressLog
                        current={progress.current}
                        total={progress.total}
                        logs={logs}
                        status={translating ? "translating" : result ? "done" : "idle"}
                        result={result}
                      />
                    )}
                  </>
                )}

                {scanResult && scanResult.totalTexts === 0 && (
                  <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-xl text-sm text-yellow-700">
                    该目录下未找到包含可翻译文本的 JSON 文件。
                  </div>
                )}
              </>
            )}

            <div className="text-center">
              <button onClick={() => setSelectedDir(null)}
                className="text-xs text-slate-400 hover:text-slate-600 underline">
                重新选择目录
              </button>
            </div>
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
