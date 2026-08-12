# Ren'Py 批次 A 发布检查表

> 适用范围：`docs/superpowers/plans/2026-08-07-renpy-app-compatibility-optimization.md` 的 Task 16，以及本次 C16/Task 19 发布机器矩阵和自动化门禁复核。
>
> 当前状态（2026-08-09）：本地 ML Kit / `content://` / 单 APK / 新游戏中文菜单与对白路线已通过验收；旧存档与 rollback 已完成单 APK debug 兼容性回归；兼容性阻断 UI 修复已通过真机验证；full discover fresh 为 `219` tests、`0` failures/errors、`1` explicit skip。工具 APK v1.0.7 与最终游戏字体修复候选的 v2/v3 签名均已通过。当前真实目标是 single APK，split session 对本目标不适用；泛化 split 矩阵仍未执行，正式生产签名未提供，因此当前结论是“本地 debug 签名发布候选”，不是正式上线完成。

> 真机复验更新（2026-08-08）：前置快照中的 `content://` 菜单注入 FAIL 已被 resolved-copy 修复并重新验证。设备 `MZNRYXEQS859O7GU` / `PEMM20` 上真实来源完成 `423/423` 批次，唯一原文 `10251`、总出现 `20864`、已验证 `10251`、缺失/拒绝/不确定均为 `0`、字体 `28/28`、编译合并 `9907` 条；补丁已安装，主菜单和实际中文对白均可见。残余回归见 §7。

> 真机复验更新（2026-08-09）：最终字体修复候选 `E:\D-file-translation-renpy-release-20260809-fontfix\renpy-translated-font-runtimefix-home-debug-signed.apk`（SHA-256 `335166E2F0003C1BEB343CCBACC56F3E6DB9C6DFE3FBCC1E43296D51DB88FB28`）已恢复安装。`apk-work/qa/old-save-test-20260809/31-final-restored-ready/ready.png` 显示中文主菜单，`32-final-old-save-regression/02-jhonny-confirm.png` 与 `03-old-save-loaded.png` 证明 `Jhonny` 旧存档可读，`34-final-newgame-tap2/screen.png` 显示中文新游戏对白；对应日志均无 `FATAL EXCEPTION`/`Traceback`。回滚使用原始代码的 debug 签名兼容包，不等同于生产证书回滚。

> 本次问题修复验证（2026-08-09）：工具 APK `apk-work/slg-workshop-ui-signed.apk`（SHA-256 `BC0639BEAD0C198B7DD3DAE9A5D196F02B5AFDAD1262D554929372143CBBED83`）保留数据覆盖安装到 `MZNRYXEQS859O7GU`；重新选择 `mayfly.SLLXXL` 后，页面进入明确的 `EXTRACT_ONLY` 阻断态，只显示“重新选择 APK”，会话保持 `translating:false`，无应用崩溃签名。证据：`apk-work/qa/bug-start-translation-20260809/fixed-extract-only-blocked.png`、`fixed-cdp-state.json`。

## 1. 发布原则

- 所有未知格式、未知 RPYC 代际和不完整元数据都必须保守失败；`EXTRACT_ONLY` 不得进入当前 writer。
- `missing`、`rejected`、collision、uncertain、字体缺字和 validator 失败必须可诊断、可复现、可阻断。
- `not-run` 不是 `0`，`allowed` 不是 `success`，fixture 通过不是设备启动通过。
- `single APK`（单 APK）和 `base + split` 必须分别记录；split 必须在同一个 PackageInstaller session 中安装完整集合。
- 高级 dialogue ID 模式默认关闭。只有 extractor、writer、AST 版本和 rollback 能力全部有证据时才允许开启；否则使用全局 string map。

## 2. 自动化预检

在 PowerShell 中执行：

```powershell
Set-Location 'D:\文件翻译\apk-work\ui-redesign'
python -m py_compile patch_workshop_ui.py test_workshop_patch.py test_fast_scanner.py test_translation_quality.py test_translation_coverage.py test_engine_performance.py test_built_apk.py
python -m unittest test_fast_scanner.py -v
python -m unittest test_workshop_patch.py -v
python -m unittest test_translation_quality.py test_translation_coverage.py test_engine_performance.py -v
python -m unittest discover -s . -p 'test_*.py' -v
```

自动化门禁记录：

