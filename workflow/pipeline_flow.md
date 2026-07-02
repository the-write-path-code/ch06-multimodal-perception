# Multimodal Perception Ingestion & Retrieval Workflows

This document details the operational workflows of the multimodal perception layer using Mermaid diagrams and pipeline specifications. Each diagram maps to specific Chapter 6 sections and can be rendered in any Mermaid-compatible viewer (GitHub, VS Code, Obsidian, etc.).

---

## 1. End-to-End Ingestion Pipeline Workflow

> **Chapter Reference:** Sections 6.1, 6.3, 6.4, 6.5

This workflow represents the ingestion of documents of various modalities (PDF, PNG, CSV, WAV) through the perception extractors, embeddings, PII scanners, handoff verifiers, SQLite registries, and the Qdrant vector database.

```mermaid
graph TD
    %% Source File Input
    A["Source File Path"] --> B{"Mime Type / Extension Dispatcher"}
    
    %% Routing logic
    B -->|PDF| C1["PDF Layout Parser<br/>Docling + pypdfium2"]
    B -->|Image| C2["VLM Image Schema Parser<br/>NVIDIA NIM / Gemini / Ollama"]
    B -->|Table| C3["Pandas CSV Profiler<br/>Schema + Distribution Analysis"]
    B -->|Audio| C4["Whisper Audio Transcriber<br/>faster-whisper local model"]
    
    %% Processing and extraction
    C1 -->|"Text & Tables"| D1["PerceptionChunk<br/>text + metadata"]
    C1 -->|"Figures & Charts"| D2["Cropped Image Parts<br/>pypdfium2 coordinate crop"]
    D2 -->|"VLM Analysis"| D1
    
    C2 -->|"JSON Schema Extraction"| D1
    C3 -->|"Natural Language Profile Anchor"| D1
    C4 -->|"Transcription text + VLM Summary"| D1
    
    %% PII Scan
    D1 --> E["Sensitivity Redactor<br/>GLiNER NER + Regex Heuristics"]
    E --> F["PII Tagged & Redacted Chunk"]
    
    %% Embedding Step
    F --> G1["CLIP Dense Encoder<br/>clip-ViT-B-32 → 512d vector"]
    F --> G2["SPLADE Sparse Encoder<br/>Splade_PP_en_v1"]
    
    %% SQLite registry
    G1 & G2 --> H["Asset Registry<br/>SQLite Database"]
    
    %% Downstream validation
    H --> I{"Handoff Contract Verifier<br/>(Section 6.5)"}
    
    %% Action decisions
    I -->|"Confidence ≥ 0.85<br/>PII = False"| J1["✅ Mark VALID"]
    I -->|"Confidence < 0.50<br/>or PII = True"| J2["⚠️ Mark REVIEW"]
    
    %% Indexing
    J1 --> K["Index Vectors into<br/>Qdrant Collection"]
    K --> L["Update Chunk Table<br/>with Qdrant Point ID"]
    J2 --> M["Hold in Registry<br/>Review Queue<br/>Skip Indexing"]

    %% Styling
    style A fill:#6366f1,color:#fff,stroke:#4f46e5
    style B fill:#1e293b,color:#f1f5f9,stroke:#334155
    style J1 fill:#16a34a,color:#fff,stroke:#15803d
    style J2 fill:#ea580c,color:#fff,stroke:#c2410c
    style K fill:#2563eb,color:#fff,stroke:#1d4ed8
    style M fill:#dc2626,color:#fff,stroke:#b91c1c
```

### Key Design Decisions

| Decision | Rationale |
|---|---|
| **Layout-guided PDF extraction** | Docling identifies text vs. figure zones structurally, avoiding blind OCR on charts |
| **VLM timeout = 15 seconds** | Prevents pipeline hangs when cloud APIs are slow; triggers mock fallback for sample files |
| **PII scan before embedding** | Ensures sensitive data never enters the vector index |
| **Confidence-gated indexing** | Low-confidence chunks go to human review queue, not Qdrant |

---

## 2. Cross-Modal Search & Retrieval Workflow

> **Chapter Reference:** Section 6.4

This workflow displays the hybrid search retrieval, combining CLIP dense, SPLADE sparse, Reciprocal Rank Fusion (RRF), and SQL metadata joins to yield enriched assets.

