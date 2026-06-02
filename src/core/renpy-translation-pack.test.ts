import { describe, expect, it } from "vitest"
import { buildRenPyTranslationFile, getRenPyLanguageName } from "./renpy-translation-pack"
import type { ApkEntry } from "./filemanager"
import type { TextItem } from "./types"

function entry(name: string): ApkEntry {
  return {
    name,
    size: 100,
    compressedSize: 80,
    fileType: "rpyc",
  }
}

describe("Ren'Py translation pack generation", () => {
  it("maps app language codes to Ren'Py language folders", () => {
    expect(getRenPyLanguageName("zh")).toBe("schinese")
    expect(getRenPyLanguageName("ja")).toBe("japanese")
  })

  it("generates a strings translation file under x-tl/x-schinese", () => {
    const texts: TextItem[] = [
      { keyPath: "ast_0", text: "One moment. Almost done." },
      { keyPath: "ast_1", text: "There. What do you need?" },
    ]
    const translations = new Map([
      ["ast_0", "稍等。马上就好。"],
      ["ast_1", "好了。你需要什么？"],
    ])

    const result = buildRenPyTranslationFile(
      entry("assets/x-game/x-dialogue/x-episode1.rpyc"),
      texts,
      translations,
      "zh",
    )

    expect(result.outputPath).toBe("assets/x-game/x-tl/x-schinese/x-dialogue/x-episode1.rpy")
    expect(result.content).toContain("translate schinese strings:")
    expect(result.content).toContain('old "One moment. Almost done."')
    expect(result.content).toContain('new "稍等。马上就好。"')
  })

  it("replaces an existing translation language directory", () => {
    const result = buildRenPyTranslationFile(
      entry("assets/x-game/x-tl/x-None/x-common.rpymc"),
      [{ keyPath: "ast_0", text: "Start" }],
      new Map([["ast_0", "开始"]]),
      "zh",
    )

    expect(result.outputPath).toBe("assets/x-game/x-tl/x-schinese/x-common.rpy")
  })
  it("can generate a default None language override", () => {
    const result = buildRenPyTranslationFile(
      entry("assets/x-game/x-dialogue/x-episode1.rpyc"),
      [{ keyPath: "ast_0", text: "Save" }],
      new Map([["ast_0", "Save translated"]]),
      "None",
    )

    expect(result.outputPath).toBe("assets/x-game/x-tl/x-None/x-dialogue/x-episode1.rpy")
    expect(result.content).toContain("translate None strings:")
  })
})
