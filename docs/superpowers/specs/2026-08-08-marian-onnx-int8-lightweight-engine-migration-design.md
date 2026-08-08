# Marian ONNX INT8 轻量翻译引擎迁移设计

## 1. 背景

当前 Android 工具 APK 已提供两条本地翻译路线：

- `mlkit`：由 `MlKitTranslator` 调用 Google ML Kit 设备端翻译，作为“轻量翻译”默认引擎；
- `llm`：由 `LocalLlmEngine` 调用 llama.cpp 和 Qwen2.5 GGUF，作为较慢、体积更大的高质量引擎。

两条路线统一通过 `LocalTranslationSupport` 暴露给 Capacitor WebView。前端按 20 条文本分块调用 `translateLocal`，原生层返回 `translations`、`count`、`warnings`，Qwen 路线还返回 `rejected`。Ren'Py 占位符、插值、标签和 printf 结构由现有保护逻辑与 `RenpyTextValidator` 继续承担最终门禁。

项目不是标准 Gradle Android 工程。`fetch_third_party.py` 固定并校验 AAR/JAR，`build_fast_scanner.py` 解包依赖、使用 `javac` 和 D8 构建辅助 DEX、手工合并 manifest/resources/native libraries，`build_workshop_apk.py` 再把生成的 DEX、资源和 Web 资产替换进基准 APK。因此 Marian 迁移必须适配当前构建链，不能假设 Gradle 自动处理依赖、AAR manifest、ABI 或资源合并。

2026-08-08 的真实设备基线是 Google ML Kit 在 `MZNRYXEQS859O7GU` / `PEMM20` 上完成真实 `异世界天堂0.6` 的 `423/423` 批次翻译：唯一原文 `10251`、总出现 `20864`、已验证 `10251`、缺失/拒绝/不确定均为 `0`，最终编译 `9907` 条，并完成补丁安装、中文菜单和中文对白验收。该结果是 Marian 的迁移对照，不因新增引擎而失效。

## 2. 决策

采用“并存一个发布周期，再决定移除 ML Kit”的迁移方式：

1. 新增 `marian` 引擎，使用 Marian 英译中模型、ONNX Runtime Android 和 INT8 权重量化；
2. 新安装或没有本地翻译偏好的用户默认选择 Marian；
3. 已保存 `mlkit` 偏好的用户继续使用 ML Kit，不进行静默强制迁移；
4. 设置页同时提供 Marian、ML Kit 和 Qwen，Marian 标记为推荐，ML Kit 标记为兼容回退；
5. Marian 未安装、模型损坏、设备不支持或验收未通过时，不自动把失败结果伪装为成功；用户可以明确切换到 ML Kit；
6. 只有 Marian 满足本设计的自动化、质量、性能、离线、真实样本和真机门禁后，后续独立版本才允许删除 ML Kit。

## 3. 目标

- 用可审计、可替换、完全离线的 Marian ONNX INT8 模型建立新的轻量翻译路线。
- 首版只声明英文到简体中文，保持当前真实游戏主路线的语言范围。
- 保持 Capacitor 层的批处理、缓存、进度、覆盖率和构建流程兼容。
- 保持现有 Ren'Py 占位符保护和确定性验证，不因模型输出看似自然而放宽安全门禁。
- 模型单独下载和删除，不把百兆级模型直接打进工具 APK。
- 依赖、模型、许可证和 SHA-256 均固定，构建和运行不得依赖未固定的 `latest` 地址。
- 保留 ML Kit 作为一个发布周期内的显式回退和 A/B 对照。

## 4. 非目标

- 不在首版支持中文到英文、日文到中文、韩文到中文或自动语言检测。
- 不训练新的翻译模型，不在 Android 设备上执行微调。
- 不重构完整应用为 Gradle 工程，不替换现有 Capacitor 和 APKTool 构建方式。
- 不替换 Qwen 高质量引擎。
- 不在用户界面暴露 beam size、线程数、最大 token 等专家参数。
- 不允许 Marian 失败后静默生成不完整发布补丁。
- 不以少量示例翻译成功替代真实 `10251` 条语料和完整补丁流程验收。

