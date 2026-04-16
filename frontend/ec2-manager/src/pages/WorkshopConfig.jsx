import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import {
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  Container,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  Link,
  Switch,
  Stack,
  TextField,
  Typography
} from '@mui/material'
import { api } from '../services/api'
import AppToast from '../components/AppToast'
import Header from '../components/Header'

function WorkshopConfig() {
  const { name: workshopName } = useParams()
  const [settings, setSettings] = useState({
    stop_timeout: 4,
    terminate_timeout: 20,
    hard_terminate_timeout: 45,
    admin_cleanup_days: 7,
    shared_core_mode: false,
    shared_jenkins_url: '',
    shared_gitea_url: '',
  })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [toast, setToast] = useState({ open: false, message: '', severity: 'success' })
  const [confirmDialog, setConfirmDialog] = useState({ open: false, resourceType: '' })
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    loadSettings()
  }, [workshopName])

  const loadSettings = async () => {
    try {
      setLoading(true)
      const response = await api.getTimeoutSettings(workshopName)
      if (response.success && response.settings) {
        setSettings((prev) => ({ ...prev, ...response.settings }))
      }

      const sharedCoreResponse = await api.getSharedCoreSettings(workshopName)
      if (sharedCoreResponse.success && sharedCoreResponse.settings) {
        setSettings((prev) => ({ ...prev, ...sharedCoreResponse.settings }))
      }
    } catch (error) {
      showToast(`Error loading settings: ${error.message}`, 'error')
    } finally {
      setLoading(false)
    }
  }

  const saveSettings = async (e) => {
    e.preventDefault()
    try {
      setSaving(true)
      const response = await api.updateTimeoutSettings({
        workshop: workshopName,
        stop_timeout: parseInt(settings.stop_timeout),
        terminate_timeout: parseInt(settings.terminate_timeout),
        hard_terminate_timeout: parseInt(settings.hard_terminate_timeout),
        admin_cleanup_days: parseInt(settings.admin_cleanup_days),
      })

      const sharedCoreResponse = await api.updateSharedCoreSettings({
        workshop: workshopName,
        shared_core_mode: Boolean(settings.shared_core_mode),
      })

      if (response.success && sharedCoreResponse.success) {
        showToast(`Settings saved for ${workshopName}`, 'success')
      } else {
        showToast(response.error || sharedCoreResponse.error || 'Failed to save settings', 'error')
      }
    } catch (error) {
      showToast(error.message, 'error')
    } finally {
      setSaving(false)
    }
  }

  const showToast = (message, severity = 'success') => {
    setToast({ open: true, message, severity })
  }

  const handleDeleteSharedCoreResources = async () => {
    const { resourceType } = confirmDialog
    setConfirmDialog({ open: false, resourceType: '' })
    setDeleting(true)
    try {
      const result = await api.deleteSharedCoreResources(workshopName, resourceType)
      if (result.success) {
        const label = resourceType === 'jenkins_folders' ? 'Jenkins folders' : 'Gitea repos'
        showToast(`Deleted ${result.deleted_count} ${label}`, 'success')
      } else {
        showToast(result.error || 'Deletion failed', 'error')
      }
    } catch (error) {
      showToast(error.message, 'error')
    } finally {
      setDeleting(false)
    }
  }

  if (loading) {
    return (
      <Box sx={{ minHeight: '70vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <CircularProgress />
      </Box>
    )
  }

  return (
    <>
      <Header 
        title="Workshop Configuration"
        subtitle={`Workshop: ${workshopName}`}
        showBack={true}
        backPath="/"
        showSettings={false}
      />

      <Container maxWidth="md" sx={{ py: 3 }}>
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>Workshop Timeout Settings</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Configure defaults used when creating instances without custom timeout values.
            </Typography>

            <Box component="form" onSubmit={saveSettings}>
              <Stack spacing={2}>
                <TextField
                  type="number"
                  label="Stop Timeout (minutes)"
                  inputProps={{ min: 1, max: 1440 }}
                  value={settings.stop_timeout}
                  onChange={(e) => setSettings({ ...settings, stop_timeout: e.target.value })}
                  helperText="Before stopping unassigned running instances"
                  required
                />

                <TextField
                  type="number"
                  label="Terminate Timeout (minutes)"
                  inputProps={{ min: 1, max: 1440 }}
                  value={settings.terminate_timeout}
                  onChange={(e) => setSettings({ ...settings, terminate_timeout: e.target.value })}
                  helperText="Before terminating stopped instances"
                  required
                />

                <TextField
                  type="number"
                  label="Hard Terminate Timeout (minutes)"
                  inputProps={{ min: 1, max: 10080 }}
                  value={settings.hard_terminate_timeout}
                  onChange={(e) => setSettings({ ...settings, hard_terminate_timeout: e.target.value })}
                  helperText="Before hard terminating any instance"
                  required
                />

                <TextField
                  type="number"
                  label="Admin Cleanup Days"
                  inputProps={{ min: 1, max: 365 }}
                  value={settings.admin_cleanup_days}
                  onChange={(e) => setSettings({ ...settings, admin_cleanup_days: e.target.value })}
                  helperText="Days before admin instances are deleted"
                  required
                />

                <Box sx={{ p: 2, border: '1px solid', borderColor: 'divider', borderRadius: 1 }}>
                  <Typography variant="subtitle1" sx={{ mb: 1 }}>
                    Infrastructure Mode
                  </Typography>
                  <FormControlLabel
                    control={
                      <Switch
                        checked={Boolean(settings.shared_core_mode)}
                        onChange={(e) => setSettings({ ...settings, shared_core_mode: e.target.checked })}
                      />
                    }
                    label="Use shared-core mode for student assignments"
                  />
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                    When enabled, students are routed to shared Jenkins and Gitea instead of per-student DevOps stacks.
                  </Typography>
                  {settings.shared_core_mode && (
                    <Box sx={{ mt: 1.5 }}>
                      <Typography variant="body2" color="text.secondary">
                        Jenkins:{' '}
                        {settings.shared_jenkins_url
                          ? <Link href={settings.shared_jenkins_url} target="_blank" rel="noopener noreferrer">{settings.shared_jenkins_url}</Link>
                          : 'Not configured'}
                      </Typography>
                      <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                        Gitea:{' '}
                        {settings.shared_gitea_url
                          ? <Link href={settings.shared_gitea_url} target="_blank" rel="noopener noreferrer">{settings.shared_gitea_url}</Link>
                          : 'Not configured'}
                      </Typography>
                      <Stack direction="row" spacing={1} sx={{ mt: 1.5 }}>
                        <Button
                          size="small"
                          color="error"
                          variant="outlined"
                          disabled={deleting}
                          onClick={() => setConfirmDialog({ open: true, resourceType: 'jenkins_folders' })}
                        >
                          Delete All Jenkins Folders
                        </Button>
                        <Button
                          size="small"
                          color="error"
                          variant="outlined"
                          disabled={deleting}
                          onClick={() => setConfirmDialog({ open: true, resourceType: 'gitea_repos' })}
                        >
                          Delete All Gitea Repos
                        </Button>
                      </Stack>
                    </Box>
                  )}
                </Box>

                <Stack direction="row" spacing={1.5}>
                  <Button type="submit" variant="contained" disabled={saving}>
                    {saving ? 'Saving...' : 'Save Defaults'}
                  </Button>
                  <Button type="button" variant="outlined" onClick={loadSettings}>
                    Load Current
                  </Button>
                </Stack>
              </Stack>
            </Box>
          </CardContent>
        </Card>
      </Container>
      <AppToast
        toast={toast}
        onClose={() => setToast((prev) => ({ ...prev, open: false }))}
      />
      <Dialog open={confirmDialog.open} onClose={() => setConfirmDialog({ open: false, resourceType: '' })}>
        <DialogTitle>
          {confirmDialog.resourceType === 'jenkins_folders' ? 'Delete All Jenkins Folders' : 'Delete All Gitea Repos'}
        </DialogTitle>
        <DialogContent>
          <Typography>
            This will permanently delete{' '}
            {confirmDialog.resourceType === 'jenkins_folders'
              ? 'all top-level Jenkins folders and their pipelines'
              : 'all Gitea repositories in the shared organisation'}{' '}
            for workshop <strong>{workshopName}</strong>. This action cannot be undone.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmDialog({ open: false, resourceType: '' })}>Cancel</Button>
          <Button color="error" variant="contained" onClick={handleDeleteSharedCoreResources}>
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </>
  )
}

export default WorkshopConfig
