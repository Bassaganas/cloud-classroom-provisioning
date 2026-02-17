import express from 'express'
import cors from 'cors'
import { 
  MOCK_PASSWORD, 
  workshopTemplates, 
  timeoutSettings, 
  state, 
  initializeMockData,
  generateInstanceId,
  generateIP
} from './mockData.js'

const app = express()
const PORT = process.env.PORT || 3001

// Middleware
app.use(cors())
app.use(express.json())

// Initialize mock data
initializeMockData()

// Helper function to check authentication
function checkAuth(req, res, next) {
  const password = req.query.password || req.body.password
  if (password === MOCK_PASSWORD) {
    next()
  } else {
    res.status(401).json({ success: false, error: 'Invalid password' })
  }
}

// Helper function to simulate delay
function delay(ms = 300) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

// ==================== AUTHENTICATION ====================

app.post('/api/login', async (req, res) => {
  await delay()
  const { password } = req.body
  if (password === MOCK_PASSWORD) {
    res.json({ success: true, message: 'Login successful' })
  } else {
    res.status(401).json({ success: false, error: 'Invalid password' })
  }
})

// ==================== WORKSHOP TEMPLATES ====================

app.get('/api/templates', checkAuth, async (req, res) => {
  await delay()
  res.json({
    success: true,
    templates: workshopTemplates
  })
})

// ==================== INSTANCES ====================

app.get('/api/list', checkAuth, async (req, res) => {
  await delay()
  const { include_terminated, tutorial_session_id, workshop } = req.query
  
  let instances = [...state.instances]
  
  // Filter by tutorial session if provided
  if (tutorial_session_id) {
    instances = instances.filter(i => i.tutorial_session_id === tutorial_session_id)
  }
  
  // Filter by workshop if provided
  if (workshop) {
    instances = instances.filter(i => i.workshop === workshop)
  }
  
  // Filter terminated instances
  if (include_terminated !== 'true') {
    instances = instances.filter(i => i.state !== 'terminated')
  }
  
  res.json({
    success: true,
    instances: instances
  })
})

app.post('/api/create', checkAuth, async (req, res) => {
  await delay(500)
  const { count, type, workshop, tutorial_session_id, cleanup_days } = req.body
  
  const newInstances = []
  for (let i = 0; i < (count || 1); i++) {
    const instance = {
      instance_id: generateInstanceId(),
      instance_type: 't3.medium',
      state: 'running',
      public_ip: generateIP(),
      private_ip: `10.0.1.${50 + state.instanceCounter}`,
      type: type || 'pool',
      workshop: workshop || 'fellowship',
      tutorial_session_id: tutorial_session_id || null,
      assigned_to: null,
      created_at: new Date().toISOString(),
      https_url: null,
      cleanup_days: type === 'admin' ? (cleanup_days || 7) : null
    }
    state.instances.push(instance)
    newInstances.push(instance)
    state.instanceCounter++
  }
  
  res.json({
    success: true,
    count: newInstances.length,
    instances: newInstances
  })
})

app.post('/api/assign', checkAuth, async (req, res) => {
  await delay()
  const { instance_id, student_name } = req.body
  
  const instance = state.instances.find(i => i.instance_id === instance_id)
  if (!instance) {
    return res.status(404).json({ success: false, error: 'Instance not found' })
  }
  
  instance.assigned_to = student_name
  
  res.json({
    success: true,
    message: `Instance ${instance_id} assigned to ${student_name}`
  })
})

app.post('/api/delete', checkAuth, async (req, res) => {
  await delay(500)
  const { instance_id, instance_ids, delete_type } = req.body
  
  let deletedCount = 0
  
  if (delete_type === 'all') {
    deletedCount = state.instances.length
    state.instances.forEach(inst => {
      inst.state = 'terminated'
    })
  } else if (delete_type === 'pool') {
    state.instances.forEach(inst => {
      if (inst.type === 'pool') {
        inst.state = 'terminated'
        deletedCount++
      }
    })
  } else if (delete_type === 'admin') {
    state.instances.forEach(inst => {
      if (inst.type === 'admin') {
        inst.state = 'terminated'
        deletedCount++
      }
    })
  } else {
    const idsToDelete = instance_ids || (instance_id ? [instance_id] : [])
    idsToDelete.forEach(id => {
      const instance = state.instances.find(i => i.instance_id === id)
      if (instance) {
        instance.state = 'terminated'
        deletedCount++
      }
    })
  }
  
  res.json({
    success: true,
    count: deletedCount,
    message: `Initiated deletion of ${deletedCount} instance(s). Termination is in progress.`
  })
})

