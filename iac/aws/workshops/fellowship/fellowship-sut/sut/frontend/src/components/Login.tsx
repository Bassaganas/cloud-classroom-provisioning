import React, { useState, FormEvent } from 'react';
import { apiService } from '../services/api';
import { User } from '../types';
import './Login.css';

interface LoginProps {
  onLogin: (user: User) => void;
}

const Login: React.FC<LoginProps> = ({ onLogin }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await apiService.login({ username, password });
      onLogin(response.user);
    } catch (err: any) {
      setError(err.response?.data?.error || 'Invalid credentials. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-card">
        <h1 className="login-title">Fellowship Quest Tracker</h1>
        <p className="login-subtitle">Enter Middle-earth and track your journey</p>
        
        {error && <div className="error-message">{error}</div>}
        
        <form onSubmit={handleSubmit} className="login-form">
          <div className="form-group">
            <label htmlFor="username" className="form-label">Username</label>
            <input
              type="text"
              id="username"
              className="form-input"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              placeholder="e.g., frodo_baggins"
            />
          </div>
          
          <div className="form-group">
            <label htmlFor="password" className="form-label">Password</label>
            <input
              type="password"
              id="password"
              className="form-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              placeholder="Enter your password"
            />
          </div>
          
          <button
            type="submit"
            className="btn btn-primary login-button"
            disabled={loading}
          >
            {loading ? 'Logging in...' : 'Enter Middle-earth'}
          </button>
        </form>
        
        <div className="login-hint">
          <p>Default password: <strong>fellowship123</strong></p>
          <p>Try: frodo_baggins, samwise_gamgee, aragorn, legolas, gimli, gandalf</p>
        </div>
      </div>
    </div>
  );
};

export default Login;
