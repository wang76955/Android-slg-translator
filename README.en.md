# Android SLG Translator

Turn any Ren'Py game APK into a Chinese-translated version, right on your phone.

Select a game APK or an installed app, scan its story text, translate with AI, and repackage it into an installable patched APK. No unpacking, no command line, no Ren'Py expertise required.

## Features

- **One-tap translation**: pick an APK or installed app; Ren'Py text (dialogue, choices, phone messages, UI) is detected automatically
- **Complete coverage**: structural extraction plus official-translation cross-checking
- **Independent language entry**: a dedicated "Translated Text" option is injected into the game language menu
- **Resumable tasks**: interrupted translations can resume from local cache without re-calling the API
- **Multiple providers**: OpenAI / DeepSeek / custom endpoints; API keys stay on-device
- **Storage cleanup**: one-tap removal of old patches and temp files
- **Patch management**: generated patched APKs are saved, listed, and installable

## Download

Grab the latest APK from the [Releases](https://github.com/wang76955/Android-slg-translator/releases) page.

## Quick Start

1. Install the APK and open the app
2. Tap "Choose App or APK" and pick an installed app or APK file
3. Wait for the scan, then tap "Start Translation"
4. Once finished, install the generated patched APK
5. In the game language menu, choose "Translated Text" to see the Chinese version

## How It Works

```
Game APK (rpyc/rpymc)
    |  RpycTextExtractor parses pickle structure
    v
Extractable texts (dialogue / choices / messages / UI)
    |  AI translation (OpenAI / DeepSeek / custom)
    v
Translation cache + tl/<lang>/*.rpy
    |  TranslationCompiler builds rpyc
    v
Patched APK (signed + language menu injected)
```

## Repository Layout

```
apk-work/
|-- native-fast-scan/          # Native Java module (compiled to DEX)
|   |-- src/com/slgtranslator/app/
|   |   |-- FastApkScanner.java          # APK scanning
|   |   |-- RpycTextExtractor.java       # Ren'Py pickle text extraction
|   |   |-- TranslationCompiler.java     # rpyc compilation
|   |   |-- LanguageMenuSupport.java     # language menu injection
|   |   |-- PackageInstallerSupport.java # PackageInstaller.Session install
|   |   |-- CleanupSupport.java          # storage cleanup
|   |   |-- SaveTransfer.java            # save transfer
|   |   `-- ...
|   |-- stubs/                 # Android/Capacitor compile stubs
|   `-- build_fast_scanner.py  # build script (apktool + D8)
`-- ui-redesign/
    |-- patch_workshop_ui.py   # WebView UI patch (CSS/JS)
    |-- build_workshop_apk.py  # APK build & signing
    |-- test_*.py              # test suite
    `-- qa/                    # audit & verification tools

docs/
|-- translation-extraction-rules.md  # extraction & filtering rules
`-- superpowers/               # design docs & implementation plans
```

## Building from Source

### Prerequisites

- JDK 17
- Android SDK (aapt2, zipalign, apksigner, d8)
- apktool
- Python 3.10+

### Build

```bash
# 1. Build native module
cd apk-work/native-fast-scan
python build_fast_scanner.py

# 2. Build & sign APK
cd ../ui-redesign
python build_workshop_apk.py
# Output: apk-work/slg-workshop-ui-signed.apk
```

### Tests

```bash
cd apk-work/ui-redesign
python -m pytest test_fast_scanner.py test_workshop_patch.py test_translation_coverage.py
```

## Contributing

Issues and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
