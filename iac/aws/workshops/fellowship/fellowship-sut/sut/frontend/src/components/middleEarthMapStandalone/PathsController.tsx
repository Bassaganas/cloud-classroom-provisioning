/**
 * PathsController Component
 * Loads and renders paths based on filter state
 */

import React, { useEffect, useRef } from 'react';
import L from 'leaflet';
import type { PathData, FilterState } from './types';

interface PathsControllerProps {
  pathsLayer: L.LayerGroup | null;
  paths: PathData[];
  filters: FilterState;
}

const pathTooltip = (path: PathData): string => {
  return `
    <div class="path-name">${path.name}</div>
    <div class="path-date">[ ${path.startDate} - <br/> ${path.endDate} ]</div>
    <div class="path-distance">${path.distance}</div>
  `;
};

export const PathsController: React.FC<PathsControllerProps> = ({
  pathsLayer,
  paths,
  filters
}) => {
  const pathsRef = useRef<L.Polyline[]>([]);

  useEffect(() => {
    if (!pathsLayer) {
      return;
    }

    // Clear existing paths
    pathsLayer.clearLayers();
    pathsRef.current = [];

    // Filter and render paths
    for (const path of paths) {
      if (filters.paths.includes(path.id)) {
        // Convert path coordinates to Leaflet Simple CRS
        // In Simple CRS: [y, x] where y increases downward
        const latLongs = path.path.map((l: [number, number]) => [4334 - l[1], l[0]] as [number, number]);
        
        // Create visible line
        const line = L.polyline(latLongs, {
          color: path.color,
          weight: 4
        });
        
        line.bindTooltip(pathTooltip(path), {
          sticky: true,
          className: 'path-tooltip'
        }).addTo(pathsLayer);

        // Create invisible wider line for easier interaction
        const interactionLine = L.polyline(latLongs, {
          color: 'transparent',
          weight: 40
        });
        
        interactionLine.bindTooltip(pathTooltip(path), {
          sticky: true,
          className: 'path-tooltip'
        }).addTo(pathsLayer);

        pathsRef.current.push(line, interactionLine);
      }
    }

    // Cleanup
    return () => {
      pathsLayer.clearLayers();
      pathsRef.current = [];
    };
  }, [pathsLayer, paths, filters]);

  return null;
};
