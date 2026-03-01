import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  Chip,
  CircularProgress,
  Container,
  FormControl,
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
  TextField,
  Typography
} from '@mui/material'
import RefreshRoundedIcon from '@mui/icons-material/RefreshRounded'
import DeleteOutlineRoundedIcon from '@mui/icons-material/DeleteOutlineRounded'
import SecurityRoundedIcon from '@mui/icons-material/SecurityRounded'
import AppToast from '../components/AppToast'
import Header from '../components/Header'
import { api } from '../services/api'

function WorkshopDashboard() {
  const { name: workshopName } = useParams()
  const navigate = useNavigate()

  const [instances, setInstances] = useState([])
  const [loading, setLoading] = useState(true)
  const [settings, setSettings] = useState(null)
  const [settingsLoading, setSettingsLoading] = useState(true)
  const [toast, setToast] = useState({ open: false, message: '', severity: 'success' })

  const [showTerminated, setShowTerminated] = useState(false)
  const [search, setSearch] = useState('')
  const [stateFilter, setStateFilter] = useState('all')
  const [typeFilter, setTypeFilter] = useState('all')
  const [selectedIds, setSelectedIds] = useState([])

  useEffect(() => {
    refreshList()
    loadSettings()
    const interval = setInterval(refreshList, 30000)
    return () => clearInterval(interval)
  }, [workshopName, showTerminated])

  const refreshList = async () => {
    try {
      const response = await api.listInstances(showTerminated)
      if (response.success) {
        let data = response.instances || []
        data = data.filter((instance) => instance.workshop === workshopName || !instance.workshop)
        if (!showTerminated) {
          data = data.filter((instance) => instance.state !== 'terminated')
        }
        setInstances(data)
      }
    } catch (error) {
      showToast(error.message, 'error')
    } finally {
      setLoading(false)
    }
  }

  const loadSettings = async () => {
    try {
      setSettingsLoading(true)
      const response = await api.getTimeoutSettings(workshopName)
      if (response.success && response.settings) {
        setSettings(response.settings)
      }
    } catch (error) {
      showToast(`Error loading settings: ${error.message}`, 'error')
    } finally {
      setSettingsLoading(false)
    }
  }

  const showToast = (message, severity = 'success') => {
    setToast({ open: true, message, severity })
  }

  const filteredInstances = useMemo(() => {
    const query = search.trim().toLowerCase()

    return instances.filter((instance) => {
      if (stateFilter !== 'all' && instance.state !== stateFilter) return false
      const currentType = instance.instance_type || instance.type || 'pool'
      if (typeFilter !== 'all' && currentType !== typeFilter) return false

      if (!query) return true
      const sessionId = instance.tutorial_session_id || ''
      const assignedTo = instance.assigned || instance.assigned_to || ''

      return [
        instance.instance_id || '',
        instance.public_ip || '',
        sessionId,
        assignedTo,
        currentType,
        instance.state || ''
      ].some((value) => String(value).toLowerCase().includes(query))
    })
  }, [instances, search, stateFilter, typeFilter])

  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds])

  const instanceStats = useMemo(() => {
    const running = instances.filter((item) => item.state === 'running').length
    const stopped = instances.filter((item) => item.state === 'stopped').length
    const terminated = instances.filter((item) => item.state === 'terminated').length
    const pool = instances.filter((item) => (item.instance_type || item.type || 'pool') === 'pool').length
    const admin = instances.filter((item) => (item.instance_type || item.type || 'pool') === 'admin').length
    const total = instances.length || 1

    return {
      running,
      stopped,
      terminated,
      pool,
      admin,
      runningPct: Math.round((running / total) * 100),
      stoppedPct: Math.round((stopped / total) * 100)
    }
  }, [instances])

  const toggleSelected = (instanceId) => {
    setSelectedIds((prev) => (
      prev.includes(instanceId)
        ? prev.filter((item) => item !== instanceId)
        : [...prev, instanceId]
    ))
  }

  const toggleSelectAllFiltered = () => {
    const allFilteredIds = filteredInstances.map((item) => item.instance_id)
    const allSelected = allFilteredIds.every((id) => selectedSet.has(id))

    if (allSelected) {
      setSelectedIds((prev) => prev.filter((id) => !allFilteredIds.includes(id)))
    } else {
      setSelectedIds((prev) => [...new Set([...prev, ...allFilteredIds])])
    }
  }

  const deleteInstance = async (instanceId) => {
    if (!window.confirm(`Delete instance ${instanceId}?`)) return
    try {
      const response = await api.deleteInstance(instanceId)
      if (response.success) {
        setSelectedIds((prev) => prev.filter((id) => id !== instanceId))
        showToast('Instance deleted', 'success')
        refreshList()
      } else {
        showToast(response.error || 'Failed to delete instance', 'error')
      }
    } catch (error) {
      showToast(error.message, 'error')
    }
  }

  const handleBulkDelete = async () => {
    if (selectedIds.length === 0) return
    const confirmed = window.confirm(`Delete ${selectedIds.length} selected instances?`)
    if (!confirmed) return

    try {
      await Promise.all(selectedIds.map((instanceId) => api.deleteInstance(instanceId)))
      showToast(`Deleted ${selectedIds.length} instance(s)`, 'success')
      setSelectedIds([])
      refreshList()
    } catch (error) {
      showToast(`Bulk delete failed: ${error.message}`, 'error')
    }
  }

  const assignInstance = async (instanceId) => {
    const studentName = window.prompt(`Enter student name for ${instanceId}:`)
    if (!studentName || !studentName.trim()) return

    try {
      const response = await api.assignInstance(instanceId, studentName.trim())
      if (response.success) {
        showToast(`Assigned to ${studentName}`, 'success')
        refreshList()
      } else {
        showToast(response.error || 'Failed to assign instance', 'error')
      }
    } catch (error) {
      showToast(error.message, 'error')
    }
  }

  const enableHttps = async (instanceId) => {
    try {
      await api.enableHttps(instanceId)
      showToast('HTTPS enabled', 'success')
      refreshList()
    } catch (error) {
      showToast(error.message, 'error')
    }
  }

  return (
    <>
      <Header
        title={workshopName}
        subtitle="Workshop instance management"
        showBack={true}
        backPath="/"
        showSettings={true}
        settingsPath={`/workshop/${workshopName}/config`}
      />

      <Container maxWidth="xl" sx={{ py: 3 }}>
        <Grid container spacing={2.5} sx={{ mb: 2.5 }}>
          <Grid item xs={12} md={6} lg={3}>
            <Card>
              <CardContent>
                <Typography variant="overline" color="text.secondary">Running</Typography>
                <Typography variant="h4" fontWeight={700}>{instanceStats.running}</Typography>
                <LinearProgress variant="determinate" value={instanceStats.runningPct} sx={{ mt: 1 }} />
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} md={6} lg={3}>
            <Card>
              <CardContent>
                <Typography variant="overline" color="text.secondary">Stopped</Typography>
                <Typography variant="h4" fontWeight={700}>{instanceStats.stopped}</Typography>
                <LinearProgress color="warning" variant="determinate" value={instanceStats.stoppedPct} sx={{ mt: 1 }} />
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} md={6} lg={3}>
            <Card>
              <CardContent>
                <Typography variant="overline" color="text.secondary">Pool / Admin</Typography>
                <Typography variant="h4" fontWeight={700}>{instanceStats.pool} / {instanceStats.admin}</Typography>
                <Typography variant="body2" color="text.secondary">Distribution by role</Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} md={6} lg={3}>
            <Card>
              <CardContent>
                <Typography variant="overline" color="text.secondary">Terminated</Typography>
                <Typography variant="h4" fontWeight={700}>{instanceStats.terminated}</Typography>
                <Typography variant="body2" color="text.secondary">Use toggle to include in table</Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>

        <Card sx={{ mb: 2.5 }}>
          <CardContent>
            <Stack direction={{ xs: 'column', lg: 'row' }} spacing={2} alignItems={{ xs: 'stretch', lg: 'center' }}>
              <TextField
                label="Search instances"
                placeholder="ID, IP, session, assignee"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                fullWidth
              />

              <FormControl sx={{ minWidth: 170 }}>
                <InputLabel id="state-filter-label">State</InputLabel>
                <Select
                  labelId="state-filter-label"
                  label="State"
                  value={stateFilter}
                  onChange={(event) => setStateFilter(event.target.value)}
                >
                  <MenuItem value="all">All</MenuItem>
                  <MenuItem value="running">Running</MenuItem>
                  <MenuItem value="stopped">Stopped</MenuItem>
                  <MenuItem value="terminated">Terminated</MenuItem>
                </Select>
              </FormControl>

              <FormControl sx={{ minWidth: 170 }}>
                <InputLabel id="type-filter-label">Type</InputLabel>
                <Select
                  labelId="type-filter-label"
                  label="Type"
                  value={typeFilter}
                  onChange={(event) => setTypeFilter(event.target.value)}
                >
                  <MenuItem value="all">All</MenuItem>
                  <MenuItem value="pool">Pool</MenuItem>
                  <MenuItem value="admin">Admin</MenuItem>
                </Select>
              </FormControl>

              <Stack direction="row" spacing={1}>
                <Button variant="outlined" startIcon={<RefreshRoundedIcon />} onClick={refreshList}>
                  Refresh
                </Button>
                <Button
                  variant={showTerminated ? 'contained' : 'outlined'}
                  onClick={() => setShowTerminated((prev) => !prev)}
                >
                  {showTerminated ? 'Hide terminated' : 'Show terminated'}
                </Button>
              </Stack>
            </Stack>
          </CardContent>
        </Card>

        {settingsLoading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress size={24} />
          </Box>
        ) : settings && (
          <Card sx={{ mb: 2.5 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>Timeout configuration</Typography>
              <Stack direction={{ xs: 'column', md: 'row' }} spacing={2}>
                <Chip label={`Stop: ${settings.stop_timeout} min`} />
                <Chip label={`Terminate: ${settings.terminate_timeout} min`} />
                <Chip label={`Hard terminate: ${settings.hard_terminate_timeout} min`} />
                <Chip label={`Admin cleanup: ${settings.admin_cleanup_days} days`} />
              </Stack>
            </CardContent>
          </Card>
        )}

        <Card>
          <CardContent sx={{ pb: 1.25 }}>
            <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5} alignItems={{ xs: 'flex-start', md: 'center' }} justifyContent="space-between">
              <Typography variant="h6" fontWeight={700}>
                Instances ({filteredInstances.length})
              </Typography>
              <Stack direction="row" spacing={1}>
                <Button onClick={toggleSelectAllFiltered} variant="outlined">
                  Toggle Select Filtered
                </Button>
                <Button
                  color="error"
                  variant="contained"
                  startIcon={<DeleteOutlineRoundedIcon />}
                  disabled={selectedIds.length === 0}
                  onClick={handleBulkDelete}
                >
                  Delete Selected ({selectedIds.length})
                </Button>
              </Stack>
            </Stack>
          </CardContent>

          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell padding="checkbox">
                    <Checkbox
                      indeterminate={selectedIds.length > 0 && selectedIds.length < filteredInstances.length}
                      checked={filteredInstances.length > 0 && filteredInstances.every((item) => selectedSet.has(item.instance_id))}
                      onChange={toggleSelectAllFiltered}
                    />
                  </TableCell>
                  <TableCell>Instance ID</TableCell>
                  <TableCell>Type</TableCell>
                  <TableCell>State</TableCell>
                  <TableCell>IP Address</TableCell>
                  <TableCell>Assigned</TableCell>
                  <TableCell>Session</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {loading ? (
                  <TableRow>
                    <TableCell colSpan={8} align="center" sx={{ py: 5 }}>
                      <CircularProgress size={24} />
                    </TableCell>
                  </TableRow>
                ) : filteredInstances.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={8} align="center" sx={{ py: 5 }}>
                      No instances found
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredInstances.map((instance) => {
                    const instanceType = instance.instance_type || instance.type || 'pool'
                    const sessionId = instance.tutorial_session_id
                    const assignedTo = instance.assigned || instance.assigned_to || '-'
                    const resolvedHttpsUrl = instance.https_url || instance.tags?.HttpsUrl
                    const visitUrl = resolvedHttpsUrl || (instance.public_ip ? `http://${instance.public_ip}` : null)

                    return (
                      <TableRow hover key={instance.instance_id}>
                        <TableCell padding="checkbox">
                          <Checkbox
                            checked={selectedSet.has(instance.instance_id)}
                            onChange={() => toggleSelected(instance.instance_id)}
                          />
                        </TableCell>
                        <TableCell>{instance.instance_id}</TableCell>
                        <TableCell>
                          <Chip
                            size="small"
                            color={instanceType === 'admin' ? 'secondary' : 'default'}
                            label={instanceType}
                          />
                        </TableCell>
                        <TableCell>
                          <Chip
                            size="small"
                            color={instance.state === 'running' ? 'success' : instance.state === 'stopped' ? 'warning' : 'default'}
                            label={instance.state}
                          />
                        </TableCell>
                        <TableCell>
                          {visitUrl ? (
                            <Link href={visitUrl} target="_blank" rel="noopener noreferrer">
                              visit me
                            </Link>
                          ) : (
                            '-'
                          )}
                        </TableCell>
                        <TableCell>{assignedTo}</TableCell>
                        <TableCell>
                          {sessionId ? (
                            <Button size="small" onClick={() => navigate(`/tutorial/${instance.workshop || workshopName}/${sessionId}`)}>
                              {sessionId}
                            </Button>
                          ) : (
                            '-'
                          )}
                        </TableCell>
                        <TableCell align="right">
                          <Stack direction="row" spacing={1} justifyContent="flex-end">
                            {!instance.assigned && instanceType === 'pool' && (
                              <Button size="small" variant="outlined" onClick={() => assignInstance(instance.instance_id)}>
                                Assign
                              </Button>
                            )}

                            {instance.public_ip && !resolvedHttpsUrl && (
                              <Button
                                size="small"
                                variant="outlined"
                                startIcon={<SecurityRoundedIcon />}
                                onClick={() => enableHttps(instance.instance_id)}
                              >
                                HTTPS
                              </Button>
                            )}

                            {resolvedHttpsUrl && (
                              <Button
                                size="small"
                                variant="outlined"
                                component="a"
                                href={resolvedHttpsUrl}
                                target="_blank"
                                rel="noopener noreferrer"
                              >
                                Open
                              </Button>
                            )}

                            <Button size="small" color="error" onClick={() => deleteInstance(instance.instance_id)}>
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
      </Container>
      <AppToast
        toast={toast}
        onClose={() => setToast((prev) => ({ ...prev, open: false }))}
      />
    </>
  )
}

export default WorkshopDashboard