## 5. 候选架构与选择

### 5.1 采用：ONNX Runtime Java API + SentencePiece JNI

Java 层负责模型状态、下载、ONNX Session 生命周期、张量准备、自回归解码、结果恢复和 Capacitor 响应；一个边界清晰的小型 JNI 库只负责 SentencePiece 的加载、编码和解码。

选择原因：

- 当前本地翻译主体已经是 Java，新增引擎可以沿用现有线程、`PluginCall`、`JSObject`、错误文案和测试夹具；
- ONNX Runtime Android AAR 可以沿用第三方依赖解包、D8 合并和 ARM64 `.so` 注入路径；
- SentencePiece 使用原生实现可避免纯 Java 重写在 Unicode、normalization、unknown token 和词表兼容方面产生偏差；
- 解码循环留在 Java，便于用 JVM fixture 测试 EOS、长度限制、beam 排序、取消和失败分类；
- 后续更换为其他 Marian 模型时，JNI 分词边界不必跟随业务逻辑重写。

### 5.2 不采用：全部放入统一 C++ JNI 内核

该方案可能减少 Java/native 往返并获得更高性能，但会把 ONNX Runtime C API、SentencePiece、beam search、错误分类和模型管理集中到新的 NDK 子系统。对于当前以 Java、Python 构建脚本和 JVM harness 为主的仓库，首版维护和回归成本过高。

### 5.3 不采用：纯 Java SentencePiece

自行实现 SentencePiece 会增加 normalization、Unicode 分段、特殊 token 和模型兼容风险。首版不以减少一个小型 JNI 库为代价复制分词算法。

## 6. 组件边界

### 6.1 `MarianModelManager`

职责：

- 返回固定模型目录和当前模型版本；
- 下载模型包与许可证文件；
- 使用 `.part` 文件、长度检查、逐文件 SHA-256 和原子目录切换；
- 提供 `supported`、`installed`、`ready`、`downloading`、`downloadState`、`downloadedBytes`、`totalBytes`、`modelVersion` 和 `lastError`；
- 删除模型前关闭 `MarianOnnxEngine` 的共享 Session；
- 模型不完整、校验失败或版本不一致时返回 `ready=false`，不得继续推理。

### 6.2 `MarianSentencePiece`

职责：

- 通过 JNI 加载固定模型包中的 source/target SentencePiece 文件；
- 提供 `encodeSource(String): int[]`、`decodeTarget(int[]): String` 和 `close()`；
- 保证空文本、未知字符、中文输出、emoji、Ren'Py sentinel 和超长文本拥有确定性行为；
- 原生句柄只属于一个已验证模型版本，删除或切换模型时必须释放。

### 6.3 `MarianOnnxEngine`

职责：

- 创建并复用 encoder/decoder ONNX Session；
- 把 source token 转换为 `input_ids` 和 `attention_mask`；
- 执行 encoder 一次，再按 generation 配置执行 decoder；
- 支持中断、最大 token、EOS、无进展和重复输出保护；
- 将 token 交给 target SentencePiece 解码；
- 恢复占位符并调用统一的译文接受门禁；
- 返回与现有本地引擎兼容的结果结构。

### 6.4 `LocalTranslationSupport`

职责保持为引擎路由和 Capacitor 协议适配：

- `translateLocal(engine="marian")` 路由到 `MarianOnnxEngine`；
- `localStatus()` 新增 `marian` 状态，同时继续返回 `mlkit` 和 `llm`；
- `localDownload({engine:"marian"})` 下载 Marian，缺少 `engine` 参数时继续按旧协议下载 ML Kit；
- 新增 `marianDelete()`；
- 继续保留 `mlkitDelete()`、`llmDownload()` 和 `llmDelete()`；
- 下载和推理均运行在后台线程，不阻塞 WebView。

