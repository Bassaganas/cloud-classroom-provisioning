/**
 * Character Service - Handles NPC character dialogue, lore, and personality
 * Provides context-aware responses for Frodo, Sam, and other LOTR characters
 */

import { User } from '../types';

export interface DialogueResponse {
  character: 'frodo' | 'sam' | 'gandalf';
  message: string;
  emoji?: string;
  mood?: 'hopeful' | 'worried' | 'celebratory' | 'weary' | 'determined';
}

// Character dialogue pools organized by context
const DIALOGUES = {
  welcomes: {
    frodo: [
      'Well met, bearer of knowledge! The roads of our journey await.',
      'Hail, friend! I feel a change in the air. A new quest perhaps?',
      'Welcome back to Middle-earth! The Fellowship needs you.',
    ],
    sam: [
      "Bless you, master! The breakfast's nice and warm, but there's work to be done.",
      "There you are! I've been keeping the fire going.",
      'Welcome, friend! Ready to face whatever comes next?',
    ],
  },

  questSuggestions: {
    journey: [
      'Frodo: Every journey begins with a single step. This quest shall test your resolve.',
      'Sam: Come on then! The sooner we start, the sooner we\'ll see it done.',
      'Gandalf: This quest requires both courage and wisdom. Choose well.',
    ],
    battle: [
      'Frodo: Steel yourself! This battle will not be easy.',
      'Sam: Right then! Let\'s get this done and be home by supper.',
      'Gandalf: The time for action is upon you. Stand firm!',
    ],
    fellowship: [
      'Frodo: Together, we are stronger. This quest binds us as one fellowship.',
      'Sam: We should do this as a team. No one should face this alone.',
      'Gandalf: The strength of the Fellowship is in unity. Remember this.',
    ],
    ring: [
      'Frodo: This task weighs heavy upon my heart... but it must be done.',
      'Sam: I won\'t let you do this alone, master.',
      'Gandalf: The burden of power tests all who bear it. Proceed with caution.',
    ],
  },

  darkMagicWarnings: [
    'Frodo: I sense darkness gathering... the Shadow spreads. Be vigilant!',
    'Sam: Something wicked this way comes! We should be careful-like.',
    'Gandalf: The Enemy stirs. Dark magic corrupts all it touches. Tread carefully!',
  ],

  completionCelebrations: {
    one: [
      'Frodo: Your first quest complete! The mountains of glory await you, friend.',
      'Sam: Well done! One down, and many more to go!',
    ],
    five: [
      'Frodo: Five quests! You grow in strength and wisdom.',
      'Sam: That\'s fine work! You\'re becoming a true hero.',
    ],
    ten: [
      'Frodo: Ten quests on your shoulders! You rival the mightiest of warriors.',
      'Sam: By the roots of Yggdrasil, you\'ve earned your rest!',
    ],
    milestone: [
      'Gandalf: Behold! A champion emerges from the shadows!',
      'Frodo: You have done what many thought impossible. Bravo!',
    ],
  },

  progressRemarks: [
    'The road is long, but you walk it well.',
    'Each quest brings you closer to legend.',
    'The Fellowship believes in you.',
    'Your deeds echo through Middle-earth.',
    'Even the smallest person can change the course of the future.',
  ],

  encouragements: [
    'Sam: I know what we must do. We must go there. But we can\'t do it on foot.',
    'Frodo: This is just a taste of the doom that awaits those who give in to despair.',
    'Gandalf: All we have to decide is what to do with the time that is given to us.',
    'All we have to decide is what to do with the time that is given to us.',
    'There and back again - a quest by any name is still perilous.',
  ],

  loreQuotes: [
    '"In a hole in the ground there lived a hobbit." - The beginning of legends.',
    '"All we have to decide is what to do with the time that is given us." - Gandalf',
    '"Even the smallest person can change the course of the future." - Galadriel',
    '"The board is set, the pieces are moving." - The Wizard',
    '"I wish it need not have happened in my time," said Frodo. "So do I," said Gandalf, "and so do all who live to see such times: but that is not for them to decide. All we have to decide is what to do with the time that is given us."',
  ],
};

export class CharacterService {
  /**
   * Get a welcome message for the user
   */
  static getWelcomeMessage(user: User, isNewLogin: boolean = false): DialogueResponse {
    const character = isNewLogin ? 'frodo' : Math.random() > 0.5 ? 'frodo' : 'sam';
    const dialogues = DIALOGUES.welcomes[character];
    const message = dialogues[Math.floor(Math.random() * dialogues.length)];

    return {
      character,
      message: message.replace(/\b[a-z]/, (char) => char.toUpperCase()),
      emoji: character === 'frodo' ? '🧙‍♂️' : '👨‍🌾',
      mood: 'hopeful',
    };
  }

