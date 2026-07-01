"""Chapter 6: Multimodal Perception Pipeline.

Asynchronous RAG ingestion pipeline supporting four modalities:
- PDF documents  (Docling + GLiNER NER)
- Images         (VLM structured extraction)
- Tabular data   (Pandas + schema detection)
- Audio          (Whisper transcription)

Section mapping (Chapter 6):
  6.1 Perception Foundations     -> config.py, models.py
  6.2 PDF Grounded Extraction    -> extractors/pdf_extractor.py
  6.3 Vision-Language Models     -> extractors/image_extractor.py
  6.4 Tabular + Audio Modalities -> extractors/table_extractor.py, audio_extractor.py
  6.5 Cross-Modal RAG Retrieval  -> embeddings.py, retrieval.py, pipeline.py
"""

__version__ = "0.1.0"
__author__ = "Mohit Aggarwal"
__license__ = "Apache-2.0"
