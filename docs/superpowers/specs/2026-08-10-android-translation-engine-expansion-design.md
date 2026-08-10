# Android 翻译引擎扩展设计

> 状态：Draft，待书面审阅
> 日期：2026-08-10
> 适用项目：SLG Translator Android 版
> 目标：在保留现有安全门禁的前提下，把“只能提取文本”的 APK 转化为可继续翻译、可导出，并逐步扩展为可安全回写的多引擎处理体系。

## 1. 文档目的

当前 Android 端的文本发现能力已经宽于补丁生成能力：扫描器可以识别 Ren'Py RPYC/RPA、Split APK 和多种文本扩展名，但完整回写链路主要围绕经过验证的 Ren'Py RPYC writer 建立。当脚本属于老 Python 版本、未知 pickle 方言、未知 RPYC 代际或非 Ren'Py 引擎时，应用可能成功提取文本，却无法生成经过验证的可运行补丁。

本文档定义后续翻译引擎修改的统一方向：

1. 把检测、提取、翻译、回写、激活和验证拆成独立能力；
2. 允许可结构化提取但暂时不可回写的 APK 继续翻译和导出；
3. 保留不安全格式的 APK 构建阻断，不通过取消门禁制造伪成功；
4. 以独立后端逐步增加 Ren'Py 老版本、Android 原生资源、结构化文本、WebView 和 Unity 支持；
5. 为每个后端建立真实 APK、产物重读、安装、启动和中文生效验收。

本文档是架构与产品行为设计，不是能力已经实现的声明，也不是文件级实施计划。

## 2. 已确认事实、推断与未知项

### 2.1 已确认事实

- `FastApkScanner` 已识别 Ren'Py 脚本扩展名、RPA 虚拟条目、常见文本扩展名和完整 APK 集合。
- `RenpyPreflight` 会把无效 RPYC 标记为 `UNSUPPORTED`，把未验证的老版本或未知代际标记为 `EXTRACT_ONLY`。
- `RpycCompatibility.Report.canGenerate()` 只放行现代 writer 和经过结构验证的 protocol 2 writer。
- `TranslationCompiler` 在 writer 不可用时不生成 RPYC 补丁。
- 当前 UI 会在 `EXTRACT_ONLY` 或 `UNSUPPORTED` 状态下阻断模型调用和补丁流程。
- 当前项目已有一个真实 Ren'Py 单 APK 的完整翻译、构建、安装和中文菜单/对白证据，但该证据不能代表所有 Ren'Py 代际、Split APK 或其他游戏引擎。

### 2.2 合理推断

- 大量“只能提取文本”并不是模型无法翻译，而是缺少与目标格式匹配的 writer、激活策略或产物验证器。
- 当前把 `EXTRACT_ONLY` 在模型调用前直接视为失败，会丢失“可以翻译并导出”的有效用户价值。
- 单一的通用字符串替换器无法同时安全覆盖 RPYC、`resources.arsc`、二进制 XML、DEX、Unity AssetBundle 和远程 WebView 内容。
- 继续把所有逻辑堆入 `FastApkScanner` 与 `TranslationCompiler` 会提高回归风险，应通过适配器和后端接口隔离扩展。

### 2.3 当前未知项

- 真实用户 APK 中，各引擎、Ren'Py 代际和失败原因的占比。
- Ren'Py 6/7 真实 Python 2 游戏中，可由当前受限 protocol 2 writer 覆盖的比例。
- 在目标 Android 设备上嵌入完整资源编译器、Unity 资源库或匹配版本 Ren'Py 运行时的体积、内存和许可证成本。
- 非 Ren'Py APK 中，文本位于结构化资源、DEX、native library、图片还是联网内容的实际分布。

这些未知项必须通过脱敏兼容性报告和合法真实样本补齐，不能用猜测替代实现优先级。

## 3. 核心设计原则

### 3.1 翻译能力不等于写回能力

结构化文本可以安全提取时，应用可以执行翻译、质量校验、缓存和导出；只有存在经过验证的 writer、激活策略和产物验证器时，才允许生成最终 APK。

