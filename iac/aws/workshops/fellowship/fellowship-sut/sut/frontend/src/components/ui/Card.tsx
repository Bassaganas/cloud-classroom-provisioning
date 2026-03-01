/**
 * Card Component - Parchment-styled container with variants
 */

import React from 'react';
import { motion } from 'framer-motion';

interface CardProps {
  children: React.ReactNode;
  variant?: 'parchment' | 'dark';
  className?: string;
  hover?: boolean;
  onClick?: () => void;
  testId?: string;
}

export const Card: React.FC<CardProps> = ({
  children,
  variant = 'parchment',
  className = '',
  hover = true,
  onClick,
  testId,
}) => {
  const variantClasses = {
    parchment:
      'bg-gradient-to-br from-parchment-light to-parchment rounded-lg p-4 sm:p-6 shadow-md border border-gold-dark/30',
    dark: 'bg-gradient-to-br from-forest to-forest-dark text-parchment-light rounded-lg p-4 sm:p-6 shadow-lg border border-gold-dark/40',
  };

  const hoverClass = hover
    ? 'hover:shadow-lg transition-shadow duration-300 cursor-pointer'
    : 'transition-all duration-300';

  return (
    <motion.div
      className={`${variantClasses[variant]} ${hoverClass} ${className}`}
      data-testid={testId}
      onClick={onClick}
      whileHover={hover ? { y: -4 } : {}}
      transition={{ duration: 0.2 }}
    >
      {children}
    </motion.div>
  );
};

Card.displayName = 'Card';
