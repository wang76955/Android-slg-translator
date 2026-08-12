# Ren'Py 引擎源码优化交接文档

> 日期：2026-08-06
> 目标：新会话直接按本文档开始优化 Android 端 Ren'Py 翻译/注入工具
> 引擎参考：`https://github.com/renpy/renpy` master，本地镜像 `D:\文件翻译\_renpy-engine-ref`
> 当前端：`apk-work`（Capacitor + Java 原生插件 + llama.cpp 本地 LLM）

## 0. 结论摘要

官方源码确认了当前项目的整体路线是正确的：

- Android APK 内只加载编译后的 `.rpyc`，直接写入 `assets/x-game/x-tl/x-slgtranslated/x-translations.rpyc` 是官方机制支持的注入方式。
- `translate <lang> strings:` 的 `old/new` 替换正是官方字符串翻译机制，对话、菜单、角色名、`_()` UI 字符串都会走这条路径。
- 不需要移植完整 Ren'Py Python 编译器；应把官方源码当作“行为基准”，逐项对齐本地 Java/JS 实现。

本轮最有价值的优化方向，按优先级排列：

1. 支持 RPA-1/2/3 归档读取，解决大量 APK 的 rpyc 藏在 `game/*.rpa` 里导致漏扫的问题。
2. 支持旧版整文件 zlib 的 rpyc，解决老游戏提取不到文本的问题。
3. 给 `LocalLlmEngine` 加确定性占位符保护，避免小模型改写 `{...}`、`[...]`、`%s`。
4. 用官方 `STRING_RE` 的覆盖面扩展文本抓取：三引号、单引号、`_p`、`__`、`___`。
5. 增加缺失翻译统计与增量更新机制，形成“提取 -> 翻译 -> 覆盖率 -> 下次补翻”闭环。
6. 在 `readTemplateMeta` 中优先选择游戏本体 rpyc，避免 `version/key` 混用。

## 1. 官方引擎关键行为

### 1.1 rpyc 槽结构与校验

源码：`renpy/script.py`

- `RPYC2_HEADER = b"RENPY RPC2"`，`RPYC_MAGIC = b"_2026-08-05"`（master）。
- 槽表位于 header 之后，每条 12 字节：`slot / offset / length`，最多 3 条。
- 槽 1：静态转换前 pickle；槽 2：静态转换后 pickle。
- 运行时优先读槽 2，失败或不存在时读槽 1；读槽 1 后需要重新执行 `static_transforms()`。
- 文件尾 16 字节是 `md5(对应 .rpy 内容 + RPYC_MAGIC)`。
- 纯 archive 路径不校验 trailer；只有磁盘同时存在 `.rpy` 和 `.rpyc` 时才比较 digest 决定是否重编译。
- `data["version"]` 必须等于运行引擎的 `script_version`，`data["key"]` 必须与整个游戏一致，否则拒绝加载。

### 1.2 文本抓取规则

源码：`renpy/translation/scanstrings.py`

- `STRING_RE` 匹配 `_`、`__`、`___`、`_p`，支持单引号、双引号、三引号字符串。
- 扫描后按优先级排序并去重：`script.rpy=5`、`options.rpy=10`、`gui.rpy=20`、`screens.rpy=30`，其余 `500`。
- `translate_list_files()` 跳过 `tl/`，避免把游戏自带翻译当成源文本。
- 菜单项由 `Menu.get_translation_strings()` 注册为附加字符串。
- `Character(_("Name"))` 是官方推荐的角色名写法；即使不用 `_()`，运行时 `prefix_suffix()` 也会对角色名执行字符串翻译。

### 1.3 字符串查找与标识符

源码：`renpy/translation/__init__.py`

- `StringTranslator.translate()` 查找顺序：精确 `old` -> 去掉 `{#...}` 后查找 -> 返回原文。
- `{#project}`、`{#game}` 这类 key 必须保留，不能清洗后合并。
- `RENPY_UPDATE_STRINGS` 会把运行时未收录字符串写回 `tl/<lang>/strings.rpy`，适合增量补翻。
- 对话块标识符规则是 `label.replace(".", "_") + "_" + md5(say code)[:8]`，并且支持显式 `id` 子句与 alternate；当前项目使用字符串翻译，可暂不移植。

### 1.4 LLM/自动翻译占位符

源码：`scripts/automatic_translate.py`

- 官方 DeepL 脚本把 `{...}`、`[...]` 包成 `<span translate="no">...</span>`，翻译后再还原。
- 带 blocklist，跳过 `{#`、`APPDATA`、`$HOME`、URL 前缀等。
- 对本地 Qwen 小模型，建议不要依赖 prompt，使用确定性 sentinel 替换和恢复。