### 3.2 在写回边界失败关闭

未知格式、未知对象图、无法确认资源所有者或无法验证产物时，writer 必须停止。不得通过原位二进制字符串替换、忽略 validator 或扩大兼容标志继续生成补丁。

### 3.3 每个引擎使用独立适配器

引擎检测、文本语义、占位符规则、资源所有权、回写方式和激活方式必须由对应适配器负责。公共翻译服务只处理统一语料，不理解 APK 内部格式。

### 3.4 保留现有安全语义

现有 `SAFE`、`WARNING`、`EXTRACT_ONLY`、`UNSUPPORTED` 继续表示总体兼容性结论。新能力字段只增加阶段信息，不重新解释旧值，也不破坏已有 UI、缓存和桥接字段。

### 3.5 真实运行是最终证据

“提取成功”“翻译成功”“写入成功”“APK 签名成功”“安装成功”和“游戏中中文生效”必须分别记录。任一早期状态都不能自动提升为最终成功。

### 3.6 本地优先与最小数据

默认在设备本地处理 APK、原文和译文。需要桌面辅助或服务端后端时，必须作为显式选择，并单独定义隐私、传输、删除和失败回退边界。

## 4. 能力模型

### 4.1 保留总体支持等级

| `supportLevel` | 含义 | 是否允许翻译 | 是否允许构建 APK |
|---|---|---:|---:|
| `SAFE` | writer、激活和基础验证路径已验证 | 是 | 是 |
| `WARNING` | 可构建，但需要明确回退策略或用户确认 | 是 | 条件允许 |
| `EXTRACT_ONLY` | 可结构化提取，当前没有安全 writer | 是 | 否 |
| `UNSUPPORTED` | 无法可靠识别或结构化提取 | 否 | 否 |

变更后的关键语义是：`EXTRACT_ONLY` 不再等同于“翻译失败”，而是进入 `TRANSLATABLE_NO_PATCH` 工作流。

### 4.2 新增阶段能力

兼容性报告增加可选 `capabilities` 对象：

```json
{
  "detect": "VERIFIED",
  "extract": "STRUCTURED",
  "translate": "ALLOWED",
  "write": "NONE",
  "activate": "NONE",
  "validate": "EXTRACT_ONLY",
  "workflow": "TRANSLATABLE_NO_PATCH",
  "adapterId": "renpy",
  "writerId": ""
}
```

字段允许值固定如下：

| 字段 | 允许值 |
|---|---|
| `detect` | `NONE` / `HEURISTIC` / `VERIFIED` |
| `extract` | `NONE` / `HEURISTIC` / `STRUCTURED` |
| `translate` | `BLOCKED` / `EXPORT_ONLY` / `ALLOWED` |
| `write` | `NONE` / `EXPERIMENTAL` / `VERIFIED` |
| `activate` | `NONE` / `ALWAYS_ON` / `SELECTABLE` / `ENGINE_NATIVE` |
| `validate` | `NONE` / `EXTRACT_ONLY` / `STRUCTURAL` / `DEVICE_REQUIRED` |
| `workflow` | `UNSUPPORTED` / `EXTRACTABLE_ONLY` / `TRANSLATABLE_NO_PATCH` / `PATCHABLE_EXPERIMENTAL` / `PATCHABLE_VERIFIED` |

### 4.3 工作流推导规则

1. `extract=NONE` 时，`workflow=UNSUPPORTED`。
2. `extract=HEURISTIC` 时，只允许导出原始发现结果，不调用批量模型，不声称完整覆盖。
3. `extract=STRUCTURED` 且 `write=NONE` 时，`workflow=TRANSLATABLE_NO_PATCH`。
4. `write=EXPERIMENTAL` 时，只允许生成明确标记的测试补丁，默认不进入普通用户完成流程。
5. `write=VERIFIED` 且存在激活和 validator 时，才能进入 `PATCHABLE_VERIFIED`。
6. `UNSUPPORTED` 永远不能通过用户开关强制提升为可写。

