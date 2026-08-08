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
2. 候选/内部验证构建继续以 ML Kit 为默认；只有 `AUTOMATED_PASS`、`DEVICE_PASS` 和 `QUALITY_PASS` 同时成立的生产并存版本，才让新安装或没有本地翻译偏好的用户默认选择 Marian；
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

### 5.1 采用：单次 JNI 批调用 + 统一 C++ Marian Runtime

Java 层负责模型状态、下载、任务线程、占位符保护、最终 Ren'Py 验证和 Capacitor 响应。SentencePiece、ONNX Runtime C/C++ API、encoder、初始 decoder、带 KV cache 的 decoder、自回归生成循环和 beam/greedy 状态全部位于一个统一 native runtime 中。每个内部 micro-batch 从 Java 进入 native 一次，生成完成或失败后一次性返回译文和逐项状态；输出 token 数量不得增加 JNI 往返次数。

选择原因：

- 当前本地翻译主体已经是 Java，新增引擎可以沿用现有线程、`PluginCall`、`JSObject`、错误文案和测试夹具；
- 自回归 decoder 每个 token 都需要一次 ONNX 执行；如果循环位于 Java，`OrtSession.run()`、输入/输出包装和 Java/JNI 边界成本会随输出长度线性增长，在 `10251` 条真实语料规模上形成不可接受的额外开销；
- native runtime 在一次 JNI 调用内复用 Session、encoder states、KV cache、张量描述和解码工作区，避免每 token 创建 Java 对象或跨层传递张量；
- SentencePiece 使用原生实现可避免纯 Java 重写在 Unicode、normalization、unknown token 和词表兼容方面产生偏差；
- 统一输出一个仓库自管的 `libslg_marian.so`，更符合当前手工注入 ARM64 native library 的构建方式，也减少多个 JNI AAR 的符号和装载冲突；
- Java 仍保留模型管理、业务验证和用户可见错误，native 层只负责可独立测试的模型执行协议。

### 5.2 不采用：Java 层逐 token 调用 ONNX Runtime

该方案接入代码更接近现有 Java 引擎，但每生成一个 token 都需要 Java `OrtSession.run()` 进入 native，并处理输入、输出和生命周期对象。即使单次边界成本小于模型计算，它也会按句子输出长度和语料条数累积；因此不作为生产架构。Java ONNX API 只允许用于离线转换验证或非发布实验，不进入工具 APK 的 Marian 生产路径。

### 5.3 不采用：纯 Java SentencePiece

自行实现 SentencePiece 会增加 normalization、Unicode 分段、特殊 token 和模型兼容风险。首版不以减少 native runtime 的一个依赖为代价复制分词算法。

## 6. 组件边界

### 6.1 `MarianModelManager`

职责：

- 模型根目录固定为 `new File(context.getFilesDir(), "models/marian")`，下载 staging、已安装版本和活动指针都必须位于该根目录内；
- 目录布局固定为 `.staging/<uuid>/`、`versions/<modelBuildId>-<packageContentSha256>/` 和 `active.json`，不使用外部存储、公共下载目录或用户可配置路径作为安装目录；
- 下载模型包与许可证文件；
- 在 `.staging/<uuid>/` 内使用 `.part` 文件完成下载、解包、长度检查、逐文件 SHA-256、manifest 校验和可加载性 smoke；
- 校验通过后，将 staging 目录在同一模型根目录内重命名为不可变版本目录，再通过同目录中的 `active.json.tmp` 原子替换 `active.json` 激活新版本；
- 在目录重命名和活动指针替换前同步文件内容，并通过 native helper 同步对应目录项；
- 安装前验证 staging、versions 和 active pointer 的 canonical path 均位于 `getFilesDir()` 下，并通过 native `stat.st_dev` 验证 staging 与最终目录属于同一文件系统；
- `rename` 返回 `EXDEV`、目标冲突或其他失败时保留当前活动版本、删除或隔离 staging，并返回安装失败；禁止用跨卷复制或非原子目录移动自动兜底；
- 已存在相同 `modelBuildId + packageContentSha256` 的完整版本时复用该不可变目录，不覆盖其中任何文件；
- 提供 `supported`、`installed`、`ready`、`downloading`、`downloadState`、`downloadedBytes`、`downloadBytes`、`installedBytes`、`modelVersion`、`modelBuildId` 和 `lastError`；
- 删除模型前关闭 `MarianNativeRuntime` 的共享 native handle；
- 模型不完整、校验失败或版本不一致时返回 `ready=false`，不得继续推理。

### 6.2 `MarianNativeRuntime`

职责：

