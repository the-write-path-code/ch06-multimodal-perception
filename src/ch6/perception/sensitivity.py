# Section 6.1: Sensitivity Scanner (PII Detection & Redaction)

import re
from typing import List, Optional
from ch6.logging import logger

class SensitivityScanner:
    """Detects and redacts PII/PHI entities in text chunks before external routing."""

    def __init__(self, use_gliner: bool = True) -> None:
        self.use_gliner = use_gliner
        self._gliner_model = None
        self._labels = ["email", "phone number", "ssn", "credit card", "person", "address"]

    def _load_model(self):
        """Lazily loads the GLiNER model to save initialization memory/time."""
        if not self.use_gliner or self._gliner_model is not None:
            return

        try:
            from gliner import GLiNER
            # Load a lightweight PII-specific model
            self._gliner_model = GLiNER.from_pretrained("urchade/gliner_medium-v2.1")
            logger.info("GLiNER PII model loaded successfully.")
        except Exception as e:
            logger.warning(
                "Could not load GLiNER model. Falling back to regex-based sensitivity scanning.",
                error=str(e)
            )
            self.use_gliner = False

    def scan_for_pii(self, text: str) -> List[str]:
        """Scans the given text for any PII entities. Returns list of detected labels."""
        detected = []
        if not text:
            return detected

        # Try GLiNER
        self._load_model()
        if self.use_gliner and self._gliner_model:
            try:
                entities = self._gliner_model.predict_entities(text, self._labels, threshold=0.5)
                for ent in entities:
                    label = ent.get("label", "").upper()
                    if label not in detected:
                        detected.append(label)
            except Exception as e:
                logger.error("GLiNER predict_entities failed. Using regex fallback.", error=str(e))
                self.use_gliner = False

        # Regex fallback
        if not self.use_gliner:
            # Simple patterns
            patterns = {
                "EMAIL": r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
                "PHONE": r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
                "SSN": r"\b\d{3}-\d{2}-\d{4}\b",
                "CREDIT_CARD": r"\b(?:\d[ -]*?){13,16}\b"
            }
            for label, pattern in patterns.items():
                if re.search(pattern, text):
                    detected.append(label)

        return detected

    def redact_pii(self, text: str, placeholder: str = "[REDACTED]") -> str:
        """Redacts all detected PII in the text with a placeholder."""
        if not text:
            return text

        self._load_model()
        # If GLiNER is active, redact using entity bounding offsets
        if self.use_gliner and self._gliner_model:
            try:
                entities = self._gliner_model.predict_entities(text, self._labels, threshold=0.5)
                # Sort entities by start index descending to avoid changing offsets while editing
                entities = sorted(entities, key=lambda x: x["start"], reverse=True)
                for ent in entities:
                    start, end = ent["start"], ent["end"]
                    text = text[:start] + placeholder + text[end:]
                return text
            except Exception as e:
                logger.error("GLiNER redaction failed. Using regex fallback.", error=str(e))
                self.use_gliner = False

        # Regex fallback redaction
        if not self.use_gliner:
            patterns = [
                r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", # Email
                r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b", # Phone
                r"\b\d{3}-\d{2}-\d{4}\b", # SSN
                r"\b(?:\d[ -]*?){13,16}\b" # Credit card
            ]
            for pattern in patterns:
                text = re.sub(pattern, placeholder, text)

        return text
