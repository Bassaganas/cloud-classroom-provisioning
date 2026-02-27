/**
 * MiddleEarthMap Component
 * 
 * Interactive Middle-earth map using Leaflet.js
 * Inspired by and adapted from MiddleEarthMap by Yohann Bethoule
 * Original project: https://github.com/YohannBethoule/MiddleEarthMap
 * Live demo: https://middleearthmap.app/
 */

import React, { useEffect, useMemo, useRef } from 'react';
import { MapContainer, ImageOverlay, useMap } from 'react-leaflet';
import L from 'leaflet';
// Fix for default marker icons in Leaflet with webpack
import 'leaflet/dist/leaflet.css';
// @ts-ignore - leaflet.markercluster extends Leaflet namespace
import 'leaflet.markercluster';
import { Location, Quest } from '../types';
import './MiddleEarthMap.css';

// Extend Leaflet types for markercluster
declare module 'leaflet' {
  namespace L {
    function markerClusterGroup(options?: any): any;
  }
}

// Helper function to safely access marker icon element
// Note: _icon is a private property of Leaflet Marker, but we need it for styling
function getMarkerIcon(marker: L.Marker): HTMLElement | null {
  // @ts-expect-error - _icon is a private property but necessary for DOM manipulation
  return marker._icon || null;
}

// Fix for default marker icons - use require for images to avoid TypeScript errors
// eslint-disable-next-line @typescript-eslint/no-var-requires
const icon = require('leaflet/dist/images/marker-icon.png');
// eslint-disable-next-line @typescript-eslint/no-var-requires
const iconShadow = require('leaflet/dist/images/marker-shadow.png');

const DefaultIcon = L.icon({
  iconUrl: icon.default || icon,
  shadowUrl: iconShadow.default || iconShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
});

L.Marker.prototype.options.icon = DefaultIcon;

// Helper function to get quest type icon
function getQuestTypeIcon(questType?: string): string {
  const iconMap: { [key: string]: string } = {
    'The Journey': '🧭',
    'The Battle': '⚔️',
    'The Fellowship': '👥',
    'The Ring': '💍',
    'Dark Magic': '👁️'
  };
  return iconMap[questType || ''] || '📜';
}

// Helper function to get status display text
function getStatusText(status: string): string {
  const statusMap: { [key: string]: string } = {
    'not_yet_begun': 'Not Yet Begun',
    'the_road_goes_ever_on': 'The Road Goes Ever On...',
    'it_is_done': 'It Is Done',
    'the_shadow_falls': 'The Shadow Falls',
    'pending': 'Not Yet Begun',
    'in_progress': 'The Road Goes Ever On...',
    'completed': 'It Is Done',
    'blocked': 'The Shadow Falls'
  };
  return statusMap[status] || String(status).replace(/_/g, ' ');
}

interface MiddleEarthMapProps {
  locations: Location[];
  quests: Quest[];  // Quests to count per location
  selectedLocationId?: number;
  selectedQuestId?: number;  // Support quest selection
  onLocationClick: (locationId: number) => void;
  onQuestClick?: (questId: number) => void;  // Support quest click
  onCompleteQuest?: (questId: number) => void;  // Support quest completion
  focusLocationId?: number;  // Location to focus on
  zoomToLocation?: number;  // Location to zoom to from navigation
  onFocusComplete?: () => void;  // Callback when focus animation completes
}

// Component to handle map bounds and view updates
// For L.CRS.Simple (pixel-based), we disable bounds fitting to avoid animation loops
function MapBoundsHandler({ bounds, initialFit }: { bounds: L.LatLngBounds; initialFit: boolean }) {
  const map = useMap();
  
  useEffect(() => {
    if (initialFit && map) {
      // Set initial view without animation to avoid triggering panning loops
      map.setView([2172, 2500], -1, { animate: false });
    }
  }, [map, initialFit]);
  
  return null;
}