## 5. 目标架构

```text
APK 来源 / 已安装应用
  ↓
ApkSourceSetResolver
  ├─ base APK
  ├─ split APKs
  └─ 来源、包名、版本、签名与持久化副本
  ↓
EngineDetector
  ↓
EngineAdapter
  ├─ detect
  ├─ preflight
  ├─ extract
  ├─ classify
  └─ listWriters
  ↓
TranslationCorpus
  ↓
公共翻译、缓存、占位符保护、质量校验
  ↓
WriterBackend
  ├─ writer preflight
  ├─ build patch entries
  ├─ activation
  └─ backend validator
  ↓
ApkBuildOrchestrator
  ↓
APK 集合验证、签名、安装和启动验收
```

### 5.1 `EngineDetector`

职责：根据 manifest、Activity、native library、assets、脚本魔数和资源布局识别引擎候选。

输出必须包含：

- `adapterId`；
- 检测置信度；
- 直接证据列表；
- 冲突候选；
- 是否需要进一步读取；
- 稳定失败码。

检测器不能仅依赖扩展名。例如 APK 中存在 JSON 不代表游戏是结构化文本引擎，存在 `libunity.so` 也不代表所有可见文本都位于 Unity 资源中。

### 5.2 `EngineAdapter`

首版接口保持在现有 `com.slgtranslator.app` 包中，避免改变当前 Java/D8 构建边界：

```java
interface EngineAdapter {
    String id();
    DetectionResult detect(ApkSourceSet source);
    EnginePreflightReport preflight(ApkSourceSet source, DetectionResult detection);
    ExtractionResult extract(ApkSourceSet source, ExtractionRequest request);
    List<WriterDescriptor> listWriters(EnginePreflightReport report);
}
```

接口只传递结构化对象，不传递 UI 文案。引擎适配器不能直接调用模型、操作用户界面或签名 APK。

### 5.3 `TranslationCorpus`

公共语料模型以现有 `RenpyTextRecord` 的经验为基础，但扩展为引擎无关记录：

```text
recordId
adapterId
sourceOwner
sourcePath
resourceType
sourceKey
sourceText
speaker
context
occurrenceId
placeholders
translatability
classificationReason
metadata
```

要求：

- `recordId` 在同一 APK 版本内稳定；
- `sourceOwner` 明确属于 base 或具体 split；
- `sourceKey` 保留引擎原始定位语义；
- `sourceText` 不作为唯一定位依据；
- `metadata` 只能保存经过白名单允许的结构化字段；
- 不同语境下相同原文不得在适配器未确认前强制合并。

### 5.4 `WriterBackend`

```java
interface WriterBackend {
    String id();
    WriterPreflightReport preflight(ApkSourceSet source, TranslationCorpus corpus);
    PatchArtifact build(ApkSourceSet source, TranslationCorpus corpus,
                        Map<String, String> approvedTranslations);
    PatchValidationReport validate(ApkSourceSet source, PatchArtifact artifact);
}
```

每个 writer 必须声明：

- 支持的 adapter 和格式版本；
- 资源所有权规则；
- 是否修改 base、split 或新增 loose entry；
- 激活策略；
- 可重读验证方式；
- 运行时仍需验证的项目；
- 资源、内存和耗时预算。

## 6. 数据流与状态机

### 6.1 标准路径

```text
选择 APK
  → 解析完整 APK 集合
  → 检测引擎
  → 兼容性预检
  → 结构化提取
  → 翻译与校验
  → writer 预检
  → 构建翻译产物
  → 产物重读验证
  → APK 合并、对齐和签名
  → 安装
  → 启动与中文生效验收
```

### 6.2 `TRANSLATABLE_NO_PATCH` 路径

```text
选择 APK
  → 检测与结构化提取
  → 显示“可翻译，暂不可生成 APK”
  → 用户开始翻译
  → 缓存和质量校验
  → 导出通用 JSON
  → 可选导出引擎专用中间格式
  → 任务状态为“译文已导出”，不是“汉化完成”
```

