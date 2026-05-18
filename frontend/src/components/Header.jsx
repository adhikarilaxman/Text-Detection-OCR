import React from 'react';
import { motion } from 'framer-motion';
import { FileText, Github, Sun, Moon } from 'lucide-react';

export default function Header({ isDark, onToggleTheme }) {
    return (
        <motion.header
            initial={{ y: -20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ duration: 0.4 }}
            style={{
                position: 'sticky',
                top: 0,
                zIndex: 50,
                padding: '22px 24px 12px',
                background: 'rgb(var(--color-surface-alt))',
            }}
        >
            <div
                style={{
                    maxWidth: 1510,
                    margin: '0 auto',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                }}
            >
                {/* Logo / App Name */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <div
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            width: 38,
                            height: 38,
                            borderRadius: 11,
                            background: 'linear-gradient(135deg, rgb(var(--color-primary)), rgb(var(--color-accent)))',
                            color: '#fff',
                        }}
                    >
                        <FileText size={20} />
                    </div>
                    <span
                        style={{
                            fontWeight: 800,
                            fontSize: '1.15rem',
                            letterSpacing: '0',
                            background: 'linear-gradient(135deg, rgb(var(--color-primary)), rgb(var(--color-accent)))',
                            WebkitBackgroundClip: 'text',
                            WebkitTextFillColor: 'transparent',
                            backgroundClip: 'text',
                        }}
                    >
                        Text Detection OCR
                    </span>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <motion.a
                        whileHover={{ scale: 1.08 }}
                        whileTap={{ scale: 0.94 }}
                        href="https://github.com/adhikarilaxman"
                        target="_blank"
                        rel="noopener noreferrer"
                        aria-label="Open GitHub profile"
                        title="GitHub"
                        className="header-icon-button"
                    >
                        <Github size={19} />
                    </motion.a>

                    <motion.button
                        whileHover={{ scale: 1.08 }}
                        whileTap={{ scale: 0.94 }}
                        onClick={onToggleTheme}
                        aria-label="Toggle dark mode"
                        title="Toggle theme"
                        className="header-icon-button"
                    >
                        {isDark ? <Sun size={19} /> : <Moon size={19} />}
                    </motion.button>
                </div>
            </div>
        </motion.header>
    );
}
