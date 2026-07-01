# Chapter 6: Multimodal Ingestion & Perception Layer

This repository is the official enterprise technical companion to **Chapter 6: Multimodal Perception** from *The Write Path: Building Safe Agentic AI for Enterprise Systems*. 

It provides an end-to-end asynchronous multimodal ingestion pipeline featuring layout-guided PDF extraction, standalone image VLM parsing, CSV tabular profiling, Whisper audio transcription, PII sensitivity scanning, CLIP dense cross-modal embeddings, SPLADE sparse keyphrase embeddings, SQLite metadata registry tracking, and Qdrant hybrid vector search with Reciprocal Rank Fusion (RRF).

For detailed visual flows and architectural transition diagrams, see the [Ingestion & Retrieval Workflows](file:///Users/mohit/Documents/GitHub/ch6-multimodal-perception/workflow/pipeline_flow.md).

---

## 1. Architectural Mapping

The codebase is organized logically to align directly with the sections in Chapter 6:

```
src/ch6/
├── config.py                 # Core Configuration Loader & Validator (Pydantic Settings)
├── logging.py                # Structured JSON Structlog Integration
├── models.py                 # Grounded Chunk & Handoff Schemas (Section 6.1 / 6.5)
│
├── perception/               # Section 6.1 & 6.3: Multi-modal Perception Layer
│   ├── vlm_client.py         # Unified Gemini / Ollama Cloud-Local Router
│   ├── sensitivity.py        # GLiNER PII / PHI Redaction Scanner
│   ├── pdf.py                # Docling Layout-Guided Parser & Image Cropping
│   ├── image.py              # Standalone Image VLM Analyzer
│   ├── table.py              # Pandas Profiler & Natural Language Summary Anchor
│   ├── audio.py              # Whisper Audio Transcriber & VLM Text-Mode Analyzer
│   └── dispatcher.py         # Modality Extension Dispatcher Router
│
├── embedding/                # Section 6.4: Shared Cross-Modal Vector Space
│   ├── dense.py              # Sentence-Transformers CLIP Model Encoder
│   └── sparse.py             # SPLADE / BM42 Sparse Model Encoder (FastEmbed)
│
├── retrieval/                # Section 6.4: Asset Databases
│   ├── registry.py           # SQLite Local Asset Registry Database (aiosqlite)
│   └── store.py              # Qdrant Vector Catalog client & RRF search
│
├── contracts/                # Section 6.5: Human-in-the-Loop Safeguards
│   └── handoff.py            # Handoff Payload Contract Verifier
│
└── pipeline.py               # Section 6.5: Pipeline Orchestrator (Semaphore bounded concurrency)
```

---

## 2. Core Features & Modality Extractors

### Layout-Guided PDF Parser (`src/ch6/perception/pdf.py`)
Utilizes **Docling** for layout structural zoning. Text zones are routed directly to natural text output. Image and chart zones are dynamically cropped from the PDF page using `pypdfium2` coordinates and sent to the cloud VLM (`Gemini`) for high-fidelity description.

### Sensitivity Redaction (`src/ch6/perception/sensitivity.py`)
Applies **GLiNER** (Generalist Named Entity Recognition) alongside robust regex heuristics to scan for PII/PHI (such as Social Security Numbers, phone numbers, and names) in text. Sensitive entities are replaced with a `[REDACTED]` tag and flagged in the chunk metadata.

### Standalone Image Extractor (`src/ch6/perception/image.py`)
Routes medical card and guide images to the Gemini VLM model, enforcing a structured JSON response matching the `ImageAnalysisResult` Pydantic model. 

### Audio Extractor (`src/ch6/perception/audio.py`)
Loads a local **Whisper** model to transcribe voice notes synchronously in a thread executor, then passes the transcription text to the text-only Gemini API to yield narrative summaries and clinical actions.

### Table Profiler (`src/ch6/perception/table.py`)
Computes schema parameters (data types, missing value percentages, value distributions) over CSVs, formatting the output into a natural language text profile.

### Shared Cross-Modal Vector Space (`src/ch6/embedding/`)
Dense representations are computed using `clip-ViT-B-32`, mapping both text inputs and PIL Image crops to the same 512-dimension space. Sparse term representations are computed using SPLADE (`Splade_PP_en_v1`).

### Hybrid Search & Registry Database (`src/ch6/retrieval/`)
Enables cross-modal retrieval by querying Qdrant using dense + sparse prefetch-level filtering, merging the outputs using **Reciprocal Rank Fusion (RRF)**. It then joins the matched points with the local **SQLite registry** to reconstruct full audit tracking and structured data fields.

---

## 3. Agentic Loop Tracking

To support safe pair-programming and autonomous iteration in enterprise environments, this repository uses a **phase-gated agentic loop protocol**:

- `AGENTS.md`: Defines roles (Architect, Implementer, Verifier, Memory) and file ownership contracts.
- `TASK.md`: Lists the roadmap, roadmap phases, and task status.
- `WORKLOG.md`: Activity audit log of code and verification runs.
- `MEMORY.md`: Stores engineering lessons, gotchas, and reusable patterns.
- `FAILURES.md`: Logs error summaries and proposed resolutions.

---

## 4. Getting Started & Verification Runs

### Prerequisites
- **Python 3.12**
- **uv** (Package manager)
- **Google Gemini API Key** (optional, fallback to mock/local Ollama)

### Setup
```bash
# Clone the repository
git clone https://github.com/mohitagr18/ch6-multimodal-perception.git
cd ch6-multimodal-perception

# Sync virtual environment and dependencies
uv sync

# Copy env example and configure GEMINI_API_KEY
cp .env.example .env
```

### Running Verification Suite
The verifier runs unit and mock tests:
```bash
# Run pytest tests
PYTHONPATH=src uv run pytest tests/ -v -k "not integration"
```

### Generating Sample Data
Generates synthetic PDFs, medical card PNGs, CSV files, and voice WAV recordings:
```bash
uv run python scripts/generate_samples.py
```

### Executing Live End-to-End Pipeline
Ingests all generated sample files, processes them through Docling/Whisper/VLM, audits metadata, indexes into Qdrant in-memory catalog, and executes search queries:
```bash
PYTHONPATH=src QDRANT_URL=:memory: uv run python scripts/run_pipeline.py
```
> [!IMPORTANT]
> The pipeline handles network/quota errors (like HTTP 429 Resource Exhausted) gracefully by routing failed extractions to a manual review queue in the registry SQLite database instead of halting ingestion.