此路径必须保留翻译结果，后续新增 writer 后可直接复用，不要求用户重新消耗模型费用。

### 6.3 实验 writer 路径

实验 writer 默认隐藏在普通流程之外，只在开发者/测试构建和已登记样本中启用。生成物必须带独立文件名和诊断标记，不能覆盖最后一个已验证补丁。

## 7. 后端设计

### 7.1 Ren'Py 现代 RPYC 后端

保留现有路径：

- RPA-1/2/3 只读扫描；
- loose translation RPYC 注入；
- `selectable` 与 `always_on` 分离；
- version/key/template 选择；
- protocol、槽位、对象图和翻译数量验证；
- 字体、覆盖率、签名和运行门禁。

该后端迁移到 `RenpyEngineAdapter` 与 `RenpyRpycWriter` 时，现有行为和桥接字段必须保持兼容。

### 7.2 Ren'Py 老版本扩展

按以下顺序扩展：

1. 建立真实 Ren'Py 6、Ren'Py 7 Python 2 和 protocol 2 样本矩阵；
2. 记录 container、slot、pickle protocol、GLOBAL、对象图、version/key 和实际启动结果；
3. 只对结构完全匹配且产物可由目标游戏加载的方言增加 writer；
4. 未覆盖方言继续保持 `TRANSLATABLE_NO_PATCH`；
5. 评估匹配版本编译器辅助后端；
6. 评估运行时字符串映射后端，但不得把它描述为完整 dialogue-ID 翻译。

匹配版本编译器后端必须满足以下条件才能进入实施：

- 能在合法真实样本上由结构化语料生成目标版本可加载产物；
- 不依赖原始游戏源码才能完成已声明的字符串翻译范围；
- 依赖、许可证、体积、启动耗时和内存预算可接受；
- 生成产物可被独立 parser 重读；
- 失败时不会修改源 APK 或现有有效补丁。

运行时映射后端固定为实验能力，至少验证菜单、普通字符串、角色名、插值、存档加载和回滚。任何类别未验证时，报告中必须列出覆盖限制。

### 7.3 Android 原生资源后端

`AndroidResourceAdapter` 负责识别和提取：

- `resources.arsc` 字符串资源；
- 二进制 XML 中的资源引用；
- `string`、`plurals`、`string-array`；
- locale qualifier 和默认资源回退；
- `%s`、`%d`、位置参数、转义、HTML span 和不可翻译标记。

`AndroidResourceWriter` 不允许原始字节长度替换。它必须通过结构化资源库或 AAPT2 支持的确定性重建路径更新资源表和二进制 XML。

依赖选择先执行一个封闭技术验证：候选实现必须在目标 Android 设备上完成读取、修改、重建、重读、签名和安装；同时通过许可证、APK 增量体积、峰值内存和处理时间门禁。没有候选通过时，该后端保持 `TRANSLATABLE_NO_PATCH`，不能退回二进制字符串替换。

DEX、native library 和动态生成文本不属于此后端的首版范围。

### 7.4 结构化文本后端

首版 `StructuredTextAdapter` 支持：

- JSON；
- CSV/TSV；
- Java properties；
- APK assets 中可确认编码的纯文本；
- 包内静态 HTML 的文本节点和明确属性。

要求：

- 使用对应 parser，不使用跨格式正则替换；
- 保留键、数组顺序、数字、布尔值、空值和非翻译字段；
- CSV 保留 delimiter、quote 和换行语义；
- properties 保留转义和重复键诊断；
- HTML 不翻译脚本、样式、URL、ID 和数据协议；
- 编码不明确时停止写入；
- 写回后重新解析并逐条核对 key 与译文。

YAML、Lua、JavaScript 源码和任意 XML 不进入首版通用 writer，避免用错误 parser 扩大支持面。

### 7.5 WebView 后端

`WebViewAssetAdapter` 只处理 APK 内静态资源：

- 本地 HTML；
- 本地 JSON/locale 包；
- 可确认语义的静态文本清单。

