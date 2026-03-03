import React, { useState, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import MiddleEarthMap from '../components/MiddleEarthMap';
import { MapCharacterPanel } from '../components/characters/MapCharacterPanel';
import GoldCounter from '../components/GoldCounter';
import { apiService } from '../services/api';
import { Quest, Location, NpcCharacter, User } from '../types';
import { Button } from '../components/ui/Button';
import { useCharacterStore } from '../store/characterStore';
import './MapPage.css';

interface MapPageProps {
  user: User;
  onLogout: () => void;
}

const MapPage: React.FC<MapPageProps> = ({ user, onLogout }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const [allQuests, setAllQuests] = useState<Quest[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [selectedQuestId, setSelectedQuestId] = useState<number | undefined>();
  const [selectedLocationId, setSelectedLocationId] = useState<number | undefined>();
  const [zoomToLocation, setZoomToLocation] = useState<number | undefined>();
  const [loading, setLoading] = useState(true);
  const [filterOpen, setFilterOpen] = useState(window.innerWidth > 1024);
  const [gold, setGold] = useState<number>(user.gold || 0);
  const [showCharacterPanel, setShowCharacterPanel] = useState(false);
  const setActiveCharacter = useCharacterStore((state) => state.setActiveCharacter);

  // Filters
  const [statusFilter, setStatusFilter] = useState<string[]>(['all']);
  const [typeFilter, setTypeFilter] = useState<string[]>(['all']);

  useEffect(() => {
    loadData();
    // Handle zoom to location from navigation state
    if (location.state?.zoomToLocation) {
      setZoomToLocation(location.state.zoomToLocation);
    }
  }, [location.state?.zoomToLocation]);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const zoomToLocationParam = params.get('zoomToLocation');
    const selectedQuestIdParam = params.get('selectedQuestId');

    if (zoomToLocationParam) {
      const zoomToLocationId = Number(zoomToLocationParam);
      if (!Number.isNaN(zoomToLocationId)) {
        setZoomToLocation(zoomToLocationId);
      }
    }

    if (selectedQuestIdParam) {
      const parsedQuestId = Number(selectedQuestIdParam);
      if (!Number.isNaN(parsedQuestId)) {
        setSelectedQuestId(parsedQuestId);
      }
    }
  }, [location.search]);

  const loadData = async () => {
    try {
      console.log('MapPage: Loading data...');
      const [questsData, locationsData] = await Promise.all([
        apiService.getQuests(),
        apiService.getLocations(),
      ]);
      console.log(`MapPage: Loaded ${questsData.length} quests and ${locationsData.length} locations`);
      setAllQuests(questsData);
      setLocations(locationsData);
      const currentGold = await apiService.getGoldBalance();
      setGold(currentGold);
    } catch (error) {
      console.error('Failed to load data:', error);
    } finally {
      setLoading(false);
    }
  };

  // Handle quest click from map
  const handleQuestClick = (questId: number) => {
    console.log(`MapPage.handleQuestClick: Quest ID ${questId} clicked`);
    setSelectedQuestId(questId);
  };

  // Toggle filter sidebar
  const toggleFilterSidebar = () => {
    setFilterOpen(!filterOpen);
  };

  const normalizeStatus = (status?: string): string => {
    const statusMap: Record<string, string> = {
      pending: 'not_yet_begun',
      in_progress: 'the_road_goes_ever_on',
      completed: 'it_is_done',
      blocked: 'the_shadow_falls',
    };
    if (!status) {
      return '';
    }
    return statusMap[status] || status;
  };

  const handleLocationClick = (locationId: number) => {
    setSelectedLocationId(locationId);
  };

  const handleCompleteQuest = async (questId: number) => {
    try {
      await apiService.completeQuest(questId);
      setSelectedQuestId(questId);
      const currentGold = await apiService.getGoldBalance();
      setGold(currentGold);
      await loadData();
    } catch (error) {
      console.error('Failed to complete quest from map:', error);
    }
  };

  const handleCharacterClick = (character: NpcCharacter) => {
    setActiveCharacter(character);
    setShowCharacterPanel(true);
  };

  // Apply filters
  const getFilteredQuests = (): Quest[] => {
    let filtered = allQuests;

    // Filter by status
    if (statusFilter.length > 0 && !statusFilter.includes('all')) {
      filtered = filtered.filter((q) => statusFilter.includes(normalizeStatus(q.status)));
    }

    // Filter by type
    if (typeFilter.length > 0 && !typeFilter.includes('all')) {
      filtered = filtered.filter(q => typeFilter.includes(q.quest_type || ''));
    }

    return filtered;
  };

  const filteredQuests = getFilteredQuests();

  // Get selected quest details
  const selectedQuest = allQuests.find(q => q.id === selectedQuestId);
  const selectedLocation = locations.find((loc) => loc.id === selectedLocationId);

  const getStatusClass = (status: string): string => {
    const statusClassMap: Record<string, string> = {
      'pending': 'not_yet_begun',
      'in_progress': 'the_road_goes_ever_on',
      'completed': 'it_is_done',
      'blocked': 'the_shadow_falls'
    };
    return statusClassMap[status] || status;
  };

  const getStatusText = (status: string): string => {
    const texts: Record<string, string> = {
      'not_yet_begun': 'Not Yet Begun',
      'the_road_goes_ever_on': 'The Road Goes Ever On...',
      'it_is_done': 'It Is Done',
      'the_shadow_falls': 'The Shadow Falls',
      'pending': 'Not Yet Begun',
      'in_progress': 'The Road Goes Ever On...',
      'completed': 'It Is Done',
      'blocked': 'The Shadow Falls'
    };
    return texts[status] || status;
  };

  const getQuestTypeIcon = (questType?: string): string => {
    const iconMap: Record<string, string> = {
      'The Journey': '🧭',
      'The Battle': '⚔️',
      'The Fellowship': '👥',
      'The Ring': '💍',
      'Dark Magic': '👁️'
    };
    return iconMap[questType || ''] || '📜';
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center">
          <p className="text-text-primary font-readable">Charting the Map of Middle-earth...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Navigation Header */}
      <nav className="bg-gradient-to-r from-forest to-forest-dark shadow-lg border-b-2 border-gold">
        <div className="max-w-7xl mx-auto w-full px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Link to="/dashboard" className="font-epic text-2xl text-gold hover:text-gold-light transition-colors">
              Map of Middle-earth
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
              className="text-gold font-readable font-bold"
            >
              Map of Middle-earth
            </Link>
            <Link
              to="/inventory"
              className="text-parchment hover:text-gold transition-colors font-readable"
            >
              Inventory
            </Link>
            <GoldCounter gold={gold} />
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

      {/* Map Container */}
      <div className="flex-1 map-page-container">
        {/* Filter Sidebar */}
        <aside className={`filter-sidebar ${filterOpen ? 'open' : 'closed'}`}>
          <div className="filter-sidebar-header">
            <h3>Filters</h3>
            <button 
              className="filter-close-btn"
              onClick={toggleFilterSidebar}
              aria-label="Close filters"
            >
              ✕
            </button>
          </div>

          <div className="filter-content">
            {/* Status Filter */}
            <div className="filter-section">
              <h4>Quest Status</h4>
              <label className="filter-checkbox">
                <input
                  type="checkbox"
                  checked={statusFilter.includes('all')}
                  onChange={(e) => {
                    if (e.target.checked) {
                      setStatusFilter(['all']);
                    } else {
                      setStatusFilter([]);
                    }
                  }}
                />
                <span>All</span>
              </label>
              <label className="filter-checkbox">
                <input
                  type="checkbox"
                  checked={statusFilter.includes('not_yet_begun')}
                  onChange={(e) => {
                    const newFilter = statusFilter.filter(s => s !== 'all');
                    if (e.target.checked) {
                      setStatusFilter([...newFilter, 'not_yet_begun']);
                    } else {
                      setStatusFilter(newFilter.filter(s => s !== 'not_yet_begun'));
                    }
                  }}
                />
                <span style={{ color: '#888' }}>● Not Yet Begun</span>
              </label>
              <label className="filter-checkbox">
                <input
                  type="checkbox"
                  checked={statusFilter.includes('the_road_goes_ever_on')}
                  onChange={(e) => {
                    const newFilter = statusFilter.filter(s => s !== 'all');
                    if (e.target.checked) {
                      setStatusFilter([...newFilter, 'the_road_goes_ever_on']);
                    } else {
                      setStatusFilter(newFilter.filter(s => s !== 'the_road_goes_ever_on'));
                    }
                  }}
                />
                <span style={{ color: '#FF6B6B' }}>● In Progress</span>
              </label>
              <label className="filter-checkbox">
                <input
                  type="checkbox"
                  checked={statusFilter.includes('it_is_done')}
                  onChange={(e) => {
                    const newFilter = statusFilter.filter(s => s !== 'all');
                    if (e.target.checked) {
                      setStatusFilter([...newFilter, 'it_is_done']);
                    } else {
                      setStatusFilter(newFilter.filter(s => s !== 'it_is_done'));
                    }
                  }}
                />
                <span style={{ color: '#51CF66' }}>● Completed</span>
              </label>
              <label className="filter-checkbox">
                <input
                  type="checkbox"
                  checked={statusFilter.includes('the_shadow_falls')}
                  onChange={(e) => {
                    const newFilter = statusFilter.filter(s => s !== 'all');
                    if (e.target.checked) {
                      setStatusFilter([...newFilter, 'the_shadow_falls']);
                    } else {
                      setStatusFilter(newFilter.filter(s => s !== 'the_shadow_falls'));
                    }
                  }}
                />
                <span style={{ color: '#1A1A1A' }}>● Failed</span>
              </label>
            </div>

            {/* Type Filter */}
            <div className="filter-section">
              <h4>Quest Type</h4>
              <label className="filter-checkbox">
                <input
                  type="checkbox"
                  checked={typeFilter.includes('all')}
                  onChange={(e) => {
                    if (e.target.checked) {
                      setTypeFilter(['all']);
                    } else {
                      setTypeFilter([]);
                    }
                  }}
                />
                <span>All</span>
              </label>
              {Array.from(new Set(allQuests.map(q => q.quest_type).filter(Boolean))).map((type) => (
                <label key={type} className="filter-checkbox">
                  <input
                    type="checkbox"
                    checked={typeFilter.includes(type!)}
                    onChange={(e) => {
                      const newFilter = typeFilter.filter(t => t !== 'all');
                      if (e.target.checked) {
                        setTypeFilter([...newFilter, type!]);
                      } else {
                        setTypeFilter(newFilter.filter(t => t !== type));
                      }
                    }}
                  />
                  <span>{type}</span>
                </label>
              ))}
            </div>

            <div className="filter-actions">
              {selectedLocation && (
                <div className="mb-3 text-sm text-amber-900 font-semibold">
                  Focused Location: {selectedLocation.name}
                </div>
              )}
              <button 
                className="btn btn-secondary btn-sm"
                onClick={() => {
                  setStatusFilter(['all']);
                  setTypeFilter(['all']);
                  setSelectedQuestId(undefined);
                  setSelectedLocationId(undefined);
                }}
              >
                Clear All
              </button>
            </div>
          </div>
          
          {/* Attribution */}
          <div className="filter-attribution">
            <p><strong>Map Credit</strong></p>
            <p>Credits to Emil Johansson, creator of <em>lotrproject.com</em>, for creating the map used in this website.</p>
            <p>Created by Yohann Bethoule, 2022</p>
          </div>
        </aside>

        {/* Map Section */}
        <div className="map-main-content">
          <button
            className={`filter-toggle-btn ${filterOpen ? 'filter-open' : ''}`}
            onClick={toggleFilterSidebar}
            title="Toggle filters"
          >
            ☰
          </button>

          <MiddleEarthMap
            locations={locations}
            quests={filteredQuests.filter(q => q.location_id)}
            selectedLocationId={selectedLocationId}
            selectedQuestId={selectedQuestId}
            zoomToLocation={zoomToLocation}
            onLocationClick={handleLocationClick}
            onQuestClick={handleQuestClick}
            onCompleteQuest={handleCompleteQuest}
            onCharacterClick={handleCharacterClick}
          />

          {showCharacterPanel && (
            <div className="map-character-panel">
              <MapCharacterPanel onClose={() => setShowCharacterPanel(false)} />
            </div>
          )}



          {/* Quest Details Card */}
          {selectedQuest && (
            <div className="quest-details-card">
              <div className="quest-details-header">
                <h2>{selectedQuest.title}</h2>
                <button
                  className="close-btn"
                  onClick={() => setSelectedQuestId(undefined)}
                  aria-label="Close quest details"
                >
                  ✕
                </button>
              </div>

              <div className="quest-details-body">
                <div className="quest-badges quest-badges-map">
                  {selectedQuest.quest_type && (
                    <span className="quest-type-badge quest-chip" title={selectedQuest.quest_type}>
                      <span className="quest-chip-icon" aria-hidden="true">{getQuestTypeIcon(selectedQuest.quest_type)}</span>
                      <span className="quest-chip-label">{selectedQuest.quest_type}</span>
                    </span>
                  )}
                  <span className={`quest-status quest-status-${getStatusClass(selectedQuest.status || '')} quest-chip`}>
                    <span className="quest-chip-label">{getStatusText(selectedQuest.status || '')}</span>
                  </span>
                  {selectedQuest.priority && <span className="priority-badge">Priority: {selectedQuest.priority}</span>}
                </div>

                {selectedQuest.description && (
                  <div className="quest-description">
                    <p>{selectedQuest.description}</p>
                  </div>
                )}

                {selectedQuest.quest_type && (
                  <div className="quest-info-row">
                    <strong>Type:</strong> {selectedQuest.quest_type}
                  </div>
                )}

                {selectedQuest.location_name && (
                  <div className="quest-info-row">
                    <strong>Location:</strong> {selectedQuest.location_name}
                  </div>
                )}

                {selectedQuest.assignee_name && (
                  <div className="quest-info-row">
                    <strong>Assigned to:</strong> {selectedQuest.assignee_name}
                  </div>
                )}

                {selectedQuest.character_quote && (
                  <div className="quest-quote">
                    <em>"{selectedQuest.character_quote}"</em>
                  </div>
                )}
              </div>

              <div className="quest-details-actions">
                {selectedQuest.status !== 'it_is_done' && selectedQuest.status !== 'completed' && (
                  <button
                    className="btn btn-secondary btn-sm map-action-btn"
                    onClick={() => handleCompleteQuest(selectedQuest.id)}
                  >
                    Complete Quest
                  </button>
                )}
                <button
                  className="btn btn-secondary btn-sm map-action-btn"
                  onClick={() => {
                    setSelectedQuestId(undefined);
                  }}
                >
                  Close
                </button>
                <button
                  className="btn btn-primary btn-sm map-action-btn"
                  onClick={() => {
                    navigate('/quests', { state: { selectedQuestId: selectedQuest.id } });
                  }}
                >
                  View Full Details →
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default MapPage;
