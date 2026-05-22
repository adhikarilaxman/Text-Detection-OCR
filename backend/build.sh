#!/usr/bin/env bash
# Render build script for the OCR backend
set -e

echo "==> Installing system dependencies (Tesseract OCR)..."
apt-get update -qq
apt-get install -y -qq tesseract-ocr tesseract-ocr-eng libgl1 libglib2.0-0

echo "==> Tesseract version:"
tesseract --version

echo "==> Installing Python dependencies..."
pip install -r requirements.txt

echo "==> Build complete."