远程接口返回的剧情、加密资源、登录后内容和服务端模板标记为 `remote_content_not_patchable`。首版不注入网络代理、不绕过证书校验，也不把 DOM 运行时机器翻译当作 APK 汉化完成。

### 7.6 Unity 后端

Unity 分三层推进：

1. APK assets 中独立 JSON、CSV、XML 或 Localization 表；
2. `TextAsset`、`resources.assets` 和 AssetBundle 中的结构化本地化资源；
3. IL2CPP、native hardcoded string 和运行时解密内容。

第一层复用结构化文本后端。第二层必须使用经过验证的 Unity 资源 parser/writer，并按 Unity 版本、序列化类型和 bundle 压缩方式建立矩阵。第三层不进入首轮 writer，默认只提供诊断或导出能力。

任何 Unity writer 都必须证明修改后 bundle 可重读、资源引用未变化、游戏可启动且目标文本生效。

### 7.7 Flutter、DEX 和 native 文本

以下类型首期保持诊断或导出状态：

- Flutter AOT `libapp.so` 中的文本；
- 混淆 DEX 中的硬编码、拼接或加密字符串；
- native library 中的字符串；
- 运行时下载或解密资源。

后续若增加 smali/DEX writer 或运行时 hook，必须作为独立后端设计，不得并入 Android 资源 writer。

### 7.8 图片文本

OCR、图像修复、重新排版和纹理写回属于单独项目。扫描器可以统计疑似含文本图片，但不能把 OCR 结果计入当前结构化文本覆盖率。

## 8. Split APK 与资源所有权

所有记录和补丁条目必须保留 `sourceOwner`：

```text
base
split:<splitName>
archive:<apkName>!/<entry>
```

规则：

1. 提取记录不得丢失原资源所属 APK；
2. writer 只能修改声明允许的 owner；
3. 资源 ID 依赖 base 与 split 时必须按完整集合重建；
4. 安装使用单一 PackageInstaller session 提交完整集合；
5. 集合内包名、versionCode、splitName 和签名必须一致；
6. 无法获得完整集合时，不能把 base-only 结果标为可安装补丁；
7. 重新签名后必须验证所有 APK 的签名一致性。

## 9. 翻译导出格式

所有 `TRANSLATABLE_NO_PATCH` 后端至少支持通用 JSON：

```json
{
  "schemaVersion": 1,
  "projectFingerprint": "...",
  "adapterId": "renpy",
  "sourceVersion": "...",
  "records": [
    {
      "recordId": "...",
      "sourceOwner": "base",
      "sourcePath": "assets/...",
      "resourceType": "dialogue",
      "sourceKey": "...",
      "sourceText": "Hello",
      "translation": "你好",
      "validation": "APPROVED"
    }
  ]
}
```

导入时必须验证：

- `schemaVersion`；
- 项目指纹和源版本；
- `recordId` 是否仍存在；
- 原文是否发生变化；
- 占位符与标签；
- 重复、冲突和失效记录。

不匹配记录进入待确认列表，不自动写入新版本 APK。

## 10. UI 状态与错误码

### 10.1 用户状态

| 工作流 | 用户可见说明 | 主操作 |
|---|---|---|
| `PATCHABLE_VERIFIED` | 可翻译并生成汉化 APK | 开始翻译 |
| `PATCHABLE_EXPERIMENTAL` | 可生成测试补丁，但尚未完成该格式的运行验证 | 生成测试补丁 |
| `TRANSLATABLE_NO_PATCH` | 可以翻译和保存译文，当前不能生成可运行 APK | 翻译并导出 |
| `EXTRACTABLE_ONLY` | 发现了可能的文本，但无法确认完整性 | 导出扫描报告 |
| `UNSUPPORTED` | 无法可靠识别或提取 | 查看诊断 |

不得继续使用“请重新选择兼容 APK”作为 `EXTRACT_ONLY` 的唯一出口。

### 10.2 稳定错误码

新增错误码：