### 1.5 RPA 归档与 Android 路径

源码：`renpy/loader.py`、`launcher/game/archiver.rpy`

- Android 主资源：`assets/x-game/`
- Android 引擎公共资源：`assets/x-renpy/x-common/`
- 拆分 APK：`assets/game/`、`assets/renpy/common/`
- RPA-3.0 头：`RPA-3.0 %016x %08x\n`，前 40 字节，偏移在第 8-24 字节，key 在第 25-33 字节。
- 索引为 zlib 压缩的 pickle dict，条目是 `(offset ^ key, length ^ key, start_bytes)`，官方写入 key 固定为 `0x42424242`。
- RPA-2.0 头为 24 字节，无 XOR；RPA-1 由 `.rpi` 直接 zlib 解压得到索引。
- `tl/<lang>` 是懒加载的，切换语言时通过 `renpy.change_language()` 加载，不需要修改 init。

## 2. 本地现状与官方差异

| 模块 | 本地现状 | 官方行为 | 风险 |
|------|---------|---------|------|
| `FastApkScanner` | 只枚举 APK zip 条目 | 支持 RPA-1/2/3、拆分 APK | RPA 游戏整包漏扫 |
| `RpycTextExtractor.readSlot` | 只支持 RPC2 header | 支持旧版整文件 zlib rpyc | 老游戏提取为空 |
| `TranslationCompiler` | 两个槽写同一份 pickle，复制模板 trailer | 槽 1/2 可不同，trailer 来自源 rpy | archive-only 可用，未来有 `.rpy` 时会被重编译 |
| `TranslationCompiler.readTemplateMeta` | 扫描所有 assets，取第一个可用模板 | 应使用游戏本体同版本 rpyc | 可能混用 common 的 version/key |
| `RpycTextExtractor.collectExtraTexts` | 正则只匹配 `_("...")` | 支持单/双/三引号、`_p`、`__`、`___` | 漏 UI 与复数文本 |
| `LocalLlmEngine` | prompt 要求保留占位符 | 官方做确定性保护 | 小模型可能改写 `{}`/`[]`/`%s` |
| 翻译结果 | 有缓存和本地规则 | `RENPY_UPDATE_STRINGS` 可增量回写 | 游戏更新后缺翻译不直观 |
| 覆盖率 | 有已翻译数量 | `count_missing()` 统计缺失 | 用户不知道缺多少、缺哪里 |
| 语言菜单 | `LanguageMenuSupport` 克隆语言按钮 | `change_language()` 懒加载 tl | 自定义菜单仍可能失败 |

## 3. 建议做的事

### P0-1：RPA 归档读取

位置：`FastApkScanner.java`

目标：扫描 APK 时，对每个 `.rpa` 条目解析内部文件列表，并把其中的 `.rpy/.rpyc/.rpym/.rpymc` 加入候选文件。

实现要点：

- `RPA-3.0`：读前 40 字节，`offset = int(header[8:24], 16)`，`key = int(header[25:33], 16)`；seek 到 offset，zlib 解压，pickle 解析 dict。
- 条目 `(offset ^ key, dlen ^ key)`，可复用现有 `LanguageMenuSupport.walk()` 的 pickle opcode 工具。
- `RPA-2.0`：读前 24 字节，`offset = int(header[8:], 16)`，无 XOR。
- `RPA-1/.rpi`：整个文件 zlib 解压后就是索引。
- 内部文件名映射为运行时路径，例如 `game/chapter1.rpyc`。
- 只读 RPA 即可；注入仍写 APK 的 `assets/x-game/x-tl/...`，不需要重写 RPA。

验收：

- 构造一个 RPA-3.0 样例（用官方 `archiver.rpy` 算法或 Python 脚本生成），内含 `chapter1.rpyc`，扫描结果能列出该文件并提取出文本。
- 真机扫描一个脚本在 RPA 内的 Ren'Py APK，候选文件数明显增加。

### P0-2：旧版 rpyc 回退

位置：`RpycTextExtractor.readSlot()`

目标：当文件前 9 字节不是 `RENPY RPC2` 时，把整个文件作为 zlib 数据解压，视为槽 1。

实现要点：

- 参考官方 `read_rpyc_data()`：legacy 路径 `slot != 1` 返回 None，`slot == 1` 时 `zlib.decompress(f.read())`。
- 同时检查 `TranslationCompiler.readSlot()`，确保写入侧不会误判旧格式。
- 扫描结果里可增加 `rpycFormat: "rpc2" | "legacy"`，便于统计兼容性。

