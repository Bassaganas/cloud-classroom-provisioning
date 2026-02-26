/**
 * MarkersController Component
 * Loads and renders markers based on filter state
 */

import React, { useEffect, useRef } from 'react';
import L from 'leaflet';
import type { MarkerData, FilterState, MarkerTags, Quest } from './types';
import {
  battleIcon,
  deathIcon,
  encounterIcon,
  hobbitIcon,
  dwarfIcon,
  elfIcon,
  humanIcon,
  darkIcon
} from './MapIcons';

interface MarkersControllerProps {
  map: L.Map | null;
  cluster: any;
  markers: MarkerData[];
  filters: FilterState;
  onMarkerClick?: (questId: number, quest?: Quest) => void;
}

const createInfoDialog = (data: MarkerData): string => {
  let info = '';
  if (data.title) {
    info += `<h1 class="title">${data.title}`;
    if (data.sindarinTitle) {
      info += ` (${data.sindarinTitle})`;
    }
    info += `</h1>`;
  }
  if (data.date) {
    info += `<h2 class="date">[${data.date}]</h2>`;
  }
  if (data.description) {
    info += `<p class="description">${data.description}</p>`;
  }
  
  // If this is a quest marker, show quest action button instead of learning link
  if (data.questId && data.quest) {
    info += `<span class="info-link-container"><button class="info-link quest-link" onclick="window.__questClick && window.__questClick(${data.questId})">View Quest Details</button></span>`;
  } else if (data.infoLink) {
    info += `<span class="info-link-container"><a class="info-link" href="${data.infoLink}" target="_blank" rel="noopener noreferrer">Learn more on Tolkien Gateway</a></span>`;
  }
  return info;
};

const createMarker = (map: L.Map, data: MarkerData, onQuestClick?: (questId: number, quest?: Quest) => void): L.Marker => {
  // Convert pixel coordinates to Leaflet Simple CRS coordinates
  // In Simple CRS: [y, x] where y increases downward
  // Map bounds: [[0, 0], [4334, 5000]]
  const sol = L.latLng([4334 - data.y, data.x]);
  
  // Debug coordinate conversion
  if (data.title === 'Minas Tirith' || data.title === 'Bree') {
    // Avoid calling map.getBounds() synchronously as the map pane
    // may not yet have a DOM position attached (_leaflet_pos).
    // Guard with try/catch to prevent runtime errors.
    let bounds;
    try {
      bounds = map ? map.getBounds() : undefined;
    } catch (err) {
      bounds = undefined;
    }
    console.log(`Marker ${data.title}:`, {
      original: { x: data.x, y: data.y },
      converted: sol,
      bounds
    });
  }
  
  let markerOptions: L.MarkerOptions = {
    title: data.title,
    alt: data.title,
  };

  // Determine icon based on tags or quest status
  if (data.quest?.status === 'it_is_done') {
    markerOptions.icon = encounterIcon; // Use encounter icon for completed quests
  } else if (data.quest?.status === 'the_shadow_falls') {
    markerOptions.icon = darkIcon; // Use dark icon for failed/blocked quests
  } else if (data.quest?.status === 'the_road_goes_ever_on') {
    markerOptions.icon = battleIcon; // Use battle icon for in-progress quests
  } else if (data.tags?.events?.includes('battle')) {
    markerOptions.icon = battleIcon;
  } else if (data.tags?.events?.includes('death')) {
    markerOptions.icon = deathIcon;
  } else if (data.tags?.events?.includes('encounter')) {
    markerOptions.icon = encounterIcon;
  } else if (data.tags?.places?.includes('dwarven')) {
    markerOptions.icon = dwarfIcon;
  } else if (data.tags?.places?.includes('elven')) {
    markerOptions.icon = elfIcon;
  } else if (data.tags?.places?.includes('human')) {
    markerOptions.icon = humanIcon;
  } else if (data.tags?.places?.includes('dark')) {
    markerOptions.icon = darkIcon;
  } else if (data.tags?.places?.includes('hobbit')) {
    markerOptions.icon = hobbitIcon;
  } else {
    // Default icon if no tag matches - use human icon as fallback
    markerOptions.icon = humanIcon;
    console.warn('No matching icon for marker:', data.title, 'tags:', data.tags);
  }

  const marker = L.marker(sol, markerOptions).bindPopup(createInfoDialog(data));

  // Handle marker click for quests
  if (data.questId && onQuestClick) {
    marker.on('click', () => {
      onQuestClick(data.questId!, data.quest);
    });
  }

    // Add smooth bounce if available
    if ((marker as any).setBouncingOptions) {
      (marker as any).setBouncingOptions({
        elastic: false,
        bounceHeight: 8
      });
      marker.on('mouseover', function(this: L.Marker) {
        const markerWithBounce = this as any;
        if (markerWithBounce.bounce) {
          markerWithBounce.bounce(1);
        }
      });
    }

  return marker;
};

