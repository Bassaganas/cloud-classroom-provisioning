/**
 * Badge Component - Status indicators, priorities, and labels
 */

import React from 'react';

interface BadgeProps {
  children: React.ReactNode;
  variant?: 'ready' | 'inprogress' | 'blocked' | 'pending' | 'critical' | 'important' | 'standard';
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({ children, variant = 'standard', className = '' }) => {
  const variantClasses = {
    ready: 'bg-ready/20 text-ready',
    inprogress: 'bg-in-progress/20 text-in-progress',
    blocked: 'bg-blocked/20 text-blocked',
    pending: 'bg-pending/20 text-pending',
    critical: 'bg-red-600/20 text-red-600',
    important: 'bg-orange-600/20 text-orange-600',
    standard: 'bg-indigo-600/20 text-indigo-600',
  };

  return (
    <span
      className={`inline-block px-3 py-1 rounded-full text-xs font-semibold ${variantClasses[variant]} ${className}`}
    >
      {children}
    </span>
  );
};

Badge.displayName = 'Badge';

/**
 * Status Badge - Maps quest status to badge variant
 */
interface StatusBadgeProps {
  status: string;
  className?: string;
}

const statusMap: Record<string, { variant: BadgeProps['variant']; label: string }> = {
  'it_is_done': { variant: 'ready', label: 'It Is Done' },
  'the_road_goes_ever_on': { variant: 'inprogress', label: 'The Road Goes Ever On' },
  'the_shadow_falls': { variant: 'blocked', label: 'The Shadow Falls' },
  'not_yet_begun': { variant: 'pending', label: 'Not Yet Begun' },
};

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, className = '' }) => {
  const { variant, label } = statusMap[status] || { variant: 'pending', label: status };

  return (
    <Badge variant={variant} className={className}>
      {label}
    </Badge>
  );
};

StatusBadge.displayName = 'StatusBadge';

/**
 * Priority Badge - Maps priority to colored badge
 */
interface PriorityBadgeProps {
  priority: string;
  className?: string;
}

const priorityMap: Record<string, { variant: BadgeProps['variant']; emoji: string }> = {
  Critical: { variant: 'critical', emoji: '🔴' },
  Important: { variant: 'important', emoji: '🟠' },
  Standard: { variant: 'standard', emoji: '🟣' },
};

export const PriorityBadge: React.FC<PriorityBadgeProps> = ({ priority, className = '' }) => {
  const { variant, emoji } = priorityMap[priority] || { variant: 'standard', emoji: '⚪' };

  return (
    <Badge variant={variant} className={className}>
      <span className="mr-1">{emoji}</span>
      {priority}
    </Badge>
  );
};

PriorityBadge.displayName = 'PriorityBadge';
