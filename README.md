# Text Detection OCR 

Text Detection OCR is a full-stack web application for extracting text from images. It supports standard printed documents, handwritten text, and medical prescription style documents through a React frontend and a Flask-based OCR backend.

The project combines traditional OCR pipelines with AI-assisted handwritten text extraction. Standard OCR uses image preprocessing and Tesseract, while handwritten extraction can use an AI vision model for higher accuracy on difficult handwriting.

## About The Project

This application allows users to upload an image and receive selectable, copyable extracted text. It is designed for practical document digitization workflows where scanned images, notes, receipts, forms, and prescriptions need to be converted into editable text.

The backend processes uploaded images, validates file type and size, applies OCR-specific preprocessing, extracts text, calculates confidence values, and returns structured results to the frontend. The frontend provides a clean upload interface, image preview, OCR mode selection, extracted text display, confidence information, and copy/download actions.

## Applications

- Convert printed images and scanned documents into editable text.
- Extract text from handwritten notes using AI vision.
- Read and organize text from medical prescription images.
- Digitize forms, receipts, invoices, letters, and ID-style documents.
- Assist students, offices, clinics, and small businesses with document processing.
- Reduce manual typing from images and scanned files.

## Where To Use

This project is useful in situations where text is locked inside an image and needs to be reused, stored, searched, copied, or processed further.

Common use cases include:

- Educational notes and assignment images.
- Office document digitization.
- Healthcare prescription reading support.
- Receipt and invoice text extraction.
- Form data extraction.
- Research and archival document conversion.
- Personal productivity tools for image-to-text workflows.

## Features

- Image upload with drag-and-drop support.
- Standard OCR mode for printed text.
- AI handwritten OCR mode for better handwriting extraction.
- Medical prescription OCR mode.
- Image preprocessing with OpenCV.
- Tesseract OCR support for printed documents.
- EasyOCR fallback for local handwritten extraction.
- AI text formatting and correction support.
- Confidence score calculation.
- Confidence heatmap visualization.
- Structured template extraction for common document types.
- Copy and download extracted text.
- Light and dark theme support.
- Responsive React user interface.
- Flask REST API backend.

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Frontend | React | User interface and OCR workflow |
| Frontend Styling | CSS, Tailwind configuration | Layout, theme tokens, responsive styling |
| UI Icons | Lucide React | Interface icons and actions |
| Animation | Framer Motion | Smooth UI transitions |
| HTTP Client | Axios | API communication with backend |
| Backend | Flask | REST API server |
| API CORS | Flask-CORS | Cross-origin frontend/backend communication |
| Image Processing | OpenCV | Image decoding, preprocessing, heatmap generation |
| OCR Engine | Tesseract, pytesseract | Printed text recognition |
| Handwriting OCR | EasyOCR | Local handwriting fallback |
| AI Vision | OpenAI-compatible OpenRouter API | Handwritten and prescription text extraction |
| Data Handling | NumPy, Pillow | Image array and file processing |
| Runtime | Python, Node.js | Backend and frontend execution |

## Project Structure

```text
OCR/
  backend/
    app.py
    run_server.py
    routes.py
    utils.py
    handwritten_ocr.py
    ai_formatter.py
    prescription_parser.py
    requirements.txt
    requirements-local.txt
  frontend/
    public/
      index.html
      favicon.svg
    src/
      components/
      hooks/
      pages/
      services/
      App.jsx
      index.js
      index.css
    package.json
  README.md
```

## Backend Setup

Install Python dependencies:

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements-local.txt
```

Install Tesseract OCR on your system and make sure it is available in PATH. On Windows, the backend also checks common Tesseract installation paths automatically.

Optional AI configuration for handwritten OCR:

```bash
set OPENROUTER_API_KEY=your_api_key
```

You can also use:

```bash
set OPENAI_API_KEY=your_api_key
```

Start the backend:

```bash
cd backend
python run_server.py
```

Backend URL:

```text
http://localhost:5000
```

## Frontend Setup

Install frontend dependencies:

```bash
cd frontend
npm install
```

Start the frontend:

```bash
npm start
```

Frontend URL:

```text
http://localhost:3000
```

Build production frontend:

```bash
npm run build
```

## API Overview

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health` | Check backend status and Tesseract availability |
| POST | `/api/ocr` | Extract printed text from an uploaded image |
| POST | `/api/handwritten-ocr` | Extract handwritten text using local OCR |
| POST | `/api/prescription-ocr` | Extract text and fields from prescription images |
| POST | `/api/ocr/bytez/handwritten` | Extract handwritten text using AI vision with local fallback |
| POST | `/api/ocr/bytez/prescription` | Extract prescription data using AI vision with local fallback |
| POST | `/api/clean-text` | Clean OCR text using AI |
| POST | `/api/template` | Extract structured fields from text |
| POST | `/api/correction` | Submit user correction for learning |
| GET | `/api/correction/stats` | View correction learning statistics |

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | Optional | Enables AI vision and AI text correction through OpenRouter |
| `OPENAI_API_KEY` | Optional | Alternative key name used by the backend |
| `REACT_APP_API_URL` | Optional | Custom frontend API base URL |

## Feature Upgrades

## Security & API Keys

- Do NOT commit your API keys to the repository or share them publicly.
- If you accidentally exposed a key (for example in `.env`), revoke it immediately and generate a new one.
- Store keys in environment variables or a secrets manager. For local development, use a `.env` file that is listed in `.gitignore`.

Example local settings (do not commit):

```env
OPENROUTER_API_KEY=sk-your-openrouter-key-here
OPENAI_API_KEY=sk-your-openai-key-here
```

If you pasted a key into a public chat or committed it, rotate the key now.

Planned or recommended improvements:

- Add user authentication for saved OCR history.
- Store extracted documents in a database.
- Add PDF upload and multi-page OCR support.
- Add batch image processing.
- Export results as PDF, DOCX, CSV, and JSON.
- Add language selection for OCR.
- Add manual region selection before OCR.
- Add side-by-side comparison between original image and extracted text.
- Improve prescription parsing with medical vocabulary validation.
- Add deployment configuration for cloud hosting.
- Add automated backend and frontend test coverage.
- Add API rate limiting and upload abuse protection.

## Troubleshooting

If standard OCR fails, verify that Tesseract is installed and available in the system PATH.

If AI handwritten extraction fails, verify that `OPENROUTER_API_KEY` or `OPENAI_API_KEY` is set before starting the backend.

If the frontend cannot connect to the backend, confirm that Flask is running on `http://localhost:5000` and that the frontend API base URL is correct.

If uploads fail, check that the image format is JPG, JPEG, or PNG and that the file size is within the configured backend limit.

## License

This project is intended for educational and portfolio use. Add a license file before using it in production or distributing it publicly.
