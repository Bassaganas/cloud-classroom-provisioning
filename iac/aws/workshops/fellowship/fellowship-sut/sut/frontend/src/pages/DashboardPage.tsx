import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import Dashboard from '../components/Dashboard';
import { apiService } from '../services/api';
import { Quest, Member, User } from '../types';
import { Button } from '../components/ui/Button';

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
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center">
          <div className="text-4xl mb-4">🧝</div>
          <p className="text-text-primary font-readable">Opening the gates of Rivendell...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Navigation Header */}
      <nav className="bg-gradient-to-r from-forest to-forest-dark shadow-lg border-b-2 border-gold">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-2xl">🏰</span>
            <Link to="/dashboard" className="font-epic text-2xl text-gold hover:text-gold-light transition-colors">
              The Council Chamber
            </Link>
          </div>
          <div className="flex items-center gap-4">
            <Link
              to="/dashboard"
              className="text-parchment hover:text-gold transition-colors font-readable"
            >
              Council Chamber
            </Link>
            <Link
              to="/quests"
              className="text-parchment hover:text-gold transition-colors font-readable"
            >
              Scrolls of Middle-earth
            </Link>
            <Link
              to="/map"
              className="text-parchment hover:text-gold transition-colors font-readable"
            >
              Map of Middle-earth
            </Link>
            <Button
              onClick={onLogout}
              variant="secondary"
              className="text-sm"
            >
              Leave Fellowship
            </Button>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 py-8">
        <Dashboard quests={quests} members={members} user={user} />
      </div>
    </div>
  );
};

export default DashboardPage;
