# Ren'Py 兼容性优化基线

> 冻结日期：2026-08-07（Asia/Shanghai）

## 测试命令

从 `D:\文件翻译\apk-work\ui-redesign` 运行：

```powershell
python -m unittest test_fast_scanner.py test_translation_quality.py test_translation_coverage.py test_engine_performance.py -v
```

结果：

- 运行：56 项
- 通过：55 项
- 失败：0 项
- 跳过：1 项
- 跳过项：`test_audit_pins_the_verified_missing_set`，因为工作区没有真实完整 Ren'Py 游戏 APK/对应完整提取语料；该跳过不代表真实游戏的 `missing == 0` 已验证。

在第一次基线运行中，生成 DEX 契约测试因旧的 `apk-work/native-fast-scan/generated/classes6.dex` 缺少当前源码已有的 `listSaveGameApps` bridge 而失败。重新运行现有的 `build_fast_scanner.py` 刷新生成产物后，单测和完整核心套件均通过；本次没有为该问题修改业务源码。

## 工具环境

- Python：`Python 3.14.5`
- Java：系统 PATH 未提供 `java`/`javac`；项目捆绑 JDK 为 Temurin `17.0.19+10`，构建脚本使用该 JDK。
- Android build tools：工作区 `.tools/android-15`，包含 `aapt2`、`d8`、`dexdump`、`apksigner` 和 `zipalign`。

## GitHub APK 来源

为满足真实 APK 来源要求，直接从 GitHub 固定提交下载：

- 仓库：[wang76955/slg-translator](https://github.com/wang76955/slg-translator)
- 提交：`fc2e3f39f85a09799e63fa652e566e3850ff9f31`
- APK URL：`https://raw.githubusercontent.com/wang76955/slg-translator/fc2e3f39f85a09799e63fa652e566e3850ff9f31/android-release/slg-translator-android-rpyc-v12.apk`
- Git blob SHA：`86e4d6fce5a04cfc057abbb2caf5c8a911e21ae6`
- 本地路径：`apk-work/github-source/slg-translator-android-rpyc-v12.apk`
- 文件大小：`4,302,216` bytes
- SHA-256：`44470607C402F6E8BBBDD5CED24B3AFF9016C92CE504BA2F2C3CE77DB1567104`
- APK 元数据：包名 `com.slgtranslator.app`，`versionCode=2`，`versionName=1.0.1`，`minSdkVersion=24`，`targetSdkVersion=36`。

同一 GitHub 目录的 `README.md` 和 `patch_rpyc_dialogue.py` 已保存到 `apk-work/github-source/`，用于来源说明和后续 APK 行为比对。

## 当前生成产物指纹

以下产物由现有 `apk-work/native-fast-scan/build_fast_scanner.py` 刷新，尚未把生成的 APK 当作翻译成功证明：

| 文件 | 大小 | SHA-256 |
|---|---:|---|
| `apk-work/native-fast-scan/generated/classes6.dex` | 94,084 | `F991F783DB6072A708B46314D79C40606F75657A128240C5B9942830497CA981` |
| `apk-work/native-fast-scan/generated/classes7.dex` | 1,950,384 | `19A37FC61A5AEA5C289CCD70FAFB4E7AD6B015253DF849A1D36AC47E16D3FD98` |
| `apk-work/native-fast-scan/generated/AndroidManifest.xml` | 8,776 | `62442302BA758780254D181ADD7D0425582965B08EAD3AA830854E33E49FEB83` |

## 工作树边界

基线检查只读取了 `git status --short --branch`，没有清理、重置或广泛暂存。当前仓库仍是无提交历史的 `master`，并包含已有的大量 staged/untracked 用户文件；批次 A 后续只能按任务列出的精确路径操作，禁止 `git add .`、`git reset --hard` 和批量清理。

## 基线限制

本报告证明的是现有 Python 契约测试、Java/D8 构建链路和 GitHub 获取的翻译工具 APK 可复现；它不证明任何第三方 Ren'Py 游戏的语言激活、RPYC 可加载性、字体覆盖、完整翻译覆盖率或真机启动结果。批次 A 必须继续通过独立的激活、模板、能力、产物验证和资源预算测试后，才能把这些能力标记为已实现。

## 批次 A 回归结果（2026-08-07）

在完成 Task 1–5 后，重新运行同一套命令：

```powershell
python -m unittest test_fast_scanner.py test_translation_quality.py test_translation_coverage.py test_engine_performance.py -v
```

结果为 `62` 项运行、`0` 失败、`1` 跳过；新增的 RPYC 激活模式、模板优先级、能力分级、编译产物验证和资源预算测试均通过。跳过项仍为没有真实完整 Ren'Py 游戏 APK/完整语料的覆盖率审计，因此没有把真实游戏覆盖率标记为已证明。

另外单独运行：

```powershell
python -m unittest test_fast_scanner.py -v
```

结果为 `45/45` 通过。`python build_fast_scanner.py` 也重新完成，当前原生生成物指纹为：

| 文件 | 大小 | SHA-256 |
|---|---:|---|
| `apk-work/native-fast-scan/generated/classes6.dex` | 94,084 | `F991F783DB6072A708B46314D79C40606F75657A128240C5B9942830497CA981` |
| `apk-work/native-fast-scan/generated/classes7.dex` | 1,970,820 | `D385E0B35743A79A51F7882666DD25ADD068E96D01FD5C89B69BA7C2807A5981` |
| `apk-work/native-fast-scan/generated/AndroidManifest.xml` | 8,776 | `62442302BA758780254D181ADD7D0425582965B08EAD3AA830854E33E49FEB83` |
