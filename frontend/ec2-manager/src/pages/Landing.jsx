import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Alert,
  Box,
  Button,
  Card,
  CardActions,
  CardContent,
  Chip,
  CircularProgress,
  Container,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  Fab,
  Grid,
  IconButton,
  InputAdornment,
  List,
  ListItemButton,
  ListItemText,
  Stack,
  TextField,
  Typography
} from '@mui/material'
import SearchRoundedIcon from '@mui/icons-material/SearchRounded'
import AddRoundedIcon from '@mui/icons-material/AddRounded'
import SettingsRoundedIcon from '@mui/icons-material/SettingsRounded'
import DeleteOutlineRoundedIcon from '@mui/icons-material/DeleteOutlineRounded'
import OpenInNewRoundedIcon from '@mui/icons-material/OpenInNewRounded'
import ScienceRoundedIcon from '@mui/icons-material/ScienceRounded'
import CheckCircleRoundedIcon from '@mui/icons-material/CheckCircleRounded'
import { api } from '../services/api'
import { alwaysOnLinks } from '../config/alwaysOnLinks'
import OpenInBrowserRoundedIcon from '@mui/icons-material/OpenInBrowserRounded'
import AppToast from '../components/AppToast'
import TutorialSessionForm from './TutorialSessionForm'
import Header from '../components/Header'

