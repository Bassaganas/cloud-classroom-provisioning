import React, { useState, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import MiddleEarthMap from '../components/MiddleEarthMap';
import { apiService } from '../services/api';
import { Quest, Location, User } from '../types';
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
  const [zoomToLocation, setZoomToLocation] = useState<number | undefined>();
  const [loading, setLoading] = useState(true);
  const [filterOpen, setFilterOpen] = useState(window.innerWidth > 1024);

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

  // Apply filters
  const getFilteredQuests = (): Quest[] => {
    let filtered = allQuests;

    // Filter by status
    if (statusFilter.length > 0 && !statusFilter.includes('all')) {
      filtered = filtered.filter(q => statusFilter.includes(q.status || ''));
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

  const getStatusColor = (status: string): string => {
    const colors: Record<string, string> = {
      'not_yet_begun': '#888888',
      'the_road_goes_ever_on': '#FF6B6B',
      'it_is_done': '#51CF66',
      'the_shadow_falls': '#1A1A1A',
    };
    return colors[status] || '#888888';
  };

  const getStatusText = (status: string): string => {
    const texts: Record<string, string> = {
      'not_yet_begun': 'Not Yet Begun',
      'the_road_goes_ever_on': 'The Road Goes Ever On',
      'it_is_done': 'It Is Done',
      'the_shadow_falls': 'The Shadow Falls',
    };
    return texts[status] || status;
  };

  if (loading) {
    return (
      <div className="app-loading">
        <div className="loading-spinner">Loading the map of Middle-earth...</div>
      </div>
    );
  }

  return (
    <div className="map-page-full">
      <nav className="navbar">
        <Link to="/dashboard" className="navbar-brand">
          The Fellowship's Quest List
        </Link>
        <div className="navbar-nav">
          <Link to="/dashboard" className="nav-link">The Council Chamber</Link>
          <Link to="/quests" className="nav-link">The Scrolls of Middle-earth</Link>
          <Link to="/map" className="nav-link active">The Map of Middle-earth</Link>
          <button className="btn btn-secondary" onClick={onLogout}>
            Leave the Fellowship
          </button>
        </div>
      </nav>

      <div className="map-page-container">
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
              <button 
                className="btn btn-secondary btn-sm"
                onClick={() => {
                  setStatusFilter(['all']);
                  setTypeFilter(['all']);
                  setSelectedQuestId(undefined);
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
            selectedQuestId={selectedQuestId}
            zoomToLocation={zoomToLocation}
            onLocationClick={() => {}}
            onQuestClick={handleQuestClick}
          />



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
                <div className="quest-status" style={{ borderLeftColor: getStatusColor(selectedQuest.status || '') }}>
                  <span className="status-badge" style={{ backgroundColor: getStatusColor(selectedQuest.status || '') }}>
                    {getStatusText(selectedQuest.status || '')}
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
                <button
                  className="btn btn-secondary"
                  onClick={() => {
                    setSelectedQuestId(undefined);
                  }}
                >
                  Close
                </button>
                <button
                  className="btn btn-primary"
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
