import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Loader2, X, Eye, EyeOff } from 'lucide-react';

export default function ImagePreview({ src, isProcessing, onClear, heatmapSrc }) {
    const [showHeatmap, setShowHeatmap] = useState(false);

    if (!src) return null;

    const displaySrc = showHeatmap && heatmapSrc ? heatmapSrc : src;

    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.4 }}
            className="glass-card"
            style={{ overflow: 'hidden', position: 'relative' }}
        >
            {/* Header */}
            <div
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '14px 20px',
                    borderBottom: '1px solid rgba(var(--color-border), .4)',
                }}
            >
                <span style={{ fontWeight: 600, fontSize: '0.9375rem', color: 'rgb(var(--color-text))' }}>
                    {showHeatmap ? 'Confidence Heatmap' : 'Image Preview'}
                </span>
                <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                    {heatmapSrc && !isProcessing && (
                        <button
                            onClick={() => setShowHeatmap(!showHeatmap)}
                            className="btn-icon"
                            title={showHeatmap ? 'Show original' : 'Show confidence heatmap'}
                            style={{
                                width: 32, height: 32, padding: 0,
                                color: showHeatmap ? 'rgb(var(--color-primary))' : 'rgb(var(--color-text-secondary))',
                            }}
                        >
                            {showHeatmap ? <EyeOff size={14} /> : <Eye size={14} />}
                        </button>
                    )}
                    {!isProcessing && (
                        <button
                            onClick={onClear}
                            className="btn-icon"
                            aria-label="Remove image"
                            style={{ width: 32, height: 32, padding: 0 }}
                        >
                            <X size={14} />
                        </button>
                    )}
                </div>
            </div>

            {/* Image container */}
            <div
                style={{
                    position: 'relative',
                    padding: 16,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    background: 'rgba(var(--color-surface-alt), .5)',
                    minHeight: 240,
                }}
            >
                <img
                    src={displaySrc}
                    alt={showHeatmap ? "Confidence heatmap overlay" : "Uploaded preview"}
                    style={{
                        maxWidth: '100%',
                        maxHeight: 400,
                        objectFit: 'contain',
                        borderRadius: 'var(--radius-sm)',
                    }}
                />

                {/* Processing overlay */}
                {isProcessing && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        style={{
                            position: 'absolute',
                            inset: 0,
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            justifyContent: 'center',
                            gap: 12,
                            background: 'rgba(var(--color-surface), .7)',
                            backdropFilter: 'blur(4px)',
                            borderRadius: 'var(--radius-sm)',
                        }}
                    >
                        <Loader2
                            size={32}
                            style={{ color: 'rgb(var(--color-primary))', animation: 'spin .8s linear infinite' }}
                        />
                        <span
                            style={{
                                fontSize: '0.875rem',
                                fontWeight: 600,
                                color: 'rgb(var(--color-primary))',
                            }}
                        >
                            Processing...
                        </span>
                    </motion.div>
                )}
            </div>
        </motion.div>
    );
}
