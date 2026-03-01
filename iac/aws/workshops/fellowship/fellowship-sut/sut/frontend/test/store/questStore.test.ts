/**
 * Tests for Quest Store (Zustand)
 * TDD: Testing state mutations, selectors, and computed values
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { useQuestStore } from '@/store/questStore';
import { Quest } from '@/types';

// Mock quest data
const mockQuestNone: Quest = {
  id: '1',
  title: 'Test Quest 1',
  description: 'A test quest',
  status: 'not_yet_begun',
  quest_type: 'The Journey',
  priority: 'Standard',
  is_dark_magic: false,
  assigned_to: 'user1',
  assignee_name: 'Frodo',
  location_id: 'loc1',
  location_name: 'Bag End',
  character_quote: 'Test quote',
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  completed_at: null,
};

const mockQuestInProgress: Quest = {
  ...mockQuestNone,
  id: '2',
  status: 'the_road_goes_ever_on',
};

const mockQuestCompleted: Quest = {
  ...mockQuestNone,
  id: '3',
  status: 'it_is_done',
  completed_at: new Date().toISOString(),
};

const mockDarkMagicQuest: Quest = {
  ...mockQuestNone,
  id: '4',
  is_dark_magic: true,
};

describe('useQuestStore', () => {
  beforeEach(() => {
    useQuestStore.setState({
      quests: [],
      members: [],
      locations: [],
      statusFilter: null,
      typeFilter: null,
      priorityFilter: null,
      locationFilter: null,
      searchQuery: '',
    });
  });

  describe('Mutations', () => {
    it('should add a quest', () => {
      useQuestStore.getState().addQuest(mockQuestNone);
      const quests = useQuestStore.getState().quests;

      expect(quests).toHaveLength(1);
      expect(quests[0].id).toBe('1');
    });

    it('should update a quest', () => {
      useQuestStore.getState().addQuest(mockQuestNone);
      useQuestStore.getState().updateQuest('1', { title: 'Updated Title' });

      const quest = useQuestStore.getState().quests[0];
      expect(quest.title).toBe('Updated Title');
    });

    it('should delete a quest', () => {
      useQuestStore.getState().addQuest(mockQuestNone);
      useQuestStore.getState().deleteQuest('1');

      expect(useQuestStore.getState().quests).toHaveLength(0);
    });
  });

  describe('Selectors - getQuestsByStatus', () => {
    beforeEach(() => {
      useQuestStore.getState().setQuests([
        mockQuestNone,
        mockQuestInProgress,
        mockQuestCompleted,
      ]);
    });

    it('should filter quests by status', () => {
      const completed = useQuestStore.getState().getQuestsByStatus('it_is_done');

      expect(completed).toHaveLength(1);
      expect(completed[0].id).toBe('3');
    });

    it('should return empty array for no matches', () => {
      const blocked = useQuestStore.getState().getQuestsByStatus('the_shadow_falls');

      expect(blocked).toHaveLength(0);
    });
  });

  describe('Selectors - getDarkMagicQuests', () => {
    beforeEach(() => {
      useQuestStore.getState().setQuests([
        mockQuestNone,
        mockQuestInProgress,
        mockDarkMagicQuest,
      ]);
    });

    it('should return only dark magic quests', () => {
      const darkMagic = useQuestStore.getState().getDarkMagicQuests();

      expect(darkMagic).toHaveLength(1);
      expect(darkMagic[0].is_dark_magic).toBe(true);
    });
  });

  describe('Selectors - getQuestStats', () => {
    beforeEach(() => {
      useQuestStore.getState().setQuests([
        mockQuestNone,
        mockQuestInProgress,
        mockQuestCompleted,
      ]);
    });

    it('should calculate quest statistics', () => {
      const stats = useQuestStore.getState().getQuestStats();

      expect(stats.total).toBe(3);
      expect(stats.notBegun).toBe(1);
      expect(stats.inProgress).toBe(1);
      expect(stats.completed).toBe(1);
      expect(stats.blocked).toBe(0);
    });
  });

  describe('Selectors - getCompletionRate', () => {
    it('should calculate completion percentage', () => {
      useQuestStore.getState().setQuests([
        mockQuestNone,
        mockQuestCompleted,
      ]);
      const rate = useQuestStore.getState().getCompletionRate();

      expect(rate).toBe(50);
    });

    it('should return 0 for empty quests', () => {
      const rate = useQuestStore.getState().getCompletionRate();

      expect(rate).toBe(0);
    });

    it('should return 100 for all completed', () => {
      useQuestStore.getState().setQuests([
        mockQuestCompleted,
        { ...mockQuestCompleted, id: '5' },
      ]);
      const rate = useQuestStore.getState().getCompletionRate();

      expect(rate).toBe(100);
    });
  });

  describe('Filter actions', () => {
    it('should set status filter', () => {
      useQuestStore.getState().setStatusFilter('it_is_done');

      expect(useQuestStore.getState().statusFilter).toBe('it_is_done');
    });

    it('should set search query', () => {
      useQuestStore.getState().setSearchQuery('test');

      expect(useQuestStore.getState().searchQuery).toBe('test');
    });

    it('should clear all filters', () => {
      useQuestStore.getState().setStatusFilter('it_is_done');
      useQuestStore.getState().setSearchQuery('test');
      useQuestStore.getState().clearFilters();

      expect(useQuestStore.getState().statusFilter).toBeNull();
      expect(useQuestStore.getState().searchQuery).toBe('');
    });
  });

  describe('Filtered quests', () => {
    beforeEach(() => {
      useQuestStore.getState().setQuests([
        mockQuestNone,
        mockQuestInProgress,
        mockQuestCompleted,
      ]);
    });

    it('should filter by status', () => {
      useQuestStore.getState().setStatusFilter('it_is_done');
      const filtered = useQuestStore.getState().getFilteredQuests();

      expect(filtered).toHaveLength(1);
      expect(filtered[0].id).toBe('3');
    });

    it('should filter by search query', () => {
      useQuestStore.getState().setSearchQuery('Test Quest 1');
      const filtered = useQuestStore.getState().getFilteredQuests();

      expect(filtered).toHaveLength(1);
      expect(filtered[0].id).toBe('1');
    });

    it('should apply multiple filters', () => {
      useQuestStore.getState().setStatusFilter('it_is_done');
      useQuestStore.getState().setSearchQuery('1');
      const filtered = useQuestStore.getState().getFilteredQuests();

      // Quest 3 is completed but doesn't match search "1"
      expect(filtered).toHaveLength(0);
    });
  });

  describe('getQuestsByUser', () => {
    beforeEach(() => {
      useQuestStore.getState().setQuests([
        mockQuestNone,
        { ...mockQuestInProgress, assigned_to: 'user2' },
      ]);
    });

    it('should return quests assigned to user', () => {
      const userQuests = useQuestStore.getState().getQuestsByUser('user1');

      expect(userQuests).toHaveLength(1);
      expect(userQuests[0].assigned_to).toBe('user1');
    });

    it('should return empty for user with no quests', () => {
      const userQuests = useQuestStore.getState().getQuestsByUser('unknown');

      expect(userQuests).toHaveLength(0);
    });
  });

  describe('getLocationStats', () => {
    beforeEach(() => {
      useQuestStore.getState().setQuests([
        mockQuestNone,
        { ...mockQuestInProgress, location_id: 'loc1' },
        { ...mockQuestCompleted, location_id: 'loc2' },
      ]);
    });

    it('should count quests by location', () => {
      const stats = useQuestStore.getState().getLocationStats();

      expect(stats['loc1']).toBe(2);
      expect(stats['loc2']).toBe(1);
    });
  });

  describe('getActiveMembers', () => {
    it('should return members with assigned quests', () => {
      useQuestStore.getState().setMembers([
        { id: 'user1', name: 'Frodo', race: 'Hobbit', role: 'Ring-bearer', status: 'active', description: '' },
        { id: 'user2', name: 'Sam', race: 'Hobbit', role: 'Companion', status: 'active', description: '' },
        { id: 'user3', name: 'Gandalf', race: 'Wizard', role: 'Guide', status: 'active', description: '' },
      ]);
      useQuestStore.getState().setQuests([
        mockQuestNone,
        { ...mockQuestInProgress, assigned_to: 'user2' },
      ]);

      const active = useQuestStore.getState().getActiveMembers();

      expect(active).toHaveLength(2);
      expect(active.map((m) => m.id)).toContain('user1');
      expect(active.map((m) => m.id)).toContain('user2');
    });
  });
});