```mermaid
graph TD
    %% Query Inputs
    UserQuery["User Query<br/>text and/or image"] --> QueryDispatcher{"Query Type Router"}
    
    %% Text route
    QueryDispatcher -->|Text| TextEncoder["Text Query Encoders"]
    TextEncoder --> DenseText["CLIP Dense Vector<br/>512 dimensions"]
    TextEncoder --> SparseText["SPLADE Sparse Vector<br/>keyword weights"]
    
    %% Image route
    QueryDispatcher -->|Image| ImageEncoder["CLIP Image Encoder"]
    ImageEncoder --> DenseImage["CLIP Dense Vector<br/>512 dimensions"]
    
    %% Qdrant Query
    DenseText & SparseText & DenseImage --> QdrantSearch["Qdrant Search Request"]
    
    %% Fusion and Filtering
    QdrantSearch --> PrefetchDense["Prefetch: Dense Search<br/>Cosine Similarity"]
    QdrantSearch --> PrefetchSparse["Prefetch: Sparse Search<br/>Dot Product"]
    
    %% Modality filtering
    PrefetchDense & PrefetchSparse --> FilterModality["Apply Modality Filter<br/>if requested"]
    
    %% Fusion
    FilterModality --> RRFFusion["Reciprocal Rank Fusion<br/>RRF Score Merge"]
    
    %% Registry join
    RRFFusion --> MatchPoints["Retrieve Point IDs & Scores"]
    MatchPoints --> RegistryLookup["SQLite Registry Lookup<br/>SELECT * WHERE qdrant_point_id = ?"]
    
    %% Enriched results
    RegistryLookup --> JoinOutput["Assemble Enriched<br/>Search Results"]

    %% Styling
    style UserQuery fill:#6366f1,color:#fff,stroke:#4f46e5
    style RRFFusion fill:#9333ea,color:#fff,stroke:#7e22ce
    style JoinOutput fill:#16a34a,color:#fff,stroke:#15803d
```

### Hybrid Search Details

| Component | Model | Dimensionality | Similarity Metric |
|---|---|---|---|
| Dense encoder | `clip-ViT-B-32` | 512 | Cosine |
| Sparse encoder | `Splade_PP_en_v1` | Variable | Dot Product |
| Fusion | Reciprocal Rank Fusion | N/A | Score merge |

---

## 3. Gradio Explorer UI Workflow

> **Chapter Reference:** Section 6.5 (Interactive Demonstration)

This workflow shows how the Gradio web application orchestrates the full pipeline lifecycle — from startup auto-ingestion through interactive query, RAG answer synthesis, and result rendering.

```mermaid
graph TD
    %% Startup Phase
    Launch["python scripts/app.py"] --> EnvSetup["Load .env<br/>Force QDRANT_URL = :memory:"]
    EnvSetup --> InitPipeline["Initialize PerceptionPipeline<br/>+ Qdrant collection<br/>+ SQLite registry"]
    InitPipeline --> AutoIngest["Auto-Ingest Sample Documents"]
    
    %% Ingestion subflow
    AutoIngest --> IngestPDF["📄 patient_care_protocol.pdf"]
    AutoIngest --> IngestIMG["🖼️ insurance_card_front.png"]
    AutoIngest --> IngestCSV["📊 home_health_visits.csv"]
    AutoIngest --> IngestWAV["🎙️ nurse_visit_note_001.wav"]
    
    IngestPDF & IngestIMG & IngestCSV & IngestWAV --> PipelineRun["Full Pipeline<br/>Extract → Embed → Verify → Index"]
    PipelineRun --> Ready["✅ Dashboard Ready<br/>Browser auto-opens"]
    
    %% User interaction
    Ready --> UserAction{"User Interaction"}
    
    UserAction -->|"Text Query"| TextSearch["Encode text → Hybrid Search<br/>→ RRF Fusion"]
    UserAction -->|"Image Upload"| ImageSearch["Encode image → Dense Search"]
    UserAction -->|"Re-index"| Reindex["Wipe Qdrant → Re-ingest All"]
    
    %% RAG Answer
    TextSearch --> RAGAnswer["✨ Generate AI Answer<br/>VLM synthesizes context<br/>from top-K results"]
    TextSearch --> RenderResults["Render Ranked Cards<br/>+ Thumbnails<br/>+ Extracted Schemas"]
    ImageSearch --> RenderResults
    
    RAGAnswer --> FinalDisplay["Display Answer Panel<br/>+ Ranked Results"]
    RenderResults --> FinalDisplay
    
    Reindex --> Ready

    %% Styling
    style Launch fill:#6366f1,color:#fff,stroke:#4f46e5
    style Ready fill:#16a34a,color:#fff,stroke:#15803d
    style RAGAnswer fill:#1e1b4b,color:#a5b4fc,stroke:#4f46e5
    style FinalDisplay fill:#0f172a,color:#f1f5f9,stroke:#334155
```