- `engine_not_detected`；
- `engine_detection_conflict`；
- `structured_extraction_unavailable`；
- `engine_detected_no_writer`；
- `writer_preflight_failed`；
- `writer_dependency_unavailable`；
- `writer_output_invalid`；
- `activation_strategy_unavailable`；
- `android_resource_rebuild_unavailable`；
- `renpy_legacy_writer_unverified`；
- `renpy_runtime_mapping_unverified`；
- `unity_bundle_writer_unavailable`；
- `split_set_incomplete`；
- `remote_content_not_patchable`；
- `translation_export_version_mismatch`。

错误日志保留技术详情，用户文案只说明发生了什么、当前保留了什么结果和下一步能做什么。

## 11. 安全与资源限制

所有适配器和 writer 都把 APK 内容视为不可信输入：

- 限制 ZIP 条目数、路径长度、嵌套深度、单文件大小和总解压量；
- 拒绝 Zip Slip、绝对路径、重复冲突条目和异常压缩比；
- parser 必须支持取消和超时；
- 大文件优先流式读取；
- 临时目录按任务隔离，失败后清理未验证产物；
- writer 不直接覆盖用户源 APK；
- 导出诊断不包含 API Key、完整原文、完整译文或可还原内容的 token；
- 运行时 hook、DEX 和 native 修改必须单独执行更高等级安全审查。

## 12. 兼容迁移

### 12.1 桥接兼容

现有扫描响应字段继续保留：

- `supportLevel`；
- `compatibilityReason`；
- `reasonCode`；
- `compatibilityReport`；
- `compatibilityGate`；
- `rpycContainer`；
- `splitCount`。

新字段作为可选字段追加。旧前端忽略新字段时仍保持原有安全行为；新前端在没有 `capabilities` 时按旧 `supportLevel` 推导。

### 12.2 缓存兼容

- 翻译缓存增加 `adapterId`、`recordSchemaVersion` 和项目指纹命名空间；
- 现有 Ren'Py exact-old 缓存继续兼容读取；
- 不同适配器不能仅凭相同原文共享可写定位；
- 模型译文可以复用，但 writer 定位和验证结果不能跨引擎复用；
- schema 升级必须支持旧任务只读恢复和显式迁移。

### 12.3 源码组织

首轮新增类保持在 `com.slgtranslator.app` 包内，减少当前 javac/D8 注入链路变化。职责按类隔离，不在第一轮迁移目录结构。待 adapter 契约和构建链稳定后，再单独评估 Java package 重组。

## 13. 分阶段实施顺序

### 阶段 0：能力分层与可翻译导出

目标：在不增加任何新 writer 的情况下，让 `EXTRACT_ONLY` 产生可保存结果。

范围：

- 新增 `capabilities` 与 `workflow`；
- 增加 `EngineAdapter`、`WriterBackend` 最小接口；
- 用 `RenpyEngineAdapter` 包装现有路径；
- 将 UI 的模型前阻断移动到 writer 边界；
- 实现通用 JSON 导出/导入；
- 保持 `UNSUPPORTED` 阻断；
- 保持现有 Ren'Py 安全构建行为不变。

完成标准：受控 `EXTRACT_ONLY` fixture 能完成翻译、校验和导出，但零 writer、零 APK 构建调用；现有 `SAFE/WARNING` 路线无回归。

### 阶段 1：Ren'Py 老版本 writer 扩展

目标：扩大真实 Ren'Py 6/7 和 protocol 2 的可写覆盖率。

范围：

- 建立合法真实样本矩阵；
- 扩展经过验证的 pickle 方言；
- 增加匹配版本编译器可行性验证；
- 增加运行时映射实验后端；
- 对每种方言独立记录产物重读、安装、启动、文本和存档结果。

完成标准：只有通过真实目标游戏加载和中文生效的方言升级为 `VERIFIED`；其余继续导出，不扩大通配判断。

### 阶段 2：Android 原生资源与结构化文本

目标：覆盖资源表和常见 assets 本地化文件。

范围：

