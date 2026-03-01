/**
 * Design Tokens - LOTR-themed color palette, typography, and spacing system
 * Used throughout the app for consistency and maintainability
 */

export const Colors = {
  // Primary Palette - Parchment & Earth
  parchment: {
    light: '#F4E4BC',
    default: '#E8D5B7',
    dark: '#D4C0A4',
  },

  // Secondary Palette - Forest & Nature
  forest: {
    light: '#3D6B1F',
    default: '#2D5016',
    dark: '#1F3A0E',
  },

  // Accent Palette - Gold & Metal
  gold: {
    light: '#FFD700',
    default: '#DAA520',
    dark: '#B8860B',
  },

  // Status Colors - Quest States
  status: {
    ready: '#10B981',      // It is Done - Green
    inProgress: '#F59E0B', // The Road Goes Ever On - Amber
    blocked: '#EF4444',    // The Shadow Falls - Red
    pending: '#8B7355',    // Not Yet Begun - Brown
  },

  // Priority Colors
  priority: {
    critical: '#DC2626',    // Crimson Red
    important: '#EA580C',   // Deep Orange
    standard: '#7C3AED',    // Indigo
  },

  // Background & Text
  text: {
    primary: '#1A1F2E',     // Deep Dark Blue
    secondary: '#4B5563',   // Cool Gray
    light: '#E8E8E8',       // Off White
  },

  // Background
  background: {
    primary: '#0F1117',     // Deep Night
    secondary: '#1C1F26',   // Charcoal
    tertiary: '#2D333B',    // Dark Gray
  },

  // Dark Magic Theme
  darkMagic: {
    glow: '#C7254E',        // Wine Red
    shadow: '#08090C',      // Deepest Black
    effect: 'rgba(199, 37, 78, 0.3)',
  },

  // Utility
  border: '#3D3D3D',
  error: '#EF4444',
  warning: '#F59E0B',
  success: '#10B981',
  info: '#3B82F6',
};

export const Typography = {
  fonts: {
    epic: 'Cinzel, serif',           // Headings - uppercase, bold
    readable: 'Lora, serif',         // Body text - elegant readability
    system: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  },

  // Heading styles
  sizes: {
    h1: { fontSize: '3.5rem', fontWeight: 700, lineHeight: 1.1 },
    h2: { fontSize: '2.8rem', fontWeight: 700, lineHeight: 1.2 },
    h3: { fontSize: '2rem', fontWeight: 600, lineHeight: 1.3 },
    h4: { fontSize: '1.5rem', fontWeight: 600, lineHeight: 1.4 },
    body: { fontSize: '1rem', fontWeight: 400, lineHeight: 1.6 },
    small: { fontSize: '0.875rem', fontWeight: 400, lineHeight: 1.5 },
    caption: { fontSize: '0.75rem', fontWeight: 500, lineHeight: 1.4 },
  },
};

export const Spacing = {
  xs: '0.25rem',    // 4px
  sm: '0.5rem',     // 8px
  md: '1rem',       // 16px
  lg: '1.5rem',     // 24px
  xl: '2rem',       // 32px
  xxl: '3rem',      // 48px
  xxxl: '4rem',     // 64px
};

export const BorderRadius = {
  sm: '0.25rem',
  md: '0.5rem',
  lg: '1rem',
  xl: '1.5rem',
  full: '9999px',
};

export const Shadows = {
  sm: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
  md: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
  lg: '0 10px 15px -3px rgba(0, 0, 0, 0.1)',
  xl: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
  epic: '0 20px 40px -10px rgba(199, 37, 78, 0.3)',    // Dark Magic glow
  gold: '0 0 20px rgba(218, 165, 32, 0.5)',            // Gold glow
};

export const Animations = {
  durations: {
    fast: '150ms',
    base: '300ms',
    slow: '500ms',
    epic: '1000ms',
  },
  timings: {
    ease: 'ease',
    easeIn: 'ease-in',
    easeOut: 'ease-out',
    easeInOut: 'ease-in-out',
  },
};

export const ZIndex = {
  base: 0,
  dropdown: 10,
  sticky: 20,
  fixed: 30,
  modal: 40,
  tooltip: 50,
  notification: 60,
};

/** Get CSS variables string for theme switching */
export const getCSSVariables = () => ({
  '--color-parchment-light': Colors.parchment.light,
  '--color-parchment-default': Colors.parchment.default,
  '--color-parchment-dark': Colors.parchment.dark,
  '--color-forest-light': Colors.forest.light,
  '--color-forest-default': Colors.forest.default,
  '--color-forest-dark': Colors.forest.dark,
  '--color-gold-light': Colors.gold.light,
  '--color-gold-default': Colors.gold.default,
  '--color-gold-dark': Colors.gold.dark,
  '--color-text-primary': Colors.text.primary,
  '--color-text-secondary': Colors.text.secondary,
  '--color-bg-primary': Colors.background.primary,
});
