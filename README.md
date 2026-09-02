# Chapter 6: Multimodal Perception

Companion code for *Building Safe Agentic AI for Enterprise Systems* by Mohit Aggarwal.

This repository builds a multimodal ingestion and retrieval pipeline for PDFs, images, tables, and audio. Each input becomes a typed `PerceptionChunk` that carries source provenance, structured extraction, confidence, and personally identifiable information (PII) status through embedding, validation, and indexing.

The design does not let raw model output move directly into the retrieval layer. A chunk is scanned, typed, and checked at a handoff boundary before it can enter Qdrant. Low-confidence or PII-flagged chunks are held for review instead of indexed.

## What You Will Run

| Chapter section | Demonstration | What it shows |
| --- | --- | --- |
| 6.1 | Typed perception contract | PDFs, images, tables, and audio produce one `PerceptionChunk` contract rather than unrelated free-form outputs. |
| 6.2 | Multimodal ingestion | A dispatcher routes each source file to its extractor, then the pipeline embeds, verifies, registers, and conditionally indexes each chunk. |
| 6.3 | Vision-language model routing | NVIDIA NIM, Google Gemini, and local Ollama paths, with timeouts and sample-file mock fallbacks. |
| 6.4 | Cross-modal retrieval | CLIP dense embeddings, SPLADE sparse embeddings, Qdrant retrieval, and reciprocal rank fusion (RRF). |
| 6.5 | Deterministic handoffs | Confidence and PII checks decide whether a chunk enters the vector index or the review queue. |

The sample documents are synthetic. They exist to exercise extraction, retrieval, and safety boundaries without exposing clinical records.

## Production Warning

The PII scan is a control layer, not proof that every sensitive value was found. The pipeline blocks chunks it flags before indexing, but a missed entity remains possible. Do not treat the sample application or its scanner results as authorization to index unreviewed protected health information (PHI) in a production vector store.

The Explorer UI forces an in-memory Qdrant collection. It is a local demonstration path, not a durable deployment configuration. Use the configured Qdrant service and a documented retention policy before processing real operational data.

## Prerequisites

