// Use environment variable for API URL, fallback to relative path for backward compatibility
// Production: Set VITE_API_URL=https://ec2-management-api-{environment}.testingfantasy.com/api during build
// Example: VITE_API_URL=https://ec2-management-api-dev.testingfantasy.com/api
// Development: Uses relative /api which proxies through Vite dev server
const API_BASE = import.meta.env.VITE_API_URL || '/api'
const PASSWORD_STORAGE_KEY = 'instance_manager_password'

// Get password from sessionStorage
function getPassword() {
  return sessionStorage.getItem(PASSWORD_STORAGE_KEY) || ''
}

function generateIdempotencyKey() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `req-${Date.now()}-${Math.random().toString(36).slice(2, 12)}`
}

async function apiRequest(endpoint, options = {}) {
  // Get password from sessionStorage or from options
  const password = options.password || getPassword()
  
  // Parse endpoint to check if it already has query params
  const [path, existingQuery] = endpoint.split('?')
  const queryParams = new URLSearchParams(existingQuery || '')
  
  // For GET requests, add password to query params if not already present
  const isGetRequest = !options.method || options.method.toUpperCase() === 'GET'
  if (isGetRequest && password && !queryParams.has('password')) {
    queryParams.append('password', password)
  }
  
  // Reconstruct endpoint with query params
  const url = `${API_BASE}${path}${queryParams.toString() ? '?' + queryParams.toString() : ''}`
  
  // Parse body if it exists, or create new object
  let body = {}
  if (options.body) {
    try {
      body = JSON.parse(options.body)
    } catch (e) {
      body = {}
    }
  }
  
  // For non-GET requests, add password to body if not already present and password exists
  if (!isGetRequest && password && !body.password) {
    body.password = password
  }
  
  // Re-stringify body if it was modified
  const finalBody = Object.keys(body).length > 0 ? JSON.stringify(body) : options.body

  const requestHeaders = {
    'Content-Type': 'application/json',
    ...options.headers,
  }


  const response = await fetch(url, {
    ...options,
    body: finalBody,
    headers: requestHeaders,
  })

  if (!response.ok) {
    // Handle 401 specifically - authentication required
    if (response.status === 401) {
      const error = await response.json().catch(() => ({ error: 'Authentication required' }))
      // Clear stored password on auth failure
      sessionStorage.removeItem(PASSWORD_STORAGE_KEY)
      throw new Error(error.error || 'Authentication required. Please login again.')
    }
    const error = await response.json().catch(() => ({ error: 'Unknown error' }))
    throw new Error(error.error || `HTTP ${response.status}`)
  }

  return response.json()
}

export const api = {
  // Authentication
  login: (password) => apiRequest('/login', {
    method: 'POST',
    body: JSON.stringify({ password }),
  }),

  // Instances
  listInstances: (includeTerminated = false, includeHealth = false, includeActualCosts = false) => {
    const queryParams = new URLSearchParams()
    if (includeTerminated) queryParams.append('include_terminated', 'true')
    if (includeHealth) queryParams.append('include_health', 'true')
    if (includeActualCosts) queryParams.append('include_actual_costs', 'true')
    const query = queryParams.toString()
    return apiRequest(`/list${query ? `?${query}` : ''}`)
  },
  
  createInstances: (data) => {
    const requestPayload = {
      ...data,
      idempotency_key: data?.idempotency_key || generateIdempotencyKey(),
    }
    return apiRequest('/create', {
      method: 'POST',
      body: JSON.stringify(requestPayload),
    })
  },

  assignInstance: (instanceId, studentName) => apiRequest('/assign', {
    method: 'POST',
    body: JSON.stringify({ instance_id: instanceId, student_name: studentName }),
  }),

  deleteInstance: (instanceId) => apiRequest('/delete', {
    method: 'POST',
    body: JSON.stringify({ instance_id: instanceId }),
  }),

  deleteInstances: (instanceIds) => apiRequest('/delete', {
    method: 'POST',
    body: JSON.stringify({ instance_ids: instanceIds }),
  }),

  enableHttps: (instanceId) => apiRequest('/enable_https', {
    method: 'POST',
    body: JSON.stringify({ instance_id: instanceId }),
  }),

  deleteHttps: (instanceId) => apiRequest('/delete_https', {
    method: 'POST',
    body: JSON.stringify({ instance_id: instanceId }),
  }),

  updateCleanupDays: (instanceId, cleanupDays) => apiRequest('/update_cleanup_days', {
    method: 'POST',
    body: JSON.stringify({ instance_id: instanceId, cleanup_days: cleanupDays }),
  }),

  bulkDelete: (deleteType) => apiRequest('/bulk_delete', {
    method: 'POST',
    body: JSON.stringify({ delete_type: deleteType }),
  }),

  // Timeout settings
  getTimeoutSettings: (workshop) => apiRequest(`/timeout_settings?workshop=${workshop}`),
  
  updateTimeoutSettings: (data) => apiRequest('/update_timeout_settings', {
    method: 'POST',
    body: JSON.stringify(data),
  }),

  alwaysOnTutorials: () => apiRequest('/always-on-tutorials'),

  // Workshop templates (accepts optional password parameter for auth check)
  getWorkshopTemplates: (password) => apiRequest('/templates', password ? { password } : {}),

  // Tutorial sessions
  createTutorialSession: (data) => apiRequest('/create_tutorial_session', {
    method: 'POST',
    body: JSON.stringify(data),
  }),

  getTutorialSessions: (workshopName) => apiRequest(`/tutorial_sessions?workshop=${workshopName}`),

  getTutorialSession: (sessionId, workshopName) => apiRequest(`/tutorial_session/${sessionId}?workshop=${workshopName}`),

  deleteTutorialSession: (sessionId, workshopName, deleteInstances = false) => apiRequest(`/tutorial_session/${sessionId}?workshop=${workshopName}&delete_instances=${deleteInstances}`, {
    method: 'DELETE',
  }),

  // List instances with optional tutorial session filter
  listInstancesBySession: (tutorialSessionId, includeHealth = false, includeTerminated = false) => {
    const queryParams = new URLSearchParams({ tutorial_session_id: tutorialSessionId })
    if (includeHealth) queryParams.append('include_health', 'true')
    if (includeTerminated) queryParams.append('include_terminated', 'true')
    return apiRequest(`/list?${queryParams.toString()}`)
  },
}
