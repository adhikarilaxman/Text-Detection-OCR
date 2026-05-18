import axios from 'axios';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:5000/api';

const client = axios.create({
    baseURL: API_BASE,
    timeout: 120000,
});

/**
 * POST /api/ocr - send image for OCR processing.
 * @param {File} file - image file
 * @returns {{ success, text, full_text, confidence, results, processed_image, total_regions }}
 */
export async function performOCR(file) {
    const formData = new FormData();
    formData.append('image', file);

    try {
        const res = await client.post('/ocr', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
        });

        if (res.data && res.data.success === false) {
            throw new Error(res.data.error || 'OCR processing failed');
        }

        return res.data;
    } catch (err) {
        if (err.response?.data?.error) {
            throw new Error(err.response.data.error);
        }
        if (err.code === 'ECONNABORTED' || err.message?.includes('timeout')) {
            throw new Error('Request timed out. Please try again.');
        }
        if (err.code === 'ERR_NETWORK' || !err.response) {
            throw new Error('Cannot reach the server. Is the backend running?');
        }
        throw new Error(err.message || 'Failed to process image');
    }
}

/**
 * POST /api/handwritten-ocr - send image for handwritten OCR processing explicitly.
 * @param {File} file - image file
 * @returns {{ success, text, full_text, confidence, results, processed_image, total_regions }}
 */
export async function performHandwrittenOCR(file) {
    const formData = new FormData();
    formData.append('image', file);

    try {
        const res = await client.post('/handwritten-ocr', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
        });

        if (res.data && res.data.success === false) {
            throw new Error(res.data.error || 'Handwritten OCR processing failed');
        }

        return res.data;
    } catch (err) {
        if (err.response?.data?.error) {
            throw new Error(err.response.data.error);
        }
        if (err.code === 'ECONNABORTED' || err.message?.includes('timeout')) {
            throw new Error('Request timed out. Please try again.');
        }
        if (err.code === 'ERR_NETWORK' || !err.response) {
            throw new Error('Cannot reach the server. Is the backend running?');
        }
        throw new Error(err.message || 'Failed to process image for handwritten text');
    }
}

/**
 * POST /api/prescription-ocr - send image for medical prescription OCR processing explicitly.
 * @param {File} file - image file
 * @returns {{ success, text, full_text, confidence, results, processed_image, total_regions }}
 */
export async function performPrescriptionOCR(file) {
    const formData = new FormData();
    formData.append('image', file);

    try {
        const res = await client.post('/prescription-ocr', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
            timeout: 180000, // Longer timeout for AI processing
        });

        if (res.data && res.data.success === false) {
            throw new Error(res.data.error || 'Prescription OCR processing failed');
        }

        return res.data;
    } catch (err) {
        if (err.response?.data?.error) {
            throw new Error(err.response.data.error);
        }
        if (err.code === 'ECONNABORTED' || err.message?.includes('timeout')) {
            throw new Error('Request timed out. Please try again.');
        }
        if (err.code === 'ERR_NETWORK' || !err.response) {
            throw new Error('Cannot reach the server. Is the backend running?');
        }
        throw new Error(err.message || 'Failed to process image for medical prescription');
    }
}

/**
 * POST /api/clean-text - send raw OCR text to be cleaned and summarized by AI.
 * @param {string} text - raw OCR text
 * @returns {{ cleaned_text: string, summary: string[] }}
 * @throws Error if AI is unavailable or request fails
 */
export async function cleanTextWithAI(text) {
    try {
        const res = await client.post('/clean-text', { text });

        // Surface backend errors to the caller
        if (res.data && res.data.error) {
            throw new Error(res.data.error);
        }

        return {
            cleaned_text: res.data.cleaned_text || '',
            summary: Array.isArray(res.data.summary) ? res.data.summary : [],
        };
    } catch (err) {
        // Backend returned a 4xx/5xx
        const backendMsg = err.response?.data?.error;
        if (backendMsg) throw new Error(backendMsg);

        if (err.code === 'ECONNABORTED' || err.message?.includes('timeout')) {
            throw new Error('AI request timed out. Please try again.');
        }
        throw new Error(err.message || 'Failed to clean text with AI');
    }
}

