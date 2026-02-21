import axios, { AxiosInstance } from 'axios';
import { User, Quest, Member, Location, LoginRequest, LoginResponse } from '../types';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost/api';

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
  async getQuests(): Promise<Quest[]> {
    const response = await this.api.get<Quest[]>('/quests/');
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
