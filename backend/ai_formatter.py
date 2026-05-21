import logging
import json
import base64
import os
from typing import Optional
import openai
from dotenv import load_dotenv

# Load environment variables from .env file (works whether run from backend/ or project root)
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))

logger = logging.getLogger(__name__)

# ── OpenAI client (via OpenRouter) ─────────────────────────────────────────────
_OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")
_OPENROUTER_BASE = os.getenv("OPENROUTER_BASE", "https://openrouter.ai/api/v1")
_TEXT_MODEL   = "openai/gpt-4o-mini"        # For text correction
_VISION_MODEL = "google/gemini-2.5-flash"   # For image OCR - vision capable

if _OPENAI_API_KEY:
    try:
        if os.getenv("OPENROUTER_API_KEY") or str(_OPENAI_API_KEY).startswith("sk-or-"):
            logger.info("Configuring OpenAI client to use OpenRouter at %s", _OPENROUTER_BASE)
            client = openai.OpenAI(base_url=_OPENROUTER_BASE, api_key=_OPENAI_API_KEY)
        else:
            logger.info("Configuring OpenAI client to use official OpenAI endpoint")
            client = openai.OpenAI(api_key=_OPENAI_API_KEY)
    except Exception as e:
        logger.exception("Failed to initialize OpenAI/OpenRouter client: %s", e)
        client = None
else:
    logger.warning("OpenAI API key not configured. Set OPENAI_API_KEY or OPENROUTER_API_KEY.")
    client = None


def _get_active_client():
    """Return the module-level client, or build one on-demand from env vars.
    This ensures production env vars (e.g. Render) are always picked up even
    if they weren't set when the module was first imported."""
    if client:
        return client
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return None
    try:
        if str(api_key).startswith("sk-or-"):
            return openai.OpenAI(base_url=_OPENROUTER_BASE, api_key=api_key)
        return openai.OpenAI(api_key=api_key)
    except Exception as e:
        logger.exception("Failed to create OpenAI client on-demand: %s", e)
        return None


def _get_image_mime_type(image_path: str) -> str:
    """Return the correct MIME type based on file extension."""
    ext = os.path.splitext(image_path)[1].lower()
    return {
        '.png':  'image/png',
        '.gif':  'image/gif',
        '.webp': 'image/webp',
        '.bmp':  'image/bmp',
    }.get(ext, 'image/jpeg')


