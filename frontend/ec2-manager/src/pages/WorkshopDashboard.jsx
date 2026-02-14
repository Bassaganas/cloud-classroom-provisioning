import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { api } from '../services/api'
import Header from '../components/Header'
import './WorkshopDashboard.css'

function WorkshopDashboard() {
  const { name: workshopName } = useParams()
  const navigate = useNavigate()
  const [instances, setInstances] = useState([])
  const [loading, setLoading] = useState(true)
  const [settings, setSettings] = useState(null)
  const [settingsLoading, setSettingsLoading] = useState(true)
  const [message, setMessage] = useState({ text: '', type: '' })
  const [showTerminated, setShowTerminated] = useState(false)
  const [sortConfig, setSortConfig] = useState({ key: null, direction: 'asc' })

  useEffect(() => {
    refreshList()
    loadSettings()
    const interval = setInterval(refreshList, 30000) // Auto-refresh every 30s
    return () => clearInterval(interval)
  }, [workshopName, showTerminated])

  const refreshList = async () => {
    try {
      const response = await api.listInstances()
      if (response.success) {
        let filtered = response.instances || []
        if (!showTerminated) {
          filtered = filtered.filter(i => i.state !== 'terminated')
        }
        // Filter by workshop if needed
        const workshopInstances = filtered.filter(i => 
          i.workshop === workshopName || !i.workshop
        )
        setInstances(workshopInstances)
      }
    } catch (error) {
      showMessage(`Error: ${error.message}`, 'error')
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
      console.error('Error loading settings:', error)
    } finally {
      setSettingsLoading(false)
    }
  }

  const showMessage = (text, type) => {
    setMessage({ text, type })
    setTimeout(() => setMessage({ text: '', type: '' }), 5000)
  }

  const deleteInstance = async (instanceId) => {
    if (!confirm(`Delete instance ${instanceId}?`)) return
    try {
      const response = await api.deleteInstance(instanceId)
      if (response.success) {
        showMessage('✅ Instance deleted', 'success')
        refreshList()
      } else {
        showMessage(`❌ Error: ${response.error}`, 'error')
      }
    } catch (error) {
      showMessage(`❌ Error: ${error.message}`, 'error')
    }
  }

  const assignInstance = async (instanceId) => {
    const studentName = prompt(`Enter student name to assign instance ${instanceId}:`)
    if (!studentName || !studentName.trim()) return
    try {
      const response = await api.assignInstance(instanceId, studentName.trim())
      if (response.success) {
        showMessage(`✅ Instance assigned to ${studentName}`, 'success')
        refreshList()
      } else {
        showMessage(`❌ Error: ${response.error}`, 'error')
      }
    } catch (error) {
      showMessage(`❌ Error: ${error.message}`, 'error')
    }
  }

  const handleSort = (key) => {
    let direction = 'asc'
    if (sortConfig.key === key && sortConfig.direction === 'asc') {
      direction = 'desc'
    }
    setSortConfig({ key, direction })
  }

  const sortedInstances = [...instances].sort((a, b) => {
    if (!sortConfig.key) return 0
    let aVal = a[sortConfig.key] || ''
    let bVal = b[sortConfig.key] || ''
    
    // Handle special cases
    if (sortConfig.key === 'type') {
      aVal = a.type || a.instance_type || ''
      bVal = b.type || b.instance_type || ''
    }
    if (sortConfig.key === 'assigned') {
      aVal = a.assigned || a.assigned_to || ''
      bVal = b.assigned || b.assigned_to || ''
    }
    
    // Convert to string for comparison
    aVal = String(aVal).toLowerCase()
    bVal = String(bVal).toLowerCase()
    
    if (sortConfig.direction === 'asc') {
      return aVal > bVal ? 1 : aVal < bVal ? -1 : 0
    }
    return aVal < bVal ? 1 : aVal > bVal ? -1 : 0
  })

  return (
    <div className="page-container">
      <Header 
        title={workshopName}
        showBack={true}
        backPath="/"
        showSettings={true}
        settingsPath={`/workshop/${workshopName}/config`}
      />
      <div className="dashboard-container">

      {message.text && (
        <div className={`message message-${message.type}`}>{message.text}</div>
      )}

      {/* Settings Display */}
      {settingsLoading ? (
        <div className="card">
          <div className="loading">Loading settings...</div>
        </div>
      ) : settings && (
        <div className="card settings-display">
          <h2>Workshop Timeout Settings</h2>
          <div className="settings-grid">
            <div className="setting-item">
              <span className="setting-label">Stop Timeout:</span>
              <span className="setting-value">{settings.stop_timeout} minutes</span>
            </div>
            <div className="setting-item">
              <span className="setting-label">Terminate Timeout:</span>
              <span className="setting-value">{settings.terminate_timeout} minutes</span>
            </div>
            <div className="setting-item">
              <span className="setting-label">Hard Terminate Timeout:</span>
              <span className="setting-value">{settings.hard_terminate_timeout} minutes</span>
            </div>
            <div className="setting-item">
              <span className="setting-label">Admin Cleanup Days:</span>
              <span className="setting-value">{settings.admin_cleanup_days} days</span>
            </div>
          </div>
        </div>
      )}

      <div className="instances-section">
        <div className="instances-header">
          <h2>Instances</h2>
          <div className="instances-controls">
            <label>
              <input
                type="checkbox"
                checked={showTerminated}
                onChange={(e) => setShowTerminated(e.target.checked)}
              />
              Show terminated instances
            </label>
            <button className="refresh-btn" onClick={refreshList}>🔄 Refresh</button>
          </div>
        </div>

        {loading ? (
          <div className="loading">Loading instances...</div>
        ) : (
          <div className="instances-table">
            <table>
              <thead>
                <tr>
                  <th className="sortable" onClick={() => handleSort('instance_id')}>
                    Instance ID
                    {sortConfig.key === 'instance_id' && (
                      <span className="sort-indicator">{sortConfig.direction === 'asc' ? ' ↑' : ' ↓'}</span>
                    )}
                  </th>
                  <th className="sortable" onClick={() => handleSort('workshop')}>
                    Workshop
                    {sortConfig.key === 'workshop' && (
                      <span className="sort-indicator">{sortConfig.direction === 'asc' ? ' ↑' : ' ↓'}</span>
                    )}
                  </th>
                  <th className="sortable" onClick={() => handleSort('type')}>
                    Type
                    {sortConfig.key === 'type' && (
                      <span className="sort-indicator">{sortConfig.direction === 'asc' ? ' ↑' : ' ↓'}</span>
                    )}
                  </th>
                  <th className="sortable" onClick={() => handleSort('state')}>
                    State
                    {sortConfig.key === 'state' && (
                      <span className="sort-indicator">{sortConfig.direction === 'asc' ? ' ↑' : ' ↓'}</span>
                    )}
                  </th>
                  <th className="sortable" onClick={() => handleSort('public_ip')}>
                    IP Address
                    {sortConfig.key === 'public_ip' && (
                      <span className="sort-indicator">{sortConfig.direction === 'asc' ? ' ↑' : ' ↓'}</span>
                    )}
                  </th>
                  <th className="sortable" onClick={() => handleSort('assigned')}>
                    Assigned To
                    {sortConfig.key === 'assigned' && (
                      <span className="sort-indicator">{sortConfig.direction === 'asc' ? ' ↑' : ' ↓'}</span>
                    )}
                  </th>
                  <th className="sortable" onClick={() => handleSort('tutorial_session_id')}>
                    Tutorial Session
                    {sortConfig.key === 'tutorial_session_id' && (
                      <span className="sort-indicator">{sortConfig.direction === 'asc' ? ' ↑' : ' ↓'}</span>
                    )}
                  </th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {sortedInstances.length === 0 ? (
                  <tr>
                    <td colSpan="8" style={{ textAlign: 'center', padding: '40px' }}>
                      No instances found
                    </td>
                  </tr>
                ) : (
                  sortedInstances.map(instance => (
                    <tr key={instance.instance_id}>
                      <td>{instance.instance_id}</td>
                      <td>{instance.workshop || 'N/A'}</td>
                      <td>
                        <span className={`badge badge-${instance.instance_type || 'pool'}`}>
                          {instance.instance_type || 'pool'}
                        </span>
                      </td>
                      <td>
                        <span className={`badge badge-${instance.state}`}>
                          {instance.state}
                        </span>
                      </td>
                      <td>
                        {instance.public_ip ? (
                          <a 
                            href={`http://${instance.public_ip}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="ip-link"
                          >
                            {instance.public_ip}
                          </a>
                        ) : (
                          '-'
                        )}
                      </td>
                      <td>{instance.assigned || '-'}</td>
                      <td>
                        {instance.tutorial_session_id ? (
                          <a
                            href={`/tutorial/${instance.workshop || workshopName}/${instance.tutorial_session_id}`}
                            className="tutorial-session-link"
                            onClick={(e) => {
                              e.preventDefault()
                              navigate(`/tutorial/${instance.workshop || workshopName}/${instance.tutorial_session_id}`)
                            }}
                          >
                            <span className="badge badge-tutorial">
                              {instance.tutorial_session_id}
                            </span>
                          </a>
                        ) : (
                          '-'
                        )}
                      </td>
                      <td>
                        <div className="action-buttons">
                          {!instance.assigned && instance.instance_type === 'pool' && (
                            <button
                              className="small-btn"
                              onClick={() => assignInstance(instance.instance_id)}
                            >
                              Assign
                            </button>
                          )}
                          {instance.public_ip && !instance.https_url && (
                            <button
                              className="small-btn"
                              onClick={async () => {
                                try {
                                  await api.enableHttps(instance.instance_id)
                                  showMessage('✅ HTTPS enabled', 'success')
                                  refreshList()
                                } catch (error) {
                                  showMessage(`❌ Error: ${error.message}`, 'error')
                                }
                              }}
                            >
                              Enable HTTPS
                            </button>
                          )}
                          {instance.https_url && (
                            <a
                              href={instance.https_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="small-btn link-btn"
                            >
                              Open HTTPS
                            </a>
                          )}
                          <button
                            className="small-btn delete"
                            onClick={() => deleteInstance(instance.instance_id)}
                          >
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
      </div>
    </div>
  )
}

export default WorkshopDashboard
