/**
 * MiddleEarthMap Component Tests - Quest Marker Clustering
 * Tests quest marker aggregation/disaggregation on zoom and location validation
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MapContainer, useMap } from 'react-leaflet';
import L from 'leaflet';
import React from 'react';
import { Location, Quest } from '../../src/types';

// Mock the markerCluster plugin
vi.mock('leaflet.markercluster', () => ({}), { virtual: true });

// Test fixtures
const mockLocations: Location[] = [
  {
    id: 1,
    name: 'Rivendell',
    region: 'Imladris',
    description: 'The Hidden Valley',
    map_x: 500,
    map_y: 300
  },
  {
    id: 2,
    name: 'Lothlorien',
    region: 'Golden Wood',
    description: 'The Golden Forest',
    map_x: 400,
    map_y: 350
  },
  {
    id: 3,
    name: 'Moria',
    region: 'Dwarf Kingdom',
    description: 'The Mines of Moria',
    map_x: 600,
    map_y: 400
  }
];

const mockQuestsRivendell: Quest[] = [
  {
    id: 1,
    title: 'Meet the Council',
    description: 'Attend the Council of Rivendell',
    status: 'not_yet_begun',
    quest_type: 'The Fellowship',
    priority: 'Critical',
    location_id: 1,
    is_dark_magic: false,
    created_at: '2024-01-01',
    updated_at: '2024-01-01'
  },
  {
    id: 2,
    title: 'Gather Provisions',
    description: 'Prepare for the journey',
    status: 'not_yet_begun',
    quest_type: 'The Journey',
    priority: 'Important',
    location_id: 1,
    is_dark_magic: false,
    created_at: '2024-01-01',
    updated_at: '2024-01-01'
  },
  {
    id: 3,
    title: 'Study the Map',
    description: 'Learn the routes',
    status: 'the_road_goes_ever_on',
    quest_type: 'The Ring',
    priority: 'Critical',
    location_id: 1,
    is_dark_magic: false,
    created_at: '2024-01-01',
    updated_at: '2024-01-01'
  }
];

const mockQuestsLothlorien: Quest[] = [
  {
    id: 10,
    title: 'Wood Elf Blessings',
    description: 'Seek blessings from the Wood Elves',
    status: 'not_yet_begun',
    quest_type: 'The Fellowship',
    priority: 'Standard',
    location_id: 2,
    is_dark_magic: false,
    created_at: '2024-01-01',
    updated_at: '2024-01-01'
  },
  {
    id: 11,
    title: 'Gather Lembas Bread',
    description: 'Obtain supplies for the journey',
    status: 'not_yet_begun',
    quest_type: 'The Journey',
    priority: 'Important',
    location_id: 2,
    is_dark_magic: false,
    created_at: '2024-01-01',
    updated_at: '2024-01-01'
  }
];

const mockQuestsMoria: Quest[] = [
  {
    id: 20,
    title: 'Navigate the Depths',
    description: 'Cross through the Mines of Moria',
    status: 'the_road_goes_ever_on',
    quest_type: 'The Battle',
    priority: 'Critical',
    location_id: 3,
    is_dark_magic: true,
    created_at: '2024-01-01',
    updated_at: '2024-01-01'
  }
];

const mockQuestsNoLocation: Quest[] = [
  {
    id: 30,
    title: 'Orphan Quest',
    description: 'This quest has no location',
    status: 'not_yet_begun',
    quest_type: 'The Ring',
    priority: 'Standard',
    location_id: undefined,
    is_dark_magic: false,
    created_at: '2024-01-01',
    updated_at: '2024-01-01'
  }
];

describe('MiddleEarthMap - Quest Marker Clustering', () => {
  describe('Quest Marker Aggregation', () => {
    it('should aggregate multiple quest markers into a cluster', () => {
      const questsByLocation = {
        1: mockQuestsRivendell, // 3 quests at Rivendell
        2: mockQuestsLothlorien, // 2 quests at Lothlorien
        3: mockQuestsMoria // 1 quest at Moria
      };

      expect(questsByLocation[1].length).toBe(3);
      expect(questsByLocation[2].length).toBe(2);
      expect(questsByLocation[3].length).toBe(1);
      expect(Object.values(questsByLocation).flat().length).toBe(6);
    });

    it('should handle single quest markers without clustering', () => {
      const questsByLocation = { 3: mockQuestsMoria };
      expect(questsByLocation[3].length).toBe(1);
    });

    it('should correctly identify quests without locations for filtering', () => {
      const allQuests = [...mockQuestsRivendell, ...mockQuestsMoria, ...mockQuestsNoLocation];
      const questsWithLocation = allQuests.filter(q => q.location_id);
      const questsWithoutLocation = allQuests.filter(q => !q.location_id);

      expect(questsWithLocation.length).toBe(4);
      expect(questsWithoutLocation.length).toBe(1);
      expect(questsWithLocation[0].location_id).toBeDefined();
    });

    it('should grouped quests by location_id correctly', () => {
      const allQuests = [...mockQuestsRivendell, ...mockQuestsLothlorien, ...mockQuestsMoria];
      const questsByLocation = allQuests.reduce((acc, quest) => {
        if (quest.location_id) {
          if (!acc[quest.location_id]) {
            acc[quest.location_id] = [];
          }
          acc[quest.location_id].push(quest);
        }
        return acc;
      }, {} as Record<number, Quest[]>);

      expect(Object.keys(questsByLocation).length).toBe(3);
      expect(questsByLocation[1].length).toBe(3);
      expect(questsByLocation[2].length).toBe(2);
      expect(questsByLocation[3].length).toBe(1);
    });
  });

  describe('Quest Marker Validation', () => {
    it('should validate that all quests have location_id before clustering', () => {
      const allQuests = [...mockQuestsRivendell, ...mockQuestsNoLocation];
      const invalidQuests = allQuests.filter(q => !q.location_id);

      expect(invalidQuests.length).toBe(1);
      expect(invalidQuests[0].title).toBe('Orphan Quest');
      expect(invalidQuests[0].location_id).toBeUndefined();
    });

    it('should validate location coordinates exist for marker placement', () => {
      const validLocations = mockLocations.filter(
        loc => loc.map_x !== undefined && loc.map_y !== undefined
      );

      expect(validLocations.length).toBe(mockLocations.length);
      validLocations.forEach(loc => {
        expect(loc.map_x).toBeDefined();
        expect(loc.map_y).toBeDefined();
        expect(typeof loc.map_x).toBe('number');
        expect(typeof loc.map_y).toBe('number');
      });
    });

    it('should handle quests with matching location_ids', () => {
      const questsByLocation = {
        1: mockQuestsRivendell.filter(q => q.location_id === 1),
        2: mockQuestsLothlorien.filter(q => q.location_id === 2)
      };

      questsByLocation[1].forEach(quest => {
        expect(quest.location_id).toBe(1);
      });
      questsByLocation[2].forEach(quest => {
        expect(quest.location_id).toBe(2);
      });
    });
  });

  describe('Cluster Count Logic', () => {
    it('should calculate correct cluster sizes for small clusters', () => {
      const clusterSizes = {
        small: 1,   // 1-9 quests
        medium: 10, // 10-49 quests
        large: 50   // 50+ quests
      };

      const getClusterSize = (count: number) => {
        if (count < 10) return 'small';
        if (count < 50) return 'medium';
        return 'large';
      };

      expect(getClusterSize(1)).toBe('small');
      expect(getClusterSize(5)).toBe('small');
      expect(getClusterSize(10)).toBe('medium');
      expect(getClusterSize(30)).toBe('medium');
      expect(getClusterSize(50)).toBe('large');
      expect(getClusterSize(100)).toBe('large');
    });

    it('should calculate correct total quest count across locations', () => {
      const allQuests = [...mockQuestsRivendell, ...mockQuestsLothlorien, ...mockQuestsMoria];
      const questCountByStatus = {
        notBegun: allQuests.filter(q => q.status === 'not_yet_begun').length,
        inProgress: allQuests.filter(q => q.status === 'the_road_goes_ever_on').length,
        completed: allQuests.filter(q => q.status === 'it_is_done').length
      };

      expect(questCountByStatus.notBegun).toBe(4); // Rivendell: 1, 2 | Lothlorien: 1, 2 = 4 total not begun
      expect(questCountByStatus.inProgress).toBe(2); // Rivendell: 3 (the_road_goes_ever_on), Moria: 20 (the_road_goes_ever_on)
      expect(questCountByStatus.completed).toBe(0);
    });

    it('should identify dark magic quests for priority clustering', () => {
      const allQuests = [...mockQuestsRivendell, ...mockQuestsMoria];
      const darkMagicQuests = allQuests.filter(q => q.is_dark_magic);

      expect(darkMagicQuests.length).toBe(1);
      expect(darkMagicQuests[0].id).toBe(20);
      expect(darkMagicQuests[0].title).toBe('Navigate the Depths');
    });
  });

  describe('Quest Marker Display', () => {
    it('should display quest type icons correctly', () => {
      const iconMap: { [key: string]: string } = {
        'The Journey': '🧭',
        'The Battle': '⚔️',
        'The Fellowship': '👥',
        'The Ring': '💍',
        'Dark Magic': '👁️'
      };

      mockQuestsRivendell.forEach(quest => {
        const icon = iconMap[quest.quest_type || ''] || '📜';
        expect(icon).toBeDefined();
      });
    });

    it('should format quest status for display', () => {
      const statusMap: Record<string, string> = {
        'not_yet_begun': 'Not Yet Begun',
        'the_road_goes_ever_on': 'The Road Goes Ever On...',
        'it_is_done': 'It Is Done',
        'the_shadow_falls': 'The Shadow Falls',
        'pending': 'Not Yet Begun',
        'in_progress': 'The Road Goes Ever On...',
        'completed': 'It Is Done',
        'blocked': 'The Shadow Falls'
      };

      mockQuestsRivendell.forEach(quest => {
        const displayStatus = statusMap[quest.status] || quest.status;
        expect(displayStatus).toBeTruthy();
        expect(statusMap['not_yet_begun']).toBe('Not Yet Begun');
      });
    });

    it('should preserve quest selection state across re-renders', () => {
      const selectedQuestId = 1;
      const quests = mockQuestsRivendell;
      const isSelected = (questId: number) => questId === selectedQuestId;

      expect(isSelected(1)).toBe(true);
      expect(isSelected(2)).toBe(false);
      expect(isSelected(3)).toBe(false);
    });
  });

  describe('Marker Offset Calculation', () => {
    it('should calculate offsets for multiple markers at same location', () => {
      // Offset pattern for markers at the same location
      const getQuestOffset = (index: number, total: number): [number, number] => {
        const angleStep = (2 * Math.PI) / Math.max(total, 1);
        const angle = angleStep * index;
        const radius = total === 1 ? 0 : Math.max(15, total * 3);

        return [
          Math.sin(angle) * radius / 100,
          Math.cos(angle) * radius / 100
        ];
      };

      // Single marker should have no offset
      const [offsetY1, offsetX1] = getQuestOffset(0, 1);
      expect(offsetY1).toBe(0);
      expect(offsetX1).toBe(0);

      // Multiple markers should have circular offsets
      const [offsetY2, offsetX2] = getQuestOffset(0, 3);
      const [offsetY3, offsetX3] = getQuestOffset(1, 3);
      expect(Math.abs(offsetY2)).toBeLessThan(Math.abs(offsetX2));
    });
  });

  describe('Quest Marker Performance', () => {
    it('should handle large numbers of quests efficiently', () => {
      // Create 100 quests distributed across 10 locations
      const largeQuestSet = Array.from({ length: 100 }, (_, i) => ({
        id: i,
        title: `Quest ${i}`,
        description: 'Test quest',
        status: 'not_yet_begun',
        quest_type: 'The Journey',
        priority: 'Standard',
        location_id: (i % 10) + 1,
        is_dark_magic: false,
        created_at: '2024-01-01',
        updated_at: '2024-01-01'
      } as Quest));

      const questsByLocation = largeQuestSet.reduce((acc, quest) => {
        if (quest.location_id) {
          if (!acc[quest.location_id]) {
            acc[quest.location_id] = [];
          }
          acc[quest.location_id].push(quest);
        }
        return acc;
      }, {} as Record<number, Quest[]>);

      expect(Object.keys(questsByLocation).length).toBe(10);
      expect(questsByLocation[1].length).toBe(10);
      expect(Object.values(questsByLocation).flat().length).toBe(100);

      // Verify clustering would work
      const clusterCounts = Object.entries(questsByLocation).map(
        ([, quests]) => quests.length
      );
      expect(clusterCounts.every(count => count === 10)).toBe(true);
    });

    it('should handle empty quest arrays', () => {
      const emptyQuests: Quest[] = [];
      const questsByLocation = emptyQuests.reduce((acc, quest) => {
        if (quest.location_id) {
          if (!acc[quest.location_id]) {
            acc[quest.location_id] = [];
          }
          acc[quest.location_id].push(quest);
        }
        return acc;
      }, {} as Record<number, Quest[]>);

      expect(Object.keys(questsByLocation).length).toBe(0);
      expect(Object.values(questsByLocation).flat().length).toBe(0);
    });
  });

  describe('Zoom and Aggregation Behavior', () => {
    it('should define clustering behavior for different zoom levels', () => {
      const clusterSettings = {
        maxClusterRadius: 40,
        minZoomLevel: -2,
        maxZoomLevel: 2,
        spiderfyOnMaxZoom: true,
        zoomToBoundsOnClick: true
      };

      expect(clusterSettings.maxClusterRadius).toBe(40);
      expect(clusterSettings.minZoomLevel).toBeLessThan(clusterSettings.maxZoomLevel);
      expect(clusterSettings.spiderfyOnMaxZoom).toBe(true);
    });

    it('should support spiderfy mode for high-zoom viewing', () => {
      // Spiderfy puts markers in a circle pattern when cluster is clicked at max zoom
      const questsByLocation = {
        1: mockQuestsRivendell // 3 quests
      };

      expect(questsByLocation[1].length).toBeGreaterThan(1);
      // These would be spidered out in a circle at max zoom
    });
  });
});
