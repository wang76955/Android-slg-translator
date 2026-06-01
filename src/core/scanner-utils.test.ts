import { describe, expect, it } from "vitest"
import { extractTextsFromPlainText, extractTextsFromRpyc } from "./scanner-utils"

const helloWorld = "\u4f60\u597d\uff0c\u4e16\u754c"
const dayOne = "\u7b2c 1 \u5929"
const dialogue = "\u8fd9\u662f\u7b2c\u4e00\u53e5\u53f0\u8bcd"
const save = "\u4fdd\u5b58"
const optionText = "\u7ee7\u7eed\u524d\u8fdb"
const imageText = "\u80cc\u666f\u56fe\u7247"
const speakerName = "\u827e\u4e3d\u4e1d"
const internalTitle = "\u5185\u90e8\u6807\u9898"
const debugText = "\u8c03\u8bd5\u6587\u672c"

describe("source language filtering", () => {
  it("keeps only Chinese-looking text when source language is zh", () => {
    const texts = extractTextsFromPlainText(
      [
        "This is an engine path",
        "common/renpy/display/core.py",
        helloWorld,
        "player_name",
        dayOne,
      ].join("\n"),
      "",
      "zh",
    )

    expect(texts.map((item) => item.text)).toEqual([helloWorld, dayOne])
  })

  it("filters Ren'Py engine and identifier strings before AI translation", () => {
    const texts = extractTextsFromRpyc(
      `renpy.ast.Say "renpy/common/00start.rpy" "oldcat.echoes" "${dialogue}" "config.version" renpy.ast.Menu "${save}"`,
      "",
      "zh",
    )

    expect(texts.map((item) => item.text)).toEqual([dialogue, save])
  })

  it("extracts only Ren'Py dialogue and menu options from source-like scripts", () => {
    const texts = extractTextsFromRpyc(
      [
        `define config.name = "${internalTitle}"`,
        "image bg room = \"images/room.png\"",
        `e "${dialogue}"`,
        "menu:",
        `    "${optionText}":`,
        "        jump next_day",
        `$ debug_label = "${debugText}"`,
      ].join("\n"),
      "",
      "zh",
    )

    expect(texts.map((item) => item.text)).toEqual([dialogue, optionText])
  })

  it("does not use broad CJK fallback for non-dialogue Ren'Py strings", () => {
    const texts = extractTextsFromRpyc(
      `renpy.ast.Image "${imageText}" renpy.ast.Python "${dayOne}" renpy.ast.Menu "${optionText}"`,
      "",
      "zh",
    )

    expect(texts.map((item) => item.text)).toEqual([optionText])
  })

  it("extracts Ren'Py speaker names, dialogue, and menu options", () => {
    const texts = extractTextsFromRpyc(
      `renpy.ast.Say "${speakerName}" "${dialogue}" renpy.ast.Menu "${optionText}"`,
      "",
      "zh",
    )

    expect(texts.map((item) => item.text)).toEqual([speakerName, dialogue, optionText])
  })
})
