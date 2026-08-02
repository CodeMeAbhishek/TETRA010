"""
Consumer Tier document extraction — MedGemma stub.

Provides a clean interface for extracting structured clinical fields
from photographed lab reports.  The actual MedGemma 1.5 4B call is
stubbed here; hosting decision (Vertex AI Model Garden / HF Inference
Endpoint / local download) is still open — see documentation.md.

IMPORTANT: All values extracted from a document ALWAYS get
  source = "extracted_from_document"
  requires_confirmation = True
regardless of confidence.  Values are NOT wired into engines until
the user explicitly confirms them (safety rule #3).
"""

import logging
from typing import Dict

logger = logging.getLogger(__name__)


def extract_from_document(image_bytes: bytes) -> Dict:
    """
    Extract structured clinical fields from a lab report image.

    Args:
        image_bytes: Raw bytes of the uploaded image.

    Returns:
        {
            "fields": {
                "field_name": {"value": ..., "confidence": ...},
                ...
            },
            "raw_text": str,   # OCR'd text (empty in stub)
            "error": str|None  # Error message if extraction failed
        }

    ── Integration point (TODO) ──────────────────────────────────────
    Replace the stub body below with an actual MedGemma 1.5 4B call.
    Candidate hosting options:
      1. Vertex AI Model Garden  — managed, lowest latency
      2. Hugging Face Inference Endpoint — serverless, easy setup
      3. Local download via transformers — offline-capable, needs GPU

    Whichever option is chosen, this function's signature and return
    format must stay the same so calling code does not need changes.
    ──────────────────────────────────────────────────────────────────
    """
    logger.info(
        "document_extraction.extract_from_document called with %d bytes "
        "(stub — MedGemma integration pending)",
        len(image_bytes),
    )

    # ── Stub return ──────────────────────────────────────────────────
    return {
        "fields": {},
        "raw_text": "",
        "error": (
            "MedGemma integration pending — hosting decision still open "
            "(Vertex AI / Hugging Face / local). See documentation.md."
        ),
    }