| 检查项 | 通过标准 | 证据文件/输出 | 状态 |
|---|---|---|---|
| Python syntax | 所有目标 Python 文件 `py_compile` 返回 0 | Task 19 fresh 命令返回 0 | PASS |
| scanner contract | 无失败；生成物缺失时只能有明确外部条件 skip | `test_fast_scanner.py`：`95` tests，OK | PASS |
| workshop contract | 无失败；UI/构建契约保持可执行 | `test_workshop_patch.py`：`64` tests，OK | PASS |
| translation quality / coverage / performance | 无失败；真实审计缺输入时保留显式 skip | 合计 `37` tests，OK，`1` 个 `audit APK/extracted texts not present` skip | PASS |
| full discover | 无失败；每个 skip 在本清单第 6 节登记原因 | `apk-work/qa/final-verification-20260809/full_discover_after_ui_block_fix.txt`：`219` tests，0 failures/errors，`1` 个明确 skip | PASS |
| diff hygiene | `git diff --check` 返回 0 | `apk-work/qa/final-verification-20260809/git_diff_check.txt`，返回 0 | PASS |

任何失败都必须在修复并重新运行后才能继续；不能用删测试、放宽断言或隐藏异常来清绿。

## 3. APK 构建和原生 helper 门禁

```powershell
Set-Location 'D:\文件翻译\apk-work\ui-redesign'
python build_workshop_apk.py
```

构建结果必须同时记录：

- APK 构建命令返回 0；
- `apksigner verify` 返回 0，且签名证书符合安装目标；
- `versionCode`/`versionName` 按产品发布规则更新并记录；
- `generated/classes6.dex` 和 `generated/classes7.dex` 存在；
- helper dex 至少包含 `FastApkScanner`、`InstalledApkSet`、`InstalledAppSource`、`PackageInstallerSupport`；
- `RenpyPatchValidator`、`RenpyPreflight` 和当前任务新增类与 APK 中的 helper 版本一致；
- 生成的 APK 只作为工具构建证据，不能被写成“真实游戏翻译成功”。

| 构建证据 | 结果/路径 | 状态 |
|---|---|---|
| unsigned/aligned/signed APK | `apk-work/slg-workshop-ui-signed.apk`，`34,293,878` bytes；fresh build exit 0 | PASS |
| SHA-256 | `BC0639BEAD0C198B7DD3DAE9A5D196F02B5AFDAD1262D554929372143CBBED83` | PASS |
| `apksigner verify` | v2=true，v3=true，1 signer；debug certificate，仅作本地工具验收 | PASS |
| DEX class inventory | `classes6.dex`/`classes7.dex` 存在；`FastApkScanner`、`InstalledApkSet`、`InstalledAppSource`、`PackageInstallerSupport`、`RenpyPatchValidator`、`RenpyPreflight`、`LanguageMenuSupport` 标记均存在 | PASS |
| version metadata | package `com.slgtranslator.app`；`versionCode=7`；`versionName=1.0.7`；target SDK 36 | PASS |

## 4. 真实样本执行表

每个真实样本先在 `renpy-compatibility-matrix.md` 登记，再执行下面的流水线。每个箭头都要有日志或导出的脱敏 JSON：

```text
scan
  → compatibility preflight
  → coverage / collision report
  → translate
  → strict lint
  → compile
  → RenpyPatchValidator
  → merge base/split APK set
  → sign
  → install
  → launch
  → observe translated text
  → load old save / rollback
```

| 样本 ID | 代际/容器 | 菜单/激活 | 字体 | 单 APK 或 split | report 路径 | 当前状态 |
|---|---|---|---|---|---|---|
| 真实样本 1 | Ren'Py 0.6 / single APK；package `com.yishijietiantang.com` | 原始基线、中文菜单/对白、新游戏、旧存档和 debug rollback PASS | `28/28` | single APK；最终字体修复候选已恢复安装 | T22-06..T22-08；`apk-work/qa/old-save-test-20260809/` | ☑ single APK scoped；split 对本目标 N/A；生产签名未完成 |
| 真实样本 2 | 待登记 | 待登记 | 待登记 | 待登记 | `docs/qa/evidence/<id>/` | ☐ |

第二行仍保留 `待登记` 和 `☐`；第一行只记录已经实际观察到的范围，不能把单 APK debug 候选扩大解释为完整批次发布。

## 5. 真机冒烟检查

### 5.1 扫描与预检