验收：

- 准备一个旧版整文件 zlib rpyc fixture，`extractTexts()` 能返回文本。
- 现有 RPC2 fixture 回归不破坏。

### P0-3：LocalLlmEngine 确定性占位符保护

位置：`LocalLlmEngine.java`

目标：翻译前保护占位符，翻译后还原，并校验数量。

实现要点：

- 正则提取 `{...}`、`[...]`、`%s/%d/%f`、`$` 前缀变量、`{{`/`[[` 转义形式。
- 替换为 `«0»`、`«1»` 或 `__PH0__` 这类模型不易改写的 sentinel。
- 翻译完成后逐一还原，若任一 sentinel 缺失或顺序被破坏，丢弃该条结果并记 warning。
- 跳过规则参考官方 blocklist：含 `{#` 的 key、路径常量、`APPDATA`、`$HOME`、URL、纯引擎内部字符串。
- 若 Web/API 端已有 `__PH0__` 机制，Android 本地端保持一致命名，方便以后共享工具类。

验收：

- 输入 `"{b}Hello{/b} [name]!"`，输出必须包含完全相同的 `{b}`、`{/b}`、`[name]`。
- 输入 `"Score: %s / %d"`，输出占位符顺序和类型不变。
- 单测覆盖模型“自作聪明改写占位符”的失败路径。

### P0-4：模板选择优先游戏本体 rpyc

位置：`TranslationCompiler.readTemplateMeta()`

目标：`version/key` 必须来自游戏本体，而不是引擎公共目录。

实现要点：

- 优先扫描 `assets/x-game/` 和 `assets/game/` 下的 `.rpyc`。
- 只有找不到时才回退到 `assets/x-renpy/` 或 `assets/renpy/`。
- 在同一 APK 出现多个版本时，优先选择 `assets/x-game/x-tl/` 之外的普通脚本 rpyc。
- 保留 `meta.trailer` 复制逻辑，但加注释说明 archive-only 不校验。

验收：

- 构造含不同 `version/key` 的混合 APK fixture，编译结果使用游戏本体的值。
- 现有注入后游戏能加载翻译的回归用例通过。

### P1-1：扩展文本抓取覆盖面

位置：`RpycTextExtractor.java`

目标：对齐官方 `STRING_RE`。

实现要点：

- 增加 `'(...)'`、`'''...'''`、`"""..."""` 支持。
- 增加 `__()`、`___()`、`_p()` 识别。
- `_p` 至少提取字符串字面量；若游戏常用复数形式，再研究官方 `renpy.minstore._p` 的 key 语义。
- 保持现有 `isUserText()` 过滤，但不要在过滤前把 `{#...}` 删除。
- 在 JS 侧确认去重逻辑没有把 `{#...}` 差异合并成一个 key。

验收：

- 新增 fixture：`_('single')`、`_(r"""multi""")`、`_p(1, "one", "many")`，均能提取。
- 全量回归语料条数不下降。

### P1-2：缺失翻译统计

位置：`FastApkScanner` 结果、前端处理流程

目标：让用户看到“可翻译 N 条 / 已翻译 M 条 / 缺失 K 条”。

实现要点：

- 仿照官方 `count_missing()`：扫描得到的唯一文本集合与翻译缓存/结果 key 集合做差。
- 缺失统计按文件分组，给出前 20 条样例和文件路径。
- 在补丁完成页显示缺失数，而不是只显示成功条数。
- 为“游戏更新后补翻”预留入口：保留上一版翻译 JSON，新版本只翻译新增 key。

验收：

- 构造一个故意漏翻 5 条的 APK，界面显示 `缺失 5` 且样例可定位文件。
- 更新游戏脚本后，旧译文不重复翻译，只补新增文本。

### P1-3：语言切换与懒加载说明落地

位置：`LanguageMenuSupport.java`、前端提示

目标：确认注入语言菜单后调用的是官方 `change_language()` 语义。

实现要点：

- 语言菜单注入成功后，游戏内选择 `slgtranslated` 会触发 `renpy.change_language("slgtranslated")`，此时才懒加载 `tl/slgtranslated`。
- 若游戏使用自定义语言菜单且注入失败，可考虑注入启动时强制 `renpy.change_language()`，但要在 UI 明确提示“启动即启用翻译语言”。
- 参考官方顺序：Python -> early block -> callbacks -> deferred styles -> block -> 系统样式 -> free memory -> block rollback，不要在注入脚本里乱序执行。

