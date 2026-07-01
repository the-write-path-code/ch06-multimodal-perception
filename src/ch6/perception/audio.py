# Section 6.3: Audio Extractor

import os
import json
import hashlib
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from ch6.config import config
from ch6.logging import logger, ctx_source_file, ctx_modality, ctx_pipeline_stage
from ch6.models import PerceptionChunk, ModalityType
from ch6.perception.vlm_client import VLMClient

class AudioAnalysisSchema(BaseModel):
    """Structured analysis representation for voice notes transcripts."""
    summary: str = Field(..., description="High-level narrative summary of the audio transcript")
    entities: List[str] = Field(default_factory=list, description="Key clinical entities, doctor names, or patient names")
    action_items: List[str] = Field(default_factory=list, description="Follow-ups, care protocols, or reminders mentioned")
    sentiment: str = Field(..., description="Sentiment/tone of the voice recording (e.g. calm, stressed, neutral)")
    duration_seconds: float = Field(..., description="Total length of recording in seconds")

class AudioExtractor:
    """Transcribes audio files locally with Whisper and enriches them via VLM text-mode analysis."""

    def __init__(self) -> None:
        self.vlm_client = VLMClient()
        self._whisper_model = None

    def _load_whisper(self):
        """Lazily loads Whisper model to avoid overhead if not processing audio."""
        if self._whisper_model is not None:
            return
        
        try:
            from faster_whisper import WhisperModel
            # Load model onto CPU with int8 quantization for speed
            self._whisper_model = WhisperModel(
                config.whisper_model_size,
                device="cpu",
                compute_type="int8"
            )
            logger.info("Local Whisper model initialized successfully.")
        except Exception as e:
            logger.error("Failed to initialize Whisper model", error=str(e))
            raise e

    def _generate_chunk_id(self, filepath: str) -> str:
        """Generates unique chunk ID from file path."""
        return hashlib.md5(filepath.encode()).hexdigest()

    async def extract(self, file_path: str) -> List[PerceptionChunk]:
        """Transcribes the audio locally and runs VLM text extraction over the transcript."""
        ctx_source_file.set(os.path.basename(file_path))
        ctx_modality.set("audio")
        ctx_pipeline_stage.set("extraction")

        logger.info("Starting audio transcription", file=file_path)

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Audio file not found: {file_path}")

        chunk_id = self._generate_chunk_id(file_path)

        # 1. Transcribe Audio
        try:
            self._load_whisper()
            if not self._whisper_model:
                raise RuntimeError("Whisper model is not available")

            # Run synchronous CPU-bound transcribe in executor
            try:
                import asyncio
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.get_event_loop()

            def _transcribe_sync():
                segments, info = self._whisper_model.transcribe(file_path, beam_size=5)
                full_text = " ".join(seg.text for seg in segments).strip()
                return full_text, info.duration

            transcript, duration = await loop.run_in_executor(None, _transcribe_sync)
            logger.info("Audio transcription complete", duration_sec=duration, text_len=len(transcript))

        except Exception as e:
            logger.error("Audio transcription failed", error=str(e))
            # Graceful wrapper fallback
            transcript = "Audio transcription failed."
            duration = 0.0

        # 2. Run text-mode VLM analysis over transcript if transcript is valid
        structured_data: Dict[str, Any] = {}
        confidence = 1.0

        if duration > 0.0 and transcript != "Audio transcription failed.":
            prompt = (
                f"You are analyzing a transcript of a nurse clinical voice note.\n"
                f"Transcript text: \"{transcript}\"\n"
                f"Synthesize this transcript into structured fields: 'summary' (detailed narrative), "
                f"'entities' (patient/doctor names, care settings, medications), "
                f"'action_items' (required clinical followups), and 'sentiment' (calm, urgent, neutral).\n"
                f"Report the duration_seconds as: {duration:.2f}."
            )

            try:
                # Call VLM with no image bytes (text-only call)
                vlm_data = await self.vlm_client.analyze_image(
                    prompt=prompt,
                    response_schema=AudioAnalysisSchema
                )

                if isinstance(vlm_data, dict):
                    structured_data = vlm_data
                else:
                    structured_data = {
                        "summary": getattr(vlm_data, "summary", ""),
                        "entities": getattr(vlm_data, "entities", []),
                        "action_items": getattr(vlm_data, "action_items", []),
                        "sentiment": getattr(vlm_data, "sentiment", ""),
                        "duration_seconds": float(getattr(vlm_data, "duration_seconds", duration))
                    }

            except Exception as e:
                logger.error("VLM enrichment on transcript failed. Using simple wrapper.", error=str(e))
                confidence = 0.5
                structured_data = {
                    "summary": f"VLM parsing failed. Simple transcript: {transcript}",
                    "entities": [],
                    "action_items": [],
                    "sentiment": "unknown",
                    "duration_seconds": duration
                }
        else:
            confidence = 0.0
            structured_data = {
                "summary": "Audio processing failed.",
                "entities": [],
                "action_items": [],
                "sentiment": "failed",
                "duration_seconds": 0.0
            }

        meta = {
            "layout_type": "audio_transcript",
            "duration": duration,
            "routing_decision": "whisper_then_vlm"
        }

        chunk = PerceptionChunk(
            chunk_id=chunk_id,
            modality=ModalityType.AUDIO,
            source_file=file_path,
            confidence=confidence,
            content_text=transcript,
            structured_data=structured_data,
            metadata=meta
        )

        return [chunk]