- [ ] 选择应用只显示用户可启动的 launcher 应用，不泄露 `sourceDir` 等私有路径。
- [ ] 单 APK 记录 base；base + split 记录 split 数量、split name、packageName、versionCode 和签名一致性。
- [ ] 预检报告包含 `supportLevel`、`activationStrategy`、`templatePath`、文本计数、font report、issues。
- [ ] `EXTRACT_ONLY`、`UNSUPPORTED` 和 invalid RPYC 显示阻断原因，不出现“可以继续编译”的按钮状态。
- [ ] RPA-1/RPA-2/RPA-3、legacy zlib 和未知格式均按矩阵登记真实结果。

### 5.2 翻译、lint 和覆盖率

- [ ] 对话、菜单、角色名、UI、`{#}`、插值、printf 和重复语境均有计数。
- [ ] exact-old key 在去重前保留 `{#...}`；重复 old 的不同 sourcePath/speaker 不被静默合并。
- [ ] validator-approved、cached、rejected、uncertain 和 collision 记录可导出且不包含译文泄露。
- [ ] 完整构建前 `missing == 0` 且 `rejected == 0`；若用户明确选择 incomplete test patch，界面必须明确显示“不完整测试补丁”。
- [ ] placeholder、Ren'Py markup、插值和 printf lint 全部通过。

### 5.3 编译、字体和产物

- [ ] 编译前根据兼容性等级选择 writer；没有已验证的 writer 时保持 extract-only。
- [ ] 编译返回后立即运行 `RenpyPatchValidator`；validator 失败时临时产物被删除/放弃，不能继续签名。
- [ ] `tl/None` always-on 与 selectable language 使用的语言字段、完成页文案和旧存档策略均记录。
- [ ] 所有新增中文 code point 在最终字体中有覆盖；缺字或部分缺字时构建阻断。
- [ ] 生成的 RPYC 能通过 version、key、language、pair count、zlib 完整性和字符串非空检查。

### 5.4 安装、启动、语言和存档

- [ ] 单 APK 以一个安装流程完成；base + split 在同一个 PackageInstaller session 中写入 base 后全部 split。
- [ ] 安装失败时 session 被 abandon，UI 不显示成功，失败原因可追踪。
- [ ] 标准菜单：打开语言菜单、选择译文语言、重启/回到游戏后仍看到译文。
- [ ] 自定义菜单：若未人工证明注入策略，必须落到 always-on 或阻断；不能误报 selectable。
- [ ] 无菜单：仅在预检明确允许时验证 `tl/None` always-on，并确认完成页文案准确。
- [ ] 菜单注入失败：应用稳定阻断，不崩溃、不生成伪成功包。
- [ ] 新游戏能看到译文；旧存档能加载；rollback、跳转和切换语言不破坏文本状态。
- [ ] selectable 模式能够切回原文；always-on 模式显示“完成后持续使用翻译”的准确说明。
- [ ] 每种激活模式至少完成一次“扫描 → 翻译 → lint → 编译 → 签名 → 安装 → 启动 → 看到译文 → 加载旧存档”。

### 5.5 已安装工具的范围受限冒烟（2026-08-08）

- [x] `PEMM20` / Android 13 / SDK 33 上，已安装 `com.slgtranslator.app` v1.0.10（versionCode 10）冷启动成功，主活动保持前台。
- [x] 中文首页、三步流程、APK 选择入口和底部导航渲染正常；入口能够打开“选择来源”面板。
- [x] “从文件选择 APK”能够调用 `com.android.documentsui/.picker.PickActivity`；未选择文件，显式返回后工具主活动和首页恢复。
- [x] 观察窗口内 app-specific logcat 未命中 `FATAL EXCEPTION`、`ANR in`、`Fatal signal`、`SIGSEGV` 或 `Process: com.slgtranslator.app`。
- [x] 本节只记录设备上既有 v1.0.10 工具包的范围受限冒烟；本地重建 v1.0.7 和真实游戏翻译证据统一见 §5.6。old save、rollback、跳转和 split session 仍属于残余回归。

证据截图：`apk-work/device-smoke-v10-20260808-0620.png`、`apk-work/device-smoke-picker-v10-20260808-0621.png`、`apk-work/device-smoke-documentsui-v10-20260808-0623.png`、`apk-work/device-smoke-v10-final-20260808-0625.png`。本节 PASS 仅适用于设备现有 v1.0.10 工具包；真实样本的新增证据和未完成边界见 §5.6，不得把 v1.0.10 冒烟当作完整翻译验收。

