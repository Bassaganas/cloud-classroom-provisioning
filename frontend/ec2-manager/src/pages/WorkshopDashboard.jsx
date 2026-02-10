import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { api } from '../services/api'
import './WorkshopDashboard.css'

function WorkshopDashboard() {
  const { name: workshopName } = useParams()
  const navigate = useNavigate()
  const [instances, setInstances] = useState([])
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState({ text: '', type: '' })
  const [showTerminated, setShowTerminated] = useState(false)
  
  // Form states
  const [poolCount, setPoolCount] = useState(4)
  const [poolStopTimeout, setPoolStopTimeout] = useState('')
  const [poolTerminateTimeout, setPoolTerminateTimeout] = useState('')
  const [poolHardTerminateTimeout, setPoolHardTerminateTimeout] = useState('')
  
  const [adminCount, setAdminCount] = useState(1)
  const [adminCleanupDays, setAdminCleanupDays] = useState(7)
  const [adminStopTimeout, setAdminStopTimeout] = useState('')
  const [adminTerminateTimeout, setAdminTerminateTimeout] = useState('')
  const [adminHardTerminateTimeout, setAdminHardTerminateTimeout] = useState('')

  useEffect(() => {
    refreshList()
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

  const showMessage = (text, type) => {
    setMessage({ text, type })
    setTimeout(() => setMessage({ text: '', type: '' }), 5000)
  }

  const createPoolInstances = async (e) => {
    e.preventDefault()
    try {
      showMessage('Creating instances...', 'success')
      const payload = {
        count: poolCount,
        type: 'pool',
        workshop: workshopName,
      }
      if (poolStopTimeout) payload.stop_timeout = parseInt(poolStopTimeout)
      if (poolTerminateTimeout) payload.terminate_timeout = parseInt(poolTerminateTimeout)
      if (poolHardTerminateTimeout) payload.hard_terminate_timeout = parseInt(poolHardTerminateTimeout)
      
      const response = await api.createInstances(payload)
      if (response.success) {
        showMessage(`✅ Created ${response.count} pool instance(s)`, 'success')
        refreshList()
        setTimeout(refreshList, 5000)
      } else {
        showMessage(`❌ Error: ${response.error}`, 'error')
      }
    } catch (error) {
      showMessage(`❌ Error: ${error.message}`, 'error')
    }
  }

  const createAdminInstances = async (e) => {
    e.preventDefault()
    try {
      showMessage('Creating instances...', 'success')
      const payload = {
        count: adminCount,
        type: 'admin',
        workshop: workshopName,
        cleanup_days: adminCleanupDays,
      }
      if (adminStopTimeout) payload.stop_timeout = parseInt(adminStopTimeout)
      if (adminTerminateTimeout) payload.terminate_timeout = parseInt(adminTerminateTimeout)
      if (adminHardTerminateTimeout) payload.hard_terminate_timeout = parseInt(adminHardTerminateTimeout)
      
      const response = await api.createInstances(payload)
      if (response.success) {
        showMessage(`✅ Created ${response.count} admin instance(s)`, 'success')
        refreshList()
        setTimeout(refreshList, 5000)
      } else {
        showMessage(`❌ Error: ${response.error}`, 'error')
      }
    } catch (error) {
      showMessage(`❌ Error: ${error.message}`, 'error')
    }
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

  const bulkDelete = async (deleteType) => {
    if (!confirm(`Delete all ${deleteType} instances?`)) return
    try {
      const response = await api.bulkDelete(deleteType)
      if (response.success) {
        showMessage(`✅ Deleted ${response.deleted_count} instance(s)`, 'success')
        refreshList()
      } else {
        showMessage(`❌ Error: ${response.error}`, 'error')
      }
    } catch (error) {
      showMessage(`❌ Error: ${error.message}`, 'error')
    }
  }

  const stats = {
    active: instances.filter(i => ['running', 'stopped'].includes(i.state)).length,
    pool: {
      total: instances.filter(i => i.instance_type === 'pool').length,
      running: instances.filter(i => i.instance_type === 'pool' && i.state === 'running').length,
      stopped: instances.filter(i => i.instance_type === 'pool' && i.state === 'stopped').length,
      assigned: instances.filter(i => i.instance_type === 'pool' && i.assigned).length,
    },
    admin: {
      total: instances.filter(i => i.instance_type === 'admin').length,
      running: instances.filter(i => i.instance_type === 'admin' && i.state === 'running').length,
      stopped: instances.filter(i => i.instance_type === 'admin' && i.state === 'stopped').length,
    },
  }

  return (
    <div className="dashboard-container">
      <header className="dashboard-header">
        <div>
          <h1>🚀 EC2 Instance Manager</h1>
          <p className="subtitle">Workshop: {workshopName}</p>
        </div>
        <div className="header-actions">
          <Link to="/" className="back-link">← Back to Workshops</Link>
          <Link to={`/workshop/${workshopName}/config`} className="config-link">⚙️ Config</Link>
        </div>
      </header>

      {message.text && (
        <div className={`message message-${message.type}`}>{message.text}</div>
      )}

      <div className="summary">
        <div className="summary-card">
          <h3>Active Instances</h3>
          <div className="number">{stats.active}</div>
        </div>
        <div className="summary-card">
          <h3>Pool Instances</h3>
          <div className="number">{stats.pool.total}</div>
          <div className="details">
            Running: {stats.pool.running} | Stopped: {stats.pool.stopped} | Assigned: {stats.pool.assigned}
          </div>
        </div>
        <div className="summary-card">
          <h3>Admin Instances</h3>
          <div className="number">{stats.admin.total}</div>
          <div className="details">
            Running: {stats.admin.running} | Stopped: {stats.admin.stopped}
          </div>
        </div>
      </div>

      <div className="actions">
        <div className="card">
          <h2>Create Pool Instances</h2>
          <form onSubmit={createPoolInstances}>
            <div className="form-group">
              <label>Number of instances:</label>
              <input
                type="number"
                min="1"
                max="120"
                value={poolCount}
                onChange={(e) => setPoolCount(parseInt(e.target.value))}
                required
              />
            </div>
            <div className="form-group">
              <label>Stop Timeout (minutes, optional):</label>
              <input
                type="number"
                min="1"
                max="1440"
                value={poolStopTimeout}
                onChange={(e) => setPoolStopTimeout(e.target.value)}
                placeholder="Uses SSM default"
              />
              <small>Minutes before stopping unassigned running instances</small>
            </div>
            <div className="form-group">
              <label>Terminate Timeout (minutes, optional):</label>
              <input
                type="number"
                min="1"
                max="1440"
                value={poolTerminateTimeout}
                onChange={(e) => setPoolTerminateTimeout(e.target.value)}
                placeholder="Uses SSM default"
              />
              <small>Minutes before terminating stopped instances</small>
            </div>
            <div className="form-group">
              <label>Hard Terminate Timeout (minutes, optional):</label>
              <input
                type="number"
                min="1"
                max="10080"
                value={poolHardTerminateTimeout}
                onChange={(e) => setPoolHardTerminateTimeout(e.target.value)}
                placeholder="Uses SSM default"
              />
              <small>Minutes before hard terminating any instance</small>
            </div>
            <button type="submit">Create Pool</button>
          </form>
        </div>

        <div className="card">
          <h2>Create Admin Instance</h2>
          <form onSubmit={createAdminInstances}>
            <div className="form-group">
              <label>Number of instances:</label>
              <input
                type="number"
                min="1"
                max="5"
                value={adminCount}
                onChange={(e) => setAdminCount(parseInt(e.target.value))}
                required
              />
            </div>
            <div className="form-group">
              <label>Cleanup after (days):</label>
              <input
                type="number"
                min="1"
                max="365"
                value={adminCleanupDays}
                onChange={(e) => setAdminCleanupDays(parseInt(e.target.value))}
                required
              />
              <small>Instances will be automatically deleted after this many days (default: 7)</small>
            </div>
            <div className="form-group">
              <label>Stop Timeout (minutes, optional):</label>
              <input
                type="number"
                min="1"
                max="1440"
                value={adminStopTimeout}
                onChange={(e) => setAdminStopTimeout(e.target.value)}
                placeholder="Uses SSM default"
              />
              <small>Minutes before stopping unassigned running instances</small>
            </div>
            <div className="form-group">
              <label>Terminate Timeout (minutes, optional):</label>
              <input
                type="number"
                min="1"
                max="1440"
                value={adminTerminateTimeout}
                onChange={(e) => setAdminTerminateTimeout(e.target.value)}
                placeholder="Uses SSM default"
              />
              <small>Minutes before terminating stopped instances</small>
            </div>
            <div className="form-group">
              <label>Hard Terminate Timeout (minutes, optional):</label>
              <input
                type="number"
                min="1"
                max="10080"
                value={adminHardTerminateTimeout}
                onChange={(e) => setAdminHardTerminateTimeout(e.target.value)}
                placeholder="Uses SSM default"
              />
              <small>Minutes before hard terminating any instance</small>
            </div>
            <button type="submit">Create Admin</button>
          </form>
        </div>

        <div className="card">
          <h2>Bulk Delete</h2>
          <div className="form-group">
            <label>Delete type:</label>
            <select id="deleteType">
              <option value="pool">All Pool Instances</option>
              <option value="admin">All Admin Instances</option>
              <option value="all">All Instances</option>
            </select>
          </div>
          <button
            className="delete"
            onClick={() => {
              const select = document.getElementById('deleteType')
              bulkDelete(select.value)
            }}
          >
            Delete Selected
          </button>
        </div>
      </div>

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
                  <th>Instance ID</th>
                  <th>Workshop</th>
                  <th>Type</th>
                  <th>State</th>
                  <th>IP Address</th>
                  <th>Assigned To</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {instances.length === 0 ? (
                  <tr>
                    <td colSpan="7" style={{ textAlign: 'center', padding: '40px' }}>
                      No instances found
                    </td>
                  </tr>
                ) : (
                  instances.map(instance => (
                    <tr key={instance.instance_id}>
                      <td>{instance.instance_id}</td>
                      <td>{instance.workshop || 'N/A'}</td>
                      <td>
                        <span className={`badge badge-${instance.instance_type}`}>
                          {instance.instance_type}
                        </span>
                      </td>
                      <td>
                        <span className={`badge badge-${instance.state}`}>
                          {instance.state}
                        </span>
                      </td>
                      <td>{instance.public_ip || '-'}</td>
                      <td>{instance.assigned || '-'}</td>
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
  )
}

export default WorkshopDashboard