## 7. 模型基线与模型包

首版基线模型为 `Helsinki-NLP/opus-mt-en-zh`。它是英文到中文的 Marian 模型，模型来源、许可证和原始 revision 必须记录在转换清单中。模型发布不能引用浮动分支；转换输入必须固定到具体 revision/commit。

运行模型包固定为：

```text
marian-opus-en-zh-int8-v1/
  manifest.json
  encoder_model.int8.onnx
  decoder_model.int8.onnx
  source.spm
  target.spm
  tokenizer_config.json
  generation_config.json
  LICENSE
  NOTICE
  SHA256SUMS
```

`manifest.json` 至少包含：

```json
{
  "engine": "marian",
  "modelId": "marian-opus-en-zh-int8-v1",
  "sourceLanguage": "en",
  "targetLanguage": "zh",
  "format": "onnx-int8",
  "minimumApi": 24,
  "supportedAbis": ["arm64-v8a"],
  "files": []
}
```

实际生成的 manifest 必须额外包含 `sourceRevision`，其值为转换工具实际检出的 40 位小写十六进制上游 commit SHA；转换命令只接受 commit SHA，不接受 `main`、tag 或短 SHA。`files` 必须写入真实文件项，每项包含相对路径、字节数和 SHA-256。转换工具在无法解析或验证 commit SHA 时直接失败，不生成可发布模型包。

量化范围固定为权重 INT8。首版不使用 INT4，不量化 SentencePiece，不在没有质量对照的情况下量化激活。模型转换必须保存一套未量化 ONNX 参考产物用于离线差异测试，但参考产物不随 Android 模型包发布。

## 8. 解码与批处理

### 8.1 文本入口

WebView 继续按最多 20 条调用原生桥。原生 Marian 引擎不假设 20 条必须同时进入一个张量，而是按 token 长度排序后形成最多 4 条的内部 micro-batch，避免单条长文本拖大整个 batch 的 padding。

### 8.2 占位符

进入 SentencePiece 前，继续调用现有 `LocalLlmEngine.protectPlaceholders` 生成 `__SLGPHn__` sentinel。输出解码后调用 `restorePlaceholders`；任何 sentinel 缺失、重复、顺序错误或残留都进入 `rejected`，不能写入 `translations`。

### 8.3 Generation 配置

首版只比较两种候选配置：greedy 和 beam size 2。beam size 4 不进入移动端首版候选，以控制内存和十万级 decoder step 风险。

固定选择规则：

- 如果 beam size 2 在固定质量集上相对 greedy 的人工偏好提升至少 5 个百分点，且在目标设备上的总耗时不超过 greedy 的 1.6 倍，则使用 beam size 2；
- 否则使用 greedy；
- 被选配置写入 `generation_config.json` 并由 SHA-256 固定，运行时不允许 UI 覆盖；
- 两种配置都必须使用明确的 `decoder_start_token_id`、`eos_token_id`、`pad_token_id`、最大 source token 和最大 target token；
- 达到最大 token、连续重复、空输出或未产生 EOS 时返回明确警告或拒绝，不截断后伪装为完整译文。

### 8.4 结果接受

Marian 与 Qwen 共用同一套最终接受语义：

1. 译文非空；
2. sentinel 完整恢复；
3. `RenpyTextValidator.validate(old, translated)` 通过；
4. 译文与原文不完全相同；
5. 相同 exact-old 不产生冲突译文；
6. 通过后才写入 `translations`。

Marian 响应结构固定为：

```json
{
  "translations": {},
  "count": 0,
  "warnings": [],
  "rejected": [],
  "engine": "marian",
  "modelVersion": "marian-opus-en-zh-int8-v1"
}
```

## 9. UI 与设置迁移

本地供应商显示三个模型选项：

- `marian`：`轻量翻译（Marian，推荐）`；
- `mlkit`：`兼容翻译（ML Kit）`；
- `qwen`：`高质量翻译（本地模型）`。