- Android 资源 parser/writer 技术验证；
- `string`、`plurals`、`string-array`；
- JSON、CSV、properties、静态 HTML；
- 格式化占位符和资源引用校验；
- base/split 资源所有权；
- 重建、签名、安装和启动验收。

完成标准：至少两个结构不同的合法 Android 原生样本和两个结构化 assets 样本完成端到端验证。

### 阶段 3：WebView 与 Unity 静态资源

目标：支持包内静态 WebView 内容和 Unity 独立本地化资源。

范围：

- 静态 WebView JSON/HTML；
- Unity 独立 JSON/CSV/Localization 表；
- Unity 资源 parser/writer 技术验证；
- 明确排除远程内容和 IL2CPP hardcoded string。

完成标准：每种 writer 至少一个真实样本完成重读、安装、启动和中文生效。

### 阶段 4：高风险与媒体资源

单独评估：

- AssetBundle 深层写回；
- DEX/smali writer；
- native/IL2CPP；
- 运行时 hook；
- 图片 OCR 与纹理重建；
- 桌面或服务端辅助后端。

这些能力不能作为前述阶段的附带任务实施。

## 14. 测试与验收

### 14.1 适配器契约测试

每个 adapter 必须覆盖：

- 正确识别；
- 相似结构误判；
- 冲突引擎证据；
- 空文件、畸形文件和资源上限；
- 结构化记录稳定性；
- 相同原文不同语境；
- 不可翻译字段过滤；
- 取消和超时。

### 14.2 writer 契约测试

每个 writer 必须覆盖：

- 支持矩阵内样本成功；
- 支持矩阵外样本失败关闭；
- 占位符、标签、格式参数和编码；
- 资源所有者和 split 路由；
- 写后重读；
- 译文数量和定位一致；
- 源 APK 不被修改；
- 中断后无半成品被标为有效；
- 重复运行幂等或产生明确版本化结果。

### 14.3 APK 产物测试

- ZIP 条目和压缩方式符合后端要求；
- `zipalign` 通过；
- v2/v3 签名通过；
- base/split 集合一致；
- 包名、versionCode 和 manifest 未意外变化；
- 修改范围只包含 writer 声明的条目；
- 产物由独立读取路径重新提取时得到预期译文。

### 14.4 真机验收

每个升级为 `VERIFIED` 的后端至少保存：

- 来源指纹和合法性确认；
- 工具 APK 版本和 SHA-256；
- 设备、Android 版本和 ABI；
- 兼容性报告；
- 提取、唯一文本、出现次数、缺失和拒绝统计；
- writer 与 validator 结果；
- 生成 APK/集合的 SHA-256 与签名；
- 安装结果；
- 启动结果；
- 实际中文菜单、UI 或对白证据；
- 崩溃、ANR、存档和回滚结果。

### 14.5 样本矩阵最低要求

| 类别 | 最低样本 |
|---|---:|
| Ren'Py 现代 | 2 个不同版本/结构 |
| Ren'Py Python 2/protocol 2 | 2 个不同方言 |
| Android resources | 2 个资源布局不同的 APK |
| 结构化 assets | 2 个不同格式 |
| Split APK | 1 个完整 base+split 集合 |
| WebView 静态资源 | 1 个 |
| Unity 静态本地化 | 1 个 |
| 每个预期阻断类型 | 至少 1 个对抗 fixture |

单一样本通过不能将整个引擎标记为通用支持。

## 15. 可观测性与兼容性数据

为决定后续 writer 优先级，兼容性报告可以在用户明确同意后记录以下脱敏统计：

- `adapterId` 与检测置信度；
- `supportLevel` 和 `workflow`；
- 容器、协议和资源类型枚举；
- base/split 数量；
- 文本数量区间；
- writer 缺失或失败码；
- 处理阶段与耗时区间；
- 是否完成导出、构建、安装和启动。

不得上传 APK、完整路径、原文、译文、API Key 或可还原内容的资源片段。

优先级以真实失败分布、实现成本、设备资源成本和端到端成功率共同决定，不以“看起来支持的扩展名数量”决定。

## 16. 明确不采用的方案

