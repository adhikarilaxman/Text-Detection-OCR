import React, { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Sparkles, ArrowLeft, Loader2, FileText, Activity } from 'lucide-react';
import UploadBox from '../components/UploadBox';
import ImagePreview from '../components/ImagePreview';
import ExtractedText from '../components/ExtractedText';
import { performOCR, performPrescriptionOCR, performHandwrittenOCR } from '../services/api';
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
        // Warn user that the backend may be waking up on first request
        addToast('Processing... If this is the first request, the server may take ~30s to wake up.', 'info');
        try {
            let data;
            if (ocrMode === 'prescription') {
                data = await performPrescriptionOCR(file);
            } else if (ocrMode === 'handwritten') {
                data = await performHandwrittenOCR(file);
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
                            }}
                        >
                            <button className="btn-secondary" onClick={handleReset} disabled={isProcessing}>
                                <ArrowLeft size={15} />
                                New Upload
                            </button>
                        </div>

                        {/* Two-column on desktop */}
                        <div
                            style={{
                                display: 'grid',
                                gridTemplateColumns: 'minmax(0, 5fr) minmax(0, 7fr)',
                                gap: 28,
                                alignItems: 'start',
                            }}
                            className="content-grid"
                        >
                            <div style={{ position: 'relative' }}>
                                <ImagePreview
                                    src={preview}
                                    isProcessing={isProcessing}
                                    onClear={handleReset}
                                    heatmapSrc={heatmapSrc}
                                />
                            </div>

                            {/* Right column workspace states */}
                            <AnimatePresence mode="wait">
                                {isProcessing ? (
                                    <motion.div
                                        key="processing-state"
                                        initial={{ opacity: 0, scale: 0.98 }}
                                        animate={{ opacity: 1, scale: 1 }}
                                        exit={{ opacity: 0, scale: 0.98 }}
                                        transition={{ duration: 0.3 }}
                                        className="glass-card"
                                        style={{
                                            padding: 28,
                                            display: 'flex',
                                            flexDirection: 'column',
                                            gap: 24,
                                            background: 'rgba(var(--color-surface), 0.75)',
                                            border: '1px solid rgba(var(--color-border), 0.5)',
                                        }}
                                    >
                                        <div>
                                            <h2 style={{ fontSize: '1.25rem', fontWeight: 800, color: 'rgb(var(--color-text))', marginBottom: 6 }}>
                                                Processing Document
                                            </h2>
                                            <p style={{ fontSize: '0.875rem', color: 'rgb(var(--color-text-secondary))' }}>
                                                Our models are analyzing the pixel data, running OCR grids, and cleaning the text.
                                            </p>
                                        </div>

                                        {/* Skeleton lines with shimmer effect */}
                                        <div style={{ display: 'flex', flexDirection: 'column', gap: 14, margin: '8px 0' }}>
                                            <div className="skeleton-line" style={{ width: '85%' }} />
                                            <div className="skeleton-line" style={{ width: '95%' }} />
                                            <div className="skeleton-line" style={{ width: '60%' }} />
                                            <div className="skeleton-line" style={{ width: '80%' }} />
                                            <div className="skeleton-line" style={{ width: '45%' }} />
                                        </div>

                                        <div style={{ 
                                            display: 'flex', 
                                            alignItems: 'center', 
                                            justifyContent: 'center', 
                                            gap: 10,
                                            padding: '14px',
                                            borderRadius: 'var(--radius-md)',
                                            background: 'rgba(var(--color-primary), 0.06)',
                                            color: 'rgb(var(--color-primary))',
                                            fontSize: '0.875rem',
                                            fontWeight: 600
                                        }}>
                                            <Loader2 size={16} className="spinner" />
                                            <span>Running AI processing pipeline...</span>
                                        </div>
                                    </motion.div>
                                ) : result ? (
                                    <ExtractedText
                                        key="result-state"
                                        text={result.full_text || result.text || ''}
                                        confidence={avgConfidence}
                                        onClear={handleReset}
                                        addToast={addToast}
                                        template={result.template}
                                        rawText={result.raw_text}
                                    />
                                ) : (
                                    <motion.div
                                        key="workspace-state"
                                        initial={{ opacity: 0, scale: 0.98 }}
                                        animate={{ opacity: 1, scale: 1 }}
                                        exit={{ opacity: 0, scale: 0.98 }}
                                        transition={{ duration: 0.3 }}
                                        className="glass-card"
                                        style={{
                                            padding: 28,
                                            display: 'flex',
                                            flexDirection: 'column',
                                            gap: 24,
                                            background: 'rgba(var(--color-surface), 0.75)',
                                            border: '1px solid rgba(var(--color-border), 0.5)',
                                        }}
                                    >
                                        <div>
                                            <h2 style={{ fontSize: '1.25rem', fontWeight: 800, color: 'rgb(var(--color-text))', marginBottom: 6 }}>
                                                Select Extraction Mode
                                            </h2>
                                            <p style={{ fontSize: '0.875rem', color: 'rgb(var(--color-text-secondary))' }}>
                                                Configure the OCR engine mode for optimal accuracy based on your document type.
                                            </p>
                                        </div>

                                        {/* Visual Mode Selection Grid */}
                                        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                                            {[
                                                {
                                                    id: 'normal',
                                                    title: 'Standard OCR',
                                                    description: 'Best for clean, printed scanned documents, tables, & screenshots.',
                                                    icon: <FileText size={18} />
                                                },
                                                {
                                                    id: 'handwritten',
                                                    title: 'Handwritten Text (AI)',
                                                    description: 'Notes, whiteboards, or complex handwritten cards via Gemini Vision.',
                                                    icon: <Sparkles size={18} />
                                                },
                                                {
                                                    id: 'prescription',
                                                    title: 'Medical Prescription (AI)',
                                                    description: 'Extracts structured medicines, doctor notes, dosage, and schedules.',
                                                    icon: <Activity size={18} />
                                                }
                                            ].map((mode) => (
                                                <motion.div
                                                    key={mode.id}
                                                    whileHover={{ scale: 1.01 }}
                                                    whileTap={{ scale: 0.99 }}
                                                    onClick={() => setOcrMode(mode.id)}
                                                    style={{
                                                        display: 'flex',
                                                        alignItems: 'flex-start',
                                                        gap: 14,
                                                        padding: '16px 20px',
                                                        borderRadius: 'var(--radius-md)',
                                                        border: ocrMode === mode.id 
                                                            ? '2px solid rgb(var(--color-primary))' 
                                                            : '1px solid rgba(var(--color-border), 0.5)',
                                                        background: ocrMode === mode.id 
                                                            ? 'rgba(var(--color-primary), 0.05)' 
                                                            : 'rgba(var(--color-surface), 0.5)',
                                                        cursor: 'pointer',
                                                        transition: 'all 0.2s ease',
                                                        boxShadow: ocrMode === mode.id ? '0 0 15px rgba(var(--color-primary), 0.1)' : 'none',
                                                    }}
                                                >
                                                    <div style={{
                                                        color: ocrMode === mode.id ? 'rgb(var(--color-primary))' : 'rgb(var(--color-text-secondary))',
                                                        paddingTop: 2
                                                    }}>
                                                        {mode.icon}
                                                    </div>
                                                    <div style={{ textAlign: 'left' }}>
                                                        <div style={{ fontWeight: 700, fontSize: '0.9375rem', color: 'rgb(var(--color-text))', marginBottom: 2 }}>
                                                            {mode.title}
                                                        </div>
                                                        <div style={{ fontSize: '0.8125rem', color: 'rgb(var(--color-text-secondary))', lineHeight: 1.35 }}>
                                                            {mode.description}
                                                        </div>
                                                    </div>
                                                </motion.div>
                                            ))}
                                        </div>

                                        <button 
                                            className="btn-primary" 
                                            onClick={handleExtract} 
                                            style={{ width: '100%', padding: '14px 28px', marginTop: 8, justifyContent: 'center' }}
                                        >
                                            <Sparkles size={16} />
                                            Start Text Extraction
                                        </button>
                                    </motion.div>
                                )}
                            </AnimatePresence>
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
