# SLG 文本翻译 - Android

在 Android 手机上选择游戏 APK，自动扫描可翻译文本，调用 AI 翻译后保存到输出目录。

## 当前策略

- 默认只翻译 Ren'Py 游戏文本
- 默认包含：角色名、对白、菜单选项
- 默认跳过：图片名、变量、路径、调试文本、内部配置文本
- XML 默认不翻译
- 如需翻译 Android 界面文案，可在应用中手动打开 `翻译 Android 界面 XML`

## 功能

- **APK 选择**：使用系统文件选择器选择游戏 APK
- **Ren'Py 优先**：自动解压 RPC2 格式的 `.rpyc` 文件，并优先提取可见游戏文本
- **可选 XML 翻译**：可选翻译 `res/values/*.xml` 和 `res/layout/*.xml` 中的 Android 界面文本
- **AI 翻译**：支持 OpenAI / DeepSeek / 兼容 OpenAI 的 API
- **文本去重**：相同原文只请求一次，减少 token 消耗
- **本地缓存**：相同语言对和模型下的译文会复用
- **占位符保护**：自动保护 Ren'Py / 格式化占位符，如 `{color}`、`[name]`、`%s`、`${name}`
- **批量并发**：按文件并行处理，批量请求翻译
- **输出结构保留**：翻译结果保留 APK 内原始目录结构
- **无需 Root**

## 使用流程

1. 安装 APK 并打开应用
2. 授予文件访问权限
3. 点击 `选择 APK 文件`
4. 应用会扫描并列出当前可翻译文件
5. 如需翻译 Android 界面文字，打开 `翻译 Android 界面 XML`
6. 配置翻译提供商、模型和 API Key
7. 点击 `开始翻译`

## 默认会翻译什么

- Ren'Py `Say` 节点中的角色名和对白
- Ren'Py `Menu` 节点中的选项文本
- Ren'Py 源码 `.rpy` 中的对白和菜单选项

## 默认不会翻译什么

- `x-renpy/x-common` 下的引擎通用脚本
- 图片、字体、音频等二进制资源
- 路径、变量名、哈希、调试文本
- Android `AndroidManifest.xml`
- 普通 JSON / CSV / XML 配置文件

## XML 可选模式

打开 `翻译 Android 界面 XML` 后，会额外包含：

- `res/values/*.xml`
- `res/layout/*.xml`

不会包含：

- `AndroidManifest.xml`
- 非界面用途的 XML 配置

## 输出位置

翻译结果默认保存到：

```text
Android/data/com.slgtranslator.app/files/SLG-Translator-Output/
```

每个文件会生成一个 `.translated` 副本，并保留原有目录结构。

## 构建

```bash
npm install
npm run build

cd android
./gradlew assembleDebug
```

APK 路径：

```text
android/app/build/outputs/apk/debug/app-debug.apk
```

## 技术栈

- React + TypeScript
- Tailwind CSS
- Capacitor
- Kotlin
- OpenAI SDK

## 项目结构

```text
src/
  core/
    apk-entry-filter.ts
    scanner-utils.ts
    translator.ts
    filemanager.ts
  components/
  App.tsx
android/
```

## 验证

当前仓库已补充核心测试，覆盖：

- Ren'Py 文本筛选
- XML 可选过滤
- 翻译去重与紧凑请求
- 占位符保护与恢复

运行：

```bash
npm test
```

## 许可证

MIT
