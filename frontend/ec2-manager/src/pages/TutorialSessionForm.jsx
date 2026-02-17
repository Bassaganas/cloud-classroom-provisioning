import { useState } from 'react'
import './TutorialSessionForm.css'

function TutorialSessionForm({ workshopName, onClose, onSuccess }) {
  const [formData, setFormData] = useState({
    session_id: '',
    pool_count: 1,
    admin_count: 0,
    admin_cleanup_days: 7,
  })
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    
    if (!formData.session_id.trim()) {
      setError('Session ID is required')
      return
    }

    if (formData.pool_count < 0 || formData.admin_count < 0) {
      setError('Counts must be non-negative')
      return
    }

    if (formData.pool_count === 0 && formData.admin_count === 0) {
      setError('At least one pool or admin instance must be created')
      return
    }

    try {
      setSubmitting(true)
      const { api } = await import('../services/api')
      const response = await api.createTutorialSession({
        session_id: formData.session_id.trim(),
        workshop_name: workshopName,
        pool_count: parseInt(formData.pool_count),
        admin_count: parseInt(formData.admin_count),
        admin_cleanup_days: parseInt(formData.admin_cleanup_days),
      })

      if (response.success) {
        onSuccess && onSuccess(response.session)
        onClose()
      } else {
        setError(response.error || 'Failed to create tutorial session')
      }
    } catch (err) {
      setError(err.message || 'Failed to create tutorial session')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content tutorial-session-form" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Start New Tutorial Session</h2>
          <button className="close-btn" onClick={onClose}>×</button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="session_id">Session ID *</label>
            <input
              id="session_id"
              type="text"
              value={formData.session_id}
              onChange={(e) => setFormData({ ...formData, session_id: e.target.value })}
              placeholder="e.g., tutorial_001, session_2024_01"
              required
              disabled={submitting}
            />
            <small>Unique identifier for this tutorial session</small>
          </div>

          <div className="form-group">
            <label htmlFor="pool_count">Pool Instances</label>
            <input
              id="pool_count"
              type="number"
              min="0"
              max="120"
              value={formData.pool_count}
              onChange={(e) => setFormData({ ...formData, pool_count: e.target.value })}
              required
              disabled={submitting}
            />
            <small>Number of pool instances to create (0-120)</small>
          </div>

          <div className="form-group">
            <label htmlFor="admin_count">Admin Instances</label>
            <input
              id="admin_count"
              type="number"
              min="0"
              max="120"
              value={formData.admin_count}
              onChange={(e) => setFormData({ ...formData, admin_count: e.target.value })}
              required
              disabled={submitting}
            />
            <small>Number of admin instances to create (0-120)</small>
          </div>

          {formData.admin_count > 0 && (
            <div className="form-group">
              <label htmlFor="admin_cleanup_days">Admin Cleanup Days</label>
              <input
                id="admin_cleanup_days"
                type="number"
                min="1"
                max="365"
                value={formData.admin_cleanup_days}
                onChange={(e) => setFormData({ ...formData, admin_cleanup_days: e.target.value })}
                required
                disabled={submitting}
              />
              <small>Days before admin instances are automatically deleted (1-365)</small>
            </div>
          )}

          {error && <div className="error-message">{error}</div>}

          <div className="form-actions">
            <button type="button" onClick={onClose} disabled={submitting} className="secondary">
              Cancel
            </button>
            <button type="submit" disabled={submitting}>
              {submitting ? 'Creating...' : 'Create Session'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default TutorialSessionForm
