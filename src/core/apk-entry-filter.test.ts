import { describe, expect, it } from "vitest"
import { filterTranslatableApkEntries } from "./apk-entry-filter"
import type { ApkEntry } from "./filemanager"

function entry(name: string, fileType: ApkEntry["fileType"]): ApkEntry {
  return {
    name,
    size: 100,
    compressedSize: 80,
    fileType,
  }
}

describe("APK translatable entry filtering", () => {
  it("keeps only game Ren'Py files by default", () => {
    const entries = [
      entry("assets/game/script.rpyc", "rpyc"),
      entry("assets/x-renpy/x-common/00start.rpyc", "rpyc"),
      entry("res/values/strings.xml", "xml"),
      entry("assets/game/data.json", "json"),
    ]

    expect(filterTranslatableApkEntries(entries, false).map((item) => item.name))
      .toEqual(["assets/game/script.rpyc"])
  })

  it("optionally includes Android UI XML resources", () => {
    const entries = [
      entry("assets/game/script.rpyc", "rpyc"),
      entry("res/values/strings.xml", "xml"),
      entry("res/layout/main.xml", "xml"),
      entry("AndroidManifest.xml", "xml"),
    ]

    expect(filterTranslatableApkEntries(entries, true).map((item) => item.name))
      .toEqual([
        "assets/game/script.rpyc",
        "res/values/strings.xml",
        "res/layout/main.xml",
      ])
  })

  it("keeps only matching Ren'Py translation dirs for Chinese source", () => {
    const entries = [
      entry("assets/x-game/x-dialogue/x-episode1.rpyc", "rpyc"),
      entry("assets/x-game/x-tl/x-schinese/x-dialogue/x-episode1.rpyc", "rpyc"),
      entry("assets/x-game/x-tl/x-japanese/x-dialogue/x-episode1.rpyc", "rpyc"),
      entry("assets/x-game/x-tl/x-indonesian/x-dialogue/x-episode1.rpyc", "rpyc"),
    ]

    expect(filterTranslatableApkEntries(entries, false, "zh").map((item) => item.name))
      .toEqual([
        "assets/x-game/x-dialogue/x-episode1.rpyc",
        "assets/x-game/x-tl/x-schinese/x-dialogue/x-episode1.rpyc",
      ])
  })

  it("keeps only matching Ren'Py translation dirs for Japanese source", () => {
    const entries = [
      entry("assets/x-game/x-tl/x-schinese/x-dialogue/x-episode1.rpyc", "rpyc"),
      entry("assets/x-game/x-tl/x-japanese/x-dialogue/x-episode1.rpyc", "rpyc"),
    ]

    expect(filterTranslatableApkEntries(entries, false, "ja").map((item) => item.name))
      .toEqual(["assets/x-game/x-tl/x-japanese/x-dialogue/x-episode1.rpyc"])
  })
})
