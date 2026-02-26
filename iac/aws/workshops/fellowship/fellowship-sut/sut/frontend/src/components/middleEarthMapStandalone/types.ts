/**
 * Type definitions for MiddleEarthMap standalone component
 * Local types file to avoid module resolution issues
 */

export interface Quest {
  id: number;
  title: string;
  description?: string;
  status: 'not_yet_begun' | 'the_road_goes_ever_on' | 'it_is_done' | 'the_shadow_falls';
  quest_type?: string;
  priority?: string;
  is_dark_magic: boolean;
  assigned_to?: number;
  location_id?: number;
  location_name?: string;
  assignee_name?: string;
  character_quote?: string;
  created_at?: string;
  updated_at?: string;
  completed_at?: string;
}

export interface Location {
  id: number;
  name: string;
  description?: string;
  region: string;
  map_x: number;
  map_y: number;
  created_at?: string;
}

export interface MarkerTags {
  places?: string[];
  events?: string[];
  quests?: string[];
  paths?: string[];
  questStatus?: string[];
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
  questId?: number; // Associated quest ID if this marker represents a quest
  quest?: Quest; // Full quest data if available
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
  questStatus: string[];
}

export type FilterCategory = 'places' | 'events' | 'quests' | 'paths' | 'questStatus';

export interface FilterOption {
  id: string;
  label: string;
  category: FilterCategory;
  filter: string;
}
