# VERIFY.md — Verification Contracts and Acceptance Criteria

> **Owned by:** Verifier Agent
> **Purpose:** Define exactly what must pass for each phase to be accepted. This is the source of truth for `scripts/verify.sh`.

---

## Verification Philosophy

Verification is **non-negotiable**. A phase is not complete until every check in its section below exits with status `0`. The Verifier Agent:

1. Reads the current phase from `TASK.md`
2. Runs the corresponding checks in order
3. On first failure: writes to `FAILURES.md`, calls `summarize_failure.sh`, stops
4. On full pass: appends `PASS phase=N ts=<ISO8601>` to `WORKLOG.md`
5. Never skips a check, even if prior checks are slow

---

## Phase 0 — Foundation Checks

### P0-1: Python version
```bash
python --version | grep -q '3.12'
```
Expected: `Python 3.12.x`

### P0-2: uv available
```bash
uv --version
```
Expected: exits 0

### P0-3: All required top-level files exist
```bash
for f in pyproject.toml .python-version .env.example Makefile docker-compose.yml \
          AGENTS.md TASK.md VERIFY.md MEMORY.md FAILURES.md WORKLOG.md \
          scripts/verify.sh scripts/summarize_failure.sh; do
  test -f "$f" || (echo "MISSING: $f" && exit 1)
done
```

### P0-4: src package directory exists
```bash
test -d src/ch6_multimodal_perception
test -f src/ch6_multimodal_perception/__init__.py
```

### P0-5: Package imports cleanly
```bash
uv run python -c "import ch6_multimodal_perception; print(ch6_multimodal_perception.__version__)"
```
Expected: prints `0.1.0`

**Phase 0 Pass Condition:** All P0-1 through P0-5 exit 0.

---

## Phase 1 — Config + Models Checks

### P1-1: Settings loads with defaults (no .env required)
```bash
uv run python -c "
from ch6_multimodal_perception.config import get_settings
s = get_settings()
assert s.chunk_size == 512
assert s.hybrid_alpha == 0.7
assert s.dense_embed_dim == 1024
print('Settings OK')
"
```

### P1-2: Settings rejects invalid hybrid_alpha
```bash
uv run python -c "
from pydantic import ValidationError
from ch6_multimodal_perception.config import Settings
try:
    Settings(hybrid_alpha=1.5)
    raise AssertionError('Should have raised')
except ValidationError:
    print('Validation OK')
"
```

### P1-3: All modality models instantiate
```bash
uv run python -c "
from ch6_multimodal_perception.models import (
    PDFChunk, ImageChunk, TableChunk, AudioChunk, ModalityType
)
from pathlib import Path
import uuid, datetime
base = dict(id=str(uuid.uuid4()), source_path=Path('/tmp/x'), created_at=datetime.datetime.now(datetime.UTC))
p = PDFChunk(**base, modality=ModalityType.PDF, text='hello', page_number=1)
i = ImageChunk(**base, modality=ModalityType.IMAGE, caption='test', width=100, height=100)
t = TableChunk(**base, modality=ModalityType.TABLE, rows=[], schema_detected={})
a = AudioChunk(**base, modality=ModalityType.AUDIO, transcript='hi', duration_seconds=1.0)
print('All models OK')
"
```

### P1-4: pytest suite for phase 1
```bash
uv run pytest tests/test_phase1_config.py -v --tb=short
```
Expected: all tests pass, 0 failures

### P1-5: No import errors in logging_config
```bash
uv run python -c "from ch6_multimodal_perception.logging_config import get_logger; print('Logger OK')"
```

**Phase 1 Pass Condition:** All P1-1 through P1-5 exit 0.

---

## Phase 2 — Perception Extractor Checks

### P2-1: Data generator produces all 4 modalities
```bash
uv run python -m ch6_multimodal_perception.data_generator --output-dir /tmp/ch6_verify
test -d /tmp/ch6_verify/pdfs
test -d /tmp/ch6_verify/images
test -d /tmp/ch6_verify/tables
test -d /tmp/ch6_verify/audio
# Must produce at least 1 file per modality
test $(ls /tmp/ch6_verify/pdfs/*.pdf 2>/dev/null | wc -l) -ge 1
test $(ls /tmp/ch6_verify/images/*.png 2>/dev/null | wc -l) -ge 1
test $(ls /tmp/ch6_verify/tables/*.csv 2>/dev/null | wc -l) -ge 1
test $(ls /tmp/ch6_verify/audio/*.wav 2>/dev/null | wc -l) -ge 1
```

### P2-2: Ground truth JSON exists
```bash
test -f /tmp/ch6_verify/ground_truth.json
uv run python -c "
import json
with open('/tmp/ch6_verify/ground_truth.json') as f:
    gt = json.load(f)
assert 'pdfs' in gt and 'images' in gt and 'tables' in gt and 'audio' in gt
print('Ground truth OK')
"
```

