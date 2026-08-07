# Ren'Py 批次 A 发布检查表

> 适用范围：`docs/superpowers/plans/2026-08-07-renpy-app-compatibility-optimization.md` 的 Task 16，以及本次 C16/Task 19 发布机器矩阵和自动化门禁复核。
>
> 当前状态：未批准发布。Task 19 fresh 自动化门禁已通过：scanner `77` 项、workshop `60` 项、quality/coverage/performance 合计 `37` 项（1 个明确 audit-fixture skip）、full discover `192` 项（1 个明确 audit-fixture skip），均无 failures/errors。Task 20–23 的产物、真实游戏样本和真机验收仍是独立条件；本工作区没有完整第三方 Ren'Py 游戏样本，真实样本的 coverage、安装、启动、old save 和 rollback 仍为 `NOT-RUN`。

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
| scanner contract | 无失败；生成物缺失时只能有明确外部条件 skip | `test_fast_scanner.py`：`77` tests，OK | PASS |
| workshop contract | 无失败；UI/构建契约保持可执行 | `test_workshop_patch.py`：`60` tests，OK | PASS |
| translation quality / coverage / performance | 无失败；真实审计缺输入时保留显式 skip | 合计 `37` tests，OK，`1` 个 `audit APK/extracted texts not present` skip | PASS |
| full discover | 无失败；每个 skip 在本清单第 6 节登记原因 | Task 19 fresh：`192` tests，0 failures/errors，`1` 个明确 skip | PASS |
| diff hygiene | `git diff --check` 返回 0 | Task 19 证据固化前复核 | PASS |

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
| unsigned/aligned/signed APK | `apk-work/ui-redesign/generated/` 或构建输出 | ☐ |
| SHA-256 | `build-artifacts.sha256` | ☐ |
| `apksigner verify` | `apksigner-verify.txt` | ☐ |
| DEX class inventory | `helper-dex-classes.txt` | ☐ |
| version metadata | `version-metadata.txt` | ☐ |

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
| 真实样本 1 | 待登记 | 待登记 | 待登记 | 待登记 | `docs/qa/evidence/<id>/` | ☐ |
| 真实样本 2 | 待登记 | 待登记 | 待登记 | 待登记 | `docs/qa/evidence/<id>/` | ☐ |

若没有真实样本，保留这两行的 `待登记` 和 `☐`；不要填写虚构的包名、文本数量或启动结果。

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

Task 19 fresh 重新执行的 discover 为 `192` 项、0 failures/errors、1 个明确的 `audit APK/extracted texts not present` skip；scanner 为 `77` 项，workshop 为 `60` 项，quality/coverage/performance 合计为 `37` 项并保留同一个明确 skip。这个 skip 只说明真实审计 APK/提取语料缺失，不证明真实游戏 `missing == 0`；真实样本和设备门禁仍按 `NOT-RUN` 处理。

如果 `test_workshop_patch.py`、构建测试或其他 discover 测试失败，必须把准确的失败测试名、首个稳定错误和是否属于本批次变更写入 `full-discover.txt`，然后修复或明确阻断发布；不能用“基线已通过”覆盖新的失败。

## 7. 最终发布门禁

以下八项必须全部满足，才可以把版本标记为“可发布”：

| 门禁 | 通过条件 | 当前状态 |
|---|---|---|
| 自动化测试 | full discover 无失败；所有 skip 有外部条件 | ☐ |
| 真实样本覆盖 | `missing == 0`，或用户明确选择并看到 incomplete test patch | ☐ |
| rejected | `rejected == 0` | ☐ |
| 编译产物 | `RenpyPatchValidator` 通过，签名在 validator 之后进行 | ☐ |
| 字体终检 | `missingCodePoints` 为空，覆盖报告已保存 | ☐ |
| 语言激活 | 每种声明支持的激活模式已在设备观察到译文 | ☐ |
| 安装/存档 | 单 APK、split（如适用）、新游戏和旧存档回归通过 | ☐ |
| 不支持样本 | 被稳定阻止，无崩溃、无伪成功 | ☐ |

当前缺任一项都必须保持“未批准发布”。特别是 `EXTRACT_ONLY`/`UNSUPPORTED` 样本被正确阻断，是安全行为，不是可以通过发布门禁的理由。

## 7.1 C16 发布机器矩阵与完成定义

以下六行与 `renpy-compatibility-matrix.md` 的 C16-01..C16-06 一一对应。`PASS` 只代表当前列出的本地契约或构建证据；真实样本、安装、启动、old save 和 rollback 没有证据时必须保持 `NOT-RUN`，不能被机器测试结果替代。

| requirementId | 门禁范围 | supportLevel | activationStrategy | template/source + counts | missing/rejected/font | build/install/startup/save/rollback | status/evidence |
|---|---|---|---|---|---|---|---|
| C16-01 | engine generation 与 `SAFE`/`WARNING`/`EXTRACT_ONLY`/`UNSUPPORTED` 分类 | SAFE/WARNING/EXTRACT_ONLY/UNSUPPORTED | selectable / always-on / NONE | T6–T12 preflight/extractor/coverage fixtures；real text counts `not-run` | real missing/rejected/font `not-run` | controlled build PASS；real install/startup/old save/rollback NOT-RUN | PASS (controlled); real sample NOT-RUN |
| C16-02 | loose RPYC2、RPA-1/RPA-2/RPA-3、legacy zlib | inherited or EXTRACT_ONLY/UNSUPPORTED | inherited or NONE | RPA/RPYC/legacy parser fixtures；real template/source and counts `not-run` | unknown format blocked; real missing/rejected/font `not-run` | blocked for unknown; real install/startup/save/rollback NOT-RUN | PASS (controlled); real archive NOT-RUN |
| C16-03 | selectable、always-on、标准/自定义/无菜单和菜单注入失败 | SAFE/WARNING/EXTRACT_ONLY/UNSUPPORTED | selectable / always-on / NONE | C13/T12/C15 UI/compile fixtures；real menu/source counts `not-run` | real missing/rejected/font `not-run` | tool build PASS；real activation/startup/old save/rollback NOT-RUN | PASS (controlled); device NOT-RUN |
| C16-04 | 对话、菜单、角色名、UI、`{#}`、插值、printf、重复语境和字体 | inherited source level | inherited activation; advanced dialogue ID default-off | T8–T11/C15 controlled counts/collision/lint/font；real template/source `not-run` | complete real build requires `missing == 0` and `rejected == 0`; real font `not-run` | controlled gates PASS；real install/startup/save/rollback NOT-RUN | PASS (controlled); real corpus NOT-RUN |
| C16-05 | `single APK` 与 `base + split` 的构建/签名/单 session 安装 | inherited source level | inherited activation | C14 split lifecycle and C15 workshop/helper builds；Task 20 fresh artifact evidence pending | real missing/rejected/font `not-run` | local build/signature PASS; real install/startup/old save/rollback NOT-RUN | PASS (local build); device NOT-RUN |
| C16-06 | 最终定义的自动化、artifact、样本、语言、安装/存档和不支持门禁 | all declared levels require evidence | all applicable modes require evidence | current evidence index; real source/template/counts `not-run` | mandatory real rows `NOT-RUN` | Task 19–22 and Task 23 audit still pending | NOT-RUN |

## 8. 签字与交接

| 角色 | 姓名 | 日期 | 证据目录 | 签字 |
|---|---|---|---|---|
| 自动化测试 |  |  |  | ☐ |
| APK 构建/签名 |  |  |  | ☐ |
| 真实设备 QA |  |  |  | ☐ |
| 发布负责人 |  |  |  | ☐ |