- 通过 JNI 加载固定模型包中的 SentencePiece、encoder、decoder 和 decoder-with-past；
- Java 边界只暴露 `open(modelDir, manifest)`、`translateBatch(handle, requestId, protectedTexts)`、`cancel(handle, requestId)` 和 `close(handle)`；
- `translateBatch` 在一次 JNI 调用内完成 tokenization、encoder、完整自回归循环、detokenization 和逐项 native 错误分类；
- decoder 循环复用预分配工作区、encoder states 和 KV cache，不把 token logits、past tensors 或 attention mask 逐 token 返回 Java；
- 保证空文本、未知字符、中文输出、emoji、Ren'Py sentinel 和超长文本拥有确定性行为；
- 每个 native handle 只允许一个活动 `translateBatch`；SentencePiece 的 `Load`、模型切换和 handle 关闭使用独占锁，Encode/Decode 虽然是 const 操作，仍与共享 decoder 工作区一起受该 handle 的推理互斥锁保护；
- `cancel` 可以从另一后台线程设置 request-scoped 原子取消标记，并对当前请求专属的 ONNX Runtime `RunOptions` 调用 terminate；当前 `Session::Run` 返回取消状态后 native decoder 立即退出，不通过并发 `close(Session)` 取消；
- 原生 handle 只属于一个已验证模型版本，删除、切换模型或内存回收时必须释放。

### 6.3 `MarianOnnxEngine`

职责：

