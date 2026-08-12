#!/usr/bin/env python3
"""Quick experiment: where does apktool put injected lib/*.so after 'b'?"""
import os
import shutil
import subprocess
import zipfile
from pathlib import Path

JAVA = r"D:\文件翻译\.tools\jdk-17\jdk-17.0.19+10\bin\java.exe"
APKTOOL = r"D:\文件翻译\.tools\apktool\apktool_3.0.2.jar"
BASE = r"D:\文件翻译\apk-work\com.slgtranslator.app-base.apk"
AAR = r"D:\文件翻译\apk-work\native-fast-scan\third-party\llama-android-0.1.1.aar"
EXP = Path(r"C:\codex-apk-build\apktool-exp")

env = os.environ.copy()
env["JAVA_HOME"] = r"D:\文件翻译\.tools\jdk-17\jdk-17.0.19+10"
env["TEMP"] = r"C:\codex-apk-build"
env["TMP"] = r"C:\codex-apk-build"

if EXP.exists():
    shutil.rmtree(EXP)
EXP.mkdir(parents=True)

subprocess.run(
    [JAVA, "-jar", APKTOOL, "d", "-f", "--no-assets", "--all-src", "-o", str(EXP), BASE],
    check=True, env=env, capture_output=True,
)

lib_dir = EXP / "lib" / "arm64-v8a"
lib_dir.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(AAR) as z:
    lib_dir.joinpath("libllama.so").write_bytes(z.read("jni/arm64-v8a/libllama.so"))

subprocess.run(
    [JAVA, "-jar", APKTOOL, "b", "-f", "--no-apk", str(EXP)],
    check=True, env=env, capture_output=True,
)

print("decoded lib files:")
for p in sorted((EXP / "lib").rglob("*")):
    print(" ", p.relative_to(EXP), p.is_file() and p.stat().st_size)

print("build/apk so files:")
for p in sorted((EXP / "build" / "apk").rglob("*.so")):
    print(" ", p.relative_to(EXP / "build" / "apk"), p.stat().st_size)
