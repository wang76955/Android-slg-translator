# Task 0 implementation report

## Status

`DONE_WITH_CONCERNS`

Task 0 is implemented and committed. The concerns are deliberately carried
forward as baseline findings: the complete source test suite still has the
pre-existing 25 failures, 1 error, and 1 skipped test, and Java plus the
Android command-line tools were unavailable in this environment. Task 0 did
not attempt to fix either class of issue.

## Implementation

Implemented only the Task 0 scope from
`task-0-brief.md`:

- Created the plan-specific progress ledger at
  `.superpowers/sdd/2026-08-07-renpy-batch-bc-complete-revalidation/progress.md`.
  It records Task 0 as `DONE`, keeps Tasks 1–23 `NOT-RUN`, and does not replace
  an older plan ledger.
- Created `docs/qa/renpy-revalidation-baseline.md` with the current source APK
  hash, Git HEAD/status snapshot, Python/Java/Node/Android tool probe, complete
  unittest baseline, unavailable-tool recovery commands, and the shared
  status-contract reference.
- Created `docs/qa/renpy-batch-bc-evidence.md` with the exact required header,
  eleven `T6`–`T16` rows initialized as `NOT-RUN`, and explicit definitions
  for `PASS`, `FAIL`, and `NOT-RUN`.
- Added `import re` and the explicit evidence-state assertion to
  `apk-work/ui-redesign/test_translation_coverage.py`.
- Wrote this report to the required plan-specific `.superpowers` path after
  the implementation commit.

No later Task 1–23 implementation was performed.

## Baseline commands and actual output

### APK, HEAD, and status

Command:

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath 'apk-work/github-source/slg-translator-android-rpyc-v12.apk'
```

Actual SHA256:

```text
44470607C402F6E8BBBDD5CED24B3AFF9016C92CE504BA2F2C3CE77DB1567104
```

Command:

```powershell
git rev-parse HEAD
git status --short --branch
```

Before Task 0 changes, the actual HEAD was:

```text
d38b551aa96a3914bfbb3795c70808ae900626f3
```

The branch line was `## master`. The four protected documents were already
staged as `A` and were not changed. The status also contained the pre-existing
large set of unrelated `??` APK, screenshot, fixture, and script paths; none
was added, removed, cleaned, reset, or rewritten.

### Toolchain

Commands:

```powershell
python --version
java -version
node --version
Get-Command adb,apksigner,zipalign -ErrorAction SilentlyContinue | Select-Object Name,Source
```

Actual results:

```text
Python 3.14.5

java : The term 'java' is not recognized as the name of a cmdlet, function, script file, or operable program.
CategoryInfo          : ObjectNotFound: (java:String) [], CommandNotFoundException
FullyQualifiedErrorId : CommandNotFoundException

v22.14.0

<no output from Get-Command adb,apksigner,zipalign ...>
```

Java, `adb`, `apksigner`, and `zipalign` were recorded as unavailable / not
run for those checks, never as passing. The baseline document contains the
recovery probe that sets `JAVA_HOME`, `ANDROID_SDK_ROOT`, and the relevant
`PATH` entries before rerunning the same commands.

### Complete unittest baseline before the Task 0 test

Command from `apk-work/ui-redesign`:

```powershell
python -m unittest discover -s . -p 'test_*.py' -v
```

Actual final summary:

```text
Ran 167 tests in 144.343s

FAILED (failures=25, errors=1, skipped=1)
```

The count exactly matched the brief's expected start baseline, so there were
no added or disappeared test names to reconcile. The existing skip reason was
`audit APK/extracted texts not present`.

## TDD RED/GREEN evidence

### RED

The assertion was added before the evidence rows were populated. The first
targeted run found the expected missing-file setup issue:

```text
FileNotFoundError: [Errno 2] No such file or directory:
'D:\\文件翻译\\docs\\qa\\renpy-batch-bc-evidence.md'
```

To make the RED evidence a real assertion failure rather than a fixture
error, the required exact table header was created with zero status rows. The
targeted test was then rerun:

```powershell
python -m unittest test_translation_coverage.TranslationCoverageLogicTest.test_revalidation_evidence_uses_only_explicit_statuses -v
```

Actual RED result:

```text
test_revalidation_evidence_uses_only_explicit_statuses (...) ... FAIL

AssertionError: 0 not greater than or equal to 11

Ran 1 test in 0.011s

FAILED (failures=1)
EXIT_CODE=1
```

The failure was specifically caused by the missing eleven explicit evidence
statuses, not by a syntax error or an unrelated production behavior.

### GREEN

After adding the eleven `T6`–`T16` `NOT-RUN` rows and the status definitions,
the same command produced:

```text
test_revalidation_evidence_uses_only_explicit_statuses (...) ... ok

Ran 1 test in 0.015s

OK
EXIT_CODE=0
```

