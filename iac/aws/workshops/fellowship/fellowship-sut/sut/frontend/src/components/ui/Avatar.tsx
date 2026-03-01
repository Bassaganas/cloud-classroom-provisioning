/**
 * Avatar Component - Display character/member avatars
 */

import React from 'react';

interface AvatarProps {
  initials?: string;
  emoji?: string;
  name?: string;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
}

const sizeClasses = {
  sm: 'w-8 h-8 text-xs',
  md: 'w-10 h-10 text-sm',
  lg: 'w-12 h-12 text-base',
  xl: 'w-16 h-16 text-lg',
};

export const Avatar: React.FC<AvatarProps> = ({
  initials,
  emoji,
  name,
  size = 'md',
  className = '',
}) => {
  const content = emoji || initials?.substring(0, 2).toUpperCase() || '?';

  return (
    <div
      className={`${sizeClasses[size]} rounded-full bg-gradient-to-br from-gold to-gold-light text-text-primary font-semibold flex items-center justify-center shadow-md border-2 border-parchment-light ${className}`}
      title={name}
    >
      {content}
    </div>
  );
};

Avatar.displayName = 'Avatar';
