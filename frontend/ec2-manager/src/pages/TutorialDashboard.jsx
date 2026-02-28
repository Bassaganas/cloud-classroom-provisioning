import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  Chip,
  CircularProgress,
  Container,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Fab,
  FormControl,
  FormControlLabel,
  Grid,
  InputLabel,
  LinearProgress,
  Link,
  MenuItem,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TableSortLabel,
  TextField,
  Tooltip,
  Typography
} from '@mui/material'
import AddRoundedIcon from '@mui/icons-material/AddRounded'
import DeleteOutlineRoundedIcon from '@mui/icons-material/DeleteOutlineRounded'
import RefreshRoundedIcon from '@mui/icons-material/RefreshRounded'
import KeyboardRoundedIcon from '@mui/icons-material/KeyboardRounded'
import SecurityRoundedIcon from '@mui/icons-material/SecurityRounded'
import AppToast from '../components/AppToast'
import Header from '../components/Header'
import PurchaseTypeSelector from '../components/PurchaseTypeSelector'
import { api } from '../services/api'

function TutorialDashboard() {
  const { workshop, sessionId } = useParams()
  const navigate = useNavigate()

  const [session, setSession] = useState(null)
  const [instances, setInstances] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [toast, setToast] = useState({ open: false, message: '', severity: 'success' })

  const [showCreateForm, setShowCreateForm] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [deleteInstances, setDeleteInstances] = useState(false)
  const [deletingSession, setDeletingSession] = useState(false)

  const [activeFilter, setActiveFilter] = useState('all')
  const [search, setSearch] = useState('')
  const [sortConfig, setSortConfig] = useState({ key: 'instance_id', direction: 'asc' })

  const [createFormData, setCreateFormData] = useState({
    type: 'pool',
    count: 1,
    cleanup_days: 7,
    purchase_type: 'on-demand',
    spot_duration_hours: 2
  })

  useEffect(() => {
    loadSession()
    const interval = setInterval(loadSession, 30000)
    return () => clearInterval(interval)
  }, [workshop, sessionId])

  useEffect(() => {
    const handleKeyDown = (event) => {
      const targetTag = event.target?.tagName?.toLowerCase()
      const typing = targetTag === 'input' || targetTag === 'textarea' || event.target?.isContentEditable
      if (typing) return

      if (event.key === 'n') {
        event.preventDefault()
        setShowCreateForm(true)
      }
      if (event.key === 'Delete') {
        event.preventDefault()
        setShowDeleteConfirm(true)
      }
      if (event.key === 'Escape') {
        setShowCreateForm(false)
        setShowDeleteConfirm(false)
      }
      if (event.key === 'r') {
        event.preventDefault()
        loadSession()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  const loadSession = async () => {
    try {
      setLoading(true)
      const response = await api.getTutorialSession(sessionId, workshop)
      if (response.success) {
        setSession(response.session)
        setInstances(response.instances || [])
        setStats(response.stats || null)
      } else {
        showToast(response.error || 'Failed to load session', 'error')
      }
    } catch (error) {
      showToast(error.message, 'error')
    } finally {
      setLoading(false)
    }
  }

  const showToast = (message, severity = 'success') => {
    setToast({ open: true, message, severity })
  }

  const handleCreateInstances = async (event) => {
    event.preventDefault()
    try {
      const payload = {
        count: parseInt(createFormData.count, 10),
        type: createFormData.type,
        workshop,
        tutorial_session_id: sessionId,
        purchase_type: createFormData.purchase_type,
        spot_duration_hours: createFormData.purchase_type === 'spot'
          ? createFormData.spot_duration_hours
          : null
      }

      if (createFormData.type === 'admin') {
        payload.cleanup_days = parseInt(createFormData.cleanup_days, 10)
      }

      const response = await api.createInstances(payload)
      if (response.success) {
        showToast(`Created ${response.count} ${createFormData.type} instance(s)`, 'success')
        setShowCreateForm(false)
        await loadSession()
      } else {
        showToast(response.error || 'Failed to create instances', 'error')
      }
    } catch (error) {
      showToast(error.message, 'error')
    }
  }

  const handleDeleteInstance = async (instanceId) => {
    const confirmed = window.confirm(`Delete instance ${instanceId}?`)
    if (!confirmed) return

    try {
      const response = await api.deleteInstance(instanceId)
      if (response.success) {
        showToast(`Instance ${instanceId} deleted`, 'success')
        await loadSession()
      } else {
        showToast(response.error || 'Failed to delete instance', 'error')
      }
    } catch (error) {
      showToast(error.message, 'error')
    }
  }

  const handleEnableHttps = async (instanceId) => {
    try {
      const response = await api.enableHttps(instanceId)
      if (response.success) {
        showToast(`HTTPS enabled for ${instanceId}`, 'success')
        await loadSession()
      } else {
        showToast(response.error || 'Failed to enable HTTPS', 'error')
      }
    } catch (error) {
      showToast(error.message, 'error')
    }
  }

  const handleDeleteSession = async () => {
    try {
      setDeletingSession(true)
      const response = await api.deleteTutorialSession(sessionId, workshop, deleteInstances)
      if (response.success) {
        showToast(`Tutorial session ${sessionId} deleted`, 'success')
        setTimeout(() => navigate('/'), 900)
      } else {
        showToast(response.error || 'Failed to delete session', 'error')
      }
    } catch (error) {
      showToast(error.message, 'error')
    } finally {
      setDeletingSession(false)
      setShowDeleteConfirm(false)
    }
  }

  const filteredInstances = useMemo(() => {
    const query = search.trim().toLowerCase()

    return instances.filter((instance) => {
      const type = instance.type || instance.instance_type || 'pool'
      if (activeFilter !== 'all' && activeFilter !== type && activeFilter !== instance.state) {
        return false
      }

      if (!query) return true

      return [
        instance.instance_id || '',
        instance.public_ip || '',
        instance.state || '',
        type,
        instance.assigned_to || ''
      ].some((value) => String(value).toLowerCase().includes(query))
    })
  }, [activeFilter, instances, search])

  const sortedInstances = useMemo(() => {
    return [...filteredInstances].sort((a, b) => {
      if (!sortConfig.key) return 0

      const readValue = (instance) => {
        if (sortConfig.key === 'type') return instance.type || instance.instance_type || 'pool'
        return instance[sortConfig.key] || ''
      }

      const aVal = String(readValue(a)).toLowerCase()
      const bVal = String(readValue(b)).toLowerCase()

      if (sortConfig.direction === 'asc') {
        return aVal > bVal ? 1 : aVal < bVal ? -1 : 0
      }
      return aVal < bVal ? 1 : aVal > bVal ? -1 : 0
    })
  }, [filteredInstances, sortConfig])

  const toggleSort = (key) => {
    setSortConfig((prev) => ({
      key,
      direction: prev.key === key && prev.direction === 'asc' ? 'desc' : 'asc'
    }))
  }

  if (loading && !session) {
    return (
      <Box sx={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <CircularProgress />
      </Box>
    )
  }

  if (!session) {
    return (
      <Container sx={{ py: 4 }}>
        <Alert severity="error" sx={{ mb: 2 }}>Session not found</Alert>
        <Button variant="contained" onClick={() => navigate('/')}>Back to Landing</Button>
      </Container>
    )
  }

  const total = Math.max(stats?.total_instances || instances.length || 0, 1)
  const runningPct = Math.round(((stats?.running || 0) / total) * 100)
  const stoppedPct = Math.round(((stats?.stopped || 0) / total) * 100)
  const poolPct = Math.round(((stats?.pool_instances || 0) / total) * 100)
  const adminPct = Math.round(((stats?.admin_instances || 0) / total) * 100)

  return (
    <>
      <Header
        title={session.session_id}
        subtitle={`Workshop: ${session.workshop_name}`}
        showBack={true}
        backPath="/"
      />

      <Container maxWidth="xl" sx={{ py: 3 }}>
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5} justifyContent="space-between" sx={{ mb: 2 }}>
          <Stack direction="row" spacing={1} alignItems="center">
            <Tooltip title="Keyboard shortcuts: N create, Delete session, R refresh, Esc close dialogs">
              <Chip icon={<KeyboardRoundedIcon />} label="Shortcuts" variant="outlined" />
            </Tooltip>
            <Chip label="Auto-refresh: 30s" size="small" />
          </Stack>
          <Stack direction="row" spacing={1}>
            <Button startIcon={<RefreshRoundedIcon />} onClick={loadSession} variant="outlined">Refresh</Button>
            <Button
              color="error"
              variant="outlined"
              startIcon={<DeleteOutlineRoundedIcon />}
              onClick={() => setShowDeleteConfirm(true)}
              disabled={deletingSession}
            >
              Delete Session
            </Button>
          </Stack>
        </Stack>

        <Grid container spacing={2.5} sx={{ mb: 2.5 }}>
          <StatCard label="Total" value={stats?.total_instances || 0} onClick={() => setActiveFilter('all')} active={activeFilter === 'all'} />
          <StatCard label="Running" value={stats?.running || 0} onClick={() => setActiveFilter('running')} active={activeFilter === 'running'} color="success.main" />
          <StatCard label="Stopped" value={stats?.stopped || 0} onClick={() => setActiveFilter('stopped')} active={activeFilter === 'stopped'} color="warning.main" />
          <StatCard label="Pool" value={stats?.pool_instances || 0} onClick={() => setActiveFilter('pool')} active={activeFilter === 'pool'} color="info.main" />
          <StatCard label="Admin" value={stats?.admin_instances || 0} onClick={() => setActiveFilter('admin')} active={activeFilter === 'admin'} color="secondary.main" />
        </Grid>

        <Grid container spacing={2.5} sx={{ mb: 2.5 }}>
          <Grid item xs={12} md={7}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>Instance State Distribution</Typography>
                <Stack spacing={1.5}>
                  <MetricRow label="Running" value={runningPct} color="success" />
                  <MetricRow label="Stopped" value={stoppedPct} color="warning" />
                  <MetricRow label="Pool" value={poolPct} color="info" />
                  <MetricRow label="Admin" value={adminPct} color="secondary" />
                </Stack>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} md={5}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>Filters</Typography>
                <Stack spacing={1.5}>
                  <TextField
                    label="Search instances"
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    placeholder="ID, IP, state, assignee"
                    fullWidth
                  />
                  <FormControl fullWidth>
                    <InputLabel id="active-filter-label">Quick filter</InputLabel>
                    <Select
                      labelId="active-filter-label"
                      value={activeFilter}
                      label="Quick filter"
                      onChange={(event) => setActiveFilter(event.target.value)}
                    >
                      <MenuItem value="all">All</MenuItem>
                      <MenuItem value="running">Running</MenuItem>
                      <MenuItem value="stopped">Stopped</MenuItem>
                      <MenuItem value="pool">Pool</MenuItem>
                      <MenuItem value="admin">Admin</MenuItem>
                    </Select>
                  </FormControl>
                </Stack>
              </CardContent>
            </Card>
          </Grid>
        </Grid>

        <Card>
          <CardContent sx={{ pb: 1 }}>
            <Typography variant="h6" fontWeight={700}>Instances ({sortedInstances.length})</Typography>
          </CardContent>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <HeaderSort label="Instance ID" sortKey="instance_id" sortConfig={sortConfig} onSort={toggleSort} />
                  <HeaderSort label="Type" sortKey="type" sortConfig={sortConfig} onSort={toggleSort} />
                  <HeaderSort label="State" sortKey="state" sortConfig={sortConfig} onSort={toggleSort} />
                  <HeaderSort label="IP" sortKey="public_ip" sortConfig={sortConfig} onSort={toggleSort} />
                  <HeaderSort label="Assigned" sortKey="assigned_to" sortConfig={sortConfig} onSort={toggleSort} />
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {loading ? (
                  <TableRow>
                    <TableCell colSpan={6} align="center" sx={{ py: 6 }}>
                      <CircularProgress size={24} />
                    </TableCell>
                  </TableRow>
                ) : sortedInstances.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} align="center" sx={{ py: 6 }}>
                      No instances found
                    </TableCell>
                  </TableRow>
                ) : (
                  sortedInstances.map((instance) => {
                    const type = instance.type || instance.instance_type || 'pool'
                    return (
                      <TableRow key={instance.instance_id} hover>
                        <TableCell>{instance.instance_id}</TableCell>
                        <TableCell><Chip size="small" label={type} color={type === 'admin' ? 'secondary' : 'default'} /></TableCell>
                        <TableCell>
                          <Chip
                            size="small"
                            label={instance.state}
                            color={instance.state === 'running' ? 'success' : instance.state === 'stopped' ? 'warning' : 'default'}
                          />
                        </TableCell>
                        <TableCell>
                          {instance.public_ip ? (
                            <Link href={`http://${instance.public_ip}`} target="_blank" rel="noopener noreferrer">
                              {instance.public_ip}
                            </Link>
                          ) : '-'}
                        </TableCell>
                        <TableCell>{instance.assigned_to || '-'}</TableCell>
                        <TableCell align="right">
                          <Stack direction="row" spacing={1} justifyContent="flex-end">
                            {instance.public_ip && !instance.https_url && (
                              <Button
                                size="small"
                                startIcon={<SecurityRoundedIcon />}
                                onClick={() => handleEnableHttps(instance.instance_id)}
                                disabled={instance.state !== 'running'}
                                variant="outlined"
                              >
                                HTTPS
                              </Button>
                            )}
                            {instance.https_url && (
                              <Button
                                size="small"
                                variant="outlined"
                                component="a"
                                href={instance.https_url}
                                target="_blank"
                                rel="noopener noreferrer"
                              >
                                Open
                              </Button>
                            )}
                            <Button color="error" size="small" onClick={() => handleDeleteInstance(instance.instance_id)}>
                              Delete
                            </Button>
                          </Stack>
                        </TableCell>
                      </TableRow>
                    )
                  })
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </Card>

        <Fab
          color="primary"
          aria-label="Create instance"
          sx={{ position: 'fixed', right: 24, bottom: 24 }}
          onClick={() => setShowCreateForm(true)}
        >
          <AddRoundedIcon />
        </Fab>
      </Container>

      <Dialog open={showCreateForm} onClose={() => setShowCreateForm(false)} maxWidth="md" fullWidth>
        <DialogTitle>Create Instance</DialogTitle>
        <Box component="form" onSubmit={handleCreateInstances}>
          <DialogContent>
            <Stack spacing={2}>
              <FormControl fullWidth>
                <InputLabel id="instance-type-label">Instance Type</InputLabel>
                <Select
                  labelId="instance-type-label"
                  value={createFormData.type}
                  label="Instance Type"
                  onChange={(event) => setCreateFormData({ ...createFormData, type: event.target.value })}
                >
                  <MenuItem value="pool">Pool</MenuItem>
                  <MenuItem value="admin">Admin</MenuItem>
                </Select>
              </FormControl>

              <TextField
                type="number"
                label="Count"
                inputProps={{ min: 1, max: 120 }}
                value={createFormData.count}
                onChange={(event) => setCreateFormData({ ...createFormData, count: event.target.value })}
                required
              />

              {createFormData.type === 'admin' && (
                <TextField
                  type="number"
                  label="Cleanup Days"
                  inputProps={{ min: 1, max: 365 }}
                  value={createFormData.cleanup_days}
                  onChange={(event) => setCreateFormData({ ...createFormData, cleanup_days: event.target.value })}
                  required
                />
              )}

              <Box sx={{ p: 1.25, border: '1px solid', borderColor: 'divider', borderRadius: 2, bgcolor: 'grey.50' }}>
                <PurchaseTypeSelector
                  onPurchaseTypeChange={(config) => setCreateFormData({ ...createFormData, ...config })}
                  instanceType={createFormData.type}
                />
              </Box>
            </Stack>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setShowCreateForm(false)}>Cancel</Button>
            <Button type="submit" variant="contained">Create</Button>
          </DialogActions>
        </Box>
      </Dialog>

      <Dialog open={showDeleteConfirm} onClose={() => setShowDeleteConfirm(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Delete Tutorial Session</DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ mb: 1.5 }}>
            Delete session <strong>{sessionId}</strong>?
          </Typography>
          <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1 }}>
            Current instance count: {instances.length}
          </Typography>
          <FormControlLabel
            control={
              <Checkbox
                checked={deleteInstances}
                onChange={(event) => setDeleteInstances(event.target.checked)}
              />
            }
            label="Also delete associated EC2 instances"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowDeleteConfirm(false)} disabled={deletingSession}>Cancel</Button>
          <Button color="error" variant="contained" onClick={handleDeleteSession} disabled={deletingSession}>
            {deletingSession ? 'Deleting...' : 'Delete Session'}
          </Button>
        </DialogActions>
      </Dialog>

      <AppToast
        toast={toast}
        onClose={() => setToast((prev) => ({ ...prev, open: false }))}
      />
    </>
  )
}

