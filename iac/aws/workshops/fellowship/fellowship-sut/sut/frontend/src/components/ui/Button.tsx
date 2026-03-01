/**
 * Button Component - Epic button with Tailwind styling
 * Supports multiple variants: epic, secondary, danger
 */

import React from 'react';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'epic' | 'secondary' | 'danger' | 'small';
  children: React.ReactNode;
  isLoading?: boolean;
  icon?: React.ReactNode;
  disabled?: boolean;
  className?: string;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = 'epic',
      children,
      isLoading = false,
      icon,
      disabled,
      className = '',
      ...props
    },
    ref
  ) => {
    const variantClasses = {
      epic: 'px-6 py-3 bg-gold text-text-primary font-epic rounded-lg hover:bg-gold-light shadow-lg hover:shadow-gold transition-all duration-300 hover:scale-105 active:scale-95',
      secondary:
        'px-6 py-3 bg-forest text-parchment-light font-medium rounded-lg hover:bg-forest-light shadow-md hover:shadow-lg transition-all duration-300',
      danger:
        'px-6 py-3 bg-red-600 text-white font-medium rounded-lg hover:bg-red-700 shadow-md hover:shadow-lg transition-all duration-300',
      small:
        'px-3 py-1 text-sm font-medium rounded transition-all duration-300 bg-gold hover:bg-gold-light text-text-primary',
    };

    const disabledClass = disabled || isLoading ? 'opacity-50 cursor-not-allowed' : '';

    return (
      <button
        ref={ref}
        className={`${variantClasses[variant]} ${disabledClass} ${className} font-medium cursor-pointer flex items-center gap-2 justify-center`}
        disabled={disabled || isLoading}
        {...props}
      >
        {isLoading && <span className="animate-spin">⏳</span>}
        {icon && <span>{icon}</span>}
        {children}
      </button>
    );
  }
);

Button.displayName = 'Button';
