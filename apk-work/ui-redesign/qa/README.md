# QA / 审计测试工具

这些脚本用于验证 Ren'Py 文本抽取、翻译覆盖率和补丁 APK 内容的正确性。除 `pytest` 测试套件（`../test_*.py`）外，这里提供面向真实游戏 APK 的审计工具。

## 运行前置条件

大多数脚本需要真实游戏 APK 和抽取文本转储作为输入。准备方式：

1. 用翻译器扫描目标游戏 APK（例如 `恶女2.2.apk`），生成 `extracted-texts.txt`（行协议转储）
2. 将游戏 APK 与转储文件放到本目录（脚本默认路径见各脚本头部的 `APK` / `DUMP` 常量，可修改）
3. 安装 `python3`（需要 `zipfile`、`zlib`、`pickletools` 标准库）

## 脚本清单

| 脚本 | 用途 |
|------|------|
| `audit_coverage.py` | 权威翻译覆盖审计：语料（原始 rpyc 抽取文本）对比翻译 old keys，输出 missing 清单；同时统计官方中文内置键覆盖情况 |
| `comprehensive_check.py` | 综合覆盖检查：按文件分类统计抽取文本，找出未被任何翻译键覆盖的原文 |
| `sim_extractor.py` | 独立实现 pickle 抽取逻辑，验证 `RpycTextExtractor` 的结构化抽取行为 |
| `check_sizes.py` | 统计各 rpyc 文件抽取输出大小，用于定位超大文件 / 内存风险 |
| `verify_install.py` | 验证已生成补丁 APK 中 `x-slgtranslated/x-translations.rpyc` 的翻译键数量与标记文本覆盖 |
| `dump_phone_src.py` | 从 pickle 中提取手机短信 / 偏好类函数调用的字符串参数（`send_phone_message`、`_*Preference` 等） |
| `walk_check.py` | 检查 pickle 字符串遍历是否完整（memo 解析、BINGET 解析） |
| `verify_items.py` | 逐条核对菜单选项 / 选择文本是否被抽取 |
| `frag_probes.py` | 探测长文本 / 片段文本在 pickle 中的存储方式 |

## 红绿灯测试

主测试套件：

```bash
cd apk-work/ui-redesign
python3 -m pytest test_fast_scanner.py test_workshop_patch.py test_translation_coverage.py
```

- `test_fast_scanner.py`：抽取器、扫描器、安装支持、存档转移、清单注入等原生桥接测试
- `test_workshop_patch.py`：JS 补丁语法、翻译流水线、网络失败恢复、缓存复用
- `test_translation_coverage.py`：翻译覆盖规则契约
- `test_built_apk.py`：构建产物完整性验证

所有测试应先写失败用例（红），再实现修复（绿），确保回归可控。