- 创建、复用和关闭 `MarianNativeRuntime` handle；
- 为每个 WebView chunk 生成唯一 `requestId`，一次性把最多 20 条受保护文本交给 native；
- native 完成真实 SentencePiece tokenization 后再执行动态 batch planning，Java 不用字符长度猜测 token 数；
- 每个 WebView chunk 只调用一次 `translateBatch`，不得在 Java 中按 item、micro-batch 或 token 调用 ONNX Runtime；
- Java 侧使用公平的单引擎串行队列，避免 Capacitor 后台线程并发进入同一个 handle；排队请求必须可取消，超过队列上限时返回 `MARIAN_ENGINE_BUSY`；
- 将线程中断转换为 `cancel(handle, requestId)`，等待 native 调用有界退出；
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
marian-opus-en-zh-int8-1.0.0/
  manifest.json
  encoder_model.int8.onnx
  decoder_model.int8.onnx
  decoder_with_past_model.int8.onnx
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
  "modelFamilyId": "marian-opus-en-zh-int8",
  "modelVersion": "1.0.0",
  "sourceLanguage": "en",
  "targetLanguage": "zh",
  "format": "onnx-int8",
  "minimumApi": 24,
  "supportedAbis": ["arm64-v8a"],
  "files": []
}
```

实际生成的 manifest 必须额外包含：

- `sourceRevision`：转换工具实际检出的 40 位小写十六进制上游 commit SHA，仅用于来源追踪，不参与版本先后比较；
- `packageContentSha256`：按路径排序后的 `files` 项进行 canonical serialization 后计算的内容摘要；
- `modelBuildId`：固定为 `<modelVersion>+<packageContentSha256前12位>`，例如 `1.0.0+4f8c2a61bd90`；
- `createdUtc`：构建记录字段，不参与安装身份和升级判断；
- `files`：真实文件项，每项包含相对路径、字节数和 SHA-256。

转换命令只接受 commit SHA，不接受 `main`、tag 或短 SHA。任何会改变模型输出、tokenizer、generation 配置、文件内容或 native 兼容要求的重新转换都必须递增语义化 `modelVersion`；同一 `modelVersion` 出现不同 `packageContentSha256` 时，发布流水线按不可变版本被篡改处理并失败，不允许以构建时间戳掩盖。安装、状态、缓存和更新比较使用完整 `modelBuildId`，不能只比较 `modelFamilyId`、`modelVersion` 或 `sourceRevision`。

量化范围固定为权重 INT8。首版不使用 INT4，不量化 SentencePiece，不在没有质量对照的情况下量化激活。模型转换必须导出可复用 past key/value 的 decoder-with-past；如果固定模型和导出工具无法生成或验证 KV cache 路线，Marian 移动端迁移保持阻断，不回退到每一步重算完整 decoder prefix。转换同时保存一套未量化 ONNX 参考产物用于离线差异测试，但参考产物不随 Android 模型包发布。

## 8. 解码与批处理

### 8.1 文本入口

WebView 继续按最多 20 条调用原生桥，并把整个 chunk 通过一次 `MarianNativeRuntime.translateBatch` 交给 C++。native 先对全部条目执行真实 SentencePiece tokenization，再按 token 成本动态规划内部 micro-batch；JNI 调用次数只允许与 WebView chunk 数量相关，不允许与内部 micro-batch 或输出 token 数量相关。

动态规划规则固定为：

- `generation_config.json` 固定 `maxSourceTokens=512`、`maxBatchItems=20` 和首版 `maxPaddedSourceTokens=512`；
- 对可直接翻译的条目按 source token 数降序排列，使用 first-fit-decreasing 放入 batch；加入条目后的 padded cost 定义为 `batchItemCount * maxSourceLength`，不得超过 `maxPaddedSourceTokens`；
- 20 条短词只要 padded cost 不超过预算即可进入一个 batch，不人为拆成 5 个四条 batch；
- 单条超过 `maxSourceTokens` 时先按换行、句末标点和安全空白边界分段，sentinel 和 Ren'Py 标记不可拆分；各段分别翻译后按原分隔符重组；
- 无法安全分段或单个不可拆单元仍超过上限时返回 `MARIAN_SOURCE_TOO_LONG`，不截断、不尝试超预算推理；
- batch planner 的输入长度、padded cost、分组结果和拒绝原因进入无文本内容的诊断指标。

### 8.2 启动预检、下载与热切换

每个翻译任务在首次调用 Marian 前固定 `engineId="marian"` 和当前 `modelBuildId`，并执行本地 preflight：

- `ready=false` 或模型缺失时，前端不调用翻译循环，展示模型大小、网络要求和“一键下载并继续”；
- 用户确认后调用 `localDownload({engine:"marian"})`，下载、校验、激活和 warm-up 全部成功后自动重试原 pending start action；
- 用户取消、下载失败或校验失败时任务保持 `ready/paused`，已扫描文本和缓存不丢失，不进入编译；
- 同一界面提供“改用 ML Kit”显式操作，但不得自动降级；
- 原生 `translateLocal` 无论前端是否做过 preflight，都必须再次校验并使用稳定错误码拒绝：`MARIAN_MODEL_NOT_READY`、`MARIAN_MODEL_CORRUPT`、`MARIAN_MODEL_CHANGED`、`MARIAN_ENGINE_BUSY` 或 `MARIAN_WARMUP_FAILED`；
- preflight 失败不得返回 `translations:{}` 的成功响应，不增加 success count，不写翻译缓存，因此不会生成空对白或不完整补丁；
- 任务快照和缓存命名空间必须包含 `engineId + modelBuildId`；活动模型在任务运行中更新时，既有任务继续持有旧不可变版本的 handle，新任务使用新活动版本；
- 用户在已有成功译文后切换 Marian/ML Kit/Qwen，必须在批次边界暂停并确认“使用新引擎重新翻译”；确认后清空当前任务的活动 translation map，旧引擎缓存保留在独立命名空间，不允许一个发布补丁静默混合多个引擎或模型构建的译文；
- 旧版本目录只有在没有任务引用且新的活动版本通过校验后才允许清理。

### 8.3 占位符

进入 SentencePiece 前，继续调用现有 `LocalLlmEngine.protectPlaceholders` 生成 `__SLGPHn__` sentinel。输出解码后调用 `restorePlaceholders`；任何 sentinel 缺失、重复、顺序错误或残留都进入 `rejected`，不能写入 `translations`。

### 8.4 Generation 配置

首版只比较两种候选配置：greedy 和 beam size 2。beam size 4 不进入移动端首版候选，以控制内存和十万级 decoder step 风险。

固定选择规则：

- 如果 beam size 2 在固定质量集上相对 greedy 的人工偏好提升至少 5 个百分点，且在目标设备上的总耗时不超过 greedy 的 1.6 倍，则使用 beam size 2；
- 否则使用 greedy；
- 被选配置写入 `generation_config.json` 并由 SHA-256 固定，运行时不允许 UI 覆盖；
- 两种配置都必须使用明确的 `decoder_start_token_id`、`eos_token_id`、`pad_token_id`、最大 source token 和最大 target token；
- 初始 token 使用 `decoder_model.int8.onnx`，后续 token 必须使用 `decoder_with_past_model.int8.onnx` 和复用的 KV cache；
- native 循环复用张量元数据和工作区，禁止每 token 重新打开 Session、重新执行 encoder 或重新构造完整历史 prefix；
- 达到最大 token、连续重复、空输出或未产生 EOS 时返回明确警告或拒绝，不截断后伪装为完整译文。

### 8.5 结果接受

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
  "modelVersion": "1.0.0",
  "modelBuildId": "1.0.0+4f8c2a61bd90"
}
```

## 9. UI 与设置迁移

本地供应商显示三个模型选项：

- `marian`：`轻量翻译（Marian，推荐）`；
- `mlkit`：`兼容翻译（ML Kit）`；
- `qwen`：`高质量翻译（本地模型）`。

行为规则：

