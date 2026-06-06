# -- Stage 1: Build the React frontend ----------------------------------------
FROM node:20-slim AS frontend-builder

WORKDIR /frontend

# Install dependencies first (layer cache)
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --silent

# Copy source and build
# NODE_ENV=production causes api.js to use relative /api path (no hardcoded host)
COPY frontend/ .
RUN CI=false NODE_NO_WARNINGS=1 npm run build


# -- Stage 2: Flask backend + built frontend static files ----------------------
FROM python:3.11-slim

# Install Tesseract and system dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application code
COPY backend/ .

# Copy the built React app where Flask expects it: ../frontend/build
# app.py uses static_folder='../frontend/build' relative to /app
COPY --from=frontend-builder /frontend/build /frontend/build

# Create uploads directory
RUN mkdir -p uploads

EXPOSE 10000

CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:10000", "--timeout", "120", "--workers", "1"]