### 5.6 真实 Ren'Py 样本与本地 v1.0.7 复验（2026-08-08）

- [x] 用户确认手机本地 `异世界天堂0.6翻.apk` 合法、完整且可用于测试；系统确认 package `com.yishijietiantang.com`、versionName `0.6`、versionCode `1755587835`，入口为 `org.renpy.android.PythonSDLActivity`。
- [x] 本地重建工具 `apk-work/slg-workshop-ui-signed.apk`（versionCode `7` / versionName `1.0.7`，SHA-256 `731B25B459D57E23A2BD3BBB02C5407DD69491C62AE355A070105588BF4FDA41`）通过 fresh build 与签名验证；`/data/user/0/com.slgtranslator.app` 未被清除。
- [x] 兼容性阻断 UI 修复候选 `apk-work/slg-workshop-ui-signed.apk`（SHA-256 `BC0639BEAD0C198B7DD3DAE9A5D196F02B5AFDAD1262D554929372143CBBED83`）重新覆盖安装并完成 `EXTRACT_ONLY` 真机阻断复验；数据未清除。
- [x] 未修改的真实游戏通过手机本地 APK 安装后，观察到 Ren'Py loading、`Ver. 0.6` 主菜单、新游戏和两段英文对白；目标日志观察窗口未命中 fatal/ANR 模式。
- [x] v1.0.7 通过 DocumentsUI 选择真实 APK，显示 `104 个脚本`、`发现 104 个可翻译文件`，并列出 RPYC 文件后进入 `已就绪`。
- [x] 翻译、lint、编译、签名和译文补丁安装：本地 ML Kit 完成 `423/423` 批次；唯一原文 `10251`、总出现 `20864`、已验证 `10251`、缺失/拒绝/不确定均为 `0`；字体覆盖 `28/28`；编译合并 `9907` 条；未选择不完整测试补丁；补丁通过应用内完整流程安装。
- [x] 语言菜单/always-on/selectable 激活：历史 `content://` 失败已由 resolved-copy 修复；当前设备补丁主菜单和实际对白均显示中文，见 T22-06/T22-07/T22-08。
- [x] old save / rollback：使用原始代码的 debug 签名兼容回滚包完成安装、启动、`Jhonny` 旧存档选择和对白加载；证据见 `apk-work/qa/old-save-test-20260809/26-original-debug-rollback-launch/` 至 `29-original-debug-old-save-loaded/`。
- [x] 最终字体修复候选恢复安装后再次通过中文主菜单、旧存档和新游戏对白；证据见 `31-final-restored-ready/`、`32-final-old-save-regression/` 和 `34-final-newgame-tap2/`。
- split session：当前真实目标为 single APK，对本目标为 N/A；泛化 split 安装集合的更大批次回归仍未执行。
- [ ] 正式生产签名：未提供生产 keystore/certificate；当前候选只使用本机 debug certificate，不能标记为正式上线包。

证据截图：`apk-work/device-v7-home-20260808-0630.png`、`apk-work/device-v7-after-real-apk-select-20260808-0636.png`、`apk-work/device-v7-real-scan-scroll-20260808-0638.png`、`apk-work/device-v7-real-settings-bottom-20260808-0640.png`、`apk-work/device-game-current.png`、`apk-work/device-game-dialogue-01.png`、`apk-work/device-game-relaunch-01.png`、`apk-work/device-game-relaunch-dialogue.png`。日志：`apk-work/device-game-final-log.txt`、`apk-work/device-game-relaunch-log.txt`。

## 6. Skip 与外部条件登记

允许 skip 的唯一理由是可验证的外部条件，例如真实 APK、完整提取语料、Android 设备或 `dexdump` 不存在。每条 skip 必须写清：

```text
测试名：
外部条件：
检查命令/路径：
为什么不能安全地填 success 或 0：
补测方式：
```

当前已知的合法外部条件是：没有真实完整 Ren'Py 游戏 APK/对应完整提取语料时，coverage audit 可以显式 skip；这不证明真实游戏 `missing == 0`。生成 DEX 缺失时也只能登记“需先运行 `python build_fast_scanner.py`”，不能把 artifact gate 改成无条件通过。