export const MarkersController: React.FC<MarkersControllerProps> = ({
  map,
  cluster,
  markers,
  filters,
  onMarkerClick
}) => {
  const markersRef = useRef<L.Marker[]>([]);

  useEffect(() => {
    if (!map || !cluster) {
      console.log('MarkersController: Waiting for map/cluster', { map: !!map, cluster: !!cluster });
      return;
    }
    
    if (markers.length === 0) {
      console.warn('MarkersController: No markers data available');
      return;
    }

    // Clear existing markers - defer to ensure map is ready
    requestAnimationFrame(() => {
      try {
        cluster.clearLayers();
      } catch (err) {
        console.warn('Error clearing cluster layers:', err);
      }
    });
    markersRef.current = [];

    // Filter markers based on filter state
    const filteredMarkers: MarkerData[] = [];
    
    // Only check categories that exist in MarkerTags (exclude 'map-layers')
    const markerCategories: Array<keyof MarkerTags> = ['places', 'events', 'quests', 'paths'];
    
    console.log('Filtering markers:', { 
      totalMarkers: markers.length, 
      filters,
      sampleMarker: markers[0],
      sampleMarkerTags: markers[0]?.tags
    });
    
    // Check which categories have active filters
    const activeCategories = markerCategories.filter(cat => {
      const categoryFilters = filters[cat];
      return categoryFilters && categoryFilters.length > 0;
    });
    
    console.log('Active filter categories:', activeCategories);
    
    // Filter logic matches original MiddleEarthMap:
    // Check if marker matches ANY filter in ANY category
    // If ANY tag in ANY category matches ANY filter, render it
    for (const marker of markers) {
      let isRendered = false;
      
      // Check all categories and their filters
      for (const category of markerCategories) {
        const categoryFilters = filters[category];
        if (!categoryFilters || categoryFilters.length === 0) {
          continue; // Skip categories with no filters
        }
        
        // Check if any filter in this category matches marker's tags
        for (const filter of categoryFilters) {
          if (marker.tags[category]?.includes(filter)) {
            isRendered = true;
            break;
          }
        }
        
        if (isRendered) break;
      }
      
      if (isRendered) {
        filteredMarkers.push(marker);
      }
    }
    
    console.log('Filtered markers count:', filteredMarkers.length);
    if (filteredMarkers.length > 0) {
      console.log('First filtered marker:', filteredMarkers[0]);
    }

    // Create and add markers
    const leafletMarkers = filteredMarkers.map(markerData => {
      const marker = createMarker(map, markerData, onMarkerClick);
      // Verify icon is set
      if (!marker.options.icon) {
        console.warn('Marker created without icon:', markerData.title);
      }
      return marker;
    });

    console.log('Created markers:', leafletMarkers.length);
    if (leafletMarkers.length > 0) {
      console.log('First marker details:', {
        title: leafletMarkers[0].options.title,
        icon: leafletMarkers[0].options.icon?.options?.iconUrl,
        position: leafletMarkers[0].getLatLng(),
        visible: leafletMarkers[0].options.icon ? 'YES' : 'NO ICON!'
      });
      
      // Verify icon is actually set
      leafletMarkers.slice(0, 3).forEach((m, i) => {
        console.log(`Marker ${i + 1}:`, {
          title: m.options.title,
          hasIcon: !!m.options.icon,
          iconUrl: m.options.icon?.options?.iconUrl
        });
      });
    }
    markersRef.current = leafletMarkers;
    
    if (leafletMarkers.length > 0) {
      // Use setTimeout to ensure map is fully ready before adding layers
      const timeoutId = setTimeout(() => {
        try {
          cluster.addLayers(leafletMarkers);
          const clusterLayers = cluster.getLayers();
          console.log('Markers added to cluster. Cluster layer count:', clusterLayers.length);
          console.log('Map bounds:', map.getBounds());
          console.log('Map zoom:', map.getZoom());
        } catch (error) {
          console.error('Error adding markers to cluster:', error);
        }
      }, 100);
      
      return () => {
        clearTimeout(timeoutId);
        try {
          cluster.clearLayers();
        } catch (err) {
          console.warn('Error clearing cluster on cleanup:', err);
        }
        markersRef.current = [];
      };
    } else {
      console.warn('No markers to add to cluster! Check filter logic.');
      return () => {
        try {
          cluster.clearLayers();
        } catch (err) {
          console.warn('Error clearing cluster on cleanup:', err);
        }
        markersRef.current = [];
      };
    }
  }, [map, cluster, markers, filters, onMarkerClick]);

  return null;
};
