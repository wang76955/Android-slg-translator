# Known Issues

## Android cache and data cleanup after patch install

### Summary

After installing a patched game APK, the translated scripts may not appear immediately if the original Ren'Py game data or extracted script cache is still present on the device.

This is not regular RAM usage. It is persistent app data/cache created by Android and Ren'Py.

### Current behavior

- The translator can build and sign a patched APK.
- The translator can open Android's system installer.
- The translator can open the target game's system app settings page.
- The user still needs to confirm install, uninstall, or clear data/cache in Android system screens.

### Why it cannot be fully automatic

Normal Android apps cannot silently clear another app's data or cache. Android only allows this with elevated privileges such as:

- root access
- ADB shell commands granted by the user
- system app privileges
- enterprise/device-owner management APIs

The translator is designed to work without root, so it uses the safest available flow: guide the user to the relevant system screen.

### Recommended user flow

1. Generate the patched APK.
2. Tap `Uninstall original + install patch` when replacing an already installed game.
3. Confirm the Android uninstall and install dialogs.
4. If the game still shows the old language, tap `Clear old cache/data`.
5. In the target game's Android app settings, clear storage or cache.
6. Return to the translator and tap `Launch game verification`.

### Future options

- Add an ADB-assisted desktop helper for users who explicitly enable USB debugging.
- Add clearer in-app status text for games that are likely to need Ren'Py cache cleanup.
- Add a troubleshooting checklist after patch installation.
