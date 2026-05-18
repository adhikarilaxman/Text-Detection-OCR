import os
import platform
import logging
import base64
import pytesseract
import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp', 'gif', 'webp'}
MIN_IMAGE_DIMENSION = 2

def setup_tesseract_path():
    """Configure Tesseract executable path based on OS."""
    if platform.system() == 'Windows':
        tesseract_paths = [
            r'C:\Program Files\Tesseract-OCR\tesseract.exe',
            r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
            r'C:\Users\{}\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'.format(os.getenv('USERNAME', '')),
        ]
        for path in tesseract_paths:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                logger.info("Tesseract configured: %s", path)
                return True
        logger.warning("Tesseract not found in standard Windows paths")
        return False
    return True

# Initialize on module load
setup_tesseract_path()

def is_tesseract_available():
    """Verify Tesseract OCR is installed and available."""
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception as e:
        logger.warning("Tesseract check failed: %s", e)
        return False

def allowed_file(filename):
    """Check if the provided filename has an allowed extension."""
    if not filename or '.' not in filename:
        return False
    return filename.rsplit('.', 1)[-1].lower() in ALLOWED_EXTENSIONS

def decode_image(image_bytes):
    """Safely decode image bytes using OpenCV."""
    nparr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if image is not None:
        return image
    image = cv2.imdecode(nparr, cv2.IMREAD_UNCHANGED)
    return image

def image_to_base64(image):
    """Convert an OpenCV image to a base64 encoded string."""
    _, buffer = cv2.imencode('.png', image)
    return base64.b64encode(buffer).decode('utf-8')


def perform_ocr(image):
    """
    Extract text from an image exactly as provided, using Tesseract OCR.
    No automatic resizing or destructive modifications to ensure exact text matching.
    Returns a list of regions containing extracted text, bounding boxes, and confidence.
    """
    if isinstance(image, np.ndarray):
        # Default OpenCV images to RGB for PIL processing if they are BGR
        if len(image.shape) == 3:
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(image_rgb)
        else:
            pil_image = Image.fromarray(image)
    else:
        pil_image = image

    # Basic layout analysis config
    config = '--psm 6 --oem 3'
    
    try:
        data = pytesseract.image_to_data(pil_image, output_type=pytesseract.Output.DICT, config=config)
    except Exception as e:
        # Fallback to simple string extraction if data extraction fails
        logger.warning(f"Detailed data extraction failed, falling back to basic string: {e}")
        text = pytesseract.image_to_string(pil_image, config=config)
        if text.strip():
            return [{'text': text.strip(), 'bbox': {'x': 0, 'y': 0, 'width': 0, 'height': 0}, 'confidence': 100}]
        return []

    results = []
    n_boxes = len(data['text'])
    
    for i in range(n_boxes):
        text = data['text'][i].strip()
        conf = data['conf'][i]
        
        if isinstance(conf, str):
            try:
                conf = float(conf) if conf != '-1' else 0
            except ValueError:
                conf = 0
        else:
            conf = float(conf) if conf > 0 else 0
            
        if text and conf >= 0:
            results.append({
                'text': text,
                'bbox': {
                    'x': int(data['left'][i]),
                    'y': int(data['top'][i]),
                    'width': int(data['width'][i]),
                    'height': int(data['height'][i])
                },
                'confidence': conf
            })
            
    return results

def extract_raw_text(image):
    """
    Return the exact raw string from Tesseract with original spacing and
    line breaks preserved. This is the true OCR output — nothing is modified.
    """
    if isinstance(image, np.ndarray):
        if len(image.shape) == 3:
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(image_rgb)
        else:
            pil_image = Image.fromarray(image)
    else:
        pil_image = image

    config = '--psm 6 --oem 3'
    try:
        raw = pytesseract.image_to_string(pil_image, config=config)
        return raw  # Return as-is — no stripping, no collapsing
    except Exception as e:
        logger.warning("extract_raw_text failed: %s", e)
        return ""


