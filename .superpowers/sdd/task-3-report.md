# Task 3 Report: Fail fast on unreachable provider networks

## Status

Implemented and verified. Commit: `298286b`.

## TDD record

- RED: `python -m unittest discover -s apk-work/ui-redesign -p "test_workshop_patch.py" -v`
  failed only `test_network_failures_stop_batches_without_recursive_splitting` because `function isNetworkFailure(e)` was absent (7 passed, 1 failed).
- GREEN focused: the same command passed 8/8 tests.
- GREEN full: `python -m unittest discover -s apk-work/ui-redesign -p "test_*.py" -v` passed 12/12 tests.
- Generated JavaScript: `python apk-work/ui-redesign/patch_workshop_ui.py` followed by
  `node --check apk-work/ui-redesign/generated/index-CJtfdHOF.js` exited 0.
- Diff hygiene: `git diff --check` exited 0.

## Implementation

- Added `patch_translation_network(js: str) -> str` with exact, single-occurrence
  signature guards for the coordinator, retry setting, worker state/catch, result,
  and recursive batch recovery.
- Reduced the SDK retry bound from 2 to 1.
- Added generated `isNetworkFailure` and `providerLabel` helpers.
- Network failures now stop remaining worker batches and bypass recursive splitting;
  non-network content errors still retain `let c=Math.ceil(n.length/2)` recovery.
- Added behavior-level Node coverage for observed browser
  `net::ERR_CONNECTION_TIMED_OUT`, SDK `Connection error`, a non-network content
  error, and all provider labels.
- Applied the required patch order: scan flow, translation cache, translation network.

## Self-review and concerns

- No API keys or request bodies are logged or printed by the implementation/tests.
- Only `apk-work/ui-redesign/patch_workshop_ui.py` and
  `apk-work/ui-redesign/test_workshop_patch.py` are intended for the commit.
- The classifier intentionally follows the requested broad keyword contract; messages
  containing words such as `connection` are treated as network failures.
- Existing unrelated modified/untracked workspace files were left untouched.

## Review fix pass

Status: implemented and verified. Follow-up commit: `57ea18b`.

### Findings addressed

- Replaced the outer `fs`/`Promise.allSettled` file chunk with the generated
  `runFileTasksUntilFatal()` scheduler. The exact outer state, loop start/end,
  per-file result, empty-result return, and final result signatures each have
  single-occurrence guards. A provider network fatal now stops file acquisition,
  including the two-file case where file 2 must not start.
- Preserved the actionable fatal string through cache/partial successes, logged it
  for partial results, and selected it ahead of the generic final partial-failure
  string. The provider label is captured before the batch worker shadows the
  minified `i` variable, so DeepSeek/OpenAI/custom labels remain accurate.
- Narrowed `isNetworkFailure()` to inspect `name`, `code`, and `message` through
  nested `cause` values. It allowlists the reviewed browser/SDK codes and shapes,
  including `net::ERR_CONNECTION_TIMED_OUT`, `ERR_NETWORK`, `ENOTFOUND`,
  `EAI_AGAIN`, `ECONNREFUSED`, `ECONNRESET`, `ETIMEDOUT`, SDK
  `APIConnectionError`/exact `Connection error`, failed-to-fetch, offline, DNS,
  and timeout forms. Blanket `ERR_`, `network`, and `connection` matching was removed.
- Added a network-failed snapshot before completed/patching/translating checks.
  The visible shell renders the provider-aware message and working settings/retry
  actions, so stale translating logs cannot trap the UI in an active state.
- Added executable Node behavior coverage around generated `Bo()`, `Lo()`, the
  outer scheduler, `readTaskSnapshot()`, and `renderStateBody()` with controlled
  promises and stubs. Network errors avoid recursive splits; empty/JSON/count and
  `ERR_INVALID_JSON` content errors still split; current in-flight batches settle;
  later work does not start; partial results retain the fatal error; and UI recovery
  actions invoke their handlers.

### TDD and verification record

- Initial review RED:
  `python -m unittest discover -s apk-work/ui-redesign -p "test_workshop_patch.py" -v`
  -> 7 passed, 3 failed for the missing outer scheduler, missing network UI state,
  and missing nested `cause.code` classification.
- Provider-label RED during GREEN iteration: the executable partial-result test
  exposed the minified worker's shadowed `i`, yielding the wrong provider label.
- Failed-to-fetch boundary RED: the executable classifier test rejected the
  hyphenated form before the allowlist was extended.
- Focused final:
  `python -m unittest discover -s apk-work/ui-redesign -p "test_workshop_patch.py" -v`
  -> 10 tests passed.
- Full final:
  `python -m unittest discover -s apk-work/ui-redesign -p "test_*.py" -v`
  -> 14 tests passed.
- Generated JavaScript:
  `python apk-work/ui-redesign/patch_workshop_ui.py`
  -> exit 0.
- JavaScript syntax:
  `node --check apk-work/ui-redesign/generated/index-CJtfdHOF.js`
  -> exit 0, no output.
- Diff hygiene: `git diff --check` -> exit 0 (line-ending warnings only).

### Fix-pass self-review

- No API keys or request bodies are logged or printed by the new code or tests.
- Content error recovery remains bounded by the existing split depth and its
  `let c=Math.ceil(n.length/2)` path.
- The outer source already declares `fs=1`; the scheduler preserves sequential file
  behavior while adding an explicit task-fatal return contract.
- The failure matcher intentionally accepts only the exact generated Chinese
  provider-aware message for cross-layer task/UI propagation.
- Existing unrelated modified and untracked files remain untouched; only the two
  requested Python files will be staged for the follow-up commit.

## Authoritative latest status

This section supersedes the status and commit references above. Task 3 is fully
implemented and verified through the browser/WebView allowlist follow-up. Latest
commit: `4da776a`.

### Browser/WebView allowlist follow-up

- Added explicit Chromium/WebView positives for
  `net::ERR_CONNECTION_REFUSED`, `net::ERR_INTERNET_DISCONNECTED`,
  `net::ERR_NAME_NOT_RESOLVED`, `DNS_PROBE_FINISHED_NXDOMAIN`,
  `net::ERR_CONNECTION_RESET`, and `net::ERR_TIMED_OUT`, while retaining
  `net::ERR_CONNECTION_TIMED_OUT`.
- The allowlist remains explicit; no blanket `ERR_`, `network`, or `connection`
  matcher was reintroduced.
- Executable negatives for `ERR_INVALID_JSON`, arbitrary connection wording, and
  arbitrary network wording remain active and passing.

### Latest TDD and verification results

- RED: `python -m unittest discover -s apk-work/ui-redesign -p "test_workshop_patch.py" -v`
  -> 9 passed, 1 failed at `browser refused classification` before the allowlist
  extension.
- Focused GREEN: the same command -> 10 tests passed.
- Full: `python -m unittest discover -s apk-work/ui-redesign -p "test_*.py" -v`
  -> 14 tests passed.
- Generated output: `python apk-work/ui-redesign/patch_workshop_ui.py` -> exit 0.
- Syntax: `node --check apk-work/ui-redesign/generated/index-CJtfdHOF.js`
  -> exit 0, no output.
- Hygiene: `git diff --check` -> exit 0 (line-ending warnings only).

### Latest self-review

- The new browser codes are enumerated in one bounded regular-expression branch.
- SDK/cause inspection and task-wide fatal propagation are unchanged.
- Content failures remain recursively splittable, and no API keys or request bodies
  are printed by the implementation or tests.
- Only `patch_workshop_ui.py` and `test_workshop_patch.py` will be committed.