def _encode_image_to_base64(image_path: str) -> str:
    """Encode an image file to base64 string."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode('utf-8')


def _strip_code_fences(content: str) -> str:
    """Remove markdown code fences from a string."""
    if content.startswith("```"):
        lines = content.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        content = "\n".join(lines)
    return content.strip()


# ── Public API ───────────────────────────────────────────────────────────────

def format_text_with_ai(raw_text: str) -> Optional[dict]:
    """Send raw OCR text to the AI model and return cleaned_text + summary.
    Returns None on any failure so callers can gracefully fall back."""
    active = _get_active_client()
    if not active:
        logger.warning("OpenAI client not configured.")
        return None

    raw_text = (raw_text or "").strip()
    if not raw_text:
        return None

    system = (
        "You are an expert OCR post-processing assistant. "
        "Your job is to take messy OCR output and produce clean, well-formatted text. "
        "Return ONLY a strict JSON object — no markdown, no code fences, no extra text."
    )
    user = (
        "The following text was extracted via OCR and contains errors. Clean it up:\n\n"
        "Rules:\n"
        "1. Remove stray pipe characters (|), stray dashes used as separators, and OCR artifacts.\n"
        "2. Fix garbled characters ONLY when clearly wrong (e.g. replace '_' or '¥' used as ':').\n"
        "   IMPORTANT: Keep all currency symbols exactly as-is (₹, $, €, £, ¥, etc.).\n"
        "3. Restore missing currency symbols before monetary amounts:\n"
        "   - If the text contains UPI, HDFC, SBI, ICICI, @hdfcbank, @okicici, @oksbi, paytm, gpay, phonepe, or any Indian payment reference → prefix amounts with ₹\n"
        "   - If the text contains USD, dollar, paypal, venmo → prefix amounts with $\n"
        "   - If the text contains EUR, euro → prefix amounts with €\n"
        "   Example: '25,000.00 Paid to ... UPI ID: ...' → '₹25,000.00 Paid to ...'\n"
        "4. Format structured data (ID cards, forms, receipts, payment confirmations) with each field on its own line as 'Label: Value'.\n"
        "5. Fix spacing and punctuation errors.\n"
        "6. Preserve ALL real data — names, numbers, dates, addresses, amounts — exactly as they appear.\n"
        "7. Do NOT add any information that is not in the original text.\n\n"
        "Also generate a short summary as 3-5 bullet points listing the key information found.\n\n"
        "Return EXACTLY this JSON format:\n"
        "{\n"
        '  "cleaned_text": "the fully cleaned and formatted text",\n'
        '  "summary": ["key point 1", "key point 2", "key point 3"]\n'
        "}\n\n"
        f"OCR TEXT:\n{raw_text}\n"
    )

    try:
        response = active.chat.completions.create(
            model=_TEXT_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            temperature=0.1,
            max_tokens=800,
        )
        content = _strip_code_fences(response.choices[0].message.content.strip())
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"cleaned_text": content, "summary": []}
    except Exception as e:
        logger.exception("OpenAI formatting request failed: %s", e)
        return None


def format_text_locally(raw_text: str) -> dict:
    """Lightweight local fallback formatter when AI is unavailable."""
    import re

    if not raw_text:
        return {"cleaned_text": "", "summary": ["No text provided."]}

    text = raw_text.strip()
    text = text.replace('\r', '\n')
    text = re.sub(r"[\t\u00A0]+", ' ', text)
    text = re.sub(r" +", ' ', text)
    text = text.replace('|', ' ')
    text = re.sub(r"\s+([,:.])", r"\1", text)
    text = re.sub(r":\s*", ': ', text)

    labels = ['PRN', 'Degree', 'Branch', 'Date of Birth', 'Blood Group', 'Tel', 'Phone', 'Date', 'Name']
    for lab in labels:
        pattern = re.compile(r"\s*" + re.escape(lab) + r"\s*[:\-–—]*\s*", flags=re.IGNORECASE)
        text = pattern.sub('\n' + lab + ': ', text)

    lines = [ln.strip() for ln in re.split(r"[\n]+", text) if ln.strip()]
    cleaned_text = '\n'.join(lines).strip()

    summary = ['Long OCR text cleaned locally.' if len(cleaned_text) > 200 else 'OCR text cleaned locally.']
    return {"cleaned_text": cleaned_text, "summary": summary}


def extract_handwritten_text_with_openai(image_path: str) -> Optional[dict]:
    """Extract text from a handwritten image using the vision model."""
    active = _get_active_client()
    if not active:
        logger.warning("OpenAI client not configured for handwritten text extraction.")
        return None
    if not image_path:
        return None

    try:
        base64_image = _encode_image_to_base64(image_path)
        mime_type = _get_image_mime_type(image_path)

        system_msg = (
            "You are an expert OCR system specialized in reading handwritten text. "
            "Extract ALL text from the image exactly as written. "
            "Preserve the original structure and line breaks. "
            "Return ONLY a valid JSON object: "
            '{"text": "the complete extracted text", "confidence": 0.95}'
        )

        response = active.chat.completions.create(
            model=_VISION_MODEL,
            messages=[
                {"role": "system", "content": system_msg},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extract all text from this image."},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{base64_image}"},
                        },
                    ],
                },
            ],
            temperature=0.0,
            max_tokens=800,
        )

        content = _strip_code_fences(response.choices[0].message.content.strip())
        try:
            result = json.loads(content)
            return {
                "text": result.get("text", content),
                "confidence": result.get("confidence", 0.90),
                "model": _VISION_MODEL,
            }
        except json.JSONDecodeError:
            return {"text": content, "confidence": 0.85, "model": _VISION_MODEL}

    except Exception as e:
        logger.exception("OpenAI Vision handwritten extraction failed: %s", e)
        return None


def extract_medical_prescription_with_openai(image_path: str) -> Optional[dict]:
    """Extract structured prescription data from an image using the vision model."""
    active = _get_active_client()
    if not active:
        logger.warning("OpenAI client not configured for prescription extraction.")
        return None
    if not image_path:
        return None

    try:
        base64_image = _encode_image_to_base64(image_path)
        mime_type = _get_image_mime_type(image_path)

        system_msg = (
            "You are a medical prescription expert. Extract structured data from prescription images. "
            "Return ONLY a valid JSON object with no markdown formatting."
        )
        user_msg = (
            "Extract these fields from the prescription image as JSON:\n"
            '{"doctor_name":null,"patient_name":null,"date":null,'
            '"medications":[{"name":"","dosage":"","frequency":"","duration":""}],'
            '"instructions":null,"pharmacy_name":null,"prescription_number":null,"raw_text":""}\n'
            "Use null for missing fields. Be careful with medication names and dosages."
        )

        response = active.chat.completions.create(
            model=_VISION_MODEL,
            messages=[
                {"role": "system", "content": system_msg},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_msg},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{base64_image}"},
                        },
                    ],
                },
            ],
            temperature=0.0,
            max_tokens=800,
        )

        content = _strip_code_fences(response.choices[0].message.content.strip())
        try:
            result = json.loads(content)
            result["confidence"] = 0.90
            result["structured"] = True
            return result
        except json.JSONDecodeError:
            logger.warning("Failed to parse prescription JSON, returning raw text")
            return {"raw_text": content, "confidence": 0.75, "medications": [], "structured": False}

    except Exception as e:
        logger.exception("OpenAI Vision prescription extraction failed: %s", e)
        return None


def correct_handwritten_text(raw_text: str) -> Optional[dict]:
    """Apply AI correction optimized for handwritten text."""
    active = _get_active_client()
    if not active:
        return {"corrected_text": raw_text, "confidence": 0.5, "changes_made": []}
    if not raw_text:
        return None

    system_msg = (
        "You are a handwriting recognition expert. Fix OCR errors in handwritten text. "
        "Common issues: cursive connections, similar letters (a/o, n/u, l/1, 0/O). "
        "Return ONLY valid JSON with no markdown."
    )
    user_msg = (
        "Correct this handwritten OCR text and return JSON:\n"
        '{"corrected_text":"...","confidence":0.95,"changes_made":[]}\n\n'
        f"HANDWRITTEN TEXT:\n{raw_text}"
    )

    try:
        response = active.chat.completions.create(
            model=_TEXT_MODEL,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user",   "content": user_msg},
            ],
            temperature=0.2,
            max_tokens=800,
        )
        content = _strip_code_fences(response.choices[0].message.content.strip())
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"corrected_text": raw_text, "confidence": 0.5, "changes_made": []}
    except Exception as e:
        logger.exception("Handwritten text correction failed: %s", e)
        return {"corrected_text": raw_text, "confidence": 0.5, "changes_made": []}


# Backward compatibility aliases
def extract_text_with_bytez_ocr(image_path: str) -> Optional[dict]:
    return extract_handwritten_text_with_openai(image_path)


def extract_medical_prescription(image_path: str) -> Optional[dict]:
    return extract_medical_prescription_with_openai(image_path)
