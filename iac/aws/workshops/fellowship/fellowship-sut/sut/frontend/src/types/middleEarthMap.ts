/**
 * Type definitions for MiddleEarthMap standalone component
 */

export interface MarkerTags {
  places?: string[];
  events?: string[];
  quests?: string[];
  paths?: string[];
}

export interface MarkerData {
  title: string;
  description?: string;
  sindarinTitle?: string;
  date?: string;
  infoLink?: string;
  tags: MarkerTags;
  x: number; // Pixel X coordinate
  y: number; // Pixel Y coordinate
}

export interface PathData {
  name: string;
  id: string;
  color: string;
  distance: string;
  startDate: string;
  endDate: string;
  path: [number, number][]; // Array of [x, y] coordinates
}

export interface FilterState {
  places: string[];
  events: string[];
  quests: string[];
  paths: string[];
  'map-layers': string[];
}

export type FilterCategory = 'places' | 'events' | 'quests' | 'paths';

export interface FilterOption {
  id: string;
  label: string;
  category: FilterCategory;
  filter: string;
}