Task 21/22 前置盘点（2026-08-08）只读完成：本地候选 `samples/newmanwa.apk`（`newmanwa.com`/`Manwa2`）和 `samples/nearbubble_final_hclm67.apk`、`selected.apk`（`com.nearbubble`/`盘丝洞`）均未发现 Ren'Py 入口；该结论只适用于那些本地候选。用户确认的真实 `异世界天堂0.6` 手机 APK 后续已完成当前 §5.6 路线，不能再用前置候选盘点覆盖真实样本证据。

已连接设备先完成只读 inventory，随后仅对现有工具包做了不安装、不降级、不清数据的范围受限冒烟：`PEMM20`、Android 13 / SDK 33、ABI `arm64-v8a,armeabi-v7a,armeabi`、`/data/user/0` 可用 `36,952,844 KiB`；设备上的工具包为 `com.slgtranslator.app` versionCode `10` / versionName `1.0.10`。工具包冷启动、首页、来源面板、DocumentsUI 调用和返回恢复记录为 PASS，但这不是真实游戏验收；没有安装或启动 Task 20 的 versionCode 7 APK，也没有安装真实游戏；Task 22 真机完整工作流仍保持 `NOT-RUN`。

以上两段是本次设备复验前的前置快照。后续复验已安装并确认 v1.0.7，完成真实 `com.yishijietiantang.com` 的本地 ML Kit 翻译、补丁安装、中文菜单/对白启动；历史 `content://` FAIL 已由 resolved-copy 修复，详见 §5.6 和 QA evidence ledger 的 T22-06..T22-08。

Task 8 fresh 重新执行的 discover 为 `218` 项、0 failures/errors、1 个明确的 `audit APK/extracted texts not present` skip；这个 skip 只说明受控审计 fixture 缺失，不影响本次真实设备路线的独立 coverage 证据。旧存档和 debug rollback 已有单 APK 证据；对当前目标 split session 不适用，生产签名仍是残余发布项。

如果 `test_workshop_patch.py`、构建测试或其他 discover 测试失败，必须把准确的失败测试名、首个稳定错误和是否属于本批次变更写入 `full-discover.txt`，然后修复或明确阻断发布；不能用“基线已通过”覆盖新的失败。

## 7. 最终发布门禁

以下八项必须全部满足，才可以把版本标记为“可发布”：

| 门禁 | 通过条件 | 当前状态 |
|---|---|---|
| 自动化测试 | full discover 无失败；所有 skip 有外部条件 | PASS — fresh `219` tests，`1` skip |
| 真实样本覆盖 | `missing == 0`，或用户明确选择并看到 incomplete test patch | PASS（本地 ML Kit 路线）— unique `10251`、occurrences `20864`、validated `10251`、missing/rejected/uncertain `0`；未选择 incomplete test patch |
| rejected | `rejected == 0` | PASS — 真实覆盖报告 rejected `0` |
| 编译产物 | `RenpyPatchValidator` 通过，签名在 validator 之后进行 | PASS — 编译合并 `9907` 条；工具 APK v2/v3 true；补丁已通过应用内流程安装 |
| 字体终检 | `missingCodePoints` 为空，覆盖报告已保存 | PASS — 真实字体覆盖 `28/28` |
| 语言激活 | 每种声明支持的激活模式已在设备观察到译文 | PASS（新游戏路线）— 中文主菜单和实际中文对白均已观察到；历史 `content://` 注入失败已修复并重验 |
| 安装/存档 | 单 APK、split（如适用）、新游戏和旧存档回归通过 | PASS（当前目标）— 单 APK、最终候选安装、新游戏、旧存档和 debug rollback PASS；split 对当前目标不适用 |
| 不支持样本 | 被稳定阻止，无崩溃、无伪成功 | PASS — controlled unsupported gate；真实菜单注入 FAIL，不能据此发布 |

本次请求的本地 ML Kit/单 APK/新游戏/旧存档使用路线可以交付使用；当前仍只能标记为“本地 debug 签名发布候选”。对当前目标，正式上线前必须补齐生产签名；若后续产物包含 split，再按适用范围完成 split session 回归。`EXTRACT_ONLY`/`UNSUPPORTED` 样本被正确阻断，是安全行为，不是可以通过发布门禁的理由。

## 7.1 C16 发布机器矩阵与完成定义