1. 直接删除 `EXTRACT_ONLY` 或 `UNSUPPORTED` 门禁。
2. 对 RPYC、`resources.arsc`、DEX、AssetBundle 做不验证的等长字符串替换。
3. 用一个正则提取器处理 JSON、XML、HTML、Lua、YAML 和 JavaScript。
4. 只要 APK 能重新签名就显示“汉化成功”。
5. 把安装成功视为游戏启动或中文生效证据。
6. 在没有真实样本的情况下按文件名或单个魔数放行 writer。
7. 第一轮同时嵌入 Ren'Py、AAPT2、Unity、DEX 和 OCR 全套运行时。
8. 在用户不知情的情况下上传 APK 或剧情文本到服务端处理。
9. 为提高表面兼容率而关闭占位符、字体、覆盖率或产物 validator。

## 17. 风险与控制

| 风险 | 影响 | 控制措施 |
|---|---|---|
| 适配器误判 | 使用错误 writer 损坏 APK | 多证据检测、冲突状态、writer 二次预检 |
| writer 支持面过宽 | 游戏启动失败或存档异常 | 精确版本矩阵、默认失败关闭、真实样本门禁 |
| 新依赖过重 | 工具 APK 体积、内存和启动时间恶化 | 先做封闭技术验证，按后端独立预算 |
| Split 所有权错误 | 漏资源、资源 ID 冲突、安装失败 | 完整集合模型、owner 字段、单 session 验证 |
| 翻译缓存错配 | 新版本写入旧定位 | 项目指纹、recordId、原文和 schema 校验 |
| 运行时 hook 不稳定 | 崩溃、反作弊或系统兼容问题 | 独立实验后端，不进入默认流程 |
| 用户误解导出状态 | 把译文文件当作已汉化 APK | 独立状态和完成文案，不显示安装操作 |
| 样本偏差 | 对单个游戏过拟合 | 每类多样本、阻断 fixture、公开证据边界 |

## 18. 完成定义

本设计本身完成的标准：

- 能力模型与现有 `supportLevel` 不冲突；
- `TRANSLATABLE_NO_PATCH` 的数据流和用户结果明确；
- adapter、corpus、writer 和 validator 职责边界明确；
- Ren'Py、Android resources、结构化文本、WebView 和 Unity 的范围分开；
- Split APK、安全、缓存和迁移规则明确；
- 每个阶段有可执行验收门禁；
- 未验证能力没有写成已实现或通用支持。

后续实现阶段的总完成标准：

- `EXTRACT_ONLY` 能安全完成翻译、缓存和导出；
- 现有 Ren'Py 已验证路线无回归；
- 每个新增 writer 都通过契约、产物和真实设备验收；
- 不存在通过取消门禁获得的兼容率提升；
- 应用能准确说明每个 APK 当前可以做到哪一步。

## 19. 现有资料关联

- `docs/renpy-engine-optimization.md`：Ren'Py 扫描、RPA/RPYC 与官方行为基线。
- `docs/superpowers/plans/2026-08-07-renpy-app-compatibility-optimization.md`：现有 Ren'Py 安全链路实施计划。
- `docs/qa/renpy-compatibility-matrix.md`：兼容性等级、样本和证据边界。
- `docs/qa/renpy-release-checklist.md`：构建、签名、安装和真机发布门禁。
- `docs/translation-extraction-rules.md`：现有文本提取规则。
- `docs/translation-quality-rules.md`：占位符、上下文和译文质量规则。
- `apk-work/native-fast-scan/src/com/slgtranslator/app/FastApkScanner.java`：当前扫描入口。
- `apk-work/native-fast-scan/src/com/slgtranslator/app/RenpyPreflight.java`：当前 Ren'Py 兼容性预检。
- `apk-work/native-fast-scan/src/com/slgtranslator/app/RpycCompatibility.java`：当前 RPYC writer 能力判断。
- `apk-work/native-fast-scan/src/com/slgtranslator/app/TranslationCompiler.java`：当前 Ren'Py 翻译产物生成链路。
