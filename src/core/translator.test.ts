import { describe, expect, it } from "vitest"
import {
  buildCompactTranslationPayload,
  collectUniqueTranslatableTexts,
  parseTranslationResponse,
  protectTextForTranslation,
  restoreProtectedText,
} from "./translator"
import type { TextItem } from "./types"

const startGame = "\u5f00\u59cb\u6e38\u620f"
const save = "\u4fdd\u5b58"
const hello = "\u4f60\u597d"
const goodbye = "\u518d\u89c1"
const playerName = "\u73a9\u5bb6"

describe("translation batching efficiency", () => {
  it("deduplicates repeated source text and keeps duplicate key paths", () => {
    const texts: TextItem[] = [
      { keyPath: "a", text: startGame },
      { keyPath: "b", text: save },
      { keyPath: "c", text: startGame },
    ]

    const uniqueTexts = collectUniqueTranslatableTexts(texts)

    expect(uniqueTexts).toEqual([
      { keyPath: "a", text: startGame, duplicateKeys: ["c"] },
      { keyPath: "b", text: save, duplicateKeys: [] },
    ])
  })

  it("uses a compact array payload instead of keyPath JSON", () => {
    const payload = buildCompactTranslationPayload([
      { keyPath: "renpy/script.rpyc:str_1", text: hello },
      { keyPath: "renpy/script.rpyc:str_2", text: goodbye },
    ])

    expect(payload).toBe(`["${hello}","${goodbye}"]`)
    expect(payload).not.toContain("renpy/script.rpyc")
  })

  it("protects Ren'Py placeholders before sending text to AI", () => {
    const protectedText = protectTextForTranslation(`${hello}{color=#fff}[player_name]{/color}%s`)

    expect(protectedText.text).toBe(`${hello}__PH0____PH1____PH2____PH3__`)
    expect(restoreProtectedText(`${playerName}__PH0____PH1____PH2____PH3__`, protectedText))
      .toBe(`${playerName}{color=#fff}[player_name]{/color}%s`)
  })

  it("extracts JSON from markdown fenced model responses", () => {
    expect(parseTranslationResponse('```json\n{"translations":["Hello","Bye"]}\n```')).toEqual(["Hello", "Bye"])
  })
})