以下六行与 `renpy-compatibility-matrix.md` 的 C16-01..C16-06 一一对应。`PASS` 只代表当前列出的证据范围；本次新游戏/单 APK/中文对白/旧存档/debug rollback 路线已有真实证据，split session 和生产签名没有证据时仍必须保持 `NOT-RUN`/`PARTIAL`。

| requirementId | 门禁范围 | supportLevel | activationStrategy | template/source + counts | missing/rejected/font | build/install/startup/save/rollback | status/evidence |
|---|---|---|---|---|---|---|---|
| C16-01 | engine generation 与 `SAFE`/`WARNING`/`EXTRACT_ONLY`/`UNSUPPORTED` 分类 | SAFE/WARNING/EXTRACT_ONLY/UNSUPPORTED | selectable / always-on / NONE | T6–T12 preflight/extractor/coverage fixtures；real text counts `not-run` | real missing/rejected/font `not-run` | controlled build PASS；real install/startup/old save/rollback NOT-RUN | PASS (controlled); real sample NOT-RUN |
| C16-02 | loose RPYC2、RPA-1/RPA-2/RPA-3、legacy zlib | inherited or EXTRACT_ONLY/UNSUPPORTED | inherited or NONE | RPA/RPYC/legacy parser fixtures；real template/source and counts `not-run` | unknown format blocked; real missing/rejected/font `not-run` | blocked for unknown; real install/startup/save/rollback NOT-RUN | PASS (controlled); real archive NOT-RUN |
| C16-03 | selectable、always-on、标准/自定义/无菜单和菜单注入失败 | SAFE/WARNING/EXTRACT_ONLY/UNSUPPORTED | selectable / always-on / NONE | C13/T12/C15 UI/compile fixtures；real `content://` route full coverage and translated menu/dialogue | real missing/rejected `0`; font `28/28` | tool build PASS；translated single-APK new-game/startup/dialogue and debug old-save/rollback PASS；split 对当前目标 N/A | PASS for tested local MLKit single-APK route; production-signing residual remains |
| C16-04 | 对话、菜单、角色名、UI、`{#}`、插值、printf、重复语境和字体 | inherited source level | inherited activation; advanced dialogue ID default-off | T8–T11/C15 controlled counts/collision/lint/font；real template/source `not-run` | complete real build requires `missing == 0` and `rejected == 0`; real font `not-run` | controlled gates PASS；real install/startup/save/rollback NOT-RUN | PASS (controlled); real corpus NOT-RUN |
| C16-05 | `single APK` 与 `base + split` 的构建/签名/单 session 安装 | inherited source level | inherited activation | C14 split lifecycle; fresh helper artifact `versionCode=7`/`versionName=1.0.7`；bugfix candidate SHA-256 `BC0639BEAD0C198B7DD3DAE9A5D196F02B5AFDAD1262D554929372143CBBED83`；real target single APK candidate SHA-256 `335166E2F0003C1BEB343CCBACC56F3E6DB9C6DFE3FBCC1E43296D51DB88FB28` | real missing/rejected `0`; font `28/28` | local build/signature/asset PASS；v2/v3 true；translated install/startup/new-game/old-save/debug-rollback PASS；unsupported UI block PASS；split 对当前目标 N/A | PASS for tested single-APK debug route; formal production signing residual remains |
| C16-06 | 最终定义的自动化、artifact、样本、语言、安装/存档和不支持门禁 | all declared levels require evidence | all applicable modes require evidence | current evidence index; real sample identity, full local route, patch install, Chinese menu/dialogue and old-save evidence recorded | tested route missing/rejected `0`; font `28/28`; old-save/debug-rollback PASS; unsupported UI block PASS; split/prod signing residual | fresh `219` tests, artifact, translated install/startup/new-game/old-save evidence PASS | PASS (scoped) for local MLKit single-APK debug candidate; formal release remains conditional |

## 8. 签字与交接

| 角色 | 姓名 | 日期 | 证据目录 | 签字 |
|---|---|---|---|---|
| 自动化测试 |  |  |  | ☐ |
| APK 构建/签名 |  |  |  | ☐ |
| 真实设备 QA |  |  |  | ☐ |
| 发布负责人 |  |  |  | ☐ |

## 9. Package Delete Acceptance (2026-08-09)

### 9.1 Build and automated evidence

