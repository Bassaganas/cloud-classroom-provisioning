import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../services/api'
import TutorialSessionForm from './TutorialSessionForm'
import Header from '../components/Header'
import './Landing.css'

function Landing() {
  const [workshops, setWorkshops] = useState([])
  const [tutorialSessions, setTutorialSessions] = useState({}) // { workshopName: [sessions] }
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showSessionForm, setShowSessionForm] = useState(null) // workshopName or null
  const [showSettings, setShowSettings] = useState(null) // workshopName or null
  const [deletingSession, setDeletingSession] = useState(null) // { workshopName, sessionId }
  const [deleteConfirmData, setDeleteConfirmData] = useState(null) // { workshopName, sessionId, instanceCount }
  const navigate = useNavigate()

  useEffect(() => {
    loadWorkshops()
  }, [])

  useEffect(() => {
    // Load tutorial sessions for each workshop
    if (workshops.length > 0) {
      workshops.forEach(workshop => {
        loadTutorialSessions(workshop.name)
      })
    }
  }, [workshops])

  const loadWorkshops = async () => {
    try {
      setLoading(true)
      const response = await api.getWorkshopTemplates()
      if (response.success && response.templates) {
        const workshopNames = Object.keys(response.templates)
        setWorkshops(workshopNames.map(name => ({
          name,
          ...response.templates[name]
        })))
      }
    } catch (err) {
      setError(err.message || 'Failed to load workshops')
    } finally {
      setLoading(false)
    }
  }

  const loadTutorialSessions = async (workshopName) => {
    try {
      const response = await api.getTutorialSessions(workshopName)
      if (response.success && response.sessions) {
        setTutorialSessions(prev => ({
          ...prev,
          [workshopName]: response.sessions
        }))
      }
    } catch (err) {
      console.error(`Failed to load tutorial sessions for ${workshopName}:`, err)
    }
  }

  const handleSessionCreated = (workshopName) => {
    loadTutorialSessions(workshopName)
  }

  const handleDeleteSession = async (workshopName, sessionId, instanceCount, deleteInstances) => {
    try {
      setDeletingSession({ workshopName, sessionId })
      const response = await api.deleteTutorialSession(sessionId, workshopName, deleteInstances)
      
      if (response.success) {
        // Reload sessions for this workshop
        await loadTutorialSessions(workshopName)
        setDeleteConfirmData(null)
      } else {
        alert(`Error: ${response.error || 'Failed to delete session'}`)
      }
    } catch (error) {
      alert(`Error: ${error.message || 'Failed to delete session'}`)
    } finally {
      setDeletingSession(null)
    }
  }

  const handleDeleteClick = (e, workshopName, sessionId, instanceCount) => {
    e.stopPropagation()
    setDeleteConfirmData({ workshopName, sessionId, instanceCount })
  }

  if (loading) {
    return <div className="landing-container"><div className="loading">Loading workshops...</div></div>
  }

  if (error) {
    return (
      <div className="landing-container">
        <div className="error">Error: {error}</div>
        <button onClick={loadWorkshops}>Retry</button>
      </div>
    )
  }

  return (
    <div className="page-container">
      <Header />
      <div className="landing-container">

      <div className="workshops-grid">
        {workshops.length === 0 ? (
          <div className="no-workshops">No workshops available</div>
        ) : (
          workshops.map(workshop => {
            const sessions = tutorialSessions[workshop.name] || []
            return (
              <div 
                key={workshop.name} 
                className="workshop-card"
                onClick={() => navigate(`/workshop/${workshop.name}`)}
              >
                <div className="workshop-card-header">
                  <h2>{workshop.name}</h2>
                  <div className="workshop-card-actions">
                    <button
                      className="icon-btn settings-btn"
                      onClick={(e) => {
                        e.stopPropagation()
                        setShowSettings(workshop.name)
                        navigate(`/workshop/${workshop.name}/config`)
                      }}
                      title="Settings"
                      aria-label="Settings"
                    >
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.06-.94l1.69-1.32c.15-.12.19-.34.1-.51l-1.6-2.77c-.1-.18-.31-.24-.49-.18l-1.99.8c-.42-.32-.86-.58-1.35-.78L14 4.74c-.03-.2-.2-.35-.4-.35h-3.2c-.2 0-.36.15-.4.34l-.3 2.12c-.49.2-.94.47-1.35.78l-1.99-.8c-.18-.07-.39 0-.49.18l-1.6 2.77c-.1.18-.06.39.1.51l1.69 1.32c-.04.3-.06.61-.06.94 0 .32.02.64.06.94l-1.69 1.32c-.15.12-.19.34-.1.51l1.6 2.77c.1.18.31.24.49.18l1.99-.8c.42.32.86.58 1.35.78l.3 2.12c.04.2.2.34.4.34h3.2c.2 0 .37-.15.4-.34l.3-2.12c.49-.2.94-.47 1.35-.78l1.99.8c.18.07.39 0 .49-.18l1.6-2.77c.1-.18.06-.39-.1-.51l-1.67-1.32zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z" fill="currentColor"/>
                      </svg>
                    </button>
                    <button
                      className="icon-btn start-tutorial-btn"
                      onClick={(e) => {
                        e.stopPropagation()
                        setShowSessionForm(workshop.name)
                      }}
                      title="Start Tutorial"
                      aria-label="Start Tutorial"
                    >
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z" fill="currentColor"/>
                      </svg>
                    </button>
                  </div>
                </div>
                
                <div className="workshop-card-content">
                  {sessions.length > 0 ? (
                    <div className="tutorial-sessions-list">
                      <h3>Tutorial Sessions</h3>
                      <ul>
                        {sessions.map(session => (
                          <li
                            key={session.session_id}
                            className="tutorial-session-item"
                            onClick={(e) => {
                              e.stopPropagation()
                              navigate(`/tutorial/${workshop.name}/${session.session_id}`)
                            }}
                          >
                            <div className="session-info">
                              <span className="session-name">{session.session_id}</span>
                              <span className="session-stats">
                                {session.actual_instance_count || 0} instances
                              </span>
                            </div>
                            <div className="session-meta">
                              <span className="session-date">
                                {new Date(session.created_at).toLocaleDateString()}
                              </span>
                              <button
                                className="session-delete-btn"
                                onClick={(e) => handleDeleteClick(e, workshop.name, session.session_id, session.actual_instance_count || 0)}
                                title="Delete session"
                                aria-label="Delete session"
                                disabled={deletingSession?.sessionId === session.session_id}
                              >
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                                  <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z" fill="currentColor"/>
                                </svg>
                              </button>
                            </div>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : (
                    <p className="no-sessions">
                      No tutorial sessions yet. Click <span className="plus-hint">+</span> to start one.
                    </p>
                  )}
                </div>
              </div>
            )
          })
        )}
      </div>

      {showSessionForm && (
        <TutorialSessionForm
          workshopName={showSessionForm}
          onClose={() => setShowSessionForm(null)}
          onSuccess={() => handleSessionCreated(showSessionForm)}
        />
      )}

      {/* Delete Confirmation Modal */}
      {deleteConfirmData && (
        <div className="modal-overlay" onClick={() => setDeleteConfirmData(null)}>
          <div className="modal-content delete-confirm-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Delete Tutorial Session</h2>
              <button className="close-btn" onClick={() => setDeleteConfirmData(null)}>×</button>
            </div>
            <div className="modal-body">
              <p>Are you sure you want to delete the tutorial session <strong>{deleteConfirmData.sessionId}</strong>?</p>
              {deleteConfirmData.instanceCount > 0 && (
                <div className="delete-instance-warning">
                  <p>This session has <strong>{deleteConfirmData.instanceCount}</strong> associated instance(s).</p>
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      id="deleteInstances"
                      onChange={(e) => setDeleteConfirmData({ ...deleteConfirmData, deleteInstances: e.target.checked })}
                    />
                    <span>Also delete all associated EC2 instances</span>
                  </label>
                </div>
              )}
            </div>
            <div className="form-actions">
              <button
                type="button"
                onClick={() => setDeleteConfirmData(null)}
                className="secondary"
                disabled={deletingSession?.sessionId === deleteConfirmData.sessionId}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => handleDeleteSession(
                  deleteConfirmData.workshopName,
                  deleteConfirmData.sessionId,
                  deleteConfirmData.instanceCount,
                  deleteConfirmData.deleteInstances || false
                )}
                className="delete-btn"
                disabled={deletingSession?.sessionId === deleteConfirmData.sessionId}
              >
                {deletingSession?.sessionId === deleteConfirmData.sessionId ? 'Deleting...' : 'Delete Session'}
              </button>
            </div>
          </div>
        </div>
      )}
      </div>
    </div>
  )
}

export default Landing
