# Ren'Py batch BC complete revalidation baseline

This is the Task 0 baseline for plan `2026-08-07-renpy-batch-bc-complete-revalidation`.
It was collected from `D:\文件翻译` on 2026-08-07. Values below are from the
current checkout and are not carried forward from an older ledger.

## Source APK and Git snapshot

Command:

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath 'apk-work/github-source/slg-translator-android-rpyc-v12.apk'
```

Actual output:

```text
Algorithm       Hash                                                                   Path
---------       ----                                                                   ----
SHA256          44470607C402F6E8BBBDD5CED24B3AFF9016C92CE504BA2F2C3CE77DB1567104       D:\文件翻译\apk-work\github-source\slg-translator-android-rpyc-v12.apk
```

Command:

```powershell
git rev-parse HEAD
git status --short --branch
```

Actual HEAD:

```text
d38b551aa96a3914bfbb3795c70808ae900626f3
```

The status began with `## master`. The four user-protected documents were
already staged as `A` before Task 0:

```text
A  PRODUCT.md
A  docs/superpowers/plans/2026-07-13-apk-main-flow-redesign-v2.md
A  docs/superpowers/specs/2026-07-13-android-apk-ui-redesign-design.md
A  docs/superpowers/specs/2026-07-13-apk-main-flow-redesign-v2-design.md
```

The same status also contained a large pre-existing set of unrelated `??`
APK, screenshot, fixture, and script paths. They were left untouched. No
pre-existing staged path was changed by Task 0.

## Toolchain probe

Commands were run from the repository root:

```powershell
python --version
java -version
node --version
Get-Command adb,apksigner,zipalign -ErrorAction SilentlyContinue | Select-Object Name,Source
```

Actual outputs:

```text
Python 3.14.5

java : The term 'java' is not recognized as the name of a cmdlet, function, script file, or operable program.
...
CategoryInfo          : ObjectNotFound: (java:String) [], CommandNotFoundException
FullyQualifiedErrorId : CommandNotFoundException

v22.14.0

<no output from Get-Command adb,apksigner,zipalign ...>
```

The unavailable tools are explicitly not treated as successful checks:

| Tool | Observed state | State used by this baseline | Recovery command |
|---|---|---|---|
| Python | `Python 3.14.5` | available | `python --version` |
| Java | PowerShell `CommandNotFoundException` | `NOT-RUN` | Set `JAVA_HOME` and prepend `<JAVA_HOME>\bin` to `PATH`, then run `java -version` |
| Node | `v22.14.0` | available | `node --version` |
| `adb` | no `Get-Command` row | `NOT-RUN` | Set `$env:Path` to include `<ANDROID_SDK_ROOT>\platform-tools`, then run `Get-Command adb` |
| `apksigner` | no `Get-Command` row | `NOT-RUN` | Set `$env:Path` to include `<ANDROID_SDK_ROOT>\build-tools\<version>`, then run `Get-Command apksigner` |
| `zipalign` | no `Get-Command` row | `NOT-RUN` | Set `$env:Path` to include `<ANDROID_SDK_ROOT>\build-tools\<version>`, then run `Get-Command zipalign` |

Reusable PowerShell recovery probe once the SDK/JDK locations are installed:

```powershell
$env:JAVA_HOME = '<JAVA_HOME>'
$env:ANDROID_SDK_ROOT = '<ANDROID_SDK_ROOT>'
$env:Path = "$env:JAVA_HOME\bin;$env:ANDROID_SDK_ROOT\platform-tools;$env:ANDROID_SDK_ROOT\build-tools\<version>;$env:Path"
python --version
java -version
node --version
Get-Command adb,apksigner,zipalign -ErrorAction SilentlyContinue | Select-Object Name,Source
```

## Complete unittest baseline

Command, run from `apk-work/ui-redesign` before adding the Task 0 test:

```powershell
python -m unittest discover -s . -p 'test_*.py' -v
```

Actual final output summary:

```text
Ran 167 tests in 144.343s

FAILED (failures=25, errors=1, skipped=1)
```

The observed count exactly matched the brief's expected plan-start baseline
(167 / 25 / 1 / 1), so there was no added or disappeared test name to record.
The skipped test reported the existing reason:
`audit APK/extracted texts not present`.

This result is a source-test baseline only. It does not claim APK build,
signing, installation, launch, or translation coverage success.

## Task 0 evidence contract

The companion evidence ledger at
`docs/qa/renpy-batch-bc-evidence.md` is the shared state model for Tasks 6–16.
Every row uses exactly one of `PASS`, `FAIL`, or `NOT-RUN`. Task 0 initializes
Tasks 6–16 as `NOT-RUN`; later tasks must replace a row only with evidence
backed by the referenced command and artifact.

The machine assertion is
`TranslationCoverageLogicTest.test_revalidation_evidence_uses_only_explicit_statuses`.
Its TDD RED/GREEN record is in `task-0-report.md`.
