import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '../services/api'
import Header from '../components/Header'
import './TutorialDashboard.css'

function TutorialDashboard() {
  const { workshop, sessionId } = useParams()
  const navigate = useNavigate()
  const [session, setSession] = useState(null)
  const [instances, setInstances] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState({ text: '', type: '' })
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [deleteInstances, setDeleteInstances] = useState(false)
  const [deletingSession, setDeletingSession] = useState(false)
  const [activeFilter, setActiveFilter] = useState(null)
  const [sortConfig, setSortConfig] = useState({ key: null, direction: 'asc' })
  const [createFormData, setCreateFormData] = useState({
    type: 'pool',
    count: 1,
    cleanup_days: 7,
  })

  useEffect(() => {
    loadSession()
    const interval = setInterval(loadSession, 30000) // Auto-refresh every 30s
    return () => clearInterval(interval)
  }, [workshop, sessionId])

  const loadSession = async () => {
    try {
      setLoading(true)
      const response = await api.getTutorialSession(sessionId, workshop)
      if (response.success) {
        setSession(response.session)
        setInstances(response.instances || [])
        setStats(response.stats)
      } else {
        showMessage(`Error: ${response.error}`, 'error')
      }
    } catch (error) {
      showMessage(`Error: ${error.message}`, 'error')
    } finally {
      setLoading(false)
    }
  }

  const showMessage = (text, type) => {
    setMessage({ text, type })
    setTimeout(() => setMessage({ text: '', type: '' }), 5000)
  }

  const handleCreateInstances = async (e) => {
    e.preventDefault()
    try {
      showMessage('Creating instances...', 'success')
      const payload = {
        count: parseInt(createFormData.count),
        type: createFormData.type,
        workshop: workshop,
        tutorial_session_id: sessionId,
      }
      if (createFormData.type === 'admin') {
        payload.cleanup_days = parseInt(createFormData.cleanup_days)
      }
      
      const response = await api.createInstances(payload)
      if (response.success) {
        showMessage(`✅ Created ${response.count} ${createFormData.type} instance(s)`, 'success')
        setShowCreateForm(false)
        loadSession()
        setTimeout(loadSession, 5000)
      } else {
        showMessage(`❌ Error: ${response.error}`, 'error')
      }
    } catch (error) {
      showMessage(`❌ Error: ${error.message}`, 'error')
    }
  }

  const handleDeleteInstance = async (instanceId) => {
    if (!confirm(`Are you sure you want to delete instance ${instanceId}?`)) {
      return
    }
    try {
      const response = await api.deleteInstance(instanceId)
      if (response.success) {
        showMessage(`✅ Instance ${instanceId} deleted`, 'success')
        loadSession()
      } else {
        showMessage(`❌ Error: ${response.error}`, 'error')
      }
    } catch (error) {
      showMessage(`❌ Error: ${error.message}`, 'error')
    }
  }

  const handleEnableHttps = async (instanceId) => {
    try {
      showMessage('Enabling HTTPS...', 'success')
      const response = await api.enableHttps(instanceId)
      if (response.success) {
        showMessage(`✅ HTTPS enabled for ${instanceId}`, 'success')
        loadSession()
      } else {
        showMessage(`❌ Error: ${response.error}`, 'error')
      }
    } catch (error) {
      showMessage(`❌ Error: ${error.message}`, 'error')
    }
  }

  const handleDeleteSession = async (deleteInstances) => {
    try {
      setDeletingSession(true)
      const response = await api.deleteTutorialSession(sessionId, workshop, deleteInstances)
      
      if (response.success) {
        showMessage(`✅ Tutorial session ${sessionId} deleted`, 'success')
        setTimeout(() => {
          navigate('/')
        }, 1500)
      } else {
        showMessage(`❌ Error: ${response.error || 'Failed to delete session'}`, 'error')
        setDeletingSession(false)
      }
    } catch (error) {
      showMessage(`❌ Error: ${error.message || 'Failed to delete session'}`, 'error')
      setDeletingSession(false)
    }
  }

  if (loading && !session) {
    return <div className="tutorial-dashboard"><div className="loading">Loading...</div></div>
  }

  if (!session) {
    return (
      <div className="tutorial-dashboard">
        <div className="error">Session not found</div>
        <button onClick={() => navigate('/')}>Back to Landing</button>
      </div>
    )
  }

  // Filter instances based on active filter
  const filteredInstances = instances.filter(instance => {
    if (!activeFilter) return true
    if (activeFilter === 'running' || activeFilter === 'stopped') {
      return instance.state === activeFilter
    }
    if (activeFilter === 'pool' || activeFilter === 'admin') {
      return instance.type === activeFilter
    }
    return true
  })

  const handleFilterClick = (filterType) => {
    if (activeFilter === filterType) {
      setActiveFilter(null) // Toggle off if already active
    } else {
      setActiveFilter(filterType)
    }
  }

  const handleSort = (key) => {
    let direction = 'asc'
    if (sortConfig.key === key && sortConfig.direction === 'asc') {
      direction = 'desc'
    }
    setSortConfig({ key, direction })
  }

  const sortedInstances = [...filteredInstances].sort((a, b) => {
    if (!sortConfig.key) return 0
    let aVal = a[sortConfig.key] || ''
    let bVal = b[sortConfig.key] || ''
    
    // Handle special cases
    if (sortConfig.key === 'type') {
      aVal = a.type || a.instance_type || ''
      bVal = b.type || b.instance_type || ''
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
        title={session.session_id}
        subtitle={`Workshop: ${session.workshop_name}`}
        showBack={true}
        backPath="/"
      />
      <div className="tutorial-dashboard">

      {message.text && (
        <div className={`message message-${message.type}`}>{message.text}</div>
      )}

      {/* Stats Cards */}
      <div className="stats-grid">
        <div 
          className={`stat-card ${activeFilter === null ? 'active' : ''}`}
          onClick={() => handleFilterClick(null)}
        >
          <div className="stat-value">{stats?.total_instances || 0}</div>
          <div className="stat-label">Total Instances</div>
        </div>
        <div 
          className={`stat-card running ${activeFilter === 'running' ? 'active' : ''}`}
          onClick={() => handleFilterClick('running')}
        >
          <div className="stat-value">{stats?.running || 0}</div>
          <div className="stat-label">Running</div>
        </div>
        <div 
          className={`stat-card stopped ${activeFilter === 'stopped' ? 'active' : ''}`}
          onClick={() => handleFilterClick('stopped')}
        >
          <div className="stat-value">{stats?.stopped || 0}</div>
          <div className="stat-label">Stopped</div>
        </div>
        <div 
          className={`stat-card pool ${activeFilter === 'pool' ? 'active' : ''}`}
          onClick={() => handleFilterClick('pool')}
        >
          <div className="stat-value">{stats?.pool_instances || 0}</div>
          <div className="stat-label">Pool Instances</div>
        </div>
        <div 
          className={`stat-card admin ${activeFilter === 'admin' ? 'active' : ''}`}
          onClick={() => handleFilterClick('admin')}
        >
          <div className="stat-value">{stats?.admin_instances || 0}</div>
          <div className="stat-label">Admin Instances</div>
        </div>
      </div>

      {/* Session Actions */}
      <div className="session-actions">
        <button
          className="delete-session-btn"
          onClick={() => setShowDeleteConfirm(true)}
          disabled={deletingSession}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z" fill="currentColor"/>
          </svg>
          Delete Session
        </button>
      </div>

      {/* Instances Table */}
      <div className="instances-section">
        <div className="instances-header">
          <h2>Instances ({filteredInstances.length})</h2>
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
                  <th className="sortable" onClick={() => handleSort('assigned_to')}>
                    Assigned To
                    {sortConfig.key === 'assigned_to' && (
                      <span className="sort-indicator">{sortConfig.direction === 'asc' ? ' ↑' : ' ↓'}</span>
                    )}
                  </th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {sortedInstances.length === 0 ? (
                  <tr>
                    <td colSpan="6" style={{ textAlign: 'center', padding: '40px' }}>
                      No instances found
                    </td>
                  </tr>
                ) : (
                  sortedInstances.map(instance => (
                    <tr key={instance.instance_id}>
                      <td>{instance.instance_id}</td>
                      <td>
                        <span className={`badge badge-${instance.type || 'pool'}`}>
                          {instance.type || 'pool'}
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
                      <td>{instance.assigned_to || '-'}</td>
                      <td>
                        <div className="action-buttons">
                          {instance.public_ip && !instance.https_url && (
                            <button
                              className="small-btn"
                              onClick={() => handleEnableHttps(instance.instance_id)}
                              disabled={instance.state !== 'running'}
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
                            onClick={() => handleDeleteInstance(instance.instance_id)}
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

      {/* Floating Action Button */}
      <button className="fab" onClick={() => setShowCreateForm(true)} aria-label="Create Instance">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z" fill="currentColor"/>
        </svg>
      </button>

      {/* Create Instance Modal */}
      {showCreateForm && (
        <div className="modal-overlay" onClick={() => setShowCreateForm(false)}>
          <div className="modal-content create-instance-form" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Create Instance</h2>
              <button className="close-btn" onClick={() => setShowCreateForm(false)}>×</button>
            </div>
            <form onSubmit={handleCreateInstances}>
              <div className="form-group">
                <label>Instance Type</label>
                <select
                  value={createFormData.type}
                  onChange={(e) => setCreateFormData({ ...createFormData, type: e.target.value })}
                >
                  <option value="pool">Pool</option>
                  <option value="admin">Admin</option>
                </select>
              </div>
              <div className="form-group">
                <label>Count</label>
                <input
                  type="number"
                  min="1"
                  max="120"
                  value={createFormData.count}
                  onChange={(e) => setCreateFormData({ ...createFormData, count: e.target.value })}
                  required
                />
              </div>
              {createFormData.type === 'admin' && (
                <div className="form-group">
                  <label>Cleanup Days</label>
                  <input
                    type="number"
                    min="1"
                    max="365"
                    value={createFormData.cleanup_days}
                    onChange={(e) => setCreateFormData({ ...createFormData, cleanup_days: e.target.value })}
                    required
                  />
                </div>
              )}
              <div className="form-actions">
                <button type="button" onClick={() => setShowCreateForm(false)} className="secondary">
                  Cancel
                </button>
                <button type="submit">Create</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Session Confirmation Modal */}
      {showDeleteConfirm && (
        <div className="modal-overlay" onClick={() => setShowDeleteConfirm(false)}>
          <div className="modal-content delete-confirm-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Delete Tutorial Session</h2>
              <button className="close-btn" onClick={() => setShowDeleteConfirm(false)}>×</button>
            </div>
            <div className="modal-body">
              <p>Are you sure you want to delete the tutorial session <strong>{sessionId}</strong>?</p>
              {instances.length > 0 && (
                <div className="delete-instance-warning">
                  <p>This session has <strong>{instances.length}</strong> associated instance(s).</p>
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      id="deleteInstances"
                      checked={deleteInstances}
                      onChange={(e) => setDeleteInstances(e.target.checked)}
                    />
                    <span>Also delete all associated EC2 instances</span>
                  </label>
                </div>
              )}
            </div>
            <div className="form-actions">
              <button
                type="button"
                onClick={() => {
                  setShowDeleteConfirm(false)
                  setDeleteInstances(false)
                }}
                className="secondary"
                disabled={deletingSession}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => handleDeleteSession(deleteInstances)}
                className="delete-btn"
                disabled={deletingSession}
              >
                {deletingSession ? 'Deleting...' : 'Delete Session'}
              </button>
            </div>
          </div>
        </div>
      )}
      </div>
    </div>
  )
}

export default TutorialDashboard
