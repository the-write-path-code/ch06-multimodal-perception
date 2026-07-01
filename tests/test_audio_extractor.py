# Section 6.3: Audio Extractor Unit Tests

import pytest
from pathlib import Path
from ch6.perception.audio import AudioExtractor, AudioAnalysisSchema
from ch6.perception.vlm_client import VLMClient
from ch6.models import ModalityType

SAMPLE_DIR = Path("data/samples")

class DummySegment:
    def __init__(self, text):
        self.text = text

class DummyInfo:
    def __init__(self, duration):
        self.duration = duration

@pytest.mark.asyncio
async def test_audio_extractor_success(monkeypatch):
    """Tests transcribing audio and running VLM metadata extraction with mocked services."""
    extractor = AudioExtractor()
    audio_path = SAMPLE_DIR / "nurse_visit_note_001.wav"
    assert audio_path.exists()

    # Mock Whisper transcribe method
    def mock_transcribe_sync():
        segments = [DummySegment("Patient John Smith visited today.")]
        return "Patient John Smith visited today.", 15.4

    # Replace the internal transcribe runner
    async def mock_run_in_executor(self, executor, func, *args, **kwargs):
        # We need to simulate loop.run_in_executor
        return "Patient John Smith visited today.", 15.4

    # Mock _load_whisper to avoid PyTorch loading in unit tests
    def mock_load_whisper(self):
        self._whisper_model = object() # Dummy non-None object

    monkeypatch.setattr(AudioExtractor, "_load_whisper", mock_load_whisper)

    # Let's mock loop.run_in_executor by overriding it inside the asyncio event loop or patching
    # actually a simpler way is monkeypatching the helper transcribe function inside the executor block:
    # inside extract:
    # loop.run_in_executor(None, _transcribe_sync)
    # Since _transcribe_sync is nested inside extract, we can patch asyncio.get_running_loop().run_in_executor!
    # Let's mock loop.run_in_executor:
    class MockLoop:
        async def run_in_executor(self, executor, func, *args, **kwargs):
            return "Patient John Smith visited today.", 15.4
            
    monkeypatch.setattr("asyncio.get_running_loop", lambda: MockLoop())

    # Mock VLMClient.analyze_image
    expected_vlm_output = AudioAnalysisSchema(
        summary="A checkup visit summary",
        entities=["John Smith"],
        action_items=["Follow up blood pressure checks"],
        sentiment="calm",
        duration_seconds=15.4
    )

    async def mock_vlm_analyze(*args, **kwargs):
        return expected_vlm_output

    monkeypatch.setattr(VLMClient, "analyze_image", mock_vlm_analyze)

    chunks = await extractor.extract(str(audio_path))
    assert len(chunks) == 1
    chunk = chunks[0]

    assert chunk.modality == ModalityType.AUDIO
    assert chunk.confidence == 1.0
    assert chunk.content_text == "Patient John Smith visited today."
    assert chunk.structured_data["summary"] == "A checkup visit summary"
    assert "John Smith" in chunk.structured_data["entities"]
    assert chunk.metadata["duration"] == 15.4