- [x] Asset generation: `python apk-work/ui-redesign/patch_workshop_ui.py` returned 0.
- [x] UI contracts: `python -m unittest -v test_workshop_patch`, 64/64 passed.
- [x] Native contracts: `python -m unittest -v test_fast_scanner`, 98 passed, 1 explicit skip (Windows symlink privilege); no failures/errors.
- [x] Python compileall returned 0 for the modified native/UI Python surfaces.
- [x] Candidate: `apk-work/slg-workshop-ui-signed.apk`, 34,293,878 bytes, SHA-256 `10ADC584F12D3A589AC9AD186EA5D0B976B3868ACD170CCF281180E9938D34F5`.
- [x] `zipalign -c -v 4` passed; `apksigner verify --verbose` reported v2=true, v3=true, one signer.
- [x] Metadata: `com.slgtranslator.app`, versionCode 7, versionName 1.0.7, target/compile SDK 36.
- [x] Packaged `classes6.dex` equals `apk-work/native-fast-scan/generated/classes6.dex`, 94,164 bytes, SHA-256 `79A6778C066E845B8C20FEEAF3154D4723F94E716E9B050C49D624D8338967DF`; generated JS contains `deletePatchedApk({path})` and the gallery title is the tested runtime string `\u5b89\u88c5\u5305`.

The default `python apk-work/ui-redesign/build_workshop_apk.py` still fails because `apk-work/com.slgtranslator.app-base.apk` is absent. The candidate was built with a temporary copy of the verified equivalent `apk-work/slg-workshop-ui-unsigned.apk` injected into both build modules in memory. The build script was not changed. This is a local debug-signed candidate; formal production signing still requires the production keystore.

### 9.2 Device file-level evidence

Device: `MZNRYXEQS859O7GU` / `PEMM20`, Android 13 / SDK 33; the candidate was installed with `adb install -r` without clearing app data.

Original game APK, outside the patch output directory:

- `/storage/emulated/0/Android/data/com.slgtranslator.app/files/installed-apks/a6fc46983ff20875aeebe4d4309256bb9c3d816d5efa364025d99d90b9c3c9d2.apk`
- 2,576,983,684 bytes; SHA-256 before and after deletion was `65BB558CE57EA3B1BD7D89E5888AEEED0AE6D73E54D4CDFA63B4CBBA33C579A4`.

Two QA patch APK copies were placed only in the app-owned output directory and deleted one at a time through the UI:

| Item | Path | Size | SHA-256 | Result |
|---|---|---:|---|---|
| C | `/storage/emulated/0/Android/data/com.slgtranslator.app/files/SLG-Translator-Output/qa-delete-c-20260809-patched-signed.apk` | 34,293,878 | `10ADC584F12D3A589AC9AD186EA5D0B976B3868ACD170CCF281180E9938D34F5` | Deleted through UI; file absent |
| D | `/storage/emulated/0/Android/data/com.slgtranslator.app/files/SLG-Translator-Output/qa-delete-d-20260809-patched-signed.apk` | 34,293,878 | `10ADC584F12D3A589AC9AD186EA5D0B976B3868ACD170CCF281180E9938D34F5` | Deleted through UI; file absent |

The historical real patch remained after both deletions: `/storage/emulated/0/Android/data/com.slgtranslator.app/files/SLG-Translator-Output/content-29469595fc65b1170d93bd5d8d576811293a8fbbd698a8ac5bed736957662383-patched-signed.apk`, 2,493,730,816 bytes, SHA-256 `07F1684D7D0AE83BA4BA3B6642AE92F3ECE7A1D24D8CEBC1E8EE27ED4814A5A1`. Temporary `/sdcard/Download/qa-delete-source.apk` was removed.

### 9.3 UI and startup evidence

- [x] Real WebView DOM: gallery `h1` and `aria-label` were the tested runtime string `\u5b89\u88c5\u5305`; delete buttons had `type=button`, delete label/title, and 48x48 bounds; the FileManager bridge was callable.
- [x] Node contracts cover cancel/no native call, duplicate request sharing, deletion failure retention, refresh failure retention, accessibility tokens, title rename, and save-action preservation. Device C/D deletion refreshed the list without errors.
- [x] Original game `mayfly.SLLXXL` launched through `org.renpy.android.PythonSDLActivity` and was resumed. The sampled logcat contained no `FATAL EXCEPTION`, `ANR in`, `Fatal signal`, or `SIGSEGV` matches.
- [x] Evidence files: `apk-work/qa/package-delete-device-start.png`, `apk-work/qa/package-delete-device-gallery-empty.png`, `apk-work/qa/package-delete-game-launch.png`, `apk-work/qa/package-delete-translator-after-game.png`, and matching XML dumps.

