import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { api } from '../services/api'
import Header from '../components/Header'
import './WorkshopConfig.css'

function WorkshopConfig() {
  const { name: workshopName } = useParams()
  const navigate = useNavigate()
  const [settings, setSettings] = useState({
    stop_timeout: 4,
    terminate_timeout: 20,
    hard_terminate_timeout: 45,
    admin_cleanup_days: 7,
  })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState({ text: '', type: '' })

  useEffect(() => {
    loadSettings()
  }, [workshopName])

  const loadSettings = async () => {
    try {
      setLoading(true)
      const response = await api.getTimeoutSettings(workshopName)
      if (response.success && response.settings) {
        setSettings(response.settings)
      }
    } catch (error) {
      showMessage(`Error loading settings: ${error.message}`, 'error')
    } finally {
      setLoading(false)
    }
  }

  const saveSettings = async (e) => {
    e.preventDefault()
    try {
      setSaving(true)
      const response = await api.updateTimeoutSettings({
        workshop: workshopName,
        stop_timeout: parseInt(settings.stop_timeout),
        terminate_timeout: parseInt(settings.terminate_timeout),
        hard_terminate_timeout: parseInt(settings.hard_terminate_timeout),
        admin_cleanup_days: parseInt(settings.admin_cleanup_days),
      })
      if (response.success) {
        showMessage(`✅ Settings saved for ${workshopName}`, 'success')
      } else {
        showMessage(`❌ Error: ${response.error}`, 'error')
      }
    } catch (error) {
      showMessage(`❌ Error: ${error.message}`, 'error')
    } finally {
      setSaving(false)
    }
  }

  const showMessage = (text, type) => {
    setMessage({ text, type })
    setTimeout(() => setMessage({ text: '', type: '' }), 5000)
  }

  if (loading) {
    return (
      <div className="config-container">
        <div className="loading">Loading settings...</div>
      </div>
    )
  }

  return (
    <div className="page-container">
      <Header 
        title="Workshop Configuration"
        subtitle={`Workshop: ${workshopName}`}
        showBack={true}
        backPath="/"
        showSettings={false}
      />
      <div className="config-container">

      {message.text && (
        <div className={`message message-${message.type}`}>{message.text}</div>
      )}

      <div className="card">
        <h2>Workshop Timeout Settings (SSM Defaults)</h2>
        <p className="description">
          Configure default timeout values per workshop. These are used when creating instances
          without custom timeout values.
        </p>
        <form onSubmit={saveSettings}>
          <div className="form-group">
            <label>Stop Timeout (minutes):</label>
            <input
              type="number"
              min="1"
              max="1440"
              value={settings.stop_timeout}
              onChange={(e) => setSettings({ ...settings, stop_timeout: e.target.value })}
              required
            />
            <small>Default minutes before stopping unassigned running instances</small>
          </div>
          <div className="form-group">
            <label>Terminate Timeout (minutes):</label>
            <input
              type="number"
              min="1"
              max="1440"
              value={settings.terminate_timeout}
              onChange={(e) => setSettings({ ...settings, terminate_timeout: e.target.value })}
              required
            />
            <small>Default minutes before terminating stopped instances</small>
          </div>
          <div className="form-group">
            <label>Hard Terminate Timeout (minutes):</label>
            <input
              type="number"
              min="1"
              max="10080"
              value={settings.hard_terminate_timeout}
              onChange={(e) => setSettings({ ...settings, hard_terminate_timeout: e.target.value })}
              required
            />
            <small>Default minutes before hard terminating any instance (max: 7 days)</small>
          </div>
          <div className="form-group">
            <label>Admin Cleanup Days:</label>
            <input
              type="number"
              min="1"
              max="365"
              value={settings.admin_cleanup_days}
              onChange={(e) => setSettings({ ...settings, admin_cleanup_days: e.target.value })}
              required
            />
            <small>Default days before admin instances are deleted</small>
          </div>
          <div className="form-actions">
            <button type="submit" disabled={saving}>
              {saving ? 'Saving...' : 'Save Defaults'}
            </button>
            <button type="button" onClick={loadSettings} className="secondary">
              Load Current
            </button>
          </div>
        </form>
      </div>
      </div>
    </div>
  )
}

export default WorkshopConfig
