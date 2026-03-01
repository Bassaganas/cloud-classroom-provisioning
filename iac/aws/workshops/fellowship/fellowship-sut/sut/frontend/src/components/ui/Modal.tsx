/**
 * Modal Component - Dialog overlay for forms and content
 */

import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
  size?: 'sm' | 'md' | 'lg' | 'full';
  footer?: React.ReactNode;
  className?: string;
}

export const Modal: React.FC<ModalProps> = ({
  isOpen,
  onClose,
  title,
  children,
  size = 'md',
  footer,
  className = '',
}) => {
  const sizeClasses = {
    sm: 'max-w-sm',
    md: 'max-w-md',
    lg: 'max-w-lg',
    full: 'max-w-4xl',
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            className="fixed inset-0 bg-background-primary/50 backdrop-blur-sm z-40"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            transition={{ duration: 0.2 }}
          />

          <div className="fixed inset-0 z-40 flex items-center justify-center p-4">
            <motion.div
              className={`bg-background-secondary rounded-lg shadow-xl border border-gold-dark/30 ${sizeClasses[size]} ${className}`}
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              transition={{ duration: 0.3 }}
            >
              {/* Header */}
              <div className="flex items-center justify-between p-6 border-b border-gold-dark/20">
                <h2 className="text-2xl font-epic text-parchment-light">{title}</h2>
                <button
                  onClick={onClose}
                  className="text-text-secondary hover:text-parchment-light transition-colors text-2xl"
                >
                  ✕
                </button>
              </div>

              {/* Content */}
              <div className="p-6 text-text-primary max-h-96 overflow-y-auto">{children}</div>

              {/* Footer */}
              {footer && <div className="p-6 border-t border-gold-dark/20">{footer}</div>}
            </motion.div>
          </div>
        </>
      )}
    </AnimatePresence>
  );
};

Modal.displayName = 'Modal';
