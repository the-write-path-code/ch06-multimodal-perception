# MEMORY.md — Agent Memory and Learned Patterns

> **Owned by:** Memory Agent (append-only; never delete entries)
> **Purpose:** Accumulate patterns, gotchas, fixes, and reusable knowledge across all loop iterations.
> **Format:** Each entry has a unique ID (`MEM-NNNN`), a pattern name, a trigger condition, and a recommended action.

---

## How to Read This File

Before coding, the Implementer Agent scans this file for patterns matching the current task.
Before verifying, the Verifier Agent scans for known failure modes.
After any PASS or FAIL, the Memory Agent appends a new entry.

**Search tip:** Use `grep -i <keyword> MEMORY.md` to find relevant entries quickly.

---

## Entries

### MEM-0001
**Pattern:** `pydantic-settings lru_cache invalidation`
**Phase:** 1
**Trigger:** `get_settings()` returns stale values in tests after monkeypatching env vars
**Root cause:** `@lru_cache` caches the Settings instance; env var changes in tests don’t propagate
**Recommended action:**
```python
# In conftest.py, clear the cache before each test that modifies env:
from ch6_multimodal_perception.config import get_settings
get_settings.cache_clear()
```
**Added by:** Memory Agent | **Date:** 2026-06-30

---

### MEM-0002
**Pattern:** `uv sync fails with torch CPU-only constraint`
**Phase:** 0
**Trigger:** `uv sync` on a machine without CUDA fails if torch is pulled as a CUDA wheel
**Root cause:** torch>=2.3.0 defaults to CUDA on Linux; CPU-only build needed in CI
**Recommended action:**
Add to `pyproject.toml` under `[tool.uv]`:
```toml
[tool.uv]
extra-index-url = ["https://download.pytorch.org/whl/cpu"]
```
Or pass `--extra-index-url https://download.pytorch.org/whl/cpu` to `uv sync`
**Added by:** Memory Agent | **Date:** 2026-06-30

---

### MEM-0003
**Pattern:** `docling ImportError on first run`
**Phase:** 2
**Trigger:** `from docling.document_converter import DocumentConverter` raises `ImportError: No module named 'easyocr'`
**Root cause:** `docling` has optional OCR dependencies not installed by default
**Recommended action:**
Add `easyocr>=1.7.0` to the `[project.dependencies]` in `pyproject.toml` or use `docling[ocr]` if the package exposes that extra.
Alternatively, init `DocumentConverter` with `ocr=False` when OCR is not needed:
```python
converter = DocumentConverter(allowed_formats=[InputFormat.PDF])
```
**Added by:** Memory Agent | **Date:** 2026-06-30

---

### MEM-0004
**Pattern:** `asyncpg SSL connection to NeonDB`
**Phase:** 4
**Trigger:** `asyncpg` raises `ssl.SSLError: [SSL: WRONG_VERSION_NUMBER]` when connecting to NeonDB
**Root cause:** NeonDB requires `?sslmode=require` in the connection string; `asyncpg` needs `ssl=True` kwarg
**Recommended action:**
Use `NEON_DATABASE_URL` from `.env` (which includes `?sslmode=require`) rather than the local `DATABASE_URL`.
In `SQLAlchemy` use:
```python
engine = create_async_engine(settings.database_url, connect_args={"ssl": True})
```
**Added by:** Memory Agent | **Date:** 2026-06-30

---

### MEM-0005
**Pattern:** `Qdrant collection already exists on re-run`
**Phase:** 3
**Trigger:** Second run of pipeline raises `qdrant_client.http.exceptions.UnexpectedResponse: Collection already exists`
**Root cause:** `recreate_collection()` was deprecated in Qdrant v1.4+; use `create_collection()` with `if_not_exists` logic
**Recommended action:**
```python
from qdrant_client.models import Distance, VectorParams
try:
    client.create_collection(
        collection_name=name,
        vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
    )
except Exception:
    pass  # Already exists; safe to continue
```
Or check existence first:
```python
if not client.collection_exists(name):
    client.create_collection(...)
```
**Added by:** Memory Agent | **Date:** 2026-06-30

---

