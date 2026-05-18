import cv2
import numpy as np
import easyocr
import logging

logger = logging.getLogger(__name__)

# Initialize EasyOCR reader once to avoid loading models repeatedly.
# It might take a moment on first run.
reader = None

def get_reader():
    """Singleton getter for the EasyOCR reader."""
    global reader
    if reader is None:
        logger.info("Initializing EasyOCR reader (CPU mode)...")
        # Use CPU for better compatibility
        reader = easyocr.Reader(['en'], gpu=False) 
    return reader

def preprocess_for_handwritten(image):
    """
    Apply OpenCV preprocessing: grayscale, noise removal, and adaptive thresholding
    to enhance handwritten text for extraction.
    """
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
        
    # Resize slightly if too small to help EasyOCR
    h, w = gray.shape
    if h < 500 or w < 500:
        scale = 1000.0 / max(h, w)
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        
    # Noise removal
    denoised = cv2.medianBlur(gray, 3)
    
    # Adaptive thresholding
    binary = cv2.adaptiveThreshold(
        denoised, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 11, 2
    )
    
    return binary

def extract_handwritten_text(image):
    """
    Extract handwritten text using EasyOCR and OpenCV preprocessing.
    Expects a cv2 image (numpy array).
    """
    # 1. Preprocess
    processed_image = preprocess_for_handwritten(image)
    
    # 2. Get reader
    ocr_reader = get_reader()
    
    # 3. Read text
    # EasyOCR returns a list of tuples: (bbox, text, prob)
    raw_results = ocr_reader.readtext(processed_image)
    
    results = []
    total_confidence = 0
    text_lines = []
    
    for bbox, text, conf in raw_results:
        # bbox format: [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
        tl = bbox[0]
        br = bbox[2]
        x = int(tl[0])
        y = int(tl[1])
        w = int(br[0] - tl[0])
        h = int(br[1] - tl[1])
        
        confidence_percent = float(conf) * 100
        
        results.append({
            'text': text,
            'bbox': {'x': x, 'y': y, 'width': w, 'height': h},
            'confidence': confidence_percent
        })
        text_lines.append(text)
        total_confidence += confidence_percent
        
    avg_confidence = total_confidence / len(results) if results else 0
    raw_text = "\n".join(text_lines)
    
    # Convert processed image back to BGR for heatmap/saving consistency if needed elsewhere
    if len(processed_image.shape) == 2:
        processed_image_bgr = cv2.cvtColor(processed_image, cv2.COLOR_GRAY2BGR)
    else:
        processed_image_bgr = processed_image
    
    return {
        'results': results,
        'raw_text': raw_text,
        'confidence': avg_confidence,
        'processed_image': processed_image_bgr
    }
