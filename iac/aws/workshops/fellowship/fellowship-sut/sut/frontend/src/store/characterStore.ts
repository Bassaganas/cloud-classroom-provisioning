/**
 * Zustand Character Store - Manages NPC character state
 * Tracks character mood, dialogue history, and personality traits
 */

import { create } from 'zustand';
import { DialogueResponse } from '../services/characterService';
import { NpcCharacter, NpcChatMessage, NpcSuggestedAction } from '../types';

interface CharacterState {
  // State
  activeCharacter: NpcCharacter;
  currentDialogue: DialogueResponse | null;
  dialogueHistory: DialogueResponse[];
  characterMood: 'hopeful' | 'worried' | 'celebratory' | 'weary' | 'determined';
  isDarkMagicActive: boolean;
  questCompletionCount: number;
  chatMessages: NpcChatMessage[];
  suggestedAction: NpcSuggestedAction | null;
  isChatLoading: boolean;

  // Actions
  setActiveCharacter: (character: NpcCharacter) => void;
  setCurrentDialogue: (dialogue: DialogueResponse | null) => void;
  addDialogueToHistory: (dialogue: DialogueResponse) => void;
  clearDialogueHistory: () => void;
  setCharacterMood: (mood: CharacterState['characterMood']) => void;
  setDarkMagicActive: (active: boolean) => void;
  setQuestCompletionCount: (count: number) => void;
  setChatMessages: (messages: NpcChatMessage[]) => void;
  appendChatMessage: (message: NpcChatMessage) => void;
  setSuggestedAction: (action: NpcSuggestedAction | null) => void;
  setChatLoading: (loading: boolean) => void;

  // Computed
  getCharacterAvatar: () => string;
  getCharacterColor: () => string;
  getShouldShowPanel: () => boolean;
}

export const useCharacterStore = create<CharacterState>((set, get) => ({
  // Initial state
  activeCharacter: 'frodo',
  currentDialogue: null,
  dialogueHistory: [],
  characterMood: 'hopeful',
  isDarkMagicActive: false,
  questCompletionCount: 0,
  chatMessages: [],
  suggestedAction: null,
  isChatLoading: false,

  // Actions
  setActiveCharacter: (character) => set({ activeCharacter: character }),

  setCurrentDialogue: (dialogue) => {
    if (dialogue) {
      get().addDialogueToHistory(dialogue);
    }
    set({ currentDialogue: dialogue });
  },

  addDialogueToHistory: (dialogue) =>
    set((state) => ({
      dialogueHistory: [
        ...state.dialogueHistory.slice(-9), // Keep last 10 dialogues
        dialogue,
      ],
    })),

  clearDialogueHistory: () => set({ dialogueHistory: [], currentDialogue: null }),

  setCharacterMood: (mood) => set({ characterMood: mood }),

  setDarkMagicActive: (active) => set({ isDarkMagicActive: active }),

  setQuestCompletionCount: (count) => set({ questCompletionCount: count }),

  setChatMessages: (messages) => set({ chatMessages: messages }),

  appendChatMessage: (message) =>
    set((state) => ({
      chatMessages: [...state.chatMessages, message],
    })),

  setSuggestedAction: (action) => set({ suggestedAction: action }),

  setChatLoading: (loading) => set({ isChatLoading: loading }),

  // Computed selectors
  getCharacterAvatar: () => {
    const character = get().activeCharacter;
    const avatars = {
      frodo: '🧝',
      sam: '👨‍🌾',
      gandalf: '🧙‍♂️',
    };
    return avatars[character];
  },

  getCharacterColor: () => {
    const character = get().activeCharacter;
    const colors = {
      frodo: '#3B82F6',    // Blue
      sam: '#10B981',      // Green
      gandalf: '#8B5CF6',  // Purple
    };
    return colors[character];
  },

  getShouldShowPanel: () => {
    return get().currentDialogue !== null;
  },
}));

/**
 * Custom hooks for convenient store access
 */
export const useCharacter = () =>
  useCharacterStore((state) => ({
    activeCharacter: state.activeCharacter,
    currentDialogue: state.currentDialogue,
    mood: state.characterMood,
    chatMessages: state.chatMessages,
    suggestedAction: state.suggestedAction,
    isChatLoading: state.isChatLoading,
    avatar: state.getCharacterAvatar(),
    color: state.getCharacterColor(),
    setActiveCharacter: state.setActiveCharacter,
    setCurrentDialogue: state.setCurrentDialogue,
    setChatMessages: state.setChatMessages,
    appendChatMessage: state.appendChatMessage,
    setSuggestedAction: state.setSuggestedAction,
    setChatLoading: state.setChatLoading,
  }));

export const useCharacterMood = () => useCharacterStore((state) => state.characterMood);
export const useCurrentDialogue = () => useCharacterStore((state) => state.currentDialogue);
export const useDarkMagicState = () => useCharacterStore((state) => state.isDarkMagicActive);