### P2-3: All extractor modules import cleanly
```bash
uv run python -c "
from ch6_multimodal_perception.extractors.pdf_extractor import PDFExtractor
from ch6_multimodal_perception.extractors.image_extractor import ImageExtractor
from ch6_multimodal_perception.extractors.table_extractor import TableExtractor
from ch6_multimodal_perception.extractors.audio_extractor import AudioExtractor
print('All extractors import OK')
"
```

### P2-4: Each extractor has correct async signature
```bash
uv run python -c "
import inspect, asyncio
from ch6_multimodal_perception.extractors.pdf_extractor import PDFExtractor
from ch6_multimodal_perception.extractors.image_extractor import ImageExtractor
from ch6_multimodal_perception.extractors.table_extractor import TableExtractor
from ch6_multimodal_perception.extractors.audio_extractor import AudioExtractor
for cls in [PDFExtractor, ImageExtractor, TableExtractor, AudioExtractor]:
    assert hasattr(cls, 'extract'), f'{cls} missing extract'
    assert asyncio.iscoroutinefunction(cls.extract), f'{cls}.extract must be async'
print('Signatures OK')
"
```

### P2-5: pytest suite for phase 2
```bash
uv run pytest tests/test_phase2_extractors.py -v --tb=short
```

**Phase 2 Pass Condition:** All P2-1 through P2-5 exit 0.

---

## Phase 3 — Embeddings + Retrieval Checks

### P3-1: embeddings module imports cleanly
```bash
uv run python -c "from ch6_multimodal_perception.embeddings import EmbeddingService; print('OK')"
```

### P3-2: EmbeddedChunk has required fields
```bash
uv run python -c "
from ch6_multimodal_perception.embeddings import EmbeddedChunk
import inspect
fields = inspect.get_annotations(EmbeddedChunk)
assert 'dense_vector' in fields
assert 'sparse_vector' in fields
assert 'chunk_id' in fields
print('EmbeddedChunk fields OK')
"
```

### P3-3: Hybrid alpha is applied correctly (unit test)
```bash
uv run pytest tests/test_phase3_retrieval.py::test_hybrid_alpha -v
```

### P3-4: pytest suite for phase 3
```bash
uv run pytest tests/test_phase3_retrieval.py -v --tb=short
```

**Phase 3 Pass Condition:** All P3-1 through P3-4 exit 0.

---

## Phase 4 — Pipeline + Handoffs Checks

### P4-1: Pipeline imports and instantiates
```bash
uv run python -c "
from ch6_multimodal_perception.pipeline import Pipeline
p = Pipeline()
print('Pipeline OK')
"
```

### P4-2: Handoff contracts are typed dataclasses (not dicts)
```bash
uv run python -c "
from ch6_multimodal_perception.pipeline import (
    ExtractionResult, EmbeddingResult, RetrievalResult
)
import dataclasses
for cls in [ExtractionResult, EmbeddingResult, RetrievalResult]:
    assert dataclasses.is_dataclass(cls), f'{cls} must be a dataclass'
print('Contracts OK')
"
```

### P4-3: CLI entry points are registered
```bash
uv run ch6-pipeline --help
uv run ch6-generate --help
```

### P4-4: pytest suite for phase 4
```bash
uv run pytest tests/test_phase4_pipeline.py -v --tb=short
```

### P4-5: Full test suite passes
```bash
uv run pytest tests/ -v --tb=short --ignore=tests/test_phase5_docs.py
```

**Phase 4 Pass Condition:** All P4-1 through P4-5 exit 0.

---

## Phase 5 — Polish + Docs Checks

### P5-1: README contains all section references
```bash
grep -q '6.1' README.md
grep -q '6.2' README.md
grep -q '6.3' README.md
grep -q '6.4' README.md
grep -q '6.5' README.md
```

### P5-2: PROMPT_AGENT.md exists and is non-empty
```bash
test -s PROMPT_AGENT.md
```

### P5-3: Full test suite passes (all phases)
```bash
uv run pytest tests/ -v --tb=short
```

**Phase 5 Pass Condition:** All P5-1 through P5-3 exit 0.

---

## Failure Severity Levels

| Level | Meaning | Action |
|-------|---------|--------|
| `WARN` | Non-blocking issue | Log to WORKLOG.md, continue |
| `ERROR` | Phase gate blocked | Log to FAILURES.md, halt phase, notify Orchestrator |
| `CRITICAL` | Data corruption or security issue | Halt entire loop, require human review |

---

## Adding New Checks

To add a new verification check:
1. Add it to the appropriate phase section above with a `P{N}-{K}` identifier
2. Add the corresponding shell case to `scripts/verify.sh`
3. Update `WORKLOG.md` with `[VERIFY] Added check P{N}-{K}`
4. Never remove an existing check without Orchestrator approval in `WORKLOG.md`
