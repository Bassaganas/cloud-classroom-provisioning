import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '../services/api'
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

  const poolInstances = instances.filter(i => i.type === 'pool')
  const adminInstances = instances.filter(i => i.type === 'admin')
  const runningInstances = instances.filter(i => i.state === 'running')
  const stoppedInstances = instances.filter(i => i.state === 'stopped')

  return (
    <div className="tutorial-dashboard">
      <header className="dashboard-header">
        <div>
          <button className="back-btn" onClick={() => navigate('/')}>← Back</button>
          <h1>{session.session_id}</h1>
          <p className="subtitle">Workshop: {session.workshop_name}</p>
        </div>
        <button className="create-instance-btn" onClick={() => setShowCreateForm(true)}>
          ➕ Create Instance
        </button>
      </header>

      {message.text && (
        <div className={`message message-${message.type}`}>{message.text}</div>
      )}

      {/* Stats Cards */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-value">{stats?.total_instances || 0}</div>
          <div className="stat-label">Total Instances</div>
        </div>
        <div className="stat-card running">
          <div className="stat-value">{stats?.running || 0}</div>
          <div className="stat-label">Running</div>
        </div>
        <div className="stat-card stopped">
          <div className="stat-value">{stats?.stopped || 0}</div>
          <div className="stat-label">Stopped</div>
        </div>
        <div className="stat-card pool">
          <div className="stat-value">{stats?.pool_instances || 0}</div>
          <div className="stat-label">Pool Instances</div>
        </div>
        <div className="stat-card admin">
          <div className="stat-value">{stats?.admin_instances || 0}</div>
          <div className="stat-label">Admin Instances</div>
        </div>
      </div>

      {/* Instance Lists */}
      <div className="instances-container">
        <div className="instances-column">
          <h2>Pool Instances ({poolInstances.length})</h2>
          <div className="instances-list">
            {poolInstances.length === 0 ? (
              <div className="no-instances">No pool instances</div>
            ) : (
              poolInstances.map(instance => (
                <InstanceCard
                  key={instance.instance_id}
                  instance={instance}
                  onDelete={handleDeleteInstance}
                  onEnableHttps={handleEnableHttps}
                />
              ))
            )}
          </div>
        </div>

        <div className="instances-column">
          <h2>Admin Instances ({adminInstances.length})</h2>
          <div className="instances-list">
            {adminInstances.length === 0 ? (
              <div className="no-instances">No admin instances</div>
            ) : (
              adminInstances.map(instance => (
                <InstanceCard
                  key={instance.instance_id}
                  instance={instance}
                  onDelete={handleDeleteInstance}
                  onEnableHttps={handleEnableHttps}
                />
              ))
            )}
          </div>
        </div>
      </div>

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
    </div>
  )
}

function InstanceCard({ instance, onDelete, onEnableHttps }) {
  const stateColors = {
    running: '#4caf50',
    stopped: '#ff9800',
    pending: '#2196f3',
    stopping: '#ff9800',
    starting: '#2196f3',
    terminated: '#999',
  }

  return (
    <div className="instance-card">
      <div className="instance-header">
        <div className="instance-id">{instance.instance_id}</div>
        <span
          className="instance-state"
          style={{ color: stateColors[instance.state] || '#666' }}
        >
          {instance.state}
        </span>
      </div>
      <div className="instance-details">
        {instance.public_ip && (
          <div className="instance-detail">
            <span className="detail-label">IP:</span>
            <span className="detail-value">{instance.public_ip}</span>
          </div>
        )}
        {instance.assigned_to && (
          <div className="instance-detail">
            <span className="detail-label">Assigned to:</span>
            <span className="detail-value">{instance.assigned_to}</span>
          </div>
        )}
        {instance.cleanup_days_remaining !== null && instance.cleanup_days_remaining !== undefined && (
          <div className="instance-detail">
            <span className="detail-label">Cleanup in:</span>
            <span className="detail-value">{instance.cleanup_days_remaining} days</span>
          </div>
        )}
      </div>
      <div className="instance-actions">
        <button
          className="action-btn enable-https-btn"
          onClick={() => onEnableHttps(instance.instance_id)}
          disabled={instance.state !== 'running'}
        >
          Enable HTTPS
        </button>
        <button
          className="action-btn delete-btn"
          onClick={() => onDelete(instance.instance_id)}
        >
          Delete
        </button>
      </div>
    </div>
  )
}

export default TutorialDashboard