function Landing() {
  const [workshops, setWorkshops] = useState([])
  const [tutorialSessions, setTutorialSessions] = useState({}) // { workshopName: [sessions] }
  // Remove alwaysOnTutorials state, use alwaysOnLinks config
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showSessionForm, setShowSessionForm] = useState(null) // workshopName or null
  const [deletingSession, setDeletingSession] = useState(null) // { workshopName, sessionId }
  const [deleteConfirmData, setDeleteConfirmData] = useState(null) // { workshopName, sessionId, instanceCount }
  const [search, setSearch] = useState('')
  const [toast, setToast] = useState({ open: false, message: '', severity: 'success' })
  const [showWorkshopSelector, setShowWorkshopSelector] = useState(false)
  const [selectedWorkshopForSession, setSelectedWorkshopForSession] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    loadWorkshops()
  }, [])

  // Removed loadAlwaysOnTutorials, alwaysOnLinks is static/local for now

  useEffect(() => {
    // Load tutorial sessions for each workshop
    if (workshops.length > 0) {
      workshops.forEach(workshop => {
        loadTutorialSessions(workshop.name)
      })
    }
  }, [workshops])

  const loadWorkshops = async () => {
    try {
      setLoading(true)
      const response = await api.getWorkshopTemplates()
      if (response.success && response.templates) {
        const workshopNames = Object.keys(response.templates)
        setWorkshops(workshopNames.map(name => ({
          name,
          ...response.templates[name]
        })))
      }
    } catch (err) {
      setError(err.message || 'Failed to load workshops')
    } finally {
      setLoading(false)
    }
  }

  const loadTutorialSessions = async (workshopName) => {
    try {
      const response = await api.getTutorialSessions(workshopName)
      if (response.success && response.sessions) {
        console.log(`[Landing] Loaded ${response.sessions.length} sessions for ${workshopName}:`, response.sessions)
        setTutorialSessions(prev => ({
          ...prev,
          [workshopName]: response.sessions
        }))
      }
    } catch (err) {
      console.error(`Failed to load tutorial sessions for ${workshopName}:`, err)
    }
  }

  const handleSessionCreated = (workshopName) => {
    loadTutorialSessions(workshopName)
  }

  const handleDeleteSession = async (workshopName, sessionId, instanceCount, deleteInstances) => {
    try {
      setDeletingSession({ workshopName, sessionId })
      const response = await api.deleteTutorialSession(sessionId, workshopName, deleteInstances)
      
      if (response.success) {
        // Reload sessions for this workshop
        await loadTutorialSessions(workshopName)
        setDeleteConfirmData(null)
        setToast({ open: true, message: `Session ${sessionId} deleted`, severity: 'success' })
      } else {
        setToast({ open: true, message: response.error || 'Failed to delete session', severity: 'error' })
      }
    } catch (error) {
      setToast({ open: true, message: error.message || 'Failed to delete session', severity: 'error' })
    } finally {
      setDeletingSession(null)
    }
  }

  const handleDeleteClick = (e, workshopName, sessionId, instanceCount) => {
    e.stopPropagation()
    setDeleteConfirmData({ workshopName, sessionId, instanceCount })
  }

  const filteredWorkshops = useMemo(() => {
    const query = search.trim().toLowerCase()
    if (!query) return workshops

    return workshops.filter((workshop) => {
      const matchesWorkshop = workshop.name.toLowerCase().includes(query)
      const sessions = tutorialSessions[workshop.name] || []
      const matchesSession = sessions.some((session) => session.session_id.toLowerCase().includes(query))
      return matchesWorkshop || matchesSession
    })
  }, [search, tutorialSessions, workshops])

  const totalSessions = useMemo(
    () => Object.values(tutorialSessions).reduce((acc, sessions) => acc + sessions.length, 0),
    [tutorialSessions]
  )

  const totalSessionInstances = useMemo(
    () => Object.values(tutorialSessions).flat().reduce((acc, session) => acc + (session.actual_instance_count || 0), 0),
    [tutorialSessions]
  )

  const totalSessionCosts = useMemo(() => {
    const allSessions = Object.values(tutorialSessions).flat()
    console.log('[Landing] All sessions for cost calculation:', allSessions)
    const total = allSessions.reduce((acc, session) => {
      const sessionCost = session.aggregated_estimated_cost_usd || 0
      console.log(`[Landing] Session ${session.session_id}: cost=${sessionCost}, running_total=${acc + sessionCost}`)
      return acc + sessionCost
    }, 0)
    console.log('[Landing] Total session costs:', total)
    return total
  }, [tutorialSessions])

  const formatUsd = (value, decimals = 2) => {
    if (value === null || value === undefined) return '-'
    const formatted = `$${Number(value).toFixed(decimals)}`
    if (value > 0) {
      console.log(`[Landing] formatUsd(${value}) -> ${formatted}`)
    }
    return formatted
  }

  if (loading) {
    return (
      <Box sx={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <CircularProgress />
      </Box>
    )
  }

  if (error) {
    return (
      <Container maxWidth="lg" sx={{ py: 6 }}>
        <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>
        <Button variant="contained" onClick={loadWorkshops}>Retry</Button>
      </Container>
    )
  }

  return (
    <>
      <Header />
      <Container maxWidth="xl" sx={{ py: 3 }}>
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} sx={{ mb: 3 }}>
          <Card sx={{ flex: 1 }}>
            <CardContent>
              <Typography variant="overline" color="text.secondary">Workshops</Typography>
              <Typography variant="h4" fontWeight={700}>{workshops.length}</Typography>
            </CardContent>
          </Card>
          <Card sx={{ flex: 1 }}>
            <CardContent>
              <Typography variant="overline" color="text.secondary">Tutorial Sessions</Typography>
              <Typography variant="h4" fontWeight={700}>{totalSessions}</Typography>
            </CardContent>
          </Card>
          <Card sx={{ flex: 1 }}>
            <CardContent>
              <Typography variant="overline" color="text.secondary">Tracked Session Instances</Typography>
              <Typography variant="h4" fontWeight={700}>{totalSessionInstances}</Typography>
            </CardContent>
          </Card>
          <Card sx={{ flex: 1 }}>
            <CardContent>
              <Typography variant="overline" color="text.secondary">Session Costs (Est.)</Typography>
              <Typography variant="h4" fontWeight={700}>{formatUsd(totalSessionCosts, 2)}</Typography>
            </CardContent>
          </Card>
        </Stack>

        <TextField
          fullWidth
          placeholder="Search workshops or session IDs"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          sx={{ mb: 3 }}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchRoundedIcon />
              </InputAdornment>
            )
          }}
        />

        <Grid container spacing={2.5}>
          {filteredWorkshops.length === 0 ? (
            <Grid item xs={12}>
              <Card>
                <CardContent>
                  <Typography color="text.secondary">No workshops available for this search.</Typography>
                </CardContent>
              </Card>
            </Grid>
          ) : (
            filteredWorkshops.map((workshop) => {
            const sessions = tutorialSessions[workshop.name] || []
            // Find always-on links for this workshop
            const links = alwaysOnLinks[workshop.name] || [];
            return (
              <Grid item xs={12} md={6} lg={4} key={workshop.name}>
                <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
                  <CardContent sx={{ pb: 1.5 }}>
                    <Stack direction="row" alignItems="center" justifyContent="space-between" spacing={1}>
                      <Box>
                        <Typography variant="h6" fontWeight={700} sx={{ textTransform: 'capitalize' }}>
                          {workshop.name.replaceAll('_', ' ')}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          {sessions.length} active session{sessions.length !== 1 ? 's' : ''}
                        </Typography>
                        {links.length > 0 && (
                          <Box sx={{ mt: 1 }}>
                            <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 0.5 }}>
                              Always-On Environments
                            </Typography>
                            <Stack direction="column" spacing={0.5}>
                              {links.slice(0, 3).map((linkObj, idx) => (
                                <Button
                                  key={idx}
                                  variant="contained"
                                  color="info"
                                  size="small"
                                  href={linkObj.link}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  startIcon={<OpenInBrowserRoundedIcon />}
                                  sx={{ fontWeight: 600, borderRadius: 2, textTransform: 'none', boxShadow: 2 }}
                                >
                                  {linkObj.label}
                                </Button>
                              ))}
                            </Stack>
                          </Box>
                        )}
                      </Box>
                      <Stack direction="row" spacing={1}>
                        <TooltipButton
                          title="Open settings"
                          onClick={() => navigate(`/workshop/${workshop.name}/config`)}
                          icon={<SettingsRoundedIcon fontSize="small" />}
                        />
                      </Stack>
                    </Stack>
                  </CardContent>

                  <Divider />

                  <CardContent sx={{ pt: 2, flexGrow: 1 }}>
                    {sessions.length > 0 ? (
                      <List dense disablePadding>
                        {sessions.map((session) => (
                          <ListItemButton
                            key={session.session_id}
                            sx={{ borderRadius: 2, mb: 1 }}
                            onClick={() => navigate(`/tutorial/${workshop.name}/${session.session_id}`)}
                          >
                            {(() => {
                              const isProductiveTutorial = session?.productive_tutorial === true ||
                                (session?.productive_tutorial === undefined && session?.purchase_type === 'on-demand')

                              return (
                            <ListItemText
                              primary={
                                <Stack direction="row" alignItems="center" spacing={1} sx={{ flexWrap: 'wrap' }}>
                                  <Typography variant="body2" fontWeight={600}>{session.session_id}</Typography>
                                  <Chip
                                    size="small"
                                    icon={isProductiveTutorial ? <CheckCircleRoundedIcon /> : <ScienceRoundedIcon />}
                                    color={isProductiveTutorial ? 'success' : 'warning'}
                                    variant={isProductiveTutorial ? 'filled' : 'outlined'}
                                    label={isProductiveTutorial ? 'Productive' : 'Test'}
                                  />
                                  <Chip size="small" label={`${session.actual_instance_count || 0} inst`} />
                                  <Chip size="small" label={formatUsd(session.aggregated_estimated_cost_usd || 0)} variant="outlined" />
                                </Stack>
                              }
                              secondary={new Date(session.created_at).toLocaleDateString()}
                            />
                              )
                            })()}
                            <IconButton
                              edge="end"
                              aria-label="Delete session"
                              color="error"
                              disabled={deletingSession?.sessionId === session.session_id}
                              onClick={(e) => handleDeleteClick(e, workshop.name, session.session_id, session.actual_instance_count || 0)}
                            >
                              <DeleteOutlineRoundedIcon fontSize="small" />
                            </IconButton>
                          </ListItemButton>
                        ))}
                      </List>
                    ) : (
                      <Typography color="text.secondary" variant="body2">
                        No tutorial sessions yet. Use create session to start.
                      </Typography>
                    )}
                  </CardContent>

                  <CardActions sx={{ px: 2, pb: 2, pt: 0 }}>
                    <Button
                      variant="outlined"
                      endIcon={<OpenInNewRoundedIcon />}
                      onClick={() => navigate(`/workshop/${workshop.name}`)}
                    >
                      Open Workshop
                    </Button>
                    <Button
                      variant="contained"
                      startIcon={<AddRoundedIcon />}
                      onClick={() => setShowSessionForm(workshop.name)}
                    >
                      Create Session
                    </Button>
                  </CardActions>
                </Card>
              </Grid>
            )
          })
        )}
        </Grid>

      {showWorkshopSelector && (
        <Dialog open onClose={() => setShowWorkshopSelector(false)} maxWidth="sm" fullWidth>
          <DialogTitle>Select Workshop</DialogTitle>
          <DialogContent>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Choose a workshop to create a new tutorial session:
            </Typography>
            <List>
              {workshops.map((workshop) => (
                <ListItemButton
                  key={workshop.name}
                  onClick={() => {
                    setSelectedWorkshopForSession(workshop.name)
                    setShowWorkshopSelector(false)
                    setShowSessionForm(workshop.name)
                  }}
                  sx={{ borderRadius: 1, mb: 1 }}
                >
                  <ListItemText
                    primary={<Typography fontWeight={600}>{workshop.name.replaceAll('_', ' ')}</Typography>}
                    secondary={`${(tutorialSessions[workshop.name] || []).length} active session${(tutorialSessions[workshop.name] || []).length !== 1 ? 's' : ''}`}
                  />
                </ListItemButton>
              ))}
            </List>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setShowWorkshopSelector(false)}>Cancel</Button>
          </DialogActions>
        </Dialog>
      )}

      {showSessionForm && (
        <TutorialSessionForm
          workshopName={showSessionForm}
          onClose={() => setShowSessionForm(null)}
          onSuccess={() => {
            handleSessionCreated(showSessionForm)
            setToast({ open: true, message: `Session created for ${showSessionForm}`, severity: 'success' })
          }}
        />
      )}

      {deleteConfirmData && (
        <Dialog open onClose={() => setDeleteConfirmData(null)} maxWidth="sm" fullWidth>
          <DialogTitle>Delete Tutorial Session</DialogTitle>
          <DialogContent>
            <Typography variant="body2" sx={{ mb: 2 }}>
              Delete session <strong>{deleteConfirmData.sessionId}</strong>?
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Associated instances: {deleteConfirmData.instanceCount}
            </Typography>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setDeleteConfirmData(null)}>Cancel</Button>
            <Button
              color="error"
              variant="contained"
              onClick={() => handleDeleteSession(
                deleteConfirmData.workshopName,
                deleteConfirmData.sessionId,
                deleteConfirmData.instanceCount,
                deleteConfirmData.deleteInstances || false
              )}
              disabled={deletingSession?.sessionId === deleteConfirmData.sessionId}
            >
              {deletingSession?.sessionId === deleteConfirmData.sessionId ? 'Deleting...' : 'Delete Session'}
            </Button>
          </DialogActions>
        </Dialog>
      )}

        {workshops.length > 0 && (
          <Fab
            color="primary"
            aria-label="Create session"
            sx={{ position: 'fixed', right: 24, bottom: 24 }}
            onClick={() => setShowWorkshopSelector(true)}
          >
            <AddRoundedIcon />
          </Fab>
        )}
      </Container>
      <AppToast
        toast={toast}
        onClose={() => setToast((prev) => ({ ...prev, open: false }))}
      />
    </>
  )
}

function TooltipButton({ title, onClick, icon }) {
  return (
    <IconButton
      size="small"
      aria-label={title}
      onClick={(e) => {
        e.stopPropagation()
        onClick()
      }}
    >
      {icon}
    </IconButton>
  )
}

export default Landing
