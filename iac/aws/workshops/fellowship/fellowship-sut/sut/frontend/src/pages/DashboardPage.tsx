import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import Dashboard from '../components/Dashboard';
import { apiService } from '../services/api';
import { Quest, Member, User } from '../types';

interface DashboardPageProps {
  user: User;
  onLogout: () => void;
}

const DashboardPage: React.FC<DashboardPageProps> = ({ user, onLogout }) => {
  const [quests, setQuests] = useState<Quest[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
      try {
        const [questsData, membersData] = await Promise.all([
          apiService.getQuests(),
          apiService.getMembers(),
        ]);
        setQuests(questsData);
        setMembers(membersData);
      } catch (error) {
        console.error('Failed to load dashboard data:', error);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, []);

  if (loading) {
    return (
      <div className="app-loading">
        <div className="loading-spinner">Loading dashboard...</div>
      </div>
    );
  }

  return (
    <div>
      <nav className="navbar">
        <Link to="/dashboard" className="navbar-brand">
          Fellowship Quest Tracker
        </Link>
        <div className="navbar-nav">
          <Link to="/dashboard" className="nav-link">Dashboard</Link>
          <Link to="/quests" className="nav-link">Quests</Link>
          <button className="btn btn-secondary" onClick={onLogout}>
            Logout
          </button>
        </div>
      </nav>
      <div className="container">
        <Dashboard quests={quests} members={members} user={user} />
      </div>
    </div>
  );
};

export default DashboardPage;
