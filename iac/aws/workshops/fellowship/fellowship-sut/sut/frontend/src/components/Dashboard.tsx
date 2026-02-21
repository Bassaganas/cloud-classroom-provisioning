import React from 'react';
import { Quest, Member } from '../types';
import './Dashboard.css';

interface DashboardProps {
  quests: Quest[];
  members: Member[];
  user: { username: string; role: string };
}

const Dashboard: React.FC<DashboardProps> = ({ quests, members, user }) => {
  const stats = {
    total: quests.length,
    pending: quests.filter(q => q.status === 'pending').length,
    inProgress: quests.filter(q => q.status === 'in_progress').length,
    completed: quests.filter(q => q.status === 'completed').length,
  };

  const activeMembers = members.filter(m => m.status === 'active').length;

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h1>Welcome, {user.role}!</h1>
        <p className="dashboard-subtitle">Track the Fellowship's journey through Middle-earth</p>
      </div>

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-value">{stats.total}</div>
          <div className="stat-label">Total Quests</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{stats.pending}</div>
          <div className="stat-label">Pending</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{stats.inProgress}</div>
          <div className="stat-label">In Progress</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{stats.completed}</div>
          <div className="stat-label">Completed</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{activeMembers}</div>
          <div className="stat-label">Active Members</div>
        </div>
      </div>

      <div className="dashboard-section">
        <h2>Recent Quests</h2>
        <div className="quest-list">
          {quests.slice(0, 5).map((quest) => (
            <div key={quest.id} className="quest-item">
              <div className="quest-header">
                <h3>{quest.title}</h3>
                <span className={`quest-status quest-status-${quest.status}`}>
                  {quest.status.replace('_', ' ')}
                </span>
              </div>
              <p className="quest-description">{quest.description}</p>
              {quest.location_name && (
                <p className="quest-location">📍 {quest.location_name}</p>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
