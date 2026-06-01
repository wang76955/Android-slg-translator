# SLG 文本翻译 - Android 版

在 Android 手机上选择游戏 APK，自动扫描其中的文本文件，调用 AI 翻译后保存到输出目录。

## 功能

- **APK 选择** — 使用系统文件选择器选择游戏 APK 文件
- **自动扫描** — 扫描 APK 内所有文本文件，自动识别格式（JSON / XML / RPYC / CSV / TXT 等）
- **Ren'Py 支持** — 自动解压 RPC2 格式的 rpyc 文件，提取可翻译文本
- **AI 翻译** — 支持 OpenAI / DeepSeek / 任意兼容 API，可配置模型
- **批量并行翻译** — 多文件并行处理 + 每文件内批量翻译，大幅提升速度
- **自动输出** — 翻译结果自动保存到应用目录，无需手动选择输出位置
- **目录结构保留** — 翻译后的文件保持原 APK 内的目录结构
- **免 Root** — 无需 Root 权限

## 快速开始

### 构建 APK

`ash
# 1. 安装依赖
npm install

# 2. 构建前端
npm run build

# 3. 同步 Capacitor
npx cap sync

# 4. 构建 APK
cd android
./gradlew assembleDebug
`

APK 生成路径：ndroid/app/build/outputs/apk/debug/app-debug.apk

### 使用流程

1. 安装 APK 并打开应用
2. 授权「所有文件访问权限」
3. 点击「选择 APK 文件」选择游戏 APK
4. 应用自动扫描并列出所有文本文件
5. 选择翻译提供商（OpenAI / DeepSeek）和模型
6. 输入 API Key
7. 点击「开始翻译」— 翻译结果自动保存

### 翻译结果位置

翻译后的文件保存在：
`
内部存储/Android/data/com.slgtranslator.app/files/SLG-Translator-Output/
`

每个文件会生成 .translated.扩展名 的副本，保留原始目录结构。

## 支持的格式

| 格式 | 扩展名 | 说明 |
|------|--------|------|
| JSON | .json | 标准 JSON 文本文件 |
| XML | .xml | Android strings.xml 等 |
| Ren'Py RPC2 | .rpyc | Ren'Py 引擎编译脚本（自动解压） |
| CSV | .csv | 逗号分隔值 |
| 纯文本 | .txt | 普通文本文件 |
| YAML | .yaml / .yml | YAML 配置 |
| Properties | .properties | Java 属性文件 |
| Lua | .lua | Lua 脚本 |
| HTML | .html / .htm | HTML 文件 |
| INI | .ini | 配置文件 |

## 设备要求

- Android 11+（API 30+）
- 需授予「所有文件访问权限」（MANAGE_EXTERNAL_STORAGE）
- 无需 Root

## 技术栈

| 层 | 技术 |
|------|--------|
| 前端 | React + TypeScript + Tailwind CSS |
| 容器 | Capacitor (WebView) |
| 原生 | Kotlin (自定义 APK 扫描 / 文件系统插件) |
| 翻译引擎 | OpenAI SDK (WebView 直接调用) |

## 项目结构

`
slg-translator-android/
├── src/
│   ├── core/                    # 翻译核心逻辑
│   │   ├── translator.ts        # AI 翻译引擎（批量并行）
│   │   ├── types.ts             # 类型定义
│   │   ├── providers.ts         # AI 提供商配置
│   │   ├── scanner-utils.ts     # 多格式文本提取工具
│   │   └── filemanager.ts      # Capacitor 原生插件桥接
│   ├── components/              # React UI 组件
│   │   ├── PermissionGate.tsx   # 权限授权引导
│   │   ├── TranslationConfig.tsx # 翻译设置面板
│   │   └── ProgressLog.tsx      # 翻译进度日志
│   └── App.tsx                  # 主组件
├── android/
│   └── app/src/main/java/com/slgtranslator/app/
│       ├── MainActivity.kt
│       └── FileManagerPlugin.kt # 自定义 APK 扫描 + 文件系统插件
├── package.json
└── vite.config.ts
`

## 优化建议

- **翻译速度**：应用会自动并行处理文件，如需调整并发数可修改 src/App.tsx 中的 MAX_CONCURRENT_FILES 和 src/core/translator.ts 中的 MAX_CONCURRENT
- **API 超时**：默认 30 秒超时 + 2 次重试，可在 	ranslator.ts 中调整

## License

MIT
