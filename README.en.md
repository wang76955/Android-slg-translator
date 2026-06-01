# SLG Text Translator - Android

Select a game APK on your Android phone, scan translatable text, send it to an AI model, and save the translated output to a local directory.

## Current Strategy

- Ren'Py text is translated by default
- Included by default: speaker names, dialogue lines, and menu choices
- Excluded by default: image names, variables, paths, debug text, and internal config text
- XML is off by default
- Android UI XML can be enabled manually with the `Translate Android UI XML` toggle

## Features

- **APK picker**: choose a game APK with the system file picker
- **Ren'Py-first extraction**: decompresses `.rpyc` RPC2 files and focuses on visible game text
- **Optional XML translation**: can include Android UI strings from `res/values/*.xml` and `res/layout/*.xml`
- **AI translation**: supports OpenAI, DeepSeek, and OpenAI-compatible APIs
- **Deduplication**: identical source text is translated once
- **Local cache**: reuses translations for the same language pair and model
- **Placeholder protection**: preserves Ren'Py and formatting tokens such as `{color}`, `[name]`, `%s`, and `${name}`
- **Batch concurrency**: processes files in parallel with compact batch requests
- **Directory preservation**: keeps the original APK folder structure
- **No root required**

## App Flow

1. Install the APK and open the app
2. Grant file access permission
3. Tap `Select APK File`
4. The app scans and lists currently translatable files
5. If needed, enable `Translate Android UI XML`
6. Configure provider, model, and API key
7. Tap `Start Translation`

## What Gets Translated by Default

- Speaker names and dialogue from Ren'Py `Say` nodes
- Choice text from Ren'Py `Menu` nodes
- Dialogue and menu choices from Ren'Py source `.rpy` files

## What Is Skipped by Default

- Shared engine files under `x-renpy/x-common`
- Binary assets such as images, fonts, and audio
- Paths, variable names, hashes, and debug strings
- Android `AndroidManifest.xml`
- Regular JSON / CSV / XML config files

## Optional XML Mode

When `Translate Android UI XML` is enabled, the app also includes:

- `res/values/*.xml`
- `res/layout/*.xml`

Still excluded:

- `AndroidManifest.xml`
- non-UI XML configuration files

## Output Location

Translated files are written to:

```text
Android/data/com.slgtranslator.app/files/SLG-Translator-Output/
```

Each file generates a `.translated` copy while keeping the original directory layout.

## Build

```bash
npm install
npm run build

cd android
./gradlew assembleDebug
```

APK output:

```text
android/app/build/outputs/apk/debug/app-debug.apk
```

## Stack

- React + TypeScript
- Tailwind CSS
- Capacitor
- Kotlin
- OpenAI SDK

## Project Layout

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

## Verification

The repo now includes focused tests for:

- Ren'Py text filtering
- optional XML filtering
- translation deduplication and compact payloads
- placeholder protection and restoration

Run:

```bash
npm test
```

## License

MIT
