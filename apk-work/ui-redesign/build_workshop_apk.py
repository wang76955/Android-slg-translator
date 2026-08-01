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
FAST_SCAN = APK_WORK / "native-fast-scan"
sys.path.insert(0, str(FAST_SCAN))
from build_fast_scanner import main as generate_fast_scanner_dex  # noqa: E402

FAST_SCAN_GENERATED = FAST_SCAN / "generated"
ZIPALIGN = TOOLS / "android-15" / "zipalign.exe"
APKSIGNER = TOOLS / "android-15" / "apksigner.bat"
KEYSTORE = Path.home() / ".android" / "debug.keystore"

REPLACEMENTS = {
    "assets/public/assets/index-CJtfdHOF.js": GENERATED / "index-CJtfdHOF.js",
    "assets/public/assets/index-C044IUg3.css": GENERATED / "index-C044IUg3.css",
    "classes6.dex": FAST_SCAN_GENERATED / "classes6.dex",
    "classes3.dex": FAST_SCAN_GENERATED / "classes3.dex",
    "classes7.dex": FAST_SCAN_GENERATED / "classes7.dex",
    "AndroidManifest.xml": FAST_SCAN_GENERATED / "AndroidManifest.xml",
}


def build_unsigned() -> None:
    generate_assets()
    generate_fast_scanner_dex()
    replacement_bytes = {
        name: path.read_bytes() for name, path in REPLACEMENTS.items()
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
            info.compress_type = zipfile.ZIP_STORED if name.endswith(".dex") else zipfile.ZIP_DEFLATED
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
