/**
 * Zustand Quest Store - Global state management for quests, members, locations
 * Provides selectors, mutations, and derived computations
 */

import { create } from 'zustand';
import { Quest, User, Member, Location } from '../types';
import { apiService } from '../services/api';

interface QuestState {
  // State
  currentUser: User | null;
  quests: Quest[];
  members: Member[];
  locations: Location[];
  isLoading: boolean;
  error: string | null;

  // Filters
  statusFilter: string | null;
  typeFilter: string | null;
  priorityFilter: string | null;
  locationFilter: number | null;
  searchQuery: string;

  // Actions - User
  setCurrentUser: (user: User | null) => void;

  // Actions - Quests
  setQuests: (quests: Quest[]) => void;
  addQuest: (quest: Quest) => void;
  updateQuest: (id: number, quest: Partial<Quest>) => void;
  deleteQuest: (id: number) => void;
  setIsLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;

  // Actions - Data
  setMembers: (members: Member[]) => void;
  setLocations: (locations: Location[]) => void;

  // Actions - Filters
  setStatusFilter: (status: string | null) => void;
  setTypeFilter: (type: string | null) => void;
  setPriorityFilter: (priority: string | null) => void;
  setLocationFilter: (location: number | null) => void;
  setSearchQuery: (query: string) => void;
  clearFilters: () => void;

  // Selectors - Computed
  getFilteredQuests: () => Quest[];
  getQuestsByStatus: (status: string) => Quest[];
  getQuestsByUser: (userId: number) => Quest[];
  getDarkMagicQuests: () => Quest[];
  getQuestStats: () => {
    total: number;
    notBegun: number;
    inProgress: number;
    completed: number;
    blocked: number;
  };
  getCompletionRate: () => number;
  getActiveMembers: () => Member[];
  getLocationStats: () => Record<string, number>;

  // Async API actions
  fetchAllData: () => Promise<void>;
  fetchQuests: () => Promise<void>;
  createQuest: (quest: Omit<Quest, 'id' | 'created_at' | 'updated_at'>) => Promise<Quest>;
  completeQuest: (questId: number) => Promise<void>;
}