行为规则：

- 没有保存偏好的新用户默认 `marian`；
- 已保存 `model:"mlkit"` 的用户仍选中 ML Kit；
- 已保存 `model:"qwen"` 的用户仍映射到原生 `llm`；
- 不把 `mlkit` 字符串全局替换成 `marian`，避免破坏旧任务、缓存和回退入口；
- Marian 卡片显示下载状态、版本、体积、下载/删除操作和校验失败信息；
- Marian 下载按钮调用 `localDownload({engine:"marian",sourceLang:"en",targetLang:"zh"})`；
- 翻译入口将 `marian` 映射为 `translateLocal(...,engine:"marian")`；
- API Key 门禁继续对所有本地模型关闭；
- Marian 失败时显示可执行操作：重新下载、切换 ML Kit 或查看处理详情，不自动切换并继续生成补丁。

## 10. 构建与依赖

### 10.1 ONNX Runtime

`fetch_third_party.py` 新增固定版本的 `com.microsoft.onnxruntime:onnxruntime-android` 根依赖，并把 AAR、POM、文件大小和 SHA-256 写入现有 `SHA256SUMS.txt`。版本只能在专项兼容测试通过后更新。

`build_fast_scanner.py` 必须：

- 从 ONNX Runtime AAR 提取 `classes.jar` 参与 javac/D8；
- 仅注入 `arm64-v8a` 所需 `.so`；
- 检测同名 native library 冲突并失败，而不是后写覆盖；
- 验证最终 APK 中每个要求的 ORT/SentencePiece `.so` 恰好存在一次；
- 把 Marian Java 类合入 helper DEX，并验证类描述符归属唯一。

### 10.2 SentencePiece JNI

新增一个独立、可重复的 NDK 构建脚本，输入固定 SentencePiece source revision，输出仅包含 `arm64-v8a` 的 JNI `.so`。构建产物及 source revision 必须写入 checksum 清单。该脚本不能依赖开发者机器中未记录的全局 CMake/NDK 状态。

### 10.3 ML Kit 并存

并存版本继续保留 ML Kit AAR、manifest registrar、资源和 native library 注入逻辑。Marian 验收通过前不得删除 `translate-17.0.3.aar` 或相关资源生成代码。ML Kit 的删除属于后续独立计划，必须重新验证 APK 资源、manifest、DEX、签名和真机回滚。

## 11. 错误处理与资源生命周期

- ONNX Runtime 初始化失败：`supported=false` 或 `ready=false`，记录短错误码和可读中文信息；
- 模型缺失：拒绝翻译并提示先下载，不创建空结果补丁；
- SHA-256 不匹配：删除临时文件，保留已安装的旧版本；
- 存储不足：下载前按 manifest 总大小加安全余量检查；
- 下载中断：保留可验证的 `.part` 供明确的断点续传实现使用；没有断点信息时重新下载，不把 partial 标为 installed；
- Session 创建失败：关闭已创建资源并允许用户切换 ML Kit；
- 单条文本失败：记录 `rejected`/`warnings`，继续同批其他条目；
- 进程回收：翻译缓存继续由现有 WebView 任务快照恢复，原生 Session 下次按模型状态重新创建；
- 删除模型：先阻止新的 Marian 调用，再等待或取消当前推理，关闭 Session/tokenizer，最后删除目录；
- 内存压力：允许关闭共享 Session，但不得删除模型文件或破坏任务缓存。

## 12. 测试设计

### 12.1 模型工具测试

- 上游 revision、许可证和模型文件清单可重复获取；
- ONNX FP32 与原始 Transformers 输出在固定语料上语义一致；
- INT8 与 FP32 在固定质量集上没有超过门限的退化；
- 每个发布文件的大小和 SHA-256 与 manifest 一致；
- 损坏、缺失、额外和版本错误文件均不能通过模型校验。

### 12.2 JVM/原生契约测试

