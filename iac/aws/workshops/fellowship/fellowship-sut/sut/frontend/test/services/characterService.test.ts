/**
 * Tests for CharacterService
 * TDD: Tests written first to define expected behavior
 */

import { describe, it, expect } from 'vitest';
import { CharacterService } from '@/services/characterService';
import { User } from '@/types';

describe('CharacterService', () => {
  it('should return a welcome message with valid character', () => {
    const dialogue = CharacterService.getWelcomeMessage({} as User, true);

    expect(dialogue).toBeDefined();
    expect(['frodo', 'sam']).toContain(dialogue.character);
    expect(dialogue.message).toBeTruthy();
    expect(dialogue.mood).toBe('hopeful');
  });

  it('should vary welcomes between Frodo and Sam', () => {
    const welcomes = new Set<string>();

    for (let i = 0; i < 10; i++) {
      const dialogue = CharacterService.getWelcomeMessage({} as User, false);
      welcomes.add(dialogue.character);
    }

    // Should have randomness between Frodo and Sam
    expect(welcomes.size).toBeGreaterThan(1);
  });

  describe('getQuestAdvice', () => {
    it('should return advice for Journey quests', () => {
      const dialogue = CharacterService.getQuestAdvice('The Journey');

      expect(dialogue).toBeDefined();
      expect(['frodo', 'sam', 'gandalf']).toContain(dialogue.character);
      expect(dialogue.message).toBeTruthy();
      expect(dialogue.mood).toBe('determined');
    });

    it('should return advice for Battle quests', () => {
      const dialogue = CharacterService.getQuestAdvice('The Battle');

      expect(dialogue).toBeDefined();
      expect(['frodo', 'sam', 'gandalf']).toContain(dialogue.character);
      expect(dialogue.message).toBeTruthy();
    });

    it('should default to journey advice for unknown quest type', () => {
      const dialogue = CharacterService.getQuestAdvice('Unknown Type');

      expect(dialogue).toBeDefined();
      expect(dialogue.message).toBeTruthy();
    });
  });

  describe('getDarkMagicWarning', () => {
    it('should return a warning with worried mood', () => {
      const dialogue = CharacterService.getDarkMagicWarning();

      expect(dialogue).toBeDefined();
      expect(['frodo', 'sam', 'gandalf']).toContain(dialogue.character);
      expect(dialogue.message).toContain('darkness');
      expect(dialogue.mood).toBe('worried');
    });

    it('should randomize characters', () => {
      const characters = new Set<string>();

      for (let i = 0; i < 10; i++) {
        const dialogue = CharacterService.getDarkMagicWarning();
        characters.add(dialogue.character);
      }

      expect(characters.size).toBeGreaterThan(1);
    });
  });

  describe('getCelebration', () => {
    it('should celebrate first completion', () => {
      const dialogue = CharacterService.getCelebration(1);

      expect(dialogue).toBeDefined();
      expect(dialogue.mood).toBe('celebratory');
      expect(dialogue.emoji).toBe('🎉');
      expect(dialogue.message).toBeTruthy();
    });

    it('should escalate celebrations at milestones', () => {
      const one = CharacterService.getCelebration(1);
      const five = CharacterService.getCelebration(5);
      const ten = CharacterService.getCelebration(10);

      expect(one.message).toBeDefined();
      expect(five.message).toBeDefined();
      expect(ten.message).toBeDefined();
      // Different messages at different tiers
      expect(ten.message).not.toBe(one.message);
    });

    it('should reach milestone tier at 50+ quests', () => {
      const dialogue = CharacterService.getCelebration(50);

      expect(dialogue).toBeDefined();
      expect(dialogue.message).toContain('legend') || expect(dialogue.message).toContain('Champion');
    });
  });

  describe('getProgressRemark', () => {
    it('should provide remark based on progress', () => {
      const dialogue = CharacterService.getProgressRemark(5, 10, 3);

      expect(dialogue).toBeDefined();
      expect(dialogue.message).toBeTruthy();
      expect(['frodo', 'sam', 'gandalf']).toContain(dialogue.character);
    });

    it('should show progress percentage in remark', () => {
      const dialogue = CharacterService.getProgressRemark(5, 10, 3);

      expect(dialogue.message).toContain('5') || expect(dialogue.message).toContain('50');
    });

    it('should show celebratory mood when completion > 70%', () => {
      const dialogue = CharacterService.getProgressRemark(8, 10, 3);

      expect(dialogue.mood).toBe('celebratory');
    });

    it('should show weary mood when completion < 10%', () => {
      const dialogue = CharacterService.getProgressRemark(1, 20, 3);

      expect(dialogue.mood).toBe('weary');
    });
  });

  describe('getLoreQuote', () => {
    it('should return Gandalf as character for lore quotes', () => {
      const dialogue = CharacterService.getLoreQuote();

      expect(dialogue.character).toBe('gandalf');
      expect(dialogue.emoji).toBe('📖');
      expect(dialogue.message).toBeTruthy();
    });

    it('should contain LOTR quotes', () => {
      const quotes = new Set<string>();

      for (let i = 0; i < 5; i++) {
        const dialogue = CharacterService.getLoreQuote();
        quotes.add(dialogue.message);
      }

      // Should have variety
      expect(quotes.size).toBeGreaterThan(1);
    });
  });

  describe('getEncouragement', () => {
    it('should return encouraging message', () => {
      const dialogue = CharacterService.getEncouragement();

      expect(dialogue).toBeDefined();
      expect(dialogue.mood).toBe('hopeful');
      expect(dialogue.message).toBeTruthy();
    });

    it('should be Frodo character', () => {
      const dialogue = CharacterService.getEncouragement();

      expect(dialogue.character).toBe('frodo');
    });
  });

  describe('getMood', () => {
    it('should return worried mood with high dark magic count', () => {
      const mood = CharacterService.getMood(6, 0.5);

      expect(mood).toBe('worried');
    });

    it('should return celebratory mood with high completion rate', () => {
      const mood = CharacterService.getMood(1, 0.9);

      expect(mood).toBe('celebratory');
    });

    it('should return weary mood with low completion rate', () => {
      const mood = CharacterService.getMood(1, 0.05);

      expect(mood).toBe('weary');
    });

    it('should return hopeful mood in normal conditions', () => {
      const mood = CharacterService.getMood(2, 0.5);

      expect(mood).toBe('hopeful');
    });
  });
});