- 没有保存偏好的新用户只在生产发布配置 `DEFAULT_LOCAL_ENGINE="marian"` 经过三项 PASS 批准后默认 Marian；候选/内部验证构建固定 `DEFAULT_LOCAL_ENGINE="mlkit"`，但仍显示 Marian 实验选项；
- 已保存 `model:"mlkit"` 的用户仍选中 ML Kit；
- 已保存 `model:"qwen"` 的用户仍映射到原生 `llm`；
- 不把 `mlkit` 字符串全局替换成 `marian`，避免破坏旧任务、缓存和回退入口；
- Marian 卡片显示下载状态、版本、体积、下载/删除操作和校验失败信息；
- Marian 下载按钮调用 `localDownload({engine:"marian",sourceLang:"en",targetLang:"zh"})`；
- 翻译入口将 `marian` 映射为 `translateLocal(...,engine:"marian")`；
- API Key 门禁继续对所有本地模型关闭；
- Marian 失败时显示可执行操作：重新下载、切换 ML Kit 或查看处理详情，不自动切换并继续生成补丁。

## 10. 构建与依赖

### 10.1 统一 Native Runtime

生产 APK 不引入 ONNX Runtime Java binding，也不在 Java 中持有 `OrtSession`。新增一个独立、可重复的 NDK 构建单元，输入固定 commit 的 ONNX Runtime 和 SentencePiece source，输出仅包含 `arm64-v8a` 的 `libslg_marian.so`。该库静态链接裁剪后的 ONNX Runtime mobile runtime 和 SentencePiece，并导出仓库自有 JNI 符号。

native 构建必须：

- 固定 ONNX Runtime、SentencePiece、NDK、CMake 和编译参数；
- 根据 encoder、decoder、decoder-with-past 模型生成 required-operator 配置，只编入实际使用的算子和类型；
- 默认关闭异常、RTTI 或其他特性前，必须证明 JNI 错误映射和 ONNX Runtime 构建仍完整；
- 生成 `libslg_marian.so`、构建元数据、符号清单、文件大小和 SHA-256；
- 使用 NDK libc++ 静态运行时和 hidden visibility；C++ 对象不跨 JNI ABI 边界，最终动态依赖中不得出现 `libc++_shared.so`、`libprotobuf.so` 或 `libonnxruntime.so`；
- 运行 host/native 测试后才把 `.so` 复制到 `third-party/` 或专用 pinned-native 目录；
- 不依赖开发者机器中未记录的全局 CMake、NDK、Python 包或环境变量。

`build_fast_scanner.py` 必须：

- 把 Marian Java bridge 类合入 helper DEX，并验证类描述符归属唯一；
- 仅注入 `arm64-v8a/libslg_marian.so`；
- 检测同名 native library 冲突并失败，而不是后写覆盖；
- 验证最终 APK 中 `libslg_marian.so` 恰好存在一次；
- 验证 Marian 生产 DEX 不引用 `ai.onnxruntime.OrtSession`、`OnnxTensor` 或其他 Java binding 类；
- 使用 NDK `llvm-readelf -d` 验证 SONAME 恰好为 `libslg_marian.so`，并验证 `DT_NEEDED` 只包含批准的 Android NDK 公共系统库 allowlist；
- 使用 `llvm-readelf --dyn-syms --version-info` 验证只导出批准 JNI/诊断符号，不出现意外 `GLIBC`、`GLIBCXX`、protobuf、ONNX Runtime 或超出 API 24 的符号版本依赖；Android 使用 libc++，因此不能只搜索 `GLIBCXX` 就宣布兼容；
- 在 API 24 arm64 模拟器或批准的真实 Android 7 设备执行 `System.loadLibrary("slg_marian")`、native ABI probe、Session open 和一句 smoke 翻译；只有静态 readelf 检查不能替代实际装载；
- 保持现有 llama 和 ML Kit native library 注入路径不变。

### 10.2 JNI 协议

JNI 只传递模型目录、manifest、受保护字符串数组、request ID、译文数组和逐项状态。encoder states、logits、token IDs、attention masks、KV cache 和 beam state 不得穿越 Java/native 边界。`translateBatch` 的一次调用必须覆盖一个 WebView chunk 的 tokenization、动态 micro-batch planning 和完整生成过程；取消通过独立 `cancel(handle, requestId)` 设置 native 原子标志，不通过杀死线程或泄漏 Session 实现。

### 10.3 ML Kit 并存

并存版本继续保留 ML Kit AAR、manifest registrar、资源和 native library 注入逻辑。Marian 验收通过前不得删除 `translate-17.0.3.aar` 或相关资源生成代码。ML Kit 的删除属于后续独立计划，必须重新验证 APK 资源、manifest、DEX、签名和真机回滚。