function StatCard({ label, value, onClick, active, color = 'text.primary' }) {
  return (
    <Grid item xs={12} sm={6} md={4} lg={2}>
      <Card
        onClick={onClick}
        sx={{
          cursor: 'pointer',
          borderColor: active ? 'primary.main' : 'divider',
          borderWidth: 1,
          borderStyle: 'solid',
          transition: 'all .2s ease',
          '&:hover': { transform: 'translateY(-2px)' }
        }}
      >
        <CardContent>
          <Typography variant="overline" color="text.secondary">{label}</Typography>
          <Typography variant="h5" fontWeight={700} sx={{ color }}>{value}</Typography>
        </CardContent>
      </Card>
    </Grid>
  )
}

function MetricRow({ label, value, color }) {
  return (
    <Box>
      <Stack direction="row" justifyContent="space-between" sx={{ mb: 0.5 }}>
        <Typography variant="body2">{label}</Typography>
        <Typography variant="body2" fontWeight={700}>{value}%</Typography>
      </Stack>
      <LinearProgress variant="determinate" value={value} color={color} />
    </Box>
  )
}

function HeaderSort({ label, sortKey, sortConfig, onSort }) {
  const active = sortConfig.key === sortKey
  return (
    <TableCell>
      <TableSortLabel
        active={active}
        direction={active ? sortConfig.direction : 'asc'}
        onClick={() => onSort(sortKey)}
      >
        {label}
      </TableSortLabel>
    </TableCell>
  )
}

export default TutorialDashboard
