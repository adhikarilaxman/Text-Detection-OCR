import logging
import os
import tempfile
from flask import Blueprint, request, jsonify
import handwritten_ocr
import prescription_parser

# Import the existing ai_formatter directly
from ai_formatter import (
    format_text_with_ai,
    correct_handwritten_text,
    extract_handwritten_text_with_openai,
    extract_medical_prescription_with_openai
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
    get_correction_stats
)

logger = logging.getLogger(__name__)

# Create the blueprint for all API routes
api = Blueprint('api', __name__)


def _build_local_handwritten_response(image, image_type='handwritten', mode_used='local-handwritten-fallback'):
    """Run local EasyOCR handwriting extraction and shape the standard API response."""
    ocr_data = handwritten_ocr.extract_handwritten_text(image)
    raw_text = ocr_data['raw_text']
    correction_result = correct_handwritten_text(raw_text)
    corrected_text = correction_result.get('corrected_text', raw_text) if correction_result else raw_text
    processed_image_base64 = image_to_base64(ocr_data['processed_image'])
    heatmap_base64 = image_to_base64(generate_confidence_heatmap(image, ocr_data['results']))
    template_data = extract_template_fields(corrected_text, ocr_data['results'])

    return {
        'success': True,
        'text': corrected_text,
        'full_text': corrected_text,
        'raw_text': raw_text,
        'confidence': round(ocr_data['confidence'], 2),
        'results': ocr_data['results'],
        'processed_image': processed_image_base64,
        'heatmap_image': heatmap_base64,
        'total_regions': len(ocr_data['results']),
        'image_type': image_type,
        'preprocessing_steps': ['grayscale', 'median_blur', 'adaptive_threshold'],
        'mode_used': mode_used,
        'ocr_engine': 'easyocr',
        'template': template_data,
        'extraction_method': 'local_easyocr'
    }