# =============================================================================
# BLUR DETECTION & ENHANCEMENT
# =============================================================================

def detect_blur(image, threshold=100):
    """
    Detect blur using Variance of Laplacian method.
    Returns:
        - is_blurry (bool): True if image is blurry
        - score (float): Variance of Laplacian (lower = more blurry)
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    is_blurry = laplacian_var < threshold
    return is_blurry, laplacian_var


def apply_sharpening(image, kernel_size=3, strength=1.5):
    """
    Apply sharpening kernel to enhance image details.
    """
    kernel = np.array([[-1, -1, -1],
                       [-1, strength*8 + 1, -1],
                       [-1, -1, -1]]) / (strength * 8 + 1)
    sharpened = cv2.filter2D(image, -1, kernel)
    return np.clip(sharpened, 0, 255).astype(np.uint8)


def apply_unsharp_mask(image, gaussian_blur_radius=3, strength=1.5):
    """
    Apply unsharp masking for blur enhancement.
    """
    blurred = cv2.GaussianBlur(image, (0, 0), gaussian_blur_radius)
    sharpened = cv2.addWeighted(image, 1.0 + strength, blurred, -strength, 0)
    return np.clip(sharpened, 0, 255).astype(np.uint8)


def enhance_blurry_image(image):
    """
    Pipeline for enhancing blurry images.
    Applies sharpening and unsharp masking sequentially.
    """
    # Convert to grayscale if needed
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    
    # Apply sharpening
    sharpened = apply_sharpening(gray)
    
    # Apply unsharp masking
    enhanced = apply_unsharp_mask(sharpened)
    
    # Convert back to BGR if original was color
    if len(image.shape) == 3:
        enhanced = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)
    
    return enhanced


# =============================================================================
# HANDWRITTEN TEXT PREPROCESSING
# =============================================================================

def preprocess_handwritten(image):
    """
    Preprocessing pipeline specifically for handwritten text.
    Includes:
    - Contrast enhancement (CLAHE)
    - Adaptive thresholding
    - Noise removal (median blur)
    """
    # Convert to grayscale
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    
    # Apply CLAHE for contrast enhancement
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    
    # Apply median blur for noise removal
    denoised = cv2.medianBlur(enhanced, 3)
    
    # Apply adaptive thresholding
    binary = cv2.adaptiveThreshold(
        denoised, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 11, 2
    )
    
    # Convert back to BGR if original was color
    if len(image.shape) == 3:
        binary = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
    
    return binary





# =============================================================================
# CONDITIONAL PREPROCESSING FLOW
# =============================================================================

def detect_image_type(image):
    """
    Detect image type: blurry, handwritten, or normal.
    Returns:
        - image_type (str): 'blurry', 'handwritten', or 'normal'
        - confidence (float): Detection confidence score
    """
    # Check for blur
    is_blurry, blur_score = detect_blur(image)
    
    if is_blurry:
        return 'blurry', blur_score
    
    # Heuristic for handwritten text detection
    # Handwritten text typically has more irregular patterns
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    
    # Calculate edge density
    edges = cv2.Canny(gray, 50, 150)
    edge_density = np.sum(edges > 0) / (edges.shape[0] * edges.shape[1])
    
    # High edge density suggests handwritten text
    if edge_density > 0.15:
        return 'handwritten', edge_density
    
    return 'normal', blur_score


def apply_preprocessing_pipeline(image, mode='auto'):
    """
    Apply preprocessing pipeline based on mode or auto-detection.
    
    Args:
        image: Input image (numpy array)
        mode: 'auto', 'blur', 'handwritten', or 'normal'
    
    Returns:
        - processed_image: Preprocessed image
        - image_type: Detected or specified image type
        - applied_steps: List of preprocessing steps applied
    """
    applied_steps = []
    
    if mode == 'auto':
        image_type, _ = detect_image_type(image)
    else:
        image_type = mode
    
    logger.info(f"Applying preprocessing pipeline for image type: {image_type}")
    
    if image_type == 'blurry':
        processed = enhance_blurry_image(image)
        applied_steps = ['blur_detection', 'sharpening', 'unsharp_mask']
    
    elif image_type == 'handwritten':
        processed = preprocess_handwritten(image)
        applied_steps = ['grayscale', 'clahe', 'median_blur', 'adaptive_threshold']
    
    else:  # normal
        processed = image.copy()
        applied_steps = ['none']
    
    return processed, image_type, applied_steps


# =============================================================================
# OCR WITH CONFIDENCE HANDLING
# =============================================================================

def perform_ocr_with_retry(image, mode='auto', confidence_threshold=50, max_retries=2):
    """
    Perform OCR with confidence-based retry logic.
    
    Args:
        image: Input image
        mode: Preprocessing mode ('auto', 'blur', 'handwritten', 'normal')
        confidence_threshold: Minimum acceptable confidence score
        max_retries: Maximum number of retry attempts with different preprocessing
    
    Returns:
        - results: OCR results with text, bbox, confidence
        - final_image: Image used for final OCR
        - image_type: Detected/used image type
        - applied_steps: Preprocessing steps applied
        - avg_confidence: Average confidence score
    """
    # Apply preprocessing based on mode
    processed_image, image_type, applied_steps = apply_preprocessing_pipeline(image, mode)
    
    # Perform OCR
    results = perform_ocr(processed_image)
    
    # Calculate average confidence
    avg_confidence = (
        sum(r.get('confidence', 0) for r in results) / len(results)
        if results else 0
    )
    
    # Retry with different preprocessing if confidence is low
    retry_count = 0
    while avg_confidence < confidence_threshold and retry_count < max_retries:
        logger.info(f"Low confidence ({avg_confidence:.2f}), retrying with different preprocessing...")
        
        # Try alternative preprocessing
        if image_type == 'blurry':
            # Try handwritten preprocessing for blurry images
            processed_image, image_type, applied_steps = apply_preprocessing_pipeline(image, 'handwritten')
        elif image_type == 'handwritten':
            # Try blur preprocessing for handwritten
            processed_image, image_type, applied_steps = apply_preprocessing_pipeline(image, 'blur')
        else:
            # Try handwritten preprocessing for normal images
            processed_image, image_type, applied_steps = apply_preprocessing_pipeline(image, 'handwritten')
        
        results = perform_ocr(processed_image)
        avg_confidence = (
            sum(r.get('confidence', 0) for r in results) / len(results)
            if results else 0
        )
        retry_count += 1
    
    return results, processed_image, image_type, applied_steps, avg_confidence





def generate_confidence_heatmap(image, ocr_results):
    """
    Generate a color-coded confidence heatmap overlay on the original image.
    
    Green = high confidence (>= 80%)
    Yellow = medium confidence (50-80%)
    Red = low confidence (< 50%)
    
    This is a UNIQUE feature that visually shows users where OCR struggled,
    allowing them to focus corrections on low-confidence regions.
    
    Args:
        image: Original image (numpy array)
        ocr_results: List of OCR result dictionaries with bbox and confidence
    
    Returns:
        Heatmap image as numpy array (same size as input)
    """
    if image is None or not ocr_results:
        return image
    
    # Create overlay image (copy of original)
    overlay = image.copy()
    
    for result in ocr_results:
        conf = result.get('confidence', 0)
        bbox = result.get('bbox', {})
        
        x = bbox.get('x', 0)
        y = bbox.get('y', 0)
        w = bbox.get('width', 0)
        h = bbox.get('height', 0)
        
        if w <= 0 or h <= 0:
            continue
        
        # Determine color based on confidence
        if conf >= 80:
            color = (0, 255, 0)       # Green - high confidence
            alpha = 0.25
        elif conf >= 50:
            color = (0, 255, 255)     # Yellow - medium confidence
            alpha = 0.35
        else:
            color = (0, 0, 255)       # Red - low confidence
            alpha = 0.45
        
        # Draw semi-transparent rectangle
        x1 = max(0, x)
        y1 = max(0, y)
        x2 = min(image.shape[1], x + w)
        y2 = min(image.shape[0], y + h)
        
        # Create filled rectangle with transparency
        sub_img = overlay[y1:y2, x1:x2]
        colored_rect = np.full_like(sub_img, color, dtype=np.uint8)
        cv2.addWeighted(colored_rect, alpha, sub_img, 1 - alpha, 0, sub_img)
        overlay[y1:y2, x1:x2] = sub_img
        
        # Draw border
        cv2.rectangle(overlay, (x1, y1), (x2, y2), color, 1)
        
        # Draw confidence label
        label = f"{int(conf)}%"
        font_scale = 0.4
        thickness = 1
        (label_w, label_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
        
        # Position label above the box
        label_y = max(label_h + 2, y1 - 2)
        label_x = x1
        
        # Draw label background
        cv2.rectangle(overlay, 
                      (label_x, label_y - label_h - 2), 
                      (label_x + label_w + 2, label_y + 2), 
                      color, -1)
        
        # Draw label text (white)
        cv2.putText(overlay, label, (label_x, label_y), 
                    cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), thickness)
    
    # Add legend
    legend_y = image.shape[0] - 50
    legend_x = 10
    
    # Legend background
    cv2.rectangle(overlay, (legend_x, legend_y - 5), (legend_x + 220, legend_y + 40), 
                  (0, 0, 0), -1)
    cv2.addWeighted(overlay[legend_y-5:legend_y+40, legend_x:legend_x+220], 0.6,
                    np.full_like(overlay[legend_y-5:legend_y+40, legend_x:legend_x+220], 0), 0.4, 0,
                    overlay[legend_y-5:legend_y+40, legend_x:legend_x+220])
    
    # Legend items
    items = [
        ((0, 255, 0), "High (>=80%)"),
        ((0, 255, 255), "Medium (50-80%)"),
        ((0, 0, 255), "Low (<50%)")
    ]
    for i, (color, label) in enumerate(items):
        item_y = legend_y + 5 + i * 12
        cv2.rectangle(overlay, (legend_x + 5, item_y), (legend_x + 15, item_y + 8), color, -1)
        cv2.putText(overlay, label, (legend_x + 20, item_y + 8), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 255), 1)
    
    return overlay


def extract_template_fields(raw_text, ocr_results=None):
    """
    Smart Template Extraction - Auto-detect document type and extract structured fields.
    
    This is a UNIQUE feature that goes beyond simple text extraction:
    - Detects document type (receipt, invoice, ID card, form, letter, etc.)
    - Extracts key-value pairs (name, date, amount, address, etc.)
    - Returns structured data instead of raw text
    
    Args:
        raw_text: Raw OCR text string
        ocr_results: Optional OCR results with bounding boxes for spatial analysis
    
    Returns:
        Dictionary with:
        - document_type: Detected type
        - confidence: Type detection confidence
        - fields: Extracted key-value pairs
        - raw_text: Original text
    """
    import re
    
    text = raw_text.lower()
    fields = {}
    
    # ---- Document Type Detection ----
    type_scores = {
        'receipt': 0,
        'invoice': 0,
        'id_card': 0,
        'form': 0,
        'letter': 0,
        'handwritten_note': 0,
        'unknown': 0
    }
    
    # Receipt indicators
    receipt_keywords = ['total', 'subtotal', 'tax', 'change', 'cash', 'card', 'visa', 'mastercard', 
                       'receipt', 'thank you', 'amount due', 'balance due', 'payment', 'item', 'qty',
                       'price', 'discount', 'store', 'checkout', 'order #', 'trans #']
    for kw in receipt_keywords:
        if kw in text:
            type_scores['receipt'] += 2
    
    # Invoice indicators
    invoice_keywords = ['invoice', 'bill to', 'ship to', 'invoice number', 'invoice date', 
                       'due date', 'po number', 'payment terms', 'net 30', 'net 60',
                       'remit to', 'account number', 'billing address']
    for kw in invoice_keywords:
        if kw in text:
            type_scores['invoice'] += 2
    
    # ID Card indicators
    id_keywords = ['date of birth', 'dob', 'sex', 'height', 'weight', 'eye color',
                   'driver license', 'license', 'passport', 'national id', 'id number',
                   'issuing authority', 'expiry', 'expiration', 'citizen', 'nationality',
                   'identification', 'identity card', 'state of', 'country of birth']
    for kw in id_keywords:
        if kw in text:
            type_scores['id_card'] += 2
    
    # Form indicators
    form_keywords = ['name:', 'address:', 'phone:', 'email:', 'date:', 'signature:',
                     'please print', 'check one', 'circle one', 'fill in', 'applicant',
                     'applicant name', 'date of application', 'for office use']
    for kw in form_keywords:
        if kw in text:
            type_scores['form'] += 2
    
    # Letter indicators
    letter_keywords = ['dear ', 'sincerely', 'regards', 'yours truly', 'to whom it may concern',
                       'cc:', 'enclosure', 're:', 'subject:', 'from:', 'attention:']
    for kw in letter_keywords:
        if kw in text:
            type_scores['letter'] += 2
    
    # Handwritten note indicators
    if ocr_results:
        avg_conf = sum(r.get('confidence', 0) for r in ocr_results) / len(ocr_results) if ocr_results else 0
        if avg_conf < 70:
            type_scores['handwritten_note'] += 3
    
    # Determine document type
    doc_type = max(type_scores, key=type_scores.get)
    type_confidence = min(type_scores[doc_type] / 10, 1.0)  # Normalize to 0-1
    
    if type_scores[doc_type] == 0:
        doc_type = 'unknown'
        type_confidence = 0
    
    # ---- Field Extraction ----
    
    # Common fields (try for all document types)
    
    # Email
    email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', raw_text, re.IGNORECASE)
    if email_match:
        fields['email'] = email_match.group(0)
    
    # Phone number
    phone_match = re.search(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', raw_text)
    if phone_match:
        fields['phone'] = phone_match.group(0)
    
    # Date patterns
    date_patterns = [
        r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
        r'\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}\b',
        r'\b\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{4}\b',
    ]
    for pattern in date_patterns:
        date_match = re.search(pattern, raw_text, re.IGNORECASE)
        if date_match:
            fields['date'] = date_match.group(0)
            break
    
    # URL
    url_match = re.search(r'https?://[\w\-._~:/?#\[\]@!$&\'()*+,;=]+', raw_text)
    if url_match:
        fields['url'] = url_match.group(0)
    
    # Document-type specific extraction
    if doc_type == 'receipt':
        # Total amount
        total_match = re.search(r'(?:total|amount\s*due|balance\s*due)[:\s]*\$?\s*([\d,]+\.\d{2})', text, re.IGNORECASE)
        if total_match:
            fields['total'] = total_match.group(1)
        
        # Subtotal
        subtotal_match = re.search(r'subtotal[:\s]*\$?\s*([\d,]+\.\d{2})', text, re.IGNORECASE)
        if subtotal_match:
            fields['subtotal'] = subtotal_match.group(1)
        
        # Tax
        tax_match = re.search(r'(?:tax|vat|gst)[:\s]*\$?\s*([\d,]+\.\d{2})', text, re.IGNORECASE)
        if tax_match:
            fields['tax'] = tax_match.group(1)
        
        # Store name (first line or capitalized text)
        lines = raw_text.strip().split('\n')
        if lines:
            fields['store_name'] = lines[0].strip()
        
        # Payment method
        payment_match = re.search(r'(visa|mastercard|amex|cash|debit|credit|apple\s*pay|google\s*pay)', text, re.IGNORECASE)
        if payment_match:
            fields['payment_method'] = payment_match.group(0).title()
    
    elif doc_type == 'invoice':
        # Invoice number
        inv_match = re.search(r'(?:invoice|inv)[\s#.:]*([A-Z0-9\-]+)', text, re.IGNORECASE)
        if inv_match:
            fields['invoice_number'] = inv_match.group(1).upper()
        
        # Amount
        amount_match = re.search(r'(?:amount|total|balance)[:\s]*\$?\s*([\d,]+\.\d{2})', text, re.IGNORECASE)
        if amount_match:
            fields['amount'] = amount_match.group(1)
        
        # Due date
        due_match = re.search(r'(?:due\s*date|payment\s*due)[:\s]*(.+)', text, re.IGNORECASE)
        if due_match:
            fields['due_date'] = due_match.group(1).strip()
    
    elif doc_type == 'id_card':
        # ID number
        id_match = re.search(r'(?:license|id|passport|identification)\s*(?:number|no|#)?[:\s]*([A-Z0-9\-]+)', text, re.IGNORECASE)
        if id_match:
            fields['id_number'] = id_match.group(1).upper()
        
        # Name (look for patterns like "Name: John Doe")
        name_match = re.search(r'(?:name|full\s*name)[:\s]*([A-Za-z\s]+?)(?:\n|$)', raw_text, re.IGNORECASE)
        if name_match:
            fields['name'] = name_match.group(1).strip()
        
        # DOB
        dob_match = re.search(r'(?:dob|date\s*of\s*birth|born)[:\s]*(.+?)(?:\n|$)', text, re.IGNORECASE)
        if dob_match:
            fields['date_of_birth'] = dob_match.group(1).strip()
        
        # Expiry
        exp_match = re.search(r'(?:exp|expiry|expiration)[:\s]*(.+?)(?:\n|$)', text, re.IGNORECASE)
        if exp_match:
            fields['expiry_date'] = exp_match.group(1).strip()
    
    elif doc_type == 'form':
        # Extract key-value pairs (pattern: "Label: Value")
        kv_pattern = re.findall(r'^([A-Za-z\s]+?):\s*(.+?)$', raw_text, re.MULTILINE)
        for key, value in kv_pattern:
            key_clean = key.strip().lower().replace(' ', '_')
            if len(key_clean) > 0 and len(value.strip()) > 0:
                fields[key_clean] = value.strip()
    
    elif doc_type == 'letter':
        # Recipient
        dear_match = re.search(r'(?:dear|to)\s+(.+?)(?:[,:\n]|$)', raw_text, re.IGNORECASE)
        if dear_match:
            fields['recipient'] = dear_match.group(1).strip()
        
        # Subject
        subject_match = re.search(r'(?:subject|re)[:\s]+(.+?)(?:\n|$)', raw_text, re.IGNORECASE)
        if subject_match:
            fields['subject'] = subject_match.group(1).strip()
        
        # Sender (typically last name before "sincerely/regards")
        sender_match = re.search(r'(?:sincerely|regards|truly|respectfully)[,\s]*\n\s*(.+?)(?:\n|$)', raw_text, re.IGNORECASE)
        if sender_match:
            fields['sender'] = sender_match.group(1).strip()
    
    return {
        'document_type': doc_type,
        'type_confidence': round(type_confidence * 100, 1),
        'fields': fields,
        'field_count': len(fields),
        'raw_text': raw_text
    }


# ---- Interactive Correction Learning System ----
# Stores user corrections in a JSON file and applies them to future OCR results

import json
from pathlib import Path

CORRECTIONS_FILE = os.path.join(os.path.dirname(__file__), 'corrections.json')


def _load_corrections():
    """Load stored corrections from JSON file."""
    try:
        if os.path.exists(CORRECTIONS_FILE):
            with open(CORRECTIONS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load corrections: {e}")
    return {'word_corrections': {}, 'frequency': {}}


def _save_corrections(corrections):
    """Save corrections to JSON file."""
    try:
        with open(CORRECTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(corrections, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.warning(f"Failed to save corrections: {e}")
        return False


def submit_correction(original_text, corrected_text):
    """
    Store a user correction for learning.
    
    This is a UNIQUE feature - the system learns from user corrections
    and applies them automatically to future OCR results.
    
    Args:
        original_text: The incorrect OCR text
        corrected_text: The user's correction
    
    Returns:
        Dictionary with success status and correction stats
    """
    if not original_text or not corrected_text:
        return {'success': False, 'error': 'Empty text provided'}
    
    corrections = _load_corrections()
    
    # Store word-level corrections
    orig_words = original_text.split()
    corr_words = corrected_text.split()
    
    # If same number of words, map each word
    if len(orig_words) == len(corr_words):
        for orig, corr in zip(orig_words, corr_words):
            if orig != corr:
                key = orig.lower().strip()
                if key not in corrections['word_corrections']:
                    corrections['word_corrections'][key] = {}
                if corr not in corrections['word_corrections'][key]:
                    corrections['word_corrections'][key][corr] = 0
                corrections['word_corrections'][key][corr] += 1
    
    # Also store the full phrase correction
    key = original_text.lower().strip()
    if key not in corrections['word_corrections']:
        corrections['word_corrections'][key] = {}
    corr_key = corrected_text.strip()
    if corr_key not in corrections['word_corrections'][key]:
        corrections['word_corrections'][key][corr_key] = 0
    corrections['word_corrections'][key][corr_key] += 1
    
    # Track frequency
    corrections['frequency'][key] = corrections['frequency'].get(key, 0) + 1
    
    _save_corrections(corrections)
    
    total_corrections = sum(len(v) for v in corrections['word_corrections'].values())
    
    return {
        'success': True,
        'message': 'Correction learned successfully',
        'total_corrections': total_corrections,
        'correction_applied': f'"{original_text}" → "{corrected_text}"'
    }


def apply_learned_corrections(text):
    """
    Apply previously learned corrections to OCR text.
    
    This function replaces known OCR mistakes with user-verified corrections.
    The more corrections users submit, the smarter the system becomes.
    
    Args:
        text: Raw OCR text
    
    Returns:
        Corrected text string
    """
    if not text:
        return text
    
    corrections = _load_corrections()
    word_corrections = corrections.get('word_corrections', {})
    
    if not word_corrections:
        return text
    
    # Apply word-level corrections
    words = text.split()
    corrected_words = []
    
    for word in words:
        key = word.lower().strip('.,;:!?()"\'')
        if key in word_corrections:
            # Get the most frequent correction
            options = word_corrections[key]
            if options:
                best_correction = max(options, key=options.get)
                # Preserve original casing hints
                if word[0].isupper() and best_correction[0].islower():
                    best_correction = best_correction[0].upper() + best_correction[1:]
                corrected_words.append(best_correction)
            else:
                corrected_words.append(word)
        else:
            corrected_words.append(word)
    
    result = ' '.join(corrected_words)
    
    # Apply phrase-level corrections (longer matches first)
    phrase_corrections = {k: v for k, v in word_corrections.items() if ' ' in k}
    for phrase in sorted(phrase_corrections.keys(), key=len, reverse=True):
        if phrase in result.lower():
            options = phrase_corrections[phrase]
            if options:
                best = max(options, key=options.get)
                # Case-insensitive replace
                import re
                pattern = re.compile(re.escape(phrase), re.IGNORECASE)
                result = pattern.sub(best, result)
    
    return result


def get_correction_stats():
    """Get statistics about learned corrections."""
    corrections = _load_corrections()
    word_corrections = corrections.get('word_corrections', {})
    frequency = corrections.get('frequency', {})
    
    total_words = len(word_corrections)
    total_uses = sum(frequency.values())
    
    # Top corrections
    top_corrections = sorted(frequency.items(), key=lambda x: x[1], reverse=True)[:10]
    
    return {
        'total_learned_words': total_words,
        'total_correction_uses': total_uses,
        'top_corrections': top_corrections,
        'learning_active': total_words > 0
    }
