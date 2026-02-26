import axios, { AxiosInstance } from 'axios';
import { User, Quest, Member, Location, LoginRequest, LoginResponse } from '../types';

// Determine API URL based on environment and current location
// When accessing via Caddy (port 80), use relative path /api
// When accessing directly via port 3000, use full URL through Caddy (port 80) or backend (port 5000)
// Type declaration for webpack's process.env
interface ProcessEnv {
  REACT_APP_API_URL?: string;
}

declare const process: {
  env: ProcessEnv;
};

const getApiUrl = (): string => {
  // React apps use webpack's DefinePlugin which replaces process.env at build time
  const envUrl = process.env.REACT_APP_API_URL;
  
  // If environment variable is a full URL, use it
  if (envUrl && envUrl.startsWith('http')) {
    return envUrl;
  }
  
  // In browser, detect if we're accessing via port 3000 directly
  if (typeof window !== 'undefined') {
    const port = window.location.port;
    
    // If accessing via port 3000, use Caddy on port 80 (or backend on 5000)
    if (port === '3000') {
      // Use Caddy proxy on port 80 (recommended) or backend directly on 5000
      return `${window.location.protocol}//${window.location.hostname}/api`;
    }
  }
  
  // Default: use relative path (works when accessing through Caddy on port 80)
  return envUrl || '/api';
};

const API_URL = getApiUrl();

class ApiService {
  private api: AxiosInstance;

  constructor() {
    this.api = axios.create({
      baseURL: API_URL,
      withCredentials: true,
      headers: {
        'Content-Type': 'application/json',
      },
    });
  }

  // Authentication
  async login(credentials: LoginRequest): Promise<LoginResponse> {
    const response = await this.api.post<LoginResponse>('/auth/login', credentials);
    return response.data;
  }

  async logout(): Promise<void> {
    await this.api.post('/auth/logout');
  }

  async getCurrentUser(): Promise<User> {
    const response = await this.api.get<User>('/auth/me');
    return response.data;
  }

  // Quests
  async getQuests(filters?: {
    status?: string;
    quest_type?: string;
    priority?: string;
    dark_magic?: boolean;
    location_id?: number;
    assigned_to?: number;
  }): Promise<Quest[]> {
    const params = new URLSearchParams();
    if (filters) {
      if (filters.status) params.append('status', filters.status);
      if (filters.quest_type) params.append('quest_type', filters.quest_type);
      if (filters.priority) params.append('priority', filters.priority);
      if (filters.dark_magic !== undefined) params.append('dark_magic', filters.dark_magic.toString());
      if (filters.location_id) params.append('location_id', filters.location_id.toString());
      if (filters.assigned_to) params.append('assigned_to', filters.assigned_to.toString());
    }
    const queryString = params.toString();
    const url = queryString ? `/quests/?${queryString}` : '/quests/';
    const response = await this.api.get<Quest[]>(url);
    return response.data;
  }

  async getQuest(id: number): Promise<Quest> {
    const response = await this.api.get<Quest>(`/quests/${id}`);
    return response.data;
  }

  async createQuest(quest: Partial<Quest>): Promise<Quest> {
    const response = await this.api.post<Quest>('/quests/', quest);
    return response.data;
  }

  async updateQuest(id: number, quest: Partial<Quest>): Promise<Quest> {
    const response = await this.api.put<Quest>(`/quests/${id}`, quest);
    return response.data;
  }

  async deleteQuest(id: number): Promise<void> {
    await this.api.delete(`/quests/${id}`);
  }

  async completeQuest(id: number): Promise<Quest & { message?: string }> {
    const response = await this.api.put<Quest & { message?: string }>(`/quests/${id}/complete`);
    return response.data;
  }

  // Members
  async getMembers(): Promise<Member[]> {
    const response = await this.api.get<Member[]>('/members/');
    return response.data;
  }

  async getMember(id: number): Promise<Member> {
    const response = await this.api.get<Member>(`/members/${id}`);
    return response.data;
  }

  // Locations
  async getLocations(): Promise<Location[]> {
    const response = await this.api.get<Location[]>('/locations/');
    return response.data;
  }

  async getLocation(id: number): Promise<Location> {
    const response = await this.api.get<Location>(`/locations/${id}`);
    return response.data;
  }
}

export const apiService = new ApiService();
