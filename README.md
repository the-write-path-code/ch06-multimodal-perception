# Chapter 6: Multimodal Ingestion & Perception Layer

This repository is the official enterprise technical companion to **Chapter 6: Multimodal Perception** from *The Write Path: Building Safe Agentic AI for Enterprise Systems*.

It provides an end-to-end asynchronous multimodal ingestion pipeline featuring layout-guided PDF extraction, standalone image VLM parsing, CSV tabular profiling, Whisper audio transcription, PII sensitivity scanning, CLIP dense cross-modal embeddings, SPLADE sparse keyphrase embeddings, SQLite metadata registry tracking, and Qdrant hybrid vector search with Reciprocal Rank Fusion (RRF).

> [!TIP]
> For detailed visual flows and architectural transition diagrams, see the [Workflow Diagrams](workflow/pipeline_flow.md).

---

## Quick Start

### Prerequisites

| Requirement | Notes |
|---|---|
| **Python 3.12+** | Tested on CPython 3.12 |
| **uv** | Fast Python package manager (`curl -LsSf https://astral.sh/uv/install.sh \| sh`) |
| **VLM API Key** | One of: NVIDIA NIM (free tier), Google Gemini, or local Ollama |

### 1. Clone & Install

```bash
git clone https://github.com/mohitagr18/ch6-multimodal-perception.git
cd ch6-multimodal-perception
uv sync
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and set **at least one** VLM backend:

| Variable | Description |
|---|---|
| `NVIDIA_API_KEY` | Free developer key from [build.nvidia.com](https://build.nvidia.com) |
| `GEMINI_API_KEY` | Google AI Studio key for Gemini VLM |
| `USE_LOCAL_VLM=True` | Use a local Ollama instance instead (requires `ollama pull llava`) |

> [!NOTE]
> If the NVIDIA or Gemini API is slow or unavailable, the pipeline activates built-in mock fallbacks for the included sample documents, so the Explorer UI always works out of the box.

### 3. Generate Sample Data

Creates synthetic clinical PDFs, insurance card PNGs, CSV billing tables, and nurse voice note WAVs:

```bash
uv run python scripts/generate_samples.py
```

### 4. Launch the Explorer UI

```bash
PYTHONPATH=src uv run python scripts/app.py
```

This starts a local Gradio web server on [http://127.0.0.1:7860](http://127.0.0.1:7860) and automatically opens your browser. On startup, it:
1. Initializes an **in-memory Qdrant** vector collection
2. Auto-ingests all sample documents through the full pipeline
3. Presents an interactive search dashboard

> [!IMPORTANT]
> The Explorer UI forces `QDRANT_URL=:memory:` regardless of your `.env` setting, so no external Qdrant server is needed.

---

## Interactive Explorer UI

The Gradio-powered **Multimodal Perception Explorer** (`scripts/app.py`) is the primary way to interact with the pipeline. It demonstrates the full Chapter 6 architecture in a single interface.

### Features

| Feature | Description |
|---|---|
| **Auto-Ingestion on Startup** | All sample documents are automatically ingested, extracted, embedded, and indexed when the app launches |
| **Text Query Search** | Ask natural language questions (e.g., *"What is the copay amount on the insurance card?"*) |
| **Image Similarity Search** | Upload an image crop to find visually similar indexed documents via CLIP embeddings |
| **Modality Filtering** | Filter results by type: PDF, Image, Audio, Table, or All |
| **AI Conversational Answer** | A synthesized final answer is generated from the top retrieved context using the VLM |
| **Extracted Schema Viewer** | Expand structured data tables showing parsed fields, entities, and metadata per result |
| **Document Sidebar** | Live tracker showing all ingested documents with modality badges |
| **Re-index Button** | Wipe the vector collection and rebuild the index from scratch |
| **Pre-configured Examples** | One-click example queries for quick testing |

### Example Queries to Try

| Query | Expected Top Result |
|---|---|
| *"What is the copay amount on the insurance card?"* | `insurance_card_front.png` — Copay: Office $20 / Specialist $40 |
| *"John Smith patient checkup visit"* | `nurse_visit_note_001.wav` — Audio transcription of nurse visit |
| *"Member ID HFP-98765432-01"* | `insurance_card_front.png` — Member ID match |
| *"Blood pressure reading"* | `nurse_visit_note_001.wav` — BP 140/90 clinical note |
| *"Ensure all treatments are completed"* | `patient_care_protocol.pdf` — Care protocol guideline |

---

## Architecture

### Codebase Layout

```
src/ch6/
├── config.py                 # Core Configuration Loader & Validator (Pydantic Settings)
├── logging.py                # Structured JSON Structlog Integration
├── models.py                 # Grounded Chunk & Handoff Schemas (Section 6.1 / 6.5)
│
├── perception/               # Section 6.1 & 6.3: Multi-modal Perception Layer
│   ├── vlm_client.py         # Unified NVIDIA NIM / Gemini / Ollama Cloud-Local VLM Router
│   ├── sensitivity.py        # GLiNER PII / PHI Redaction Scanner
│   ├── pdf.py                # Docling Layout-Guided Parser & Image Cropping
│   ├── image.py              # Standalone Image VLM Analyzer
│   ├── table.py              # Pandas Profiler & Natural Language Summary Anchor
│   ├── audio.py              # Whisper Audio Transcriber & VLM Text-Mode Analyzer
│   └── dispatcher.py         # Modality Extension Dispatcher Router
│
├── embedding/                # Section 6.4: Shared Cross-Modal Vector Space
│   ├── dense.py              # Sentence-Transformers CLIP Model Encoder (512d)
│   └── sparse.py             # SPLADE / BM42 Sparse Model Encoder (FastEmbed)
│
├── retrieval/                # Section 6.4: Asset Databases
│   ├── registry.py           # SQLite Local Asset Registry Database (aiosqlite)
│   └── store.py              # Qdrant Vector Catalog Client & RRF Search
│
├── contracts/                # Section 6.5: Human-in-the-Loop Safeguards
│   └── handoff.py            # Handoff Payload Contract Verifier
│
├── query.py                  # Unified Search Service (text + image queries)
└── pipeline.py               # Section 6.5: Pipeline Orchestrator (Semaphore bounded concurrency)

