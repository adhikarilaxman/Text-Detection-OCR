import base64
import json
import logging
import os

from flask import Flask, jsonify, request
from flask_cors import CORS
import openai


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE = "https://openrouter.ai/api/v1"
VISION_MODEL = os.getenv("OCR_VISION_MODEL", "openai/gpt-4o")
TEXT_MODEL = os.getenv("OCR_TEXT_MODEL", "openai/gpt-4o-mini")

client = (
    openai.OpenAI(base_url=OPENROUTER_BASE, api_key=OPENAI_API_KEY)
    if OPENAI_API_KEY
    else None
)

app = Flask(__name__)
CORS(app)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024


def _strip_json_fence(content):
    content = (content or "").strip()
    if content.startswith("```"):
        lines = content.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        content = "\n".join(lines).strip()
    return content


def _get_upload():
    if "image" not in request.files:
        return None, ("No image file provided.", 400)

    file = request.files["image"]
    if not file or not file.filename:
        return None, ("Invalid image file.", 400)

    image_bytes = file.read()
    if not image_bytes or len(image_bytes) < 100:
        return None, ("File is too small or empty.", 400)

    return image_bytes, None


def _extract_text_with_ai(image_bytes, prompt):
    if not client:
        return None, "AI OCR is not configured. Set OPENROUTER_API_KEY in Vercel environment variables."

    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    response = client.chat.completions.create(
        model=VISION_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a precise OCR engine. Extract the visible text from the image. "
                    "Preserve line breaks and wording. Return only valid JSON."
                ),
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_b64}",
                        },
                    },
                ],
            },
        ],
        temperature=0,
        max_tokens=2500,
    )

    content = _strip_json_fence(response.choices[0].message.content)
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        data = {"text": content, "confidence": 0.85}

    text = data.get("text") or data.get("raw_text") or ""
    confidence = data.get("confidence", 0.9)
    return {"text": text, "confidence": confidence, "model": VISION_MODEL}, None


def _text_response(result, mode_used):
    text = result.get("text", "")
    return jsonify(
        {
            "success": True,
            "text": text,
            "full_text": text,
            "raw_text": text,
            "confidence": result.get("confidence", 0.9),
            "results": [],
            "processed_image": None,
            "heatmap_image": None,
            "total_regions": 0,
            "image_type": "ai_ocr",
            "preprocessing_steps": ["ai_vision"],
            "mode_used": mode_used,
            "ocr_engine": "openai_vision",
            "model": result.get("model", VISION_MODEL),
            "extraction_method": "openai_vision",
        }
    )


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify(
        {
            "status": "healthy",
            "tesseract_available": False,
            "ai_vision_available": bool(client),
            "runtime": "vercel_serverless",
        }
    )


@app.route("/api/ocr", methods=["POST"])
@app.route("/api/handwritten-ocr", methods=["POST"])
@app.route("/api/ocr/bytez/handwritten", methods=["POST"])
def ocr():
    image_bytes, error = _get_upload()
    if error:
        message, status = error
        return jsonify({"error": message}), status

    result, err = _extract_text_with_ai(
        image_bytes,
        (
            'Extract all readable printed or handwritten text from this image. '
            'Return JSON exactly like {"text":"...","confidence":0.95}.'
        ),
    )
    if err:
        return jsonify({"error": err}), 503

    return _text_response(result, "vercel-ai-ocr")


@app.route("/api/prescription-ocr", methods=["POST"])
@app.route("/api/ocr/bytez/prescription", methods=["POST"])
def prescription_ocr():
    image_bytes, error = _get_upload()
    if error:
        message, status = error
        return jsonify({"error": message}), status

    result, err = _extract_text_with_ai(
        image_bytes,
        (
            "Extract text from this medical prescription image. Return JSON exactly like "
            '{"text":"complete transcription","confidence":0.95}.'
        ),
    )
    if err:
        return jsonify({"error": err}), 503

    response = _text_response(result, "vercel-ai-prescription-ocr")
    return response


@app.route("/api/clean-text", methods=["POST"])
@app.route("/api/ai_format", methods=["POST"])
def clean_text():
    payload = request.get_json(force=True, silent=True) or {}
    raw_text = (payload.get("text") or payload.get("raw_text") or "").strip()
    if not raw_text:
        return jsonify({"error": "No text provided.", "cleaned_text": "", "summary": []}), 400

    if not client:
        return jsonify({"cleaned_text": raw_text, "summary": [], "used_ai": False}), 200

    response = client.chat.completions.create(
        model=TEXT_MODEL,
        messages=[
            {
                "role": "system",
                "content": "Fix obvious OCR errors without changing meaning. Return only valid JSON.",
            },
            {
                "role": "user",
                "content": (
                    'Return JSON exactly like {"cleaned_text":"...","summary":[]}. '
                    f"OCR text:\n{raw_text}"
                ),
            },
        ],
        temperature=0.1,
        max_tokens=2000,
    )
    content = _strip_json_fence(response.choices[0].message.content)
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        data = {"cleaned_text": content, "summary": []}

    return jsonify(
        {
            "cleaned_text": data.get("cleaned_text", raw_text),
            "summary": data.get("summary", []),
            "used_ai": True,
        }
    )


@app.route("/api/template", methods=["POST"])
def template():
    payload = request.get_json(force=True, silent=True) or {}
    raw_text = payload.get("text", "")
    return jsonify(
        {
            "document_type": "unknown",
            "type_confidence": 0,
            "fields": {},
            "field_count": 0,
            "raw_text": raw_text,
        }
    )


@app.route("/api/correction", methods=["POST"])
def correction():
    return jsonify({"success": True, "message": "Corrections are not persisted on Vercel."})


@app.route("/api/correction/stats", methods=["GET"])
def correction_stats():
    return jsonify(
        {
            "total_learned_words": 0,
            "total_correction_uses": 0,
            "top_corrections": [],
            "learning_active": False,
        }
    )