- Git
- [uv](https://docs.astral.sh/uv/)
- Python 3.12
- At least one vision-language model (VLM) backend: NVIDIA NIM, Google Gemini, or local Ollama with LLaVA
- Docker, optional, only if you want the local Qdrant and PostgreSQL services
- Additional disk space for local models and Whisper audio-transcription weights

The repository includes mock responses for selected sample documents. The Explorer UI can demonstrate the pipeline without a working cloud VLM key, but a real backend is needed to process new, arbitrary files.

## Quick Start

### 1. Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Clone and synchronize the repository

```bash
git clone https://github.com/the-write-path-code/ch06-multimodal-perception.git
cd ch06-multimodal-perception
uv sync
```

The repository includes `uv.lock` and `.python-version`. Run `uv sync` after pulling changes so the local environment matches the committed dependency set.

### 3. Create local configuration

```bash
cp .env.example .env
```

Choose one VLM backend in `.env`:

| Backend | Required setting | When to use it |
| --- | --- | --- |
| NVIDIA NIM | `NVIDIA_API_KEY` | Hosted VLM path through NVIDIA's API catalog |
| Google Gemini | `GEMINI_API_KEY` | Hosted Gemini VLM path |
| Ollama with LLaVA | `USE_LOCAL_VLM=True` and `LOCAL_VLM_MODEL=llava` | Local model path; requires a running Ollama service and installed model |

### 4. Generate sample data

```bash
uv run python scripts/generate_samples.py
```

The script creates synthetic PDF, image, CSV, and audio inputs in the sample-data directory.

### 5. Launch the Explorer UI

```bash
PYTHONPATH=src uv run python scripts/app.py
```

The Gradio Explorer starts locally and ingests the sample documents through the full pipeline. It uses in-memory Qdrant for this path, so no external Qdrant service is required for the first run.

## Configuration

The root `.env.example` documents all settings. The groups below are the ones readers are most likely to change.

### Pipeline and confidence controls

| Variable | Default | Purpose |
| --- | ---: | --- |
| `PIPELINE_CONCURRENCY` | `5` | Maximum active chunk-processing tasks |
| `HIGH_CONFIDENCE_THRESHOLD` | `0.85` | Minimum confidence for the valid indexing path when no PII is detected |
| `LOW_CONFIDENCE_THRESHOLD` | `0.50` | Lower confidence boundary used by the review path |
| `VLM_CROP_STRATEGY` | `zonecrop` | Strategy for PDF figure and layout-zone extraction |

### VLM backends

| Variable | Purpose |
| --- | --- |
| `NVIDIA_API_KEY` | NVIDIA NIM API credential |
| `NVIDIA_VLM_MODEL` | NVIDIA-hosted VLM model name |
| `GEMINI_API_KEY` | Google Gemini API credential |
| `USE_LOCAL_VLM` | Enables the local Ollama path |
| `LOCAL_VLM_MODEL` | Local model name, `llava` by default |
| `OLLAMA_HOST` | Ollama endpoint, normally `http://localhost:11434` |

### Storage and retrieval

| Variable | Purpose |
| --- | --- |
| `QDRANT_URL` | Optional Qdrant service URL |
| `QDRANT_API_KEY` | Credential for Qdrant Cloud or a protected remote service |
| `QDRANT_COLLECTION` | Qdrant collection name |
| `REGISTRY_DB_PATH` | SQLite asset-registry location |
| `DENSE_EMBEDDING_MODEL` | Dense cross-modal embedding model, `clip-ViT-B-32` by default |
| `ENABLE_SPARSE_EMBEDDINGS` | Enables sparse embedding generation |
| `WHISPER_MODEL_SIZE` | Local Whisper model size for audio transcription |

> **Tip**
>
> Leave `QDRANT_URL` unset for the Explorer UI. The UI forces in-memory Qdrant for a clean demonstration run regardless of the URL in `.env`.

## Run the Chapter Demonstrations

### 1. Run the Interactive Explorer, Sections 6.1 through 6.5

```bash
PYTHONPATH=src uv run python scripts/app.py
```

On startup, the Explorer:

1. Initializes a local in-memory Qdrant collection.
2. Ingests the generated sample PDF, image, table, and audio files.
3. Extracts typed `PerceptionChunk` records.
4. Scans and redacts flagged PII before the index boundary.
5. Embeds valid chunks and indexes only those that pass the handoff contract.
6. Opens a Gradio interface for text, image, and filtered retrieval.

Try the supplied example queries after ingestion. The results should show the source file, modality, relevance score, structured extraction, and metadata for each returned chunk.

### 2. Run the Headless Ingestion Pipeline, Sections 6.2 and 6.5

Use the pipeline runner when you want ingestion results without the Explorer UI:

```bash
PYTHONPATH=src uv run python scripts/run_pipeline.py
```

The pipeline dispatches files by extension and MIME type. It processes chunks concurrently, subject to `PIPELINE_CONCURRENCY`, then writes records to the SQLite asset registry. Only chunks that pass the handoff verifier receive a Qdrant point identifier.

### 3. Run the Local VLM Path, Section 6.3

Start Ollama in a separate terminal and install the configured model:

```bash
ollama serve
ollama pull llava
```

Set the local backend in `.env`:

```dotenv
USE_LOCAL_VLM=True
LOCAL_VLM_MODEL=llava
OLLAMA_HOST=http://localhost:11434
```

Then rerun the Explorer or headless pipeline. Local VLM output is still subject to the same schema, confidence, PII, and handoff checks as hosted output.

### 4. Run Persistent Local Services, Optional

The `docker-compose.yml` file provides Qdrant and PostgreSQL for local development. Start the core services with:

```bash
docker compose up -d
```

The optional pgAdmin interface is supplied through the `tools` profile:

```bash
docker compose --profile tools up -d
```

Use this path only when you need persistent local services outside the Explorer UI. The Explorer's in-memory mode does not use the Docker Qdrant service.

## Expected Results

The four extractor paths return a common `PerceptionChunk` shape, including:

- A deterministic chunk ID.
- The source file and extraction provenance.
- A known modality: PDF, image, table, or audio.
- Structured extraction data.
- A confidence value from 0.0 through 1.0.
- Metadata, including the PII-detected flag.

The handoff verifier makes the indexing decision:

| Handoff result | Condition | Action |
| --- | --- | --- |
| `VALID` | Confidence is at least `0.85` and PII is not detected | Index the chunk in Qdrant and record its point ID in SQLite |
| `REVIEW` | Confidence is low or PII is detected | Keep the chunk in the registry review path and do not index it |

A failed extraction of one file should not stop an entire batch. The dispatcher logs the file-level error and returns no chunks for that file, allowing the remaining sources to continue through the pipeline.

## Run the Tests

```bash
uv run pytest
```

Run the test suite before changing extraction schemas, confidence thresholds, PII handling, concurrency limits, backend routing, or index behavior. The tests should establish that:

- Extractors return typed chunk contracts.
- Modality dispatch selects the expected extractor.
- Confidence values remain within their allowed range.
- PII-flagged chunks do not enter Qdrant.
- Re-ingesting the same source uses deterministic IDs and updates the registry rather than creating unbounded duplicates.
- Bounded concurrency prevents a large document from starting an unbounded number of active extraction tasks.

## Repository Layout

```text
.
├── README.md
├── pyproject.toml
├── uv.lock
├── .python-version
├── .env.example
├── docker-compose.yml                # Optional Qdrant, PostgreSQL, and pgAdmin services
├── data/
│   ├── samples/                      # Generated synthetic source documents
│   └── registry.db                   # Local SQLite registry, created at runtime
├── src/ch06/
│   ├── config.py                     # Pydantic settings and environment loading
│   ├── models.py                     # PerceptionChunk and typed contracts
│   ├── pipeline.py                   # Ingestion orchestration and bounded concurrency
│   ├── perception/
│   │   ├── dispatcher.py             # Extension and MIME-type routing
│   │   ├── pdf.py                    # Docling and layout-guided PDF extraction
│   │   ├── image.py                  # Structured image VLM extraction
│   │   ├── table.py                  # CSV and spreadsheet profiling
│   │   ├── audio.py                  # Whisper transcription and VLM extraction
│   │   ├── sensitivity.py            # GLiNER and regex PII scanning
│   │   └── vlm_client.py             # NVIDIA, Gemini, and Ollama routing
│   ├── embedding/
│   │   ├── dense.py                  # CLIP dense cross-modal embeddings
│   │   └── sparse.py                 # SPLADE sparse embeddings
│   ├── retrieval/
│   │   ├── registry.py               # SQLite asset registry
│   │   ├── store.py                  # Qdrant retrieval and RRF fusion
│   │   └── query.py                  # Text and image query service
│   └── contracts/
│       └── handoff.py                # Confidence and PII handoff verifier
├── scripts/
│   ├── generate_samples.py
│   ├── app.py                        # Gradio Explorer entry point
│   └── run_pipeline.py               # Headless ingestion runner
├── workflow/
│   └── pipeline_flow.md              # Mermaid diagrams and system workflows
└── tests/
```

## Architecture Diagrams and Supporting Documents

The `workflow/` directory contains the diagrams used in Chapter 6:

- End-to-end multimodal ingestion.
- Cross-modal retrieval with CLIP, SPLADE, Qdrant, and RRF.
- Explorer UI startup, ingestion, search, and re-indexing.
- VLM backend routing and timeout handling.
- The handoff decision between `VALID` indexing and `REVIEW` containment.

Read the ingestion diagram before modifying the pipeline. The ordering matters: PII scanning occurs before embedding and vector indexing, and handoff verification occurs before a chunk receives a Qdrant point ID.

## Safety and Operational Limits

- The sample documents are synthetic. Do not substitute real patient files, addresses, insurance cards, or clinical audio without a reviewed data-handling design.
- GLiNER and regex scanning can miss sensitive entities. PII detection is not a coverage guarantee.
- A chunk marked `REVIEW` stays in the registry and out of Qdrant. Do not bypass that result by indexing it manually.
- The default VLM timeout is 15 seconds. Timeout and backend error behavior should remain visible in logs and typed results rather than being converted to empty successful output.
- Sample-file mock fallbacks support demonstrations. They are not a substitute for a working VLM path on new documents.
- The pipeline limits concurrent chunk processing. Do not remove the semaphore to accelerate a large batch without measuring the effect on memory, model quotas, and Qdrant load.

## Troubleshooting

### The Explorer does not start

Confirm that dependencies were synchronized and the source path is present:

```bash
uv sync
PYTHONPATH=src uv run python scripts/app.py
```

### The VLM backend is unavailable

Check the selected backend in `.env`. For Ollama, confirm that the service is running and that the configured local model is installed. For hosted providers, verify the corresponding API key and model name.

The Explorer can return mock output for selected sample files. New files need a working backend.

### Qdrant connection fails

The Explorer uses in-memory Qdrant. Remove or ignore `QDRANT_URL` for that path. For persistent local Qdrant, run:

```bash
docker compose up -d
```

Then verify the configured URL and port.

### A chunk is not searchable

Inspect its registry record and handoff result. Low confidence or detected PII routes a chunk to `REVIEW`, which intentionally prevents vector indexing.

### Audio extraction is slow

Whisper downloads and loads its model on first use. Reduce `WHISPER_MODEL_SIZE` only after checking the trade-off between throughput and transcription quality for your workload.

## Related Chapters

- Chapter 3 establishes dense, sparse, hybrid, and vector-store retrieval patterns for text.
- Chapter 4 evaluates retrieval, grounding, sufficiency, and policy decisions after retrieval.
- Chapter 7 applies context boundaries to sensitive geospatial and staffing data.
- Chapter 9 combines perception, local context, specialist tools, and controlled downstream action in the Plant Doctor case study.
- Chapter 14 applies fail-closed and human-review controls to regulated data-processing workflows.

## License and Errata

See `LICENSE` for licensing terms. Report documentation or code issues through this repository's GitHub issue tracker.
