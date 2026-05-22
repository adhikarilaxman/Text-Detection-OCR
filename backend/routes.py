import logging
import os
import tempfile
from flask import Blueprint, request, jsonify

from ai_formatter import (
    format_text_with_ai,
    correct_handwritten_text,
    extract_handwritten_text_with_openai,
    extract_medical_prescription_with_openai,
    _get_active_client,
)
from utils import (
    is_tesseract_available,
    allowed_file,
    decode_image,
    extract_raw_text,
    image_to_base64,
    MIN_IMAGE_DIMENSION,
    perform_ocr_with_retry,
    generate_confidence_heatmap,
    extract_template_fields,
    submit_correction,
    apply_learned_corrections,
    get_correction_stats,
)

logger = logging.getLogger(__name__)
api = Blueprint('api', __name__)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _save_upload_to_temp(file):
    suffix = os.path.splitext(file.filename or '')[1].lower()
    if suffix not in {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp'}:
        suffix = '.img'
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.close()
    file.save(tmp.name)
    return tmp.name


def _save_bytes_to_temp(image_bytes, filename=None):
    suffix = os.path.splitext(filename or '')[1].lower()
    if suffix not in {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp'}:
        suffix = '.img'
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(image_bytes)
    tmp.close()
    return tmp.name


def _remove(path):
    try:
        os.remove(path)
    except Exception:
        pass


def _ai_vision_response(file_bytes, filename, image_type='normal'):
    """Run AI Vision extraction and return a standard response dict, or None on failure."""
    temp_path = _save_bytes_to_temp(file_bytes, filename)
    try:
        result = extract_handwritten_text_with_openai(temp_path)
        if result and result.get('text'):
            raw = result['text']
            return {
                'success': True,
                'text': raw,
                'full_text': raw,
                'raw_text': raw,
                'confidence': result.get('confidence', 0.85),
                'results': [],
                'processed_image': None,
                'heatmap_image': None,
                'total_regions': 0,
                'image_type': image_type,
                'preprocessing_steps': ['ai_vision'],
                'mode_used': 'ai-vision',
                'ocr_engine': 'gemini_vision',
                'template': {},
            }
        return None
    finally:
        _remove(temp_path)


# ── Routes ────────────────────────────────────────────────────────────────────

@api.route('/health', methods=['GET'])
def health_check():
    return {
        'status': 'healthy',
        'tesseract_available': is_tesseract_available(),
        'ai_available': _get_active_client() is not None,
    }, 200


@api.route('/ocr', methods=['POST'])
def ocr_endpoint():
    """Standard OCR — Tesseract when available, AI Vision fallback otherwise."""
    try:
        if 'image' not in request.files:
            return {'error': 'No image file provided.'}, 400
        file = request.files['image']
        if not file.filename or not allowed_file(file.filename):
            return {'error': 'A valid image file must be selected.'}, 400

        image_bytes = file.read()
        if len(image_bytes) < 100:
            return {'error': 'File is too small or empty.'}, 400

        logger.info("Standard OCR request: %s", file.filename)

        # ── AI Vision path (Tesseract unavailable or on Render) ──────────────
        if not is_tesseract_available():
            logger.info("Tesseract unavailable — using AI Vision for standard OCR")
            resp = _ai_vision_response(image_bytes, file.filename, image_type='normal')
            if resp:
                return resp, 200
            return {'error': 'OCR failed: Tesseract is not installed and AI Vision also failed. Check OPENAI_API_KEY.'}, 503

        # ── Tesseract path ────────────────────────────────────────────────────
        image = decode_image(image_bytes)
        if image is None:
            return {'error': 'Could not decode image.'}, 400
        h, w = image.shape[:2]
        if h < MIN_IMAGE_DIMENSION or w < MIN_IMAGE_DIMENSION:
            return {'error': 'Image is too small.'}, 400

        results, processed, img_type, steps, confidence = perform_ocr_with_retry(
            image, mode='auto', confidence_threshold=50, max_retries=2
        )
        raw_text = extract_raw_text(processed) or ' '.join(r['text'] for r in results)
        corrected = apply_learned_corrections(raw_text)
        template = extract_template_fields(corrected, results)

        return {
            'success': True,
            'text': corrected,
            'full_text': corrected,
            'raw_text': raw_text,
            'confidence': round(confidence, 2),
            'results': results,
            'processed_image': image_to_base64(processed),
            'heatmap_image': image_to_base64(generate_confidence_heatmap(image, results)),
            'total_regions': len(results),
            'image_type': img_type,
            'preprocessing_steps': steps,
            'mode_used': 'auto',
            'ocr_engine': 'tesseract',
            'template': template,
        }, 200

    except Exception as e:
        logger.exception("OCR endpoint error: %s", e)
        return {'error': f'OCR failed: {e}'}, 500


@api.route('/handwritten-ocr', methods=['POST'])
def handwritten_ocr_endpoint():
    """Handwritten OCR — always uses AI Vision (Gemini)."""
    try:
        if 'image' not in request.files:
            return {'error': 'No image file provided.'}, 400
        file = request.files['image']
        if not file.filename or not allowed_file(file.filename):
            return {'error': 'A valid image file must be selected.'}, 400

        image_bytes = file.read()
        if len(image_bytes) < 100:
            return {'error': 'File is too small or empty.'}, 400

        logger.info("Handwritten OCR request: %s", file.filename)

        resp = _ai_vision_response(image_bytes, file.filename, image_type='handwritten')
        if resp:
            # Apply AI text correction on top
            try:
                corrected = correct_handwritten_text(resp['raw_text'])
                if corrected and isinstance(corrected, dict) and corrected.get('corrected_text'):
                    resp['text'] = corrected['corrected_text']
                    resp['full_text'] = corrected['corrected_text']
            except Exception:
                pass
            return resp, 200

        return {'error': 'Handwritten OCR failed. Ensure OPENAI_API_KEY is set in Render environment variables.'}, 503

    except Exception as e:
        logger.exception("Handwritten OCR error: %s", e)
        return {'error': f'Handwritten OCR failed: {e}'}, 500


@api.route('/prescription-ocr', methods=['POST'])
def prescription_ocr_endpoint():
    """Medical Prescription OCR — always uses AI Vision (Gemini)."""
    try:
        if 'image' not in request.files:
            return {'error': 'No image file provided.'}, 400
        file = request.files['image']
        if not file.filename or not allowed_file(file.filename):
            return {'error': 'A valid image file must be selected.'}, 400

        image_bytes = file.read()
        if len(image_bytes) < 100:
            return {'error': 'File is too small or empty.'}, 400

        logger.info("Prescription OCR request: %s", file.filename)

        temp_path = _save_bytes_to_temp(image_bytes, file.filename)
        try:
            result = extract_medical_prescription_with_openai(temp_path)
            if result:
                return {
                    'success': True,
                    'text': result.get('raw_text', ''),
                    'full_text': result.get('raw_text', ''),
                    'raw_text': result.get('raw_text', ''),
                    'confidence': result.get('confidence', 0.85),
                    'results': [],
                    'processed_image': None,
                    'heatmap_image': None,
                    'total_regions': 0,
                    'image_type': 'prescription',
                    'preprocessing_steps': ['ai_vision'],
                    'mode_used': 'ai-prescription',
                    'ocr_engine': 'gemini_vision',
                    'template': {
                        'document_type': 'prescription',
                        'fields': {
                            'doctor_name': result.get('doctor_name'),
                            'patient_name': result.get('patient_name'),
                            'date': result.get('date'),
                            'medications': result.get('medications', []),
                            'instructions': result.get('instructions'),
                        },
                    },
                }, 200
        finally:
            _remove(temp_path)

        return {'error': 'Prescription OCR failed. Ensure OPENAI_API_KEY is set in Render environment variables.'}, 503

    except Exception as e:
        logger.exception("Prescription OCR error: %s", e)
        return {'error': f'Prescription OCR failed: {e}'}, 500


@api.route('/clean-text', methods=['POST'])
def clean_text_endpoint():
    try:
        payload = request.get_json(force=True, silent=True) or {}
        raw_text = (payload.get('text') or payload.get('raw_text') or '').strip()
        if not raw_text:
            return {'error': 'No text provided', 'cleaned_text': '', 'summary': []}, 400

        result = format_text_with_ai(raw_text)
        if result:
            return {
                'cleaned_text': result.get('cleaned_text', raw_text),
                'summary': result.get('summary', []),
                'used_ai': True,
            }, 200

        # Local fallback
        from ai_formatter import format_text_locally
        local = format_text_locally(raw_text)
        return {'cleaned_text': local.get('cleaned_text', raw_text), 'summary': local.get('summary', []), 'used_ai': False}, 200

    except Exception as e:
        logger.exception('clean-text error: %s', e)
        return {'error': 'AI processing failed.'}, 500


@api.route('/correction', methods=['POST'])
def correction_endpoint():
    try:
        payload = request.get_json(force=True, silent=True) or {}
        original = payload.get('original', '').strip()
        corrected = payload.get('corrected', '').strip()
        if not original or not corrected:
            return {'error': 'Both original and corrected text are required.'}, 400
        result = submit_correction(original, corrected)
        return (result, 200) if result.get('success') else ({'error': result.get('error', 'Failed')}, 400)
    except Exception as e:
        logger.exception('Correction error: %s', e)
        return {'error': 'Failed to save correction.'}, 500


@api.route('/correction/stats', methods=['GET'])
def correction_stats_endpoint():
    try:
        return get_correction_stats(), 200
    except Exception as e:
        logger.exception('Correction stats error: %s', e)
        return {'error': 'Failed to get stats.'}, 500


@api.route('/template', methods=['POST'])
def template_extraction_endpoint():
    try:
        payload = request.get_json(force=True, silent=True) or {}
        raw_text = payload.get('text', '').strip()
        if not raw_text:
            return {'error': 'No text provided.'}, 400
        return extract_template_fields(raw_text), 200
    except Exception as e:
        logger.exception('Template extraction error: %s', e)
        return {'error': 'Failed to extract template fields.'}, 500


@api.route('/ocr/bytez/handwritten', methods=['POST'])
def bytez_handwritten_ocr_endpoint():
    """AI Vision handwritten extraction endpoint."""
    try:
        if 'image' not in request.files:
            return {'error': 'No image file provided.'}, 400
        file = request.files['image']
        if not file.filename or not allowed_file(file.filename):
            return {'error': 'Invalid image file.'}, 400

        temp_path = _save_upload_to_temp(file)
        try:
            logger.info("AI Vision handwritten OCR: %s", file.filename)
            result = extract_handwritten_text_with_openai(temp_path)
            if result:
                raw = result.get('text', '')
                return {
                    'success': True,
                    'text': raw, 'full_text': raw, 'raw_text': raw,
                    'confidence': result.get('confidence', 0.85),
                    'model': result.get('model', ''),
                    'extraction_method': 'ai_vision',
                }, 200
            return {'error': 'AI Vision extraction failed.'}, 503
        finally:
            _remove(temp_path)
    except Exception as e:
        logger.exception('bytez handwritten error: %s', e)
        return {'error': f'Handwritten extraction failed: {e}'}, 500


@api.route('/ocr/bytez/prescription', methods=['POST'])
def bytez_prescription_ocr_endpoint():
    """AI Vision prescription extraction endpoint."""
    try:
        if 'image' not in request.files:
            return {'error': 'No image file provided.'}, 400
        file = request.files['image']
        if not file.filename or not allowed_file(file.filename):
            return {'error': 'Invalid image file.'}, 400

        temp_path = _save_upload_to_temp(file)
        try:
            logger.info("AI Vision prescription OCR: %s", file.filename)
            result = extract_medical_prescription_with_openai(temp_path)
            if result:
                return {
                    'success': True,
                    'structured': result.get('structured', False),
                    'doctor_name': result.get('doctor_name'),
                    'patient_name': result.get('patient_name'),
                    'date': result.get('date'),
                    'medications': result.get('medications', []),
                    'instructions': result.get('instructions'),
                    'text': result.get('raw_text', ''),
                    'full_text': result.get('raw_text', ''),
                    'raw_text': result.get('raw_text', ''),
                    'confidence': result.get('confidence', 0.85),
                    'extraction_method': 'ai_vision',
                }, 200
            return {'error': 'AI Vision prescription extraction failed.'}, 503
        finally:
            _remove(temp_path)
    except Exception as e:
        logger.exception('bytez prescription error: %s', e)
        return {'error': f'Prescription extraction failed: {e}'}, 500


@api.route('/admin/set_api_key', methods=['POST'])
def set_api_key():
    try:
        payload = request.get_json(force=True, silent=True) or {}
        key = (payload.get('key') or '').strip()
        if not key:
            return {'error': 'No API key provided.'}, 400
        os.environ['OPENAI_API_KEY'] = key
        # Reset the cached client so _get_active_client() picks up the new key
        import ai_formatter as _af
        _af._cached_client = None
        _af._cached_key = None
        return {'success': True, 'message': 'API key updated.'}, 200
    except Exception as e:
        logger.exception('set_api_key error: %s', e)
        return {'error': 'Failed to update API key.'}, 500