app.post('/api/enable_https', checkAuth, async (req, res) => {
  await delay(1000)
  const { instance_id } = req.body
  
  const instance = state.instances.find(i => i.instance_id === instance_id)
  if (!instance) {
    return res.status(404).json({ success: false, error: 'Instance not found' })
  }
  
  instance.https_url = `https://${instance.workshop}-${instance.instance_id.substring(2, 8)}.testingfantasy.com`
  
  res.json({
    success: true,
    https_url: instance.https_url,
    message: `HTTPS enabled for instance ${instance_id}`
  })
})

app.post('/api/delete_https', checkAuth, async (req, res) => {
  await delay(500)
  const { instance_id } = req.body
  
  const instance = state.instances.find(i => i.instance_id === instance_id)
  if (!instance) {
    return res.status(404).json({ success: false, error: 'Instance not found' })
  }
  
  instance.https_url = null
  
  res.json({
    success: true,
    message: `HTTPS disabled for instance ${instance_id}`
  })
})

app.post('/api/update_cleanup_days', checkAuth, async (req, res) => {
  await delay()
  const { instance_id, cleanup_days } = req.body
  
  const instance = state.instances.find(i => i.instance_id === instance_id)
  if (!instance) {
    return res.status(404).json({ success: false, error: 'Instance not found' })
  }
  
  instance.cleanup_days = cleanup_days
  
  res.json({
    success: true,
    message: `Cleanup days updated for instance ${instance_id}`
  })
})

app.post('/api/bulk_delete', checkAuth, async (req, res) => {
  await delay(500)
  const { delete_type } = req.body
  
  let deletedCount = 0
  
  if (delete_type === 'pool') {
    state.instances.forEach(inst => {
      if (inst.type === 'pool') {
        inst.state = 'terminated'
        deletedCount++
      }
    })
  } else if (delete_type === 'admin') {
    state.instances.forEach(inst => {
      if (inst.type === 'admin') {
        inst.state = 'terminated'
        deletedCount++
      }
    })
  }
  
  res.json({
    success: true,
    count: deletedCount,
    message: `Initiated deletion of ${deletedCount} instance(s). Termination is in progress.`
  })
})

// ==================== TIMEOUT SETTINGS ====================

app.get('/api/timeout_settings', checkAuth, async (req, res) => {
  await delay()
  const { workshop } = req.query
  
  if (!workshop) {
    return res.status(400).json({ success: false, error: 'workshop parameter is required' })
  }
  
  const settings = timeoutSettings[workshop] || {
    stop_timeout: 4,
    terminate_timeout: 20,
    hard_terminate_timeout: 45,
    admin_cleanup_days: 7
  }
  
  res.json({
    success: true,
    settings: settings
  })
})

app.post('/api/update_timeout_settings', checkAuth, async (req, res) => {
  await delay()
  const { workshop, stop_timeout, terminate_timeout, hard_terminate_timeout, admin_cleanup_days } = req.body
  
  if (!workshop) {
    return res.status(400).json({ success: false, error: 'workshop parameter is required' })
  }
  
  if (!timeoutSettings[workshop]) {
    timeoutSettings[workshop] = {}
  }
  
  timeoutSettings[workshop] = {
    stop_timeout: stop_timeout || timeoutSettings[workshop].stop_timeout || 4,
    terminate_timeout: terminate_timeout || timeoutSettings[workshop].terminate_timeout || 20,
    hard_terminate_timeout: hard_terminate_timeout || timeoutSettings[workshop].hard_terminate_timeout || 45,
    admin_cleanup_days: admin_cleanup_days || timeoutSettings[workshop].admin_cleanup_days || 7
  }
  
  res.json({
    success: true,
    message: `Settings updated for ${workshop}`,
    settings: timeoutSettings[workshop]
  })
})

// ==================== TUTORIAL SESSIONS ====================

