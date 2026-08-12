#!/usr/bin/env python3
"""Sample Android translation-task memory without changing device state."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


ROOT = Path(__file__).parent
DEFAULT_ADB = ROOT.parents[1] / ".tools" / "platform-tools" / "adb.exe"
PACKAGE = "com.slgtranslator.app"


def adb(serial: str, *args: str) -> str:
    command = [str(DEFAULT_ADB) if DEFAULT_ADB.exists() else "adb"]
    if serial:
        command.extend(["-s", serial])
    command.extend(args)
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "adb failed").strip()
        raise RuntimeError(message or "adb failed")
    return result.stdout


def _value_kb(text: str, label: str) -> int:
    match = re.search(r"^\s*" + re.escape(label) + r"\s*:\s*(-?\d+)\s*(KB|MB|B)?\s*$", text, re.MULTILINE | re.IGNORECASE)
    if not match:
        return 0
    value = int(match.group(1))
    unit = (match.group(2) or "KB").upper()
    if unit == "MB":
        return value * 1024
    if unit == "B":
        return value // 1024
    return value


def _first_int(text: str, pattern: str) -> int:
    match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
    return int(match.group(1)) if match else 0


def _table_row_values(text: str, label: str) -> List[int]:
    match = re.search(
        r"^\s*" + re.escape(label) + r"\s+(-?\d+(?:\s+-?\d+)*)\s*$",
        text,
        re.MULTILINE,
    )
    return [int(value) for value in match.group(1).split()] if match else []


def parse_memory_sample(status_text: str, meminfo_text: str) -> Dict[str, int]:
    native_size = _value_kb(meminfo_text, "Native Heap Size")
    native_alloc = _value_kb(meminfo_text, "Native Heap Alloc")
    native_free = max(0, native_size - native_alloc)
    native_row = _table_row_values(meminfo_text, "Native Heap")
    if len(native_row) >= 8:
        native_size = native_row[5]
        native_alloc = native_row[6]
        native_free = max(0, native_row[7])

    pss = _first_int(meminfo_text, r"^\s*TOTAL PSS:\s*(\d+)\s*kB")
    rss = _first_int(meminfo_text, r"^\s*TOTAL RSS:\s*(\d+)\s*kB")
    swap_pss = _first_int(meminfo_text, r"^\s*TOTAL SWAP PSS:\s*(\d+)\s*kB")
    total_row = _table_row_values(meminfo_text, "TOTAL")
    if len(total_row) >= 5:
        pss = pss or total_row[0]
        swap_pss = swap_pss or total_row[3]
        rss = rss or total_row[4]
    return {
        "vmRssKb": _value_kb(status_text, "VmRSS"),
        "vmHwmKb": _value_kb(status_text, "VmHWM"),
        "pssKb": pss,
        "rssKb": rss,
        "swapPssKb": swap_pss,
        "nativeHeapSizeKb": native_size,
        "nativeHeapAllocKb": native_alloc,
        "nativeHeapFreeKb": native_free,
    }


def _pid_for(serial: str, package: str) -> str:
    output = adb(serial, "shell", "pidof", package).strip()
    pid = output.split()[0] if output else ""
    if not pid.isdigit():
        raise RuntimeError("process_not_found")
    return pid


def sample_once(serial: str, package: str, phase: str) -> Dict[str, object]:
    timestamp = int(time.time() * 1000)
    try:
        pid = _pid_for(serial, package)
        status = adb(serial, "shell", "cat", f"/proc/{pid}/status")
        meminfo = adb(serial, "shell", "dumpsys", "meminfo", package)
        sample = parse_memory_sample(status, meminfo)
        sample.update({
            "pid": int(pid),
            "timestampMs": timestamp,
            "phase": phase,
        })
        return sample
    except Exception as error:
        return {
            "pid": 0,
            "timestampMs": timestamp,
            "phase": phase,
            "error": "process_not_found" if "process_not_found" in str(error) else str(error),
        }


def sample_translation_memory(
    serial: str,
    package: str,
    duration_s: float,
    output_path: Path,
    phase: str = "unknown",
    interval_s: float = 1.0,
) -> Dict[str, object]:
    started = time.time()
    samples: List[Dict[str, object]] = []
    while True:
        samples.append(sample_once(serial, package, phase))
        if time.time() - started >= max(0.0, duration_s):
            break
        time.sleep(max(0.1, interval_s))
    report: Dict[str, object] = {
        "package": package,
        "serial": serial,
        "phase": phase,
        "startedAt": datetime.fromtimestamp(started, timezone.utc).isoformat(),
        "durationSeconds": duration_s,
        "samples": samples,
    }
    write_report(output_path, report)
    return report


def write_report(output_path: Path, report: Dict[str, object]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", default="", help="ADB serial; omit for the default device")
    parser.add_argument("--package", default=PACKAGE)
    parser.add_argument("--duration", type=float, default=60.0)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--phase", default="unknown")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    sample_translation_memory(
        args.serial,
        args.package,
        args.duration,
        args.output,
        phase=args.phase,
        interval_s=args.interval,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
