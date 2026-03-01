/**
 * Alert Component - Info, warning, error messages
 */

import React from 'react';
import { motion } from 'framer-motion';

interface AlertProps {
  children: React.ReactNode;
  variant?: 'info' | 'warning' | 'error' | 'success';
  title?: string;
  onClose?: () => void;
  className?: string;
}

export const Alert: React.FC<AlertProps> = ({
  children,
  variant = 'info',
  title,
  onClose,
  className = '',
}) => {
  const variantClasses = {
    info: 'bg-blue-600/20 border border-blue-600 text-blue-600',
    warning: 'bg-yellow-600/20 border border-yellow-600 text-yellow-600',
    error: 'bg-red-600/20 border border-red-600 text-red-600',
    success: 'bg-green-600/20 border border-green-600 text-green-600',
  };

  const iconMap = {
    info: 'ℹ️',
    warning: '⚠️',
    error: '❌',
    success: '✅',
  };

  return (
    <motion.div
      className={`rounded-lg p-4 ${variantClasses[variant]} ${className}`}
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.3 }}
    >
      <div className="flex items-start gap-3">
        <span className="text-xl flex-shrink-0">{iconMap[variant]}</span>
        <div className="flex-1">
          {title && <h4 className="font-semibold mb-1">{title}</h4>}
          <div className="text-sm">{children}</div>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="flex-shrink-0 text-lg hover:opacity-70 transition-opacity"
          >
            ✕
          </button>
        )}
      </div>
    </motion.div>
  );
};

Alert.displayName = 'Alert';
