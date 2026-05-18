import React, { useRef, useCallback } from 'react';
import { motion } from 'framer-motion';
import { CloudUpload, Image as ImageIcon } from 'lucide-react';

const ACCEPTED_TYPES = ['image/png', 'image/jpeg', 'image/jpg'];
const MAX_SIZE_MB = 16;

export default function UploadBox({
    onFileSelect,
    isProcessing,
    dragActive,
    setDragActive,
    selectedFileName,
}) {
    const inputRef = useRef(null);

    const validateFile = useCallback((file) => {
        if (!file) return 'No file selected';
        if (!ACCEPTED_TYPES.includes(file.type)) {
            return 'Invalid file type. Please use JPG or PNG.';
        }
        if (file.size > MAX_SIZE_MB * 1024 * 1024) {
            return `File too large. Maximum size is ${MAX_SIZE_MB}MB.`;
        }
        return null;
    }, []);

    const handleFile = useCallback(
        (file) => {
            const error = validateFile(file);
            if (error) {
                onFileSelect(null, error);
                return;
            }
            onFileSelect(file, null);
        },
        [validateFile, onFileSelect]
    );

    const handleDrag = useCallback(
        (e, active) => {
            e.preventDefault();
            e.stopPropagation();
            if (!isProcessing) setDragActive(active);
        },
        [isProcessing, setDragActive]
    );

    const handleDrop = useCallback(
        (e) => {
            e.preventDefault();
            e.stopPropagation();
            setDragActive(false);
            if (isProcessing) return;
            const file = e.dataTransfer.files[0];
            handleFile(file);
        },
        [isProcessing, setDragActive, handleFile]
    );

    const handleInputChange = useCallback(
        (e) => {
            const file = e.target.files[0];
            if (file) handleFile(file);
            e.target.value = '';
        },
        [handleFile]
    );

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1, duration: 0.5 }}
        >
            <div
                className={`drop-zone ${dragActive ? 'drag-active' : ''}`}
                onDragOver={(e) => handleDrag(e, true)}
                onDragEnter={(e) => handleDrag(e, true)}
                onDragLeave={(e) => handleDrag(e, false)}
                onDrop={handleDrop}
                onClick={() => !isProcessing && inputRef.current?.click()}
                style={{
                    padding: '42px 24px',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    textAlign: 'center',
                    opacity: isProcessing ? 0.6 : 1,
                    pointerEvents: isProcessing ? 'none' : 'auto',
                }}
            >
                <input
                    ref={inputRef}
                    type="file"
                    accept=".jpg,.jpeg,.png"
                    onChange={handleInputChange}
                    style={{ display: 'none' }}
                    id="file-upload-input"
                />

                <motion.div
                    animate={dragActive ? { scale: 1.15, rotate: 5 } : { scale: 1, rotate: 0 }}
                    transition={{ type: 'spring', stiffness: 300, damping: 20 }}
                    style={{
                        width: 40,
                        height: 40,
                        borderRadius: 12,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: 'rgb(var(--color-primary))',
                        marginBottom: 22,
                    }}
                >
                    <CloudUpload size={34} strokeWidth={2.2} />
                </motion.div>

                <h3
                    style={{
                        fontSize: '1.125rem',
                        fontWeight: 800,
                        marginBottom: 8,
                        color: 'rgb(var(--color-text))',
                    }}
                >
                    {dragActive ? 'Drop your image here' : 'Drag & drop your image here'}
                </h3>

                <p
                    style={{
                        fontSize: '0.875rem',
                        color: 'rgb(var(--color-text-secondary))',
                        marginBottom: 28,
                    }}
                >
                    or click to browse - Supports JPG, JPEG, PNG
                </p>

                <button className="btn-primary" type="button" disabled={isProcessing}>
                    <ImageIcon size={16} />
                    Choose File
                </button>

                {selectedFileName && (
                    <motion.p
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        style={{
                            marginTop: 16,
                            fontSize: '0.8125rem',
                            fontWeight: 500,
                            color: 'rgb(var(--color-primary))',
                        }}
                    >
                        Selected: {selectedFileName}
                    </motion.p>
                )}
            </div>
        </motion.div>
    );
}
