# Ren'Py 兼容性矩阵与样本证据

> 版本：批次 A / Task 16 / C16 / Task 19
>
> 冻结日期：2026-08-08（Asia/Shanghai）
>
> 当前结论：C16 机器矩阵和 Task 19 自动化门禁已在共享工作区 fresh 复核为绿色：scanner `77` 项、workshop `60` 项、quality/coverage/performance 合计 `37` 项（1 个明确 audit-fixture skip）、full discover `192` 项（1 个明确 audit-fixture skip），均无 failures/errors；Task 20 本地 helper/APK 产物、哈希、签名和 DEX 归属也已复核。当前工作区仍没有可用于真机验收的完整第三方 Ren'Py 游戏样本。因此真实游戏的 `missing == 0`、语言激活、字体覆盖、安装、启动、old save 和 rollback 仍保持 `NOT-RUN`，不是 `0` 或 `success`。

## 1. 证据边界

本矩阵验证的是批次 A 已实现的扫描、预检、提取、编译门禁、产物验证和完整 APK 集合处理。它不把以下内容混为一谈：

- Java/Python fixture 通过：说明代码契约成立，不说明任意第三方游戏能启动；
- APK 构建成功：说明工具 APK 可生成，不说明它已经给某个游戏产生可加载翻译包；
- 能提取文本：不等于可以安全写回；`EXTRACT_ONLY` 和 `UNSUPPORTED` 必须阻断编译；
- 没有报告缺失：不等于缺失为零；真实样本不存在时必须保留 `not-run`；
- 生成了安装包：不等于设备上的语言菜单、字体、旧存档和 rollback 都已验证。

报告字段与应用输出保持一致：

| 字段 | 允许值/格式 | 解释 |
|---|---|---|
| `supportLevel` | `SAFE` / `WARNING` / `EXTRACT_ONLY` / `UNSUPPORTED` | `EXTRACT_ONLY` 与 `UNSUPPORTED` 禁止进入当前 writer |
| `activationStrategy` | `SELECTABLE_LANGUAGE` / `ALWAYS_ON` / `NONE` | `ALWAYS_ON` 只能是预检明确选择的 `tl/None` 回退 |
| `templatePath` | APK 内相对路径；无法确认时为空 | 不允许用文件名猜模板 |
| 文本计数 | `uniqueTextCount / occurrenceCount / collisionCount` | 必须保留 exact-old occurrence 和语境碰撞 |
| `missing` | 非负整数或 `not-run` | 只有完整真实语料与补丁对照完成后才能填写整数 |
| 字体结果 | `covered/required`、`blocked` 或 `not-run` | 最终字体检查失败必须阻断完成构建 |
| 构建/安装/启动 | `allowed`、`blocked`、`success`、`not-run` | `allowed` 只表示门禁放行，不表示设备成功 |

## 2. 来源与可复现输入

本轮使用的应用源码 APK 来自 GitHub 固定提交，不能用工作区中后续生成的 APK 替代来源证据：

