import logging
import json
import base64
import os
from typing import Optional
import openai

logger = logging.getLogger(__name__)

# ── OpenAI client (via OpenRouter) ─────────────────────────────────────────────
_OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")
_OPENROUTER_BASE = "https://openrouter.ai/api/v1"
_TEXT_MODEL    = "openai/gpt-4o-mini"  # For text correction
_VISION_MODEL  = "openai/gpt-4o"       # For image OCR (vision capabilities)

if _OPENAI_API_KEY:
    client = openai.OpenAI(
        base_url=_OPENROUTER_BASE,
        api_key=_OPENAI_API_KEY
    )
else:
    logger.warning("OpenAI API key not configured. Set OPENAI_API_KEY or OPENROUTER_API_KEY environment variable.")
    client = None


# ── Prompt builder ───────────────────────────────────────────────────────────
def _build_messages(raw_text: str) -> list:
    """Build the chat messages list sent to the model."""
    system = (
        "You are an expert OCR correction assistant. "
        "Your ONLY job is to fix typos, broken characters, and whitespace caused by OCR errors. "
        "Return ONLY a strict JSON object — no markdown, no code fences, no extra text."
    )
    user = (
        "The following text was extracted via OCR and may contain spelling mistakes or random symbols.\n\n"
        "Strict Instructions:\n"
        "1. Fix obvious OCR glitches, typos, and broken words.\n"
        "2. DO NOT rephrase, paraphrase, or rewrite any sentences.\n"
        "3. DO NOT change the original tone or meaning.\n"
        "4. Preserve names and unique capitalized words exactly as they are (e.g. 'Fitzwilliam Darcy', 'Vekovior').\n"
        "5. Preserve original intentional line breaks (e.g. addresses, signatures).\n\n"
        "Return EXACTLY in this JSON format:\n"
        "{\n"
        '  "cleaned_text": "...",\n'
        '  "summary": []\n'
        "}\n\n"
        f"OCR TEXT:\n{raw_text}\n"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user",   "content": user},
    ]


# ── Public API ───────────────────────────────────────────────────────────────
def format_text_with_ai(raw_text: str) -> Optional[dict]:
    """Send raw OCR text to OpenAI (gpt-4o-mini) and return a dict
    containing ``cleaned_text`` and ``summary``.
    Returns None on any failure so callers can gracefully fall back.
    """
    if not client:
        logger.warning("OpenAI client not configured.")
        return None
        
    raw_text = (raw_text or "").strip()
    if not raw_text:
        return None

    try:
        messages = _build_messages(raw_text)
        response = client.chat.completions.create(
            model=_TEXT_MODEL, 
            messages=messages,
            temperature=0.1,
            max_tokens=2000
        )

        content = response.choices[0].message.content.strip()

        # Strip accidental markdown code fences (```json ... ```)
        if content.startswith("```"):
            lines = content.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            content = "\n".join(lines)

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            logger.warning("OpenAI response was not valid JSON — wrapping as plain text. Raw: %s", content)
            return {
                "cleaned_text": content,
                "summary": ["Summary generation failed or was malformed."],
            }

    except Exception as e:
        logger.exception("OpenAI formatting request failed: %s", e)
        return None


