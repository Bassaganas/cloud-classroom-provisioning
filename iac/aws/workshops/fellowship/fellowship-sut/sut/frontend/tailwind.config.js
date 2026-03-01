/** @type {import('tailwindcss').Config} */

module.exports = {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        // Parchment palette
        parchment: {
          light: '#F4E4BC',
          DEFAULT: '#E8D5B7',
          dark: '#D4C0A4',
        },
        // Forest palette
        forest: {
          light: '#3D6B1F',
          DEFAULT: '#2D5016',
          dark: '#1F3A0E',
        },
        // Gold palette
        gold: {
          light: '#FFD700',
          DEFAULT: '#DAA520',
          dark: '#B8860B',
        },
        // Status colors
        ready: '#10B981',
        'in-progress': '#F59E0B',
        blocked: '#EF4444',
        pending: '#8B7355',
        // Dark magic
        'dark-magic': '#C7254E',
        text: {
          primary: '#1A1F2E',
          secondary: '#4B5563',
          light: '#E8E8E8',
        },
        background: {
          primary: '#F4E4BC',
          secondary: '#E8D5B7',
          tertiary: '#D4C0A4',
        },
      },
      fontFamily: {
        epic: ['Cinzel', 'serif'],
        readable: ['Lora', 'serif'],
        system: ['-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
      fontSize: {
        epic: ['3.5rem', { lineHeight: '1.1', fontWeight: '700' }],
        '2xl': ['2.8rem', { lineHeight: '1.2', fontWeight: '700' }],
        '3xl': ['2rem', { lineHeight: '1.3', fontWeight: '600' }],
      },
      spacing: {
        xs: '0.25rem',
        sm: '0.5rem',
        md: '1rem',
        lg: '1.5rem',
        xl: '2rem',
        xxl: '3rem',
        xxxl: '4rem',
      },
      borderRadius: {
        sm: '0.25rem',
        md: '0.5rem',
        lg: '1rem',
        xl: '1.5rem',
        full: '9999px',
      },
      boxShadow: {
        epic: '0 20px 40px -10px rgba(199, 37, 78, 0.3)',
        gold: '0 0 20px rgba(218, 165, 32, 0.5)',
      },
      animation: {
        fadeIn: 'fadeIn 300ms ease-in',
        slideInUp: 'slideInUp 500ms ease-out',
        scaleIn: 'scaleIn 400ms ease-out',
        pulse: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        bounce: 'bounce 1s infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideInUp: {
          '0%': { transform: 'translateY(30px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        scaleIn: {
          '0%': { transform: 'scale(0.95)', opacity: '0' },
          '100%': { transform: 'scale(1)', opacity: '1' },
        },
      },
    },
  },
  plugins: [],
};
