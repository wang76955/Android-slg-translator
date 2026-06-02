import React, { useState, useCallback, useMemo, useRef } from "react"
import PermissionGate from "./components/PermissionGate"
import TranslationConfig from "./components/TranslationConfig"
import type { LogEntry } from "./components/ProgressLog"
import ProgressLog from "./components/ProgressLog"
import FileManager from "./core/filemanager"
import type { ApkEntry, ApkPatchFile, FileType } from "./core/filemanager"
import { extractTexts, applyTranslations } from "./core/scanner-utils"
import { translateBatch } from "./core/translator"
import { AI_PROVIDERS } from "./core/providers"
import { filterTranslatableApkEntries } from "./core/apk-entry-filter"
import { buildRenPyTranslationFile, getRenPyLanguageName, isRenPyEntry } from "./core/renpy-translation-pack"

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

const FILE_CONCURRENCY = 2
const TRANSLATION_BATCH_SIZE = 80

interface TranslationResult {
  success: boolean
  count: number
  error?: string
  patchedApkUri?: string
  patchedApkPath?: string
  patchedApkSigned?: boolean
  signatureVerified?: boolean
}

const App: React.FC = () => {
  const [step, setStep] = useState<"permission" | "main">("permission")

  // APK
  const [apkUri, setApkUri] = useState<string | null>(null)
  const [apkName, setApkName] = useState("")
  const [apkEntries, setApkEntries] = useState<ApkEntry[]>([])
  const [includeAndroidXml, setIncludeAndroidXml] = useState(false)
  const [scanning, setScanning] = useState(false)
  const [apkPackageName, setApkPackageName] = useState("")

  // 输出目录
  const [outputDirUri, setOutputDirUri] = useState<string | null>(null)

  // 翻译配置
  const [sourceLang, setSourceLang] = useState("auto")
  const [targetLang, setTargetLang] = useState("zh")
  const [providerId, setProviderId] = useState("openai")
  const [selectedModel, setSelectedModel] = useState(AI_PROVIDERS[0].models[0].id)
  const [apiKey, setApiKey] = useState("")
  const [customBaseURL, setCustomBaseURL] = useState("")
  const textFiles = useMemo(
    () => filterTranslatableApkEntries(apkEntries, includeAndroidXml, sourceLang),
    [apkEntries, includeAndroidXml, sourceLang],
  )
  const canMirrorExistingRenpyPack = useMemo(
    () => hasExistingRenPyLanguagePack(apkEntries, targetLang),
    [apkEntries, targetLang],
  )

  // 翻译进度
  const [translating, setTranslating] = useState(false)
  const [progress, setProgress] = useState({ current: 0, total: 0 })
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [result, setResult] = useState<TranslationResult | null>(null)
  const [installingPatch, setInstallingPatch] = useState(false)
  const logsRef = useRef<LogEntry[]>([])

  const addLog = useCallback((message: string, type: LogEntry["type"] = "info") => {
    const entry: LogEntry = { timestamp: getTimestamp(), message, type }
    logsRef.current = [...logsRef.current, entry]
    setLogs(logsRef.current)
  }, [])

  // 权限授权后
  const handlePermissionGranted = () => {
    setStep("main")
    initOutputDir()
  }

  // 选择 APK
  const handlePickApk = async () => {
    try {
      const result = await FileManager.pickApkFile()
      setApkUri(result.uri)
      setApkName(result.uri.split("/").pop() || "Unknown.apk")
      setApkEntries([])
      setResult(null)
      setLogs([])
      // 扫描 APK
      setScanning(true)
      addLog("正在扫描 APK 中的文本文件...", "info")
      const entries = await FileManager.listApkEntries({ uri: result.uri })
      setApkEntries(entries.entries)
      try {
        const pkgResult = await FileManager.getApkPackageName({ uri: result.uri })
        if (pkgResult.packageName) {
          setApkPackageName(pkgResult.packageName)
          addLog("识别到包名: " + pkgResult.packageName, "info")
        }
      } catch {}

      const filteredFiles = filterTranslatableApkEntries(entries.entries, includeAndroidXml, sourceLang)

      const byType = groupByType(filteredFiles)
      const typeSummary = Object.entries(byType)
        .map(([t, n]) => `${TYPE_LABELS[t as FileType] || t}×${n}`)
        .join(', ')
      addLog(`共发现 ${filteredFiles.length} 个可翻译文件（${typeSummary || "默认仅 Ren'Py"}）`, 'success')
      setScanning(false)
    } catch (e: any) {
      if (e.message !== "User cancelled") {
        addLog(`选择文件失败: ${e.message}`, "error")
      }
      setScanning(false)
    }
  }

  // 初始化输出目录
  const initOutputDir = async () => {
    try {
      const result = await FileManager.getDefaultOutputDir()
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
    if (!apkUri || textFiles.length === 0) return
    if (!apiKey && !canMirrorExistingRenpyPack) return

    setTranslating(true)
    setResult(null)
    setProgress({ current: 0, total: textFiles.length })
    logsRef.current = []
    setLogs([])

    const baseURL = providerId === "custom"
      ? customBaseURL
      : AI_PROVIDERS.find(p => p.id === providerId)?.baseURL || ""

    let totalTranslated = 0
    let hasError = false
    const renpyPatchFiles: ApkPatchFile[] = []
    let patchedApkUri = ""
    let patchedApkPath = ""
    let patchedApkSigned = false
    let signatureVerified = false

    // 创建输出根目录
    try {
      if (outputDirUri) {
        await FileManager.createDirectory({ dirUri: outputDirUri, dirName: "SLG-Translator-Output" })
      }
    } catch (_) {}

    addLog(`开始处理 ${textFiles.length} 个文件...`, "info")

    if (!apiKey && canMirrorExistingRenpyPack) {
      addLog(
        `检测到 APK 已内置 ${getRenPyLanguageName(targetLang)} Ren'Py 语言包，将直接镜像到 ${getRenPyLanguageName(sourceLang)}/None，无需 API 翻译。`,
        "info",
      )
    } else for (let batchStart = 0; batchStart < textFiles.length; batchStart += FILE_CONCURRENCY) {
      const batch = textFiles.slice(batchStart, batchStart + FILE_CONCURRENCY)
      await Promise.allSettled(batch.map((entry, offset) => (async () => {
        const index = batchStart + offset
        const typeTag = TYPE_LABELS[entry.fileType] || "?"
        addLog(`[${index + 1}/${textFiles.length}] [${typeTag}] ${entry.name}`, "progress")

        try {
          const { content, fileType } = await FileManager.readFileContent({ uri: apkUri, entryName: entry.name })
          const texts = extractTexts(content, fileType, "", sourceLang)
          const rpycHint = fileType === "rpyc" ? `（从 RPC2 解压数据中提取 ${texts.length} 条）` : ""
          if (rpycHint) addLog(`  ${rpycHint}`, "info")

          if (texts.length === 0) {
            addLog("  无文本需要翻译，跳过", "info")
            setProgress({ current: index + 1, total: textFiles.length })
            return
          }

          let lastLoggedBatch = 0
          addLog(`  翻译 ${texts.length} 条文本（小批并发，缓存优先）...`, "info")
          const { translations, successCount, error: transError } = await translateBatch({
            texts, sourceLang, targetLang, baseURL, apiKey,
            model: selectedModel, batchSize: TRANSLATION_BATCH_SIZE,
            onProgress: (current, total, phase, detail) => {
              if (phase !== "translating") return
              if (!detail?.totalBatches) {
                const savedCount = (detail?.cachedCount || 0) + (detail?.localRuleCount || 0)
                if (savedCount > 0) {
                  addLog(`  省 token：本地规则 ${detail?.localRuleCount || 0} 条，缓存 ${detail?.cachedCount || 0} 条`, "info")
                }
                return
              }

              if (detail.completedBatches === lastLoggedBatch) return
              lastLoggedBatch = detail.completedBatches || 0

              const failedText = detail.failedBatches ? `，失败批次 ${detail.failedBatches}` : ""
              const cachedText = detail.cachedCount ? `，缓存 ${detail.cachedCount}` : ""
              const localText = detail.localRuleCount ? `，本地 ${detail.localRuleCount}` : ""
              const splitText = detail.splitBatches ? `，自动拆批 ${detail.splitBatches}` : ""
              const etaText = detail.estimatedSecondsRemaining ? `，预计剩余 ${formatDuration(detail.estimatedSecondsRemaining)}` : ""
              addLog(
                `  批次 ${detail.completedBatches}/${detail.totalBatches} 完成，文本 ${current}/${total}${localText}${cachedText}${splitText}${failedText}${etaText}`,
                "progress",
              )
            },
          })

          if (successCount === 0) {
            addLog(transError ? `  翻译失败: ${transError}` : "  翻译失败，跳过", "error")
            hasError = true
            setProgress({ current: index + 1, total: textFiles.length })
            return
          }

          if (isRenPyEntry(entry)) {
            const translationFiles = [
              buildRenPyTranslationFile(entry, texts, translations, "None"),
              buildRenPyTranslationFile(entry, texts, translations, sourceLang),
            ]
            if (!canMirrorExistingRenpyPack) {
              translationFiles.unshift(buildRenPyTranslationFile(entry, texts, translations, targetLang))
            }
            const uniqueTranslationFiles = new Map<string, (typeof translationFiles)[number]>()

            for (const file of translationFiles) {
              uniqueTranslationFiles.set(file.outputPath, file)
            }

            for (const file of uniqueTranslationFiles.values()) {
              await writeOutputFile(file.outputPath, file.content)
              renpyPatchFiles.push({
                path: file.outputPath,
                content: file.content,
              })
              addLog(`  生成 Ren'Py 翻译包：${file.outputPath}`, "success")
            }
          } else {
            const outputContent = applyTranslations(content, translations, fileType)
            const ext = entry.name.substring(entry.name.lastIndexOf("."))
            const baseName = entry.name.substring(0, entry.name.lastIndexOf("."))
            await writeOutputFile(baseName + ".translated" + ext, outputContent)
          }

          totalTranslated += successCount
          addLog(`  完成：翻译 ${successCount} 条`, "success")
          setProgress({ current: index + 1, total: textFiles.length })
        } catch (e) {
          addLog(`  处理失败: ${e.message}`, "error")
          hasError = true
          setProgress({ current: index + 1, total: textFiles.length })
        }
      })()))
    }

    if (renpyPatchFiles.length > 0 || canMirrorExistingRenpyPack) {
      addLog(`正在生成 Ren'Py 补丁 APK...`, "info")
      try {
        const patchedApk = await FileManager.buildPatchedApk({
          uri: apkUri,
          files: renpyPatchFiles,
          outputDirUri,
          outputName: buildPatchedApkName(apkName),
          targetRenpyLanguage: getRenPyLanguageName(targetLang),
          sourceRenpyLanguage: getRenPyLanguageName(sourceLang),
        })
        patchedApkUri = patchedApk.uri
        patchedApkPath = patchedApk.path || patchedApk.uri
        patchedApkSigned = Boolean(patchedApk.signed)
        signatureVerified = Boolean(patchedApk.signatureVerified)
        addLog(
          `已生成补丁 APK：${patchedApkPath}（注入 ${patchedApk.fileCount} 个 .rpy，替换 ${patchedApk.replacedCount} 个旧文件，镜像 ${patchedApk.mirroredRenpyCount || 0} 个 Ren'Py 编译资源到 English/None）`,
          "success",
        )
        addLog(
          signatureVerified
            ? "已自动完成 APK 签名并通过校验，可直接尝试安装。"
            : "APK 已签名，但签名校验未通过，请不要安装。",
          signatureVerified ? "success" : "error",
        )
      } catch (e: any) {
        hasError = true
        addLog(`写入补丁 APK 失败: ${e.message}`, "error")
      }
    }

    setTranslating(false)
    setResult({
      success: !hasError,
      count: totalTranslated,
      ...(patchedApkPath ? { patchedApkUri, patchedApkPath, patchedApkSigned, signatureVerified } : {}),
      ...(hasError ? { error: "部分文件处理失败，请查看日志" } : {}),
    })
  }


  const handleUninstallAndInstall = async () => {
    const pkg = apkPackageName
    const uri = result?.patchedApkUri || (result?.patchedApkPath ? "file://" + result.patchedApkPath : "")
    if (!pkg || !uri) {
      addLog("缺少包名或补丁 APK 路径", "error")
      return
    }
    setInstallingPatch(true)
    try {
      addLog("正在打开系统卸载器，确认卸载后会继续安装补丁版...", "info")
      const installResult = await FileManager.uninstallAndInstallApk({ packageName: pkg, uri })
      if (installResult.needsPermission) {
        addLog("请在系统页面允许本应用安装未知来源应用", "info")
      } else if (installResult.uninstallCancelled) {
        addLog("原版游戏仍在手机上，补丁版会因签名不同无法覆盖安装", "error")
      } else {
        addLog("已打开补丁版安装器", "success")
        addLog("安装完成后建议启动游戏验证。若仍显示原语言，请清理游戏旧缓存/数据。", "info")
      }
    } catch (e: any) {
      addLog("操作失败: " + e.message, "error")
    } finally {
      setInstallingPatch(false)
    }
  }
  const handleInstallPatchedApk = async () => {
    const uri = result?.patchedApkUri || (result?.patchedApkPath ? `file://${result.patchedApkPath}` : "")
    if (!uri) return

    setInstallingPatch(true)
    try {
      const installResult = await FileManager.installApk({ uri })
      if (installResult.needsPermission) {
        addLog("请在系统页面允许本应用安装未知来源应用，然后回来再次点击安装。", "info")
      } else {
        addLog("已打开系统安装器。若提示签名冲突，请先卸载原版游戏。", "success")
        addLog("安装完成后如仍显示原语言，请点击“清理旧缓存/数据”让 Ren'Py 重新解包脚本。", "info")
      }
    } catch (e: any) {
      addLog(`打开安装器失败: ${e.message}`, "error")
    } finally {
      setInstallingPatch(false)
    }
  }

  const handleOpenGameSettings = async () => {
    const pkg = apkPackageName
    if (!pkg) {
      addLog("缺少包名，无法打开游戏系统设置", "error")
      return
    }

    setInstallingPatch(true)
    try {
      addLog("正在打开游戏系统设置。请进入“存储占用/存储”并清除数据或缓存，然后返回翻译器。", "info")
      await FileManager.openAppSettings({ packageName: pkg })
    } catch (e: any) {
      addLog(`打开游戏设置失败: ${e.message}`, "error")
    } finally {
      setInstallingPatch(false)
    }
  }

  const handleLaunchGame = async () => {
    const pkg = apkPackageName
    if (!pkg) {
      addLog("缺少包名，无法启动游戏", "error")
      return
    }

    setInstallingPatch(true)
    try {
      addLog("正在启动补丁版游戏，请选择原语言入口验证目标语言是否生效。", "info")
      await FileManager.launchApp({ packageName: pkg })
    } catch (e: any) {
      addLog(`启动游戏失败: ${e.message}`, "error")
    } finally {
      setInstallingPatch(false)
    }
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

  function hasExistingRenPyLanguagePack(entries: ApkEntry[], language: string): boolean {
    const renpyLanguage = getRenPyLanguageName(language)
    return entries.some((entry) => {
      const normalizedName = entry.name.replace(/\\/g, "/").toLowerCase()
      return normalizedName.includes(`/x-tl/x-${renpyLanguage.toLowerCase()}/`) ||
        normalizedName.includes(`/tl/${renpyLanguage.toLowerCase()}/`)
    })
  }

  function formatDuration(seconds: number): string {
    if (seconds < 60) return `${seconds}s`

    const minutes = Math.floor(seconds / 60)
    const restSeconds = seconds % 60
    return restSeconds > 0 ? `${minutes}m${restSeconds}s` : `${minutes}m`
  }

  function buildPatchedApkName(name: string): string {
    const decodedName = decodeURIComponent(name || "translated.apk")
    const cleanedName = decodedName.split(/[\\/]/).pop() || "translated.apk"
    const baseName = cleanedName.replace(/\.apk$/i, "") || "translated"
    return `${baseName}-patched-signed.apk`
  }

  async function writeOutputFile(outputPath: string, content: string): Promise<void> {
    const parts = outputPath.split("/")
    const fileName = parts.at(-1) || "translation.rpy"
    let currentDirUri = outputDirUri

    for (let index = 0; index < parts.length - 1; index++) {
      try {
        const result = await FileManager.createDirectory({ dirUri: currentDirUri, dirName: parts[index] })
        if (result.success && result.uri) currentDirUri = result.uri
      } catch (_) {}
    }

    await FileManager.writeFileToDir({
      dirUri: currentDirUri,
      fileName,
      content,
    })
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
                      ? `发现 ${textFiles.length} 个可翻译文件`
                      : scanning ? "正在扫描..." : ""}
                  </p>
                </div>
              )}

              {apkEntries.length > 0 && (
                <label className="mt-3 flex items-center justify-between rounded-lg border border-slate-100 bg-slate-50 px-3 py-2">
                  <span className="text-xs text-slate-600">翻译 Android 界面 XML</span>
                  <input
                    type="checkbox"
                    checked={includeAndroidXml}
                    onChange={(event) => setIncludeAndroidXml(event.target.checked)}
                    className="h-4 w-4 accent-blue-500"
                  />
                </label>
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

            {/* 第三步：翻译设置 */}
            {outputDirUri && textFiles.length > 0 && (
              <>
                <div className="border border-slate-200 rounded-xl bg-white p-4">
                  <h2 className="text-sm font-semibold text-slate-700 mb-3">3. 翻译设置</h2>
                  <TranslationConfig
                    sourceLang={sourceLang} targetLang={targetLang}
                    onSourceLangChange={setSourceLang} onTargetLangChange={setTargetLang}
                    providerId={providerId} onProviderChange={(id) => { setProviderId(id); const p = AI_PROVIDERS.find(x => x.id === id); if (p && p.models.length > 0) setSelectedModel(p.models[0].id); }}
                    selectedModel={selectedModel} onModelChange={setSelectedModel}
                    apiKey={apiKey} onApiKeyChange={setApiKey}
                    customBaseURL={customBaseURL} onCustomBaseURLChange={setCustomBaseURL}
                  />
                </div>

                <button onClick={handleTranslate} disabled={translating || (!apiKey && !canMirrorExistingRenpyPack)}
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
                    onInstallPatchedApk={handleInstallPatchedApk}
                    onUninstallAndInstall={handleUninstallAndInstall}
                    onOpenGameSettings={handleOpenGameSettings}
                    onLaunchGame={handleLaunchGame}
                    apkPackageName={apkPackageName}
                    installingPatch={installingPatch}
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
