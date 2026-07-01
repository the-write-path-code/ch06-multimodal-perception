# TASK.md — Current Phase and Task Tracker

> **Owned by:** Orchestrator Agent
> **Read by:** All agents at the start of every loop iteration
> **Rules:** Only the Orchestrator Agent advances the `CURRENT_PHASE`. Implementer and Verifier agents read this file to understand scope.

---

## Current State

```
CURRENT_PHASE : 1
PHASE_STATUS  : IN_PROGRESS
LAST_UPDATED  : 2026-06-30T22:00:00-04:00
UPDATED_BY    : Orchestrator
```

---

## Phase Definitions

### Phase 0 — Foundation Scaffolding
**Status:** `COMPLETE`
**Gate:** `uv sync` succeeds; all top-level config files present
**Deliverables:**
- [x] `pyproject.toml` with all dependencies
- [x] `.python-version` pinned to 3.12
- [x] `.env.example` with all required keys
- [x] `Makefile` with phase-based targets
- [x] `docker-compose.yml` (Qdrant + PostgreSQL)
- [x] `src/ch6_multimodal_perception/__init__.py`
- [x] `AGENTS.md`, `TASK.md`, `VERIFY.md`, `MEMORY.md`, `FAILURES.md`, `WORKLOG.md`
- [x] `scripts/verify.sh`, `scripts/summarize_failure.sh`

**Verification command:**
```bash
bash scripts/verify.sh --phase 0
```

---

### Phase 1 — Configuration + Data Models
**Status:** `IN_PROGRESS`
**Section mapping:** 6.1 Perception Foundations
**Gate:** `uv run pytest tests/test_phase1_config.py -v` all green

**Deliverables:**
- [ ] `src/ch6_multimodal_perception/config.py` — pydantic-settings Settings class
- [ ] `src/ch6_multimodal_perception/models.py` — Pydantic models for all 4 modalities
- [ ] `src/ch6_multimodal_perception/logging_config.py` — structlog setup
- [ ] `tests/conftest.py` — shared fixtures
- [ ] `tests/test_phase1_config.py` — config + model tests

**Implementer notes:**
- `config.py` is already committed; verify it passes its test
- Models must define `ModalityType` enum: `PDF | IMAGE | TABLE | AUDIO`
- All models inherit from `PerceptionChunk` base with `id`, `modality`, `source_path`, `created_at`
- Use `pydantic.BaseModel` with `model_config = ConfigDict(frozen=True)`

**Verification command:**
```bash
bash scripts/verify.sh --phase 1
```

---

### Phase 2 — Perception Extractors
**Status:** `BLOCKED` (Phase 1 must be COMPLETE)
**Section mapping:** 6.2 PDF Grounded Extraction, 6.3 Vision-Language Models, 6.4 Tabular + Audio
**Gate:** `uv run pytest tests/test_phase2_extractors.py -v` all green

**Deliverables:**
- [ ] `src/ch6_multimodal_perception/extractors/__init__.py`
- [ ] `src/ch6_multimodal_perception/extractors/pdf_extractor.py` — Docling + GLiNER NER
- [ ] `src/ch6_multimodal_perception/extractors/image_extractor.py` — SmolVLM structured extraction
- [ ] `src/ch6_multimodal_perception/extractors/table_extractor.py` — Pandas + schema detection
- [ ] `src/ch6_multimodal_perception/extractors/audio_extractor.py` — Whisper transcription
- [ ] `src/ch6_multimodal_perception/data_generator.py` — synthetic sample data for all 4 modalities
- [ ] `tests/test_phase2_extractors.py`

**Implementer notes:**
- Each extractor must be `async def extract(source: Path, settings: Settings) -> list[PerceptionChunk]`
- PDF extractor: use `docling` for layout-aware parsing; run GLiNER for entity spans; band-crop strategy for tables in PDFs
- Image extractor: load with Pillow, pass to VLM with structured prompt, parse JSON output
- Table extractor: detect schema automatically, emit one chunk per row-group (max 50 rows)
- Audio extractor: run Whisper, segment by sentence, map timestamps
- `data_generator.py` must produce: 3 PDFs, 5 images, 3 CSVs, 2 audio WAV files with ground-truth JSON

**Verification command:**
```bash
bash scripts/verify.sh --phase 2
```

---

### Phase 3 — Embeddings + Retrieval
**Status:** `BLOCKED` (Phase 2 must be COMPLETE)
**Section mapping:** 6.5 Cross-Modal RAG Retrieval
**Gate:** `uv run pytest tests/test_phase3_retrieval.py -v` all green

**Deliverables:**
- [ ] `src/ch6_multimodal_perception/embeddings.py` — dense (jina-v3) + sparse (SPLADE) hybrid
- [ ] `src/ch6_multimodal_perception/retrieval.py` — Qdrant upsert + hybrid search
- [ ] `tests/test_phase3_retrieval.py`

**Implementer notes:**
- `embed_chunks(chunks, settings)` returns `list[EmbeddedChunk]` with `dense_vector` and `sparse_vector`
- Qdrant collection names come from `settings.qdrant_collection_*`
- Hybrid alpha: `settings.hybrid_alpha` (0.7 dense, 0.3 sparse by default)
- Must support cross-modal retrieval: query against all 4 collections, merge by score

**Verification command:**
```bash
bash scripts/verify.sh --phase 3
```

---

### Phase 4 — Pipeline Orchestration + Handoff Contracts
**Status:** `BLOCKED` (Phase 3 must be COMPLETE)
**Section mapping:** 6.5 Cross-Modal RAG Retrieval (pipeline integration)
**Gate:** `uv run pytest tests/test_phase4_pipeline.py -v` all green

**Deliverables:**
- [ ] `src/ch6_multimodal_perception/pipeline.py` — async orchestrator
- [ ] `src/ch6_multimodal_perception/main.py` — CLI entry point
- [ ] `migrations/env.py` + `alembic.ini` — DB migration setup
- [ ] `tests/test_phase4_pipeline.py`

**Implementer notes:**
- `Pipeline.run(source_dir, query)` is the top-level coroutine
- Handoff contract: each stage returns a typed dataclass, never a raw dict
- Stage order: Detect → Extract → Embed → Upsert → Retrieve → Rerank → Return
- All stages run concurrently per-file using `anyio.create_task_group()`
- `main.py` exposes `ch6-pipeline` and `ch6-generate` CLI commands

**Verification command:**
```bash
bash scripts/verify.sh --phase 4
```

---

### Phase 5 — Polish + Documentation
**Status:** `BLOCKED` (Phase 4 must be COMPLETE)
**Gate:** README complete; notebook runs end-to-end without error

**Deliverables:**
- [ ] `README.md` — full Chapter 6 walkthrough with section mapping
- [ ] `notebooks/ch6_demo.ipynb` — end-to-end demo notebook
- [ ] `PROMPT_AGENT.md` — reusable agent prompt for building this repo from scratch

**Verification command:**
```bash
bash scripts/verify.sh --phase 5
```

---

## Advancement Log

| Timestamp | From Phase | To Phase | Agent | Reason |
|-----------|-----------|---------|-------|--------|
| 2026-06-30T22:00:00-04:00 | — | 0 | Orchestrator | Initial repo scaffolding started |
| 2026-06-30T22:10:00-04:00 | 0 | 1 | Orchestrator | Phase 0 scaffolding committed; config.py started |
