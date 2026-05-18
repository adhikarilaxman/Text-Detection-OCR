import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle, AlertCircle, Info, X } from 'lucide-react';

const icons = {
    success: CheckCircle,
    error: AlertCircle,
    info: Info,
};

function ToastItem({ toast, onRemove }) {
    const Icon = icons[toast.type] || Info;

    return (
        <motion.div
            layout
            initial={{ opacity: 0, x: 60, scale: 0.9 }}
            animate={{ opacity: 1, x: 0, scale: 1 }}
            exit={{ opacity: 0, x: 60, scale: 0.9 }}
            transition={{ type: 'spring', stiffness: 400, damping: 28 }}
            className={`toast toast-${toast.type}`}
            onClick={() => onRemove(toast.id)}
            role="alert"
        >
            <Icon size={18} style={{ flexShrink: 0 }} />
            <span style={{ flex: 1 }}>{toast.message}</span>
            <X size={14} style={{ opacity: 0.5, flexShrink: 0 }} />
        </motion.div>
    );
}

export default function Toast({ toasts, removeToast }) {
    return (
        <div className="toast-container">
            <AnimatePresence mode="popLayout">
                {toasts.map((t) => (
                    <ToastItem key={t.id} toast={t} onRemove={removeToast} />
                ))}
            </AnimatePresence>
        </div>
    );
}