---

## 4. VLM Client Failover Strategy

> **Chapter Reference:** Section 6.3

This diagram shows how the VLM client routes requests through multiple backends with timeout handling and mock fallbacks.

```mermaid
graph TD
    Request["analyze_image(prompt, image)"] --> Router{"VLM Backend Router"}
    
    Router -->|"USE_LOCAL_VLM=True"| Ollama["Local Ollama<br/>LLaVA model"]
    Router -->|"NVIDIA_API_KEY set"| NVIDIA["NVIDIA NIM API<br/>llama-3.2-11b-vision-instruct<br/>timeout: 15s"]
    Router -->|"GEMINI_API_KEY set"| Gemini["Google Gemini<br/>gemini-2.0-flash"]
    
    Ollama --> Success["✅ Return Parsed Response"]
    NVIDIA --> Success
    Gemini --> Success
    
    NVIDIA -->|"TimeoutException"| Fallback{"Mock Fallback Check"}
    Gemini -->|"Exception"| Fallback
    Ollama -->|"Exception"| Fallback
    
    Fallback -->|"Known sample file"| MockResponse["📋 Return Mock Schema<br/>confidence = 1.0"]
    Fallback -->|"Unknown file"| RaiseError["❌ Raise Exception<br/>Pipeline marks as REVIEW"]
    
    MockResponse --> Success

    %% Styling
    style Request fill:#6366f1,color:#fff,stroke:#4f46e5
    style Success fill:#16a34a,color:#fff,stroke:#15803d
    style MockResponse fill:#eab308,color:#1e293b,stroke:#ca8a04
    style RaiseError fill:#dc2626,color:#fff,stroke:#b91c1c
```

### Timeout & Retry Policy

| Parameter | Value | Rationale |
|---|---|---|
| HTTP timeout | 15 seconds | Prevents pipeline hangs on slow cloud endpoints |
| Retry on timeout | **No** | `TimeoutException` fails immediately (no backoff loop) |
| Retry on HTTP 429 | **Yes** | Up to 3 attempts with exponential backoff (2s → 4s → 8s) |
| Mock fallback | Sample files only | Insurance card and nurse note return pre-configured schemas |

---
## Sec 6.1 image

```
graph TD
    subgraph P1[" "]
    direction LR
    A["Source File"] --> B{"Format<br/>Dispatcher"}
    B -->|PDF/Image/Table/Audio| C["Format Parsers<br/>Docling · VLM · Pandas · Whisper"]
    C --> D["PerceptionChunk<br/>(text + metadata)"]
    D --> E["PII Redactor<br/>GLiNER + Regex"]
    E --> F["Tagged Chunk"]
    end

    subgraph P2[" "]
    direction LR
    G["Dual Encoders<br/>CLIP + SPLADE"] --> H["Asset Registry<br/>(SQLite)"]
    H --> I{"Contract<br/>Verifier"}
    I -->|Conf ≥0.85, PII=False| J1["✅ VALID"]
    I -->|Conf <0.50 or PII=True| J2["⚠️ REVIEW"]
    J1 --> K["Index in Qdrant<br/>+ Update Chunk Table"]
    J2 --> M["Review Queue<br/>(Skip Indexing)"]
    end

    P1 --> P2

    style A fill:#6366f1,color:#fff,stroke:#4f46e5
    style B fill:#1e293b,color:#f1f5f9,stroke:#334155
    style J1 fill:#16a34a,color:#fff,stroke:#15803d
    style J2 fill:#ea580c,color:#fff,stroke:#c2410c
    style K fill:#2563eb,color:#fff,stroke:#1d4ed8
    style M fill:#dc2626,color:#fff,stroke:#b91c1c
    style P1 fill:transparent,stroke:transparent
    style P2 fill:transparent,stroke:transparent

```
