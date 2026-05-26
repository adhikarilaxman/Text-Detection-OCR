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
                <motion.div
                    whileHover="hover"
                    onClick={() => window.location.reload()}
                    style={{ display: 'flex', alignItems: 'center', gap: 12, cursor: 'pointer', userSelect: 'none' }}
                >
                    <div style={{ position: 'relative', width: 38, height: 38 }}>
                        <motion.div
                            animate={{
                                y: [0, -3, 0],
                            }}
                            transition={{
                                repeat: Infinity,
                                duration: 3,
                                ease: "easeInOut"
                            }}
                            style={{ width: '100%', height: '100%' }}
                        >
                            <motion.div
                                variants={{
                                    hover: {
                                        scale: 1.12,
                                        rotate: [0, -10, 15, -10, 5, 0],
                                        boxShadow: '0 6px 14px rgba(var(--color-primary), 0.35)',
                                    }
                                }}
                                transition={{ duration: 0.5, ease: "easeInOut" }}
                                style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    width: 38,
                                    height: 38,
                                    borderRadius: 11,
                                    background: 'linear-gradient(135deg, rgb(var(--color-primary)), rgb(var(--color-accent)))',
                                    color: '#fff',
                                    boxShadow: '0 4px 8px rgba(var(--color-primary), 0.15)',
                                }}
                            >
                                <FileText size={20} />
                            </motion.div>
                        </motion.div>
                    </div>
                    <motion.span
                        variants={{
                            hover: {
                                scale: 1.03,
                                transition: { duration: 0.3, type: "spring", stiffness: 300, damping: 15 }
                            }
                        }}
                        className="animated-logo-text"
                    >
                        Text Detection OCR
                    </motion.span>
                </motion.div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <motion.a
                        whileHover={{ scale: 1.08 }}
                        whileTap={{ scale: 0.94 }}
                        href="https://github.com/adhikarilaxman/Text-Detection-OCR.git"
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
