import React, { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import QuestsPage from './pages/QuestsPage';
import MapPage from './pages/MapPage';
import { apiService } from './services/api';
import { useQuestStore } from './store/questStore';
import { useCharacterStore } from './store/characterStore';
import { getRandomQuote } from './utils/easterEggs';
import { User } from './types';
import './App.css';
import './animations.css';

function App() {
  const { currentUser, setCurrentUser, fetchAllData } = useQuestStore((state) => ({
    currentUser: state.currentUser,
    setCurrentUser: state.setCurrentUser,
    fetchAllData: state.fetchAllData,
  }));

  const { isLoading } = useQuestStore((state) => ({
    isLoading: state.isLoading,
  }));

  useEffect(() => {
    // Check if user is already logged in
    apiService
      .getCurrentUser()
      .then((user) => {
        setCurrentUser(user);
        // Load all quest data after user is authenticated
        fetchAllData();
      })
      .catch(() => {
        setCurrentUser(null);
      })
      .finally(() => {
        // Display a random Tolkien quote on app load
        console.log(
          `%c${getRandomQuote()}`,
          'font-size: 14px; color: #DAA520; font-style: italic; font-family: Lora, serif;'
        );
      });
  }, [setCurrentUser, fetchAllData]);

  const handleLogin = (user: User) => {
    setCurrentUser(user);
    fetchAllData();
  };

  const handleLogout = async () => {
    try {
      await apiService.logout();
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      setCurrentUser(null);
      useCharacterStore.getState().clearDialogueHistory();
    }
  };

  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <div className="app min-h-screen bg-background-primary text-text-primary">
        {isLoading && (
          <div className="fixed inset-0 bg-background-primary/80 backdrop-blur-sm flex items-center justify-center z-50 animate-fadeIn">
            <div className="text-center">
              <div className="text-6xl mb-4 animate-bounce">🧙‍♂️</div>
              <p className="text-parchment-light font-epic text-2xl">Loading your Fellowship...</p>
            </div>
          </div>
        )}

        <Routes>
          <Route
            path="/login"
            element={
              currentUser ? <Navigate to="/dashboard" replace /> : <LoginPage onLogin={handleLogin} />
            }
          />
          <Route
            path="/dashboard"
            element={
              currentUser ? (
                <DashboardPage user={currentUser} onLogout={handleLogout} />
              ) : (
                <Navigate to="/login" replace />
              )
            }
          />
          <Route
            path="/quests"
            element={
              currentUser ? (
                <QuestsPage user={currentUser} onLogout={handleLogout} />
              ) : (
                <Navigate to="/login" replace />
              )
            }
          />
          <Route
            path="/map"
            element={
              currentUser ? (
                <MapPage user={currentUser} onLogout={handleLogout} />
              ) : (
                <Navigate to="/login" replace />
              )
            }
          />
          <Route path="/" element={<Navigate to={currentUser ? '/dashboard' : '/login'} replace />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}

export default App;
