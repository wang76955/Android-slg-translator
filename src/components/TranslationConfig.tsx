import React from "react"
import { AI_PROVIDERS } from "../core/providers"

interface Props {
  sourceLang: string
  targetLang: string
  onSourceLangChange: (v: string) => void
  onTargetLangChange: (v: string) => void
  providerId: string
  onProviderChange: (id: string) => void
  selectedModel: string
  onModelChange: (v: string) => void
  apiKey: string
  onApiKeyChange: (v: string) => void
  customBaseURL: string
  onCustomBaseURLChange: (v: string) => void
}

const LANGUAGES = [
  { value: "auto", label: "自动识别" },
  { value: "zh", label: "中文" },
  { value: "en", label: "English" },
  { value: "ja", label: "日本語" },
  { value: "ko", label: "한국어" },
  { value: "fr", label: "Français" },
  { value: "de", label: "Deutsch" },
  { value: "ru", label: "Русский" },
  { value: "pt", label: "Português" },
  { value: "th", label: "ไทย" },
  { value: "vi", label: "Tiếng Việt" },
]

const TranslationConfig: React.FC<Props> = ({
  sourceLang, targetLang,
  onSourceLangChange, onTargetLangChange,
  providerId, onProviderChange,
  selectedModel, onModelChange,
  apiKey, onApiKeyChange,
  customBaseURL, onCustomBaseURLChange,
}) => {
  const provider = AI_PROVIDERS.find(p => p.id === providerId) || AI_PROVIDERS[0]
  const models = providerId === "custom"
    ? AI_PROVIDERS.find(p => p.id === "custom")!.models
    : provider.models

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs text-slate-500 mb-1">源语言</label>
          <select value={sourceLang} onChange={e => onSourceLangChange(e.target.value)}
            className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm bg-white">
            {LANGUAGES.map(l => <option key={l.value} value={l.value}>{l.label}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs text-slate-500 mb-1">目标语言</label>
          <select value={targetLang} onChange={e => onTargetLangChange(e.target.value)}
            className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm bg-white">
            {LANGUAGES.map(l => <option key={l.value} value={l.value}>{l.label}</option>)}
          </select>
        </div>
      </div>

      <div>
        <label className="block text-xs text-slate-500 mb-1">API 提供商</label>
        <select value={providerId} onChange={e => onProviderChange(e.target.value)}
          className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm bg-white">
          {AI_PROVIDERS.filter(p => p.id !== "custom").map(p => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
          <option value="custom">自定义 API</option>
        </select>
      </div>

      {providerId === "custom" && (
        <div>
          <label className="block text-xs text-slate-500 mb-1">自定义 Base URL</label>
          <input value={customBaseURL} onChange={e => onCustomBaseURLChange(e.target.value)}
            placeholder="https://your-api.com/v1"
            className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" />
        </div>
      )}

      <div>
        <label className="block text-xs text-slate-500 mb-1">翻译模型</label>
        <select value={selectedModel} onChange={e => onModelChange(e.target.value)}
          className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm bg-white">
          {models.map(m => (
            <option key={m.id} value={m.id}>{m.name}</option>
          ))}
        </select>
      </div>

      <div>
        <label className="block text-xs text-slate-500 mb-1">API Key</label>
        <input type="password" value={apiKey} onChange={e => onApiKeyChange(e.target.value)}
          placeholder={providerId === "openai" ? "sk-..." : "输入 API Key"}
          className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm" />
        <p className="text-xs text-slate-400 mt-0.5">密钥仅保存在本机，不会上传</p>
      </div>
    </div>
  )
}

export default TranslationConfig
