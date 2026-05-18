import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import Toast from './components/Toast';
import Home from './pages/Home';
import { useToast } from './hooks/useToast';

export default function App() {
  const [isDark, setIsDark] = useState(() => {
    const saved = localStorage.getItem('ocr-theme');
    if (saved) return saved === 'dark';
    return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false;
  });

  const { toasts, addToast, removeToast } = useToast();

  useEffect(() => {
    const theme = isDark ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('ocr-theme', theme);
  }, [isDark]);

  const toggleTheme = () => setIsDark((prev) => !prev);

  return (
    <>
      <Header isDark={isDark} onToggleTheme={toggleTheme} />
      <Home addToast={addToast} />
      <Toast toasts={toasts} removeToast={removeToast} />

      {/* Footer */}
      <footer
        style={{
          textAlign: 'center',
          padding: '20px 16px',
          borderTop: '1px solid rgba(var(--color-border), .3)',
          background: 'rgba(var(--color-surface), .5)',
          color: 'rgb(var(--color-text-secondary))',
          fontSize: '0.8125rem',
        }}
      >
        Text Detection OCR {new Date().getFullYear()} - Built with React & Tesseract OCR
      </footer>
    </>
  );
}
