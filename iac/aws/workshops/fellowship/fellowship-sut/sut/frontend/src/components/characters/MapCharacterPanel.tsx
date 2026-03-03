import React, { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { useCharacter } from '../../store/characterStore';
import { Avatar } from '../ui/Avatar';
import { Button } from '../ui/Button';
import { apiService } from '../../services/api';
import { NpcCharacter, ShopItem } from '../../types';

const characterInfo: Record<NpcCharacter, { name: string; emoji: string }> = {
  frodo: { name: 'Frodo', emoji: '🧝' },
  sam: { name: 'Sam', emoji: '👨‍🌾' },
  gandalf: { name: 'Gandalf', emoji: '🧙‍♂️' },
};

export const MapCharacterPanel: React.FC<{ onClose?: () => void }> = ({ onClose }) => {
  const {
    activeCharacter,
    setActiveCharacter,
    isChatLoading,
    chatMessages,
    setChatMessages,
    setChatLoading,
  } = useCharacter();
  const [draft, setDraft] = useState('');
  const [offerDraft, setOfferDraft] = useState('');
  const [shopItems, setShopItems] = useState<ShopItem[]>([]);
  const [gold, setGold] = useState<number>(0);
  const [negotiationStatus, setNegotiationStatus] = useState<string>('');
  const [error, setError] = useState<string | null>(null);

  const currentCharacter = useMemo(() => characterInfo[activeCharacter], [activeCharacter]);

  useEffect(() => {
    let mounted = true;
    const loadTradeData = async () => {
      try {
        const [items, balance] = await Promise.all([
          apiService.getShopItems(activeCharacter),
          apiService.getGoldBalance(),
        ]);
        if (!mounted) return;
        setShopItems(items);
        setGold(balance);
      } catch {
        if (!mounted) return;
        setShopItems([]);
      }
    };
    loadTradeData();
    return () => { mounted = false; };
  }, [activeCharacter]);

  const sendChat = async (messageInput: string) => {
    const message = messageInput.trim();
    if (!message) return;
    try {
      setError(null);
      setChatLoading(true);
      const response = await apiService.sendNpcMessage(activeCharacter, message);
      setChatMessages(response.messages);
      if (response.balance?.gold !== undefined) {
        setGold(response.balance.gold);
      }
      if (response.negotiation?.status) {
        setNegotiationStatus(response.negotiation.status);
      }
      if (response.shop_items) {
        setShopItems(response.shop_items);
      } else {
        const refreshedItems = await apiService.getShopItems(activeCharacter);
        setShopItems(refreshedItems);
      }
    } catch (sendError) {
      setError('The character did not answer. Try sending again.');
    } finally {
      setChatLoading(false);
    }
  };

  const handleSend = async () => {
    const message = draft.trim();
    if (!message) return;
    setDraft('');
    await sendChat(message);
  };

  const handleStartBargain = async (item: ShopItem) => {
    await sendChat(`I want to bargain for ${item.name} #${item.id}`);
  };

  const handleSendOffer = async () => {
    const cleanOffer = offerDraft.trim();
    if (!cleanOffer) return;
    setOfferDraft('');
    await sendChat(`Offer ${cleanOffer}`);
  };

  const quickCharacters: NpcCharacter[] = ['frodo', 'sam', 'gandalf'];

  return (
    <motion.aside
      initial={{ opacity: 0, x: 16 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.25 }}
      className="bg-gradient-to-br from-parchment-light to-parchment border border-gold-dark/40 rounded-xl shadow-lg p-4 space-y-4 relative"
    >
      {onClose && (
        <button
          className="absolute top-2 right-2 text-xl text-gold-dark hover:text-red-700 focus:outline-none bg-white/70 rounded-full w-8 h-8 flex items-center justify-center shadow"
          onClick={onClose}
          title="Close"
          aria-label="Close"
        >
          ×
        </button>
      )}
      <div className="flex items-center gap-3">
        <Avatar emoji={currentCharacter.emoji} size="lg" />
        <div>
          <h3 className="font-epic text-xl text-forest-dark">{currentCharacter.name}</h3>
          <p className="text-xs text-text-secondary">Trader Bargain</p>
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
          <p className="text-sm text-text-secondary">Start a bargain with your companion.</p>
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
      <div className="rounded-lg border border-gold-dark/30 bg-white/60 p-3 space-y-2">
        <p className="text-xs uppercase tracking-wide text-text-secondary">Trader Ledger</p>
        <p className="text-sm text-text-primary">Gold: {gold}</p>
        {shopItems.length === 0 ? (
          <p className="text-xs text-text-secondary">No available items for this character.</p>
        ) : (
          <div className="space-y-2 max-h-36 overflow-y-auto">
            {shopItems.map((item) => (
              <div key={item.id} className="rounded border border-gold-dark/20 bg-parchment-light/50 p-2">
                <p className="text-sm font-semibold text-forest-dark">{item.name}</p>
                <p className="text-xs text-text-secondary">Ask: {item.asking_price} Gold</p>
                <Button
                  variant="small"
                  className="mt-2"
                  onClick={() => handleStartBargain(item)}
                  disabled={isChatLoading}
                >
                  Bargain
                </Button>
              </div>
            ))}
          </div>
        )}
        <div className="flex gap-2 items-center">
          <input
            value={offerDraft}
            onChange={(event) => setOfferDraft(event.target.value)}
            placeholder="Offer amount"
            className="w-full rounded border border-gold-dark/30 bg-white/80 px-2 py-1 text-sm"
          />
          <Button variant="secondary" onClick={handleSendOffer} disabled={isChatLoading}>
            Send Offer
          </Button>
        </div>
        {negotiationStatus && (
          <p className="text-xs text-text-secondary">Negotiation: {negotiationStatus}</p>
        )}
      </div>
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
        </div>
      </div>
      {error && <p className="text-xs text-red-700">{error}</p>}
    </motion.aside>
  );
};

MapCharacterPanel.displayName = 'MapCharacterPanel';