scripts/
├── app.py                    # Gradio Interactive Explorer UI
├── generate_samples.py       # Synthetic sample data generator
└── run_pipeline.py           # Headless CLI pipeline runner

workflow/
└── pipeline_flow.md          # Mermaid workflow diagrams (ingestion, retrieval, agentic loop, explorer)
```

### Chapter Section Mapping

| Chapter Section | Code Module | Description |
|---|---|---|
| 6.1 — Perception Extractors | `src/ch6/perception/` | Modality-specific document parsers (PDF, Image, Audio, Table) |
| 6.2 — Orchestration Config | `src/ch6/config.py` | Environment-driven configuration with Pydantic validation |
| 6.3 — VLM Integration | `src/ch6/perception/vlm_client.py` | Cloud/local VLM routing with timeout handling and mock fallbacks |
| 6.4 — Embedding & Retrieval | `src/ch6/embedding/`, `src/ch6/retrieval/` | CLIP dense + SPLADE sparse encoding, Qdrant hybrid search with RRF |
| 6.5 — Handoff Contracts | `src/ch6/contracts/handoff.py` | Confidence gating, PII flagging, human review queue |

---

## Core Components

### Layout-Guided PDF Parser (`perception/pdf.py`)
Uses **Docling** for layout structural zoning. Text zones are routed directly to natural text output. Image and chart zones are dynamically cropped from the PDF page using `pypdfium2` coordinates and sent to the cloud VLM for high-fidelity description.

### Sensitivity Redaction (`perception/sensitivity.py`)
Applies **GLiNER** (Generalist Named Entity Recognition) alongside robust regex heuristics to scan for PII/PHI (SSNs, phone numbers, names). Sensitive entities are replaced with `[REDACTED]` tags and flagged in chunk metadata.

### Standalone Image Extractor (`perception/image.py`)
Routes medical cards and document images to the VLM, enforcing a structured JSON response matching the `ImageAnalysisResult` Pydantic model.

### Audio Extractor (`perception/audio.py`)
Loads a local **Whisper** model to transcribe voice notes synchronously in a thread executor, then passes the transcription text to the VLM to yield narrative summaries and clinical actions.

### Table Profiler (`perception/table.py`)
Computes schema parameters (data types, missing value percentages, value distributions) over CSVs, formatting the output into a natural language text profile.

### VLM Client (`perception/vlm_client.py`)
Unified router supporting three VLM backends with automatic failover:
1. **NVIDIA NIM** — OpenAI-compatible HTTP calls to `meta/llama-3.2-11b-vision-instruct`
2. **Google Gemini** — Native `google-genai` SDK calls
3. **Local Ollama** — Self-hosted LLaVA for offline environments

The client enforces a **15-second timeout** with immediate failover (no retry loops on timeout), and includes **mock fallback responses** for sample documents to ensure the Explorer UI always functions regardless of API availability.

### Shared Cross-Modal Vector Space (`embedding/`)
Dense representations use `clip-ViT-B-32`, mapping both text and PIL Image crops to the same 512-dimensional space. Sparse term representations use SPLADE (`Splade_PP_en_v1`).

### Hybrid Search & Registry (`retrieval/`)
Cross-modal retrieval queries Qdrant using dense + sparse prefetch-level filtering, merging outputs with **Reciprocal Rank Fusion (RRF)**. Matched points are joined with the local **SQLite registry** for full audit tracking.

### Handoff Contract Verifier (`contracts/handoff.py`)
Implements the human-in-the-loop safety gate from Section 6.5:
- **VALID**: Confidence ≥ 0.85 and no PII detected → indexed into Qdrant
- **REVIEW**: Confidence < 0.50 or PII detected → held in SQLite review queue, skipped from vector indexing

---

## Sample Data

The `scripts/generate_samples.py` script creates the following synthetic clinical documents in `data/samples/`:

| File | Modality | Content |
|---|---|---|
| `patient_care_protocol.pdf` | PDF | Multi-page clinical care guidelines with text, tables, and embedded figures |
| `insurance_card_front.png` | Image | Synthetic insurance card with Member ID, Group Number, Payer ID, and Copay amounts |
| `home_health_visits.csv` | Table | Billing records with patient names, visit dates, CPT codes, and charges |
| `nurse_visit_note_001.wav` | Audio | 17-second nurse dictation: vitals, medications, and clinical observations |

---

## Running Tests

### Unit Test Suite
```bash
PYTHONPATH=src uv run pytest tests/ -v -k "not integration"
```

### Headless Pipeline Run
Ingests all sample files, processes through the full pipeline, and runs search queries from the CLI:
```bash
PYTHONPATH=src QDRANT_URL=:memory: uv run python scripts/run_pipeline.py
```

> [!IMPORTANT]
> The pipeline handles network/quota errors (like HTTP 429 Resource Exhausted) gracefully by routing failed extractions to a manual review queue in the SQLite registry database instead of halting ingestion.

---

## Workflow Diagrams

All architectural and operational workflows are documented with Mermaid diagrams in [`workflow/pipeline_flow.md`](workflow/pipeline_flow.md):

1. **End-to-End Ingestion Pipeline** — Document → Extraction → Embedding → Handoff → Qdrant
2. **Cross-Modal Search & Retrieval** — Query → Encode → Prefetch → RRF → Registry Join
3. **Gradio Explorer UI Flow** — Startup → Auto-Ingest → Search → RAG Answer → Render
---

## License

This project is part of the *The Write Path* book companion series. See the repository license for terms.
