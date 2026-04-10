import { useEffect, useMemo, useRef, useState } from 'react'
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
import { api } from '../services/api'
import {
  DEFAULT_EC2_INSTANCE_TYPE,
  EC2_INSTANCE_TYPE_OPTIONS,
  EC2_ON_DEMAND_RATES,
  formatEc2OptionLabel
} from '../config/ec2InstanceTypes'

const APPROX_RATES_USD = EC2_ON_DEMAND_RATES

const FALLBACK_RATES_USD = { onDemand: 0.0416, spot: 0.0125 }

function parseNumber(value) {
  if (value === null || value === undefined || value === '') return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function normalizePurchaseType(rawValue, fallback = 'on-demand') {
  const normalized = String(rawValue || '').trim().toLowerCase()
  if (normalized.includes('spot')) return 'spot'
  if (normalized.includes('on-demand') || normalized === 'ondemand') return 'on-demand'
  return fallback
}

function getCostMeta(instance, session) {
  const instanceType = instance.instance_type || 't3.medium'
  const rates = APPROX_RATES_USD[instanceType] || FALLBACK_RATES_USD
  const purchaseType = normalizePurchaseType(
    instance.purchase_type || instance.tags?.PurchaseType || session?.purchase_type,
    'on-demand'
  )
  const spotCap = parseNumber(instance.spot_max_price ?? instance.tags?.SpotMaxPrice ?? session?.spot_max_price)
  const spotRate = spotCap !== null ? Math.min(rates.spot, spotCap) : rates.spot
  const hourlyEstimate = purchaseType === 'spot' ? spotRate : rates.onDemand

  const launchMs = instance.launch_time ? new Date(instance.launch_time).getTime() : null
  const elapsedHours = launchMs ? Math.max(0, (Date.now() - launchMs) / (1000 * 60 * 60)) : 0
  const estimatedCost = hourlyEstimate * elapsedHours
  const estimated24h = hourlyEstimate * 24
  const actualCost = parseNumber(instance.actual_cost_usd)

  return {
    purchaseType,
    spotCap,
    hourlyEstimate,
    elapsedHours,
    estimatedCost,
    estimated24h,
    actualCost
  }
}

function formatUsd(value, digits = 4) {
  if (value === null || value === undefined || Number.isNaN(value)) return '-'
  return `$${Number(value).toFixed(digits)}`
}

function TutorialDashboard() {
  const { workshop, sessionId } = useParams()
  const navigate = useNavigate()

  const [session, setSession] = useState(null)
  const [instances, setInstances] = useState([])
  const [stats, setStats] = useState(null)
  const [costs, setCosts] = useState(null)
  const [loading, setLoading] = useState(true)
  const [toast, setToast] = useState({ open: false, message: '', severity: 'success' })

  const [showCreateForm, setShowCreateForm] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [deleteInstances, setDeleteInstances] = useState(false)
  const [deletingSession, setDeletingSession] = useState(false)
  const [creatingInstances, setCreatingInstances] = useState(false)
  const [createProgress, setCreateProgress] = useState(null)
  const [checkingHealth, setCheckingHealth] = useState(false)
  const [showHealthColumn, setShowHealthColumn] = useState(false)
  const createDebounceRef = useRef(0)

  const [activeFilter, setActiveFilter] = useState('all')
  const [search, setSearch] = useState('')
  const [sortConfig, setSortConfig] = useState({ key: 'launch_time', direction: 'desc' })
  const [selectedIds, setSelectedIds] = useState([])
  const [batchDeleting, setBatchDeleting] = useState(false)

  const [showExtendDaysModal, setShowExtendDaysModal] = useState(false)
  const [extendDaysInstance, setExtendDaysInstance] = useState(null)
  const [extendDaysValue, setExtendDaysValue] = useState(7)
  const [updatingCleanupDays, setUpdatingCleanupDays] = useState(false)

  const [createFormData, setCreateFormData] = useState({
    type: 'pool',
    count: 1,
    cleanup_days: 7,
    ec2_instance_type: DEFAULT_EC2_INSTANCE_TYPE,
    spot_max_price: ''
  })

  useEffect(() => {
    loadSession()
    // Initial load only, user can click refresh button to reload
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
        setCosts(response.costs || null)
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

  const getHealthChip = (instance) => {
    const status = instance.health_status
    if (!status) {
      return <Chip size="small" label="Not checked" variant="outlined" />
    }

    const statusMap = {
      healthy: { label: 'Healthy', color: 'success' },
      unhealthy: { label: 'Unhealthy', color: 'error' },
      unreachable: { label: 'Unreachable', color: 'warning' }
    }

    const config = statusMap[status] || { label: status, color: 'default' }
    const checkedAt = instance.health_checked_at ? new Date(instance.health_checked_at).toLocaleString() : 'Unknown'
    const detail = instance.health_error ? `Error: ${instance.health_error}` : ''
    const tooltipText = `Last check: ${checkedAt}${detail ? `\n${detail}` : ''}`

    return (
      <Tooltip title={tooltipText}>
        <Chip size="small" label={config.label} color={config.color} />
      </Tooltip>
    )
  }

  const handleCreateInstances = async (event) => {
    event.preventDefault()

    const now = Date.now()
    if (now - createDebounceRef.current < 500) {
      showToast('Please wait before submitting again.', 'warning')
      return
    }
    createDebounceRef.current = now

    if (creatingInstances) {
      showToast("Instance pool is already being created, please wait...", "warning")
      return
    }

    try {
      setCreatingInstances(true)
      setCreateProgress({
        count: parseInt(createFormData.count, 10),
        type: createFormData.type
      })

      const isProductiveTutorial = session?.productive_tutorial === true ||
        (session?.productive_tutorial === undefined && session?.purchase_type === 'on-demand')
      const enforcedPurchaseType = isProductiveTutorial ? 'on-demand' : 'spot'
      const effectiveSpotMaxPrice = createFormData.spot_max_price || session?.spot_max_price || null

      const payload = {
        count: parseInt(createFormData.count, 10),
        type: createFormData.type,
        workshop,
        tutorial_session_id: sessionId,
        ec2_instance_type: createFormData.ec2_instance_type || DEFAULT_EC2_INSTANCE_TYPE,
        purchase_type: enforcedPurchaseType,
        spot_max_price: enforcedPurchaseType === 'spot' ? effectiveSpotMaxPrice : null
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
    } finally {
      setCreatingInstances(false)
      setCreateProgress(null)
    }
  }

  const handleCheckHealth = async () => {
    try {
      setCheckingHealth(true)
      setShowHealthColumn(true)
      const response = await api.listInstancesBySession(sessionId, true)

      if (!response.success) {
        showToast(response.error || 'Failed to check health', 'error')
        return
      }

      const healthByInstance = new Map(
        (response.instances || []).map((instance) => [
          instance.instance_id,
          {
            health_status: instance.health_status,
            health_checked_at: instance.health_checked_at,
            health_error: instance.health_error
          }
        ])
      )

      setInstances((previous) => previous.map((instance) => ({
        ...instance,
        ...(healthByInstance.get(instance.instance_id) || {})
      })))
      showToast('Health check completed', 'success')
    } catch (error) {
      showToast(error.message, 'error')
    } finally {
      setCheckingHealth(false)
    }
  }

  const handleDeleteInstance = async (instanceId) => {
    const confirmed = window.confirm(`Delete instance ${instanceId}?`)
    if (!confirmed) return

    try {
      const response = await api.deleteInstance(instanceId)
      if (response.success) {
        setSelectedIds((prev) => prev.filter((id) => id !== instanceId))
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

  const handleExtendDaysClick = (instance) => {
    setExtendDaysInstance(instance)
    setExtendDaysValue(instance.cleanup_days_remaining + Math.ceil((new Date(instance.launch_time).getTime() - Date.now()) / (1000 * 60 * 60 * 24)) || 7)
    setShowExtendDaysModal(true)
  }

  const handleExtendDaysSave = async () => {
    if (!extendDaysInstance) return

    try {
      setUpdatingCleanupDays(true)
      const response = await api.updateCleanupDays(extendDaysInstance.instance_id, parseInt(extendDaysValue))
      
      if (response.success) {
        showToast(`Cleanup days updated to ${extendDaysValue}`, 'success')
        setShowExtendDaysModal(false)
        setExtendDaysInstance(null)
        await loadSession()
      } else {
        showToast(response.error || 'Failed to update cleanup days', 'error')
      }
    } catch (error) {
      showToast(error.message, 'error')
    } finally {
      setUpdatingCleanupDays(false)
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
        instance.https_domain || '',
        instance.state || '',
        type,
        instance.assigned_to || ''
      ].some((value) => String(value).toLowerCase().includes(query))
    })
  }, [activeFilter, instances, search])

  useEffect(() => {
    const validIds = new Set(instances.map((instance) => instance.instance_id))
    setSelectedIds((prev) => prev.filter((id) => validIds.has(id)))
  }, [instances])

  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds])

  const toggleSelected = (instanceId) => {
    setSelectedIds((prev) => (
      prev.includes(instanceId)
        ? prev.filter((id) => id !== instanceId)
        : [...prev, instanceId]
    ))
  }

  const toggleSelectAllFiltered = () => {
    const allFilteredIds = filteredInstances.map((item) => item.instance_id)
    const allSelected = allFilteredIds.length > 0 && allFilteredIds.every((id) => selectedSet.has(id))

    if (allSelected) {
      setSelectedIds((prev) => prev.filter((id) => !allFilteredIds.includes(id)))
    } else {
      setSelectedIds((prev) => [...new Set([...prev, ...allFilteredIds])])
    }
  }

  const handleBatchDelete = async () => {
    if (selectedIds.length === 0) return
    const confirmed = window.confirm(`Delete ${selectedIds.length} selected instances?`)
    if (!confirmed) return

    try {
      setBatchDeleting(true)
      const response = await api.deleteInstances(selectedIds)
      if (response.success) {
        showToast(`Deleted ${response.count ?? selectedIds.length} instance(s)`, 'success')
        setSelectedIds([])
        await loadSession()
      } else {
        showToast(response.error || 'Failed to delete selected instances', 'error')
      }
    } catch (error) {
      showToast(error.message, 'error')
    } finally {
      setBatchDeleting(false)
    }
  }

  const sortedInstances = useMemo(() => {
    return [...filteredInstances].sort((a, b) => {
      if (!sortConfig.key) return 0

      const readValue = (instance) => {
        if (sortConfig.key === 'type') return instance.type || instance.instance_type || 'pool'
        if (sortConfig.key === 'ec2_instance_type') return instance.instance_type || DEFAULT_EC2_INSTANCE_TYPE
        if (sortConfig.key === 'launch_time') return new Date(instance.launch_time || 0).getTime()
        if (sortConfig.key === 'health_status') return instance.health_status || ''
        if (sortConfig.key === 'endpoint') return instance.https_domain || instance.public_ip || ''
        return instance[sortConfig.key] || ''
      }

      const aRead = readValue(a)
      const bRead = readValue(b)

      const aVal = typeof aRead === 'number' ? aRead : String(aRead).toLowerCase()
      const bVal = typeof bRead === 'number' ? bRead : String(bRead).toLowerCase()

      if (sortConfig.direction === 'asc') {
        return aVal > bVal ? 1 : aVal < bVal ? -1 : 0
      }
      return aVal < bVal ? 1 : aVal > bVal ? -1 : 0
    })
  }, [filteredInstances, sortConfig])

  const costByInstanceId = useMemo(() => {
    const pairs = instances.map((instance) => [instance.instance_id, getCostMeta(instance, session)])
    return new Map(pairs)
  }, [instances, session])

  const computedCostTotals = useMemo(() => {
    let estimatedHourly = 0
    let estimatedAccrued = 0
    let estimated24h = 0
    let actualTotal = 0
    let hasActual = false

    instances.forEach((instance) => {
      const meta = costByInstanceId.get(instance.instance_id)
      if (!meta) return
      estimatedHourly += meta.hourlyEstimate
      estimatedAccrued += meta.estimatedCost
      estimated24h += meta.estimated24h
      if (meta.actualCost !== null) {
        actualTotal += meta.actualCost
        hasActual = true
      }
    })

    const fallbackActualTotal = parseNumber(costs?.actual_total_usd)

    return {
      estimatedHourly,
      estimatedAccrued,
      estimated24h,
      actualTotal: hasActual ? actualTotal : fallbackActualTotal,
      actualDataSource: costs?.actual_data_source || 'unavailable'
    }
  }, [instances, costByInstanceId, costs])

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

  const isProductiveTutorial = session?.productive_tutorial === true ||
    (session?.productive_tutorial === undefined && session?.purchase_type === 'on-demand')

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
            <Chip label="Auto-refresh: Off" size="small" />
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
          <CostCard label="Hourly Burn (Est.)" value={formatUsd(computedCostTotals.estimatedHourly)} />
          <CostCard label="Accrued (Est.)" value={formatUsd(computedCostTotals.estimatedAccrued, 2)} />
          <CostCard
            label={`Actual (Billing)${computedCostTotals.actualDataSource === 'cost-explorer' ? '' : ' - Unavailable'}`}
            value={computedCostTotals.actualTotal !== null ? formatUsd(computedCostTotals.actualTotal, 2) : '-'}
          />
          <CostCard label="Next 24h (Est.)" value={formatUsd(computedCostTotals.estimated24h, 2)} />
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
            <Stack direction={{ xs: 'column', sm: 'row' }} alignItems={{ xs: 'stretch', sm: 'center' }} justifyContent="space-between" spacing={1}>
              <Typography variant="h6" fontWeight={700}>Instances ({sortedInstances.length})</Typography>
              <Stack direction="row" spacing={1}>
                <Button size="small" startIcon={<RefreshRoundedIcon />} onClick={loadSession} variant="outlined" disabled={loading || creatingInstances}>
                  Refresh
                </Button>
                <Button
                  size="small"
                  color="error"
                  variant="contained"
                  startIcon={<DeleteOutlineRoundedIcon />}
                  onClick={handleBatchDelete}
                  disabled={selectedIds.length === 0 || batchDeleting}
                >
                  {batchDeleting ? 'Deleting...' : `Delete Selected (${selectedIds.length})`}
                </Button>
                <Button size="small" onClick={handleCheckHealth} variant="outlined" disabled={checkingHealth || creatingInstances || sortedInstances.length === 0}>
                  {checkingHealth ? 'Checking...' : 'Check Health'}
                </Button>
              </Stack>
            </Stack>
          </CardContent>
          <Box sx={{ position: 'relative' }}>
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
                  <HeaderSort label="Instance ID" sortKey="instance_id" sortConfig={sortConfig} onSort={toggleSort} />
                  <HeaderSort label="Type" sortKey="type" sortConfig={sortConfig} onSort={toggleSort} />
                  <HeaderSort label="EC2 Size" sortKey="ec2_instance_type" sortConfig={sortConfig} onSort={toggleSort} />
                  <HeaderSort label="Created" sortKey="launch_time" sortConfig={sortConfig} onSort={toggleSort} />
                  <HeaderSort label="State" sortKey="state" sortConfig={sortConfig} onSort={toggleSort} />
                  <HeaderSort label="Endpoint" sortKey="endpoint" sortConfig={sortConfig} onSort={toggleSort} />
                  <HeaderSort label="Assigned" sortKey="assigned_to" sortConfig={sortConfig} onSort={toggleSort} />
                  <TableCell>Remaining Days</TableCell>
                  <TableCell>Hourly (Est.)</TableCell>
                  <TableCell>Cost (Est./Actual)</TableCell>
                  {showHealthColumn && <HeaderSort label="Health" sortKey="health_status" sortConfig={sortConfig} onSort={toggleSort} />}
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {loading ? (
                  <TableRow>
                    <TableCell colSpan={showHealthColumn ? 13 : 12} align="center" sx={{ py: 6 }}>
                      <CircularProgress size={24} />
                    </TableCell>
                  </TableRow>
                ) : sortedInstances.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={showHealthColumn ? 13 : 12} align="center" sx={{ py: 6 }}>
                      No instances found
                    </TableCell>
                  </TableRow>
                ) : (
                  sortedInstances.map((instance) => {
                    const costMeta = costByInstanceId.get(instance.instance_id) || getCostMeta(instance, session)
                    const type = instance.type || instance.instance_type || 'pool'
                    const ec2Size = instance.instance_type || DEFAULT_EC2_INSTANCE_TYPE
                    const launchTime = instance.launch_time ? new Date(instance.launch_time).toLocaleString() : '-'
                    const resolvedHttpsDomain = instance.https_domain || instance.tags?.HttpsDomain
                    const resolvedHttpsUrl = resolvedHttpsDomain ? `https://${resolvedHttpsDomain}` : (instance.https_url || instance.tags?.HttpsUrl)
                    const visitUrl = resolvedHttpsUrl || (instance.public_ip ? `http://${instance.public_ip}` : null)
                    const endpointLabel = resolvedHttpsDomain || instance.public_ip || 'Pending...'
                    return (
                      <TableRow key={instance.instance_id} hover>
                        <TableCell padding="checkbox">
                          <Checkbox
                            checked={selectedSet.has(instance.instance_id)}
                            onChange={() => toggleSelected(instance.instance_id)}
                          />
                        </TableCell>
                        <TableCell>{instance.instance_id}</TableCell>
                        <TableCell><Chip size="small" label={type} color={type === 'admin' ? 'secondary' : 'default'} /></TableCell>
                        <TableCell><Chip size="small" label={ec2Size} variant="outlined" /></TableCell>
                        <TableCell><Typography variant="caption">{launchTime}</Typography></TableCell>
                        <TableCell>
                          <Chip
                            size="small"
                            label={instance.state}
                            color={instance.state === 'running' ? 'success' : instance.state === 'stopped' ? 'warning' : 'default'}
                          />
                        </TableCell>
                        <TableCell>
                          {visitUrl ? (
                            <Link href={visitUrl} target="_blank" rel="noopener noreferrer">
                              {endpointLabel}
                            </Link>
                          ) : 'Pending...'}
                        </TableCell>
                        <TableCell>{instance.assigned_to || '-'}</TableCell>
                        <TableCell>
                          {type === 'admin' && instance.cleanup_days_remaining !== null ? (
                            <Stack spacing={0.5}>
                              <Typography variant="body2" fontWeight={600}>{instance.cleanup_days_remaining} days</Typography>
                              {type === 'admin' && instance.state === 'running' && (
                                <Button
                                  size="small"
                                  variant="outlined"
                                  onClick={() => handleExtendDaysClick(instance)}
                                  disabled={updatingCleanupDays}
                                  sx={{ fontSize: '0.7rem', padding: '2px 6px' }}
                                >
                                  Extend
                                </Button>
                              )}
                            </Stack>
                          ) : (
                            '-'
                          )}
                        </TableCell>
                        <TableCell>{formatUsd(costMeta.hourlyEstimate)}</TableCell>
                        <TableCell>
                          <Typography variant="caption" display="block">Est: {formatUsd(costMeta.estimatedCost, 2)}</Typography>
                          <Typography variant="caption" color="text.secondary">Actual: {costMeta.actualCost !== null ? formatUsd(costMeta.actualCost, 2) : '-'}</Typography>
                        </TableCell>
                        {showHealthColumn && <TableCell>{getHealthChip(instance)}</TableCell>}
                        <TableCell align="right">
                          <Stack direction="row" spacing={1} justifyContent="flex-end">
                            {instance.public_ip && !resolvedHttpsUrl && (
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
          {creatingInstances && (
            <Box
              sx={{
                position: 'absolute',
                inset: 0,
                bgcolor: 'rgba(255,255,255,0.7)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                zIndex: 2
              }}
            >
              <Stack direction="row" spacing={1.5} alignItems="center">
                <CircularProgress size={22} />
                <Typography variant="body2" fontWeight={600}>
                  Creating {createProgress?.count || createFormData.count} instance {createProgress?.type || createFormData.type}...
                </Typography>
              </Stack>
            </Box>
          )}
          </Box>
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

              <FormControl fullWidth>
                <InputLabel id="ec2-instance-size-label">EC2 Instance Size</InputLabel>
                <Select
                  labelId="ec2-instance-size-label"
                  value={createFormData.ec2_instance_type}
                  label="EC2 Instance Size"
                  onChange={(event) => setCreateFormData({ ...createFormData, ec2_instance_type: event.target.value })}
                >
                  {EC2_INSTANCE_TYPE_OPTIONS.map((option) => (
                    <MenuItem key={option.value} value={option.value}>
                      {formatEc2OptionLabel(option)}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

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

              <Alert severity={isProductiveTutorial ? 'info' : 'warning'}>
                {isProductiveTutorial
                  ? 'This is a productive tutorial. New instances are always created as On-Demand.'
                  : 'This is a test tutorial. New instances are always created as Spot.'}
              </Alert>

              {!isProductiveTutorial && (
                <>
                  <TextField
                    type="number"
                    label="Spot Max Price ($/hour, optional)"
                    inputProps={{ min: 0.0001, step: 0.0001 }}
                    value={createFormData.spot_max_price}
                    onChange={(event) => setCreateFormData({ ...createFormData, spot_max_price: event.target.value })}
                    helperText={`Default: ${session?.spot_max_price ? `$${session.spot_max_price}` : 'market price'}/h. Leave empty to use tutorial default (typically 2-3x the on-demand price for better availability).`}
                  />
                  <Alert severity="info">
                    Effective spot max price for this request: {createFormData.spot_max_price ? `$${createFormData.spot_max_price}/h` : (session?.spot_max_price ? `$${session.spot_max_price}/h` : 'market price')}
                  </Alert>
                </>
              )}
            </Stack>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setShowCreateForm(false)} disabled={creatingInstances}>Cancel</Button>
            <Button type="submit" variant="contained" disabled={creatingInstances} startIcon={creatingInstances ? <CircularProgress size={16} color="inherit" /> : null}>
              {creatingInstances ? 'Creating...' : 'Create'}
            </Button>
          </DialogActions>
        </Box>
      </Dialog>

      <Dialog open={showExtendDaysModal} onClose={() => setShowExtendDaysModal(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Extend Cleanup Days</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 2 }}>
            <Typography variant="body2">
              Instance: <strong>{extendDaysInstance?.instance_id}</strong>
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Current cleanup days configured: {extendDaysInstance?.cleanup_days || 7} days
            </Typography>
            <TextField
              label="New cleanup days"
              type="number"
              inputProps={{ min: 1, max: 365 }}
              value={extendDaysValue}
              onChange={(e) => setExtendDaysValue(e.target.value)}
              fullWidth
              disabled={updatingCleanupDays}
              helperText="Set between 1 and 365 days. Admin instances will be automatically deleted after this period."
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowExtendDaysModal(false)} disabled={updatingCleanupDays}>
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={handleExtendDaysSave}
            disabled={updatingCleanupDays || !extendDaysValue || extendDaysValue < 1 || extendDaysValue > 365}
          >
            {updatingCleanupDays ? 'Updating...' : 'Update'}
          </Button>
        </DialogActions>
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
            label="Also delete associated EC2 instances and Route53 DNS records"
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

function CostCard({ label, value }) {
  return (
    <Grid item xs={12} sm={6} md={3}>
      <Card>
        <CardContent>
          <Typography variant="overline" color="text.secondary">{label}</Typography>
          <Typography variant="h6" fontWeight={700}>{value}</Typography>
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
