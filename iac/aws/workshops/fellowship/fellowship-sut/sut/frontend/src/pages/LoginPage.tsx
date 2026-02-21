import React from 'react';
import Login from '../components/Login';
import { User } from '../types';

interface LoginPageProps {
  onLogin: (user: User) => void;
}

const LoginPage: React.FC<LoginPageProps> = ({ onLogin }) => {
  return <Login onLogin={onLogin} />;
};

export default LoginPage;
