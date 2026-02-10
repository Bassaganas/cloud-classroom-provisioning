import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../services/auth'
import { api } from '../services/api'
import TutorialSessionForm from './TutorialSessionForm'
import './Landing.css'

function Landing() {
  const [workshops, setWorkshops] = useState([])
  const [tutorialSessions, setTutorialSessions] = useState({}) // { workshopName: [sessions] }
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showSessionForm, setShowSessionForm] = useState(null) // workshopName or null
  const [showSettings, setShowSettings] = useState(null) // workshopName or null
  const navigate = useNavigate()
  const { logout } = useAuth()

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
    <div className="landing-container">
      <header className="landing-header">
        <div className="header-content">
          <div className="header-title-wrapper">
            <svg className="rocket-icon" width="32" height="32" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M9.19 6.35c-2.45 2.49-5.46 5.52-5.77 8.96-.36 3.29 3.56 6.29 6.86 5.93 3.44-.31 6.47-3.32 8.96-5.77 3.27-3.22 3.27-8.55 0-11.77-3.27-3.22-8.55-3.22-11.77 0l1.72 1.65zm3.36 3.35L6.88 16.9c-2.13-2.12-3.31-4.53-2.87-6.99.44-2.5 2.6-4.66 5.1-5.1 2.46-.44 4.87.74 6.99 2.87l-4.25 4.22z" fill="currentColor"/>
              <circle cx="15" cy="9" r="1.5" fill="currentColor"/>
            </svg>
            <h1>EC2 Instance Manager</h1>
          </div>
          <p className="subtitle">Manage your cloud classroom instances</p>
        </div>
        <button className="logout-btn" onClick={logout}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M17 7l-1.41 1.41L18.17 11H8v2h10.17l-2.58 2.59L17 17l5-5-5-5zM4 5h8V3H4c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h8v-2H4V5z" fill="currentColor"/>
          </svg>
          Logout
        </button>
      </header>

      <div className="workshops-grid">
        {workshops.length === 0 ? (
          <div className="no-workshops">No workshops available</div>
        ) : (
          workshops.map(workshop => {
            const sessions = tutorialSessions[workshop.name] || []
            return (
              <div key={workshop.name} className="workshop-card">
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
                              <span className={`session-status session-status-${session.status}`}>
                                {session.status}
                              </span>
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
    </div>
  )
}

export default Landing