### MEM-0006
**Pattern:** `Whisper on macOS requires ffmpeg`
**Phase:** 2
**Trigger:** `whisper.load_model()` raises `FileNotFoundError: [Errno 2] No such file or directory: 'ffmpeg'`
**Root cause:** openai-whisper requires `ffmpeg` to be installed system-wide
**Recommended action:**
```bash
# macOS
brew install ffmpeg
# Ubuntu/Debian
apt-get install -y ffmpeg
# In Docker, add to Dockerfile:
RUN apt-get install -y ffmpeg
```
For test environments without ffmpeg, mock `whisper.transcribe` with a fixture.
**Added by:** Memory Agent | **Date:** 2026-06-30

---

### MEM-0007
**Pattern:** `anyio task group cancellation swallows exceptions`
**Phase:** 4
**Trigger:** Silent failures in `anyio.create_task_group()` when a child task raises an exception
**Root cause:** By default, task group cancels all siblings on first exception; the exception is re-raised in the group but may appear as `ExceptionGroup`
**Recommended action:**
Always wrap task group body:
```python
try:
    async with anyio.create_task_group() as tg:
        for file in files:
            tg.start_soon(process_file, file)
except* Exception as eg:
    for exc in eg.exceptions:
        logger.error("Task failed", exc_info=exc)
    raise
```
Or catch `BaseExceptionGroup` and re-raise individual exceptions to `FAILURES.md`.
**Added by:** Memory Agent | **Date:** 2026-06-30

---

### MEM-0008
**Pattern:** `GLiNER model download on first use blocks async loop`
**Phase:** 2
**Trigger:** First call to `GLiNER.from_pretrained()` blocks the event loop for 30–6 0s while downloading weights
**Root cause:** HuggingFace Hub download is synchronous
**Recommended action:**
Pre-load GLiNER in a sync context (e.g., startup hook) before entering async code:
```python
import anyio
async def startup():
    loop = anyio.get_current_task().backend
    model = await anyio.to_thread.run_sync(
        lambda: GLiNER.from_pretrained(settings.gliner_model)
    )
    return model
```
Or use `asyncio.to_thread` / `anyio.to_thread.run_sync` for any blocking HF Hub call.
**Added by:** Memory Agent | **Date:** 2026-06-30

---

### MEM-0009
**Pattern:** `SmolVLM structured output requires explicit JSON prompt`
**Phase:** 2
**Trigger:** VLM returns free-text instead of JSON; `json.loads()` raises `JSONDecodeError`
**Root cause:** SmolVLM-Instruct does not have a native JSON mode; structured output must be prompted
**Recommended action:**
Use a strict prompt template:
```python
PROMPT = (
    "Analyze this image and return ONLY valid JSON with keys: "
    "caption, objects (list), dominant_colors (list), has_text (bool). "
    "Do not include any text outside the JSON object."
)
```
Post-process: extract JSON from response with regex `r'\{.*?\}'` (DOTALL) before parsing.
**Added by:** Memory Agent | **Date:** 2026-06-30

---

### MEM-0010
**Pattern:** `fpdf2 font encoding for non-ASCII characters in generated PDFs`
**Phase:** 2
**Trigger:** `fpdf2` raises `UnicodeEncodeError` when writing non-ASCII text to synthetic PDFs
**Root cause:** Default font (helvetica) in fpdf2 is Latin-1 only
**Recommended action:**
```python
from fpdf import FPDF
pdf = FPDF()
pdf.add_page()
pdf.add_font('DejaVu', '', 'DejaVuSans.ttf', uni=True)
pdf.set_font('DejaVu', size=12)
```
For simple ASCII-only synthetic data, restrict `Faker` locale to `en_US`.
**Added by:** Memory Agent | **Date:** 2026-06-30

---

## Template for New Entries

```markdown
### MEM-NNNN
**Pattern:** `short descriptive name`
**Phase:** N
**Trigger:** What condition or error triggers this pattern
**Root cause:** Why it happens
**Recommended action:**
[code or prose]
**Added by:** [Agent role] | **Date:** YYYY-MM-DD
```

---

*Last entry: MEM-0010 | Total entries: 10*
