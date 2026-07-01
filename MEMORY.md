# MEMORY.md — Lessons Learned & Reusable Patterns

This document is maintained by the Memory Agent to record design decisions, patterns, config tweaks, and debugging lessons.

---

## 2026-07-01: Initialization

### Pattern Name: Cross-Modal Shared Embedding Space
- **Trigger Condition:** Mapping multiple text/media modalities to a single retrieval space.
- **Recommended Action:** Use a CLIP model (such as `clip-ViT-B-32` from `sentence-transformers`) that embeds both text descriptions and visual images into the exact same vector dimension (e.g. 512 dimensions), allowing a cosine-similarity comparison between text and images.

### Pattern Name: Audio TTS Generation via Edge API
- **Trigger Condition:** Generating high-quality synthetic audio for Whisper evaluation without local TTS dependencies.
- **Recommended Action:** Use `edge-tts` to make an async API call to Microsoft's Edge TTS service. Save the stream as MP3, and use PyAV or standard conversion libraries (e.g. wave or pydub) to store it as a clean WAV file format.
