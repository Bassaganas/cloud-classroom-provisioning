import { useState } from 'react'
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  Stack,
  TextField,
  Typography
} from '@mui/material'
import { api } from '../services/api'

function TutorialSessionForm({ workshopName, onClose, onSuccess }) {
  const [formData, setFormData] = useState({
    session_id: '',
    pool_count: 1,
    admin_count: 0,
    admin_cleanup_days: 7,
    productive_tutorial: false,
    spot_max_price: '',
  })
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    
    if (!formData.session_id.trim()) {
      setError('Session ID is required')
      return
    }

    if (formData.pool_count < 0 || formData.admin_count < 0) {
      setError('Counts must be non-negative')
      return
    }

    if (formData.pool_count === 0 && formData.admin_count === 0) {
      setError('At least one pool or admin instance must be created')
      return
    }

    try {
      setSubmitting(true)
      const response = await api.createTutorialSession({
        session_id: formData.session_id.trim(),
        workshop_name: workshopName,
        pool_count: parseInt(formData.pool_count),
        admin_count: parseInt(formData.admin_count),
        admin_cleanup_days: parseInt(formData.admin_cleanup_days),
        productive_tutorial: formData.productive_tutorial,
        spot_max_price: formData.productive_tutorial || !formData.spot_max_price ? null : formData.spot_max_price,
      })

      if (response.success) {
        onSuccess && onSuccess(response.session)
        onClose()
      } else {
        setError(response.error || 'Failed to create tutorial session')
      }
    } catch (err) {
      setError(err.message || 'Failed to create tutorial session')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>Start New Tutorial Session</DialogTitle>
      <Box component="form" onSubmit={handleSubmit}>
        <DialogContent>
          <Stack spacing={2}>
            <TextField
              id="session_id"
              label="Session ID"
              value={formData.session_id}
              onChange={(e) => setFormData({ ...formData, session_id: e.target.value })}
              placeholder="e.g., tutorial_001"
              helperText="Unique identifier for this tutorial session"
              required
              disabled={submitting}
              fullWidth
            />

            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
              <TextField
                id="pool_count"
                label="Pool Instances"
                type="number"
                inputProps={{ min: 0, max: 120 }}
                value={formData.pool_count}
                onChange={(e) => setFormData({ ...formData, pool_count: e.target.value })}
                helperText="Number of pool instances (0-120)"
                required
                disabled={submitting}
                fullWidth
              />

              <TextField
                id="admin_count"
                label="Admin Instances"
                type="number"
                inputProps={{ min: 0, max: 120 }}
                value={formData.admin_count}
                onChange={(e) => setFormData({ ...formData, admin_count: e.target.value })}
                helperText="Number of admin instances (0-120)"
                required
                disabled={submitting}
                fullWidth
              />
            </Stack>

            <FormControlLabel
              control={
                <Checkbox
                  checked={formData.productive_tutorial}
                  onChange={(e) => setFormData({ ...formData, productive_tutorial: e.target.checked })}
                  disabled={submitting}
                />
              }
              label="Productive tutorial (use On-Demand only)"
            />

            <Alert severity={formData.productive_tutorial ? 'info' : 'warning'}>
              {formData.productive_tutorial
                ? 'Productive tutorial: all instances in this tutorial will be created as On-Demand.'
                : 'Test tutorial: all instances in this tutorial will be created as Spot.'}
            </Alert>

            {!formData.productive_tutorial && (
              <TextField
                id="spot_max_price"
                label="Spot Max Price ($/hour, optional)"
                type="number"
                inputProps={{ min: 0.0001, step: 0.0001 }}
                value={formData.spot_max_price}
                onChange={(e) => setFormData({ ...formData, spot_max_price: e.target.value })}
                helperText="Leave empty to use market Spot price. Example: 0.011"
                disabled={submitting}
                fullWidth
              />
            )}

            {formData.admin_count > 0 && (
              <TextField
                id="admin_cleanup_days"
                label="Admin Cleanup Days"
                type="number"
                inputProps={{ min: 1, max: 365 }}
                value={formData.admin_cleanup_days}
                onChange={(e) => setFormData({ ...formData, admin_cleanup_days: e.target.value })}
                helperText="Days before admin instances are deleted"
                required
                disabled={submitting}
              />
            )}

            {error && <Alert severity="error">{error}</Alert>}

            <Typography variant="caption" color="text.secondary">
              Keyboard tip: press Enter to create the session.
            </Typography>
          </Stack>
        </DialogContent>

        <DialogActions>
          <Button type="button" onClick={onClose} disabled={submitting}>Cancel</Button>
          <Button type="submit" variant="contained" disabled={submitting}>
            {submitting ? 'Creating...' : 'Create Session'}
          </Button>
        </DialogActions>
      </Box>
    </Dialog>
  )
}

export default TutorialSessionForm
