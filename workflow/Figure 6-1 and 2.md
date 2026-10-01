## Figure 6.1

```mermaid
%%{init: {"theme": "base", "themeVariables": {"fontFamily": "Arial, Helvetica, sans-serif", "fontSize": "28px", "primaryTextColor": "#000000", "lineColor": "#4B5563"}}}%%
flowchart TD
    DISPATCH{"PerceptionDispatcher<br/>(Source File MIME / Extension Router)"}

    subgraph Extractors ["Multi-Modal Extraction Layer"]
        direction LR
        PDF_P["PDF Parser & Cropper<br/>(Docling + pypdfium2)"]
        VLM_P["VLM Image Parser<br/>(NVIDIA / Gemini / Ollama)"]
        CSV_P["Table Profiler<br/>(Pandas NL Anchor)"]
        AUDIO_P["Audio Transcriber<br/>(faster-whisper)"]
    end

    DISPATCH -->|"PDF"| PDF_P
    DISPATCH -->|"Image"| VLM_P
    DISPATCH -->|"Table"| CSV_P
    DISPATCH -->|"Audio"| AUDIO_P

    subgraph Contract ["Canonical Contract & Governance Stage"]
        direction LR
        CHUNK["PerceptionChunk<br/>(Canonical Typed State)"] --> REDACT["Sensitivity Redactor<br/>(GLiNER NER + Regex)"] --> OUT["PII-Redacted Chunk<br/>(To Vector DB & Registry)"]
    end

    PDF_P --> CHUNK
    VLM_P --> CHUNK
    CSV_P --> CHUNK
    AUDIO_P --> CHUNK

    classDef dispatch fill:#FEF9C3,stroke:#CA8A04,color:#000000,stroke-width:1.5px
    classDef parser fill:#EDE9FE,stroke:#7C3AED,color:#000000,stroke-width:1.5px
    classDef chunk fill:#DCFCE7,stroke:#15803D,color:#000000,stroke-width:1.5px
    classDef red fill:#FEE2E2,stroke:#DC2626,color:#000000,stroke-width:1.5px
    classDef out fill:#EBF5FF,stroke:#2563EB,color:#000000,stroke-width:1.5px

    class DISPATCH dispatch
    class PDF_P,VLM_P,CSV_P,AUDIO_P parser
    class CHUNK chunk
    class REDACT red
    class OUT out
```

## Figure 6.2

```mermaid
%%{init: {"theme": "base", "themeVariables": {"fontFamily": "Arial, Helvetica, sans-serif", "fontSize": "18px", "primaryTextColor": "#000000", "lineColor": "#4B5563"}}}%%
flowchart TD
    CHUNK["PII Tagged & Redacted<br/>Chunk"]

    CHUNK --> CLIP["CLIP Dense Encoder<br/>(clip-ViT-B-32 → 512d)"]
    CHUNK --> SPLADE["SPLADE Sparse Encoder<br/>(Splade_PP_en_v1)"]

    CLIP --> REG["Asset Registry<br/>(SQLite Database)"]
    SPLADE --> REG

    REG --> VERIFY{"Handoff Contract Verifier<br/>(Section 6.5)"}

    VERIFY -->|"Confidence ≥ 0.85<br/>PII = False"| VALID["Mark VALID"]
    VERIFY -->|"Confidence < 0.50<br/>or PII = True"| REVIEW["Mark REVIEW"]

    VALID --> INDEX["Index Vectors into<br/>Qdrant Collection"]
    INDEX --> UPDATE["Update Chunk Table<br/>with Qdrant Point ID"]

    REVIEW --> HOLD["Hold in Registry<br/>(Review Queue / Skip Index)"]

    classDef chunk fill:#EBF5FF,stroke:#2563EB,color:#000000,stroke-width:1.5px
    classDef enc fill:#EDE9FE,stroke:#7C3AED,color:#000000,stroke-width:1.5px
    classDef reg fill:#F3F4F6,stroke:#4B5563,color:#000000,stroke-width:1.5px
    classDef verify fill:#FEF9C3,stroke:#CA8A04,color:#000000,stroke-width:1.5px
    classDef pass fill:#DCFCE7,stroke:#15803D,color:#000000,stroke-width:1.5px
    classDef warn fill:#FEE2E2,stroke:#DC2626,color:#000000,stroke-width:1.5px

    class CHUNK chunk
    class CLIP,SPLADE enc
    class REG reg
    class VERIFY verify
    class VALID,INDEX,UPDATE pass
    class REVIEW,HOLD warn
```