  /**
   * Get contextual advice for a specific quest type
   */
  static getQuestAdvice(questType: string): DialogueResponse {
    const typeKey = (questType.toLowerCase().replace(/\s+/g, '') || 'journey') as keyof typeof DIALOGUES.questSuggestions;
    const suggestions = DIALOGUES.questSuggestions[typeKey] || DIALOGUES.questSuggestions.journey;
    const message = suggestions[Math.floor(Math.random() * suggestions.length)];

    const [character] = message.split(':') as ['frodo' | 'sam' | 'gandalf', string];
    const cleanMessage = message.split(': ')[1];

    return {
      character: character.toLowerCase() as 'frodo' | 'sam' | 'gandalf',
      message: cleanMessage || message,
      mood: 'determined',
    };
  }

  /**
   * Get warning about dark magic activity
   */
  static getDarkMagicWarning(): DialogueResponse {
    const message = DIALOGUES.darkMagicWarnings[
      Math.floor(Math.random() * DIALOGUES.darkMagicWarnings.length)
    ];
    const [character] = message.split(':') as ['frodo' | 'sam' | 'gandalf', string];
    const cleanMessage = message.split(': ')[1];

    return {
      character: character.toLowerCase() as 'frodo' | 'sam' | 'gandalf',
      message: cleanMessage || message,
      emoji: '👁️',
      mood: 'worried',
    };
  }

  /**
   * Get celebration message based on quest milestone
   */
  static getCelebration(questsCompleted: number): DialogueResponse {
    let tier: 'one' | 'five' | 'ten' | 'milestone' = 'one';

    if (questsCompleted >= 50) tier = 'milestone';
    else if (questsCompleted >= 10) tier = 'ten';
    else if (questsCompleted >= 5) tier = 'five';

    const celebrations = DIALOGUES.completionCelebrations[tier];
    const message = celebrations[Math.floor(Math.random() * celebrations.length)];
    const [character] = message.split(':') as ['frodo' | 'sam' | 'gandalf', string];
    const cleanMessage = message.split(': ')[1];

    return {
      character: character.toLowerCase() as 'frodo' | 'sam' | 'gandalf',
      message: cleanMessage || message,
      emoji: '🎉',
      mood: 'celebratory',
    };
  }

  /**
   * Get random encouragement
   */
  static getEncouragement(): DialogueResponse {
    const message = DIALOGUES.encouragements[
      Math.floor(Math.random() * DIALOGUES.encouragements.length)
    ];

    return {
      character: 'frodo',
      message,
      mood: 'hopeful',
    };
  }

  /**
   * Get random lore quote
   */
  static getLoreQuote(): DialogueResponse {
    const quote = DIALOGUES.loreQuotes[Math.floor(Math.random() * DIALOGUES.loreQuotes.length)];

    return {
      character: 'gandalf',
      message: quote,
      emoji: '📖',
      mood: 'determined',
    };
  }

  /**
   * Get dynamic progress remark based on stats
   */
  static getProgressRemark(
    questsCompleted: number,
    totalQuests: number,
    members: number
  ): DialogueResponse {
    const completionRate = questsCompleted / totalQuests;
    const character = completionRate > 0.5 ? 'gandalf' : Math.random() > 0.5 ? 'frodo' : 'sam';
    const baseMessage = DIALOGUES.progressRemarks[
      Math.floor(Math.random() * DIALOGUES.progressRemarks.length)
    ];

    let message = baseMessage;
    if (completionRate < 0.2)
      message = `The journey is long, but you've taken the first steps: ${questsCompleted}/${totalQuests} quests complete.`;
    else if (completionRate < 0.5)
      message = `Good progress! ${questsCompleted}/${totalQuests} quests done. The end is in sight.`;
    else if (completionRate < 0.9)
      message = `Remarkable work! You're nearly there: ${questsCompleted}/${totalQuests} quests complete.`;
    else message = `Champion! You've conquered ${questsCompleted}/${totalQuests} quests! Only legend awaits.`;

    return {
      character: character as 'frodo' | 'sam' | 'gandalf',
      message,
      mood: completionRate > 0.7 ? 'celebratory' : 'hopeful',
    };
  }

  /**
   * Generate character mood based on current state
   */
  static getMood(darkMagicCount: number, completionRate: number): DialogueResponse['mood'] {
    if (darkMagicCount > 5) return 'worried';
    if (completionRate > 0.8) return 'celebratory';
    if (completionRate < 0.1) return 'weary';
    return 'hopeful';
  }
}