app.post('/api/create_tutorial_session', checkAuth, async (req, res) => {
  await delay(800)
  const { session_id, workshop, pool_count, admin_count, admin_cleanup_days } = req.body
  
  if (!session_id || !workshop) {
    return res.status(400).json({ success: false, error: 'session_id and workshop are required' })
  }
  
  // Create tutorial session
  const session = {
    session_id: session_id,
    workshop_name: workshop,
    created_at: new Date().toISOString(),
    status: 'active',
    expected_instance_count: (pool_count || 0) + (admin_count || 0),
    actual_instance_count: 0
  }
  
  if (!state.tutorialSessions[workshop]) {
    state.tutorialSessions[workshop] = []
  }
  state.tutorialSessions[workshop].push(session)
  
  // Create instances for the session
  const createdInstances = []
  
  // Create pool instances
  for (let i = 0; i < (pool_count || 0); i++) {
    const instance = {
      instance_id: generateInstanceId(),
      instance_type: 't3.medium',
      state: 'running',
      public_ip: generateIP(),
      private_ip: `10.0.1.${50 + state.instanceCounter}`,
      type: 'pool',
      workshop: workshop,
      tutorial_session_id: session_id,
      assigned_to: null,
      created_at: new Date().toISOString(),
      https_url: null,
      cleanup_days: null
    }
    state.instances.push(instance)
    createdInstances.push(instance)
    state.instanceCounter++
  }
  
  // Create admin instances
  for (let i = 0; i < (admin_count || 0); i++) {
    const instance = {
      instance_id: generateInstanceId(),
      instance_type: 't3.medium',
      state: 'running',
      public_ip: generateIP(),
      private_ip: `10.0.1.${50 + state.instanceCounter}`,
      type: 'admin',
      workshop: workshop,
      tutorial_session_id: session_id,
      assigned_to: null,
      created_at: new Date().toISOString(),
      https_url: null,
      cleanup_days: admin_cleanup_days || 7
    }
    state.instances.push(instance)
    createdInstances.push(instance)
    state.instanceCounter++
  }
  
  session.actual_instance_count = createdInstances.length
  
  res.json({
    success: true,
    session: session,
    instances: createdInstances,
    message: `Tutorial session ${session_id} created with ${createdInstances.length} instances`
  })
})

app.get('/api/tutorial_sessions', checkAuth, async (req, res) => {
  await delay()
  const { workshop } = req.query
  
  if (!workshop) {
    return res.status(400).json({ success: false, error: 'workshop parameter is required' })
  }
  
  const sessions = state.tutorialSessions[workshop] || []
  
  res.json({
    success: true,
    sessions: sessions
  })
})

app.get('/api/tutorial_session/:sessionId', checkAuth, async (req, res) => {
  await delay()
  const { sessionId } = req.params
  const { workshop } = req.query
  
  if (!workshop) {
    return res.status(400).json({ success: false, error: 'workshop parameter is required' })
  }
  
  const sessions = state.tutorialSessions[workshop] || []
  const session = sessions.find(s => s.session_id === sessionId)
  
  if (!session) {
    return res.status(404).json({ success: false, error: 'Session not found' })
  }
  
  // Get instances for this session
  const instances = state.instances.filter(i => i.tutorial_session_id === sessionId)
  
  // Calculate stats
  const stats = {
    total_instances: instances.length,
    running: instances.filter(i => i.state === 'running').length,
    stopped: instances.filter(i => i.state === 'stopped').length,
    pool_instances: instances.filter(i => i.type === 'pool').length,
    admin_instances: instances.filter(i => i.type === 'admin').length
  }
  
  res.json({
    success: true,
    session: session,
    instances: instances,
    stats: stats
  })
})

app.delete('/api/tutorial_session/:sessionId', checkAuth, async (req, res) => {
  await delay(500)
  const { sessionId } = req.params
  const { workshop, delete_instances } = req.query
  
  if (!workshop) {
    return res.status(400).json({ success: false, error: 'workshop parameter is required' })
  }
  
  const sessions = state.tutorialSessions[workshop] || []
  const sessionIndex = sessions.findIndex(s => s.session_id === sessionId)
  
  if (sessionIndex === -1) {
    return res.status(404).json({ success: false, error: 'Session not found' })
  }
  
  // Delete instances if requested
  if (delete_instances === 'true') {
    const instancesToDelete = state.instances.filter(i => i.tutorial_session_id === sessionId)
    instancesToDelete.forEach(inst => {
      inst.state = 'terminated'
    })
  }
  
  // Remove session
  sessions.splice(sessionIndex, 1)
  
  res.json({
    success: true,
    message: `Session ${sessionId} deleted`,
    instances_deleted: delete_instances === 'true'
  })
})

// Health check endpoint
app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', message: 'Mock API server is running' })
})

// Start server
app.listen(PORT, () => {
  console.log(`🚀 Mock API server running on http://localhost:${PORT}`)
  console.log(`📝 Default password: ${MOCK_PASSWORD}`)
  console.log(`🔗 API endpoints available at http://localhost:${PORT}/api/*`)
})
