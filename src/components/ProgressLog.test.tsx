import React from "react"
import { renderToStaticMarkup } from "react-dom/server"
import { describe, expect, it } from "vitest"
import ProgressLog from "./ProgressLog"

describe("ProgressLog patch follow-up actions", () => {
  it("shows cache clearing and launch verification actions after patched APK generation", () => {
    const markup = renderToStaticMarkup(
      <ProgressLog
        current={1}
        total={1}
        logs={[]}
        status="done"
        result={{
          success: true,
          count: 12,
          patchedApkPath: "/storage/emulated/0/Download/game-patched.apk",
          patchedApkSigned: true,
        }}
        apkPackageName="oldcat.echoes"
        onInstallPatchedApk={() => {}}
        onUninstallAndInstall={() => {}}
        onOpenGameSettings={() => {}}
        onLaunchGame={() => {}}
      />,
    )

    expect(markup).toContain("清理旧缓存/数据")
    expect(markup).toContain("启动游戏验证")
    expect(markup).toContain("Ren’Py 旧缓存")
  })
})
