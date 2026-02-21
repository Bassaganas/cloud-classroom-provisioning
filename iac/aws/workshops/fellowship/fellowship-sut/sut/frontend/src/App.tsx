import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import QuestsPage from './pages/QuestsPage';
import { apiService } from './services/api';
import { User } from './types';
import './App.css';

function App() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check if user is already logged in
    apiService.getCurrentUser()
      .then((currentUser) => {
        setUser(currentUser);
      })
      .catch(() => {
        setUser(null);
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  const handleLogin = (user: User) => {
    setUser(user);
  };

  const handleLogout = async () => {
    try {
      await apiService.logout();
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      setUser(null);
    }
  };

  if (loading) {
    return (
      <div className="app-loading">
        <div className="loading-spinner">Loading...</div>
      </div>
    );
  }

  return (
    <BrowserRouter>
      <div className="app">
        <Routes>
          <Route
            path="/login"
            element={
              user ? (
                <Navigate to="/dashboard" replace />
              ) : (
                <LoginPage onLogin={handleLogin} />
              )
            }
          />
          <Route
            path="/dashboard"
            element={
              user ? (
                <DashboardPage user={user} onLogout={handleLogout} />
              ) : (
                <Navigate to="/login" replace />
              )
            }
          />
          <Route
            path="/quests"
            element={
              user ? (
                <QuestsPage user={user} onLogout={handleLogout} />
              ) : (
                <Navigate to="/login" replace />
              )
            }
          />
          <Route path="/" element={<Navigate to={user ? "/dashboard" : "/login"} replace />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}

export default App;
