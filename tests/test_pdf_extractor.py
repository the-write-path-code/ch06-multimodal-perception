# Section 6.1 / 6.3: PDF Extractor Unit Tests

import pytest
from pathlib import Path
from ch6.perception.pdf import PDFExtractor
from ch6.perception.vlm_client import VLMClient
from ch6.models import ModalityType
import pypdfium2 as pdfium

SAMPLE_DIR = Path("data/samples")

# Mock classes for Docling Document Model
class MockBBox:
    def __init__(self):
        self.l = 10.0
        self.b = 20.0
        self.r = 100.0
        self.t = 120.0

class MockProv:
    def __init__(self):
        self.page_no = 1
        self.bbox = MockBBox()

def create_mock_element(class_name: str, text: str, confidence: float = 1.0):
    """Dynamically creates a class with class_name so element.__class__.__name__ works correctly."""
    cls = type(class_name, (object,), {
        "text": text,
        "confidence": confidence,
        "prov": [MockProv()],
        "export_to_markdown": lambda self: text
    })
    return cls()

class MockPageSize:
    def __init__(self):
        self.width = 612.0
        self.height = 792.0

class MockPage:
    def __init__(self):
        self.size = MockPageSize()

class MockDocument:
    def __init__(self, elements):
        self.elements = elements
        self.pages = {1: MockPage()}

class MockResult:
    def __init__(self, elements):
        self.document = MockDocument(elements)

@pytest.mark.asyncio
async def test_pdf_extractor_routing(monkeypatch):
    """Tests that PDF extractor layout-guided parser splits, routes, and processes chunks correctly."""
    extractor = PDFExtractor()
    pdf_path = SAMPLE_DIR / "patient_care_protocol.pdf"
    assert pdf_path.exists()

    # Define mock layout elements
    mock_elements = [
        create_mock_element("Paragraph", "Home Health Care protocol text.", confidence=1.0),
        create_mock_element("Table", "Service Code | Limit\nS9123 | 2hr", confidence=0.9),
        create_mock_element("Picture", "Bar Chart of Audits", confidence=1.0)
    ]

    # Mock Docling convert method
    def mock_convert(*args, **kwargs):
        return MockResult(mock_elements)

    monkeypatch.setattr(extractor.converter, "convert", mock_convert)

    # Mock pypdfium2 PdfDocument
    class DummyPdfiumPage:
        def render(self, *args, **kwargs):
            class DummyRender:
                def to_pil(self):
                    from PIL import Image
                    return Image.new("RGBA", (612, 792), (255, 255, 255, 255))
            return DummyRender()

    class DummyPdfiumDoc:
        def __init__(self, *args, **kwargs):
            pass
        def __getitem__(self, idx):
            return DummyPdfiumPage()
        def close(self):
            pass

    monkeypatch.setattr(pdfium, "PdfDocument", DummyPdfiumDoc)

    # Mock VLMClient for the picture element on the extractor instance
    async def mock_vlm_analyze(*args, **kwargs):
        return {"raw_text": "Mocked chart analysis describing a bar chart of healthcare audits."}
    monkeypatch.setattr(extractor.vlm_client, "analyze_image", mock_vlm_analyze)

    # Mock SensitivityScanner to avoid running real PII models during unit tests
    monkeypatch.setattr(extractor.sensitivity_scanner, "scan_for_pii", lambda text: [])
    monkeypatch.setattr(extractor.sensitivity_scanner, "redact_pii", lambda text, *args: text)

    # Run extraction
    chunks = await extractor.extract(str(pdf_path))
    
    assert len(chunks) == 3
    
    # Text chunk
    c_text = chunks[0]
    assert c_text.modality == ModalityType.PDF
    assert c_text.metadata["routing_decision"] == "ocr_only"
    assert c_text.content_text == "Home Health Care protocol text."

    # Table chunk
    c_table = chunks[1]
    assert c_table.metadata["routing_decision"] == "table_extract"
    assert "S9123" in c_table.content_text

    # Figure chunk (should have VLM description)
    c_fig = chunks[2]
    assert c_fig.metadata["routing_decision"] == "vlm_crop"
    assert "Mocked chart analysis" in c_fig.content_text
    assert c_fig.confidence == 1.0