## 11. 错误处理与资源生命周期

- ONNX Runtime 初始化失败：`supported=false` 或 `ready=false`，记录短错误码和可读中文信息；
- 模型缺失：拒绝翻译并提示先下载，不创建空结果补丁；
- SHA-256 不匹配：删除临时文件，保留已安装的旧版本；
- 存储不足：manifest 必须分别声明压缩/传输体积 `downloadBytes` 和解包后的 `installedBytes`；开始下载前通过 `StatFs` 要求 `availableBytes >= downloadBytes + installedBytes + max(50 MiB, ceil(installedBytes * 0.5))`；如果旧格式只提供单一 `totalBytes`，使用保守公式 `ceil(totalBytes * 2.5) + 50 MiB`；
- 下载中断：保留可验证的 `.part` 供明确的断点续传实现使用；没有断点信息时重新下载，不把 partial 标为 installed；
- 下载完成和每个大文件解包前重新检查剩余空间；任何写入、解压、fsync 或 rename 的 `ENOSPC` 失败都关闭句柄、删除当前 staging 和 `.part`、保留旧活动版本，并返回 `MARIAN_STORAGE_INSUFFICIENT`；
- staging 与最终目录不在同一 `st_dev`、canonical path 逃出内部模型根目录或 rename 返回 `EXDEV`：终止安装并保持原 `active.json` 不变，不执行复制兜底；
- `active.json` 损坏或指向不存在/未通过校验的版本：返回 `ready=false`，尝试从最近一个完整不可变版本恢复活动指针前必须重新校验该版本；
- native handle 或 Session 创建失败：关闭已创建资源并允许用户切换 ML Kit；
- 单条文本失败：记录 `rejected`/`warnings`，继续同批其他条目；
- 进程回收：翻译缓存继续由现有 WebView 任务快照恢复，native handle 下次按模型状态重新创建；
- 删除模型：先阻止新的 Marian 调用，再取消并有界等待当前 request，关闭 native handle，最后删除目录；
- 内存压力：允许关闭共享 native handle，但不得删除模型文件或破坏任务缓存。

### 11.1 取消协议

- 每个 `translateBatch` 创建 request-scoped `Ort::RunOptions` 和原子取消标记，不在请求之间复用 terminated RunOptions；
- `cancel(handle, requestId)` 先设置原子标记，再对当前 RunOptions 调用 terminate；native 循环在每次 tokenizer segment、encoder、decoder step 和 batch 边界检查标记；
- 正在执行的 ONNX kernel 只能在 ONNX Runtime 响应 terminate 后返回，UI 在此期间显示“正在取消”，不得并发关闭或删除 Session；
- Run 返回取消状态后，native 释放该请求的 tensors、KV cache 和工作区，返回 `MARIAN_CANCELLED`，不写入当前 micro-batch 的部分译文；
- 目标设备上从用户取消到 native 调用返回的 P95 必须不超过 5 秒；超过门限记为 `DEVICE_FAIL`，不得以强关 Session 规避。

### 11.2 模型预热

- 模型下载、校验和活动指针切换后，在后台打开共享 handle，并使用固定输入 `Hello` 执行一次完整 tokenizer、encoder、decoder-with-past 和 decode warm-up；
- warm-up 输出不进入用户缓存，但必须通过非空、EOS、Unicode 和占位符基础检查；
- `localStatus.marian` 增加 `warmingUp`、`warmupReady`、`warmupMs` 和 `warmupErrorCode`；`localDownload(engine="marian")` 只有在 warm-up 通过后才返回 `ready=true` 并触发 pending start 自动重试；
- 进程冷启动不在主线程或应用首屏同步预热；只有用户进入本地翻译设置、恢复 Marian 任务或准备开始 Marian 翻译时才启动后台预热；
- warm-up 失败返回 `MARIAN_WARMUP_FAILED`，模型文件保留用于诊断或重试，但不能进入翻译循环。

### 11.3 输出规范化

模型输出按固定顺序处理：

1. 将 `CRLF` 和孤立 `CR` 统一为 `LF`；
2. 使用 Java `Normalizer.normalize(text, Normalizer.Form.NFC)`，禁止使用会改变兼容字符语义的 NFKC；
3. 移除单个开头 BOM `U+FEFF`；
4. 检查 NUL、非换行/制表的 C0 控制字符、`U+200B`、`U+2060`、双向控制字符和中间位置 BOM；仅当同一字符原文中已经存在时才允许保留，否则以 `unsafe_control_character` 拒绝，不静默删除；
5. 恢复 sentinel 占位符；
6. 执行 `RenpyTextValidator` 和 exact-old 冲突检查。

规范化前后的字符数、被拒绝的 Unicode code point 和错误码可以进入诊断日志，但不得记录原文或完整译文。

