import { describe, it, expect, beforeEach } from 'vitest';
import { useCharacterStore } from '@/store/characterStore';

describe('characterStore chat state', () => {
  beforeEach(() => {
    useCharacterStore.setState({
      activeCharacter: 'gandalf',
      currentDialogue: null,
      dialogueHistory: [],
      characterMood: 'hopeful',
      isDarkMagicActive: false,
      questCompletionCount: 0,
      chatMessages: [],
      suggestedAction: null,
      isChatLoading: false,
    });
  });

  it('stores chat transcript messages', () => {
    useCharacterStore.getState().setChatMessages([
      { role: 'assistant', content: 'Name your next step.' },
    ]);

    useCharacterStore.getState().appendChatMessage({
      role: 'user',
      content: 'I will complete a quest.',
    });

    const state = useCharacterStore.getState();
    expect(state.chatMessages).toHaveLength(2);
    expect(state.chatMessages[1].role).toBe('user');
  });

  it('stores suggested action payload', () => {
    useCharacterStore.getState().setSuggestedAction({
      goal_type: 'finish_critical_in_progress',
      title: 'Finish a critical in-progress quest',
      reason: 'Momentum comes from completion.',
      target: { route: '/quests', quest_id: 3 },
    });

    const state = useCharacterStore.getState();
    expect(state.suggestedAction?.target?.route).toBe('/quests');
  });

  it('toggles loading state for pending chat requests', () => {
    useCharacterStore.getState().setChatLoading(true);
    expect(useCharacterStore.getState().isChatLoading).toBe(true);

    useCharacterStore.getState().setChatLoading(false);
    expect(useCharacterStore.getState().isChatLoading).toBe(false);
  });
});
