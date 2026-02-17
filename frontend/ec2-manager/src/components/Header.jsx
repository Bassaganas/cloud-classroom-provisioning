import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../services/auth'
import './Header.css'

function Header({ title, subtitle, showBack = false, backPath, showSettings = false, settingsPath }) {
  const { logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const handleBack = () => {
    if (backPath) {
      navigate(backPath)
    } else {
      navigate(-1)
    }
  }

  const handleSettings = () => {
    if (settingsPath) {
      navigate(settingsPath)
    }
  }

  // Generate breadcrumbs from path
  const getBreadcrumbs = () => {
    const paths = location.pathname.split('/').filter(Boolean)
    if (paths.length === 0) return null
    
    const breadcrumbs = []
    let currentPath = ''
    
    paths.forEach((path, index) => {
      currentPath += `/${path}`
      const isLast = index === paths.length - 1
      
      // Format path name
      let name = path.replace(/_/g, ' ').replace(/-/g, ' ')
      name = name.charAt(0).toUpperCase() + name.slice(1)
      
      breadcrumbs.push({
        path: currentPath,
        name: name,
        isLast: isLast
      })
    })
    
    return breadcrumbs
  }

  const breadcrumbs = getBreadcrumbs()
  const isLanding = location.pathname === '/'

  return (
    <header className="app-header">
      <div className="header-content">
        <div className="header-left">
          <Link to="/" className="logo-link">
            <svg className="logo-icon" width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M9.19 6.35c-2.45 2.49-5.46 5.52-5.77 8.96-.36 3.29 3.56 6.29 6.86 5.93 3.44-.31 6.47-3.32 8.96-5.77 3.27-3.22 3.27-8.55 0-11.77-3.27-3.22-8.55-3.22-11.77 0l1.72 1.65zm3.36 3.35L6.88 16.9c-2.13-2.12-3.31-4.53-2.87-6.99.44-2.5 2.6-4.66 5.1-5.1 2.46-.44 4.87.74 6.99 2.87l-4.25 4.22z" fill="currentColor"/>
              <circle cx="15" cy="9" r="1.5" fill="currentColor"/>
            </svg>
            {isLanding && <span className="logo-text">Tutorials Manager</span>}
          </Link>
          
          {!isLanding && title && (
            <div className="header-title-section">
              <h1 className="page-title">{title}</h1>
            </div>
          )}
          
          {breadcrumbs && breadcrumbs.length > 1 && (
            <nav className="breadcrumbs" aria-label="Breadcrumb">
              {breadcrumbs.map((crumb, index) => (
                <span key={crumb.path} className="breadcrumb-item">
                  {index > 0 && <span className="breadcrumb-separator">/</span>}
                  {crumb.isLast ? (
                    <span className="breadcrumb-current">{crumb.name}</span>
                  ) : (
                    <Link to={crumb.path} className="breadcrumb-link">{crumb.name}</Link>
                  )}
                </span>
              ))}
            </nav>
          )}
          <div className="header-right">
          {showBack && (
            <button 
              className="header-icon-btn" 
              onClick={handleBack}
              title="Go back"
              aria-label="Go back"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M15 18l-6-6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
          )}
          
          {showSettings && (
            <button 
              className="header-icon-btn" 
              onClick={handleSettings}
              title="Settings"
              aria-label="Settings"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.06-.94l1.69-1.32c.15-.12.19-.34.1-.51l-1.6-2.77c-.1-.18-.31-.24-.49-.18l-1.99.8c-.42-.32-.86-.58-1.35-.78L14 4.74c-.03-.2-.2-.35-.4-.35h-3.2c-.2 0-.36.15-.4.34l-.3 2.12c-.49.2-.94.47-1.35.78l-1.99-.8c-.18-.07-.39 0-.49.18l-1.6 2.77c-.1.18-.06.39.1.51l1.69 1.32c-.04.3-.06.61-.06.94 0 .32.02.64.06.94l-1.69 1.32c-.15.12-.19.34-.1.51l1.6 2.77c.1.18.31.24.49.18l1.99-.8c.42.32.86.58 1.35.78l.3 2.12c.04.2.2.34.4.34h3.2c.2 0 .37-.15.4-.34l.3-2.12c.49-.2.94-.47 1.35-.78l1.99.8c.18.07.39 0 .49-.18l1.6-2.77c.1-.18.06-.39-.1-.51l-1.67-1.32zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z" fill="currentColor"/>
              </svg>
            </button>
          )}
          
          <button 
            className="header-icon-btn header-icon-btn-danger" 
            onClick={logout}
            title="Logout"
            aria-label="Logout"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M17 7l-1.41 1.41L18.17 11H8v2h10.17l-2.58 2.59L17 17l5-5-5-5zM4 5h8V3H4c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h8v-2H4V5z" fill="currentColor"/>
            </svg>
          </button>
        </div>
        </div>
      </div>
    </header>
  )
}

export default Header
