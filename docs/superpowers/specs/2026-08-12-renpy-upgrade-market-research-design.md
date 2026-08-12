# Ren'Py 翻译兼容性升级设计 —— 基于市场与中文社区调研

> 状态：Draft，待书面审阅
> 日期：2026-08-12
> 适用项目：SLG Translator Android 版
> 定位：对 `2026-08-10-android-translation-engine-expansion-design.md` 的补充 spec。只覆盖调研新增的 5 个缺口与修订后的阶段顺序，不重述扩展设计已有的能力后端，不改写扩展设计本身。

## 1. 文档目的

现有扩展设计按"能力后端"展开（Ren'Py 现代、Ren'Py 老版本、Android 资源、结构化文本、WebView、Unity），并把阶段优先级建立在"实现成本与端到端成功率"上，但当时缺少**真实市场分布证据**来定先后。

本文档用两轮调研（英文/市场 + 中文社区）得到的数据与工作流证据，回答三个问题：

1. 市面上哪些 Ren'Py 版本占比最高、最需要 writer？
2. 中文汉化社区的标准流程里，哪些环节是我们工具目前做不到的？
3. 据此，下一阶段的实施优先级应该如何修订？

本文档是架构与产品行为设计，不是文件级实施计划；不承诺任何缺口本期实现。每个缺口是否进入实施，由后续独立的实施计划决定，并沿用扩展设计的"封闭技术验证 → 样本矩阵 → 真机验收"门禁。

## 2. 调研证据库

### 2.1 VNDB 市场分布

数据来源：VNDB dump（2026-08-11 拉取），28,879 款记录到 Ren'Py 引擎的游戏。获取渠道为 agent-reach 的 Exa 语义搜索（国内网络下 r.jina.ai 不可达，故用 Exa 索引摘要而非直接页面抓取）。

| 段 | 占比 | 量级 | 当前工具状态 |
|---|---|---|---:|
| Python 2 整体 | 38.1% | ~10,993 | 部分 `LEGACY_PROTOCOL2_SUPPORTED`，部分 `LEGACY_EXTRACT_ONLY` |
| 6.x 时代（Py2 子集） | 16.5% | ~4,754 | 同上 |
| 7.x 时代（Py2 子集） | ~22% | ~6,300 | 同上 |
| 8.4 / 8.5（2025 年中后） | ~27% | ~7,900 | **`UNKNOWN_EXTRACT_ONLY` —— 最大可写缺口** |

说明：

- 6.x（16.5%）与 7.x（~22%）同为 Python 2 时代，加总约等于 Py2 整体（38.1%），二者是子集关系，不重复计数。
- 8.x 为 Python 3；其中 8.4/8.5 占比最大，且为**当前增量市场**（新游戏持续发布在 8.4/8.5 上）。
- 8.4 起 AST 只序列化非默认值；8.5 起 Cython 化 `renpy/astsupport.pyx` 全局变量。8.5.3 为 2026-05-15 最新稳定版。
- **承重结论**：8.4/8.5 是最大单桶且是增长型缺口；Py2 是存量、逐代衰减。这构成"8.4/8.5 优先于 py2"的第一依据。

### 2.2 中文生态标准汉化流程

```
解包 rpa → 反编译 rpyc→rpy → 生成 tl/ → 翻译 → 校验 → 注入语言入口 + 字体 → 可选打包
```

- **关键机制**：Ren'Py 引擎对 `.rpa` 内只读 `.rpyc` **不读 `.rpy`** —— 内嵌汉化必须重建编译产物；companion 翻译 + 语言切换是主流分发形态。
- **安卓侧现状**：中文圈做安卓汉化主流是"100MB 壳子 APK + 塞 `archive.rpa`"，由 PC 端手工整合，**没有自动打补丁的产品**。这与本工具的"APK 内自动"定位形成差异；rpa 重建（缺口 2）正是把这条 PC 手工路径自动化的一环。

### 2.3 中文生态工具对照

