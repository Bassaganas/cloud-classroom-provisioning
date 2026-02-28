import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Container,
  TextField,
  Typography
} from '@mui/material'
import { useAuth } from '../services/auth'

function Login() {
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const result = await login(password)
      if (result.success) {
        navigate('/')
      } else {
        setError(result.error || 'Invalid password')
      }
    } catch (err) {
      setError(err.message || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        background: 'linear-gradient(135deg, #eef2ff 0%, #f0f9ff 100%)'
      }}
    >
      <Container maxWidth="sm">
        <Card>
          <CardContent sx={{ p: 4 }}>
            <Typography variant="h4" fontWeight={800} gutterBottom>
              EC2 Instance Manager
            </Typography>
            <Typography color="text.secondary" sx={{ mb: 3 }}>
              Enter your access password to continue.
            </Typography>

            <Box component="form" onSubmit={handleSubmit}>
              <TextField
                type="password"
                id="password"
                label="Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoFocus
                fullWidth
                sx={{ mb: 2 }}
              />
              {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
              <Button type="submit" variant="contained" size="large" disabled={loading} fullWidth>
                {loading ? 'Logging in...' : 'Login'}
              </Button>
            </Box>
          </CardContent>
        </Card>
      </Container>
    </Box>
  )
}

export default Login
