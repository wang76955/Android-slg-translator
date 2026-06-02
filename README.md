# SLG 文本翻译器 - Android

在 Android 手机上选择游戏 APK，自动扫描 Ren'Py 和部分 Android UI 文本，调用 AI 翻译后生成带补丁的 APK。这个项目适合给 SLG、Ren'Py 游戏做汉化、回译，或者把游戏文本整理成可复用的翻译包。

## 主要能力

- `APK 选择`：使用系统文件选择器打开游戏 APK
- `Ren'Py 优先`：优先提取可见文本，包括角色名、对白、选项
- `可选 XML`：可手动包含 `res/values/*.xml` 和 `res/layout/*.xml`
- `文本去重`：相同原文只翻译一次，减少 token 消耗
- `本地缓存`：同一语言对和模型下复用历史翻译
- `占位符保护`：保留 `{color}`、`[name]`、`%s`、`${name}` 等格式标记
- `补丁 APK`：翻译完成后生成并签名补丁版 APK
- `安装引导`：支持系统安装器、卸载原版后安装补丁、启动游戏验证
- `缓存提示`：如果补丁装好后仍显示旧语言，可以跳转到游戏系统设置清理缓存或数据
- `无需 Root`：普通 Android 设备即可使用

## 使用流程

1. 安装 APK 并打开应用
2. 授予文件访问权限
3. 选择游戏 APK
4. 选择源语言、目标语言、翻译服务商和模型
5. 如有需要，开启 `翻译 Android UI XML`
6. 点击 `开始翻译`
7. 翻译完成后安装补丁版 APK
8. 如果仍显示原语言，先清理目标游戏的缓存或数据，再启动验证

## 默认会翻译什么

- Ren'Py `Say` 节点里的角色名和对白
- Ren'Py `Menu` 节点里的选项文本
- Ren'Py 源文件 `.rpy` 中的对白和菜单文本
- 启用 XML 选项后，部分 Android UI 文本也会被纳入翻译

## 默认不会翻译什么

- `x-renpy/x-common` 下的引擎通用脚本
- 图片、字体、音频等二进制资源
- 路径、变量名、哈希、调试文本
- `AndroidManifest.xml`
- 普通的 JSON / CSV / XML 配置文件

## Android XML 选项

打开 `翻译 Android UI XML` 后，除了游戏文本，还会额外包含：

- `res/values/*.xml`
- `res/layout/*.xml`

仍然不会包含：

- `AndroidManifest.xml`
- 非界面用途的 XML 配置文件

## 安装后如果没有生效

有些 Ren'Py 游戏在安装补丁版后，还会保留旧的解包缓存或旧数据，导致你进入游戏时还是看到原语言。这不是普通内存占用，而是应用数据或缓存。

推荐处理顺序：

1. 先用 `卸载原版+安装补丁`
2. 如果仍然显示旧语言，点击 `清理旧缓存/数据`
3. 在系统页面清除目标游戏的存储或缓存
4. 返回翻译器，点击 `启动游戏验证`

普通 Android 应用不能静默清理其他应用的数据，所以这里会跳转到系统设置页让你手动确认。

## 输出位置

翻译后的文件默认写入：

```text
Android/data/com.slgtranslator.app/files/SLG-Translator-Output/
```

补丁 APK 会在输出目录中生成并保留原始目录结构。

## 构建

```bash
npm install
npm run build

cd android
./gradlew assembleDebug
```

调试包输出：

```text
android/app/build/outputs/apk/debug/app-debug.apk
```

## 测试

仓库里包含针对以下行为的测试：

- Ren'Py 文本过滤
- 可选 XML 过滤
- 翻译去重与紧凑请求
- 占位符保护与还原
- Ren'Py 补丁 APK 打包
- 翻译缓存持久化

运行：

```bash
npm test
```

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

## 技术栈

- React + TypeScript
- Tailwind CSS
- Capacitor
- Kotlin
- OpenAI SDK

## 许可证

MIT
