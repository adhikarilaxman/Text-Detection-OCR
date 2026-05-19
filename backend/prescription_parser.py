import logging
import json
import os
from typing import Optional
import openai

logger = logging.getLogger(__name__)

# Use OpenRouter for AI access
_OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")
_OPENROUTER_BASE = "https://openrouter.ai/api/v1"
_MODEL_ID       = "openai/gpt-4o-mini"

if _OPENAI_API_KEY:
    try:
        _client = openai.OpenAI(
            base_url=_OPENROUTER_BASE,
            api_key=_OPENAI_API_KEY
        )
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client: {e}")
        _client = None
else:
    logger.warning("OpenAI API key not configured. Set OPENAI_API_KEY or OPENROUTER_API_KEY environment variable.")
    _client = None

def _build_prescription_messages(raw_text: str) -> list:
    system = (
        "You are an expert medical transcriptionist and pharmacist. "
        "Return ONLY a strict JSON object — no markdown, no code fences, no extra text."
    )
    user = (
        "The following text is OCR extracted from a handwritten doctor's prescription.\n"
        "Your task is to identify the listed medicines, their dosage (e.g. mg/ml), and frequency.\n"
        "You must explicitly convert any medical abbreviations into their full forms:\n"
        "- OD -> Once a day\n"
        "- BD/BID -> Twice a day\n"
        "- TID/TDS -> Three times a day\n"
        "- QID -> Four times a day\n"
        "- SOS -> As needed\n"
        "- HS -> At bedtime\n"
        "- AC -> Before meals\n"
        "- PC -> After meals\n\n"
        "Return EXACTLY in this JSON format:\n"
        "{\n"
        '  "medicines": [\n'
        '    {"name": "...", "dosage": "...", "frequency": "...", "notes": "..."}\n'
        "  ]\n"
        "}\n\n"
        f"OCR TEXT:\n{raw_text}\n"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user",   "content": user},
    ]

def parse_prescription_with_ai(raw_text: str) -> Optional[dict]:
    """
    Parses OCR text of a prescription using AI, extracting medicines and expanding abbreviations.
    Returns a dict that can be mapped directly to the frontend's template fields.
    """
    raw_text = (raw_text or "").strip()
    if not raw_text or _client is None:
        return None

    try:
        messages = _build_prescription_messages(raw_text)
        response = _client.chat.completions.create(
            model=_MODEL_ID,
            messages=messages,
            temperature=0.1,
            max_tokens=1000
        )

        content = response.choices[0].message.content.strip()

        if content.startswith("```"):
            lines = content.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            content = "\n".join(lines)

        data = json.loads(content)
        
        # Transform into a flat field dictionary for the frontend "Smart Extraction" template
        fields = {}
        medicines = data.get("medicines", [])
        
        for i, med in enumerate(medicines):
            name = med.get("name", "Unknown Medicine")
            dosage = med.get("dosage", "")
            freq = med.get("frequency", "")
            
            # Combine parts cleanly
            med_info = name.strip()
            if dosage and dosage.lower() != "unknown" and dosage != "N/A":
                med_info += f" {dosage.strip()}"
            if freq and freq.lower() != "unknown" and freq != "N/A":
                med_info += f" - {freq.strip()}"
                
            fields[f"Medicine_{i+1}"] = med_info

        return {
            "document_type": "medical_prescription",
            "type_confidence": 95,
            "fields": fields,
            "field_count": len(fields)
        }

    except Exception as e:
        logger.exception("Prescription AI parser request failed: %s", e)
        return None
