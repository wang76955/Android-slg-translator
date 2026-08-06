# Ren'Py 文本抽取与过滤规则（经验总结）

> 本文档沉淀自“恶女2.2”全量翻译对比审计（2026-08-02）。
> 目标：任何 Ren'Py APK 都做到“可翻译文本一条不漏”，且 key 与运行时完全一致。

## 1. 抽取管线总览

```
APK 内 rpyc/rpymc
   │  RpycTextExtractor.extractTexts（原生，结构化解 pickle）
   ▼
RPYC_STRING 行协议（按行分隔；换行/制表转义为 \n \r \t；反斜杠先转义为 \\）
   │  JS Ne()：去空行/去重/单遍还原转义
   ▼
翻译候选文本列表
   │  Ue() 短文本过滤 / Ke() 代码与路径过滤 / He() 代码调用过滤
   ▼
翻译 → 生成 tl/<lang>/*.rpy（old/new 用 JSON.stringify 转义）
   │  parseTranslationRpy + unquote（合并端）
   ▼
合并写入 assets/x-game/x-tl/x-slgtranslated/x-translations.rpyc
```

## 2. 各过滤规则及用途

| 函数 | 规则 | 用途 |
|------|------|------|
| `RpycTextExtractor` | 取 Say 的 `what`、菜单 `caption/items`、官方 marked-string helper（`_()` / `__()` / `___()` / `_p()`，支持单/双/三引号与合法字符串前缀）、`Character("名")`、translate 块 `old`；**源码字符串中的消息类/偏好类函数调用参数**（`send_phone_message("发送者","消息",...)`、`_VolumePreference(u"标签",...)` 等）；翻译文件用 **old-only 模式**只取 `old` key | 保证与 Ren'Py 运行时 key 一致，且不漏手机短信/设置标签 |
| `Ne`（rpyc 行协议） | 丢弃空行与重复；长度 ≥1；单遍还原 `\\`/`\n`/`\r`/`\t` | 防止把“字面反斜杠+n”误还原成真换行 |
| `Ue`（短文本） | 丢弃纯标点、hex 颜色、小写 1-2 字母标识符、全大写 2-12 token、小写下划线标识符 | 保留 `E`/`Sky`/`Fine` 等大写短名与选项 |
| `Ke`（代码/路径） | 含 `/` 或 `\` 且**无空格**的 token 判为路径丢弃；后缀/前缀代码模式丢弃 | 保留 `A/Bottom Button`、带 URL 的句子 |
| `He`（代码调用） | 函数调用、赋值、`__`、驼峰小写开头、短 hex、Ren'Py 语句关键字 | 滤掉 pickle 噪声 |
| `_rpycSkip`（候选文件） | 跳过 `gui/media/gallery/gallery_new/common/style/audio/images/init/splash/preferences`（**不跳 `options`**） | `x-options.rpyc` 里有游戏标题，必须可译 |
| rpy 写出 `ls=JSON.stringify` | 字符串原样转义，保证 `old` key 与运行时一致 | 防止丢首尾空白 |

## 3. 审计中发现并修复的三个根因

1. **反斜杠/换行回程损坏 key（影响 17 条）**
   原生协议只转义 `\n\r\t` 不转义 `\`，JS 端再无条件把 `\n` 还原成真换行，
   导致原文中“字面 `\n`”（Ren'Py 屏幕文本常见）被改写成真换行，翻译 key 与运行时不符，游戏里查不到译文。
   修复：原生先转义 `\`（`text.replace("\\","\\\\")`），JS 端用单遍正则
   `/\\(?:\\|n|r|t)/g` 还原，字面反斜杠与真换行互不串扰。

2. **`/` 与 `\` 一刀切过滤（影响控制器/同步/剪贴板等 UI 文本）**
   `Ke` 原先只要含 `/` 或 `\` 就丢弃；改为“含分隔符且无空格”才判路径。
   带空格的 `Right Trigger\nA/Bottom Button`、带 URL 的 Ren'Py 同步说明、颜色标签 toast 全部保留。

3. **候选名单误跳 `options`（影响游戏标题）**
   `_rpycSkip` 原包含 `options`，导致 `x-options.rpyc` 里的“游戏标题”整条不译。
   移除 `options` 后标题可译。

## 4. 第二轮审计：手机短信/UI 文本漏译（本次修复）

首轮修复后重跑全量对比，语料从 30,875 增至 32,683 条（新增约 1,800 条手机短信 + UI 文本），缺译 1,827 条。逐条核实根因：

1. **手机短信文本藏在源码字符串里（约 1,800 条）**
   `x-phone.rpyc`（及各章节脚本）的 pickle 内嵌整段 Python 源码（单条 BINUNICODE），
   短信是 `send_phone_message("Aine", "消息", "频道", ...)` 的字符串参数，
   不在 Say 的 `what` 字段，旧 extractor 一个都提不到。
   修复：`collectSourceCallTexts` 从源码字符串识别消息类函数
   （函数名含 `message/phone/chat/dm`）提取前 2 个字符串参数，
   识别偏好类函数（`_*Preference`）提取标签；变量参数、路径、空串仍被 `isUserText` 滤掉。

2. **UI 文本只在官方翻译 old keys 里（约 190 条）**
   “And Sky is her? (Default: tenant)”、“Music Volume” 等运行时动态文本
   不出现在任何原始 rpyc，只在 `x-tl/x-chinese|english|german/` 的 `TranslateString` old keys。
   修复：
   - extractor 增加 `extractTexts(rpyc, onlyOld)` 重载——翻译桶文件只取 `old` key，
     绝不让翻译后的 `what`/`new`（中文/德文）污染语料；
   - JS 候选过滤 `Yo` 允许 chinese/english/german 翻译桶进入（排除 slgtranslated 自身与 none）；
   - `_f`（写回补丁的文件列表）同步保留翻译桶、排除 `x-slgtranslated`。

3. **补充语料与原始翻译同名输出互相覆盖（本轮最严重 bug）**
   `x-german/x-ch1ep1.rpyc` 与原始 `x-ch1ep1.rpyc` basename 相同，
   `os()` 生成同一个 `x-tl/x-slgtranslated/x-ch1ep1.rpy`，后处理者覆盖先处理者，
   导致章节翻译只剩 27 条菜单选项、数千条对话全部丢失（编译后 key 仅 4,300）。
   修复：`os()` 对翻译桶输出文件名加源语言前缀
   （`x-tl/x-slgtranslated/x-german-x-ch1ep1.rpy`），与原始翻译并存，编译端 `merged` 去重合并。

4. **翻译中断“页面刷新”**
   OPPO 屏幕熄灭/系统优化会回收 WebView 渲染进程，`onRenderProcessGone` reload 后
   JS 状态丢失，报“翻译会话因页面刷新中断”。
   修复：翻译/生成补丁状态下用 `navigator.wakeLock.request("screen")` 保持屏幕常亮
   （渲染进程不再被回收），其他状态释放；实测 195 个文件全程无中断。

## 5. 当前验证状态

- 全套 73 项红绿灯测试通过（extractor fixture、JS 过滤、os() 路径、wakeLock、APK pin、审计 pin）。
- 全量审计：语料 32,683 条唯一文本 vs 已翻译 32,936 条 key，**missing = 0**。
- 真机：195 个可翻译文件一次跑完、40,434 条译文、补丁 APK 签名校验通过、
  游戏内新增独立“翻译文本”语言入口。

## 6. 经验沉淀（写给下一个游戏）

- 对话不只藏在 Say 的 `what`：手机/聊天/即时消息系统通常把文本写成自定义函数调用参数，
  它们以整段源码字符串存在 pickle 里，必须做函数调用参数提取。
- 官方 marked-string helper 不能只靠单个正则：`_()/__()/___()/_p()` 会混用三引号、raw/u/b 前缀与多行文本，
  必须做确定性词法扫描；`_p(context, text)` 的 `context` 只保存在结构化记录的 `identifier`，
  绝不能当普通可见文本送去翻译。
- 官方多语言翻译文件（x-tl/<lang>/）是“补充语料金矿”：其 `old` key 覆盖运行时动态文本；
  但提取时必须 old-only，否则翻译后的 `what`/`new` 会污染语料。
- 补充语料与原始脚本常同名：输出路径必须区分来源（加语言前缀），否则相互覆盖。
- 长任务必须保持屏幕常亮（Wake Lock），否则 WebView 渲染进程被系统回收导致任务中断。

## 8. Official marked-string forms without full Ren'Py runtime (2026-08-07 fix)

- 识别范围：`_()`、`__()`、`___()`、`_p()`；支持单引号、双引号、三单引号、三双引号，以及合法字符串前缀（如 `r` / `u` / `b` 组合）。
- 静态可恢复的前缀集合为无前缀、`r`、`u`、`b`、`ur`/`ru`、`br`/`rb`（大小写不敏感）；重复、非法组合和格式化 `f` 前缀不当作静态文本。三引号只在匹配的同类三引号处结束，结束后的相邻调用仍分别扫描。
- `_p(context, text)`：只把第二个参数作为可见文本；`context` 通过结构化 `RenpyTextRecord.identifier` 保留关联，不进入旧的 `extractTexts()` 文本流。
- `{#...}`：必须保留为 exact key，例如 `Save{#slot}` 与 `Save{#menu}` 是两个不同翻译 key，不能在缓存/编译前合并。
- 动态/无法静态求值的 helper 调用，以及无法静态理解的 `UserStatement`：不把表达式源码当译文；在 `extractRecords()` 中留下 `UNKNOWN + coverageCertain=false` 的诊断记录，同时保持 `extractTexts()` 兼容，不输出空文本。


## 7. Ren'Py markup tags with '/' cause isUserText false rejection (2026-08-03 fix)

**Root cause**: `isUserText()` in `RpycTextExtractor.java` rejected ANY text
containing '/' as a potential file path. However, Ren'Py rich-text markup
tags like `{/i}`, `{/b}`, `{/color}` also contain '/', and these appear in
character dialogue `what` values throughout the game.

**Impact**: 726 dialogue lines with markup tags (italic, bold, color) were
silently dropped during extraction. The audit showed `missing = 0` because
the missing texts were never in the corpus to begin with - a blind spot in
the audit methodology.

**Fix**: Strip all `{...}` tags before the path-character check. The Java code
now does `s.replaceAll("\\{[^}]*\\}", "")` before checking for path
separators.

**Lesson**: Path filters must not use a naive '/' check. Ren'Py markup tags
are ubiquitous in dialogue and always contain '/' in their closing form.
Always strip known markup patterns before applying path/file filters.
