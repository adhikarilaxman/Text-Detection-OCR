import sys
import os
import io

# ── Load .env FIRST so every module (including ai_formatter) sees the API key ──
from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))
import logging
from flask import Flask, send_from_directory, abort
from flask_cors import CORS

# Force UTF-8 encoding for standard output to prevent crashes
# when libraries like EasyOCR print unicode progress bars on Windows
try:
    out_enc = (sys.stdout.encoding or '').lower()
except Exception:
    out_enc = ''
try:
    err_enc = (sys.stderr.encoding or '').lower()
except Exception:
    err_enc = ''

if out_enc != 'utf-8':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass
if err_enc != 'utf-8':
    try:
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

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
    app = Flask(__name__, static_folder='../frontend/build')
    
    # Configure application defaults
    UPLOAD_FOLDER = 'uploads'
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
        
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    # Allow uploads up to 16MB
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
    
    # Allow cross-origin requests
    CORS(app)
    
    # Catch-all route to serve the React frontend static files
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve(path):
        if path.startswith('api/'):
            abort(404)
        if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
            return send_from_directory(app.static_folder, path)
        else:
            return send_from_directory(app.static_folder, 'index.html')

    # Register blueprints (all our OCR and health endpoints are prefixed under /api)
    app.register_blueprint(api, url_prefix='/api')
    
    logger.info("Flask OCR App initialized successfully.")
    
    return app


app = create_app()

if __name__ == '__main__':
    # Run development server explicitly on port 5000
    app.run(debug=True, port=5000)