### 11.4 日志与诊断指标

每个 WebView chunk 和内部 micro-batch 记录结构化指标：

- `requestId`、`engine`、`modelBuildId`、chunk/batch 序号和 item 数；
- source token、padded token、generated token、分段数和 beam 配置；
- queue wait、tokenize、encoder、decoder、decode、Unicode/validator 和总耗时；
- 峰值 native working-set 采样、取消延迟、错误码、rejected 数和 retry 次数；
- warm-up、handle open/close、模型激活和活动指针恢复事件。

日志不得包含 API Key、文件正文、原文、译文、完整文件路径或可还原游戏内容的 token 序列。应用内诊断环形缓冲最多保留 1000 条事件或 2 MiB，先到者触发覆盖；用户导出诊断时继续执行现有脱敏规则。

## 12. 测试设计

### 12.1 模型工具测试

- 上游 revision、许可证和模型文件清单可重复获取；
- ONNX FP32 与原始 Transformers 输出在固定语料上语义一致；
- INT8 与 FP32 在固定质量集上没有超过门限的退化；
- 每个发布文件的大小和 SHA-256 与 manifest 一致；
- `modelBuildId` 与 canonical `packageContentSha256` 一致；相同 `modelVersion` 配不同内容摘要时发布流水线必须失败；
- `downloadBytes`、`installedBytes` 和实际下载/解包体积一致，磁盘公式覆盖压缩包、staging、解包结果和 50 MiB 最小余量；
- 损坏、缺失、额外和版本错误文件均不能通过模型校验。

### 12.2 JVM/原生契约测试

- `localStatus` 同时返回 `marian`、`mlkit`、`llm`；
- 缺省 `localDownload` 仍走 ML Kit，新调用通过 `engine:"marian"` 下载 Marian；
- native SentencePiece 编解码覆盖 ASCII、中文、emoji、sentinel、空文本和未知字符；
- encoder/decoder/decoder-with-past 输入名称、维度和 dtype 与模型 manifest 一致；
- EOS、最大长度、中断、空输出、重复输出和异常张量稳定失败；
- 1、10、50 个输出 token 的 JNI `translateBatch` 调用次数均为 1，native ONNX decoder 执行次数按 token 增长；
- 20 条短文本在 padded cost 预算允许时形成一个内部 batch；混合长短文本按 first-fit-decreasing 分组且每批成本不超过 `maxPaddedSourceTokens`；
- 超过 `maxSourceTokens` 的文本只能安全分段或返回 `MARIAN_SOURCE_TOO_LONG`，不能截断或触发超预算分配；
- decoder 第一步之后只执行 decoder-with-past，encoder 每个 micro-batch 恰好执行一次；
- 同一 handle 的两个翻译请求不会并发使用共享工作区；排队取消和 `MARIAN_ENGINE_BUSY` 行为可重复；
- `cancel` 会 terminate 当前 request 的 RunOptions，P95 门限在设备测试中验证，取消后不保留部分 micro-batch 结果；
- NFC、换行、BOM、零宽字符、双向控制字符和 sentinel 的处理顺序固定，新增危险控制字符被拒绝；
- warm-up 成功才报告 `warmupReady=true`，失败稳定返回 `MARIAN_WARMUP_FAILED`；
- Java 生产类不导入或调用 ONNX Runtime Java binding；
- 占位符丢失和 `RenpyTextValidator` 失败进入 `rejected`；
- 模型删除会关闭 native handle，删除后状态变为未安装；
- 并发下载和并发初始化不会创建两套可写模型目录或两个共享 native handle。

### 12.3 UI 契约测试

- 候选构建的新设置默认 ML Kit，三项 PASS 批准后的生产并存构建默认 Marian；旧 `mlkit` 和 `qwen` 偏好始终保持不变；
- Marian/ML Kit/Qwen 三项均可选择；
- Marian 下载、状态、删除和翻译调用包含正确 engine；
- Marian 未下载时不会进入翻译循环，用户确认下载后能够自动重试 pending start；取消或失败不会返回空成功、增加 success count 或进入编译；
- 任务快照固定 `engineId + modelBuildId`；模型更新不改变运行中任务，切换引擎必须显式清空当前活动 translation map；
- 本地供应商不要求 API Key；
- Marian 失败不会自动切换、继续编译或伪造成功数；
- 旧 ML Kit 路线的现有自动化继续通过。

### 12.4 构建测试

