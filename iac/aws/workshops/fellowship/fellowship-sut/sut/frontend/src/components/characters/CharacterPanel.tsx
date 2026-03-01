/**
 * Character Panel Component - realistic multi-turn NPC chat panel.
 */

import React, { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { useCharacter } from '../../store/characterStore';
import { Avatar } from '../ui/Avatar';
import { Button } from '../ui/Button';
import { apiService } from '../../services/api';
import { NpcCharacter } from '../../types';

const characterInfo: Record<NpcCharacter, { name: string; emoji: string }> = {
  frodo: { name: 'Frodo', emoji: '🧝' },
  sam: { name: 'Sam', emoji: '👨‍🌾' },
  gandalf: { name: 'Gandalf', emoji: '🧙‍♂️' },
};

export const CharacterPanel: React.FC = () => {
  const navigate = useNavigate();
  const {
    activeCharacter,
    chatMessages,
    suggestedAction,
    isChatLoading,
    setActiveCharacter,
    setChatMessages,
    setSuggestedAction,
    setChatLoading,
  } = useCharacter();
  const [draft, setDraft] = useState('');
  const [error, setError] = useState<string | null>(null);

  const currentCharacter = useMemo(() => characterInfo[activeCharacter], [activeCharacter]);

  useEffect(() => {
    let mounted = true;

    const bootstrapConversation = async () => {
      try {
        setError(null);
        setChatLoading(true);
        const session = await apiService.getNpcChatSession(activeCharacter);

        if (!mounted) return;

        if (session.messages.length > 0) {
          setChatMessages(session.messages);
          setSuggestedAction(session.suggested_action);
          return;
        }

        const started = await apiService.startNpcChat(activeCharacter);
        if (!mounted) return;

        setChatMessages(started.messages);
        setSuggestedAction(started.suggested_action);
      } catch (bootstrapError) {
        if (!mounted) return;
        setError('The companion is gathering thoughts. Try again in a moment.');
      } finally {
        if (mounted) {
          setChatLoading(false);
        }
      }
    };

    bootstrapConversation();

    return () => {
      mounted = false;
    };
  }, [activeCharacter, setChatLoading, setChatMessages, setSuggestedAction]);

  const handleSend = async () => {
    const message = draft.trim();
    if (!message) return;

    try {
      setError(null);
      setDraft('');
      setChatLoading(true);

      const response = await apiService.sendNpcMessage(activeCharacter, message);
      setChatMessages(response.messages);
      setSuggestedAction(response.suggested_action);
    } catch (sendError) {
      setError('The character did not answer. Try sending again.');
    } finally {
      setChatLoading(false);
    }
  };

  const handleReset = async () => {
    try {
      setError(null);
      setChatLoading(true);
      await apiService.resetNpcChat(activeCharacter);
      const started = await apiService.startNpcChat(activeCharacter);
      setChatMessages(started.messages);
      setSuggestedAction(started.suggested_action);
    } catch (resetError) {
      setError('Unable to reset this conversation right now.');
    } finally {
      setChatLoading(false);
    }
  };

  const quickCharacters: NpcCharacter[] = ['frodo', 'sam', 'gandalf'];

  const buildActionUrl = () => {
    const route = suggestedAction?.target?.route || '/quests';
    const query = suggestedAction?.target?.query || {};
    const params = new URLSearchParams();

    Object.entries(query).forEach(([key, value]) => {
      params.set(key, String(value));
    });

    const queryString = params.toString();
    return queryString ? `${route}?${queryString}` : route;
  };

  const getActionButtonLabel = () => {
    switch (suggestedAction?.goal_type) {
      case 'scout_map_hotspot':
        return 'Scout on Map';
      case 'propose_side_quest':
        return 'Create Side Quest';
      case 'resolve_dark_magic':
        return 'Contain Dark Magic';
      default:
        return 'Open Action';
    }
  };

  return (
    <motion.aside
      initial={{ opacity: 0, x: 16 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.25 }}
      className="bg-gradient-to-br from-parchment-light to-parchment border border-gold-dark/40 rounded-xl shadow-lg p-4 space-y-4"
    >
      <div className="flex items-center gap-3">
        <Avatar emoji={currentCharacter.emoji} size="lg" />
        <div>
          <h3 className="font-epic text-xl text-forest-dark">{currentCharacter.name}</h3>
          <p className="text-xs text-text-secondary">Companion Chat</p>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {quickCharacters.map((character) => (
          <Button
            key={character}
            variant={character === activeCharacter ? 'epic' : 'small'}
            className="text-xs"
            onClick={() => setActiveCharacter(character)}
          >
            {characterInfo[character].emoji} {characterInfo[character].name}
          </Button>
        ))}
      </div>

      <div className="h-80 overflow-y-auto bg-white/50 rounded-lg border border-gold-dark/20 p-3 space-y-3">
        {chatMessages.length === 0 && !isChatLoading && (
          <p className="text-sm text-text-secondary">Your companion will open the conversation shortly.</p>
        )}

        {chatMessages.map((message, index) => (
          <div
            key={`${message.role}-${index}`}
            className={message.role === 'assistant' ? 'text-left' : 'text-right'}
          >
            <div
              className={
                message.role === 'assistant'
                  ? 'inline-block max-w-[92%] rounded-lg px-3 py-2 bg-parchment-dark/70 text-text-primary text-sm whitespace-pre-wrap break-words'
                  : 'inline-block max-w-[92%] rounded-lg px-3 py-2 bg-forest text-parchment-light text-sm whitespace-pre-wrap break-words'
              }
            >
              {message.content}
            </div>
          </div>
        ))}

        {isChatLoading && (
          <p className="text-xs text-text-secondary italic">{currentCharacter.name} is thinking…</p>
        )}
      </div>

      {suggestedAction && (
        <div className="rounded-lg border border-gold-dark/30 bg-gold/10 p-3">
          <p className="text-xs uppercase tracking-wide text-text-secondary">Suggested action</p>
          <p className="font-readable text-sm text-text-primary mt-1">{suggestedAction.title}</p>
          <p className="text-xs text-text-secondary mt-1">{suggestedAction.reason}</p>
          {suggestedAction.target?.route && (
            <Button
              variant="small"
              className="mt-2"
              onClick={() => navigate(buildActionUrl())}
            >
              {getActionButtonLabel()}
            </Button>
          )}
        </div>
      )}

      <div className="space-y-2">
        <textarea
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault();
              handleSend();
            }
          }}
          rows={3}
          placeholder={`Reply to ${currentCharacter.name}...`}
          className="w-full rounded-lg border border-gold-dark/30 bg-white/70 px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-gold/50 resize-none"
        />
        <div className="flex gap-2">
          <Button variant="epic" className="flex-1" onClick={handleSend} disabled={isChatLoading}>
            Send
          </Button>
          <Button variant="secondary" className="flex-1" onClick={handleReset} disabled={isChatLoading}>
            New Opener
          </Button>
        </div>
      </div>

      {error && <p className="text-xs text-red-700">{error}</p>}
    </motion.aside>
  );
};

CharacterPanel.displayName = 'CharacterPanel';
