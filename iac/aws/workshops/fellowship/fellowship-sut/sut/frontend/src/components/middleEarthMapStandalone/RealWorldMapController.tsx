/**
 * RealWorldMapController Component
 * Handles OSM map overlay for comparison
 */

import React, { useEffect, useRef } from 'react';
import L from 'leaflet';

interface RealWorldMapControllerProps {
  isVisible: boolean;
  mainMap: L.Map | null;
}

const OSM_ZOOM = 5.3;

const getZoomFromDevice = (): number => {
  if (window.innerWidth < 768) {
    return OSM_ZOOM / 1.7;
  } else {
    return OSM_ZOOM;
  }
};

const getMinZoomFromDevice = (): number => {
  if (window.innerWidth < 768) {
    return -4;
  } else {
    return -2;
  }
};

export const RealWorldMapController: React.FC<RealWorldMapControllerProps> = ({
  isVisible,
  mainMap
}) => {
  const osmMapRef = useRef<L.Map | null>(null);
  const realWorldLayerRef = useRef<L.TileLayer | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!isVisible) {
      // Remove OSM map
      if (osmMapRef.current) {
        osmMapRef.current.remove();
        osmMapRef.current = null;
      }
      if (realWorldLayerRef.current) {
        realWorldLayerRef.current.remove();
        realWorldLayerRef.current = null;
      }
      if (containerRef.current && containerRef.current.parentNode) {
        // Clear the container - React will handle ref updates on next render
        containerRef.current.className = '';
        // Remove all child nodes to clean up
        while (containerRef.current.firstChild) {
          containerRef.current.removeChild(containerRef.current.firstChild);
        }
      }
      return;
    }

    if (!mainMap || !containerRef.current || osmMapRef.current) {
      return;
    }

    // Create OSM map
    const osmMap = L.map(containerRef.current, {
      minZoom: getZoomFromDevice(),
      maxZoom: getZoomFromDevice(),
      zoomControl: false,
      attributionControl: false,
    }).setView([46.01358283112393, 7.379250937736971], getZoomFromDevice());

    const realWorldLayer = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      opacity: 0.47,
      attribution: '&copy; <a href="https://openstreetmap.org/copyright">OpenStreetMap contributors</a>'
    }).addTo(osmMap);

    osmMapRef.current = osmMap;
    realWorldLayerRef.current = realWorldLayer;

    // Adjust main map view - wait for next frame to ensure DOM is ready
    requestAnimationFrame(() => {
      if (mainMap && osmMapRef.current) {
        try {
          mainMap.setView([2167, 2500], getMinZoomFromDevice());
        } catch (err) {
          console.warn('Map not fully ready for view update:', err);
        }
      }
    });

    // Cleanup
    return () => {
      if (osmMapRef.current) {
        osmMapRef.current.remove();
        osmMapRef.current = null;
      }
      if (realWorldLayerRef.current) {
        realWorldLayerRef.current.remove();
        realWorldLayerRef.current = null;
      }
    };
  }, [isVisible, mainMap]);

  return <div ref={containerRef} style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', zIndex: 100 }} />;
};
