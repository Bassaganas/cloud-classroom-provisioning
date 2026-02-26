import React from 'react';
import { Quest, Member } from '../types';
import './Dashboard.css';

interface DashboardProps {
  quests: Quest[];
  members: Member[];
  user: { username: string; role: string };
}

const Dashboard: React.FC<DashboardProps> = ({ quests, members, user }) => {
  // Helper function to check if status matches (handles both old and new values)
  const matchesStatus = (quest: Quest, statuses: string[]): boolean => {
    return statuses.includes(quest.status);
  };

  // Helper function to get status display text
  const getStatusText = (status: string): string => {
    if (status === 'not_yet_begun' || status === 'pending') {
      return 'Not Yet Begun';
    }
    if (status === 'the_road_goes_ever_on' || status === 'in_progress') {
      return 'The Road Goes Ever On...';
    }
    if (status === 'it_is_done' || status === 'completed') {
      return 'It Is Done';
    }
    if (status === 'the_shadow_falls' || status === 'blocked') {
      return 'The Shadow Falls';
    }
    // Fallback for any other status values
    return String(status).replace(/_/g, ' ');
  };

  const stats = {
    total: quests.length,
    notYetBegun: quests.filter(q => matchesStatus(q, ['not_yet_begun', 'pending'])).length,
    inProgress: quests.filter(q => matchesStatus(q, ['the_road_goes_ever_on', 'in_progress'])).length,
    completed: quests.filter(q => matchesStatus(q, ['it_is_done', 'completed'])).length,
    shadowFalls: quests.filter(q => matchesStatus(q, ['the_shadow_falls', 'blocked'])).length,
    darkMagic: quests.filter(q => q.is_dark_magic).length,
  };

  const activeMembers = members.filter(m => m.status === 'active').length;
  const userQuests = quests.filter(q => q.assignee_name === user.role || q.assigned_to);
  const userCompleted = userQuests.filter(q => matchesStatus(q, ['it_is_done', 'completed'])).length;

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h1>The Council Chamber</h1>
        <p className="dashboard-subtitle">Welcome, {user.role}! Track the Fellowship's journey through Middle-earth</p>
      </div>

      {stats.darkMagic > 0 && (
        <div className="dark-magic-warning">
          <strong>⚠️ Dark Magic Detected!</strong> {stats.darkMagic} quest{stats.darkMagic !== 1 ? 's' : ''} {stats.darkMagic !== 1 ? 'have' : 'has'} been corrupted by Sauron's influence.
        </div>
      )}

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-value">{stats.total}</div>
          <div className="stat-label">Total Quests</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{stats.notYetBegun}</div>
          <div className="stat-label">Not Yet Begun</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{stats.inProgress}</div>
          <div className="stat-label">The Road Goes Ever On</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{stats.completed}</div>
          <div className="stat-label">It Is Done</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{stats.shadowFalls}</div>
          <div className="stat-label">The Shadow Falls</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{activeMembers}</div>
          <div className="stat-label">Active Fellowship Members</div>
        </div>
      </div>

      {userQuests.length > 0 && (
        <div className="dashboard-section">
          <h2>Your Quests</h2>
          <div className="user-stats">
            <div className="user-stat-item">
              <span className="user-stat-label">Assigned to you:</span>
              <span className="user-stat-value">{userQuests.length}</span>
            </div>
            <div className="user-stat-item">
              <span className="user-stat-label">Completed:</span>
              <span className="user-stat-value">{userCompleted}</span>
            </div>
          </div>
        </div>
      )}

      <div className="dashboard-section">
        <h2>Recent Quests</h2>
        <div className="quest-list">
          {quests.slice(0, 5).map((quest) => (
            <div key={quest.id} className="quest-item">
              <div className="quest-header">
                <h3>{quest.title}</h3>
                <span className={`quest-status quest-status-${quest.status}`}>
                  {getStatusText(quest.status)}
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
