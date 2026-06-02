const EXACT_PHRASES: Record<string, Record<string, string>> = {
  "en>zh": {
    "back": "返回",
    "cancel": "取消",
    "chapter": "章节",
    "close": "关闭",
    "continue": "继续",
    "delete": "删除",
    "exit": "退出",
    "gallery": "画廊",
    "hide": "隐藏",
    "history": "历史",
    "load": "读取",
    "main menu": "主菜单",
    "menu": "菜单",
    "no": "否",
    "ok": "确定",
    "options": "选项",
    "preferences": "设置",
    "quit": "退出",
    "return": "返回",
    "save": "保存",
    "settings": "设置",
    "skip": "快进",
    "start": "开始",
    "start game": "开始游戏",
    "yes": "是",
    "dad": "爸爸",
    "father": "父亲",
    "girl": "女孩",
    "man": "男人",
    "mom": "妈妈",
    "mother": "母亲",
    "officer": "警官",
    "player": "玩家",
    "sister": "姐姐",
    "woman": "女人",
  },
  "zh>en": {
    "保存": "Save",
    "返回": "Back",
    "菜单": "Menu",
    "设置": "Settings",
    "开始": "Start",
    "开始游戏": "Start Game",
    "继续": "Continue",
    "退出": "Exit",
    "是": "Yes",
    "否": "No",
    "确定": "OK",
    "取消": "Cancel",
  },
}

const ALL_SOURCE_LANGS = Array.from(new Set(
  Object.keys(EXACT_PHRASES).map((key) => key.split(">")[0]),
))

export function getLocalTranslation(
  text: string,
  sourceLang: string,
  targetLang: string,
): string | null {
  const normalized = normalizePhrase(text)
  for (const candidateSourceLang of getCandidateSourceLangs(sourceLang)) {
    const exact = EXACT_PHRASES[`${candidateSourceLang}>${targetLang}`]?.[normalized]
    if (exact) return preserveOuterWhitespace(text, exact)

    const patternTranslation = translatePattern(normalized, candidateSourceLang, targetLang)
    if (patternTranslation) return preserveOuterWhitespace(text, patternTranslation)
  }

  return null
}

export function isKnownLocalPhrase(text: string, sourceLang?: string): boolean {
  if (!sourceLang) return false
  const normalized = normalizePhrase(text)
  return getCandidateSourceLangs(sourceLang).some((candidateSourceLang) =>
    Object.keys(EXACT_PHRASES)
      .filter((key) => key.startsWith(`${candidateSourceLang}>`))
      .some((key) => Boolean(EXACT_PHRASES[key][normalized]) || Boolean(translatePattern(normalized, candidateSourceLang, key.split(">")[1]))),
  )
}

function getCandidateSourceLangs(sourceLang: string): string[] {
  if (sourceLang === "auto") return ALL_SOURCE_LANGS
  return [sourceLang]
}

function translatePattern(normalized: string, sourceLang: string, targetLang: string): string | null {
  if (sourceLang === "en" && targetLang === "zh") {
    const episodeMatch = normalized.match(/^episode\s+(\d+)$/)
    if (episodeMatch) return `第 ${episodeMatch[1]} 集`

    const chapterMatch = normalized.match(/^chapter\s+(\d+)$/)
    if (chapterMatch) return `第 ${chapterMatch[1]} 章`

    const dayMatch = normalized.match(/^day\s+(\d+)$/)
    if (dayMatch) return `第 ${dayMatch[1]} 天`

    const partMatch = normalized.match(/^part\s+(\d+)$/)
    if (partMatch) return `第 ${partMatch[1]} 部分`
  }

  if (sourceLang === "zh" && targetLang === "en") {
    const episodeMatch = normalized.match(/^第\s*(\d+)\s*[集话]$/)
    if (episodeMatch) return `Episode ${episodeMatch[1]}`

    const chapterMatch = normalized.match(/^第\s*(\d+)\s*章$/)
    if (chapterMatch) return `Chapter ${chapterMatch[1]}`

    const dayMatch = normalized.match(/^第\s*(\d+)\s*天$/)
    if (dayMatch) return `Day ${dayMatch[1]}`
  }

  return null
}

function normalizePhrase(text: string): string {
  return text
    .trim()
    .toLowerCase()
    .replace(/[.!?。！？:：]+$/g, "")
    .replace(/\s+/g, " ")
}

function preserveOuterWhitespace(original: string, translated: string): string {
  const prefix = original.match(/^\s*/)?.[0] ?? ""
  const suffix = original.match(/\s*$/)?.[0] ?? ""
  return `${prefix}${translated}${suffix}`
}
