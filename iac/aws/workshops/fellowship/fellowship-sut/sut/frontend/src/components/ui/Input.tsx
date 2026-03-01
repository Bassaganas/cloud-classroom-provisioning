/**
 * Input Components - Text, textarea, select inputs with Tailwind styling
 */

import React from 'react';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  hint?: string;
  className?: string;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, hint, className = '', ...props }, ref) => {
    const baseClasses =
      'w-full px-4 py-2 bg-background-tertiary border border-gold-dark/50 rounded-lg text-parchment-light focus:outline-none focus:border-gold focus:ring-2 focus:ring-gold/20 transition-all duration-300 placeholder-text-secondary';

    const errorClasses = error ? 'border-red-600 focus:border-red-600 focus:ring-red-600/20' : '';

    return (
      <div className="w-full">
        {label && <label className="block text-sm font-semibold text-parchment-light mb-2">{label}</label>}
        <input ref={ref} className={`${baseClasses} ${errorClasses} ${className}`} {...props} />
        {error && <p className="text-red-600 text-xs mt-1">{error}</p>}
        {hint && <p className="text-text-secondary text-xs mt-1">{hint}</p>}
      </div>
    );
  }
);

Input.displayName = 'Input';

/**
 * Textarea Component
 */
interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
  hint?: string;
  className?: string;
}

export const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ label, error, hint, className = '', rows = 4, ...props }, ref) => {
    const baseClasses =
      'w-full px-4 py-2 bg-background-tertiary border border-gold-dark/50 rounded-lg text-parchment-light focus:outline-none focus:border-gold focus:ring-2 focus:ring-gold/20 transition-all duration-300 placeholder-text-secondary resize-vertical';

    const errorClasses = error ? 'border-red-600 focus:border-red-600 focus:ring-red-600/20' : '';

    return (
      <div className="w-full">
        {label && <label className="block text-sm font-semibold text-parchment-light mb-2">{label}</label>}
        <textarea
          ref={ref}
          rows={rows}
          className={`${baseClasses} ${errorClasses} ${className}`}
          {...props}
        />
        {error && <p className="text-red-600 text-xs mt-1">{error}</p>}
        {hint && <p className="text-text-secondary text-xs mt-1">{hint}</p>}
      </div>
    );
  }
);

Textarea.displayName = 'Textarea';

/**
 * Select Component
 */
interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
  hint?: string;
  options: { value: string; label: string }[];
  className?: string;
}

export const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  ({ label, error, hint, options, className = '', ...props }, ref) => {
    const baseClasses =
      'w-full px-4 py-2 bg-background-tertiary border border-gold-dark/50 rounded-lg text-parchment-light focus:outline-none focus:border-gold focus:ring-2 focus:ring-gold/20 transition-all duration-300 appearance-none cursor-pointer';

    const errorClasses = error ? 'border-red-600 focus:border-red-600 focus:ring-red-600/20' : '';

    return (
      <div className="w-full">
        {label && <label className="block text-sm font-semibold text-parchment-light mb-2">{label}</label>}
        <div className="relative">
          <select
            ref={ref}
            className={`${baseClasses} ${errorClasses} ${className}`}
            {...props}
          >
            <option value="">Select an option...</option>
            {options.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <span className="absolute right-3 top-3 text-parchment-light pointer-events-none">▼</span>
        </div>
        {error && <p className="text-red-600 text-xs mt-1">{error}</p>}
        {hint && <p className="text-text-secondary text-xs mt-1">{hint}</p>}
      </div>
    );
  }
);

Select.displayName = 'Select';
