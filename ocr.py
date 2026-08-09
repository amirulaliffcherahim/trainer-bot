"""Local OCR wrapper — screenshot text extraction with a 4096px cap.

Routes:
1. **Vision LLM (Gemini Flash)** — ONLY if VISION_API_KEY is set (accuracy
   upgrade route; needs `google-genai` installed — optional dependency).
2. **EasyOCR** (local, free, DL-based) — the default.

Resource guard: images are downscaled so the max dimension is ≤ 4096px
before any OCR work (public-bot abuse hardening).

EasyOCR downloads its detection model on first use (~64MB, one time) and is
slow to warm up — the reader is cached as a lazy singleton.
"""

from __future__ import annotations

import io
import logging
import os

from PIL import Image

log = logging.getLogger(__name__)

MAX_DIM = 4096
_EASYOCR_READER = None


def cap_image(image_bytes: bytes) -> bytes:
    """Resize so max dimension ≤ MAX_DIM (aspect preserved). PNG output."""
    img = Image.open(io.BytesIO(image_bytes))
    if max(img.size) > MAX_DIM:
        img.thumbnail((MAX_DIM, MAX_DIM), Image.LANCZOS)
        log.info("Image capped to %s", img.size)
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


def _easyocr_text(image_bytes: bytes) -> str:
    global _EASYOCR_READER
    if _EASYOCR_READER is None:
        import easyocr  # heavy import, lazy

        _EASYOCR_READER = easyocr.Reader(["en"], gpu=False, verbose=False)
    results = _EASYOCR_READER.readtext(image_bytes, detail=0, paragraph=True)
    return "\n".join(results)


def _vision_llm_text(image_bytes: bytes) -> str:
    """Gemini Flash route — only reached when VISION_API_KEY is set."""
    api_key = os.environ.get("VISION_API_KEY")
    from google import genai  # optional dependency

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[
            "Transcribe ALL text and numbers in this running-app screenshot "
            "verbatim, line by line. Include distance, time, pace, heart "
            "rate, elevation and the date if visible. Numbers only, no "
            "commentary.",
            genai.types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
        ],
    )
    return response.text or ""


def extract_text(image_bytes: bytes, *, vision_api_key: str | None = None) -> str:
    """OCR a capped image. Vision-LLM route wins when a key is provided."""
    capped = cap_image(image_bytes)
    if vision_api_key or os.environ.get("VISION_API_KEY"):
        return _vision_llm_text(capped)
    return _easyocr_text(capped)