| 工具 | 关键能力 | 对本设计的启示 |
|---|---|---|
| rpycdec | rpyc = AST 的 pickle 序列化；用 fake renpy 包反序列化；"AST 还原最难，不同版本结构不同" | 独立印证方言分层方向，且提示"按版本重建 AST"是 writer 的核心难点（缺口 1 直接相关） |
| LinguaGacha | 本地 LLM、上下文窗口分块、命名一致性 | 直接支撑缺口 3（术语表）与缺口 4（上下文分块） |
| RenpyThief | 闭源、40×4090、GPT-5、40+ 引擎 | 商业化模式；"告别机翻"= 翻译质量是卖点 |
| renpy-translator / RenpyBox | PC 全流程汉化 | 桌面参照系 |
| TrRenpy | 安卓套壳 | 安卓无自动补丁佐证 |
| unrpa / unren / unrpyc | 解包三件套 | rpa 读取是必经步骤 |

### 2.4 社区补丁机制与失效案例

- **f95zone**（"Don't use if `renpy.loadable('patch.rpy')`"讨论）：label/identifier 引用变化会让已编译翻译字符串匹配失效 → 支撑缺口 5（运行时验证）的正当性。
- **zorleone rpa 逆向**：RPA-3.0 头 + XOR `offset^key` / `size^key` + zlib pickle 索引 → rpa 结构已被第三方独立验证；重打包关键在索引 pickle 方言（缺口 2 直接相关）。
- **renpy.cn（RenPy 中文空间）**：字体方块字（tofu）＋"rpyc 反编译再编译回 rpyc"教程 → 字体与产物重建是社区刚需。
- **贴吧 translator++ 指南（2026-02）**、**NGA RenpyThief 安利帖**、**Lemmasoft 2010 中文翻译话题**、**doc.renpy.cn（Ren'Py 官方中文文档）** → 生态成熟度与需求侧佐证。

## 3. 现状边界

### 3.1 已有能力（代码核实，非缺口）

| 能力 | 状态 | 位置 |
|---|---|---|
| rpa 读取（RPA-1/.rpi/2/3） | ✅ | `apk-work/native-fast-scan/.../RpaArchive.java` |
| rpyc 提取（6 类记录：对话/选项/源码调用/标记文本/不确定/角色名） | ✅ | `RpycTextExtractor.java` |
| rpyc 对话写回（RPC2 pickle 重建） | ✅ | `RpycDialoguePatcher.java` |
| 语言入口注入（RPC2 菜单重写） | ✅ | `LanguageMenuSupport.java` |
| 字体检查 + 注入（CJK 覆盖度 + 字体分配） | ✅ | `RenpyFontSupport.java` + `TranslationCompiler.java` |
| always-on 兜底 | ✅ | `TranslationCompiler.java` |
| 占位符/标签校验 | ✅ | `RenpyTextValidator.java` |
| 能力分层 + 可翻译可导出（Phase 0） | ✅（已有计划） | `2026-08-10-android-translation-engine-capability-layer.md` |

### 3.2 已有计划（视为已覆盖，仅引用）

| 计划 | 覆盖 |
|---|---|
| `2026-08-10-android-translation-engine-capability-layer.md` | Phase 0：能力分层、EXTRACT_ONLY → 可翻译可导出 |
| `2026-08-10-renpy-legacy-writer-expansion.md` | Py2 / protocol-2 legacy writer（阶段 1b） |
| `2026-08-10-android-resource-backend.md` | resources.arsc / AAPT2 重建 |
| `2026-08-10-structured-text-backend.md` | JSON / CSV / properties / 静态 HTML |
| `2026-08-10-unity-static-localization-backend.md` | Unity 静态本地化资源 |
| `2026-08-10-webview-static-resource-backend.md` | WebView 静态资源 |
| `2026-08-10-android-translation-memory-optimization.md` | 翻译缓存 / 内存 |

### 3.3 本档新增 5 缺口概览

| # | 缺口 | 类型 | 阶段 |
|---|---|---|---:|
| 1 | Ren'Py 8.4/8.5 AST writer | 写回 | 1a |
| 2 | rpa 重建/打包 | 写回 / 交付 | 2 |
| 3 | 术语表（glossary） | 翻译质量 | 3 |
| 4 | 上下文分块翻译 | 翻译质量 | 3 |
| 5 | 运行时验证恢复（canValidateRuntime） | 验证 | 4 |

## 4. 缺口定义（证据 → 现状 → 方案 → 验收）

### 缺口 1 · Ren'Py 8.4/8.5 AST writer

