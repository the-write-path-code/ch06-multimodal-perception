# Section 6.1: Tabular Extractor Unit Tests

import pytest
from pathlib import Path
import pandas as pd
from ch6.perception.table import TableExtractor
from ch6.models import ModalityType

SAMPLE_DIR = Path("data/samples")

@pytest.mark.asyncio
async def test_table_profiler_parsing():
    """Tests that TableExtractor profiles a CSV dataset schema and statistics correctly."""
    extractor = TableExtractor()
    csv_path = SAMPLE_DIR / "medical_supplies_inventory.csv"
    
    assert csv_path.exists(), "Sample CSV file must exist before running test"
    
    chunks = await extractor.extract(str(csv_path))
    assert len(chunks) == 1
    chunk = chunks[0]
    
    assert chunk.modality == ModalityType.TABLE
    assert chunk.confidence == 1.0
    assert chunk.source_file == str(csv_path)
    assert chunk.content_text is not None
    assert "SUP-" in chunk.content_text or "Dimensions: 200 rows" in chunk.content_text
    
    # Verify structured profiling data exists
    struct = chunk.structured_data
    assert struct is not None
    assert struct["row_count"] == 200
    assert struct["col_count"] == 8
    assert "supply_id" in struct["columns"]
    assert "unit_price" in struct["columns"]
    assert struct["dtypes"]["quantity"] == "int64"

@pytest.mark.asyncio
async def test_table_profiler_pii_redaction(tmp_path):
    """Tests that TableExtractor triggers SensitivityScanner redaction when tabular summaries contain PII."""
    extractor = TableExtractor()
    csv_path = tmp_path / "patients_contacts.csv"
    
    df = pd.DataFrame([
        {"name": "Alice Cooper", "email": "alice.cooper@example.com"},
        {"name": "Bob Marley", "email": "bob.marley@example.com"}
    ])
    df.to_csv(csv_path, index=False)
    
    chunks = await extractor.extract(str(csv_path))
    chunk = chunks[0]
    
    assert chunk.metadata["pii_detected"] is True
    # The summary should be redacted
    assert "alice.cooper@example.com" not in chunk.content_text
    assert "[REDACTED]" in chunk.content_text
