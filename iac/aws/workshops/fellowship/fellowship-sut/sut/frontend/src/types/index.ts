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
  status: 'pending' | 'in_progress' | 'completed';
  assigned_to?: number;
  location_id?: number;
  location_name?: string;
  assignee_name?: string;
  created_at?: string;
  updated_at?: string;
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
