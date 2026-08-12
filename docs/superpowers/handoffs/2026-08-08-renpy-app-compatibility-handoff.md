# Ren’Py 应用兼容性优化交接文档

更新时间：2026-08-09（Asia/Shanghai）  
工作区：`D:\文件翻译`  
交接目的：由新会话继续完成真实 Ren’Py 游戏的完整本地翻译、补丁构建、安装和真机验收。

## 一、当前结论

源码修复、批次 A 的构建链路、静态/单元测试、真实本地 ML Kit 翻译、补丁安装和目标游戏中文对白验收均已完成。

真实游戏“异世界天堂0.6”的本次本地翻译路线已经形成闭环：完整覆盖门禁通过，未选择“不完整测试补丁”，补丁 APK 已通过应用内流程安装，游戏主菜单和实际对白均显示中文。2026-08-09 又完成了单 APK 的旧存档与 rollback debug 兼容性回归，并恢复了最终字体修复候选；当前目标是 single APK，split session 对本目标不适用，但泛化 base + split 矩阵仍未执行；正式生产签名仍未提供。

## 二、已完成且已验证的工作

### 1. 源码和构建

- 修复真机 WebView 中 workshop 页面 IIFE 拼接导致的语法错误。
- 在 `apk-work\ui-redesign\patch_workshop_ui.py` 中加入顶层 IIFE 终止处理 `terminate_top_level_iife`。
- 在 `apk-work\ui-redesign\test_workshop_patch.py` 增加回归测试。
- 统一 `x-tl` 构建过滤契约，排除旧 Ren’Py 翻译 loose 文件。
- fresh 全量测试结果：`218` tests、`0` failures/errors、`1` explicit skip；组件测试分别为 `95`、`63`、`37`，均返回 0。

### 2. 最终应用 APK

- 文件：`D:\文件翻译\apk-work\slg-workshop-ui-signed.apk`
- 应用包名：`com.slgtranslator.app`
- 版本：`1.0.7`
- SHA-256：`731B25B459D57E23A2BD3BBB02C5407DD69491C62AE355A070105588BF4FDA41`
- 文件大小：`34,293,878` bytes；`versionCode=7` / `versionName=1.0.7`。
- APK v2/v3 签名验证通过。
- 已安装到真机：`MZNRYXEQS859O7GU`。

### 3. 应用自身真机验证

- `window.__slgHandleAndroidBack` 为 `function`。
- `.workshop-task-shell` 已挂载。
- 未再出现 IIFE `TypeError`。
- 应用入口可打开，应用内选择器和设置页面已验证。

### 4. 目标游戏扫描结果

- 游戏名称：异世界天堂0.6
- 包名：`com.yishijietiantang.com`
- `versionCode`：`1755587835`
- 无 split APK。
- Ren’Py：`RPC2`
- preferred slot：`2`
- protocol：`2`
- 兼容性：`SAFE`
- 字体覆盖：`28/28`
- 可翻译文件：`105`

### 5. 无 API Key 本地翻译路线

已确认应用使用本地模型，不需要 API Key：

```text
providerId=local
model=mlkit
apiKey=""
```

原生日志已经出现实际调用：

```text
FileManager.translateLocal
engine="mlkit"
sourceLang="en"
targetLang="zh"
```

## 三、上一会话最后可靠状态

最后可靠快照时间约为 `2026-08-08 20:01:50`。当时页面状态为 `translating`：

```text
当前脚本：约 9 / 10519
当前批次：30 / 132
唯一原文：7578
已验证：2848
缺失：4730
拒绝：0
不确定：0
compiled：0
错误：0
```

这只是历史中断快照，已被后续 `completed` 结果和真机证据取代；不要用这些旧计数判断当前发布状态。

## 三点五、2026-08-09 最新真机回归