验收：

- 真机安装补丁后选择“翻译文本”，对白、菜单、角色名、UI `_()` 字符串全部切换。
- 切换回原语言后恢复原文本，不残留翻译缓存。

### P2-1：rpyc trailer 正确性

位置：`TranslationCompiler.java`

目标：仅在同时注入 `.rpy` 源码时需要真正计算 trailer。

实现要点：

- 保持当前 archive-only 复制模板 trailer 的策略，但增加注释说明原因。
- 如果未来补丁同时写入 `.rpy`，必须计算 `md5(.rpy 内容 + RPYC_MAGIC)` 作为 trailer。
- 不要从随机模板复制 trailer 后还宣称它“校验通过”。

### P2-2：增量更新与翻译记忆

位置：前端缓存、`TranslationCompiler` 合并逻辑

目标：参考官方 `RENPY_UPDATE_STRINGS` 和 `extract_strings/merge_strings`。

实现要点：

- 翻译记忆采用 JSON `{old: new}`，支持 `--merge` 语义：已有译文保留，新译文追加。
- 导出/导入翻译 JSON，方便跨游戏、跨版本复用。
- 合并时保留第一个 key，不因文件顺序变化覆盖已有翻译。

### P2-3：拆分 APK 扫描

位置：`FastApkScanner`、前端选择流程

目标：对齐官方 `find_apks()` 的 `assets/game/` 拆分路径。

实现要点：

- 安装包来源扫描时读取 `PackageManager.getSplits()` 的所有拆分 APK。
- 主 APK 读 `assets/x-game/`，拆分包读 `assets/game/`。
- 注入仍写主 APK `assets/x-game/x-tl/...`，保证所有拆分都可见。
- 若拆分 APK 无法读取，UI 明确提示哪些文件来自拆分包。

### P2-4：翻译调试信息

位置：前端“校验”页

目标：提供类似官方 `_translation_info` 的调试能力。

实现要点：

- 补丁安装后，可注入/显示当前对话翻译 ID、源文件、对应翻译文件。
- 至少在前端提供“扫描该 APK 的 tl 语言桶数量、rpyc 格式统计、RPA 文件数”的诊断页。
- 便于用户反馈问题时快速定位是提取、编译还是语言菜单的问题。

## 4. 不建议做的事

- 不要在 Android 端移植完整 Ren'Py Python 解析器/编译器。
- 不要为了“校验”而强制验证 archive-only rpyc 的 trailer，官方本来就不校验。
- 不要把 `{#...}` 从 key 中剥离后再去重，会破坏运行时精确匹配。
- 不要用“模型会遵守 prompt”替代占位符保护。
- 不要重写 RPA 来实现注入；新语言包放 APK `x-tl` 目录即可。
- 不要依赖 APK 内的 `.rpy` 文件，archive 加载路径只会读取 `.rpyc`。

## 5. 建议实施顺序

1. 建立 RPA fixture 与旧 rpyc fixture，先补自动化测试。
2. 实现 RPA 读取（P0-1）。
3. 实现 legacy rpyc 回退（P0-2）。
4. 实现本地 LLM 占位符保护（P0-3）。
5. 修正模板选择（P0-4）。
6. 扩展文本抓取正则（P1-1）。
7. 增加缺失翻译统计与增量更新（P1-2、P2-2）。
8. 完善拆分 APK、trailer、调试信息（P2-1、P2-3、P2-4）。

## 6. 验证清单

- [ ] RPA-3.0 fixture 扫描出内部 rpyc。
- [ ] legacy rpyc fixture 提取出文本。
- [ ] 占位符保护单测覆盖 `{...}`、`[...]`、`%s`。
- [ ] `readTemplateMeta` 优先选择 `assets/x-game/`。
- [ ] 三引号/单引号/`_p` fixture 提取通过。
- [ ] `{#}` key 不被合并或剥离。
- [ ] 缺失统计能发现故意漏翻。
- [ ] 真机安装后语言菜单切换成功。
- [ ] 现有 `translation-extraction-rules.md` 与 `translation-quality-rules.md` 的回归经验不回归。

## 7. 相关文件索引

- 引擎源码镜像：`D:\文件翻译\_renpy-engine-ref`
- 当前抽取规则：`docs/translation-extraction-rules.md`
- 当前翻译质量规则：`docs/translation-quality-rules.md`
- Android 原生插件：`apk-work/native-fast-scan/src/com/slgtranslator/app/`
- 前端生成物与 QA：`apk-work/ui-redesign/`
