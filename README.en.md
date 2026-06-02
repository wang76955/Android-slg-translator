# SLG Text Translator - Android

Select a game APK on your Android device, scan Ren'Py and selected Android UI text, translate it with AI, and generate a patched APK. This project is meant for SLG and Ren'Py localization, back-translation, and reusable translation packs.

## What It Does

- `APK picker`: opens game APKs through the system file picker
- `Ren'Py first`: prioritizes visible in-game text, including speaker names, dialogue, and menu choices
- `Optional XML`: can include `res/values/*.xml` and `res/layout/*.xml`
- `Text deduplication`: translates repeated source text once to reduce token usage
- `Local cache`: reuses translations for the same language pair and model
- `Placeholder protection`: preserves formatting tokens such as `{color}`, `[name]`, `%s`, and `${name}`
- `Patched APK output`: builds and signs a patched APK after translation
- `Install flow`: supports the system installer, uninstall-then-install, and launch verification
- `Cache guidance`: if the patched game still shows the old language, the app can jump to the target game's system settings so you can clear cache or data
- `No root required`: works on ordinary Android devices

## Workflow

1. Install the APK and open the app
2. Grant file access permission
3. Select a game APK
4. Choose source language, target language, provider, model, and API key
5. Enable `Translate Android UI XML` only if you need UI strings
6. Tap `Start Translation`
7. Install the patched APK when translation finishes
8. If the game still shows the original language, clear the target app's cache or data and launch it again for verification

## What Gets Translated by Default

- Speaker names and dialogue from Ren'Py `Say` nodes
- Choice text from Ren'Py `Menu` nodes
- Dialogue and menu text from Ren'Py source `.rpy` files
- Android UI text if the XML option is enabled

## What Is Skipped by Default

- Shared engine files under `x-renpy/x-common`
- Binary assets such as images, fonts, and audio
- Paths, variable names, hashes, and debug text
- `AndroidManifest.xml`
- Ordinary JSON / CSV / XML configuration files

## Optional XML Mode

When `Translate Android UI XML` is enabled, the app also includes:

- `res/values/*.xml`
- `res/layout/*.xml`

Still excluded:

- `AndroidManifest.xml`
- non-UI XML configuration files

## When the Patch Does Not Take Effect

Some Ren'Py games keep extracted script cache or app data after the patch is installed, so the game still opens in the original language. This is not normal RAM usage. It is persistent app data or cache.

Recommended order:

1. Use `Uninstall original + install patch`
2. If the original language still appears, tap `Clear old cache/data`
3. Clear storage or cache from the target game's Android settings page
4. Return to the translator and tap `Launch game verification`

Normal Android apps cannot silently clear another app's data, so the app guides you to the system settings page instead.

## Output Location

Translated files are written to:

```text
Android/data/com.slgtranslator.app/files/SLG-Translator-Output/
```

The patched APK is also generated inside the output flow and keeps the original folder structure intact.

## Build

```bash
npm install
npm run build

cd android
./gradlew assembleDebug
```

Debug APK output:

```text
android/app/build/outputs/apk/debug/app-debug.apk
```

## GitHub Release

A signed APK is published on GitHub Releases and can be installed directly:

- [Releases page](https://github.com/wang76955/Android-slg-translator/releases/latest)
- [Current signed APK](https://github.com/wang76955/Android-slg-translator/releases/latest/download/slg-translator-android.apk)

If Android asks for permission to install from unknown sources, allow it first. If an older version is already installed and the upgrade fails, uninstall the old app before installing the patch build.

## Tests

The repository includes focused tests for:

- Ren'Py text filtering
- optional XML filtering
- translation deduplication and compact requests
- placeholder protection and restoration
- Ren'Py patch APK packaging
- translation cache persistence

Run:

```bash
npm test
```

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

## Stack

- React + TypeScript
- Tailwind CSS
- Capacitor
- Kotlin
- OpenAI SDK

## License

MIT
