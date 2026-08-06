# 视觉小说 AI 翻译质量规则（经验总结）

> 本文档沉淀自 2026-08 桌面版与 Android 版的翻译质量优化迭代。
> 目标：任何视觉小说 EN→ZH 翻译都达到"有本地化意识、无翻译腔、场景内连贯一致"的水准。
> 执行位置：Android 版 `apk-work/ui-redesign/patch_workshop_ui.py` 的
> `QUALITY_PROMPT_EN_ZH`（system prompt）与 `patch_translation_quality`（批次上下文注入）。

## 1. 质量优化总览

翻译质量 = Prompt 工程 + 上下文注入 + 工程保障，三者缺一不可：

| 层 | 手段 | 作用 |
|----|------|------|
| Prompt 工程 | 分层系统提示词（定位→原则→习惯→规则→示例→输出格式） | 让模型按"有经验的汉化组"的方式翻译 |
| 上下文注入 | 来源文件名、说话人（.rpy 源格式）、同场景连续行提示 | 让模型知道文本从哪来、谁在说、前后是什么 |
| 工程保障 | `__PH0__` 占位符保护、缓存、本地规则、失败二分重试、并行批次 | 保证格式零损坏、成本可控、任务不中断 |

## 2. 通用视觉小说翻译习惯档案（权威版）

适用所有视觉小说 EN→ZH，不依赖具体游戏数据。改动时须同步
`patch_workshop_ui.py` 中的 `QUALITY_PROMPT_EN_ZH` 与本文档。

1. **口语化**：对话必须像中文母语者说出来的话。自然使用语气词
   （呢/吧/啊/嘛/哦/呀），但不要每句都堆。
2. **感叹词对照表**：Hmph→哼，Ah→啊，Uh/Ugh→呃/唔，Huh→嗯/诶，Ha→哈，
   Oh→哦/啊，Hmm→嗯……，\*sigh\*→（叹气）/唉，\*laugh\*→（笑）/呵呵，
   \*yawn\*→（打哈欠）。星号舞台提示保持简短自然，不过度翻译。
3. **拟声词本地化**：bang→砰，creak→吱呀，rustle→沙沙，thud→咚；
   不保留罗马音。
4. **省略号**：一律用……（两个省略号），禁止三点（...）。
5. **短句节奏**：短句保持短促有力。不把两句并成一句，不把一句拆成两句。
6. **称呼适配**：mom/dad/brother→妈妈/爸爸/哥哥/姐姐（按关系和语域）；
   Mr./Miss→先生/小姐；仅当题材明确需要时才用 君/桑。
7. **内心独白 vs 旁白**：第一人称想法用"我"自然表达；旁白可略文学化但必须
   流畅；中文体貌（了/着/过）不要滥用。
8. **重复有意义**：原文为强调而重复的词或句式，中文保留重复。
9. **术语一致性**：同一场景内同一术语/人名译法完全一致。
10. **文化引用**：有意译时用中文惯用表达；否则保留原意。绝不加译者注。

## 3. 上下文策略

### 3.1 来源文件名
Ren'Py 提取的 keyPath 形如 `assets/x-game/tl/x-english/chapter1.rpy::rpyc_string_0`，
取 `::` 前段再取最后一段文件名，注入批次请求开头：`Source file: chapter1.rpy`。模型由此获得题材/章节背景。
**经验教训**：早期提取调用 `ke(i,s,``,g)` 把 keyPath 前缀传成空串，真实 keyPath 是纯序号
（`rpyc_string_0`），导致 Source file/场景提示从未触发，而测试用虚构的 `file::seq` 格式掩盖了
问题。修复：调用点传 `o.name+`::``。任何 keyPath 格式假设都必须用真实提取产物验证。

### 3.2 说话人（仅 .rpy 源格式可用）
`maria "text"` 行能捕获说话人（Le 正则 group 1）。说话人随占位符保护（Ro）、
去重（No 保留第一个 speaker）一路传递，在请求中标注 `[0] → maria`。
**注意**：RPYC 二进制提取（`RPYC_STRING` 协议）输出纯文本行，**没有**说话人，
因此不能依赖说话人做角色级一致性。

### 3.3 同场景连续行（主要场景感知手段）
当批次内全部文本来自同一文件时，注入：
> These are consecutive lines from the same scene (chapter1.rpy). Translate them
> as one coherent dialogue flow — keep tone, terminology and speaking habits
> consistent across all lines.

这是纯文本行数据下最重要的场景感知手段：问答逻辑、语气、专名在批次内自然连贯。
判断条件与分级：
- **强提示（consecutive）**：同文件 + 所有行都能解析出序号（`rpyc_string_N`/`rpy_N`/`ast_N`/`[L_N]`/`[rNcM]`）+ 排序后相邻序号差为 1
- **弱提示（same file）**：同文件但序号跳号（缓存/本地规则剔除导致）或无法解析序号——只用
  "lines belong to the same file"，避免用 "consecutive" 误导模型
- **无提示**：keyPath 无 `::`（非 Ren'Py 提取），退化为原行为

