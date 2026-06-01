# SLG Text Translator - Android

Select a game APK on your Android phone, automatically scan text files inside, translate via AI, and save the results to an output directory.

## Features

- **APK Selection** - Pick a game APK using the system file picker
- **Auto Scanning** - Scans all text files inside the APK, auto-detecting formats (JSON / XML / RPYC / CSV / TXT / etc.)
- **Ren'Py Support** - Automatically decompresses RPC2 format rpyc files and extracts translatable text
- **AI Translation** - Supports OpenAI / DeepSeek / any compatible API with configurable models
- **Parallel Batch Translation** - 3 files in parallel + 5 concurrent requests per file, up to 15 concurrent API calls
- **Text Deduplication** - Automatically deduplicates identical text to reduce API calls
- **Auto Output** - Translation results are automatically saved, no manual output directory selection needed
- **Directory Structure Preserved** - Translated files maintain the original APK directory structure
- **No Root Required** - Works without root access

## Quick Start

### Build APK

```bash
# 1. Install dependencies
npm install

# 2. Build frontend
npm run build

# 3. Sync Capacitor
npx cap sync

# 4. Build APK
cd android
./gradlew assembleDebug
```

APK output: `android/app/build/outputs/apk/debug/app-debug.apk`

### Usage

1. Install the APK and open the app
2. Grant "All Files Access" permission
3. Tap "Select APK File" to pick a game APK
4. The app automatically scans and lists all text files
5. Choose a translation provider (OpenAI / DeepSeek) and model
6. Enter your API Key
7. Tap "Start Translation" - results are saved automatically

### Translation Output Location

Translated files are saved to:

```
Internal Storage/Android/data/com.slgtranslator.app/files/SLG-Translator-Output/
```

Each file generates a `.translated.extension` copy, preserving the original directory structure.

## Supported Formats

| Format | Extension | Description |
|--------|-----------|-------------|
| JSON | .json | Standard JSON text files |
| XML | .xml | Android strings.xml, etc. |
| Ren'Py RPC2 | .rpyc | Ren'Py compiled scripts (auto-decompressed) |
| CSV | .csv | Comma-separated values |
| Plain Text | .txt | Regular text files |
| YAML | .yaml / .yml | YAML configuration |
| Properties | .properties | Java properties files |
| Lua | .lua | Lua scripts |
| HTML | .html / .htm | HTML files |
| INI | .ini | Configuration files |

## Requirements

- Android 11+ (API 30+)
- "All Files Access" permission (`MANAGE_EXTERNAL_STORAGE`) required
- No root required

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React + TypeScript + Tailwind CSS |
| Container | Capacitor (WebView) |
| Native | Kotlin (custom APK scanning / file system plugin) |
| Translation Engine | OpenAI SDK (direct WebView invocation) |

## Project Structure

```
slg-translator-android/
├── src/
│   ├── core/                    # Core translation logic
│   │   ├── translator.ts        # AI translation engine (parallel batches)
│   │   ├── types.ts             # Type definitions
│   │   ├── providers.ts         # AI provider configuration
│   │   ├── scanner-utils.ts     # Multi-format text extraction utilities
│   │   └── filemanager.ts      # Capacitor native plugin bridge
│   ├── components/              # React UI components
│   │   ├── PermissionGate.tsx   # Permission grant guide
│   │   ├── TranslationConfig.tsx # Translation settings panel
│   │   └── ProgressLog.tsx      # Translation progress log
│   └── App.tsx                  # Main component
├── android/
│   └── app/src/main/java/com/slgtranslator/app/
│       ├── MainActivity.kt
│       └── FileManagerPlugin.kt # Custom APK scanning + file system plugin
├── package.json
└── vite.config.ts
```

## Performance Tuning

- **Translation Speed**: Files are processed in parallel (3 concurrent). Adjust the concurrency in `src/App.tsx`
- **API Concurrency**: 5 concurrent requests per file. Adjust `MAX_CONCURRENT` in `src/core/translator.ts`
- **API Timeout**: Default 30s timeout + 2 retries. Configure in `translator.ts`

## License

MIT