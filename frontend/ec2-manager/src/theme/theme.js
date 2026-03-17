import { createTheme } from '@mui/material/styles'

const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#4f46e5'
    },
    secondary: {
      main: '#0ea5e9'
    },
    success: {
      main: '#16a34a'
    },
    warning: {
      main: '#f59e0b'
    },
    error: {
      main: '#dc2626'
    },
    background: {
      default: '#f8fafc',
      paper: '#ffffff'
    }
  },
  shape: {
    borderRadius: 12
  },
  typography: {
    fontFamily: [
      'Inter',
      'system-ui',
      '-apple-system',
      'Segoe UI',
      'Roboto',
      'sans-serif'
    ].join(',')
  },
  components: {
    MuiCard: {
      styleOverrides: {
        root: {
          border: '1px solid #e2e8f0',
          boxShadow: '0 8px 20px rgba(15, 23, 42, 0.06)',
          transition: 'transform 180ms ease, box-shadow 180ms ease',
          '&:hover': {
            transform: 'translateY(-1px)',
            boxShadow: '0 14px 26px rgba(15, 23, 42, 0.10)'
          }
        }
      }
    },
    MuiButton: {
      defaultProps: {
        disableElevation: true
      },
      styleOverrides: {
        root: {
          transition: 'transform 140ms ease, background-color 140ms ease',
          '&:active': {
            transform: 'translateY(1px)'
          }
        }
      }
    },
    MuiTableRow: {
      styleOverrides: {
        root: {
          transition: 'background-color 120ms ease'
        }
      }
    }
  }
})

export default theme
