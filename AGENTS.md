# AGENTS.md — Agentic Loop Engineering Guide

> **Repo:** `ch6-multimodal-perception`
> **Purpose:** Define agent roles, responsibilities, loop contracts, and coordination rules for the multimodal perception pipeline.

---

## 1. Overview

This repository is designed to be built and iterated by autonomous coding agents operating in a **phase-gated agentic loop**. Each agent reads this file to understand:

- Its role and scope
- What it is allowed to modify
- How to signal completion or failure
- Where to log work and decisions

The loop follows: **TASK → IMPLEMENT → VERIFY → LOG → (FAIL → MEMORY) → NEXT TASK**

---

## 2. Agent Roles

### 2.1 Architect Agent
- **Scope:** Top-level design only — `pyproject.toml`, `docker-compose.yml`, `Makefile`, `TASK.md`, `AGENTS.md`
- **Must NOT:** Write business logic or test code
- **Signals done:** Updates `WORKLOG.md` with `[ARCH]` prefix
- **Constraint:** All decisions must trace to a Chapter 6 section (6.1–6.5)

### 2.2 Implementer Agent
- **Scope:** All files under `src/ch6/` and `migrations/`
- **Must NOT:** Modify test files or top-level config docs
- **Reads before coding:** `TASK.md` (current phase), `MEMORY.md` (known patterns), `FAILURES.md` (known pitfalls)
- **Signals done:** Appends to `WORKLOG.md` with `[IMPL]` prefix
- **Constraint:** Every new module must have a corresponding `# Section X.Y` comment at the top

### 2.3 Verifier Agent
- **Scope:** `tests/` directory and `scripts/verify.sh`
- **Must NOT:** Modify source code
- **Runs:** `bash scripts/verify.sh` after every implementation phase
- **Signals pass:** Appends `PASS phase=N` to `WORKLOG.md`
- **Signals fail:** Appends structured failure to `FAILURES.md` and calls `scripts/summarize_failure.sh`
- **Constraint:** Never mark a phase complete unless ALL tests in that phase pass

### 2.4 Memory Agent
- **Scope:** `MEMORY.md` only
- **Triggered:** After every PASS or FAIL event
- **Writes:** Lessons learned, reusable patterns, gotchas
- **Must NOT:** Delete existing entries — append only

### 2.5 Orchestrator Agent
- **Scope:** Read-only across all files; writes only to `TASK.md` (phase advancement)
- **Decides:** When to advance phase, when to halt, when to retry
- **Halt condition:** More than 3 consecutive FAIL entries for the same phase in `FAILURES.md`
- **Retry condition:** FAIL is in `MEMORY.md` with a known fix — apply fix and re-verify

---

## 3. Agentic Loop Protocol

```
┌─────────────────────────────────────────────────────┐
│                  ORCHESTRATOR                       │
│  reads TASK.md → selects current phase              │
└──────────────────────┬──────────────────────────────┘
                       │
              ┌────────▼────────┐
              │  IMPLEMENTER    │
              │  reads MEMORY   │
              │  writes src/    │
              └────────┬────────┘
                       │
              ┌────────▼────────┐
              │   VERIFIER      │
              │  runs verify.sh │
              └──┬──────────┬───┘
                 │          │
              PASS        FAIL
                 │          │
          ┌──────▼──┐  ┌────▼──────────┐
          │ MEMORY  │  │ FAILURES.md   │
          │ Agent   │  │ summarize.sh  │
          └──────┬──┘  └────┬──────────┘
                 │           │
                 └─────┬─────┘
                  ┌────▼─────┐
                  │WORKLOG.md│
                  └──────────┘
```

---

## 4. Phase Gate Rules

| Phase | Name | Gate Condition |
|-------|------|----------------|
| 0 | Foundation Scaffolding | `pyproject.toml` installs cleanly with `uv sync` |
| 1 | Config + Models | `test_phase1_config.py` all green |
| 2 | Perception Extractors | `test_phase2_extractors.py` all green |
| 3 | Embeddings + Retrieval | `test_phase3_retrieval.py` all green |
| 4 | Pipeline + Handoffs | `test_phase4_pipeline.py` all green |
| 5 | Polish + Docs | README complete, notebook runs end-to-end |

---

## 5. File Ownership Matrix

| File / Directory | Architect | Implementer | Verifier | Memory | Orchestrator |
|---|---|---|---|---|---|
| `TASK.md` | W | R | R | R | W |
| `AGENTS.md` | W | R | R | R | R |
| `MEMORY.md` | R | R | R | W | R |
| `FAILURES.md` | R | R | W | R | R |
| `WORKLOG.md` | W | W | W | W | R |
| `src/` | R | W | R | R | R |
| `tests/` | R | R | W | R | R |
| `scripts/` | W | R | W | R | R |
| `migrations/` | R | W | R | R | R |

`W` = Write, `R` = Read-only

---

## 6. Communication Conventions

- **All log entries** must include: timestamp (ISO 8601), phase number, agent role, and a one-line description
- **Failures** must include: error class, traceback snippet (≤10 lines), file + line number, and proposed fix
- **Memory entries** must include: pattern name, trigger condition, recommended action
- **No agent** may silently swallow errors — all exceptions go to `FAILURES.md`
- **No agent** may modify files outside its ownership matrix without explicit Orchestrator approval logged in `WORKLOG.md`

---

## 7. Stopping Criteria

The agentic loop halts (and waits for human review) when:

1. Phase 4 gate is passed and `WORKLOG.md` contains `PASS phase=4`
2. Three consecutive failures on the same phase without a matching `MEMORY.md` fix
3. Any `FAILURES.md` entry with severity `CRITICAL`
4. `TASK.md` status is set to `COMPLETE`

---

## 8. Quick Reference Commands

```bash
# Run verifier for a specific phase
bash scripts/verify.sh --phase 2

# Summarize latest failure
bash scripts/summarize_failure.sh

# Run full suite
make test

# Generate sample data
make generate

# Check current task
cat TASK.md

# Review memory
cat MEMORY.md

# Check failures
cat FAILURES.md
```
