export interface User {
  id: number;
  username: string;
  email: string;
  role: string;
  created_at?: string;
}

export interface Quest {
  id: number;
  title: string;
  description: string;
  status: 'not_yet_begun' | 'the_road_goes_ever_on' | 'it_is_done' | 'the_shadow_falls' | 'pending' | 'in_progress' | 'completed' | 'blocked'; // Include old values for backward compatibility
  quest_type?: 'The Journey' | 'The Battle' | 'The Fellowship' | 'The Ring' | 'Dark Magic';
  priority?: 'Critical' | 'Important' | 'Standard';
  is_dark_magic?: boolean;
  assigned_to?: number;
  location_id?: number;
  location_name?: string;
  assignee_name?: string;
  character_quote?: string;
  created_at?: string;
  updated_at?: string;
  completed_at?: string;
}

export interface Member {
  id: number;
  name: string;
  race: string;
  role: string;
  status: string;
  description?: string;
  created_at?: string;
}

export interface Location {
  id: number;
  name: string;
  description?: string;
  region: string;
  map_x?: number;  // X coordinate (0-100)
  map_y?: number;  // Y coordinate (0-100)
  created_at?: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  message: string;
  user: User;
}

// Re-export MiddleEarthMap types
export * from './middleEarthMap';
