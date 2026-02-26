/**
 * MapController Component
 * Initializes and manages the Leaflet map instance
 */

import React, { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
// @ts-ignore - markerClusterGroup extends Leaflet namespace
import 'leaflet.markercluster';
// Load marker cluster CSS
import 'leaflet.markercluster/dist/MarkerCluster.css';
import 'leaflet.markercluster/dist/MarkerCluster.Default.css';

// Extend Leaflet types
declare module 'leaflet' {
  namespace L {
    function markerClusterGroup(options?: any): any;
  }
}

// Extend Marker prototype for smooth bounce
declare global {
  interface Window {
    L: typeof L;
  }
}

interface MapControllerProps {
  onMapReady: (map: L.Map, cluster: any, pathsLayer: L.LayerGroup) => void;
  mapLoaded: boolean;
}

const getMinZoomFromDevice = (): number => {
  if (window.innerWidth < 768) {
    return -4;
  } else {
    return -2;
  }
};

export const MapController: React.FC<MapControllerProps> = ({ onMapReady, mapLoaded }) => {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const clusterRef = useRef<any>(null);
  const pathsLayerRef = useRef<L.LayerGroup | null>(null);
  const imageOverlayRef = useRef<L.ImageOverlay | null>(null);
  const readyNotifiedRef = useRef(false);

  useEffect(() => {
    if (!mapRef.current || !mapLoaded || mapInstanceRef.current) {
      return;
    }

    // Initialize map
    const map = L.map(mapRef.current, {
      crs: L.CRS.Simple,
      minZoom: getMinZoomFromDevice(),
      maxZoom: 2
    });

    const bounds: [[number, number], [number, number]] = [[0, 0], [4334, 5000]];
    
    // Add image overlay - verify path is correct
    const mapImage = '/middle-earth-map.webp';
    const imageOverlay = L.imageOverlay(mapImage, bounds);
    
    // Log for debugging
    console.log('Initializing Middle-earth map with image:', mapImage);
    
    imageOverlay.on('load', () => {
      console.log('Map image loaded successfully');
    });
    
    imageOverlay.on('error', (error: any) => {
      console.error('Failed to load map image:', error);
      console.error('Attempted to load from:', mapImage);
    });

    imageOverlay.addTo(map);
    imageOverlayRef.current = imageOverlay;

    map.fitBounds(bounds);

    // Create marker cluster group (plugin augments L; cast to any to satisfy TS)
    const cluster = (L as any).markerClusterGroup({
      maxClusterRadius: 20
    });
    map.addLayer(cluster);
    clusterRef.current = cluster;

    // Create paths layer
    const pathsLayer = L.layerGroup([]);
    map.addLayer(pathsLayer);
    pathsLayerRef.current = pathsLayer;

    mapInstanceRef.current = map;

    // Notify parent that map is ready - only once
    if (!readyNotifiedRef.current) {
      readyNotifiedRef.current = true;
      onMapReady(map, cluster, pathsLayer);
    }

    // Cleanup
    return () => {
      if (clusterRef.current) {
        map.removeLayer(clusterRef.current);
      }
      if (pathsLayerRef.current) {
        map.removeLayer(pathsLayerRef.current);
      }
      if (imageOverlayRef.current) {
        map.removeLayer(imageOverlayRef.current);
      }
      map.remove();
      mapInstanceRef.current = null;
      readyNotifiedRef.current = false;
    };
  }, [mapLoaded, onMapReady]);

  return (
    <div 
      ref={mapRef}
      style={{ width: '100%', height: '100%' }}
    />
  );
};