The post-commit rerun also passed:

```text
Ran 1 test in 0.001s

OK
```

Independent content checks reported:

```text
TABLE_DATA_ROW_COUNT=11
TABLE_STATUS_COLUMN_COUNT=11
HAS_HEADER=True
HAS_ASSUMED_PASS=False
HAS_INFERRED_ZERO=False
```

The machine assertion now counts exactly 11 data rows and reads exactly 11
status values from the sixth table column. It accepts `PASS`, `FAIL`, or
`NOT-RUN` for each row, so later Task 6–16 updates can replace `NOT-RUN`
without changing the assertion.

### Full regression after the Task 0 test

The complete suite was rerun after the GREEN state:

```powershell
python -m unittest discover -s . -p 'test_*.py' -v
```

Actual final summary:

```text
Ran 168 tests in 139.046s

FAILED (failures=25, errors=1, skipped=1)
EXIT_CODE=1
```

The total increased by exactly one for the new machine assertion. The
existing failure/error/skip counts remained unchanged; Task 0 did not broaden
scope to repair them.

## Changed paths and commit

The implementation commit was created with explicit paths and
`git commit --only`:

```text
d3c56b820d6a178f0856db48461ff3d864a34607
test: freeze renpy complete revalidation baseline
```

The commit's actual name-status was exactly:

```text
A .superpowers/sdd/2026-08-07-renpy-batch-bc-complete-revalidation/progress.md
M apk-work/ui-redesign/test_translation_coverage.py
A docs/qa/renpy-batch-bc-evidence.md
A docs/qa/renpy-revalidation-baseline.md
```

The report itself is intentionally written after the commit, because the
brief's explicit commit path list contains exactly those four implementation
paths. It remains at the required plan-specific `.superpowers` report path.

## Self-audit

- The commit contains only the four Task 0 paths required by the brief.
- The four pre-existing staged protection files remain staged as `A` after the
  commit and have no Task 0 diff.
- Existing unrelated untracked APKs, screenshots, fixtures, scripts, and
  directories remain in the working tree and were not cleaned or staged.
- No `git add .`, `git add -A`, `git reset`, `git clean`, or `git checkout` was
  used.
- No child agent was created.
- No Task 1–23 source file was modified.
- The ignored plan progress path was included only through its explicit path
  with `git add -f --`; no broad force-add was used.
- The final targeted assertion passes and the full regression result is
  honestly recorded as failing at the pre-existing 25/1/1 baseline level.

## Risks and follow-up

- The full unittest suite is not green: 25 failures, 1 error, and 1 skip are
  still present. These are baseline observations and require later task or
  separate bug-fix scope.
- Java is not on `PATH`, so Java compilation and Java-dependent APK checks
  cannot be run in this environment.
- `adb`, `apksigner`, and `zipalign` are not discoverable, so APK alignment,
  signing, installation, and device validation remain unverified.
- The source APK hash proves the identity of the input artifact only; it is not
  evidence that a rebuilt APK is signed, installable, launchable, or fully
  translated.
- The evidence ledger correctly leaves Tasks 6–16 `NOT-RUN`; later work must
  replace those rows only with command- and artifact-backed status.

## Fix round 1 — review remediation

### Review outcome and scope

Review baseline: `d38b551aa96a3914bfbb3795c70808ae900626f3`.
Pre-fix head: `d3c56b820d6a178f0856db48461ff3d864a34607`.

This round addressed every listed Critical/Important issue and the audit
ambiguity in the old status-count wording. No product implementation, no
pre-existing behavior test, no protected staged document, and no unrelated
untracked file was modified. The fix commit uses the requested subject:

```text
test: tighten revalidation baseline evidence
```

### 1. Fixed evidence-schema machine assertion

The former assertion used a whole-document regular expression and reported a
wide count that included status words in non-status columns. It was replaced
with a fixed table parser that:

- locates the exact nine-column header;
- checks the separator has nine columns;
- reads the contiguous data rows only;
- requires exactly 11 rows;
- requires the exact ID set `T6`–`T16` with no duplicates; and
- reads `row[5]`, the sixth column, and accepts only `PASS`, `FAIL`, or
  `NOT-RUN`.

The assertion does not require all rows to remain `NOT-RUN`. A temporary test
mutation setting T6 to `PASS` and T7 to `FAIL` passed, after which the ledger
was restored to its correct all-`NOT-RUN` state.

### 2. TDD RED/GREEN evidence for the parser

The old broad assertion was freshly run before the change:

```powershell
python -m unittest test_translation_coverage.TranslationCoverageLogicTest.test_revalidation_evidence_uses_only_explicit_statuses -v
```

Actual old-assertion result:

```text
Ran 1 test in 0.001s

OK
EXIT_CODE=0
```