- **证据**：VNDB ~27%（~7,900 款）为最大单桶；新游戏持续发布在 8.4/8.5 上（增长型）；8.4 起 AST 只序列化非默认值，8.5 起 Cython 化 astsupport。
- **现状**：这些游戏落入 `UNKNOWN_EXTRACT_ONLY` —— 能提取、能翻译、能导出，但**不能写回 APK**。
- **方案**：
  1. 建立 8.4/8.5 真实样本矩阵（优先 8.5.3 最新稳定版），记录 container / slot / pickle protocol / 对象图 / version-key / 启动结果。
  2. **先封闭技术验证**：能否用 fake renpy 包重建 8.4/8.5 的 AST pickle。8.4 的"只序列化非默认值"是最大变数——需确认默认值还原规则是否可在不依赖原版源码的情况下复现。
  3. 扩展 `RpycCompatibility` 方言识别，使 8.4/8.5 从 `UNKNOWN_EXTRACT_ONLY` 进入可生成候选，再由 writer 承载。
  4. 产物重读 → 安装 → 启动 → 中文生效，逐级升级为 `VERIFIED`。
- **验收**：≥2 个真实 8.4/8.5 样本端到端通过；未覆盖方言保持 `TRANSLATABLE_NO_PATCH`，不扩大通配判断。

### 缺口 2 · rpa 重建/打包

- **证据**：中文生态每篇教程都从"解包 rpa"开始、以"打包 rpa / 整合 APK"结束；zorleone 独立验证 RPA-3.0 头 + XOR key + zlib pickle 索引；companion 汉化以 rpa mod 分发。
- **现状**：`RpaArchive` 只读（RPA-1/.rpi/2/3 的读取已实现），**无写回**。
- **方案**：
  1. 新增 rpa writer：写头 + 重建索引（索引 pickle 方言按目标游戏 Python 版本选择 protocol）+ XOR key + zlib 条目。
  2. 支持 RPA-3.0（现代）、RPA-2.0（旧）、v1 + `.rpi`。
  3. 作为独立交付形态（rpa mod），可覆盖非 APK 安装的原版游戏目录；后续 APK 内嵌流程复用同一 writer。
  4. 写后由独立 parser 重读，逐条对比索引与条目，验证通过才可交付。
- **验收**：≥1 个真实游戏 rpa 重建后，原版引擎可加载并显示中文；写后重读索引与条目一致；源 rpa 不被修改。

### 缺口 3 · 术语表（glossary）

- **证据**：LinguaGacha 主打命名一致性；RenpyThief "告别机翻"；中文圈工具普遍有术语维护能力。
- **现状**：已有翻译缓存与占位符校验，但**没有术语表概念** —— 人名/地名/专名无法跨记录强制一致。
- **方案**：
  1. 术语表为可导入导出的 JSON，字段与项目导出 schema（schemaVersion 1）兼容。
  2. 命中规则（整词匹配 / 上下文限定）→ 翻译 prompt 注入 + 校验阶段复核。
  3. 角色名、地名、专名优先受术语表约束；冲突进待确认集合，不静默覆盖。
- **验收**：同一专名跨记录翻译一致；术语冲突进入待确认而非静默覆盖；术语表可关闭。

### 缺口 4 · 上下文分块翻译

- **证据**：LinguaGacha 以"上下文窗口分块"为卖点；按条独立翻译在人称指代、长对话上质量明显下降。
- **现状**：按条翻译，无场景上下文。
- **方案**：
  1. 按 `sourcePath` + occurrence 分场景/章节，分批送入模型，块内共享上下文。
  2. 与缓存 recordId 设计兼容，块间不破坏缓存复用。
  3. 用户可切回按条模式，保持现有行为兼容。
- **验收**：上下文块内人称/指代一致；缓存复用不退化；按条模式行为不变。

### 缺口 5 · 运行时验证恢复（canValidateRuntime）

- **证据**：f95zone 讨论表明 label/identifier 引用变化会让已编译翻译字符串失效，补丁"装了没生效/崩溃"时无诊断手段。
- **现状**：capability-layer 计划显式移除了 `canValidateRuntime` 能力位（当时无消费方）。
- **方案**：
  1. 恢复能力位，先做**轻量版**：安装后启动 + 断言语言入口存在 + 目标语言文本实际出现。
  2. 扩展为运行时映射验证，与扩展设计 §7.2 的"运行时字符串映射后端（实验）"衔接。
  3. 明确"安装成功"≠"汉化生效"，两者分开记录。
