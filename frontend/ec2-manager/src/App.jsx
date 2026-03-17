import { Suspense, lazy } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Box, CircularProgress, CssBaseline } from '@mui/material'
import { ThemeProvider } from '@mui/material/styles'
import { AuthProvider, useAuth } from './services/auth'
import theme from './theme/theme'

const Landing = lazy(() => import('./pages/Landing'))
const WorkshopDashboard = lazy(() => import('./pages/WorkshopDashboard'))
const WorkshopConfig = lazy(() => import('./pages/WorkshopConfig'))
const TutorialDashboard = lazy(() => import('./pages/TutorialDashboard'))
const Login = lazy(() => import('./pages/Login'))

function RouteLoader() {
  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center'
      }}
    >
      <CircularProgress />
    </Box>
  )
}

function ProtectedRoute({ children }) {
  const { isAuthenticated, isLoading } = useAuth()
  
  if (isLoading) {
    return (
      <Box
        sx={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center'
        }}
      >
        <CircularProgress />
      </Box>
    )
  }
  
  return isAuthenticated ? children : <Navigate to="/login" replace />
}

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <AuthProvider>
        <BrowserRouter>
          <Suspense fallback={<RouteLoader />}>
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route path="/ui" element={<Navigate to="/" replace />} />
              <Route path="/" element={<ProtectedRoute><Landing /></ProtectedRoute>} />
              <Route path="/workshop/:name" element={<ProtectedRoute><WorkshopDashboard /></ProtectedRoute>} />
              <Route path="/workshop/:name/config" element={<ProtectedRoute><WorkshopConfig /></ProtectedRoute>} />
              <Route path="/tutorial/:workshop/:sessionId" element={<ProtectedRoute><TutorialDashboard /></ProtectedRoute>} />
            </Routes>
          </Suspense>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  )
}

export default App
