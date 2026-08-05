import unittest
from pathlib import Path


class TranslationCoverageLogicTest(unittest.TestCase):
    """Pure-Python coverage comparison used by the full APK audit."""

    def test_missing_strings_are_reported(self):
        corpus = {"Hello", "Choice A", "Name", "Screen Title"}
        translated = {"Hello", "Choice A"}
        missing = sorted(corpus - translated)
        self.assertEqual(missing, ["Name", "Screen Title"])

    def test_files_without_translation_counterpart_are_flagged(self):
        original_files = {
            "assets/x-game/x-ch1.rpyc",
            "assets/x-game/x-ch2.rpyc",
        }
        translated_files = {
            "assets/x-game/x-tl/x-slgtranslated/x-ch1.rpyc",
        }
        missing_files = sorted(
            name
            for name in original_files
            if not any(
                name.split("/")[-1] == tf.split("/")[-1]
                for tf in translated_files
            )
        )
        self.assertEqual(missing_files, ["assets/x-game/x-ch2.rpyc"])

    def test_builtin_chinese_coverage_is_separate(self):
        corpus = {"Hello", "Menu", "Unique"}
        builtin = {"Hello", "Menu"}      # official Chinese bucket
        translator = {"Hello", "Unique"}  # our slgtranslated bucket
        only_builtin = sorted(builtin - translator)
        self.assertEqual(only_builtin, ["Menu"])
        translator_only = sorted(translator - builtin)
        self.assertEqual(translator_only, ["Unique"])
        uncovered = sorted(corpus - builtin - translator)
        self.assertEqual(uncovered, [])


    def test_audit_pins_the_verified_missing_set(self):
        """The patched APK must cover the full extracted corpus (missing == 0).

        Uses the rebuilt corpus dump (extractor now pulls source-call text and
        translation-bucket old keys) plus the latest patched APK when present.
        """
        import importlib.util
        import sys
        from pathlib import Path
        qa = Path(__file__).resolve().parent / "qa"
        apk = qa / "ewn-audit-patched2.apk"
        dump = qa / "extracted-texts-v2.txt"
        if not (apk.exists() and dump.exists()):
            self.skipTest("audit APK/extracted texts not present")
        spec = importlib.util.spec_from_file_location("audit_coverage", qa / "audit_coverage.py")
        audit = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(audit)
        result = audit.audit(apk_path=apk, dump_path=dump)
        self.assertEqual(len(result["missing"]), 0)
        self.assertGreater(result["translated_keys"], 32000)


if __name__ == "__main__":
    unittest.main()