- 第三方 checksum 全部通过；
- helper DEX 中 Marian 类恰好一份；
- 最终 APK 中 `libslg_marian.so`、llama 和 ML Kit 要求的 ARM64 `.so` 均存在且无同名冲突；
- `libslg_marian.so` 的 SHA-256、ABI、依赖符号和导出 JNI 符号与 pinned manifest 一致；
- `llvm-readelf` 证明 SONAME、DT_NEEDED allowlist、动态符号和版本依赖合规，不存在动态 protobuf、ONNX Runtime、libc++_shared、GLIBC 或 GLIBCXX 依赖；
- API 24 arm64 环境能够加载 `libslg_marian.so`、打开 Session 并完成一句 smoke 翻译；
- Marian 生产 DEX 不包含 ONNX Runtime Java API 引用；
- manifest、ML Kit 资源和现有 Capacitor bridge 保持有效；
- `zipalign`、APK v2/v3 签名、版本和包名检查通过；
- APK 能在目标 Android 13 设备替换安装且不清除应用数据。

## 13. 质量与性能验收

验收拆成三个互不替代的状态：

- `AUTOMATED_PASS`：CI 可自动执行的模型、运行时、结构、指标和构建门禁；
- `DEVICE_PASS`：批准 Android 设备上的性能、离线、稳定性和完整工作流门禁；
- `QUALITY_PASS`：人工盲评和严重错误审查门禁。

CI 获得 `AUTOMATED_PASS` 后可以生成和分发内部验证 APK，不需要等待人工盲评。Marian 只有同时获得三个 PASS 才能作为生产默认；人工盲评失败或未执行不会把自动测试改写为失败，但发布状态保持“实验/候选”，ML Kit 继续作为默认。

### 13.1 固定语料集

建立三个带来源、许可证、固定 revision 和 SHA-256 的语料集：

1. `local-engine-smoke`：不少于 200 条，覆盖菜单、短对白、长对白、角色名、标点、emoji、Ren'Py 标签、插值、printf 和不可翻译文本；
2. `marian-reference`：不少于 1000 对具有人工中文参考译文的公开英文到中文测试句，用于 SacreBLEU 和 chrF++；
3. `real-game-quality`：从真实 `10251` 条唯一原文中按固定种子分层抽取不少于 500 条，保留文本类型和长度分布，用于 Marian 与 ML Kit 的人工盲评。

不得把当前 ML Kit 输出或 Marian FP32 输出当作 `marian-reference` 的人工参考译文。模型输出只能用于退化和运行时一致性比较。

### 13.2 自动质量门禁

CI 固定计算并保存 SacreBLEU 的 signature、BLEU 和 chrF++，不使用未声明 tokenizer、大小写或归一化参数的裸分数。

自动门限固定为：

- `local-engine-smoke` placeholder/markup 结构通过率为 100%；
- smoke 集没有空译文、残留 sentinel、不可解析输出或未分类异常；
- 上游 Transformers FP32、ONNX FP32 和 ONNX INT8 使用同一固定 generation 配置；
- ONNX FP32 相对 Transformers FP32 在 `marian-reference` 上的 chrF++ 下降不超过 `0.2`，BLEU 下降不超过 `0.1`；
- ONNX INT8 相对 ONNX FP32 的 chrF++ 下降不超过 `1.0`，BLEU 下降不超过 `0.5`；
- Android native INT8 相对离线 ONNX INT8 固定输出的 aggregate chrF++ 至少为 `99.0`，逐句完全一致率至少为 `95%`；
- 任一版本出现数字、占位符、标签或特殊 token 结构损坏时直接失败，不允许由 aggregate 指标抵消；
- `marian-reference` 的绝对 BLEU/chrF++ 作为趋势指标保存，但在没有对该固定语料完成独立校准前，不采用来源不明的单一绝对阈值，例如无条件写死 `chrF >= 55`。

这些门限只证明导出、量化和 Android runtime 没有相对固定上游基线发生不可接受的退化，不证明 Marian 比 ML Kit 更符合游戏文本风格。

### 13.3 人工质量门禁

`real-game-quality` 的 500 条使用隐藏引擎身份、随机左右顺序的盲评，比较 Marian 与当前 ML Kit：

- Marian 的“更好”比例至少比“更差”比例高 10 个百分点；
- 严重错误率不得高于 ML Kit，包括反义、漏掉关键否定、人物/数字错误和明显未翻译；
- 固定术语一致性不得低于 ML Kit；
- 评审记录包含评审人数、分歧处理、样本 SHA-256 和最终统计；
- 未执行时状态为 `QUALITY_NOT_RUN`，不阻断 CI 构建内部验证 APK，但阻断 Marian 成为生产默认和 ML Kit 移除；
- 未通过时状态为 `QUALITY_FAIL`，ML Kit 保持默认，Marian 只能保留为实验选项或停止发布。

### 13.4 设备性能门禁

性能验收在 `PEMM20` 或性能不高于该设备的批准设备上执行：

