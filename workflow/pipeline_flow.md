# Multimodal Perception Ingestion & Retrieval Workflows

This document details the operational workflows of the multimodal perception layer using Mermaid diagrams and pipeline specifications.

---

## 1. End-to-End Ingestion Pipeline Workflow

This workflow represents the ingestion of documents of various modalities (PDF, PNG, CSV, WAV) through the perception extractors, embeddings, PII scanners, handoff verifiers, SQLite registries, and the Qdrant vector database.

```mermaid
graph TD
    %% Source File Input
    A[Source File Path] --> B{Mime Type / Extension Dispatcher}
    
    %% Routing logic
    B -->|PDF| C1[PDF Layout Parser Docling/pdfium2]
    B -->|Image| C2[VLM Image Schema Parser]
    B -->|Table| C3[Pandas CSV Profiler]
    B -->|Audio| C4[Whisper Audio Transcriber]
    
    %% Processing and extraction
    C1 -->|Text & Tables| D1[Text Chunks]
    C1 -->|Figures & Charts| D2[Cropped Image Parts]
    D2 -->|VLM Analysis| D1
    
    C2 -->|JSON Schema Extraction| D1
    C3 -->|Natural Language Profile Anchor| D1
    C4 -->|Transcription text + VLM Summary| D1
    
    %% PII Scan
    D1 --> E[Sensitivity Redactor GLiNER/Regex]
    E --> F[PII Tagged & Redacted Chunk]
    
    %% Embedding Step
    F --> G1[CLIP Dense Encoder 512d]
    F --> G2[SPLADE Sparse Encoder SPLADE++ v1]
    
    %% SQLite registry
    G1 & G2 --> H[Asset Registry SQLite Database]
    
    %% Downstream validation
    H --> I{Handoff Contract Verifier}
    
    %% Action decisions
    I -->|CONF >= 0.85 & PII=False| J1[Mark VALID]
    I -->|CONF < 0.50 or PII=True| J2[Mark REVIEW]
    
    %% Indexing
    J1 --> K[Index Vectors into Qdrant Collection]
    K --> L[Update Chunk Table with Qdrant Point ID]
    J2 --> M[Hold in Registry Review Queue - Skip Indexing]
```

---

## 2. Cross-Modal Search & Retrieval Workflow

This workflow displays the hybrid search retrieval, combining CLIP dense, SPLADE sparse, Reciprocal Rank Fusion (RRF), and SQL metadata joins to yield enriched assets.

```mermaid
graph TD
    %% Query Inputs
    UserQuery[User Query text / image] --> QueryDispatcher{Query Type}
    
    %% Text route
    QueryDispatcher -->|Text| TextEncoder[Text Query Encoders]
    TextEncoder --> DenseText[CLIP Dense Vector]
    TextEncoder --> SparseText[SPLADE Sparse Vector]
    
    %% Image route
    QueryDispatcher -->|Image| ImageEncoder[CLIP Image Encoder]
    ImageEncoder --> DenseImage[CLIP Dense Vector]
    
    %% Qdrant Query
    DenseText & SparseText & DenseImage --> QdrantSearch[Qdrant Search Request]
    
    %% Fusion and Filtering
    QdrantSearch --> PrefetchDense[Prefetch Dense Search]
    QdrantSearch --> PrefetchSparse[Prefetch Sparse Search]
    
    %% Modality filtering
    PrefetchDense & PrefetchSparse --> FilterModality[Apply Modality Filter if requested]
    
    %% Fusion
    FilterModality --> RRFFusion[Reciprocal Rank Fusion RRF]
    
    %% Registry join
    RRFFusion --> MatchPoints[Retrieve Point IDs & Scores]
    MatchPoints --> RegistryLookup[SQLite Registry Lookup SELECT * WHERE qdrant_point_id = ?]
    
    %% Enriched results
    RegistryLookup --> JoinOutput[Assemble Enriched Search Results]
```

---

## 3. Gated Agentic Loop State Transitions

This state diagram depicts the execution contracts and phase gates governing autonomous iteration within the repository.

```mermaid
stateDiagram-v2
    [*] --> Architect : Task Initialized
    
    Architect --> Implementer : TASK.md updated [ARCH] prefix
    note right of Architect
        Defines high-level schemas
        and structural boundaries
    end note
    
    Implementer --> Verifier : src/ files coded [IMPL] prefix
    note right of Implementer
        Writes modality parsers,
        sensitivity scans, and search pipelines
    end note
    
    state Verifier {
        [*] --> RunTests
        RunTests --> TestPass : All tests green
        RunTests --> TestFail : Any test fails
    }
    
    TestPass --> MemoryAgent : Pass phase=N
    TestFail --> SummarizeFailure : Append details to FAILURES.md
    
    SummarizeFailure --> Implementer : Retry pipeline loop
    
    MemoryAgent --> Orchestrator : Lessons recorded
    Orchestrator --> [*] : Phase 4 complete
    Orchestrator --> Architect : Advance Phase [ORCH]
```
