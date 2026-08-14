from __future__ import annotations

import os
import subprocess
import zipfile
from pathlib import Path

from patch_workshop_ui import main as generate_assets

import sys


ROOT = Path(__file__).resolve().parents[2]
APK_WORK = ROOT / "apk-work"
TOOLS = ROOT / ".tools"
BASE_APK = APK_WORK / "com.slgtranslator.app-base.apk"
UNSIGNED_APK = APK_WORK / "slg-workshop-ui-unsigned.apk"
ALIGNED_APK = APK_WORK / "slg-workshop-ui-aligned.apk"
SIGNED_APK = APK_WORK / "slg-workshop-ui-signed.apk"
GENERATED = Path(__file__).parent / "generated"
ICON_RESOURCES = Path(__file__).parent / "icon-res"
FAST_SCAN = APK_WORK / "native-fast-scan"
sys.path.insert(0, str(FAST_SCAN))
from build_fast_scanner import main as generate_fast_scanner_dex  # noqa: E402

FAST_SCAN_GENERATED = FAST_SCAN / "generated"
BUNDLED_CJK_FONT_ENTRY = "assets/slg/fonts/NotoSansSC-Regular.ttf"
BUNDLED_CJK_FONT_SOURCE = FAST_SCAN_GENERATED / BUNDLED_CJK_FONT_ENTRY
ZIPALIGN = TOOLS / "android-15" / "zipalign.exe"
APKSIGNER = TOOLS / "android-15" / "apksigner.bat"
KEYSTORE = Path.home() / ".android" / "debug.keystore"

BASE_REPLACEMENTS = {
    "assets/public/assets/index-CJtfdHOF.js": GENERATED / "index-CJtfdHOF.js",
    "assets/public/assets/index-C044IUg3.css": GENERATED / "index-C044IUg3.css",
    "classes6.dex": FAST_SCAN_GENERATED / "classes6.dex",
    "classes3.dex": FAST_SCAN_GENERATED / "classes3.dex",
    "classes7.dex": FAST_SCAN_GENERATED / "classes7.dex",
    "AndroidManifest.xml": FAST_SCAN_GENERATED / "AndroidManifest.xml",
    BUNDLED_CJK_FONT_ENTRY: BUNDLED_CJK_FONT_SOURCE,
}

ICON_DENSITIES = {
    "mdpi": (48, 108),
    "hdpi": (72, 162),
    "xhdpi": (96, 216),
    "xxhdpi": (144, 324),
    "xxxhdpi": (192, 432),
}

ICON_REPLACEMENTS = {
    f"res/mipmap-{density}/{name}": ICON_RESOURCES / density / name
    for density in ICON_DENSITIES
    for name in (
        "ic_launcher.png",
        "ic_launcher_round.png",
        "ic_launcher_foreground.png",
    )
}

MLKIT_RES_ENTRIES = {
    "resources.arsc": FAST_SCAN_GENERATED / "resources.arsc",
    "res/raw/translate_models_metadata.json": FAST_SCAN_GENERATED / "res" / "raw" / "translate_models_metadata.json",
    "res/xml/rapid_response_client_defaults.xml": FAST_SCAN_GENERATED / "res" / "xml" / "rapid_response_client_defaults.xml",
}

# Native libraries bundled for the on-device translation kernel (llama.cpp
# runtime + ML Kit translate). They are added as new APK entries.
NATIVE_LIB_DIR = FAST_SCAN_GENERATED / "lib" / "arm64-v8a"


def replacement_sources() -> dict[str, Path]:
    """Collect generated entries after the scanner build has materialized them."""
    replacements = dict(BASE_REPLACEMENTS)
    replacements.update(ICON_REPLACEMENTS)
    if all(path.is_file() for path in MLKIT_RES_ENTRIES.values()):
        replacements.update(MLKIT_RES_ENTRIES)
    if NATIVE_LIB_DIR.is_dir():
        for native_lib in sorted(NATIVE_LIB_DIR.glob("*.so")):
            replacements[f"lib/arm64-v8a/{native_lib.name}"] = native_lib
    return replacements


def build_unsigned() -> None:
    generate_assets()
    generate_fast_scanner_dex()
    replacements = replacement_sources()
    replacement_bytes = {
        name: path.read_bytes() for name, path in replacements.items()
    }
    written = set()
    with zipfile.ZipFile(BASE_APK, "r") as source, zipfile.ZipFile(
        UNSIGNED_APK, "w"
    ) as output:
        for item in source.infolist():
            upper = item.filename.upper()
            if upper.startswith("META-INF/") and upper.endswith(
                (".RSA", ".DSA", ".EC", ".SF", ".MF")
            ):
                continue
            data = replacement_bytes.get(item.filename, source.read(item.filename))
            written.add(item.filename)
            info = zipfile.ZipInfo(item.filename, date_time=(2026, 7, 13, 12, 0, 0))
            info.external_attr = item.external_attr
            info.compress_type = (
                zipfile.ZIP_STORED
                if item.filename == "resources.arsc" or item.filename.endswith(".dex")
                else item.compress_type
            )
            output.writestr(info, data)
        for name, data in replacement_bytes.items():
            if name in written:
                continue
            info = zipfile.ZipInfo(name, date_time=(2026, 7, 13, 12, 0, 0))
            info.compress_type = (
                zipfile.ZIP_STORED
                if name.endswith(".dex") or name.endswith(".so")
                else zipfile.ZIP_DEFLATED
            )
            output.writestr(info, data)


def run(command: list[str], env: dict[str, str]) -> None:
    subprocess.run(command, check=True, env=env)


def main() -> None:
    env = os.environ.copy()
    env["JAVA_HOME"] = str(TOOLS / "jdk-17" / "jdk-17.0.19+10")
    build_unsigned()
    for output in (ALIGNED_APK, SIGNED_APK):
        output.unlink(missing_ok=True)
    run([str(ZIPALIGN), "-f", "-p", "4", str(UNSIGNED_APK), str(ALIGNED_APK)], env)
    run(
        [
            str(APKSIGNER),
            "sign",
            "--ks",
            str(KEYSTORE),
            "--ks-key-alias",
            "androiddebugkey",
            "--ks-pass",
            "pass:android",
            "--key-pass",
            "pass:android",
            "--out",
            str(SIGNED_APK),
            str(ALIGNED_APK),
        ],
        env,
    )
    run([str(APKSIGNER), "verify", "--verbose", str(SIGNED_APK)], env)
    print(SIGNED_APK)


if __name__ == "__main__":
    main()
