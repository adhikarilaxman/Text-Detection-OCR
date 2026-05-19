import React, { useState, useCallback } from 'react';

import { motion, AnimatePresence } from 'framer-motion';

import { Copy, Download, Trash2, FileText, BarChart2, Sparkles, Loader2, List, AlertCircle } from 'lucide-react';

import { cleanTextWithAI } from '../services/api';



export default function ExtractedText({ text, confidence, onClear, addToast }) {

    // -------  AI state (separate from raw OCR text) -------

    const [isCleaning, setIsCleaning] = useState(false);

    const [cleanedText, setCleanedText] = useState(null);   // AI corrected text

    const [summary, setSummary] = useState(null);           // AI bullet points

    const [aiError, setAiError] = useState(null);           // Error from AI



    // Raw OCR text metrics

    const isEmpty = !text || text.trim().length === 0;

    const wordCount = isEmpty ? 0 : text.trim().split(/\s+/).filter(Boolean).length;

    const charCount = text ? text.length : 0;

    const confidencePct = confidence != null ? Math.round(confidence <= 1 ? confidence * 100 : confidence) : null;



    // -------  Handlers -------

    const handleCopy = useCallback(async (textToCopy) => {

        if (!textToCopy) { addToast('Nothing to copy', 'error'); return; }

        try {

            await navigator.clipboard.writeText(textToCopy);

            addToast('Copied Successfully', 'success');

        } catch {

            addToast('Failed to copy text', 'error');

        }

    }, [addToast]);



    const handleDownload = useCallback((textToDownload, filename = 'extracted-text.txt') => {

        if (!textToDownload) { addToast('Nothing to download', 'error'); return; }

        const blob = new Blob([textToDownload], { type: 'text/plain' });

        const url = URL.createObjectURL(blob);

        const a = document.createElement('a');

        a.href = url;

        a.download = filename;

        document.body.appendChild(a);

        a.click();

        document.body.removeChild(a);

        URL.revokeObjectURL(url);

        addToast('Text downloaded!', 'success');

    }, [addToast]);



    const handleClear = useCallback(() => {

        if (onClear) onClear();

        addToast('Cleared results', 'info');

    }, [onClear, addToast]);



    // Send raw OCR text to AI cleaning endpoint

    const handleCleanText = async () => {

        if (isEmpty) return;

        setIsCleaning(true);

        setAiError(null);

        setCleanedText(null);

        setSummary(null);

        try {

            const data = await cleanTextWithAI(text);

            // data = { cleaned_text: "...", summary: [...] }

            setCleanedText(data.cleaned_text || '');

            setSummary(Array.isArray(data.summary) ? data.summary : []);

            addToast('Text cleaned by AI!', 'success');

        } catch (err) {

            const msg = err.message || 'Failed to clean text';

            setAiError(msg);

            addToast(msg, 'error');

        } finally {

            setIsCleaning(false);

        }

    };



    // Don't render anything if text prop was never provided

    if (text == null) return null;



    return (

        <motion.div

            initial={{ opacity: 0, scale: 0.96 }}

            animate={{ opacity: 1, scale: 1 }}

            transition={{ duration: 0.4, delay: 0.1 }}

            className="glass-card"

            style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}

        >

            {/* ===== RAW OCR TEXT SECTION ===== */}

            <SectionHeader

                icon={<FileText size={18} style={{ color: 'rgb(var(--color-primary))' }} />}

                title="Raw OCR Text"

                actions={

                    <>

                        <button onClick={() => handleCopy(text)} className="btn-icon" title="Copy raw text"><Copy size={15} /></button>

                        <button onClick={() => handleDownload(text, 'raw-ocr-text.txt')} className="btn-icon" title="Download raw text"><Download size={15} /></button>

                        <button onClick={handleClear} className="btn-icon" title="Clear results"><Trash2 size={15} /></button>

                    </>

                }

            />



            {/* Stats */}

            <div style={{

                display: 'flex', flexWrap: 'wrap', gap: 10,

                padding: '10px 20px',

                borderBottom: '1px solid rgba(var(--color-border), .25)',

                background: 'rgba(var(--color-surface-alt), .4)',

            }}>

                <span className="badge badge-primary"><BarChart2 size={12} />{wordCount} words</span>

                <span className="badge badge-primary">{charCount} chars</span>

                {confidencePct != null && <span className="badge badge-success">{confidencePct}% confidence</span>}

            </div>



            {/* Raw text - preserve whitespace and line breaks exactly */}

            <div

                className="extracted-text-area"

                tabIndex={0}

                role="textbox"

                aria-readonly="true"

                aria-label="Raw OCR text"

                style={{ flex: 1, whiteSpace: 'pre-wrap', overflowY: 'auto' }}

            >

                {isEmpty

                    ? <span style={{ color: 'rgb(var(--color-text-secondary))', fontStyle: 'italic' }}>No text was detected in this image.</span>

                    : text

                }

            </div>



            {/* ===== CLEAN WITH AI BUTTON ===== */}

            {!isEmpty && (

                <div style={{ padding: '16px 20px', borderTop: '1px solid rgba(var(--color-border), .4)' }}>

                    <button

                        className="btn-primary"

                        onClick={handleCleanText}

                        disabled={isCleaning}

                        style={{ width: '100%', justifyContent: 'center' }}

                    >

                        {isCleaning

                            ? <><Loader2 size={17} style={{ animation: 'spin .7s linear infinite' }} /> Processing with AI...</>

                            : <><Sparkles size={17} /> Clean with AI</>

                        }

                    </button>

                </div>

            )}



            {/* ===== AI ERROR MESSAGE ===== */}

            <AnimatePresence>

                {aiError && (

                    <motion.div

                        initial={{ opacity: 0, height: 0 }}

                        animate={{ opacity: 1, height: 'auto' }}

                        exit={{ opacity: 0, height: 0 }}

                        style={{

                            display: 'flex', alignItems: 'center', gap: 8,

                            padding: '12px 20px',

                            borderTop: '1px solid rgba(var(--color-border), .4)',

                            background: 'rgba(239,68,68,0.08)',

                            color: '#ef4444', fontSize: '0.875rem'

                        }}

                    >

                        <AlertCircle size={16} />

                        {aiError}

                    </motion.div>

                )}

            </AnimatePresence>



            {/* ===== CLEANED TEXT SECTION ===== */}

            <AnimatePresence>

                {cleanedText != null && (

                    <motion.div

                        initial={{ opacity: 0 }}

                        animate={{ opacity: 1 }}

                        transition={{ duration: 0.3 }}

                        style={{ display: 'flex', flexDirection: 'column' }}

                    >

                        <SectionHeader

                            icon={<Sparkles size={18} style={{ color: 'rgb(var(--color-primary))' }} />}

                            title="Cleaned Text"

                            style={{ backgroundColor: 'rgba(var(--color-primary), 0.05)' }}

                            actions={

                                <>

                                    <button onClick={() => handleCopy(cleanedText)} className="btn-icon" title="Copy cleaned text"><Copy size={15} /></button>

                                    <button onClick={() => handleDownload(cleanedText, 'cleaned-text.txt')} className="btn-icon" title="Download cleaned text"><Download size={15} /></button>

                                </>

                            }

                        />

                        <div

                            className="extracted-text-area"

                            style={{ flex: 1, whiteSpace: 'pre-wrap', overflowY: 'auto' }}

                            aria-label="AI cleaned text"

                        >

                            {cleanedText || <span style={{ fontStyle: 'italic', color: 'rgb(var(--color-text-secondary))' }}>No cleaned text returned.</span>}

                        </div>

                    </motion.div>

                )}

            </AnimatePresence>



            {/* ===== SUMMARY SECTION ===== */}

            <AnimatePresence>

                {summary != null && summary.length > 0 && (

                    <motion.div

                        initial={{ opacity: 0 }}

                        animate={{ opacity: 1 }}

                        transition={{ duration: 0.3 }}

                    >

                        <SectionHeader

                            icon={<List size={18} style={{ color: 'rgb(var(--color-accent))' }} />}

                            title="Summary"

                            style={{ backgroundColor: 'rgba(var(--color-accent), 0.05)' }}

                        />

                        <div style={{ padding: '16px 20px', fontSize: '0.9375rem', color: 'rgb(var(--color-text))', lineHeight: 1.7 }}>

                            <ul style={{ margin: 0, paddingLeft: '20px', display: 'flex', flexDirection: 'column', gap: '6px' }}>

                                {summary.map((point, index) => (

                                    <li key={index}>{point}</li>

                                ))}

                            </ul>

                        </div>

                    </motion.div>

                )}

            </AnimatePresence>

        </motion.div>

    );

}



/** Reusable section header bar */

function SectionHeader({ icon, title, actions, style }) {

    return (

        <div style={{

            display: 'flex', alignItems: 'center', justifyContent: 'space-between',

            flexWrap: 'wrap', gap: 12,

            padding: '14px 20px',

            borderTop: '1px solid rgba(var(--color-border), .4)',

            borderBottom: '1px solid rgba(var(--color-border), .4)',

            ...style,

        }}>

            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>

                {icon}

                <span style={{ fontWeight: 700, fontSize: '0.9375rem', color: 'rgb(var(--color-text))' }}>{title}</span>

            </div>

            {actions && <div style={{ display: 'flex', gap: 6 }}>{actions}</div>}

        </div>

    );

}

