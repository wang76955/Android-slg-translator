# SLG 翻译器（Android SLG Translator）

把复杂的 Ren'Py 游戏 APK 汉化流程，变成普通玩家也能一次完成的手机向导。

选择游戏 APK 或已安装应用 → 自动扫描剧情文本 → 通过 AI 翻译成中文 → 重新打包为可安装的补丁 APK。全程不需要解包、不需要命令行、不需要理解 Ren'Py 结构。

## 功能特性

- **一键汉化**：选择 APK / 已安装应用，自动识别 Ren'Py 文本（对话、选项、手机短信、UI 文本）
- **完整覆盖**：结构化抽取 + 官方翻译对照，保证对话不漏译、不错序
- **独立翻译入口**：给游戏注入独立的「翻译文本」语言选项，原版语言不受影响
- **可恢复任务**：翻译中断可继续，进度缓存到本机，不重复调用 API
- **多供应商支持**：OpenAI / DeepSeek / 自定义接口，API Key 仅保存在本机
- **存储清理**：一键清理旧游戏补丁与临时文件，释放手机空间
- **补丁管理**：生成的补丁 APK 统一管理，可保存到下载、直接安装

## 下载

从 [Releases](https://github.com/wang76955/Android-slg-translator/releases) 下载最新 APK 安装到 Android 手机。

> 注意：使用前需要在「我的 → 翻译服务」中配置 API Key（OpenAI / DeepSeek / 自定义接口均可）。

## 快速开始

1. 安装 APK，打开应用
2. 点「选择应用或 APK」→ 从已安装应用选择，或选择 APK 文件
3. 等待扫描完成，点「开始翻译」
4. 翻译完成后生成补丁 APK，安装即可
5. 在游戏设置的语言菜单中，选择「翻译文本」查看中文译文

## 工作原理

```
游戏 APK (rpyc/rpymc)
    │  RpycTextExtractor 结构化解析 pickle
    ▼
可翻译文本（对话 / 选项 / 短信 / UI）
    │  AI 翻译（OpenAI / DeepSeek / 自定义）
    ▼
翻译缓存 + tl/<lang>/*.rpy
    │  TranslationCompiler 编译为 rpyc
    ▼
补丁 APK（签名 + 注入翻译语言菜单）
```

核心流程：

1. **扫描**：解析 APK 内 Ren'Py 编译脚本（rpyc/rpymc），结构化抽取用户可见文本
2. **翻译**：文本分批调用 AI 接口，本地缓存 + 官方翻译对照避免重复调用
3. **编译**：将翻译结果编译成 Ren'Py 翻译资源（rpyc），写入补丁 APK
4. **注入**：在游戏语言菜单中注入独立的「翻译文本」入口
5. **安装**：通过 PackageInstaller.Session 直接安装多 GB 补丁 APK

## 项目结构

```
apk-work/
├── native-fast-scan/          # 原生 Java 模块（编译为 DEX 注入应用）
│   ├── src/com/slgtranslator/app/
│   │   ├── FastApkScanner.java        # APK 扫描与文件枚举
│   │   ├── RpycTextExtractor.java     # Ren'Py pickle 文本抽取
│   │   ├── TranslationCompiler.java   # 翻译资源编译为 rpyc
│   │   ├── LanguageMenuSupport.java   # 语言菜单注入
│   │   ├── PackageInstallerSupport.java # PackageInstaller.Session 安装
│   │   ├── CleanupSupport.java        # 存储清理
│   │   ├── SaveTransfer.java          # 存档转移
│   │   └── ...
│   ├── stubs/                 # Android/Capacitor 编译桩
│   └── build_fast_scanner.py  # 构建脚本（apktool + D8）
└── ui-redesign/
    ├── patch_workshop_ui.py   # WebView UI 补丁（CSS/JS 注入）
    ├── build_workshop_apk.py  # APK 构建与签名
    ├── test_*.py              # 红绿灯测试套件
    └── qa/                    # 审计与验证工具

docs/
├── translation-extraction-rules.md  # 文本抽取与过滤规则（经验总结）
└── superpowers/               # 设计文档与实施计划
```

## 从源码构建

### 前置依赖

- JDK 17
- Android SDK（aapt2、zipalign、apksigner、d8）
- apktool
- Python 3.10+

### 构建步骤

```bash
# 1. 构建原生模块
cd apk-work/native-fast-scan
python build_fast_scanner.py

# 2. 构建并签名 APK
cd ../ui-redesign
python build_workshop_apk.py
# 输出: apk-work/slg-workshop-ui-signed.apk
```

### 运行测试

```bash
cd apk-work/ui-redesign
python -m pytest test_fast_scanner.py test_workshop_patch.py test_translation_coverage.py
```

所有测试采用红绿灯模式（先写失败用例，再实现修复），确保回归可控。

## 文档

- [翻译抽取规则](docs/translation-extraction-rules.md)：Ren'Py 文本抽取与过滤的完整经验总结
- [QA 工具说明](apk-work/ui-redesign/qa/README.md)：翻译覆盖审计工具用法
- [设计文档](docs/superpowers/)：功能设计规格与实施计划

## 贡献

欢迎提交 Issue 和 Pull Request。请阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 了解开发流程。

## 许可证

[MIT](LICENSE)
