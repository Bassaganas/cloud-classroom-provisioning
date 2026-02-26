/**
 * MiddleEarthMapPage Component
 * Main page that combines all MiddleEarthMap standalone components
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Link } from 'react-router-dom';
import L from 'leaflet';
import { MapController } from '../components/middleEarthMapStandalone/MapController';
import { MarkersController } from '../components/middleEarthMapStandalone/MarkersController';
import { PathsController } from '../components/middleEarthMapStandalone/PathsController';
import { FilterSidebar } from '../components/middleEarthMapStandalone/FilterSidebar';
import { QuestDetailsSidebar } from '../components/middleEarthMapStandalone/QuestDetailsSidebar';
import { RealWorldMapController } from '../components/middleEarthMapStandalone/RealWorldMapController';
import { LoaderScreen } from '../components/middleEarthMapStandalone/LoaderScreen';
import { MarkerData, PathData, FilterState, FilterCategory, Quest, Location } from '../components/middleEarthMapStandalone/types';
import { User } from '../types';
import './MiddleEarthMapPage.css';
import '../components/middleEarthMapStandalone/MiddleEarthMapStandalone.css';

// Load Ringbearer font
const fontFace = new FontFace('RingBearer', 'url(/middle-earth-map/fonts/RingbearerMedium.ttf)');
fontFace.load().then((loadedFont) => {
  document.fonts.add(loadedFont);
}).catch((error) => {
  console.warn('Failed to load Ringbearer font:', error);
});

interface MiddleEarthMapPageProps {
  user: User;
  onLogout: () => void;
}

const initialFilters: FilterState = {
  places: ['all', 'human', 'elven', 'dwarven', 'hobbit', 'dark'],
  events: ['all', 'battle', 'death', 'encounter'],
  quests: ['all', 'erebor', 'ring'],
  paths: [],
  'map-layers': [],
  questStatus: ['all', 'not_yet_begun', 'the_road_goes_ever_on', 'it_is_done', 'the_shadow_falls']
};

export const MiddleEarthMapPage: React.FC<MiddleEarthMapPageProps> = ({ user, onLogout }) => {
  const [mapLoaded, setMapLoaded] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [map, setMap] = useState<L.Map | null>(null);
  const [cluster, setCluster] = useState<any>(null);
  const [pathsLayer, setPathsLayer] = useState<L.LayerGroup | null>(null);
  const [markers, setMarkers] = useState<MarkerData[]>([]);
  const [quests, setQuests] = useState<Quest[]>([]);
  const [paths, setPaths] = useState<PathData[]>([]);
  const [filters, setFilters] = useState<FilterState>(initialFilters);
  const [sidebarOpen, setSidebarOpen] = useState(window.innerWidth > 840);
  const [questDetailsOpen, setQuestDetailsOpen] = useState(false);
  const [realWorldMapVisible, setRealWorldMapVisible] = useState(false);
  const [dataLoaded, setDataLoaded] = useState(false);
  const [selectedQuest, setSelectedQuest] = useState<Quest | null>(null);
  const loaderScreenRef = useRef<HTMLDivElement>(null);

  // Helper function to construct API URL
  // In Docker: use the 'backend' service name via Docker network
  // Otherwise: use the REACT_APP_API_URL environment variable or relative path
  const getApiUrl = (endpoint: string): string => {
    // If REACT_APP_API_URL is set in environment (for Caddy/production routing)
    // Note: endpoint already includes /api prefix, so we just use it directly
    if (process.env.REACT_APP_API_URL) {
      // Remove leading /api from endpoint if REACT_APP_API_URL is /api
      const cleanEndpoint = endpoint.replace(/^\/api/, '');
      return `${process.env.REACT_APP_API_URL}${cleanEndpoint}`;
    }
    
    // For development in Docker, use the backend service via Docker DNS
    // The backend service is at http://backend:5000 and handles /api/* routes
    if (process.env.NODE_ENV === 'development') {
      return `http://backend:5000${endpoint}`;
    }
    
    // Fallback to relative path (works through Caddy reverse proxy)
    return endpoint;
  };

  // Function to create markers from quests
  const createMarkersFromQuests = useCallback((questsData: Quest[], locationsData: Location[]): MarkerData[] => {
    return questsData
      .filter(quest => quest.location_id && quest.location_id > 0)
      .map(quest => {
        const location = locationsData.find(loc => loc.id === quest.location_id);
        
        if (!location || location.map_x === undefined || location.map_y === undefined) {
          return null;
        }
        
        return {
          title: quest.title,
          description: quest.description,
          x: location.map_x,
          y: location.map_y,
          questId: quest.id,
          quest: quest,
          tags: {
            questStatus: [quest.status || 'not_yet_begun'],
            quests: [quest.quest_type || 'other']
          }
        } as MarkerData;
      })
      .filter((marker): marker is MarkerData => marker !== null);
  }, []);

  // Load markers, paths, quests, and locations data
  useEffect(() => {
    const loadData = async () => {
      try {
        console.log('Loading Middle-earth map data and quests...');
        const questsUrl = getApiUrl('/api/quests/');
        const locationsUrl = getApiUrl('/api/locations/');
        console.log(`API URLs - Quests: ${questsUrl}, Locations: ${locationsUrl}`);
        
        const [markersResponse, pathsResponse, questsResponse, locationsResponse] = await Promise.all([
          fetch('/middle-earth-map/data/markers.json'),
          fetch('/middle-earth-map/data/paths.json'),
          fetch(questsUrl),
          fetch(locationsUrl)
        ]);

        if (!markersResponse.ok || !pathsResponse.ok) {
          throw new Error(`Failed to load static map data`);
        }

        const markersData: MarkerData[] = await markersResponse.json();
        const pathsData: PathData[] = await pathsResponse.json();
        
        // Load quests and locations, handle if API is unavailable
        let questsData: Quest[] = [];
        let locationsData: Location[] = [];
        
        try {
          if (questsResponse.ok) {
            const text = await questsResponse.text();
            if (text) {
              try {
                questsData = JSON.parse(text);
              } catch (parseErr) {
                console.warn('Failed to parse quests response as JSON:', parseErr);
              }
            }
          } else {
            console.warn(`Quests API returned status ${questsResponse.status}`);
          }
          
          if (locationsResponse.ok) {
            const text = await locationsResponse.text();
            if (text) {
              try {
                locationsData = JSON.parse(text);
              } catch (parseErr) {
                console.warn('Failed to parse locations response as JSON:', parseErr);
              }
            }
          } else {
            console.warn(`Locations API returned status ${locationsResponse.status}`);
          }
        } catch (apiError) {
          console.warn('Failed to load quests/locations from API:', apiError);
        }

        console.log(`Loaded ${markersData.length} base markers, ${pathsData.length} paths, ${questsData.length} quests`);
        
        // Create markers from quests
        const questMarkers = createMarkersFromQuests(questsData, locationsData);
        console.log(`Created ${questMarkers.length} markers from quests`);
        
        setMarkers([...markersData, ...questMarkers]);
        setPaths(pathsData);
        setQuests(questsData);
        setDataLoaded(true);
      } catch (error) {
        console.error('Failed to load map data:', error);
        // Still allow map to load even if data fails
        setDataLoaded(true);
      }
    };

    loadData();
  }, [createMarkersFromQuests]);

  // Auto-load map after data is loaded (or after short delay)
  useEffect(() => {
    if (dataLoaded) {
      // Auto-load map after data is ready
      const timer = setTimeout(() => {
        console.log('Auto-loading map...');
        setMapLoaded(true);
        setIsLoading(false);
      }, 500); // Small delay to show loader briefly
      return () => clearTimeout(timer);
    }
  }, [dataLoaded]);

  const handleLoadMap = () => {
    // Manual load button (optional, map auto-loads)
    console.log('Manual map load triggered');
    setMapLoaded(true);
    setIsLoading(false);
  };

  const handleMapReady = useCallback((mapInstance: L.Map, clusterInstance: any, pathsLayerInstance: L.LayerGroup) => {
    setMap(mapInstance);
    setCluster(clusterInstance);
    setPathsLayer(pathsLayerInstance);
  }, []);

  const handleFilterChange = useCallback((category: FilterCategory, filter: string, checked: boolean) => {
    setFilters(prev => {
      const newFilters = { ...prev };
      const categoryFilters = newFilters[category];
      
      if (!categoryFilters) {
        // If category doesn't exist, initialize it
        newFilters[category] = [filter];
        return newFilters;
      }
      
      if (checked) {
        if (!categoryFilters.includes(filter)) {
          newFilters[category] = [...categoryFilters, filter];
        }
      } else {
        newFilters[category] = categoryFilters.filter(f => f !== filter);
      }
      return newFilters;
    });
  }, []);

  const handleToggleRealWorldMap = useCallback(() => {
    setRealWorldMapVisible(prev => !prev);
  }, []);

  const handleMarkerClick = useCallback((questId: number, quest?: Quest) => {
    if (quest) {
      setSelectedQuest(quest);
      setQuestDetailsOpen(true);
      console.log('Selected quest:', quest);
    }
  }, []);

  // Set up window callback for popup button clicks
  useEffect(() => {
    (window as any).__questClick = (questId: number) => {
      const quest = quests.find(q => q.id === questId);
      if (quest) {
        handleMarkerClick(questId, quest);
      }
    };
    
    return () => {
      delete (window as any).__questClick;
    };
  }, [quests, handleMarkerClick]);

  // Handle loader screen fade out
  useEffect(() => {
    if (!isLoading && loaderScreenRef.current) {
      const loader = loaderScreenRef.current;
      // Start fade out
      loader.style.opacity = '0';
      loader.addEventListener('transitionend', () => {
        if (loader.parentNode) {
          loader.style.display = 'none';
        }
      }, { once: true });
    }
  }, [isLoading]);

  // Also hide loader when map is loaded
  useEffect(() => {
    if (mapLoaded && loaderScreenRef.current) {
      const loader = loaderScreenRef.current;
      loader.style.opacity = '0';
      setTimeout(() => {
        if (loader.parentNode) {
          loader.style.display = 'none';
        }
      }, 1000); // Wait for transition
    }
  }, [mapLoaded]);

  return (
    <div className="middle-earth-map-page">
      <nav className="navbar">
        <Link to="/dashboard" className="navbar-brand">
          The Fellowship's Quest List
        </Link>
        <div className="navbar-nav">
          <Link to="/dashboard" className="nav-link">The Council Chamber</Link>
          <Link to="/quests" className="nav-link">The Scrolls of Middle-earth</Link>
          <Link to="/map" className="nav-link">The Map of Middle-earth</Link>
          <Link to="/middle-earth-map" className="nav-link active">Middle-Earth Interactive Map</Link>
          <button className="btn btn-secondary" onClick={onLogout}>
            Leave the Fellowship
          </button>
        </div>
      </nav>

      {(isLoading || !mapLoaded) && (
        <div id="loader-screen" ref={loaderScreenRef}>
          <LoaderScreen onLoadMap={handleLoadMap} isLoading={isLoading} />
        </div>
      )}

      <div id="control-buttons">
        <button 
          type="button"
          id="open-filters-btn" 
          onClick={() => setSidebarOpen(true)}
        >
          <img alt="Open filters" src="/middle-earth-map/icons/layers.svg" />
        </button>
        <button
          type="button"
          id="map-comparison-btn" 
          title="Compare with Earth map"
          onClick={handleToggleRealWorldMap}
        >
          <img alt="Compare with Earth map" src="/middle-earth-map/icons/earth.svg" />
        </button>
      </div>

      <main style={{ position: 'relative', width: '100%', height: 'calc(100vh - 60px)' }}>
        {mapLoaded ? (
          <>
            <MapController onMapReady={handleMapReady} mapLoaded={mapLoaded} />
            {map && cluster && (
              <MarkersController map={map} cluster={cluster} markers={markers} filters={filters} onMarkerClick={handleMarkerClick} />
            )}
            {map && pathsLayer && (
              <PathsController pathsLayer={pathsLayer} paths={paths} filters={filters} />
            )}
            {map && (
              <RealWorldMapController isVisible={realWorldMapVisible} mainMap={map} />
            )}
          </>
        ) : (
          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center', 
            height: '100%',
            color: '#666'
          }}>
            {dataLoaded ? 'Loading map...' : 'Loading data...'}
          </div>
        )}
      </main>

      {mapLoaded && (
        <FilterSidebar
          filters={filters}
          onFilterChange={handleFilterChange}
          isOpen={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
        />
      )}

      {mapLoaded && (
        <QuestDetailsSidebar
          quest={selectedQuest}
          isOpen={questDetailsOpen}
          onClose={() => setQuestDetailsOpen(false)}
        />
      )}
    </div>
  );
};

export default MiddleEarthMapPage;
