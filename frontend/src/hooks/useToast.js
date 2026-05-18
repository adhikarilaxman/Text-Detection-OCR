import { useState, useCallback, useRef } from 'react';

let nextId = 1;

export function useToast(autoDismissMs = 3500) {
    const [toasts, setToasts] = useState([]);
    const timers = useRef({});

    const removeToast = useCallback((id) => {
        clearTimeout(timers.current[id]);
        delete timers.current[id];
        setToasts((prev) => prev.filter((t) => t.id !== id));
    }, []);

    const addToast = useCallback(
        (message, type = 'success') => {
            const id = nextId++;
            setToasts((prev) => [...prev, { id, message, type }]);
            timers.current[id] = setTimeout(() => removeToast(id), autoDismissMs);
            return id;
        },
        [autoDismissMs, removeToast]
    );

    return { toasts, addToast, removeToast };
}
