import React, { useState, FormEvent } from 'react';
import { apiService } from '../services/api';
import { User } from '../types';
import { Alert, Button, Input } from './ui';

interface LoginProps {
  onLogin: (user: User) => void;
}

const Login: React.FC<LoginProps> = ({ onLogin }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
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
    <div className="w-full max-w-md">
      <div className="card-parchment shadow-epic border border-gold-dark/30">
        <h1 className="text-3xl md:text-4xl text-center text-text-primary mb-2">Enter the Fellowship</h1>
        <p className="text-center text-pending mb-6 italic">One does not simply walk into Middle-earth without credentials.</p>

        {error && (
          <Alert variant="error" title="The Gate Remains Closed" className="mb-4">
            {error}
          </Alert>
        )}

        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          <Input
            id="username"
            label="Username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            required
            placeholder="e.g., frodo_baggins"
            autoComplete="username"
          />

          <div>
            <Input
              id="password"
              label="Password"
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              placeholder="Enter your password"
              autoComplete="current-password"
            />
            <button
              type="button"
              className="mt-2 text-sm text-forest hover:text-forest-light"
              onClick={() => setShowPassword((current) => !current)}
            >
              {showPassword ? 'Hide password' : 'Show password'}
            </button>
          </div>

          <label className="flex items-center gap-2 text-sm text-text-primary">
            <input
              type="checkbox"
              checked={rememberMe}
              onChange={(event) => setRememberMe(event.target.checked)}
              className="h-4 w-4 accent-gold"
            />
            Keep me in the Fellowship on this device
          </label>

          <Button type="submit" variant="epic" className="w-full" isLoading={loading}>
            {loading ? 'Opening the Gates...' : 'Enter Middle-earth'}
          </Button>
        </form>

        <div className="mt-6 pt-4 border-t border-gold-dark/30 text-sm text-text-primary">
          <p>
            Default password: <strong>fellowship123</strong>
          </p>
          <p className="mt-1 text-text-secondary">
            Try: frodo_baggins, samwise_gamgee, aragorn, legolas, gimli, gandalf
          </p>
        </div>
      </div>
    </div>
  );
};

export default Login;