def _save_upload_to_temp(file):
    """Persist an uploaded image to a unique temporary file and return its path."""
    suffix = os.path.splitext(file.filename or '')[1].lower()
    if suffix not in {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp'}:
        suffix = '.img'

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    temp_path = temp_file.name
    temp_file.close()
    file.save(temp_path)
    return temp_path

@api.route('/health', methods=['GET'])
def health_check():
    """Basic health check endpoint to verify backend status and Tesseract availability."""
    tesseract_available = is_tesseract_available()
    return jsonify({
        'status': 'healthy',
        'tesseract_available': tesseract_available
    }), 200

@api.route('/ocr', methods=['POST'])
def ocr_endpoint():
    """
    Main OCR endpoint. Accepts an image upload, processes it with adaptive preprocessing,
    and returns text with enhanced support for blurry and handwritten images.
    
    Query Parameters:
        - mode: 'auto' (default), 'blur', 'handwritten', or 'normal'
        - use_handwriting_config: true/false to use handwriting-optimized Tesseract config
        - use_advanced_handwriting: true/false to use the complete advanced handwritten OCR pipeline
    """
    try:
        if not is_tesseract_available():
            logger.error("OCR requested but Tesseract is not available")
            return jsonify({
                'error': 'Tesseract OCR is not installed or not found. Please verify the installation path.'
            }), 503

        if 'image' not in request.files:
            return jsonify({'error': 'No image file provided in the request.'}), 400
            
        file = request.files['image']
        if file.filename == '' or not allowed_file(file.filename):
            return jsonify({'error': 'A valid image file must be selected.'}), 400

        image_bytes = file.read()
        if not image_bytes or len(image_bytes) < 100:
            logger.warning("Rejected upload: file is empty or too small")
            return jsonify({'error': 'File is too small or empty. Please upload a valid image.'}), 400

        logger.info(f"Processing image upload: {file.filename}")
        
        # Decode the image
        image = decode_image(image_bytes)
        if image is None:
            logger.warning("Failed to decode the provided image.")
            return jsonify({
                'error': 'Could not decode image. Please use a supported format (PNG, JPG, JPEG) and ensure it is not corrupted.'
            }), 400

        h, w = image.shape[:2]
        if h < MIN_IMAGE_DIMENSION or w < MIN_IMAGE_DIMENSION:
            return jsonify({'error': 'Image dimensions are too small. Please use a larger image.'}), 400

        # Run normal OCR logic
        ocr_results, processed_image, image_type, applied_steps, avg_confidence = perform_ocr_with_retry(
            image, 
            mode='auto',
            confidence_threshold=50,
            max_retries=2
        )
        ocr_engine = 'tesseract'
        
        # Extract raw text
        raw_text = extract_raw_text(processed_image)
        if not raw_text and ocr_results:
            raw_text = ' '.join([r['text'] for r in ocr_results])
        
        # Apply learned corrections from previous user feedback
        corrected_text = apply_learned_corrections(raw_text)
        if corrected_text != raw_text:
            logger.info("Applied learned corrections to OCR text")
        
        processed_image_base64 = image_to_base64(processed_image)
        
        # Generate confidence heatmap overlay
        heatmap_image = generate_confidence_heatmap(image, ocr_results)
        heatmap_base64 = image_to_base64(heatmap_image)
        
        # Extract structured template fields
        template_data = extract_template_fields(corrected_text, ocr_results)

        return jsonify({
            'success': True,
            'text': corrected_text,
            'full_text': corrected_text,
            'raw_text': raw_text,
            'corrected_text': corrected_text,
            'confidence': round(avg_confidence, 2),
            'results': ocr_results,
            'processed_image': processed_image_base64,
            'heatmap_image': heatmap_base64,
            'total_regions': len(ocr_results),
            'image_type': image_type,
            'preprocessing_steps': applied_steps,
            'mode_used': 'auto',
            'ocr_engine': ocr_engine,
            'template': template_data
        }), 200

    except Exception as e:
        error_msg = str(e)
        logger.exception("OCR endpoint encountered an unexpected error: %s", e)

        if 'tesseract' in error_msg.lower():
            user_msg = 'Tesseract OCR is not installed or not found in system PATH.'
        elif 'memory' in error_msg.lower():
            user_msg = 'Image is too large and caused a memory error. Try a smaller image.'
        else:
            user_msg = 'Failed to process image due to an internal server error.'

        return jsonify({'error': user_msg}), 500

@api.route('/handwritten-ocr', methods=['POST'])
def handwritten_ocr_endpoint():
    """
    Dedicated endpoint for handwritten OCR.
    Applies custom preprocessing and uses EasyOCR from a separate module.
    """
    try:
        if 'image' not in request.files:
            return jsonify({'error': 'No image file provided in the request.'}), 400
            
        file = request.files['image']
        if file.filename == '' or not allowed_file(file.filename):
            return jsonify({'error': 'A valid image file must be selected.'}), 400

        image_bytes = file.read()
        if not image_bytes or len(image_bytes) < 100:
            logger.warning("Rejected upload: file is empty or too small")
            return jsonify({'error': 'File is too small or empty.'}), 400

        image = decode_image(image_bytes)
        if image is None:
            logger.warning("Failed to decode the provided image.")
            return jsonify({'error': 'Could not decode image.'}), 400

        # Perform handwritten OCR
        logger.info(f"Processing handwritten image upload: {file.filename}")
        response_data = _build_local_handwritten_response(
            image,
            image_type='handwritten',
            mode_used='handwritten-ocr-endpoint'
        )
        return jsonify(response_data), 200

    except Exception as e:
        logger.exception("Handwritten OCR endpoint error: %s", e)
        return jsonify({'error': 'Failed to process handwritten image due to an internal error.'}), 500

@api.route('/prescription-ocr', methods=['POST'])
def prescription_ocr_endpoint():
    """
    Endpoint for Medical Prescription OCR.
    Extracts handwritten text and parses medical terms using an AI agent.
    """
    try:
        if 'image' not in request.files:
            return jsonify({'error': 'No image file provided in the request.'}), 400
            
        file = request.files['image']
        if file.filename == '' or not allowed_file(file.filename):
            return jsonify({'error': 'A valid image file must be selected.'}), 400

        image_bytes = file.read()
        if not image_bytes or len(image_bytes) < 100:
            return jsonify({'error': 'File is too small or empty.'}), 400

        image = decode_image(image_bytes)
        if image is None:
            return jsonify({'error': 'Could not decode image.'}), 400

        # Perform handwritten OCR first (it's handwritten!)
        logger.info(f"Processing prescription image upload: {file.filename}")
        ocr_data = handwritten_ocr.extract_handwritten_text(image)
        
        raw_text = ocr_data['raw_text']
        
        # Apply specialized AI prescription parsing instead of standard text cleanup
        template_data = None
        if raw_text.strip():
            logger.info("Applying specialized prescription AI parsing")
            template_data = prescription_parser.parse_prescription_with_ai(raw_text)

        # Fallback if AI fails or no fields are found
        if not template_data:
            template_data = extract_template_fields(raw_text, ocr_data['results'])

        # Keep original corrected text logic for the main text display
        corrected_text = raw_text
        if raw_text.strip():
            try:
                ai_result = format_text_with_ai(raw_text)
                if ai_result and ai_result.get('cleaned_text'):
                    c_text = ai_result.get('cleaned_text', raw_text)
                    if c_text.strip() and len(c_text) >= len(raw_text) * 0.5:
                        corrected_text = c_text
            except Exception as e:
                logger.warning(f"Standard AI text correction failed during prescription flow: {e}")

        # Heatmap & base64
        processed_image_base64 = image_to_base64(ocr_data['processed_image'])
        heatmap_base64 = image_to_base64(generate_confidence_heatmap(image, ocr_data['results']))
        
        return jsonify({
            'success': True,
            'text': corrected_text,
            'full_text': corrected_text,
            'raw_text': raw_text,
            'confidence': round(ocr_data['confidence'], 2),
            'results': ocr_data['results'],
            'processed_image': processed_image_base64,
            'heatmap_image': heatmap_base64,
            'total_regions': len(ocr_data['results']),
            'image_type': 'prescription',
            'preprocessing_steps': ['grayscale', 'median_blur', 'adaptive_threshold', 'prescription_ai'],
            'mode_used': 'prescription-ocr-endpoint',
            'ocr_engine': 'easyocr',
            'template': template_data
        }), 200

    except Exception as e:
        logger.exception("Prescription OCR endpoint error: %s", e)
        return jsonify({'error': 'Failed to process prescription image due to an internal error.'}), 500

@api.route('/ai_format', methods=['POST'])
def ai_format_endpoint():
    """Accepts raw text and delegates to the AI formatter to clean it. Returns structured JSON."""
    try:
        payload = request.get_json(force=True, silent=True)
        raw_text = ''
        if payload and isinstance(payload, dict):
            raw_text = payload.get('text') or payload.get('raw_text') or ''
        
        # Fallback to form data
        if not raw_text:
            raw_text = request.form.get('text', '')

        raw_text = (raw_text or '').strip()
        if not raw_text:
            return jsonify({'success': False, 'error': 'No text provided to format.'}), 400

        ai_result = format_text_with_ai(raw_text)
        if ai_result is None:
            # AI not configured or failed - return fallback
            return jsonify({
                'success': True, 
                'cleaned_text': raw_text, 
                'summary': ["AI formatting unavailable."],
                'used_ai': False
            }), 200

        return jsonify({
            'success': True, 
            'cleaned_text': ai_result.get('cleaned_text', raw_text), 
            'summary': ai_result.get('summary', []),
            'used_ai': True
        }), 200
        
    except Exception as e:
        logger.exception('AI format endpoint experienced an error: %s', e)
        return jsonify({'success': False, 'error': 'AI formatting operation failed.'}), 500

@api.route('/clean-text', methods=['POST'])
def clean_text_endpoint():
    """Compatibility route requested by frontend. Wraps the AI formatter."""
    try:
        payload = request.get_json(force=True, silent=True) or {}
        raw_text = payload.get('text') or payload.get('raw_text') or ''
        raw_text = (raw_text or '').strip()
        
        if not raw_text:
            return jsonify({'error': 'No text provided', 'cleaned_text': '', 'summary': []}), 400

        ai_result = format_text_with_ai(raw_text)
        if ai_result is None:
            # AI not configured - return clear error instead of fallback
            return jsonify({
                'error': 'AI processing failed. Please set OPENAI_API_KEY in your environment.'
            }), 503
            
        cleaned_text = ai_result.get('cleaned_text', '').strip()
        summary = ai_result.get('summary', [])
        
        if not cleaned_text:
            return jsonify({'error': 'AI processing failed: empty response.'}), 500

        return jsonify({
            'cleaned_text': cleaned_text,
            'summary': summary
        }), 200
        
    except Exception:
        logger.exception('clean-text endpoint failed unexpectedly.')
        return jsonify({'error': 'AI processing failed due to an internal server error.'}), 500


@api.route('/correction', methods=['POST'])
def correction_endpoint():
    """
    Submit a user correction for the Interactive Learning system.
    
    The system stores corrections and automatically applies them to future OCR results.
    This creates a self-improving feedback loop unique to this OCR tool.
    
    Request Body:
        - original: The incorrect OCR text
        - corrected: The user's correction
    """
    try:
        payload = request.get_json(force=True, silent=True) or {}
        original = payload.get('original', '').strip()
        corrected = payload.get('corrected', '').strip()
        
        if not original or not corrected:
            return jsonify({'error': 'Both original and corrected text are required.'}), 400
        
        result = submit_correction(original, corrected)
        
        if result.get('success'):
            return jsonify(result), 200
        else:
            return jsonify({'error': result.get('error', 'Failed to save correction')}), 400
            
    except Exception as e:
        logger.exception('Correction endpoint failed: %s', e)
        return jsonify({'error': 'Failed to save correction.'}), 500


@api.route('/correction/stats', methods=['GET'])
def correction_stats_endpoint():
    """Get statistics about learned corrections."""
    try:
        stats = get_correction_stats()
        return jsonify(stats), 200
    except Exception as e:
        logger.exception('Correction stats endpoint failed: %s', e)
        return jsonify({'error': 'Failed to get correction stats.'}), 500


@api.route('/template', methods=['POST'])
def template_extraction_endpoint():
    """
    Extract structured fields from raw text using Smart Template Extraction.
    
    Auto-detects document type (receipt, invoice, ID card, form, letter)
    and extracts key-value pairs.
    
    Request Body:
        - text: Raw OCR text
    """
    try:
        payload = request.get_json(force=True, silent=True) or {}
        raw_text = payload.get('text', '').strip()
        
        if not raw_text:
            return jsonify({'error': 'No text provided.'}), 400
        
        result = extract_template_fields(raw_text)
        return jsonify(result), 200
        
    except Exception as e:
        logger.exception('Template extraction endpoint failed: %s', e)
        return jsonify({'error': 'Failed to extract template fields.'}), 500


@api.route('/ocr/bytez/handwritten', methods=['POST'])
def bytez_handwritten_ocr_endpoint():
    """
    Specialized endpoint for handwritten text extraction using OpenAI Vision API.
    Uses GPT-4o with vision capabilities for optimal handwritten text extraction.
    
    Request: multipart/form-data with 'image' file
    """
    try:
        if 'image' not in request.files:
            return jsonify({'error': 'No image file provided.'}), 400
        
        file = request.files['image']
        if file.filename == '' or not allowed_file(file.filename):
            return jsonify({'error': 'Invalid image file.'}), 400
        
        temp_path = _save_upload_to_temp(file)
        try:
            logger.info(f"Processing handwritten OCR with OpenAI Vision for: {file.filename}")
            result = extract_handwritten_text_with_openai(temp_path)

            if result:
                raw_text = result.get('text', '')

                return jsonify({
                    'success': True,
                    'text': raw_text,
                    'full_text': raw_text,
                    'raw_text': raw_text,
                    'confidence': result.get('confidence', 0.85),
                    'corrections_applied': [],
                    'model': result.get('model', 'gpt-4o'),
                    'extraction_method': 'openai_vision'
                }), 200

            logger.info("OpenAI Vision unavailable; falling back to local EasyOCR handwriting extraction.")
            with open(temp_path, 'rb') as temp_image:
                image = decode_image(temp_image.read())
            if image is None:
                return jsonify({'error': 'Could not decode image.'}), 400

            response_data = _build_local_handwritten_response(
                image,
                image_type='handwritten',
                mode_used='local-fallback-from-openai-handwritten'
            )
            response_data['extraction_method'] = 'local_easyocr_fallback'
            return jsonify(response_data), 200
        finally:
            try:
                os.remove(temp_path)
            except OSError:
                logger.warning("Could not remove temporary upload: %s", temp_path)
        
    except Exception as e:
        logger.exception('Handwritten OCR endpoint failed: %s', e)
        return jsonify({'error': 'Handwritten text extraction failed.'}), 500


@api.route('/ocr/bytez/prescription', methods=['POST'])
def bytez_prescription_ocr_endpoint():
    """
    Specialized endpoint for medical prescription extraction using OpenAI Vision API.
    Uses GPT-4o with vision capabilities for optimal prescription data extraction.

    Extracts structured prescription data:
    - Doctor name, patient name, date
    - Medications (name, dosage, frequency, duration)
    - Instructions, pharmacy info

    Request: multipart/form-data with 'image' file
    """
    try:
        if 'image' not in request.files:
            return jsonify({'error': 'No image file provided.'}), 400
        
        file = request.files['image']
        if file.filename == '' or not allowed_file(file.filename):
            return jsonify({'error': 'Invalid image file.'}), 400
        
        temp_path = _save_upload_to_temp(file)
        try:
            logger.info(f"Processing prescription extraction with OpenAI Vision for: {file.filename}")
            result = extract_medical_prescription_with_openai(temp_path)

            if result:
                return jsonify({
                    'success': True,
                    'structured': result.get('structured', False),
                    'doctor_name': result.get('doctor_name'),
                    'patient_name': result.get('patient_name'),
                    'date': result.get('date'),
                    'medications': result.get('medications', []),
                    'instructions': result.get('instructions'),
                    'pharmacy_name': result.get('pharmacy_name'),
                    'prescription_number': result.get('prescription_number'),
                    'text': result.get('raw_text', ''),
                    'full_text': result.get('raw_text', ''),
                    'raw_text': result.get('raw_text', ''),
                    'confidence': result.get('confidence', 0.85),
                    'extraction_method': 'openai_vision'
                }), 200

            logger.info("OpenAI Vision unavailable; falling back to local EasyOCR prescription extraction.")
            with open(temp_path, 'rb') as temp_image:
                image = decode_image(temp_image.read())
            if image is None:
                return jsonify({'error': 'Could not decode image.'}), 400

            ocr_data = handwritten_ocr.extract_handwritten_text(image)
            raw_text = ocr_data['raw_text']
            template_data = prescription_parser.parse_prescription_with_ai(raw_text) if raw_text.strip() else None
            if not template_data:
                template_data = extract_template_fields(raw_text, ocr_data['results'])

            return jsonify({
                'success': True,
                'structured': bool(template_data),
                'text': raw_text,
                'full_text': raw_text,
                'raw_text': raw_text,
                'confidence': round(ocr_data['confidence'], 2),
                'results': ocr_data['results'],
                'processed_image': image_to_base64(ocr_data['processed_image']),
                'heatmap_image': image_to_base64(generate_confidence_heatmap(image, ocr_data['results'])),
                'total_regions': len(ocr_data['results']),
                'image_type': 'prescription',
                'preprocessing_steps': ['grayscale', 'median_blur', 'adaptive_threshold'],
                'mode_used': 'local-fallback-from-openai-prescription',
                'ocr_engine': 'easyocr',
                'template': template_data,
                'extraction_method': 'local_easyocr_fallback'
            }), 200
        finally:
            try:
                os.remove(temp_path)
            except OSError:
                logger.warning("Could not remove temporary upload: %s", temp_path)
        
    except Exception as e:
        logger.exception('Prescription OCR endpoint failed: %s', e)
        return jsonify({'error': 'Prescription extraction failed.'}), 500