## 9.4 Translation Storage Preflight Repair (2026-08-10)

- [x] `TranslationCompiler` performs a `StatFs.getAvailableBytes()` preflight before `rewriteApkWithEntries`.
- [x] Disk-backed pending APK payloads report their reserved size without restoring a `List<byte[]>` aggregation.
- [x] The current source APK is preserved while stale app-owned `installed-apks` copies, `.tl.tmp`, and `.partial` build material are pruned.
- [x] Rewrite failure cleanup removes `.tl.tmp`; successful rename leaves the final APK in place.
- [x] Stable low-space code is `translation_storage_insufficient`; raw I/O details remain available for diagnostics.
- [x] Java harness, UI/performance tests, signed APK verification, data-preserving device install, and home-screen startup passed.
- [ ] Full two-run real-device translation memory acceptance is still pending; see `docs/qa/translation-memory-acceptance-20260810.md`.
- [ ] The default build input `apk-work/com.slgtranslator.app-base.apk` and production signing key are still external prerequisites.

## 9.5 运行时验证恢复（Phase 4, 2026-08-12）

范围：`docs/superpowers/plans/2026-08-12-renpy-runtime-validation-recovery.md`。以下条目为 harness / JS 契约 / javac 编译期证据；**均未在真机 APK 上复验**，真机与发布前证据仍待办。

- [x] 可生成方言（`canGenerate()`）scan 响应含 `canValidateRuntime=true`；`EXTRACT_ONLY`/`UNSUPPORTED`/无激活为 `false`（EngineCapabilities + JS 兜底契约，`test_engine_capability_js_fallback_defaults_can_validate_runtime_false`）。
- [x] 补丁产物重读：语言入口断言与抽样译文断言由调用方预计算为 `staticAsserts`，安装返回独立于 `installed` 的字段（PackageInstallerSupport 4-arg 契约 harness）。
- [x] 安装后记录卡：安装成功 / 汉化生效 分开展示、互不推导；`readTaskSnapshot` 区分 `generated` 与 `installed` 两 stage（`test_completed_state_splits_install_and_effect`）。
- [x] 三组 fixture（正常/label 失效/未生效）+ 未安装 + 待确认在 harness 中分类为 `ACTIVE`/`STRING_MISMATCH`/`PATCH_NOT_APPLIED`/`NOT_INSTALLED`/`PENDING_CONFIRM`（`test_runtime_validation_classifies_install_launch_and_text_evidence`）。
- [x] 启动探针如实记录"启动动作已发出"（`LaunchResult{resolved,started}`），不声称已渲染（`test_launch_probe_resolves_intent_and_reports_launch_outcome`）。
- [x] 用户确认流程：已生效 / 未生效 均正确更新 `textAppears` 并刷新记录卡与诊断文案（UI 契约行为测试）。
- [x] 诊断文案只含"已保留什么结果 + 下一步能做什么"（`classify` 的 `reason`/`nextSteps` 边界断言）。
- [x] `canValidateRuntime=false` 的 APK 不渲染验证步骤、不显示"汉化完成"（`noValidate` 行为断言）。

残余与待办：

- [x] 工具 APK `apk-work/slg-workshop-ui-signed.apk` 已按当前 `patch_workshop_ui.py` 输出重建（SHA-256 `5A88A53EC526694A09C75AB4F5C13D9B85CDA0D475717CC6E39E46DC5CC3D233`），`test_built_apk.test_assets_exactly_match_pinned_patch_output` 已 PASS；重建产物含验证卡与两段记录卡运行时标记。
- [ ] 真机复验：安装→启动探针→汉化生效/未生效 确认流程在设备上执行并留证。
- [ ] 预存失败（与 Phase 4 无关，本会话用阶段前基线复核确认）：`test_translation_coverage` 三个 `test_task10*`（`occurrenceCount` 提取段不一致）与 `test_known_bugfixes.test_cache_writes_are_throttled_and_forced_at_commit_points`（断言 minified `__slgCoreLocalTranslate` 片段在当前生成物中缺失）。