- **验收**：正常 / label 失效 / 未生效三类 fixture 可被区分；诊断文案只说明"已保留什么结果、下一步能做什么"。

## 5. 修订后的阶段顺序

| 阶段 | 内容 | 依据 | 状态 |
|---|---|---|---:|
| **1a** | 8.4/8.5 AST writer | VNDB ~27%，增长型缺口 | 本档新增 |
| **1b** | Py2 legacy writer | 存量 38% | 已有计划维持 |
| **2** | rpa 重建/打包 | 中文流程必经 | 本档新增 |
| **3** | 术语表 + 上下文分块 | 翻译质量杠杆 | 本档新增 |
| **4** | 运行时验证恢复 | 补丁失效根因 | 本档新增 |

修订说明：

- 原扩展设计 Phase 1 = "Ren'Py 老版本 writer"，只指 Python 2。本文档拆为 **1a（8.4/8.5，新增优先）+ 1b（py2，维持）**。
- 扩展设计原有的资源 / 结构化文本 / WebView / Unity 阶段（原 Phase 2-4）不受影响，可穿插或并行推进。
- 阶段顺序的裁决依据是市场分布证据，不是"支持的扩展名数量"。

## 6. 风险与控制

| 风险 | 影响 | 控制措施 |
|---|---|---|
| 8.4/8.5 AST 重建不可行 | 1a 无法实施 | 先封闭技术验证；失败则保持 `TRANSLATABLE_NO_PATCH`，不做通配放行 |
| rpa 索引 pickle 方言错配 | 原版引擎无法加载 rpa | 按目标游戏 Python 版本选 protocol；写后独立 parser 重读 |
| 术语表过度约束 | 译稿生硬 | 可关闭；冲突进待确认 |
| 上下文分块消耗模型费用 | 成本上升 | 复用现有缓存；用户可切回按条 |
| 运行时验证误报/漏报 | 诊断误导 | 三类 fixture 分离；分开记录"安装成功"与"汉化生效" |

## 7. 明确不采用的方案

1. 对 8.4/8.5 或 py2 未知方言做通配放行，以提高表面可写率。
2. rpa 重建不做独立重读验证就标记成功。
3. 术语表冲突静默覆盖（最后一条赢）。
4. 把上下文分块设为唯一翻译模式，取消按条兼容。
5. 在无运行时验证的情况下仍对补丁显示"汉化完成"。
6. 为了新增 writer 而关闭占位符、字体、覆盖率或产物 validator。

## 8. 完成定义

本设计完成的标准：

- 证据可追溯（来源、渠道、日期、量级）；
- 五个缺口逐项有"证据 → 现状 → 方案 → 验收"；
- 阶段顺序有市场分布依据，且与扩展设计衔接明确；
- 已有能力与已有计划被正确引用，不重复设计；
- 未验证能力没有被写成已实现或通用支持。

后续实施阶段的总完成标准（沿用扩展设计）：

- 每个新 writer 通过契约、产物重读和真机验收；
- 不存在通过取消门禁获得的兼容率提升；
- 应用能准确说明每个 APK 当前可以做到哪一步。

## 9. 现有资料关联

- `docs/superpowers/specs/2026-08-10-android-translation-engine-expansion-design.md`：总架构 spec，本文档的上级文档。
- `docs/superpowers/plans/2026-08-10-android-translation-engine-capability-layer.md`：Phase 0 实施计划（已完成）。
- `docs/superpowers/plans/2026-08-10-renpy-legacy-writer-expansion.md`：阶段 1b（py2）实施计划。
- `docs/superpowers/plans/2026-08-10-android-resource-backend.md`、`2026-08-10-structured-text-backend.md`、`2026-08-10-unity-static-localization-backend.md`、`2026-08-10-webview-static-resource-backend.md`：其余能力后端计划。
- `docs/superpowers/plans/2026-08-10-android-translation-memory-optimization.md`：缓存/内存计划。
- `apk-work/native-fast-scan/src/com/slgtranslator/app/`：能力现状代码位置。