After writing the fixed parser assertion, a temporary extra `T17` data row
was added to the evidence table. The new assertion correctly produced RED:

```text
AssertionError: 12 != 11

Ran 1 test in 0.011s

FAILED (failures=1)
EXIT_CODE=1
```

The temporary row was removed. With the valid T6–T16 table, the same command
produced GREEN:

```text
Ran 1 test in 0.002s

OK
EXIT_CODE=0
```

The future-status compatibility run, with temporary T6=`PASS` and T7=`FAIL`,
also produced:

```text
Ran 1 test in 0.013s

OK
EXIT_CODE=0
```

The final evidence ledger was restored to all eleven `NOT-RUN` rows before
staging.

### 3. Failure/error inventory and focused verification

The baseline document now contains all 25 failure names and the one error
name, one stable focus command per item, the first useful exception/assertion,
and one of the fixed design categories C1–C6. It records the real module run:

```powershell
python -m unittest test_workshop_patch.py -v
```

Before and after the parser/document fixes, the focused module remained:

```text
Ran 49 tests in 6.926s   # pre-fix inventory run
FAILED (failures=25, errors=1)
EXIT_CODE=1

Ran 49 tests in 7.209s   # post-fix verification run
FAILED (failures=25, errors=1)
EXIT_CODE=1
```

The raw temporary logs contained generated bundle output, but the baseline
document intentionally records only the first useful diagnostic and marks
the bundle right-hand side as omitted; no multi-megabyte dump was copied into
the repository.

### 4. APK provenance

`docs/qa/renpy-revalidation-baseline.md` now pins all required provenance:

- repository: `https://github.com/wang76955/slg-translator`;
- fixed commit: `fc2e3f39f85a09799e63fa652e566e3850ff9f31`;
- raw APK URL:
  `https://raw.githubusercontent.com/wang76955/slg-translator/fc2e3f39f85a09799e63fa652e566e3850ff9f31/android-release/slg-translator-android-rpyc-v12.apk`;
- local path: `apk-work/github-source/slg-translator-android-rpyc-v12.apk`;
- observed local SHA256:
  `44470607C402F6E8BBBDD5CED24B3AFF9016C92CE504BA2F2C3CE77DB1567104`.

The document explicitly requires an immediate stop on any mismatch instead
of substituting another APK or treating it as equivalent.

### 5. Phase 0 scope ruling

The authority design
`docs/superpowers/specs/2026-08-07-renpy-batch-bc-complete-revalidation-design.md`
§5.1 now states the minimal ruling: “read-only” means no product-logic or
existing behavior-test changes; Task 0 may add one evidence-schema machine
assertion that does not change product behavior. The assertion is the only
test-file change in this round, and this report records the ruling so future
review does not treat the brief/design wording as contradictory.

### 6. Corrected status-count language

The earlier `EXPLICIT_STATUS_COUNT=22` wording was removed. The report now
records the accurate model:

```text
TABLE_DATA_ROW_COUNT=11
TABLE_STATUS_COLUMN_COUNT=11
HAS_HEADER=True
HAS_ASSUMED_PASS=False
HAS_INFERRED_ZERO=False
```

### 7. Full discover verification

After all fixes, the complete suite was rerun:

```powershell
python -m unittest discover -s . -p 'test_*.py' -v
```

Actual output summary:

```text
Ran 168 tests in 137.456s

FAILED (failures=25, errors=1, skipped=1)
EXIT_CODE=1
```

The result is unchanged in failure/error/skip counts from the original
baseline; only the evidence assertion implementation and documentation were
changed. The remaining 25/1/1 are therefore still an explicit unresolved
risk, not hidden by this repair.

### Fix round 1 files

Modified or appended only:

- `docs/qa/renpy-revalidation-baseline.md`
- `apk-work/ui-redesign/test_translation_coverage.py`
- `docs/superpowers/specs/2026-08-07-renpy-batch-bc-complete-revalidation-design.md`
- `.superpowers/sdd/2026-08-07-renpy-batch-bc-complete-revalidation/progress.md`
- this report

The evidence ledger itself was restored to its pre-round T6–T16 `NOT-RUN`
content and is not part of the fix diff. The four protected user-staged
documents and unrelated untracked files remain untouched.

### Remaining risks

- The full suite remains non-green at 25 failures, 1 error, and 1 skipped;
  this round did not modify product behavior or repair those findings.
- Java, `adb`, `apksigner`, and `zipalign` remain unavailable, so build/sign/
  install/device evidence is still not run.
- The provenance tuple is pinned, but this round did not replace the local APK
  or claim remote artifact equivalence; a future mismatch must stop the run.
- The failure inventory classifies observed evidence for Phase 0; it does not
  decide whether later Phase 1 work should change a product implementation,
  a behavior test, a fixture, or a compressed-bundle contract.
