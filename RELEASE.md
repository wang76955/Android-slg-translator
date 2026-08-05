# Release 规范

从 v1.0.5 起，每个版本按以下流程发布，保证下载直链稳定、用户可校验、反馈可追溯。

## 发布前检查清单

1. **CHANGELOG**：在 `CHANGELOG.md` 顶部新增版本条目，记录 Added / Changed / Fixed
2. **版本号**：`android/app/build.gradle` 的 `versionCode` 递增、`versionName` 与标签一致；`src/App.tsx` 顶部 `APP_VERSION` 同步更新
3. **构建与测试**：`npm test` 全绿；`npm run build` 成功；`cd android && ./gradlew assembleRelease` 生成签名 APK
4. **APK 资产命名**：统一为 `slg-translator-android-vX.Y.Z.apk`，保持 `releases/latest/download/` 直链可预期
5. **SHA256**：对发布的 APK 计算校验值并写入 Release 正文。PowerShell 命令：`Get-FileHash <apk> -Algorithm SHA256`
6. **最低 Android 版本**：在 Release 正文写明（当前为 Android 7.0 / API 24，见 `android/variables.gradle` 的 `minSdkVersion`）
7. **Release 正文**：包含本版 CHANGELOG 摘要、SHA256、最低 Android 版本、APK 下载链接
8. **官网同步**：更新 `slg-translator-site/app/page.tsx` 下载卡片的版本号与日期，然后重新部署
9. **通知**：发布 GitHub Release 后，在 QQ 交流群发公告

## Release 正文模板

```markdown
## Android vX.Y.Z（YYYY-MM-DD）

### 新增 / 优化 / 修复
- ...

### 校验信息
- APK：slg-translator-android-vX.Y.Z.apk
- SHA256：`...`
- 最低 Android 版本：Android 7.0（API 24）
- 更新记录：https://github.com/wang76955/Android-slg-translator/blob/main/CHANGELOG.md
```