# ── Handwritten & Medical Prescription OCR with OpenAI Vision ──────────────
def _encode_image_to_base64(image_path: str) -> str:
    """Encode an image file to base64 string."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


def extract_handwritten_text_with_openai(image_path: str) -> Optional[dict]:
    """
    Extract text from handwritten images using OpenAI GPT-4o Vision.
    Optimized for handwritten text and complex documents.

    Args:
        image_path: Local file path to the image

    Returns:
        Dictionary with extracted text and metadata, or None on failure.
    """
    if not client:
        logger.warning("OpenAI client not configured for handwritten text extraction.")
        return None
        
    if not image_path:
        return None

    try:
        # Encode image to base64
        base64_image = _encode_image_to_base64(image_path)

        system_msg = (
            "You are an expert OCR system specialized in reading handwritten text. "
            "Extract ALL text from the image, including handwriting. "
            "Preserve the original structure and line breaks as much as possible. "
            "If the image contains a medical prescription, pay special attention to medication names, dosages, and instructions. "
            "Return ONLY a valid JSON object with these fields:\n"
            '{\n'
            '  "text": "the complete extracted text with line breaks",\n'
            '  "confidence": 0.95\n'
            '}'
        )

        response = client.chat.completions.create(
            model=_VISION_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": system_msg
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extract all text from this image."},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=2000
        )

        content = response.choices[0].message.content.strip()

        # Strip markdown code fences if present
        if content.startswith("```"):
            lines = content.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            content = "\n".join(lines)

        try:
            result = json.loads(content)
            return {
                "text": result.get("text", content),
                "confidence": result.get("confidence", 0.90),
                "model": _VISION_MODEL
            }
        except json.JSONDecodeError:
            return {
                "text": content,
                "confidence": 0.85,
                "model": _VISION_MODEL
            }

    except Exception as e:
        logger.exception("OpenAI Vision handwritten extraction failed: %s", e)
        return None


def extract_medical_prescription_with_openai(image_path: str) -> Optional[dict]:
    """
    Specialized extraction for medical prescriptions using OpenAI GPT-4o Vision.
    Extracts and structures prescription data directly from the image.

    Args:
        image_path: Local file path to the prescription image

    Returns:
        Structured prescription data with fields like:
        - doctor_name, patient_name, date
        - medications (name, dosage, frequency)
        - instructions, pharmacy_info
    """
    if not client:
        logger.warning("OpenAI client not configured for prescription extraction.")
        return None
        
    if not image_path:
        return None

    try:
        # Encode image to base64
        base64_image = _encode_image_to_base64(image_path)

        system_msg = (
            "You are a medical prescription expert. Extract structured data from prescription images. "
            "Return ONLY a valid JSON object with no markdown formatting."
        )

        user_msg = (
            "Analyze this medical prescription image and extract the following fields in JSON format:\n\n"
            "{\n"
            '  "doctor_name": "doctor\'s name",\n'
            '  "patient_name": "patient\'s name",\n'
            '  "date": "prescription date",\n'
            '  "medications": [\n'
            '    {"name": "medication name", "dosage": "dosage amount", "frequency": "how often to take", "duration": "how long"}\n'
            '  ],\n'
            '  "instructions": "general instructions",\n'
            '  "pharmacy_name": "pharmacy name",\n'
            '  "prescription_number": "Rx number",\n'
            '  "raw_text": "complete text from image"\n'
            "}\n\n"
            "If a field is not found, use null. Be very careful with medication names and dosages."
        )

        response = client.chat.completions.create(
            model=_VISION_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": system_msg
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_msg},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=2500
        )

        content = response.choices[0].message.content.strip()

        # Strip markdown code fences if present
        if content.startswith("```"):
            lines = content.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            content = "\n".join(lines)

        try:
            result = json.loads(content)
            result["confidence"] = 0.90
            result["structured"] = True
            return result
        except json.JSONDecodeError:
            logger.warning("Failed to parse prescription JSON, returning raw text")
            return {
                "raw_text": content,
                "confidence": 0.75,
                "medications": [],
                "structured": False
            }

    except Exception as e:
        logger.exception("OpenAI Vision prescription extraction failed: %s", e)
        return None


def correct_handwritten_text(raw_text: str) -> Optional[dict]:
    """
    Apply AI correction specifically optimized for handwritten text.
    Uses OpenAI GPT-4o-mini to fix common handwritten OCR errors.

    Args:
        raw_text: Raw OCR text from handwritten document

    Returns:
        Dictionary with corrected text and confidence score.
    """
    if not client:
        logger.warning("OpenAI client not configured for handwritten text correction.")
        return {"corrected_text": raw_text, "confidence": 0.5, "changes_made": []}
        
    if not raw_text:
        return None

    try:
        system_msg = (
            "You are a handwriting recognition expert. Fix OCR errors in handwritten text. "
            "Common issues: cursive connections, similar letters (a/o, n/u, l/1, 0/O), "
            "inconsistent spacing, and smudged characters. "
            "Return ONLY valid JSON with no markdown."
        )
        user_msg = (
            "Correct this handwritten text OCR output:\n\n"
            "{\n"
            '  "corrected_text": "the corrected text",\n'
            '  "confidence": 0.95,\n'
            '  "changes_made": ["list of corrections applied"]\n'
            "}\n\n"
            f"HANDWRITTEN TEXT:\n{raw_text}"
        )

        response = client.chat.completions.create(
            model=_TEXT_MODEL,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg}
            ],
            temperature=0.2,
            max_tokens=2000
        )

        content = response.choices[0].message.content.strip()

        # Strip markdown code fences
        if content.startswith("```"):
            lines = content.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            content = "\n".join(lines)

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"corrected_text": raw_text, "confidence": 0.5, "changes_made": []}

    except Exception as e:
        logger.exception("Handwritten text correction failed: %s", e)
        return {"corrected_text": raw_text, "confidence": 0.5, "changes_made": []}


# Backward compatibility aliases
def extract_text_with_bytez_ocr(image_path: str) -> Optional[dict]:
    """Backward compatibility wrapper - now uses OpenAI Vision."""
    return extract_handwritten_text_with_openai(image_path)


def extract_medical_prescription(image_path: str) -> Optional[dict]:
    """Backward compatibility wrapper - now uses OpenAI Vision."""
    return extract_medical_prescription_with_openai(image_path)