- 首次 native handle/Session 初始化峰值内存、稳定内存和耗时必须有实测记录；
- 使用 native 计数器或 Perfetto/atrace 证明每个 WebView chunk 只有一次 `translateBatch` JNI 入口；内部 micro-batch 和生成 token 数不得增加 JNI 调用数；
- 分别记录 10、50、100 个输出 token 的 native decoder 时间和 Java 端端到端时间，用差值监控 JNI、字符串封送和调度开销；不使用未经本机测量的固定毫秒估算替代证据；
- decoder-with-past 命中率必须为 100%（第一步除外），encoder 每个 micro-batch 只执行一次；
- 冷启动 warm-up 时间、warm-up 后首个真实 chunk 延迟和取消 P50/P95 必须单独记录；
- 结构化诊断中每个 chunk 都能关联 source/padded/generated token 和各阶段耗时，同时抽查日志不包含原文或译文；
- 200 条 smoke 集翻译过程不得发生 OOM、ANR、WebView 崩溃或进程被系统杀死；
- 设备锁屏/解锁或应用前后台切换后，任务状态和已完成缓存保持一致；
- Marian 的 200 条总耗时不得超过同机 ML Kit 的 4 倍；
- 真实 `10251` 条路线必须在应用允许的长任务边界内完成，不出现持续无进展 5 分钟以上的批次；
- 如果性能门限未通过，记录 `DEVICE_FAIL`，保留 Marian 为实验选项或阻断发布，不通过隐藏降级掩盖失败。

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
- Marian `modelFamilyId`、`modelVersion`、`modelBuildId`、上游 revision、模型包 SHA-256 和 generation 配置；
- 下载完成后的离线状态和断网翻译结果；
- 批次数、唯一原文、总出现、validated、missing、rejected、uncertain 和 compiled；
- 总耗时、峰值内存、失败批次、重试和前后台行为；
- 生成补丁安装结果、中文菜单、真实对白和启动日志；
- 同一版本中 ML Kit 回退 smoke 路线仍然可用。

真实路线达到 `missing=0`、`rejected=0`、`uncertain=0`，且没有选择 incomplete test patch 时，只授予该路线 `DEVICE_PASS`；它证明覆盖率、确定性校验、编译和运行链路完整，不代替人工翻译质量结论。任何缺少设备、模型、网络、存储或真实样本证据的情况保持 `DEVICE_NOT_RUN`、`BLOCKED` 或 `DEVICE_FAIL`，不得推断通过。

发布状态按以下规则合成：

| Automated | Device | Quality | 允许结果 |
| --- | --- | --- | --- |
| PASS | 未执行/失败 | 任意 | 只生成 CI 内部验证产物 |
| PASS | PASS | 未执行 | 可进行候选版/内部设备试用，ML Kit 仍为默认 |
| PASS | PASS | FAIL | Marian 保持实验选项或撤回 |
| PASS | PASS | PASS | Marian 可成为生产默认，仍保留一个发布周期的 ML Kit 回退 |
| FAIL | 任意 | 任意 | 不生成 Marian 候选 APK |

## 15. ML Kit 移除门禁

并存版本发布后，只有同时满足以下条件，才能启动独立的 ML Kit 移除计划：

1. Marian 自动化测试、完整 discover、APK 构建和签名全部通过；
2. `AUTOMATED_PASS`、`DEVICE_PASS` 和 `QUALITY_PASS` 均已取得；
3. 至少一次真实 `10251` 条完整路线通过；
4. 至少一次断网完整 smoke 和前后台恢复通过；
5. Marian 版本发布后没有 P0/P1 模型损坏、崩溃、严重错译或无法下载问题；
6. QA 文档明确记录 Marian PASS 和 ML Kit 回退 PASS；
7. 删除 ML Kit 后预计 APK 体积、manifest、资源、依赖和 native library 差异经过独立审计；
8. 存在可安装的上一版本 APK，能够在不清除应用数据的情况下回滚。

ML Kit 移除必须是单独设计、单独计划和单独发布门禁，不作为本迁移计划的最后一个顺手删除步骤。

## 16. 发布与回滚

### 16.1 通过全部门禁的生产并存版本

- Marian 为新安装和无既有偏好用户的新默认；
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

- `marian` 引擎、模型管理、统一 C++ runtime、单次 JNI 批协议和 UI 路由全部实现；
- ML Kit 与 Qwen 路线没有回归；
- 模型和依赖均有固定版本、许可证和 SHA-256；
- 自动化、完整 discover、APK 构建、签名和安装验证通过；
- `AUTOMATED_PASS`、`DEVICE_PASS` 和 `QUALITY_PASS` 均已取得；
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
