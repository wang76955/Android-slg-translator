#!/usr/bin/env python3
"""Build the workshop APK with the custom launcher icon set."""
from __future__ import annotations

import os
import zipfile
from pathlib import Path

from fast_reassemble import APK_WORK, APKSIGNER, KEYSTORE, TOOLS, ZIPALIGN, run

DENSITIES = ("mdpi", "hdpi", "xhdpi", "xxhdpi", "xxxhdpi")
ICON_DIR = APK_WORK / "new-icons"
SOURCE = APK_WORK / "slg-workshop-ui-unsigned.apk"
UNSIGNED = APK_WORK / "slg-workshop-ui-icons-unsigned.apk"
ALIGNED = APK_WORK / "slg-workshop-ui-icons-aligned.apk"
SIGNED = APK_WORK / "slg-workshop-ui-icons-signed.apk"


def icon_replacements() -> dict[str, Path]:
    replacements: dict[str, Path] = {}
    for density in DENSITIES:
        replacements[f"res/mipmap-{density}-v4/ic_launcher.png"] = (
            ICON_DIR / f"mipmap-{density}_ic_launcher.png"
        )
        replacements[f"res/mipmap-{density}-v4/ic_launcher_round.png"] = (
            ICON_DIR / f"mipmap-{density}_ic_launcher_round.png"
        )
        replacements[f"res/mipmap-{density}-v4/ic_launcher_foreground.png"] = (
            ICON_DIR / f"fg-{density}_ic_launcher_foreground.png"
        )
    return replacements


def build_unsigned() -> None:
    replacements = icon_replacements()
    replacement_bytes = {name: path.read_bytes() for name, path in replacements.items()}
    written: set[str] = set()
    with zipfile.ZipFile(SOURCE, "r") as source, zipfile.ZipFile(
        UNSIGNED, "w"
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
                if item.filename == "resources.arsc"
                or item.filename.endswith(".dex")
                or item.filename.endswith(".so")
                else item.compress_type
            )
            output.writestr(info, data)
        for name, data in replacement_bytes.items():
            if name in written:
                continue
            info = zipfile.ZipInfo(name, date_time=(2026, 7, 13, 12, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            output.writestr(info, data)


def main() -> None:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"missing unsigned APK: {SOURCE}")
    for path in (UNSIGNED, ALIGNED, SIGNED):
        path.unlink(missing_ok=True)
    env = os.environ.copy()
    env["JAVA_HOME"] = str(TOOLS / "jdk-17" / "jdk-17.0.19+10")
    build_unsigned()
    run([str(ZIPALIGN), "-f", "-p", "4", str(UNSIGNED), str(ALIGNED)], env)
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
            str(SIGNED),
            str(ALIGNED),
        ],
        env,
    )
    run([str(APKSIGNER), "verify", "--verbose", str(SIGNED)], env)
    print(SIGNED)


if __name__ == "__main__":
    main()
