import React, { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import QuestList from '../components/QuestList';
import QuestForm from '../components/QuestForm';
import { apiService } from '../services/api';
import { Quest, Location, Member, User } from '../types';
import { Button } from '../components/ui/Button';

interface QuestsPageProps {
  user: User;
  onLogout: () => void;
}

const QuestsPage: React.FC<QuestsPageProps> = ({ user, onLogout }) => {
  const location = useLocation();
  const [quests, setQuests] = useState<Quest[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingQuest, setEditingQuest] = useState<Quest | undefined>();
  const [prefilledQuest, setPrefilledQuest] = useState<Partial<Quest> | undefined>();
  const [filterStatus, setFilterStatus] = useState<string | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const status = params.get('status');
    if (status) {
      setFilterStatus(status);
    }

    const shouldPropose = params.get('propose') === '1';
    if (shouldPropose) {
      const seedType = params.get('seedType');
      const seedPriority = params.get('seedPriority');
      const seedLocationId = params.get('seedLocationId');

      const allowedTypes: Quest['quest_type'][] = ['The Journey', 'The Battle', 'The Fellowship', 'The Ring', 'Dark Magic'];
      const allowedPriorities: Quest['priority'][] = ['Critical', 'Important', 'Standard'];

      const questType = allowedTypes.includes(seedType as Quest['quest_type'])
        ? (seedType as Quest['quest_type'])
        : 'The Journey';

      const priority = allowedPriorities.includes(seedPriority as Quest['priority'])
        ? (seedPriority as Quest['priority'])
        : 'Important';

      const locationId = seedLocationId ? Number(seedLocationId) : undefined;

      setEditingQuest(undefined);
      setPrefilledQuest({
        title: params.get('seedTitle') || 'Scout the frontier',
        description: params.get('seedDescription') || 'Investigate the region and report meaningful leads.',
        status: 'not_yet_begun',
        quest_type: questType,
        priority,
        location_id: Number.isNaN(locationId) ? undefined : locationId,
      });
      setShowForm(true);
    }
  }, [location.search]);

  // Handle quest selection from map navigation
  useEffect(() => {
    if (location.state?.selectedQuestId && quests.length > 0) {
      const selectedQuest = quests.find(q => q.id === location.state.selectedQuestId);
      if (selectedQuest) {
        setEditingQuest(selectedQuest);
        setShowForm(true);
      }
    }
  }, [location.state?.selectedQuestId, quests]);

  useEffect(() => {
    if (quests.length === 0) {
      return;
    }

    const params = new URLSearchParams(location.search);
    const focusQuestIdRaw = params.get('focusQuestId');
    if (!focusQuestIdRaw) {
      return;
    }

    const focusQuestId = Number(focusQuestIdRaw);
    if (!focusQuestId || Number.isNaN(focusQuestId)) {
      return;
    }

    const selectedQuest = quests.find(q => q.id === focusQuestId);
    if (selectedQuest) {
      setEditingQuest(selectedQuest);
      setShowForm(true);
    }
  }, [location.search, quests]);

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
    setPrefilledQuest(undefined);
  };

  const handleUpdateQuest = async (questData: Partial<Quest>) => {
    if (editingQuest) {
      await apiService.updateQuest(editingQuest.id, questData);
      await loadData();
      setEditingQuest(undefined);
      setPrefilledQuest(undefined);
    }
  };

  const handleDeleteQuest = async (id: number) => {
    if (window.confirm('Are you sure you want to abandon this quest?')) {
      await apiService.deleteQuest(id);
      await loadData();
    }
  };

  const handleCompleteQuest = async (id: number) => {
    try {
      const result = await apiService.completeQuest(id);
      if (result.message) {
        alert(result.message + (result.character_quote ? `\n\n"${result.character_quote}"` : ''));
      }
      await loadData();
    } catch (error) {
      console.error('Failed to complete quest:', error);
      alert('Failed to complete quest. The shadow may have fallen upon it.');
    }
  };

  const handleEditQuest = (quest: Quest) => {
    setEditingQuest(quest);
    setPrefilledQuest(undefined);
    setShowForm(true);
  };

  const handleFormCancel = () => {
    setShowForm(false);
    setEditingQuest(undefined);
    setPrefilledQuest(undefined);
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
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center">
          <div className="text-4xl mb-4">📜</div>
          <p className="text-text-primary font-readable">Unfurling the Scrolls of Middle-earth...</p>
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
            <Link to="/dashboard" className="font-epic text-2xl text-gold hover:text-gold-light transition-colors">
              The Scrolls of Middle-earth
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
        {/* Page Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <p className="font-readable text-text-muted text-lg">
              All {quests.length} quest objectives across the realm
            </p>
          </div>
          <Button
            onClick={() => {
              setEditingQuest(undefined);
              setPrefilledQuest(undefined);
              setShowForm(true);
            }}
            variant="epic"
          >
            🗂️ Propose a Quest
          </Button>
        </div>

        {/* Filter Bar */}
        <div className="flex gap-2 mb-8 flex-wrap">
          <button
            onClick={() => setFilterStatus(null)}
            className={`px-4 py-2 rounded font-readable transition-all ${
              filterStatus === null
                ? 'bg-gold text-text-primary'
                : 'bg-parchment-light text-text-primary hover:bg-gold/20'
            }`}
          >
            All Quests ({quests.length})
          </button>
          <button
            onClick={() => setFilterStatus('the_road_goes_ever_on')}
            className={`px-4 py-2 rounded font-readable transition-all ${
              filterStatus === 'the_road_goes_ever_on'
                ? 'bg-forest text-parchment'
                : 'bg-parchment-light text-text-primary hover:bg-forest/20'
            }`}
          >
            In Progress ({quests.filter(q => q.status === 'the_road_goes_ever_on').length})
          </button>
          <button
            onClick={() => setFilterStatus('it_is_done')}
            className={`px-4 py-2 rounded font-readable transition-all ${
              filterStatus === 'it_is_done'
                ? 'bg-success text-parchment'
                : 'bg-parchment-light text-text-primary hover:bg-success/20'
            }`}
          >
            Completed ({quests.filter(q => q.status === 'it_is_done').length})
          </button>
          <button
            onClick={() => setFilterStatus('the_shadow_falls')}
            className={`px-4 py-2 rounded font-readable transition-all ${
              filterStatus === 'the_shadow_falls'
                ? 'bg-danger text-parchment'
                : 'bg-parchment-light text-text-primary hover:bg-danger/20'
            }`}
          >
            Blocked ({quests.filter(q => q.status === 'the_shadow_falls').length})
          </button>
        </div>

        {/* Quest List */}
        <div>
          <QuestList
            quests={filterStatus ? quests.filter(q => q.status === filterStatus) : quests}
            onEdit={handleEditQuest}
            onDelete={handleDeleteQuest}
            onComplete={handleCompleteQuest}
          />
        </div>
      </div>

      {/* Quest Form Modal */}
      {showForm && (
        <QuestForm
          quest={editingQuest || prefilledQuest}
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

