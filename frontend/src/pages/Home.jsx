import React, { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Sparkles, ArrowLeft, Loader2 } from 'lucide-react';
import UploadBox from '../components/UploadBox';
import ImagePreview from '../components/ImagePreview';
import ExtractedText from '../components/ExtractedText';
import { performOCR, performPrescriptionOCR, extractHandwrittenBytez } from '../services/api';

export default function Home({ addToast }) {
    const [file, setFile] = useState(null);
    const [preview, setPreview] = useState(null);
    const [isProcessing, setIsProcessing] = useState(false);
    const [result, setResult] = useState(null);
    const [dragActive, setDragActive] = useState(false);
    const [ocrMode, setOcrMode] = useState('normal');

    /* ---- File selection ---- */
    const handleFileSelect = useCallback(
        (selectedFile, error) => {
            if (error) {
                addToast(error, 'error');
                return;
            }
            setFile(selectedFile);
            setResult(null);

            const reader = new FileReader();
            reader.onloadend = () => setPreview(reader.result);
            reader.readAsDataURL(selectedFile);
        },
        [addToast]
    );

    /* ---- Run OCR ---- */
    const handleExtract = useCallback(async () => {
        if (!file) {
            addToast('Please select an image first', 'error');
            return;
        }

        setIsProcessing(true);
        try {
            let data;
            if (ocrMode === 'prescription') {
                data = await performPrescriptionOCR(file);
            } else if (ocrMode === 'handwritten') {
                data = await extractHandwrittenBytez(file);
            } else {
                data = await performOCR(file);
            }
            setResult(data);
            addToast('Text extracted successfully!', 'success');
        } catch (err) {
            addToast(err.message || 'Failed to process image', 'error');
        } finally {
            setIsProcessing(false);
        }
    }, [file, ocrMode, addToast]);

    /* ---- Reset ---- */
    const handleReset = useCallback(() => {
        setFile(null);
        setPreview(null);
        setResult(null);
    }, []);

    /* ---- Compute average confidence ---- */
    const avgConfidence =
        result?.results?.length > 0
            ? result.results.reduce((sum, r) => sum + (r.confidence || 0), 0) / result.results.length
            : result?.confidence ?? null;

    /* ---- Compute heatmap data URL ---- */
    const heatmapSrc = result?.heatmap_image
        ? `data:image/png;base64,${result.heatmap_image}`
        : null;

    return (
        <main
            style={{
                maxWidth: 1510,
                margin: '0 auto',
                padding: preview ? '32px 24px 72px' : '54px 24px 96px',
                minHeight: 'calc(100vh - 92px)',
            }}
        >
            {/* Title */}
            <motion.div
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                style={{ textAlign: 'center', marginBottom: preview ? 34 : 122 }}
            >
                <h1
                    style={{
                        fontSize: 'clamp(2rem, 4.2vw, 2.85rem)',
                        fontWeight: 800,
                        letterSpacing: '0',
                        lineHeight: 1.12,
                        color: 'rgb(var(--color-text))',
                        marginBottom: 18,
                    }}
                >
                    Extract Text from Images{' '}
                    <span
                        style={{
                            background: 'linear-gradient(135deg, rgb(var(--color-primary)), rgb(var(--color-accent)))',
                            WebkitBackgroundClip: 'text',
                            WebkitTextFillColor: 'transparent',
                            backgroundClip: 'text',
                        }}
                    >
                        Instantly
                    </span>
                </h1>
                <p
                    style={{
                        fontSize: 'clamp(1rem, 1.7vw, 1.35rem)',
                        color: 'rgb(var(--color-text-secondary))',
                        maxWidth: 610,
                        margin: '0 auto',
                        lineHeight: 1.45,
                    }}
                >
                    Upload an image and our AI-powered OCR engine will extract selectable, copyable text in seconds.
                </p>
            </motion.div>

            {/* Upload zone - shown when no preview */}
            <AnimatePresence mode="wait">
                {!preview && (
                    <motion.div
                        key="upload"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0, y: -10 }}
                        style={{ maxWidth: 620, margin: '0 auto' }}
                    >
                        <UploadBox
                            onFileSelect={handleFileSelect}
                            isProcessing={isProcessing}
                            dragActive={dragActive}
                            setDragActive={setDragActive}
                            selectedFileName={file?.name}
                        />
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Preview + Results */}
            <AnimatePresence mode="wait">
                {preview && (
                    <motion.div
                        key="content"
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0 }}
                    >
                        {/* Action bar */}
                        <div
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between',
                                flexWrap: 'wrap',
                                gap: 12,
                                marginBottom: 24,
                                maxWidth: 640,
                                marginLeft: 'auto',
                                marginRight: 'auto',
                            }}
                        >
                            <button className="btn-secondary" onClick={handleReset} disabled={isProcessing}>
                                <ArrowLeft size={15} />
                                New Upload
                            </button>

                            {!result && (
                                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                        <label style={{ fontSize: '0.875rem', fontWeight: 500, color: 'rgb(var(--color-text-secondary))' }}>
                                            Mode:
                                        </label>
                                        <select
                                            value={ocrMode}
                                            onChange={(e) => setOcrMode(e.target.value)}
                                            disabled={isProcessing}
                                            style={{
                                                padding: '6px 12px',
                                                borderRadius: 'var(--radius-sm)',
                                                border: '1px solid rgba(var(--color-border), 0.5)',
                                                background: 'rgba(var(--color-surface), 0.8)',
                                                color: 'rgb(var(--color-text))',
                                                fontSize: '0.875rem',
                                                outline: 'none',
                                                cursor: 'pointer'
                                            }}
                                        >
                                            <option value="normal">Standard OCR</option>
                                            <option value="handwritten">Handwritten Text</option>
                                            <option value="prescription">Medical Prescription</option>
                                        </select>
                                    </div>
                                    <button className="btn-primary" onClick={handleExtract} disabled={isProcessing}>
                                        {isProcessing ? (
                                            <Loader2 size={17} style={{ animation: 'spin .7s linear infinite' }} />
                                        ) : (
                                            <Sparkles size={17} />
                                        )}
                                        {isProcessing ? 'Processing...' : 'Extract Text'}
                                    </button>
                                </div>
                            )}
                        </div>

                        {/* Two-column on desktop */}
                        <div
                            style={{
                                display: 'grid',
                                gridTemplateColumns: result ? 'minmax(0,5fr) minmax(0,7fr)' : '1fr',
                                gap: 24,
                                alignItems: 'start',
                            }}
                            className="content-grid"
                        >
                            <ImagePreview
                                src={preview}
                                isProcessing={isProcessing}
                                onClear={handleReset}
                                heatmapSrc={heatmapSrc}
                            />

                            {result && (
                                <ExtractedText
                                    text={result.full_text || result.text || ''}
                                    confidence={avgConfidence}
                                    onClear={handleReset}
                                    addToast={addToast}
                                    template={result.template}
                                    rawText={result.raw_text}
                                />
                            )}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Responsive grid override */}
            <style>{`
        @media (max-width: 768px) {
          .content-grid {
            grid-template-columns: 1fr !important;
          }
        }
      `}</style>
        </main>
    );
}
