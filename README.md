# SLG 文本翻译 - Android 版

在 Android 手机上浏览游戏目录，自动扫描 JSON 文本文件，调用 AI 翻译后备份原始文件并覆写为目标语言。

## 功能

- **文件管理器式浏览** — 浏览 `/Android/data/` 下的游戏目录，选择目标文件夹
- **自动扫描** — 递归扫描目录中所有 JSON 文件，提取可翻译文本
- **AI 翻译** — 支持 OpenAI / DeepSeek / 任意兼容 API
- **备份覆写** — 翻译前自动备份原始文件 (`.bak`)，完成后覆写原文件
- **免 Root** — 使用 `MANAGE_EXTERNAL_STORAGE` 权限（Android 11+ 需手动授权）

## 截图

| 权限授权 | 文件浏览 | 翻译配置 |
|---------|---------|---------|
| (待补充) | (待补充) | (待补充) |

## 快速开始

### 构建 APK

```bash
# 1. 安装依赖
npm install

# 2. 构建前端
npm run build

# 3. 构建 APK
cd android
./gradlew assembleDebug
```

APK 生成路径：`android/app/build/outputs/apk/debug/app-debug.apk`

### 设备要求

- Android 11+（API 30+）
- 需授予「所有文件访问权限」
- 已 Root 设备可访问 `/data/data/`，不 Root 也可使用 `/Android/data/` 等位置

## 技术栈

| 层 | 技术 |
|------|--------|
| 前端 | React + TypeScript + Tailwind CSS |
| 容器 | Capacitor (WebView) |
| 原生 | Kotlin (自定义文件系统插件) |
| 翻译引擎 | OpenAI SDK (直接 WebView 调用) |

## 项目结构

```
slg-translator-android/
├── src/
│   ├── core/                    # 翻译核心逻辑
│   │   ├── translator.ts        # AI 翻译引擎（复用桌面版）
│   │   ├── types.ts             # 类型定义
│   │   ├── providers.ts         # AI 提供商配置
│   │   ├── scanner-utils.ts     # JSON 文本提取工具
│   │   └── filemanager.ts      # Capacitor 原生插件桥接
│   ├── components/              # React UI 组件
│   │   ├── PermissionGate.tsx   # 权限授权引导
│   │   ├── FileBrowser.tsx      # 文件管理器目录浏览
│   │   ├── ScanResultPanel.tsx  # 扫描结果展示
│   │   ├── TranslationConfig.tsx # 翻译设置面板
│   │   └── ProgressLog.tsx      # 翻译进度日志
│   └── App.tsx                  # 主组件
├── android/
│   └── app/src/main/java/com/slgtranslator/app/
│       ├── MainActivity.kt
│       └── FileManagerPlugin.kt # 自定义文件系统插件
├── package.json
├── vite.config.ts
└── capacitor.config.ts
```

## 与原桌面版的关系

本项目的翻译核心逻辑 (`core/translator.ts`、`core/types.ts`、`core/providers.ts`) 来源于 [SLG 文本翻译工具 (Desktop)](https://github.com/wang76955/slg-translator)。桌面版是 Electron 应用，Android 版是独立的新项目，使用 Capacitor 包装为移动应用。

## License

MIT