- `localStatus` 同时返回 `marian`、`mlkit`、`llm`；
- 缺省 `localDownload` 仍走 ML Kit，新调用通过 `engine:"marian"` 下载 Marian；
- SentencePiece 编解码覆盖 ASCII、中文、emoji、sentinel、空文本和未知字符；
- encoder/decoder 输入名称、维度和 dtype 与模型 manifest 一致；
- EOS、最大长度、中断、空输出、重复输出和异常张量稳定失败；
- 占位符丢失和 `RenpyTextValidator` 失败进入 `rejected`；
- 模型删除会关闭 Session，删除后状态变为未安装；
- 并发下载和并发初始化不会创建两套可写模型目录或两个共享 Session。

### 12.3 UI 契约测试

- 新设置默认 Marian；旧 `mlkit` 和 `qwen` 偏好保持不变；
- Marian/ML Kit/Qwen 三项均可选择；
- Marian 下载、状态、删除和翻译调用包含正确 engine；
- 本地供应商不要求 API Key；
- Marian 失败不会自动切换、继续编译或伪造成功数；
- 旧 ML Kit 路线的现有自动化继续通过。

### 12.4 构建测试

- 第三方 checksum 全部通过；
- helper DEX 中 Marian 类恰好一份；
- 最终 APK 中 ORT、SentencePiece、llama 和 ML Kit 要求的 ARM64 `.so` 均存在且无同名冲突；
- manifest、ML Kit 资源和现有 Capacitor bridge 保持有效；
- `zipalign`、APK v2/v3 签名、版本和包名检查通过；
- APK 能在目标 Android 13 设备替换安装且不清除应用数据。

## 13. 质量与性能验收

建立两个固定语料集：

1. `local-engine-smoke`：不少于 200 条，覆盖菜单、短对白、长对白、角色名、标点、emoji、Ren'Py 标签、插值、printf 和不可翻译文本；
2. `real-game-quality`：从真实 `10251` 条唯一原文中按固定种子分层抽取不少于 500 条，保留文本类型和长度分布。

质量验收：

- placeholder/markup 结构通过率必须为 100%；
- smoke 集不得产生空译文、残留 sentinel 或不可解析输出；
- 500 条质量集由盲评比较 Marian 与当前 ML Kit，Marian 的“更好”比例必须至少比“更差”比例高 10 个百分点；
- 严重错误率不得高于 ML Kit，包括反义、漏掉关键否定、人物/数字错误和明显未翻译；
- 固定术语一致性不得低于 ML Kit；
- 质量门限未通过时 Marian 不成为默认引擎，ML Kit 保持默认并记录 FAIL。

性能验收在 `PEMM20` 或性能不高于该设备的批准设备上执行：

- 首次 Session 初始化峰值内存、稳定内存和耗时必须有实测记录；
- 200 条 smoke 集翻译过程不得发生 OOM、ANR、WebView 崩溃或进程被系统杀死；
- 设备锁屏/解锁或应用前后台切换后，任务状态和已完成缓存保持一致；
- Marian 的 200 条总耗时不得超过同机 ML Kit 的 4 倍；
- 真实 `10251` 条路线必须在应用允许的长任务边界内完成，不出现持续无进展 5 分钟以上的批次；
- 如果性能门限未通过，保留 Marian 为实验选项或阻断发布，不通过隐藏降级掩盖失败。

## 14. 真实设备与端到端验收

使用当前真实样本和 `content://` 路线执行：

```text
选择真实 APK
→ resolved-copy 和菜单注入
→ 扫描与兼容性预检
→ 选择 Marian
→ 下载并校验模型
→ 断网 smoke 翻译
→ 真实语料完整翻译
→ coverage/lint/font gate
→ RPYC 编译与 validator
→ patched APK 构建、签名和安装
→ 启动游戏
→ 查看中文菜单和真实对白
```

必须记录：

