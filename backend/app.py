import sys
import os
import io
import logging
from flask import Flask
from flask_cors import CORS

# Force UTF-8 encoding for standard output to prevent crashes
# when libraries like EasyOCR print unicode progress bars on Windows
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Import our modular routes
from routes import api

# Setup basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_app():
    """Factory function to construct the simple OCR Flask app."""
    app = Flask(__name__)
    
    # Configure application defaults
    UPLOAD_FOLDER = 'uploads'
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
        
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    # Allow uploads up to 16MB
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
    
    # Allow cross-origin requests
    CORS(app)
    
    # Register blueprints (all our OCR and health endpoints are prefixed under /api)
    app.register_blueprint(api, url_prefix='/api')
    
    logger.info("Flask OCR App initialized successfully.")
    
    return app


app = create_app()

if __name__ == '__main__':
    # Run development server explicitly on port 5000
    app.run(debug=True, port=5000)
