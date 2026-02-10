import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Landing from './pages/Landing'
import WorkshopDashboard from './pages/WorkshopDashboard'
import WorkshopConfig from './pages/WorkshopConfig'
import TutorialDashboard from './pages/TutorialDashboard'
import Login from './pages/Login'
import { AuthProvider, useAuth } from './services/auth'

function ProtectedRoute({ children }) {
  const { isAuthenticated, isLoading } = useAuth()
  
  if (isLoading) {
    return <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
      <div>Loading...</div>
    </div>
  }
  
  return isAuthenticated ? children : <Navigate to="/login" replace />
}

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/ui" element={<Navigate to="/" replace />} />
          <Route path="/" element={<ProtectedRoute><Landing /></ProtectedRoute>} />
          <Route path="/workshop/:name" element={<ProtectedRoute><WorkshopDashboard /></ProtectedRoute>} />
          <Route path="/workshop/:name/config" element={<ProtectedRoute><WorkshopConfig /></ProtectedRoute>} />
          <Route path="/tutorial/:workshop/:sessionId" element={<ProtectedRoute><TutorialDashboard /></ProtectedRoute>} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}

export default App