- 工具 APK SHA-256、版本、签名、设备型号和 Android 版本；
- Marian 模型 ID、上游 revision、模型包 SHA-256 和 generation 配置；
- 下载完成后的离线状态和断网翻译结果；
- 批次数、唯一原文、总出现、validated、missing、rejected、uncertain 和 compiled；
- 总耗时、峰值内存、失败批次、重试和前后台行为；
- 生成补丁安装结果、中文菜单、真实对白和启动日志；
- 同一版本中 ML Kit 回退 smoke 路线仍然可用。

Marian 只有在真实路线达到 `missing=0`、`rejected=0`、`uncertain=0`，且没有选择 incomplete test patch 时，才可获得与当前 ML Kit 基线同等级的 scoped PASS。任何缺少设备、模型、网络、存储或真实样本证据的情况保持 `NOT-RUN` 或 `BLOCKED`，不得推断通过。

## 15. ML Kit 移除门禁

并存版本发布后，只有同时满足以下条件，才能启动独立的 ML Kit 移除计划：

1. Marian 自动化测试、完整 discover、APK 构建和签名全部通过；
2. 固定质量集和性能门限通过；
3. 至少一次真实 `10251` 条完整路线通过；
4. 至少一次断网完整 smoke 和前后台恢复通过；
5. Marian 版本发布后没有 P0/P1 模型损坏、崩溃、严重错译或无法下载问题；
6. QA 文档明确记录 Marian PASS 和 ML Kit 回退 PASS；
7. 删除 ML Kit 后预计 APK 体积、manifest、资源、依赖和 native library 差异经过独立审计；
8. 存在可安装的上一版本 APK，能够在不清除应用数据的情况下回滚。

ML Kit 移除必须是单独设计、单独计划和单独发布门禁，不作为本迁移计划的最后一个顺手删除步骤。

## 16. 发布与回滚

### 16.1 并存版本

- Marian 为新默认；
- ML Kit 为显式兼容回退；
- Qwen 行为不变；
- 旧用户偏好和旧任务缓存继续可读；
- QA 结论分别记录 Marian、ML Kit 和整体发布状态。

### 16.2 回滚条件

发生以下任一情况时，发布决策回退为 ML Kit 默认：

- Marian 模型下载源不可用且没有批准镜像；
- checksum 或许可证清单不完整；
- 目标设备发生 OOM、ANR 或稳定崩溃；
- 质量或真实性能门限未通过；
- 真实语料存在无法收口的 missing/rejected/uncertain；
- 安装、启动、菜单或对白验收失败。

回滚只改变默认选择和发布结论，不删除用户已下载的 Marian 模型；用户可在设置页主动删除。除非模型被确认损坏或存在安全问题，否则不远程删除本地文件。

## 17. 完成定义

本设计的实现阶段只有在以下结果同时成立时完成：

- `marian` 引擎、模型管理、SentencePiece JNI、ONNX 推理和 UI 路由全部实现；
- ML Kit 与 Qwen 路线没有回归；
- 模型和依赖均有固定版本、许可证和 SHA-256；
- 自动化、完整 discover、APK 构建、签名和安装验证通过；
- 固定质量与性能门限通过；
- 真实 `content://`、完整语料、补丁安装和中文游戏路线通过；
- QA 证据明确区分 PASS、FAIL、BLOCKED 和 NOT-RUN；
- ML Kit 仍然存在，且是否移除由后续独立计划决定。

## 18. 参考资料

- ONNX Runtime Android Java：<https://onnxruntime.ai/docs/get-started/with-java.html>
- ONNX Runtime Mobile：<https://onnxruntime.ai/docs/tutorials/mobile/>
- ONNX Runtime 量化：<https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html>
- Optimum ONNX export：<https://huggingface.co/docs/optimum/exporters/onnx/usage_guides/export_a_model>
- Marian OPUS 英译中模型：<https://huggingface.co/Helsinki-NLP/opus-mt-en-zh>
- SentencePiece：<https://github.com/google/sentencepiece>