// Component to focus map on a location
function MapFocusHandler({ locationId, locations, convertToLatLng, onFocused }: { 
  locationId?: number; 
  locations: Location[];
  convertToLatLng: (mapX: number, mapY: number) => [number, number];
  onFocused?: () => void;
}) {
  const map = useMap();
  const lastFocusedId = useRef<number | undefined>();
  
  useEffect(() => {
    if (locationId && locationId !== lastFocusedId.current) {
      const location = locations.find(loc => loc.id === locationId);
      if (location && location.map_x !== undefined && location.map_y !== undefined) {
        const [lat, lng] = convertToLatLng(location.map_x, location.map_y);
        
        // Use setView for pixel-based coordinate system instead of fitBounds
        // Aim for a comfortable zoom level (0 or 1)
        map.setView([lat, lng], 0, { animate: true, duration: 0.5 });
        
        lastFocusedId.current = locationId;
        // Call onFocused callback after a delay to allow animation
        if (onFocused) {
          setTimeout(() => onFocused(), 600);
        }
      }
    }
  }, [map, locationId, locations, convertToLatLng, onFocused]);
  
  // Add max bounds to prevent panning outside the map
  useEffect(() => {
    const mapBounds: [[number, number], [number, number]] = [
      [0, 0],
      [4344, 5000]
    ];
    const bounds = L.latLngBounds(mapBounds[0], mapBounds[1]);
    map.setMaxBounds(bounds);
    // Don't use panInsideBounds on drag - setMaxBounds is sufficient and prevents infinite loops
  }, [map]);
  
  return null;
}

// Calculate offset for quests at the same location (spiral pattern)
// Returns offset in pixel coordinates [y, x] for L.CRS.Simple
function getQuestOffset(index: number, total: number): [number, number] {
  if (total === 1) return [0, 0];
  const angle = (2 * Math.PI * index) / total;
  const radius = 30; // pixel offset (works directly with L.CRS.Simple)
  // In L.CRS.Simple, coordinates are [y, x] where y increases downward
  // Return offset as [y_offset, x_offset] in pixel coordinates
  return [Math.sin(angle) * radius, Math.cos(angle) * radius];
}

