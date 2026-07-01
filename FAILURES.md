# FAILURES.md — Failure Log

> **Owned by:** Verifier Agent (append-only; never modify or delete past entries)
> **Purpose:** Structured log of every verification failure. Used by Memory Agent to extract patterns and by Orchestrator to decide halt/retry.
> **Rules:**
> - One entry per failure event (a failure event = one run of `verify.sh` that exits non-zero)
> - Append new entries at the **bottom** of this file
> - Call `scripts/summarize_failure.sh` after writing each entry
> - Severity levels: `WARN` | `ERROR` | `CRITICAL`

---

## Failure Entry Schema

Each entry must contain ALL of the following fields:

```
### FAIL-NNNN
- **Timestamp:** ISO 8601 with timezone
- **Phase:** N
- **Check:** P{N}-{K} (from VERIFY.md)
- **Severity:** WARN | ERROR | CRITICAL
- **Agent:** Role that detected the failure
- **Command:** Exact command that failed
- **Exit code:** N
- **Error class:** e.g. ImportError, AssertionError, CalledProcessError
- **Traceback (<=10 lines):**
  ```
  <paste here>
  ```
- **File:** path/to/file.py:line_number
- **Proposed fix:** One-line description or reference to MEMORY.md entry
- **Fix applied:** YES | NO | PENDING
- **Resolved by:** FAIL-MMMM (if a later entry resolves this) | OPEN
```

---

## How Orchestrator Uses This File

1. Count consecutive `ERROR` entries for the current phase with `Fix applied: NO`
2. If count >= 3: halt loop, set `TASK.md` `PHASE_STATUS = HALTED`, notify human
3. If a `CRITICAL` entry exists with `Fix applied: NO`: halt immediately
4. If `Fix applied: YES` and `Resolved by: FAIL-MMMM`: advance phase if VERIFY passes
5. Cross-reference `Proposed fix` with `MEMORY.md` — if a matching `MEM-NNNN` exists, apply it automatically

---

## Active Failures

*No failures recorded yet. This section will be populated by the Verifier Agent during loop execution.*

---

## Resolved Failures

*No resolved failures yet.*

---

## Failure Statistics

| Phase | Total Failures | Resolved | Open | Critical |
|-------|---------------|----------|------|----------|
| 0     | 0             | 0        | 0    | 0        |
| 1     | 0             | 0        | 0    | 0        |
| 2     | 0             | 0        | 0    | 0        |
| 3     | 0             | 0        | 0    | 0        |
| 4     | 0             | 0        | 0    | 0        |
| 5     | 0             | 0        | 0    | 0        |
| **Total** | **0**     | **0**    | **0**| **0**    |

*Statistics updated by `scripts/summarize_failure.sh` after each entry.*

---

## Example Entry (for reference)

```markdown
### FAIL-0001
- **Timestamp:** 2026-06-30T22:15:00-04:00
- **Phase:** 1
- **Check:** P1-3
- **Severity:** ERROR
- **Agent:** Verifier
- **Command:** `uv run python -c "from ch6_multimodal_perception.models import PDFChunk"`
- **Exit code:** 1
- **Error class:** ImportError
- **Traceback (<=10 lines):**
  ```
  Traceback (most recent call last):
    File "<string>", line 1, in <module>
    File ".../models.py", line 3, in <module>
      from pydantic import BaseModel, ConfigDict
  ImportError: cannot import name 'ConfigDict' from 'pydantic'
  ```
- **File:** src/ch6_multimodal_perception/models.py:3
- **Proposed fix:** Upgrade pydantic to >=2.7.0; ConfigDict was added in v2
- **Fix applied:** YES
- **Resolved by:** OPEN
```
