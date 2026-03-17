import { Link as RouterLink, useNavigate, useLocation } from 'react-router-dom'
import {
  AppBar,
  Toolbar,
  Typography,
  Box,
  IconButton,
  Breadcrumbs,
  Link,
  Tooltip
} from '@mui/material'
import ArrowBackRoundedIcon from '@mui/icons-material/ArrowBackRounded'
import SettingsRoundedIcon from '@mui/icons-material/SettingsRounded'
import LogoutRoundedIcon from '@mui/icons-material/LogoutRounded'
import HomeRoundedIcon from '@mui/icons-material/HomeRounded'
import { useAuth } from '../services/auth'

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
    <>
      <AppBar position="sticky" color="inherit" elevation={0} sx={{ borderBottom: '1px solid', borderColor: 'divider' }}>
        <Toolbar sx={{ py: 1.25, gap: 1.5, minHeight: 80 }}>
          <IconButton component={RouterLink} to="/" color="primary" aria-label="Go to home">
            <HomeRoundedIcon />
          </IconButton>

          <Box sx={{ flexGrow: 1, minWidth: 0 }}>
            <Typography variant="h6" fontWeight={700} noWrap>
              {isLanding ? 'EC2 Tutorials Manager' : title || 'EC2 Manager'}
            </Typography>
            {subtitle && (
              <Typography variant="body2" color="text.secondary" noWrap>
                {subtitle}
              </Typography>
            )}
            {breadcrumbs && breadcrumbs.length > 0 && (
              <Breadcrumbs aria-label="breadcrumb" sx={{ mt: 0.5 }}>
                <Link component={RouterLink} underline="hover" color="inherit" to="/">
                  Dashboard
                </Link>
                {breadcrumbs.map((crumb) => (
                  crumb.isLast ? (
                    <Typography key={crumb.path} color="text.primary" sx={{ textTransform: 'capitalize' }}>
                      {crumb.name}
                    </Typography>
                  ) : (
                    <Link
                      key={crumb.path}
                      component={RouterLink}
                      underline="hover"
                      color="inherit"
                      to={crumb.path}
                      sx={{ textTransform: 'capitalize' }}
                    >
                      {crumb.name}
                    </Link>
                  )
                ))}
              </Breadcrumbs>
            )}
          </Box>

          {showBack && (
            <Tooltip title="Go back">
              <IconButton onClick={handleBack} aria-label="Go back">
                <ArrowBackRoundedIcon />
              </IconButton>
            </Tooltip>
          )}

          {showSettings && (
            <Tooltip title="Settings">
              <IconButton onClick={handleSettings} aria-label="Settings">
                <SettingsRoundedIcon />
              </IconButton>
            </Tooltip>
          )}

          <Tooltip title="Logout">
            <IconButton onClick={logout} color="error" aria-label="Logout">
              <LogoutRoundedIcon />
            </IconButton>
          </Tooltip>
        </Toolbar>
      </AppBar>
    </>
  )
}

export default Header
