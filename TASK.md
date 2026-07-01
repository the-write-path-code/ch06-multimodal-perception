# TASK.md — Multimodal Perception Development Tasks

Current Phase: 4 (Handoff Contracts & Full Pipeline)
Status: IN_PROGRESS

---

## Phase 0: Plan Presentation
- [x] Tech Stack selection and justifications
- [x] Architecture translation plan
- [x] Timesheet-OCR pattern mapping
- [x] Sample data strategy
- [x] Test strategy
- [x] User approval

## Phase 1: Foundation
- [x] Write `AGENTS.md` (Agent specifications)
- [x] Create tracking files: `TASK.md`, `MEMORY.md`, `FAILURES.md`, `WORKLOG.md`
- [x] Create `pyproject.toml` and `.python-version` (Python 3.12)
- [x] Install dependencies with `uv sync`
- [x] Create config validation system (`src/ch6/config.py`)
- [x] Create structured logging helper (`src/ch6/logging.py`)
- [x] Create core models (`src/ch6/models.py`)
- [x] Create `.env.example`
- [x] Create sample data generator (`scripts/generate_samples.py`)
- [x] Implement and run unit tests for configuration, models, logging, and samples

## Phase 2: Perception Layer (Sections 6.1 + 6.3)
- [x] VLM Interface Unified Client
- [x] PII sensitivity scanner
- [x] PDF extractor (Docling + direct text OCR + confidence fallback)
- [x] Image extractor (VLM + JSON schema enforcement)
- [x] Table extractor (Pandas profiler + NL summary anchor)
- [x] Audio extractor (Whisper + VLM structured summary)
- [x] Modality Dispatcher router
- [x] Perception tests (unit, mock, integration)

## Phase 3: Embedding & Retrieval Layer (Section 6.4)
- [x] Dense encoder (CLIP)
- [x] Sparse encoder (SPLADE)
- [x] Asset registry (SQLite backend)
- [x] Vector Catalog (Qdrant client + hybrid search + RRF)
- [x] Embedding + retrieval tests

## Phase 4: Handoff Contracts & Full Pipeline (Sections 6.2 + 6.5)
- [/] Handoff payload contract verification
- [/] Async pipeline orchestrator
- [ ] Query interface
- [ ] End-to-end tests

## Phase 5: Polish & Docs
- [ ] Chapter walkthrough Jupyter notebook
- [ ] Section mapping README
- [ ] Clean up and final verification
