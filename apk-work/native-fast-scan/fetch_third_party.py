#!/usr/bin/env python3
"""Fetch the third-party Android libraries needed by the local translation
kernel and pin them with SHA-256 checksums.

The APK build here is a smali-patching pipeline (javac + d8 + apktool), so
normal Gradle dependency resolution does not exist. This script downloads the
AAR/JAR artifacts and their transitive runtime dependencies into
``third-party/`` so ``build_fast_scanner.py`` can merge the classes into the
helper dex and extract native libraries into the APK.

Resolution rules:
  * Only groups in ``RECURSE_GROUPS`` are followed transitively.
  * ``androidx.*`` and Kotlin stdlib are intentionally NOT downloaded: the
    base APK already ships a modern Capacitor androidx set and kotlinx
    coroutines, and the installed app must keep using those classes.
  * When several versions of one artifact appear, the largest version wins
    (closest-to-root Gradle behaviour approximated by max version).
"""

from __future__ import annotations

import hashlib
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "third-party"
OUT.mkdir(parents=True, exist_ok=True)

GOOGLE = "https://dl.google.com/dl/android/maven2/"
CENTRAL = "https://repo1.maven.org/maven2/"

ROOT_DEPS = [
    ("com.google.mlkit", "translate", "17.0.3"),
    ("com.google.mlkit", "common", "18.11.0"),
    ("com.google.android.datatransport", "transport-api", "2.2.1"),
    ("com.google.android.datatransport", "transport-backend-cct", "2.3.3"),
    ("com.google.android.datatransport", "transport-runtime", "2.2.6"),
    ("com.google.android.gms", "play-services-base", "18.5.0"),
    ("com.google.android.gms", "play-services-basement", "18.4.0"),
    ("com.google.android.gms", "play-services-tasks", "18.2.0"),
    ("com.google.firebase", "firebase-components", "16.1.0"),
    ("com.google.firebase", "firebase-encoders", "16.1.0"),
    ("com.google.firebase", "firebase-encoders-json", "17.1.0"),
    ("com.squareup.okhttp3", "okhttp", "3.0.0"),
    ("com.squareup.okio", "okio", "1.8.0"),
    ("org.jetbrains.kotlin", "kotlin-stdlib", "2.0.21"),
    ("androidx.lifecycle", "lifecycle-common", "2.0.0"),
    ("dev.ffmpegkit-maintained", "llama-android", "0.1.1"),
]

# Group prefixes whose POMs are followed transitively.
RECURSE_GROUPS = (
    "com.google.mlkit",
    "com.google.android.gms",
    "com.google.android.datatransport",
    "com.google.firebase",
    "com.squareup.okhttp3",
    "com.squareup.okio",
    "javax.inject",
)

_NS = {"m": "http://maven.apache.org/POM/4.0.0"}


def group_path(group: str) -> str:
    return group.replace(".", "/")


def artifact_url(group: str, artifact: str, version: str, packaging: str, repo: str) -> str:
    return (
        repo
        + group_path(group)
        + "/"
        + artifact
        + "/"
        + version
        + "/"
        + artifact
        + "-"
        + version
        + "."
        + packaging
    )


def fetch(url: str, destination: Path) -> None:
    if destination.exists() and destination.stat().st_size > 0:
        return
    tmp = destination.with_suffix(destination.suffix + ".part")
    print(f"  downloading {url}")
    request = urllib.request.Request(url, headers={"User-Agent": "slg-translator-build"})
    with urllib.request.urlopen(request, timeout=180) as response, open(tmp, "wb") as out:
        while True:
            chunk = response.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
    tmp.replace(destination)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(1 << 20)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def expand_properties(root: ET.Element, text: str | None) -> str:
    if not text:
        return ""
    props = {
        prop.get("name"): prop.text or ""
        for prop in root.findall("m:properties/m:*", _NS)
    }
    pattern = re.compile(r"\$\{([^}]+)\}")
    for _ in range(4):
        replaced = pattern.sub(lambda m: props.get(m.group(1), m.group(0)), text)
        if replaced == text:
            break
        text = replaced
    return text


def version_key(version: str):
    parts = re.split(r"[-.]", version)
    return [int(part) if part.isdigit() else part for part in parts]