跳号场景必须用弱提示：批次中的行可能因缓存/本地规则命中被剔除，`0,2,4` 不是连续行。

## 4. Prompt 工程经验

分层结构（自顶向下）被证明有效，原因：
- **角色定位**：一句话设定"资深视觉小说本地化译者"，激活专业行为
- **核心原则**：翻译腔、情感、意译、保留原名——先立原则再立规则
- **习惯档案**：把汉化组的行业惯例显式列出（见第 2 节）
- **具体规则**：占位符、标点、语域、不加注释
- **Few-shot**：2-3 组与线上格式完全一致的示例（EN→ZH 对话/UI），
  比纯规则更能锁住输出形态
- **输出格式**：JSON 指令放最后，模型遵循度最高

### 模型策略
- `supportsJsonMode` 为 false 的模型（deepseek-v4-pro / reasoner）：
  不加 `response_format: json_object`，靠 `Uo` 从 markdown/包裹文本恢复 JSON
- 推理模型在 prompt 开头附加
  `Think carefully about each line's context, tone and natural expression before translating.`
- 默认 v4-flash（快/便宜），v4-pro 可选做高质量模式

## 5. 工程保障经验

- **占位符保护（关键）**：翻译前用正则把 `{...}`、`[...]`、`%s/%d`、`${...}`
  替换为 `__PH0__` 序列，翻译后逐一还原。比"翻译后校验缺失"更可靠——模型
  根本不会碰到占位符。
- **缓存**：按 (语言对, 模型, 术语表, 源文本 hash) 缓存，重复文本零成本。
  **策略版本**：当前实现保留既有缓存命名空间 `slg-translator-cache:`，不通过改名使旧缓存失效。
  任何改变翻译输出的策略升级（prompt/上下文/模型行为）若确实需要改变缓存格式，必须引入明确的
  schema/version 并提供兼容读取，不能静默改写既有缓存键语义。
  **内存管理**（2026-08-04 修复）：清理缓存必须同步清空所有引用结构——曾出现 `full` 模式只清
  `vo={}` 但 `cacheIndex` 残留，导致旧缓存引用不释放且 `To()` 仍能命中（清理无效）。
  另设缓存上限 30000 条：`wo()` 保存前调用 `maybePruneCache()`，按 `updatedAt` 淘汰最旧一半
  并同步删除 `cacheIndex` 引用，防止翻译缓存无限增长。JS 堆释放后 V8 不一定立即归还
  系统内存（进程 RSS 可能不降），但长期不再增长；观察内存应以"翻译后再清理"对比为准。
- **本地规则**：纯本地规则表（如短句/数字/固定短语）先于 API 处理，省钱省时。
- **失败处理**：网络失败直接报错并停止；非网络失败二分递归重试（最多 4 层）。
- **并行**：多批次并发（默认 5），有剩余时间估算。

### 5.1 Ren'Py text lint and rejected translations

Every model result must pass `RenpyTextValidator` before it is accepted into the
translation cache. The validator checks the exact count, indexes, and order of
`__SLGPH<n>__` sentinels; paired Ren'Py markup such as `{b}`, `{/b}`, `{i}`,
`{/i}`, `{font=...}`, and `{/font}`; `[expression]` interpolation tokens; and
`%(name)s`, `%s`, `%d`, and `%1$s` printf tokens. It reports the stable codes
`empty_translation`, `sentinel_missing`, `sentinel_extra`, `sentinel_reordered`,
`tag_unbalanced`, `tag_misnested`, `interpolation_changed`, `printf_changed`,
and `unrestored_sentinel`.

The model acceptance path validates once, and the RPYC artifact and merge paths
validate again before writing. A rejected result must not enter the cache or an
RPYC artifact; it retains `old`, `new`, `codes`, and `source` for UI review.

## 6. 已知差距与后续方向

1. **角色级声音档案**：需要游戏角色定义（Ren'Py `define x = Character(...)`）
   或说话人数据才能做"每个角色独有的说话习惯"。当前纯文本行数据不可行。
2. **翻译记忆（语义级）**：缓存只按精确匹配。语义相近句子无法复用，
   大规模文本中同义表达仍可能译法不一。
3. **双遍润色**：当前单遍翻译。可做 flash 初翻 + pro 精修（风格统一/错漏检查）。
4. **质量评测闭环**：无量化指标（人工抽查为主）。可引入 LLM 打分或 BLEU/chrF。
5. **UI 长度约束**：对话框宽度未约束，超长译句可能溢出/截断。

## 7. 代码索引

| 资产 | 位置 |
|------|------|
| system prompt（含习惯档案） | `apk-work/ui-redesign/patch_workshop_ui.py` → `QUALITY_PROMPT_EN_ZH` |
| 批次上下文注入（文件名/连续行/说话人） | 同文件 → `patch_translation_quality` → `new_vo` |
| 说话人提取（.rpy 源格式） | 同文件 → `new_le` |
| 质量补丁测试 | `apk-work/ui-redesign/test_translation_quality.py` |
| 桌面版 Prompt 工程（历史参考） | `slg-translator/core/translator.ts` → `buildSystemPrompt` |
