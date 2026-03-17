/**
 * Health Check Configuration per Workshop
 * 
 * This configuration determines whether instances should report their status
 * based on EC2 instance state alone, or if they should also check for
 * responsive health endpoints.
 * 
 * Workshop-level configuration allows flexibility without code changes when
 * adding new workshops or modifying health check strategies.
 */

export const HEALTH_CHECK_CONFIG = {
  /**
   * Fellowship workshop - checks /api/health endpoint on port 5000
   * @example fellowship: { enabled: true, endpoint: '/api/health', port: 5000, timeout: 2000 }
   */
  fellowship: {
    enabled: false, // Set to true to enable health checks
    endpoint: '/api/health',
    port: 5000,
    timeout: 2000, // milliseconds
    description: 'Checks Fellowship SUT health endpoint'
  },

  /**
   * Testus Patronus workshop
   */
  testus_patronus: {
    enabled: false,
    endpoint: '/health',
    port: 5000,
    timeout: 2000,
    description: 'Checks TP health endpoint'
  },

  /**
   * Default configuration for unknown workshops
   */
  default: {
    enabled: false,
    endpoint: '/health',
    port: 5000,
    timeout: 2000,
    description: 'Default health check endpoint'
  }
}

/**
 * Get health check configuration for a workshop
 * @param {string} workshopName - Name of the workshop
 * @returns {Object} Health check configuration
 */
export function getHealthCheckConfig(workshopName) {
  return HEALTH_CHECK_CONFIG[workshopName] || HEALTH_CHECK_CONFIG.default
}

/**
 * Check instance health via HTTP endpoint
 * @param {string} ipAddress - Instance IP address
 * @param {Object} config - Health check configuration
 * @returns {Promise<Object>} { status: 'healthy' | 'unreachable', lastChecked: ISO8601 }
 */
export async function checkInstanceHealth(ipAddress, config) {
  if (!config.enabled) {
    return { status: 'unconfigured', lastChecked: new Date().toISOString() }
  }

  try {
    const url = `http://${ipAddress}:${config.port}${config.endpoint}`
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), config.timeout)

    const response = await fetch(url, {
      method: 'GET',
      signal: controller.signal,
      headers: { 'Accept': 'application/json' }
    })

    clearTimeout(timeout)

    if (response.ok) {
      return {
        status: 'healthy',
        statusCode: response.status,
        lastChecked: new Date().toISOString()
      }
    } else {
      return {
        status: 'unhealthy',
        statusCode: response.status,
        lastChecked: new Date().toISOString()
      }
    }
  } catch (error) {
    return {
      status: 'unreachable',
      error: error.message,
      lastChecked: new Date().toISOString()
    }
  }
}

/**
 * Get visual representation of health status
 * @param {string} status - Health status from checkInstanceHealth
 * @returns {Object} { color, icon, label }
 */
export function getHealthStatusDisplay(status) {
  const statusMap = {
    healthy: { color: 'success', label: '✓ Healthy' },
    unhealthy: { color: 'warning', label: '⚠ Unhealthy' },
    unreachable: { color: 'error', label: '✕ Unreachable' },
    unconfigured: { color: 'default', label: 'Not configured' },
    checking: { color: 'info', label: '⟳ Checking...' }
  }
  return statusMap[status] || statusMap.unconfigured
}

export default HEALTH_CHECK_CONFIG
