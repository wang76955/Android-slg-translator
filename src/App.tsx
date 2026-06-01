import React, { useState, useCallback, useRef } from "react"
import PermissionGate from "./components/PermissionGate"
import TranslationConfig from "./components/TranslationConfig"
import type { LogEntry } from "./components/ProgressLog"
import ProgressLog from "./components/ProgressLog"
import FileManager from "./core/filemanager"
import type { ApkEntry, FileType } from "./core/filemanager"
import { extractTexts, applyTranslations } from "./core/scanner-utils"
import { translateBatch } from "./core/translator"
import { AI_PROVIDERS } from "./core/providers"

function getTimestamp(): string {
  return new Date().toTimeString().slice(0, 8)
}

/** 文件类型标签映射 */
const TYPE_LABELS: Record<FileType, string> = {
  json: "JSON", xml: "XML", rpyc: "RPYC", csv: "CSV",
  yaml: "YAML", properties: "Props", lua: "Lua",
  html: "HTML", markdown: "MD", ini: "INI",
  text: "TXT", strings: "STR", bytes: "Bytes",
  dat: "DAT", rpy: "RPY", unknown: "?"
}

const App: React.FC = () => {
  const [step, setStep] = useState<"permission" | "main">("permission")

  // APK
  const [apkUri, setApkUri] = useState<string | null>(null)
  const [apkName, setApkName] = useState("")
  const [textFiles, setTextFiles] = useState<ApkEntry[]>([])
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

  // 权限授权后
  const handlePermissionGranted = () => setStep("main")

  // 选择 APK
  const handlePickApk = async () => {
    try {
      const result = await FileManager.pickApkFile()
      setApkUri(result.uri)
      setApkName(result.uri.split("/").pop() || "Unknown.apk")
      setTextFiles([])
      setResult(null)
      setLogs([])
      // 扫描 APK
      setScanning(true)
      addLog("正在扫描 APK 中的文本文件...", "info")
      const entries = await FileManager.listApkEntries({ uri: result.uri })
      setTextFiles(entries.entries)
      const byType = groupByType(entries.entries)
      const typeSummary = Object.entries(byType)
        .map(([t, n]) => `${TYPE_LABELS[t as FileType] || t}×${n}`)
        .join(", ")
      addLog(`共发现 ${entries.totalFiles} 个文本文件（${typeSummary}）`, "success")
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
    if (!apkUri || !outputDirUri || !apiKey || textFiles.length === 0) return

    setTranslating(true)
    setResult(null)
    setProgress({ current: 0, total: textFiles.length })
    logsRef.current = []
    setLogs([])

    const baseURL = providerId === "custom"
      ? customBaseURL
      : AI_PROVIDERS.find(p => p.id === providerId)?.baseURL || ""

    const outputDirName = "SLG-Translator-Output"
    let totalTranslated = 0
    let hasError = false

    // 创建输出根目录
    try {
      await FileManager.createDirectory({ dirUri: outputDirUri, dirName: outputDirName })
    } catch (_) {}

    addLog(`开始处理 ${textFiles.length} 个文件...`, "info")

    for (let i = 0; i < textFiles.length; i++) {
      const entry = textFiles[i]
      const typeTag = TYPE_LABELS[entry.fileType] || "?"
      addLog(`[${i + 1}/${textFiles.length}] [${typeTag}] ${entry.name}`, "progress")

      try {
        // 1. 读取文件内容（RPC2 等自动解压）
        const { content, fileType } = await FileManager.readFileContent({ uri: apkUri, entryName: entry.name })

        // 2. 按格式提取文本
        const texts = extractTexts(content, fileType)
        const rpycHint = fileType === "rpyc" ? `（从 RPC2 解压数据中提取 ${texts.length} 条）` : ""
        if (rpycHint) addLog(`  ${rpycHint}`, "info")

        if (texts.length === 0) {
          addLog("  无文本需要翻译，跳过", "info")
          setProgress({ current: i + 1, total: textFiles.length })
          continue
        }

        // 3. 调用 AI 翻译
        addLog(`  翻译 ${texts.length} 条文本...`, "info")
        const { translations, successCount } = await translateBatch({
          texts, sourceLang, targetLang, baseURL, apiKey,
          model: selectedModel, batchSize: 20,
        })

        if (successCount === 0) {
          addLog("  翻译失败，跳过", "error")
          hasError = true
          setProgress({ current: i + 1, total: textFiles.length })
          continue
        }

        // 4. 按原格式重组翻译内容
        const outputContent = applyTranslations(content, translations, fileType)

        // 5. 保持目录结构写入
        const ext = entry.name.substring(entry.name.lastIndexOf("."))
        const baseName = entry.name.substring(0, entry.name.lastIndexOf("."))
        const translatedName = baseName + ".translated" + ext

        const parts = entry.name.split("/")
        let currentDirUri = outputDirUri
        for (let p = 0; p < parts.length - 1; p++) {
          try {
            const result = await FileManager.createDirectory({ dirUri: currentDirUri, dirName: parts[p] })
            if (result.success && result.uri) currentDirUri = result.uri
          } catch (_) {
            // 目录已存在
          }
        }

        // 写入翻译后文件
        await FileManager.writeFileToDir({
          dirUri: currentDirUri,
          fileName: translatedName,
          content: outputContent,
        })

        totalTranslated += successCount
        addLog(`  完成：翻译 ${successCount} 条`, "success")
        setProgress({ current: i + 1, total: textFiles.length })
      } catch (e: any) {
        addLog(`  处理失败: ${e.message}`, "error")
        hasError = true
        setProgress({ current: i + 1, total: textFiles.length })
      }
    }

    setTranslating(false)
    setResult({
      success: !hasError,
      count: totalTranslated,
      ...(hasError ? { error: "部分文件处理失败，请查看日志" } : {}),
    })
  }

  // 按类型分组统计
  function groupByType(files: ApkEntry[]): Record<string, number> {
    const groups: Record<string, number> = {}
    for (const f of files) {
      const t = f.fileType || "unknown"
      groups[t] = (groups[t] || 0) + 1
    }
    return groups
  }

  

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <header className="bg-white border-b border-slate-200 px-4 py-3 shrink-0">
        <h1 className="text-base font-bold text-slate-800">SLG 文本翻译</h1>
        <p className="text-xs text-slate-400 mt-0.5">选择 APK → 自动扫描 → AI 翻译 → 导出</p>
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
                    {textFiles.length > 0
                      ? `发现 ${textFiles.length} 个文本文件`
                      : scanning ? "正在扫描..." : ""}
                  </p>
                </div>
              )}

              {textFiles.length > 0 && (
                <div className="mt-3 max-h-48 overflow-y-auto border border-slate-100 rounded-lg divide-y divide-slate-50">
                  {textFiles.map((f, i) => (
                    <div key={i} className="flex items-center justify-between px-3 py-1.5 text-xs">
                      <div className="flex items-center gap-2 min-w-0 flex-1">
                        {/* 文件类型标签 */}
                        <span className={`shrink-0 px-1.5 py-0.5 rounded text-[10px] font-medium
                          ${f.fileType === "json" ? "bg-blue-50 text-blue-600" : ""}
                          ${f.fileType === "xml" ? "bg-orange-50 text-orange-600" : ""}
                          ${f.fileType === "rpyc" ? "bg-purple-50 text-purple-600" : ""}
                          ${f.fileType === "text" || f.fileType === "unknown" ? "bg-gray-50 text-gray-500" : ""}
                          ${!"json xml rpyc text unknown".includes(f.fileType) ? "bg-teal-50 text-teal-600" : ""}`}>
                          {TYPE_LABELS[f.fileType] || f.fileType}
                        </span>
                        <span className="text-slate-600 truncate">{f.name}</span>
                      </div>
                      <span className="text-slate-400 shrink-0 ml-2">{(f.size / 1024).toFixed(1)} KB</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* 第二步：选择输出目录 */}
            {textFiles.length > 0 && (
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
            {outputDirUri && textFiles.length > 0 && (
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
