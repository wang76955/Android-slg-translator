import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).parent
MODULE_PATH = ROOT / "measure_translation_memory.py"


def load_module():
    spec = importlib.util.spec_from_file_location("measure_translation_memory", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TranslationMemoryTest(unittest.TestCase):
    def test_parse_proc_status_and_meminfo_extracts_peak_fields(self):
        module = load_module()
        status = "VmRSS: 249136 kB\nVmHWM: 444844 kB\n"
        meminfo = (
            "Native Heap Size: 206848 kB\n"
            "Native Heap Alloc: 90204 kB\n"
        )
        result = module.parse_memory_sample(status, meminfo)
        self.assertEqual(result["vmRssKb"], 249136)
        self.assertEqual(result["vmHwmKb"], 444844)
        self.assertEqual(result["nativeHeapSizeKb"], 206848)
        self.assertEqual(result["nativeHeapAllocKb"], 90204)
        self.assertEqual(result["nativeHeapFreeKb"], 116644)

    def test_parse_table_meminfo_extracts_android13_native_heap_and_total_fields(self):
        module = load_module()
        status = "VmRSS: 398380 kB\nVmHWM: 444844 kB\n"
        meminfo = (
            "  Native Heap    78953    77752     1160    19400    80136   135168    93563    41604\n"
            "  Dalvik Heap    10508     5268     4960       33    12268    11595     5451     6144\n"
            "        TOTAL   317715   141956   129368    26086   399736   146763    99014    47748\n"
            "           TOTAL PSS:   317715            TOTAL RSS:   399736       TOTAL SWAP PSS:    26086\n"
        )
        result = module.parse_memory_sample(status, meminfo)
        self.assertEqual(result["pssKb"], 317715)
        self.assertEqual(result["rssKb"], 399736)
        self.assertEqual(result["swapPssKb"], 26086)
        self.assertEqual(result["nativeHeapSizeKb"], 135168)
        self.assertEqual(result["nativeHeapAllocKb"], 93563)
        self.assertEqual(result["nativeHeapFreeKb"], 41604)

    def test_parse_memory_sample_uses_zero_for_missing_optional_fields(self):
        module = load_module()
        result = module.parse_memory_sample("VmRSS: 8 kB\n", "")
        self.assertEqual(result["vmRssKb"], 8)
        self.assertEqual(result["vmHwmKb"], 0)
        self.assertEqual(result["nativeHeapFreeKb"], 0)

    def test_write_report_creates_json_with_samples(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "memory.json"
            report = {"package": "com.slgtranslator.app", "samples": [{"phase": "scan"}]}
            module.write_report(output, report)
            self.assertEqual(json.loads(output.read_text("utf-8")), report)

    def test_sample_once_records_process_not_found(self):
        module = load_module()
        with patch.object(module, "adb", side_effect=RuntimeError("process_not_found")):
            result = module.sample_once("", "com.slgtranslator.app", "scan")
        self.assertEqual(result["error"], "process_not_found")
        self.assertEqual(result["phase"], "scan")


if __name__ == "__main__":
    unittest.main()