/**
 * GET /api/health - check backend status.
 */
export async function checkHealth() {
    try {
        const res = await client.get('/health', { timeout: 5000 });
        return {
            ok: res.data?.status === 'healthy',
            tesseractAvailable: res.data?.tesseract_available !== false,
        };
    } catch {
        return { ok: false, tesseractAvailable: false };
    }
}

/**
 * POST /api/correction - submit a user correction for the learning system.
 * @param {string} original - The incorrect OCR text
 * @param {string} corrected - The user's correction
 * @returns {{ success, message, total_corrections }}
 */
export async function submitCorrection(original, corrected) {
    try {
        const res = await client.post('/correction', { original, corrected });
        return res.data;
    } catch (err) {
        const msg = err.response?.data?.error || err.message || 'Failed to submit correction';
        throw new Error(msg);
    }
}

/**
 * GET /api/correction/stats - get correction learning statistics.
 */
export async function getCorrectionStats() {
    try {
        const res = await client.get('/correction/stats');
        return res.data;
    } catch {
        return { total_learned_words: 0, total_correction_uses: 0, learning_active: false };
    }
}

/**
 * POST /api/template - extract structured fields from text.
 * @param {string} text - Raw OCR text
 * @returns {{ document_type, type_confidence, fields, field_count }}
 */
export async function extractTemplate(text) {
    try {
        const res = await client.post('/template', { text });
        return res.data;
    } catch (err) {
        const msg = err.response?.data?.error || err.message || 'Failed to extract template';
        throw new Error(msg);
    }
}

/**
 * POST /api/ocr/handwritten - extract handwritten text (uses local EasyOCR).
 * @param {File} file - image file with handwritten text
 * @returns {{ text, raw_text, confidence, corrections_applied }}
 */
export async function extractHandwritten(file) {
    const formData = new FormData();
    formData.append('image', file);

    try {
        const res = await client.post('/handwritten-ocr', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
        });
        return res.data;
    } catch (err) {
        const msg = err.response?.data?.error || err.message || 'Handwritten extraction failed';
        throw new Error(msg);
    }
}

/**
 * POST /api/ocr/bytez/handwritten - extract handwritten text using AI Vision.
 * @param {File} file - image file with handwritten text
 * @returns {{ text, raw_text, confidence, corrections_applied }}
 */
export async function extractHandwrittenBytez(file) {
    const formData = new FormData();
    formData.append('image', file);

    try {
        const res = await client.post('/ocr/bytez/handwritten', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
        });
        return res.data;
    } catch (err) {
        const msg = err.response?.data?.error || err.message || 'AI handwritten extraction failed';
        throw new Error(msg);
    }
}

/**
 * POST /api/prescription-ocr - extract medical prescription data (uses local EasyOCR + AI).
 * @param {File} file - prescription image file
 * @returns {{ structured, doctor_name, patient_name, medications[], instructions, etc. }}
 */
export async function extractPrescription(file) {
    const formData = new FormData();
    formData.append('image', file);

    try {
        const res = await client.post('/prescription-ocr', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
        });
        return res.data;
    } catch (err) {
        const msg = err.response?.data?.error || err.message || 'Prescription extraction failed';
        throw new Error(msg);
    }
}

/**
 * POST /api/ocr/bytez/prescription - extract medical prescription data using Bytez API.
 * @param {File} file - prescription image file
 * @returns {{ structured, doctor_name, patient_name, medications[], instructions, etc. }}
 */
export async function extractPrescriptionBytez(file) {
    const formData = new FormData();
    formData.append('image', file);

    try {
        const res = await client.post('/ocr/bytez/prescription', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
        });
        return res.data;
    } catch (err) {
        const msg = err.response?.data?.error || err.message || 'Bytez prescription extraction failed';
        throw new Error(msg);
    }
}

export default client;