export const useQuestStore = create<QuestState>((set, get) => ({
  // Initial state
  currentUser: null,
  quests: [],
  members: [],
  locations: [],
  isLoading: false,
  error: null,
  statusFilter: null,
  typeFilter: null,
  priorityFilter: null,
  locationFilter: null,
  searchQuery: '',

  // Actions - User
  setCurrentUser: (user) => set({ currentUser: user }),

  // Actions - Quests
  setQuests: (quests) => set({ quests }),
  addQuest: (quest) =>
    set((state) => ({
      quests: [...state.quests, quest],
    })),
  updateQuest: (id, updatedData) =>
    set((state) => ({
      quests: state.quests.map((q) => (q.id === id ? { ...q, ...updatedData } : q)),
    })),
  deleteQuest: (id) =>
    set((state) => ({
      quests: state.quests.filter((q) => q.id !== id),
    })),
  setIsLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),

  // Actions - Data
  setMembers: (members) => set({ members }),
  setLocations: (locations) => set({ locations }),

  // Actions - Filters
  setStatusFilter: (status) => set({ statusFilter: status }),
  setTypeFilter: (type) => set({ typeFilter: type }),
  setPriorityFilter: (priority) => set({ priorityFilter: priority }),
  setLocationFilter: (location) => set({ locationFilter: location }),
  setSearchQuery: (query) => set({ searchQuery: query }),
  clearFilters: () =>
    set({
      statusFilter: null,
      typeFilter: null,
      priorityFilter: null,
      locationFilter: null,
      searchQuery: '',
    }),

  // Selectors - Computed
  getFilteredQuests: () => {
    const state = get();
    return state.quests.filter((quest) => {
      if (state.statusFilter && quest.status !== state.statusFilter) return false;
      if (state.typeFilter && quest.quest_type !== state.typeFilter) return false;
      if (state.priorityFilter && quest.priority !== state.priorityFilter) return false;
      if (state.locationFilter && quest.location_id !== state.locationFilter) return false;
      if (
        state.searchQuery &&
        !quest.title.toLowerCase().includes(state.searchQuery.toLowerCase())
      )
        return false;
      return true;
    });
  },

  getQuestsByStatus: (status) => {
    return get().quests.filter((q) => q.status === status);
  },

  getQuestsByUser: (userId) => {
    return get().quests.filter((q) => q.assigned_to === userId);
  },

  getDarkMagicQuests: () => {
    return get().quests.filter((q) => q.is_dark_magic);
  },

  getQuestStats: () => {
    const quests = get().quests;
    return {
      total: quests.length,
      notBegun: quests.filter((q) => q.status === 'not_yet_begun').length,
      inProgress: quests.filter((q) => q.status === 'the_road_goes_ever_on').length,
      completed: quests.filter((q) => q.status === 'it_is_done').length,
      blocked: quests.filter((q) => q.status === 'the_shadow_falls').length,
    };
  },

  getCompletionRate: () => {
    const quests = get().quests;
    if (quests.length === 0) return 0;
    const completed = quests.filter((q) => q.status === 'it_is_done').length;
    return Math.round((completed / quests.length) * 100);
  },

  getActiveMembers: () => {
    const memberIds = new Set(get().quests.map((q) => q.assigned_to).filter(Boolean));
    return get().members.filter((m) => memberIds.has(m.id));
  },

  getLocationStats: () => {
    const stats: Record<string, number> = {};
    get().quests.forEach((quest) => {
      if (quest.location_id) {
        stats[quest.location_id] = (stats[quest.location_id] || 0) + 1;
      }
    });
    return stats;
  },

  // Async API actions
  fetchAllData: async () => {
    set({ isLoading: true, error: null });
    try {
      const [quests, members, locations] = await Promise.all([
        apiService.getQuests(),
        apiService.getMembers(),
        apiService.getLocations(),
      ]);
      set({ quests, members, locations, isLoading: false });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to fetch data';
      set({ error: message, isLoading: false });
    }
  },

  fetchQuests: async () => {
    set({ isLoading: true, error: null });
    try {
      const quests = await apiService.getQuests();
      set({ quests, isLoading: false });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to fetch quests';
      set({ error: message, isLoading: false });
    }
  },

  createQuest: async (questData) => {
    try {
      const newQuest = await apiService.createQuest(questData);
      get().addQuest(newQuest);
      return newQuest;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to create quest';
      set({ error: message });
      throw error;
    }
  },

  completeQuest: async (questId) => {
    try {
      const updatedQuest = await apiService.completeQuest(questId);
      get().updateQuest(questId, updatedQuest);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to complete quest';
      set({ error: message });
      throw error;
    }
  },
}));

/**
 * Custom hooks for convenient store access
 */
export const useQuests = () => useQuestStore((state) => state.quests);
export const useFilteredQuests = () => useQuestStore((state) => state.getFilteredQuests());
export const useQuestStats = () => useQuestStore((state) => state.getQuestStats());
export const useCompletionRate = () => useQuestStore((state) => state.getCompletionRate());
export const useDarkMagicQuests = () => useQuestStore((state) => state.getDarkMagicQuests());
export const useMembers = () => useQuestStore((state) => state.members);
export const useLocations = () => useQuestStore((state) => state.locations);
export const useCurrentUser = () => useQuestStore((state) => state.currentUser);
export const useQuestFilters = () =>
  useQuestStore((state) => ({
    statusFilter: state.statusFilter,
    typeFilter: state.typeFilter,
    priorityFilter: state.priorityFilter,
    locationFilter: state.locationFilter,
    searchQuery: state.searchQuery,
    setStatusFilter: state.setStatusFilter,
    setTypeFilter: state.setTypeFilter,
    setPriorityFilter: state.setPriorityFilter,
    setLocationFilter: state.setLocationFilter,
    setSearchQuery: state.setSearchQuery,
    clearFilters: state.clearFilters,
  }));
