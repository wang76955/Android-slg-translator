import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FAST_SCAN = ROOT / "apk-work" / "native-fast-scan"
JAVA_HOME = Path(os.environ.get("JAVA_HOME", ""))
JAVA = JAVA_HOME / "bin" / "java.exe"
JAVAC = JAVA_HOME / "bin" / "javac.exe"


def third_party_classpath():
    from test_fast_scanner import third_party_classpath as classpath
    return classpath()


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

    def test_task8_collision_report_has_unique_old_occurrences_and_contexts(self):
        entries = [
            {"old": "OK{#menu}", "sourcePath": "game/a.rpyc", "speaker": "", "kind": "MENU"},
            {"old": "OK{#menu}", "sourcePath": "game/a.rpyc", "speaker": "", "kind": "MENU"},
            {"old": "Fine.", "sourcePath": "game/a.rpyc", "speaker": "alice", "kind": "DIALOGUE"},
            {"old": "Fine.", "sourcePath": "game/b.rpyc", "speaker": "bob", "kind": "DIALOGUE"},
        ]
        grouped = {}
        for item in entries:
            grouped.setdefault(item["old"], []).append(item)
        self.assertEqual(len(grouped), 2)
        self.assertEqual(len(grouped["OK{#menu}"]), 2)
        self.assertEqual({x["speaker"] for x in grouped["Fine."]}, {"alice", "bob"})

    def test_task10_java_report_counts_validated_rejected_collision_uncertain_and_files(self):
        source = r'''
import com.slgtranslator.app.RenpyTextRecord;
import com.slgtranslator.app.TranslationCoverageReport;
import java.util.*;

public final class CoverageReportHarness {
  public static void main(String[] args) {
    List<RenpyTextRecord> records = Arrays.asList(
      new RenpyTextRecord("Hello", RenpyTextRecord.Kind.DIALOGUE, "alice", "", "game/a.rpyc", 10, 1, true),
      new RenpyTextRecord("Hello", RenpyTextRecord.Kind.DIALOGUE, "alice", "", "game/a.rpyc", 11, 2, true),
      new RenpyTextRecord("Missing", RenpyTextRecord.Kind.DIALOGUE, "bob", "", "game/b.rpyc", 20, 1, true),
      new RenpyTextRecord("Rejected", RenpyTextRecord.Kind.UI_STRING, "", "", "game/b.rpyc", 21, 1, true),
      new RenpyTextRecord("Uncertain", RenpyTextRecord.Kind.CUSTOM_STATEMENT, "", "", "game/c.rpyc", 30, 1, false)
    );
    Map<String, String> validated = new LinkedHashMap<>();
    validated.put("Hello", "你好");
    Set<String> rejected = new LinkedHashSet<>(Collections.singleton("Rejected"));
    Set<String> uncertain = new LinkedHashSet<>(Collections.singleton("Uncertain"));
    Map<String, List<String>> candidates = new LinkedHashMap<>();
    candidates.put("Hello", Arrays.asList("你好", "您好"));
    Map<String, String> classifications = new LinkedHashMap<>();
    classifications.put("game/common.rpyc\tDeveloper", "developer_console");
    TranslationCoverageReport report = TranslationCoverageReport.build(
      records, validated, rejected, candidates, uncertain, classifications);
    require(report.uniqueSourceCount == 4, "unique source count");
    require(report.occurrenceCount == 5, "occurrence count");
    require(report.translatedCount == 1, "validated only count");
    require(report.missingCount == 1, "missing count");
    require(report.rejectedCount == 1, "rejected count");
    require(report.collisionCount == 1, "collision count");
    require(report.uncertainCount == 1, "uncertain count");
    require(report.files.get("game/b.rpyc").missingCount == 1, "per-file missing");
    require(report.topMissing().size() == 1 && "Missing".equals(report.topMissing().get(0).exactOld), "top missing");
    String json = report.toSanitizedJson();
    require(json.contains("uniqueSourceCount") && json.contains("game/b.rpyc"), "json fields");
    require(!json.contains("你好") && !json.contains("您好"), "translations must not be exported");
    require(report.shouldBlockCompleteBuild(), "missing/rejected must block complete build");
    require(report.canGenerateIncompleteTestPatch(), "incomplete test patch remains available");
    TranslationCoverageReport.IncrementalDiff diff = TranslationCoverageReport.incrementalDiff(
      Arrays.asList("Hello", "Missing", "New"),
      new LinkedHashSet<>(Collections.singleton("Hello")),
      new LinkedHashSet<>(Collections.singleton("Missing")),
      new LinkedHashSet<>(Collections.singleton("New")));
    require(diff.requestExactOld.contains("Missing") && diff.requestExactOld.contains("New"), "incremental retry");
    require(!diff.requestExactOld.contains("Hello"), "unchanged validated entry reused");

    List<RenpyTextRecord> common = Arrays.asList(
      new RenpyTextRecord("Story common", RenpyTextRecord.Kind.DIALOGUE, "", "", "assets/x-renpy/x-common/story.rpyc", 1, 1, true),
      new RenpyTextRecord("Developer", RenpyTextRecord.Kind.CUSTOM_STATEMENT, "", "", "assets/x-renpy/x-common/debug.rpyc", 2, 1, true));
    TranslationCoverageReport commonReport = TranslationCoverageReport.build(
      common, Collections.singletonMap("Story common", "故事公共文本"), Collections.emptySet(),
      Collections.emptyMap(), Collections.emptySet(),
      Collections.singletonMap("assets/x-renpy/x-common/debug.rpyc\tDeveloper", "developer_console"));
    require(commonReport.uniqueSourceCount == 1, "x-common story text is included by default");
    require(commonReport.excludedReasons.containsValue("developer_console"), "x-common skip requires explicit reason");
  }
  private static void require(boolean value, String message) {
    if (!value) throw new AssertionError(message);
  }
}
'''
        stubs = sorted((FAST_SCAN / "stubs").rglob("*.java"))
        with tempfile.TemporaryDirectory(prefix="coverage-report-red-") as temporary:
            root = Path(temporary)
            harness = root / "CoverageReportHarness.java"
            classes = root / "classes"
            harness.write_text(source, "utf-8")
            classes.mkdir()
            result = subprocess.run(
                [str(JAVAC), "-source", "8", "-target", "8", "-encoding", "UTF-8",
                 "-d", str(classes), "-classpath", third_party_classpath(),
                 *map(str, stubs),
                 str(FAST_SCAN / "src/com/slgtranslator/app/RenpyTextRecord.java"),
                 str(FAST_SCAN / "src/com/slgtranslator/app/TranslationCoverageReport.java"),
                 str(harness)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run(
                [str(JAVA), "-cp", str(classes), "CoverageReportHarness"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_task10_ui_coverage_gate_and_sanitized_report_are_wired(self):
        source = (ROOT / "apk-work" / "ui-redesign" / "patch_workshop_ui.py").read_text("utf-8")
        for token in (
            "TranslationCoverageReport", "missingCount", "rejectedCount", "uncertainCount",
            "topMissing", "x-common", "coverage", "incomplete", "__slgBuildCoverage",
            "__slgIncompleteTestPatch", "__slgTranslationCoverageReportJson",
            "__slgRecordValidatorApprovedTranslations?.(t,_lr.translations)",
            "__slgRecordValidatorApprovedTranslations?.(t,d)",
            "__slgRecordRejectedTranslations?.(_lr.rejected)",
            "__slgResetTranslationCoverage",
            "function exact(value)",
        ):
            self.assertIn(token, source)
        self.assertIn("slg-translator-cache:", source)
        self.assertNotIn("slg-translator-cache:v2:", source)

    def test_task10_scanner_keeps_exact_old_occurrences_for_coverage(self):
        source = (FAST_SCAN / "src/com/slgtranslator/app/FastApkScanner.java").read_text("utf-8")
        for token in (
            "renpyRecords", "TranslationCoverageReport", "exactOld", "occurrenceCount",
            "coverageReport", "validatorApprovedTranslations",
        ):
            self.assertIn(token, source)

    def test_task10_missing_fixture_never_becomes_fake_zero(self):
        source = Path(__file__).read_text("utf-8")
        self.assertIn('self.skipTest("audit APK/extracted texts not present")', source)
        self.assertNotIn('missing' + 'Count:0', source)


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
