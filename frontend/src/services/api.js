import axios from 'axios';

const API_BASE =
    process.env.REACT_APP_API_URL ||
    (process.env.NODE_ENV === 'production' ? '/api' : 'http://localhost:5000/api');

const client = axios.create({
    baseURL: API_BASE,
    timeout: 120000,
});

/**
 * Wake up the Render backend if it's sleeping (free tier spins down after inactivity).
 * Pings /api/health up to maxAttempts times with a delay between each.
 * Resolves when the backend responds, or rejects after all attempts fail.
 */
async function wakeUpBackend(maxAttempts = 8, delayMs = 4000) {
    for (let i = 0; i < maxAttempts; i++) {
        try {
            await client.get('/health', { timeout: 8000 });
            return; // backend is awake
        } catch {
            if (i < maxAttempts - 1) {
                await new Promise((r) => setTimeout(r, delayMs));
            }
        }
    }
    throw new Error(
        'The backend server is taking too long to start. ' +
        'It may be waking up from sleep — please wait 30 seconds and try again.'
    );
}

/**
 * Wrap any API call with automatic backend wake-up on network error.
 * If the first attempt fails with ERR_NETWORK, waits for the backend to wake up then retries.
 */
async function withWakeUp(apiFn) {
    try {
        return await apiFn();
    } catch (err) {
        if (err.code === 'ERR_NETWORK' || !err.response) {
            // Backend might be sleeping — try to wake it up then retry once
            await wakeUpBackend();
            return await apiFn();
        }
        throw err;
    }
}

/**
 * POST /api/ocr - send image for OCR processing.
 */
export async function performOCR(file) {
    const formData = new FormData();
    formData.append('image', file);

    return withWakeUp(async () => {
        try {
            const res = await client.post('/ocr', formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
            });
            if (res.data && res.data.success === false) {
                throw new Error(res.data.error || 'OCR processing failed');
            }
            return res.data;
        } catch (err) {
            if (err.response?.data?.error) throw new Error(err.response.data.error);
            if (err.code === 'ECONNABORTED' || err.message?.includes('timeout'))
                throw new Error('Request timed out. Please try again.');
            if (err.code === 'ERR_NETWORK' || !err.response)
                throw new Error('Cannot reach the server. The backend may still be waking up — please try again in a moment.');
            throw new Error(err.message || 'Failed to process image');
        }
    });
}

/**
 * POST /api/handwritten-ocr - send image for handwritten OCR processing.
 */
export async function performHandwrittenOCR(file) {
    const formData = new FormData();
    formData.append('image', file);

    return withWakeUp(async () => {
        try {
            const res = await client.post('/handwritten-ocr', formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
                timeout: 180000,
            });
            if (res.data && res.data.success === false) {
                throw new Error(res.data.error || 'Handwritten OCR processing failed');
            }
            return res.data;
        } catch (err) {
            if (err.response?.data?.error) throw new Error(err.response.data.error);
            if (err.code === 'ECONNABORTED' || err.message?.includes('timeout'))
                throw new Error('Request timed out. Please try again.');
            if (err.code === 'ERR_NETWORK' || !err.response)
                throw new Error('Cannot reach the server. The backend may still be waking up — please try again in a moment.');
            throw new Error(err.message || 'Failed to process image for handwritten text');
        }
    });
}

/**
 * POST /api/prescription-ocr - send image for medical prescription OCR processing.
 */
export async function performPrescriptionOCR(file) {
    const formData = new FormData();
    formData.append('image', file);

    return withWakeUp(async () => {
        try {
            const res = await client.post('/prescription-ocr', formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
                timeout: 180000,
            });
            if (res.data && res.data.success === false) {
                throw new Error(res.data.error || 'Prescription OCR processing failed');
            }
            return res.data;
        } catch (err) {
            if (err.response?.data?.error) throw new Error(err.response.data.error);
            if (err.code === 'ECONNABORTED' || err.message?.includes('timeout'))
                throw new Error('Request timed out. Please try again.');
            if (err.code === 'ERR_NETWORK' || !err.response)
                throw new Error('Cannot reach the server. The backend may still be waking up — please try again in a moment.');
            throw new Error(err.message || 'Failed to process image for medical prescription');
        }
    });
}

/**
 * POST /api/clean-text - send raw OCR text to be cleaned and summarized by AI.
 */
export async function cleanTextWithAI(text) {
    try {
        const res = await client.post('/clean-text', { text });
        if (res.data && res.data.error) throw new Error(res.data.error);
        return {
            cleaned_text: res.data.cleaned_text || '',
            summary: Array.isArray(res.data.summary) ? res.data.summary : [],
        };
    } catch (err) {
        const backendMsg = err.response?.data?.error;
        if (backendMsg) throw new Error(backendMsg);
        if (err.code === 'ECONNABORTED' || err.message?.includes('timeout'))
            throw new Error('AI request timed out. Please try again.');
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
 * POST /api/ocr/bytez/handwritten - extract handwritten text using AI Vision.
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
 * POST /api/ocr/bytez/prescription - extract medical prescription data using AI Vision.
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