| 项目 | 值 |
|---|---|
| 仓库 | [`wang76955/slg-translator`](https://github.com/wang76955/slg-translator) |
| commit | `fc2e3f39f85a09799e63fa652e566e3850ff9f31` |
| 本地 APK | `apk-work/github-source/slg-translator-android-rpyc-v12.apk` |
| SHA-256 | `44470607C402F6E8BBBDD5CED24B3AFF9016C92CE504BA2F2C3CE77DB1567104` |
| 包名/版本 | `com.slgtranslator.app` / `versionCode=2` / `versionName=1.0.1` |

这个 APK 是翻译工具本身，不是可代表所有 Ren'Py 游戏的真实游戏样本。真实游戏样本必须另外登记来源、包集合、签名、脚本容器和字体资产。

## 3. 最小样本矩阵

下表的每一行都是一个可登记的样本。对没有真实输入的项目，`text counts`、`missing`、安装和启动列必须保持 `not-run`；对预期被拒绝的样本，`build allowed=blocked` 是预期行为，不是测试失败。

### 3.1 Ren'Py/Python 代际

| ID / sample | `supportLevel` | `activationStrategy` | `templatePath` | text counts | missing | font result | build allowed | install success | startup translation observed | evidence / current state |
|---|---|---|---|---|---|---|---|---|---|---|
| GEN-6-PY2 / 6 / Python 2 | `EXTRACT_ONLY` | `NONE` | 真实模板路径待登记 | `not-run` | `not-run` | `not-run` | `blocked` | `not-run` | `not-run` | 期待 `renpy_python2_writer_unavailable`；需真实 Ren'Py 6 样本 |
| GEN-7-PY2 / 7 / Python 2 | `EXTRACT_ONLY` | `NONE` | 真实模板路径待登记 | `not-run` | `not-run` | `not-run` | `blocked` | `not-run` | `not-run` | protocol 2 只能在已验证 writer 形状下放行；未知形状保持 extract-only |
| GEN-8-PY3 / 8 / Python 3 | `SAFE` 或 `WARNING` | `SELECTABLE_LANGUAGE` 或 `ALWAYS_ON` | `game-script/*.rpyc` 候选，经预检确定 | `not-run` | `not-run` | `not-run` | `conditional` | `not-run` | `not-run` | 需要真实 RPYC、菜单、字体和 validator 证据；Task 13/15 fixture 只证明 writer 契约 |
| GEN-UNKNOWN / 未知 / 不支持 | `UNSUPPORTED` 或 `EXTRACT_ONLY` | `NONE` | 空或未确认 | `not-run` | `not-run` | `not-run` | `blocked` | `not-run` | `not-run` | 必须报告稳定原因并停止，不能“尽量写入” |

### 3.2 脚本容器

| ID / sample | `supportLevel` | `activationStrategy` | `templatePath` | text counts | missing | font result | build allowed | install success | startup translation observed | evidence / current state |
|---|---|---|---|---|---|---|---|---|---|---|
| CON-RPC2 / loose RPYC2 | 继承代际预检 | 继承菜单预检 | `assets/**/script.rpyc` 或 `game/**.rpyc` | `not-run` | `not-run` | `not-run` | `conditional` | `not-run` | `not-run` | `RpycCompatibility` 检查槽位、protocol、GLOBAL 和对象形状 |
| CON-RPA1 / RPA-1 | 继承 RPYC 预检 | 继承菜单预检 | 从 archive entry 解析 | `not-run` | `not-run` | `not-run` | `conditional` | `not-run` | `not-run` | archive-only 解包必须通过边界和资源预算 |
| CON-RPA2 / RPA-2 | 继承 RPYC 预检 | 继承菜单预检 | 从 archive entry 解析 | `not-run` | `not-run` | `not-run` | `conditional` | `not-run` | `not-run` | 只能使用已识别的 RPA 版本；未知 archive 不能伪成功 |
| CON-RPA3 / RPA-3 | 继承 RPYC 预检 | 继承菜单预检 | 从 archive entry 解析 | `not-run` | `not-run` | `not-run` | `conditional` | `not-run` | `not-run` | 需真实 archive fixture 或完整游戏证据；当前工作区未登记 |
| CON-ZLIB / legacy zlib | `EXTRACT_ONLY` 或 `UNSUPPORTED` | `NONE` | 真实路径待登记 | `not-run` | `not-run` | `not-run` | `blocked` | `not-run` | `not-run` | legacy zlib 只有在 parser 和 writer 均有明确验证时才可放行 |

### 3.3 语言激活

| ID / sample | `supportLevel` | `activationStrategy` | `templatePath` | text counts | missing | font result | build allowed | install success | startup translation observed | evidence / current state |
|---|---|---|---|---|---|---|---|---|---|---|
| ACT-STANDARD / 标准菜单 | `SAFE` | `SELECTABLE_LANGUAGE` | 预检选出的 game script | `not-run` | `not-run` | `not-run` | `conditional` | `not-run` | `not-run` | 真机须点选语言并看到译文；当前未完成 |
| ACT-CUSTOM / 自定义菜单 | `WARNING` | `ALWAYS_ON` 或人工确认 | 预检选出的 game script | `not-run` | `not-run` | `not-run` | `conditional` | `not-run` | `not-run` | `renpy_menu_strategy_unknown` 必须显示；不能把自定义菜单当标准菜单 |
| ACT-NONE / 无菜单 | `WARNING` | `ALWAYS_ON` | 预检选出的 game script | `not-run` | `not-run` | `not-run` | `conditional` | `not-run` | `not-run` | 只能使用明确的 `tl/None` 回退；完成页需说明 always-on |
| ACT-INJECT-FAIL / 菜单注入失败 | `UNSUPPORTED` 或 `EXTRACT_ONLY` | `NONE` | 空或未确认 | `not-run` | `not-run` | `not-run` | `blocked` | `not-run` | `not-run` | 必须阻断并保留失败证据，不得显示“已安装”伪成功 |

### 3.4 字体

| ID / sample | `supportLevel` | `activationStrategy` | `templatePath` | text counts | missing | font result | build allowed | install success | startup translation observed | evidence / current state |
|---|---|---|---|---|---|---|---|---|---|---|
| FONT-EXISTING / 已有中文字体 | 继承源样本 | 继承源样本 | 继承源样本 | `not-run` | `not-run` | `covered/required` 待真实检查 | `conditional` | `not-run` | `not-run` | 需要最终译文 code point 与目标字体覆盖报告 |
| FONT-NONE / 缺中文字体 | 继承源样本但带阻断 issue | 继承源样本 | 继承源样本 | `not-run` | `not-run` | `blocked` | `blocked` | `not-run` | `not-run` | 不自动下载或打包来源不明字体；必须明确失败原因 |
| FONT-PARTIAL / 部分缺字 | 继承源样本但带阻断 issue | 继承源样本 | 继承源样本 | `not-run` | `not-run` | `blocked` | `blocked` | `not-run` | `not-run` | `missingCodePoints` 非空时禁止把补丁标为完成 |

### 3.5 安装形态

| ID / sample | `supportLevel` | `activationStrategy` | `templatePath` | text counts | missing | font result | build allowed | install success | startup translation observed | evidence / current state |
|---|---|---|---|---|---|---|---|---|---|---|
| APK-SINGLE / 单 APK | 继承源样本 | 继承源样本 | base APK 内模板 | `not-run` | `not-run` | `not-run` | `conditional` | `not-run` | `not-run` | 需要签名、validator、安装、启动和旧存档证据 |
| APK-SPLIT / base + split | 继承源样本 | 继承源样本 | base 或特定 split 的模板 | `not-run` | `not-run` | `not-run` | `conditional` | `not-run` | `not-run` | Task 14 fixture 已验证集合扫描/单 session 写入；真实设备仍未验证 |

### 3.6 语料类型

| ID / sample | `supportLevel` | `activationStrategy` | `templatePath` | text counts | missing | font result | build allowed | install success | startup translation observed | evidence / current state |
|---|---|---|---|---|---|---|---|---|---|---|
| TXT-DIALOGUE / 对话 | 继承源样本 | 继承源样本 | 继承模板 | `fixture: 2 dialogue records` 或真实计数 | `not-run` | `not-run` | `conditional` | `not-run` | `not-run` | Task 15 fixture 覆盖相同 old、不同 dialogue ID；真机/存档仍待做 |
| TXT-MENU / 菜单 | 继承源样本 | 继承源样本 | 继承模板 | `not-run` | `not-run` | `not-run` | `conditional` | `not-run` | `not-run` | 菜单必须保留在全局 string map |
| TXT-CHARACTER / 角色名 | 继承源样本 | 继承源样本 | 继承模板 | `not-run` | `not-run` | `not-run` | `conditional` | `not-run` | `not-run` | 角色名不能因高级 dialogue ID 模式丢失 |
| TXT-UI / UI | 继承源样本 | 继承源样本 | 继承模板 | `not-run` | `not-run` | `not-run` | `conditional` | `not-run` | `not-run` | marked string 与 screen UI 需独立回归 |
| TXT-TAG / `{#}` | 继承源样本 | 继承源样本 | 继承模板 | `not-run` | `not-run` | `not-run` | `conditional` | `not-run` | `not-run` | 去重前保留 `{#...}`，旧键必须 exact match |
| TXT-INTERP / 插值 | 继承源样本 | 继承源样本 | 继承模板 | `not-run` | `not-run` | `not-run` | `conditional` | `not-run` | `not-run` | 占位符和插值形状须先 lint 再编译 |
| TXT-PRINTF / printf | 继承源样本 | 继承源样本 | 继承模板 | `not-run` | `not-run` | `not-run` | `conditional` | `not-run` | `not-run` | printf 占位符不匹配必须 reject |
| TXT-CONTEXT / 重复语境 | 继承源样本 | 继承源样本 | 继承模板 | `fixture: Fine. × 2` 或真实计数 | `not-run` | `not-run` | `conditional` | `not-run` | `not-run` | Task 8/15 fixture 覆盖 collision 与 dialogue ID 分流；真机 rollback 待做 |

## 3.7 C16 发布机器矩阵与完成定义

这些行把 Task 6–17 的可执行证据与外部验收分开记录。`PASS` 只表示控制的本地契约或构建门通过；真实样本、安装、启动、old save 和 rollback 没有证据时必须继续写 `NOT-RUN`。

| requirementId | machine gate | supportLevel / activationStrategy | template/source | unique/occurrence/collision | missing/rejected | font result | build/install/startup/save | status / evidence |
|---|---|---|---|---|---|---|---|---|
| C16-01 | engine generation: Python 2/3, SAFE/WARNING/EXTRACT_ONLY/UNSUPPORTED classification | `SAFE`, `WARNING`, `EXTRACT_ONLY`, `UNSUPPORTED`; `selectable` / `always-on` / `NONE` | Task 6–12 controlled RPYC/preflight fixtures; real GEN-6/7/8 sample `not-run` | fixture-specific counts; real `not-run` | real `missing/rejected=not-run` | real `not-run` | real build/install/startup/old save/rollback `NOT-RUN` | PASS for classification contracts; real sample NOT-RUN; T6–T12 evidence |
| C16-02 | archive/compiled format: loose RPYC2, RPA-1/RPA-2/RPA-3 and legacy zlib | compatible level inherited from preflight; unsupported shapes `EXTRACT_ONLY`/`UNSUPPORTED`, activation `NONE` | `RpycCompatibility`, RPA fixtures and legacy-zlib fixture; real archive source `not-run` | controlled fixture counts; real `not-run` | unknown/unsafe format blocked; complete real counts `not-run` | `not-run` | build may be `blocked` for unknown format; install/startup/save/rollback `NOT-RUN` | PASS for controlled parser/writer boundaries; real archives NOT-RUN; T7/T13 evidence |
| C16-03 | activation: standard/custom/none menu, selectable vs always-on | `SAFE`/`WARNING` as preflight decides; `selectable` and `always-on` remain separate | generated UI, language injection and C13 nullable-path fixtures; real game menu `not-run` | fixture counts only; real `not-run` | real `missing/rejected=not-run` | fixture gate; real `not-run` | tool artifact build PASS; device language/startup/old save/rollback `NOT-RUN` | PASS for UI/activation contract; device NOT-RUN; T12/T13/T15 evidence |
| C16-04 | font and text categories: dialogue, menu, character, UI, `{#}`, interpolation, printf, repeated context | inherited source level/activation; advanced dialogue ID defaults off | controlled structured-record/font/collision fixtures; real template/source `not-run` | fixture `uniqueTextCount/occurrenceCount/collisionCount`; real `not-run` | complete build requires `missing == 0` and `rejected == 0`; audit corpus `not-run` | controlled missing-glyph gate PASS; real `missingCodePoints` `not-run` | font/build/install/startup/save/rollback for real sample `NOT-RUN` | PASS for controlled coverage/font/lint contracts; real corpus NOT-RUN; T8–T11/T15 evidence |
| C16-05 | APK shape: `single APK` and `base + split` | inherited source level/activation; split uses one session | `InstalledApkSet`, `InstalledAppSource`, helper DEX and rebuilt workshop APK; real game package `not-run` | fixture counts; real `not-run` | real coverage `not-run` | fixture result; real `not-run` | local build/signature/asset gates PASS; SHA-256 `AF5D55B12AD0089C50539B99D9D370B4D197B90CCDD9CECAD83729C84C974295`; v2/v3 true; real install/startup/old save/rollback `NOT-RUN` | PASS for offline APK/helper shape; device split and single install NOT-RUN; T14/T15/T20 evidence |
| C16-06 | final release gate: automated, artifact, real sample and device definition of done | all declared support/activation modes must have evidence; `EXTRACT_ONLY`/`UNSUPPORTED` remain blocked | current evidence index and release checklist; real sample source/device prerequisites absent | automated fixture counts recorded; real `not-run` | mandatory real rows remain `NOT-RUN` | real font final set `not-run` | full release decision `NOT-RUN` until Task 21–22; no `批准发布` | NOT-RUN / waiting external acceptance; Task 23 must re-audit every PASS and NOT-RUN |

## 4. 预检报告和失败证据格式

每次真实样本执行都必须保存一个脱敏 JSON，建议命名为：

```text
docs/qa/evidence/<sample-id>/renpy-compatibility-report.json
docs/qa/evidence/<sample-id>/coverage-report.json
docs/qa/evidence/<sample-id>/build-validator.txt
docs/qa/evidence/<sample-id>/device-smoke.txt
```

报告至少包含以下固定字段；不得保存 APK 私有路径、完整脚本、翻译原文或 API 凭据：

```json
{
  "sampleId": "GEN-8-PY3",
  "sourceSha256": "<input fingerprint>",
  "supportLevel": "SAFE|WARNING|EXTRACT_ONLY|UNSUPPORTED",
  "activationStrategy": "SELECTABLE_LANGUAGE|ALWAYS_ON|NONE",
  "templatePath": "assets/.../script.rpyc",
  "uniqueTextCount": 0,
  "occurrenceCount": 0,
  "collisionCount": 0,
  "missing": "not-run",
  "rejected": "not-run",
  "font": {"required": 0, "covered": 0, "missing": "not-run"},
  "buildAllowed": false,
  "installSuccess": "not-run",
  "startupTranslationObserved": "not-run",
  "evidence": ["test name or device log path"],
  "failureCodes": []
}
```

失败证据必须保留稳定 code 和触发阶段，例如：

| 阶段 | 失败证据示例 | 处理 |
|---|---|---|
| 预检 | `renpy_rpyc_generation_unknown`、`renpy_python2_writer_unavailable` | 提取/诊断可以继续，编译必须阻断 |
| 激活 | `renpy_language_menu_missing`、`renpy_menu_strategy_unknown` | 进入 `ALWAYS_ON` 或要求人工确认；不能伪造 selectable 菜单 |
| 语料 | `missing`、`rejected`、`collision`、`uncertain` | 完整构建阻断；仅用户明确选择时生成 incomplete test patch |
| 字体 | `missingCodePoints` 非空 | 最终字体检查阻断 |
| 产物 | validator code 非 `OK` | 删除/放弃临时产物，禁止签名和安装 |
| 安装 | split metadata/signature/session 失败 | abandon session；不得显示安装成功 |
| 启动 | 未观察到译文、语言切换失败、旧存档失败 | 发布门禁阻断 |

## 5. 机器证据索引

以下结果只记录已经执行过的命令；本节在每次最终回归后更新，不用“预期通过”替代实际输出：

| 检查 | 命令/证据 | 当前记录 |
|---|---|---|
| scanner regression | `python -m unittest test_fast_scanner.py -v` | Task 19 fresh 实际为 `77` tests，0 failures，OK |
| workshop regression | `python -m unittest test_workshop_patch.py -v` | Task 19 fresh 实际为 `60` tests，0 failures，OK |
| quality / coverage / performance | `python -m unittest test_translation_quality.py test_translation_coverage.py test_engine_performance.py -v` | Task 19 fresh 实际为 `37` tests，0 failures，1 explicit audit-fixture skip；skip 是真实完整 APK/语料缺失，不能当 coverage 通过 |
| syntax / loader contract | `python -m py_compile ...`；`test_shared_apk_loader_and_installed_selection_behavior` | Task 19 fresh 实际通过；split loader 的 Node 语法错误已修复 |
| built APK | `python -m unittest test_built_apk.py -v` | Task 20 fresh 实际为 `4` tests，0 failures，OK；APK hash/signature/version 已在 Task 20 记录 |
| Java/D8 helper | `python build_fast_scanner.py` | 已实际构建成功；D8 使用 build-local response file 规避 Windows 命令行长度限制 |
| helper classes | `dexdump` on `generated/classes7.dex` | Task 20 fresh 验证 12 个要求类各恰好一个：FastApkScanner、RenpyTextRecord、RenpyTextValidator、TranslationCoverageReport、RenpyCompatibilityReport、RenpyPreflight、RenpyPatchValidator、RpycPickleWriter、InstalledApkSet、InstalledAppSource、PackageInstallerSupport、RenpyDialogueTranslation |
| workshop APK | `python build_workshop_apk.py` | Task 20 fresh exit 0；`versionCode=7`/`versionName=1.0.7`；SHA-256 `AF5D55B1...C974295`；apksigner v2/v3 true；debug certificate only |
| full discover | `python -m unittest discover -s . -p 'test_*.py' -v` | Task 19 fresh 实际为 `192` 项、0 failures/errors、1 个明确 `audit APK/extracted texts not present` skip；真实样本/设备仍 NOT-RUN |

## 6. 矩阵完成规则

只有当某个样本同时拥有兼容性报告、覆盖率报告、产物 validator 结果以及（若声明安装/启动成功）真机日志时，才可以把对应行从 `not-run` 改为结果值。没有真实样本时，发布状态必须是“未批准”，但不妨碍发布工具本身的测试构建。