- 最终字体修复候选：`E:\D-file-translation-renpy-release-20260809-fontfix\renpy-translated-font-runtimefix-home-debug-signed.apk`。
- SHA-256：`335166E2F0003C1BEB343CCBACC56F3E6DB9C6DFE3FBCC1E43296D51DB88FB28`；大小 `3,506,880,999` bytes；v1/v2/v3 验证通过；证书为本机 Android Debug certificate。
- 设备 `MZNRYXEQS859O7GU` / `PEMM20` 上最终候选恢复安装成功，`31-final-restored-ready/ready.png` 显示中文主菜单，`34-final-newgame-tap2/screen.png` 显示中文新游戏对白。
- 旧存档回归：使用原始代码的 debug 签名兼容回滚包安装后，`28-original-debug-old-save-selected/selected.png` 明确显示 `Use Jhonny`，`29-original-debug-old-save-loaded/loaded.png` 显示加载后的对白；最终候选恢复后 `32-final-old-save-regression/02-jhonny-confirm.png` 和 `03-old-save-loaded.png` 再次通过。
- 回滚说明：原始生产证书与 debug 候选证书不同，直接覆盖会被 Android 以签名冲突阻断。为保护数据，使用原始代码 + 当前 debug certificate 的测试包完成兼容性回归；这不替代生产证书回滚验证。
- 证书核对（2026-08-09）：原始游戏 APK 证书 SHA-256 为 `c802823da63011f16aaa5725b01c057deeb65b2ab06889153e30aaca1abdce25`；最终候选为 Android Debug 证书 `65e8a0967857d8536fc3a79f670a7f188fe17e2568b814f8849c2fb84f069730`。构建脚本当前只引用 debug keystore，未发现可复用的生产私钥。
- split session：真实目标为 single APK，对本目标不适用；更大批次的 base + split 安装集合仍未执行。
- 证据根目录：`D:\文件翻译\apk-work\qa\old-save-test-20260809\`；自动化证据：`D:\文件翻译\apk-work\qa\final-verification-20260809\`。

## 四、新会话继续顺序

1. 确认手机仍通过 ADB 连接，并唤醒屏幕。设备锁屏时间约 30 分钟。
2. 打开已安装的 `com.slgtranslator.app`，重新确认目标游戏和本地模型设置。
3. 继续等待完整翻译；不要选择“不完整测试补丁”。完整验收要求缺失和拒绝均归零。
4. 等待状态进入 `patching`，再进入 `completed`。
5. 记录 compiled count、编译路径、覆盖率和原生日志中的错误数。
6. 通过应用内流程安装生成的补丁 APK。
7. 启动 `com.yishijietiantang.com`，确认游戏能正常进入并显示中文对白。
8. 保存启动页、中文对白、补丁完成页和关键日志截图。
9. 最后再核对最终 APK、补丁 APK、日志和截图路径。

## 五、设备与调试信息

ADB 工具不在当前 PowerShell PATH，使用绝对路径：

```powershell
$adb = 'D:\文件翻译\.tools\platform-tools\adb.exe'
& $adb devices
& $adb shell input keyevent 224
```

上一会话使用的 CDP 地址为：

```text
ws://127.0.0.1:9222/devtools/page/5D77DB8233BA0DD3CBF99CB7378A5E11
```

页面 ID 可能变化；新会话应先查询当前 `/json` target，再使用：

```text
D:\文件翻译\.tools\cdp-eval-long.mjs
```

如果手机即将锁屏，执行 `input keyevent 224` 唤醒。`svc power stayon` 在该 OPPO 设备上连续失败过两次，未留下设置改动，不要继续反复重试。

## 六、测试和重建入口

除非最终 APK被证明损坏，否则不需要重复构建。必要时：

```powershell
Set-Location 'D:\文件翻译\apk-work\ui-redesign'
python -m pytest -q
python .\build_workshop_apk.py
```

关键文件：

```text
D:\文件翻译\docs\superpowers\plans\2026-08-07-renpy-app-compatibility-optimization.md
D:\文件翻译\apk-work\ui-redesign\patch_workshop_ui.py
D:\文件翻译\apk-work\ui-redesign\test_workshop_patch.py
D:\文件翻译\apk-work\ui-redesign\build_workshop_apk.py
D:\文件翻译\apk-work\slg-workshop-ui-signed.apk
```

## 七、本次清理记录

以下明确的临时/缓存文件已移入 Windows 回收站，可恢复；没有递归删除源码或证据目录：

```text
D:\文件翻译\apk-work\qa\tmp\installed-yishijietiantang-0.6.apk
D:\文件翻译\apk-work\qa\tmp\device-game-selected.apk
D:\文件翻译\apk-work\device-original-cached.apk
D:\文件翻译\apk-work\device-v9-picker-download2.xml
```

其中 `device-game-selected.apk` 与 `device-original-cached.apk` 的 SHA-256 均为：

```text
5839EB946A8EE14184E80F7F7B39872B4C5B361FD162F023CD920429C2624E31
```

必须保留的真机原始备份：

```text
D:\文件翻译\artifacts\device-backups\2026-08-08-异世界天堂0.6翻-original.apk
```

必须保留的最终应用 APK：

```text
D:\文件翻译\apk-work\slg-workshop-ui-signed.apk
```

## 八、验收完成标准

只有同时满足以下条件，才能在新会话中宣称整个任务完成：

- 翻译任务进入 `completed`。
- 缺失、拒绝、不确定均为 `0`，或有明确、可解释且经用户确认的例外。
- compiled count 与预期文件数一致，编译路径存在。
- 补丁 APK 能通过应用内安装流程安装。
- 目标游戏可以启动，不闪退、不停留在黑屏/空白页。
- 游戏实际对白显示中文，而不是只有应用 UI 中文化。
- 原生日志无未处理错误。
- 关键截图和日志已保存，并在最终报告中给出路径。

## 九、本次会话最终验收结果（2026-08-08）

- 设备：`MZNRYXEQS859O7GU` / `PEMM20` / Android 13。
- 应用：`com.slgtranslator.app` `1.0.7` / `versionCode 7`；fresh 全量自动化为 `218` tests、`1 skipped`、`0 failures`、`0 errors`。
- 真实翻译：`content://` 来源完成 `423/423` 批次；唯一原文 `10251`，总出现 `20864`，已验证 `10251`，缺失/拒绝/不确定均为 `0`；编译合并译文 `9907` 条。
- 真实安装：目标游戏 `com.yishijietiantang.com` 安装时间为 `2026-08-08 23:01:05`，设备上实际运行 APK SHA-256 为 `2d7f066b359c3480dc5f9cac9974bb8372aa364a92acde432a34554622e449f7`。
- 中文证据：`apk-work/device-game-current.png`、`apk-work/device-game-relaunch-01.png`（中文主菜单）与 `apk-work/device-game-dialogue-01.png`、`apk-work/device-game-relaunch-dialogue.png`（实际中文对白）；重新启动后再次通过 loading、主菜单和对白边界。
- 日志证据：`apk-work/device-game-final-log.txt`、`apk-work/device-game-relaunch-log.txt`；重新启动后的日志窗口 `FATAL EXCEPTION`/`Traceback` 数量为 `0`，前台 activity 为 `org.renpy.android.PythonSDLActivity`。
- 应用 APK：`apk-work/slg-workshop-ui-signed.apk`，SHA-256 `731B25B459D57E23A2BD3BBB02C5407DD69491C62AE355A070105588BF4FDA41`，大小 `34,293,878` bytes；`apksigner` v2/v3 均为 `true`。
- 当前结论：达到“本地 debug 签名发布候选”和真实设备可用验收；尚不能宣称正式上线。当前目标级唯一阻断是正式生产 keystore/certificate 未提供；泛化 split session 能力仍未执行，但不影响本 single APK 目标的适用性判断。

本次交接任务的代码、构建、真机单 APK、新游戏、旧存档和 debug rollback 证据已收口。对当前 single APK 目标，正式上线前只需补齐生产签名材料并在同一候选上重新验证；若后续扩展到 base + split 批次，再单独执行 split session 回归。在此之前应把产物标记为“本地 debug 签名发布候选”，不要标记为正式发布。