// Component to add individual quest markers
function QuestMarkersComponent({
  quests,
  locations,
  selectedQuestId,
  convertToLatLng,
  onQuestClick,
  onCompleteQuest
}: {
  quests: Quest[];
  locations: Location[];
  selectedQuestId?: number;
  convertToLatLng: (mapX: number, mapY: number) => [number, number];
  onQuestClick?: (questId: number) => void;
  onCompleteQuest?: (questId: number) => void;
}) {
  const map = useMap();
  const layerGroupRef = useRef<L.LayerGroup | null>(null);

  // Group quests by location for offset calculation
  // Filter out quests without location_id
  const questsByLocation = useMemo(() => {
    const questsWithLocations = quests.filter(quest => quest.location_id);
    if (quests.length > questsWithLocations.length) {
      console.warn(`Warning: ${quests.length - questsWithLocations.length} quest(s) without location_id will not be displayed on the map.`);
    }
    return questsWithLocations.reduce((acc, quest) => {
      if (quest.location_id) {
        if (!acc[quest.location_id]) {
          acc[quest.location_id] = [];
        }
        acc[quest.location_id].push(quest);
      }
      return acc;
    }, {} as Record<number, Quest[]>);
  }, [quests]);

  useEffect(() => {
    // Wait for map to be ready
    if (!map || !map.getContainer()) {
      return;
    }

    // Wait for map to be fully initialized and image overlay to load
    const checkMapReady = () => {
      const container = map.getContainer();
      if (!container) {
        return false;
      }
      
      // Check if Leaflet map is initialized
      if (!map.getSize || map.getSize().x === 0) {
        return false;
      }
      
      // Check if image overlay is loaded (look for the image element)
      const imageOverlay = container.querySelector('img.leaflet-image-layer');
      if (!imageOverlay || !(imageOverlay instanceof HTMLImageElement) || !imageOverlay.complete) {
        return false;
      }
      
      return true;
    };

    // Retry mechanism to wait for map to be ready
    let retryCount = 0;
    const maxRetries = 20; // 2 seconds max wait (20 * 100ms)
    
    const tryAddMarkers = () => {
      if (!checkMapReady()) {
        retryCount++;
        if (retryCount < maxRetries) {
          setTimeout(tryAddMarkers, 100);
          return;
        } else {
          console.warn('Map not ready after max retries, adding markers anyway');
        }
      }

      // Remove existing layer group if it exists
      if (layerGroupRef.current) {
        map.removeLayer(layerGroupRef.current);
        layerGroupRef.current = null;
      }

      // Create a new layer group for quest markers (ensures they render on top)
      const questLayerGroup = L.layerGroup();
      
      // Add markers for quests with locations
      Object.entries(questsByLocation).forEach(([locationIdStr, locationQuests]) => {
        const locationId = parseInt(locationIdStr, 10);
        const location = locations.find(loc => loc.id === locationId);
        
        if (location && location.map_x !== undefined && location.map_y !== undefined) {
          const [baseLat, baseLng] = convertToLatLng(location.map_x, location.map_y);
          
          locationQuests.forEach((quest, index) => {
          // Calculate offset for this quest
          const [offsetY, offsetX] = getQuestOffset(index, locationQuests.length);
          const [lat, lng] = [baseLat + offsetY, baseLng + offsetX];
          const isSelected = selectedQuestId === quest.id;
          
          // Create quest marker icon (slightly larger for better visibility)
          const questIcon = L.divIcon({
            className: 'quest-marker-icon',
            html: `
              <div class="quest-marker ${isSelected ? 'quest-marker-selected' : ''}" 
                   style="background-color: ${isSelected ? '#DAA520' : '#8B4513'}; pointer-events: auto;"
                   data-quest-id="${quest.id}"
                   data-quest-title="${quest.title.replace(/"/g, '&quot;')}">
                <div class="quest-marker-inner">${getQuestTypeIcon(quest.quest_type)}</div>
              </div>
            `,
            iconSize: [35, 35],
            iconAnchor: [17, 17],
            popupAnchor: [0, -17]
          });

          const marker = L.marker([lat, lng], { 
            icon: questIcon,
            zIndexOffset: 2000, // Ensure quest markers appear above location markers
            interactive: true, // Explicitly make marker interactive
            keyboard: true, // Enable keyboard navigation
            title: quest.title, // Tooltip on hover
            riseOnHover: true, // Raise marker on hover
            bubblingMouseEvents: false // Prevent event bubbling to map
          });

          // Add popup with full quest info
          const location = locations.find(loc => loc.id === quest.location_id);
          const popupContent = `
            <div class="quest-popup">
              <h4>${quest.title}</h4>
              ${quest.quest_type ? `<p class="quest-popup-type"><strong>${getQuestTypeIcon(quest.quest_type)} ${quest.quest_type}</strong>${quest.priority ? ` - ${quest.priority}` : ''}</p>` : ''}
              <p class="quest-popup-status">${getStatusText(quest.status)}</p>
              ${quest.description ? `<p class="quest-popup-description">${quest.description}</p>` : ''}
              ${location ? `<p class="quest-popup-location">📍 ${location.name}, ${location.region}</p>` : ''}
              ${quest.assignee_name ? `<p class="quest-popup-assignee">👤 Assigned to: ${quest.assignee_name}</p>` : ''}
              <div class="quest-popup-actions">
                <button class="btn-view-quest" onclick="window.questClickHandler && window.questClickHandler(${quest.id})">
                  View Quest
                </button>
                ${quest.status !== 'it_is_done' && quest.status !== 'completed' ? `
                  <button class="btn-complete-quest" onclick="window.completeQuestHandler && window.completeQuestHandler(${quest.id})">
                    Complete Quest
                  </button>
                ` : ''}
              </div>
            </div>
          `;
          marker.bindPopup(popupContent, {
            maxWidth: 350,
            className: 'quest-popup-wrapper',
            autoPan: true, // Auto-pan map to show popup
            autoPanPadding: [50, 50], // Padding around popup
            closeOnClick: false, // Don't close on map click
            autoClose: false, // Don't auto-close when another popup opens
            keepInView: true // Keep popup in view when panning
          });

          // Add multiple event handlers for better interactivity
          marker.on('click', (e) => {
            // Stop event propagation to prevent map click
            if (e.originalEvent) {
              e.originalEvent.stopPropagation();
              e.originalEvent.stopImmediatePropagation();
            }
            // Open popup immediately
            marker.openPopup();
            // Call callback if provided
            if (onQuestClick) {
              onQuestClick(quest.id);
            }
          });

          // Add hover effects for better UX
          marker.on('mouseover', () => {
            marker.setZIndexOffset(3000); // Raise on hover
          });

          marker.on('mouseout', () => {
            marker.setZIndexOffset(2000); // Reset z-index
          });

          // Ensure marker is clickable
          marker.options.interactive = true;
          
          // Add marker to layer group
          questLayerGroup.addLayer(marker);
          
          // After marker is added, ensure icon is clickable
          marker.on('add', () => {
            const iconElement = getMarkerIcon(marker);
            if (iconElement) {
              iconElement.style.pointerEvents = 'auto';
              iconElement.style.cursor = 'pointer';
              iconElement.setAttribute('data-quest-id', quest.id.toString());
              iconElement.setAttribute('data-quest-title', quest.title);
            }
          });
          
          // Also set immediately if icon already exists
          setTimeout(() => {
            const iconElement = getMarkerIcon(marker);
            if (iconElement) {
              iconElement.style.pointerEvents = 'auto';
              iconElement.style.cursor = 'pointer';
            }
          }, 100);
          });
        }
      });

      // Add layer group to map (this ensures quest markers render on top)
      // Add quest markers after location markers to ensure they're on top
      questLayerGroup.addTo(map);
      layerGroupRef.current = questLayerGroup;
      
      // Ensure all markers in the group are interactive
      let interactiveCount = 0;
      questLayerGroup.eachLayer((layer) => {
        if (layer instanceof L.Marker) {
          layer.options.interactive = true;
          interactiveCount++;
          // Force marker to be clickable - use setTimeout to ensure icon is rendered
          setTimeout(() => {
            const iconElement = getMarkerIcon(layer);
            if (iconElement) {
              iconElement.style.pointerEvents = 'auto';
              iconElement.style.cursor = 'pointer';
              // Also set on child elements
              const children = iconElement.querySelectorAll('*');
              children.forEach((child) => {
                if (child instanceof HTMLElement) {
                  child.style.pointerEvents = 'auto';
                  child.style.cursor = 'pointer';
                }
              });
            }
          }, 50);
        }
      });
      
      // Debug: Log marker count and details
      const markerCount = Object.values(questsByLocation).flat().length;
      if (markerCount > 0) {
        console.log(`✓ Added ${markerCount} quest markers to map (${interactiveCount} interactive)`);
        console.log(`  Quest locations: ${Object.keys(questsByLocation).join(', ')}`);
      } else {
        console.warn('⚠ No quest markers to display - ensure quests have location_id');
        console.warn(`  Total quests: ${quests.length}, Quests with locations: ${quests.filter(q => q.location_id).length}`);
      }

      // Store click handlers globally for popup buttons
      if (onQuestClick) {
        (window as any).questClickHandler = onQuestClick;
      }
      if (onCompleteQuest) {
        (window as any).completeQuestHandler = onCompleteQuest;
      }
    };

    // Start the retry mechanism
    tryAddMarkers();

    // Cleanup
    return () => {
      if (layerGroupRef.current) {
        map.removeLayer(layerGroupRef.current);
        layerGroupRef.current = null;
      }
      delete (window as any).questClickHandler;
      delete (window as any).completeQuestHandler;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, questsByLocation, locations, selectedQuestId, convertToLatLng, onQuestClick, onCompleteQuest]);

  return null;
}

// Custom marker icon with LOTR styling and quest count badge
function createLocationMarkerIcon(questCount: number, isSelected: boolean) {
  const color = isSelected ? '#DAA520' : '#8B4513';
  return L.divIcon({
    className: 'location-marker-icon',
    html: `
      <div class="location-marker" style="background-color: ${color};">
        <div class="marker-pin-inner"></div>
        ${questCount > 0 ? `<div class="quest-count-badge"><span>${questCount}</span></div>` : ''}
      </div>
    `,
    iconSize: [40, 50],
    iconAnchor: [20, 50],
    popupAnchor: [0, -50]
  });
}

// Component to handle marker clustering using leaflet.markercluster directly
function MarkerClusterComponent({
  locations,
  questsByLocation,
  selectedLocationId,
  convertToLatLng,
  onLocationClick
}: {
  locations: Location[];
  questsByLocation: Record<number, number>;
  selectedLocationId?: number;
  convertToLatLng: (mapX: number, mapY: number) => [number, number];
  onLocationClick: (locationId: number) => void;
}) {
  const map = useMap();
  const clusterGroupRef = useRef<any>(null);

  useEffect(() => {
    // Wait for map to be ready
    if (!map || !map.getContainer()) {
      return;
    }

    // Wait for map to be fully initialized and image overlay to load
    const checkMapReady = () => {
      const container = map.getContainer();
      if (!container) {
        return false;
      }
      
      // Check if Leaflet map is initialized
      if (!map.getSize || map.getSize().x === 0) {
        return false;
      }
      
      // Check if image overlay is loaded (look for the image element)
      const imageOverlay = container.querySelector('img.leaflet-image-layer');
      if (!imageOverlay || !(imageOverlay instanceof HTMLImageElement) || !imageOverlay.complete) {
        return false;
      }
      
      return true;
    };

    // Retry mechanism to wait for map to be ready
    let retryCount = 0;
    const maxRetries = 20; // 2 seconds max wait (20 * 100ms)
    
    const tryAddMarkers = () => {
      if (!checkMapReady()) {
        retryCount++;
        if (retryCount < maxRetries) {
          setTimeout(tryAddMarkers, 100);
          return;
        } else {
          console.warn('Map not ready after max retries, adding location markers anyway');
        }
      }

      // Remove existing cluster group if it exists
      if (clusterGroupRef.current) {
        map.removeLayer(clusterGroupRef.current);
        clusterGroupRef.current = null;
      }

      // Create cluster group with custom icon function
      // @ts-ignore - markerClusterGroup is added by leaflet.markercluster plugin
      const clusterGroup = L.markerClusterGroup({
        maxClusterRadius: 50,
        spiderfyOnMaxZoom: true,
        showCoverageOnHover: false,
        zoomToBoundsOnClick: true,
        iconCreateFunction: (cluster: { getChildCount: () => number }) => {
          const count = cluster.getChildCount();
          return L.divIcon({
            html: `<div class="marker-cluster">${count}</div>`,
            className: 'marker-cluster-icon',
            iconSize: L.point(40, 40)
          });
        }
      });

    // Add markers to cluster group
    locations
      .filter(loc => loc.map_x !== undefined && loc.map_y !== undefined)
      .forEach((location) => {
        const [lat, lng] = convertToLatLng(location.map_x!, location.map_y!);
        const isSelected = selectedLocationId === location.id;
        const questCount = questsByLocation[location.id] || 0;
        
        const marker = L.marker([lat, lng], {
          icon: createLocationMarkerIcon(questCount, isSelected)
        });

        // Add popup
        const popupContent = `
          <div class="location-popup">
            <h3>${location.name}</h3>
            <p class="location-region">${location.region}</p>
            ${location.description ? `<p class="location-description">${location.description}</p>` : ''}
            ${questCount > 0 ? `<p class="quest-count-info"><strong>${questCount}</strong> quest${questCount !== 1 ? 's' : ''} at this location</p>` : ''}
            <button class="btn-view-quests" onclick="window.locationClickHandler && window.locationClickHandler(${location.id})">
              View Quests Here
            </button>
          </div>
        `;
        marker.bindPopup(popupContent);

        // Add click handler
        marker.on('click', () => {
          onLocationClick(location.id);
        });

        clusterGroup.addLayer(marker);
      });

      // Add cluster group to map
      clusterGroup.addTo(map);
      clusterGroupRef.current = clusterGroup;

      // Store click handler globally for popup buttons
      (window as any).locationClickHandler = onLocationClick;

      // Debug: Log location marker count
      const locationCount = locations.filter(loc => loc.map_x !== undefined && loc.map_y !== undefined).length;
      if (locationCount > 0) {
        console.log(`✓ Added ${locationCount} location markers to map`);
      } else {
        console.warn('⚠ No location markers to display - ensure locations have map_x and map_y coordinates');
      }
    };

    // Start the retry mechanism
    tryAddMarkers();

    // Cleanup
    return () => {
      if (clusterGroupRef.current) {
        map.removeLayer(clusterGroupRef.current);
        clusterGroupRef.current = null;
      }
      delete (window as any).locationClickHandler;
    };
  }, [map, locations, questsByLocation, selectedLocationId, convertToLatLng, onLocationClick]);

  return null;
}

const MiddleEarthMap: React.FC<MiddleEarthMapProps> = ({ 
  locations, 
  quests,
  selectedLocationId,
  selectedQuestId,
  onLocationClick,
  onQuestClick,
  onCompleteQuest,
  focusLocationId,
  zoomToLocation,
  onFocusComplete
}) => {
  // Define bounds for Middle-earth map image
  // Map image dimensions: 5000x4344 pixels (width x height)
  // In L.CRS.Simple, bounds are [height, width] = [4344, 5000]
  // Original map from MiddleEarthMap by Yohann Bethoule
  // Map image credit: Emil Johansson (lotrproject.com)
  const mapBounds: [[number, number], [number, number]] = [
    [0, 0],        // Southwest corner (top-left in Simple CRS)
    [4344, 5000]   // Northeast corner (bottom-right) - height, width
  ];

  // Convert pixel coordinates (map_x, map_y) to Leaflet coordinates
  // In L.CRS.Simple, coordinates are [y, x] where:
  // - y ranges from 0 (top) to 4344 (bottom) - image height  
  // - x ranges from 0 (left) to 5000 (right) - image width
  // Database coordinates need Y inversion: the image coordinate system starts from top,
  // but we need to use [mapHeight - mapY, mapX] for proper positioning
  const convertToLatLng = (mapX: number, mapY: number): [number, number] => {
    // In L.CRS.Simple, y increases downward, so we invert: [height - y, x]
    return [mapBounds[1][0] - mapY, mapX];
  };

  // Group quests by location_id to calculate counts
  const questsByLocation = useMemo(() => {
    return quests.reduce((acc, quest) => {
      if (quest.location_id) {
        acc[quest.location_id] = (acc[quest.location_id] || 0) + 1;
      }
      return acc;
    }, {} as Record<number, number>);
  }, [quests]);

  // Track if this is the initial mount for fitBounds
  const [initialFit, setInitialFit] = React.useState(true);
  
  useEffect(() => {
    // After first render, disable fitBounds
    setInitialFit(false);
  }, []);

  return (
    <div className="middle-earth-map-container">
      <MapContainer
        center={[2172, 2500]}  // Center of map (4344/2, 5000/2)
        zoom={-1}  // Good initial zoom for full map
        style={{ height: '100%', width: '100%' }}
        crs={L.CRS.Simple}
        minZoom={-2}
        maxZoom={2}
        scrollWheelZoom={true}
        zoomControl={true}
        attributionControl={false}
        dragging={true}
        boxZoom={true}
      >
        {/* Middle-earth map image overlay */}
        {/* Map image from MiddleEarthMap by Yohann Bethoule */}
        {/* Original map credit: Emil Johansson (lotrproject.com) */}
        <ImageOverlay
          url="/middle-earth-map.webp"
          bounds={mapBounds}
          opacity={1.0}
        />
        
        {/* Set map bounds - only on initial mount */}
        <MapBoundsHandler 
          bounds={L.latLngBounds(mapBounds[0], mapBounds[1])} 
          initialFit={initialFit}
        />
        
        {/* Focus handler */}
        <MapFocusHandler 
          locationId={zoomToLocation || focusLocationId}
          locations={locations}
          convertToLatLng={convertToLatLng}
          onFocused={onFocusComplete}
        />
        
        {/* Location markers with clustering - added first so quest markers render on top */}
        <MarkerClusterComponent
          locations={locations}
          questsByLocation={questsByLocation}
          selectedLocationId={selectedLocationId}
          convertToLatLng={convertToLatLng}
          onLocationClick={onLocationClick}
        />
        
        {/* Individual quest markers - added last to ensure they render on top and are clickable */}
        <QuestMarkersComponent
          quests={quests}
          locations={locations}
          selectedQuestId={selectedQuestId}
          convertToLatLng={convertToLatLng}
          onQuestClick={onQuestClick}
          onCompleteQuest={onCompleteQuest}
        />
      </MapContainer>
    </div>
  );
};

export default MiddleEarthMap;
