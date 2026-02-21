import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import QuestList from '../components/QuestList';
import QuestForm from '../components/QuestForm';
import { apiService } from '../services/api';
import { Quest, Location, Member, User } from '../types';
import './QuestsPage.css';

interface QuestsPageProps {
  user: User;
  onLogout: () => void;
}

const QuestsPage: React.FC<QuestsPageProps> = ({ user, onLogout }) => {
  const [quests, setQuests] = useState<Quest[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingQuest, setEditingQuest] = useState<Quest | undefined>();

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [questsData, locationsData, membersData] = await Promise.all([
        apiService.getQuests(),
        apiService.getLocations(),
        apiService.getMembers(),
      ]);
      setQuests(questsData);
      setLocations(locationsData);
      setMembers(membersData);
    } catch (error) {
      console.error('Failed to load data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateQuest = async (questData: Partial<Quest>) => {
    await apiService.createQuest(questData);
    await loadData();
    setShowForm(false);
  };

  const handleUpdateQuest = async (questData: Partial<Quest>) => {
    if (editingQuest) {
      await apiService.updateQuest(editingQuest.id, questData);
      await loadData();
      setEditingQuest(undefined);
    }
  };

  const handleDeleteQuest = async (id: number) => {
    if (window.confirm('Are you sure you want to delete this quest?')) {
      await apiService.deleteQuest(id);
      await loadData();
    }
  };

  const handleEditQuest = (quest: Quest) => {
    setEditingQuest(quest);
    setShowForm(true);
  };

  const handleFormCancel = () => {
    setShowForm(false);
    setEditingQuest(undefined);
  };

  const handleFormSubmit = async (questData: Partial<Quest>) => {
    if (editingQuest) {
      await handleUpdateQuest(questData);
    } else {
      await handleCreateQuest(questData);
    }
  };

  if (loading) {
    return (
      <div className="app-loading">
        <div className="loading-spinner">Loading quests...</div>
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
        <div className="page-header">
          <h1>Quests</h1>
          <button className="btn btn-primary" onClick={() => setShowForm(true)}>
            Create New Quest
          </button>
        </div>
        <QuestList
          quests={quests}
          onEdit={handleEditQuest}
          onDelete={handleDeleteQuest}
        />
      </div>
      {showForm && (
        <QuestForm
          quest={editingQuest}
          locations={locations}
          members={members}
          onSubmit={handleFormSubmit}
          onCancel={handleFormCancel}
        />
      )}
    </div>
  );
};

export default QuestsPage;