def walk_pom(group: str, artifact: str, version: str,
             found: dict[tuple[str, str], tuple[str, str]], seen: set[tuple]) -> None:
    """Collect (group, artifact) -> (version, packaging) with max-version wins."""
    key = (group, artifact, version)
    if key in seen:
        return
    seen.add(key)
    packaging = "aar" if group != "javax.inject" and artifact not in (
        "firebase-encoders", "firebase-annotations", "okhttp", "okio"
    ) else "jar"
    if artifact == "kotlin-stdlib" or artifact == "lifecycle-common":
        packaging = "jar"
    current = found.get((group, artifact))
    if current is None or version_key(version) > version_key(current[0]):
        found[(group, artifact)] = (version, packaging)

    pom_path = OUT / f"{artifact}-{version}.pom"
    if not pom_path.exists():
        try:
            fetch(artifact_url(group, artifact, version, "pom", GOOGLE), pom_path)
        except Exception:
            fetch(artifact_url(group, artifact, version, "pom", CENTRAL), pom_path)
    try:
        root = ET.parse(pom_path).getroot()
    except ET.ParseError:
        pom_path.unlink(missing_ok=True)
        try:
            fetch(artifact_url(group, artifact, version, "pom", CENTRAL), pom_path)
        except Exception:
            return
        root = ET.parse(pom_path).getroot()

    for dep in root.findall("m:dependencies/m:dependency", _NS):
        dep_group = dep.findtext("m:groupId", default="", namespaces=_NS)
        dep_artifact = dep.findtext("m:artifactId", default="", namespaces=_NS)
        dep_scope = dep.findtext("m:scope", default="compile", namespaces=_NS)
        dep_optional = dep.findtext("m:optional", default="false", namespaces=_NS)
        dep_version_raw = dep.findtext("m:version", default="", namespaces=_NS)
        dep_version = expand_properties(root, dep_version_raw)
        dep_type = dep.findtext("m:type", default="jar", namespaces=_NS)
        if (
            not dep_group
            or not dep_artifact
            or not dep_version
            or "[" in dep_version
            or dep_scope in ("test", "provided")
            or dep_optional == "true"
            or not dep_group.startswith(RECURSE_GROUPS)
        ):
            continue
        if dep_type not in ("aar", "jar"):
            continue
        walk_pom(dep_group, dep_artifact, dep_version, found, seen)


def write_pins() -> None:
    pins: list[tuple[str, str, str]] = []
    for path in sorted(OUT.iterdir()):
        if path.suffix in (".aar", ".jar", ".pom"):
            pins.append((path.name, sha256_of(path), str(path.stat().st_size)))
    pin_path = OUT / "SHA256SUMS.txt"
    with open(pin_path, "w", encoding="utf-8") as handle:
        for name, digest, size in pins:
            handle.write(f"{digest}  {size}  {name}\n")
    print(f"pinned {len(pins)} files -> {pin_path}")


def verify_pins() -> bool:
    pin_path = OUT / "SHA256SUMS.txt"
    if not pin_path.exists():
        return False
    ok = True
    for line in pin_path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) != 3:
            continue
        digest, _, name = parts
        path = OUT / name
        if not path.exists() or sha256_of(path) != digest:
            print(f"  CHECKSUM MISMATCH: {name}")
            ok = False
    return ok


def main() -> None:
    print("Resolving third-party translation dependencies...")
    found: dict[tuple[str, str], tuple[str, str]] = {}
    seen: set[tuple] = set()
    for dep in ROOT_DEPS:
        walk_pom(*dep, found, seen)

    print(f"Downloading {len(found)} artifacts...")
    for (group, artifact), (version, packaging) in sorted(found.items()):
        dest = OUT / f"{artifact}-{version}.{packaging}"
        if not dest.exists():
            try:
                fetch(artifact_url(group, artifact, version, packaging, GOOGLE), dest)
            except Exception:
                fetch(artifact_url(group, artifact, version, packaging, CENTRAL), dest)

    if verify_pins():
        print("All pinned files verified.")
    else:
        write_pins()
    print("Done.")


if __name__ == "__main__":
    sys.exit(main())
