import React, { createContext, useContext, useState, useEffect } from 'react'
import { api } from './api'

const AuthContext = createContext()

const PASSWORD_STORAGE_KEY = 'instance_manager_password'

export function AuthProvider({ children }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    // Check if password is stored in sessionStorage
    const storedPassword = sessionStorage.getItem(PASSWORD_STORAGE_KEY)
    if (storedPassword) {
      // Verify password is still valid by trying to fetch templates
      const checkAuth = async () => {
        try {
          const response = await api.getWorkshopTemplates(storedPassword)
          if (response && (response.success !== false)) {
            setIsAuthenticated(true)
          } else {
            // Password invalid, clear it
            sessionStorage.removeItem(PASSWORD_STORAGE_KEY)
            setIsAuthenticated(false)
          }
        } catch (error) {
          // Password invalid, clear it
          console.log('Auth check failed:', error)
          sessionStorage.removeItem(PASSWORD_STORAGE_KEY)
          setIsAuthenticated(false)
        } finally {
          setIsLoading(false)
        }
      }
      checkAuth()
    } else {
      setIsAuthenticated(false)
      setIsLoading(false)
    }
  }, [])

  const login = async (password) => {
    try {
      const response = await api.login(password)
      if (response.success) {
        // Store password in sessionStorage for subsequent requests
        sessionStorage.setItem(PASSWORD_STORAGE_KEY, password)
        setIsAuthenticated(true)
        return { success: true }
      }
      return { success: false, error: response.error || 'Invalid password' }
    } catch (error) {
      return { success: false, error: error.message }
    }
  }

  const logout = () => {
    sessionStorage.removeItem(PASSWORD_STORAGE_KEY)
    setIsAuthenticated(false)
  }

  return (
    <AuthContext.Provider value={{ isAuthenticated, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return context
}
