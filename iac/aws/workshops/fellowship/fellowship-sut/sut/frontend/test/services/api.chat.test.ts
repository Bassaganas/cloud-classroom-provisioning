import { describe, it, expect, vi, beforeEach } from 'vitest';
import axios from 'axios';

const mockedAxiosInstance = {
  post: vi.fn(),
  get: vi.fn(),
  put: vi.fn(),
  delete: vi.fn(),
};

vi.mock('axios', () => ({
  default: {
    create: vi.fn(() => mockedAxiosInstance),
  },
}));

describe('apiService NPC chat methods', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('calls /chat/start with character payload', async () => {
    mockedAxiosInstance.post.mockResolvedValueOnce({
      data: {
        conversation_id: '1:gandalf',
        character: 'gandalf',
        opener: 'What is the one decision that matters most today?',
        suggested_action: {
          goal_type: 'advance_next_quest',
          title: 'Advance next quest',
          reason: 'Progress',
          target: { route: '/quests', query: { focusQuestId: 3 } },
        },
        messages: [],
      },
    });

    const { apiService } = await import('../../src/services/api');
    const result = await apiService.startNpcChat('gandalf');

    expect(mockedAxiosInstance.post).toHaveBeenCalledWith('/chat/start', { character: 'gandalf' });
    expect(result.character).toBe('gandalf');
  });

  it('calls /chat/message with user content', async () => {
    mockedAxiosInstance.post.mockResolvedValueOnce({
      data: {
        conversation_id: '1:sam',
        character: 'sam',
        message: 'Let us finish one quest first.',
        suggested_action: {
          goal_type: 'finish_critical_in_progress',
          title: 'Finish critical',
          reason: 'Momentum',
          target: { route: '/quests', query: { status: 'the_road_goes_ever_on', focusQuestId: 4 } },
        },
        messages: [
          { role: 'assistant', content: 'What first?' },
          { role: 'user', content: 'Help me choose.' },
          { role: 'assistant', content: 'Let us finish one quest first.' },
        ],
      },
    });

    const { apiService } = await import('../../src/services/api');
    const result = await apiService.sendNpcMessage('sam', 'Help me choose.');

    expect(mockedAxiosInstance.post).toHaveBeenCalledWith('/chat/message', {
      character: 'sam',
      message: 'Help me choose.',
    });
    expect(result.messages.length).toBeGreaterThan(0);
  });
});
