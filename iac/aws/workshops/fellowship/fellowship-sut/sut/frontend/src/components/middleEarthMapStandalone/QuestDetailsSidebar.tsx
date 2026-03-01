/**
 * QuestDetailsSidebar Component
 * Displays detailed information about a selected quest
 */

import React from 'react';
import { useNavigate } from 'react-router-dom';
import type { Quest } from './types';
import './QuestDetailsSidebar.css';

interface QuestDetailsSidebarProps {
  quest: Quest | null;
  isOpen: boolean;
  onClose: () => void;
}

const getStatusLabel = (status: string): string => {
  const statusMap: Record<string, string> = {
    'not_yet_begun': 'Not Yet Begun',
    'the_road_goes_ever_on': 'The Road Goes Ever On...',
    'it_is_done': 'It Is Done',
    'the_shadow_falls': 'The Shadow Falls',
    'pending': 'Not Yet Begun',
    'in_progress': 'The Road Goes Ever On...',
    'completed': 'It Is Done',
    'blocked': 'The Shadow Falls'
  };
  return statusMap[status] || status;
};

const getStatusClass = (status: string): string => {
  const classMap: Record<string, string> = {
    'pending': 'not_yet_begun',
    'in_progress': 'the_road_goes_ever_on',
    'completed': 'it_is_done',
    'blocked': 'the_shadow_falls'
  };
  return classMap[status] || status;
};

const getQuestTypeIcon = (questType?: string): string => {
  const iconMap: Record<string, string> = {
    'The Journey': '🧭',
    'The Battle': '⚔️',
    'The Fellowship': '👥',
    'The Ring': '💍',
    'Dark Magic': '👁️'
  };
  return iconMap[questType || ''] || '📜';
};

export const QuestDetailsSidebar: React.FC<QuestDetailsSidebarProps> = ({
  quest,
  isOpen,
  onClose
}) => {
  const navigate = useNavigate();
  
  if (!quest) return null;

  const handleLearnMore = () => {
    // Navigate to QuestsPage and pass the quest ID as state
    navigate('/quests', { state: { selectedQuestId: quest.id } });
    onClose();
  };

  return (
    <aside id="quest-details-container" className={isOpen ? 'active' : ''}>
      <span className="material-symbols-outlined" id="quest-close-btn" onClick={onClose}>
        <img alt="close quest details" src="/middle-earth-map/icons/close.svg" />
      </span>
      <section id="quest-details">
        <h2 id="quest-title">{quest.title}</h2>
        
        <div id="quest-status-container">
          {quest.quest_type && (
            <span className="qds-chip qds-type-badge" title={quest.quest_type}>
              <span className="qds-chip-icon" aria-hidden="true">{getQuestTypeIcon(quest.quest_type)}</span>
              <span className="qds-chip-label">{quest.quest_type}</span>
            </span>
          )}
          <span id="quest-status" className={`qds-chip qds-status qds-status-${getStatusClass(quest.status)}`}>
            <span className="qds-chip-label">{getStatusLabel(quest.status)}</span>
          </span>
        </div>

        <div id="quest-metadata">
          {quest.quest_type && (
            <div className="metadata-row">
              <span className="metadata-label">Type:</span>
              <span className="metadata-value">{quest.quest_type}</span>
            </div>
          )}
          
          {quest.priority && (
            <div className="metadata-row">
              <span className="metadata-label">Priority:</span>
              <span className="metadata-value">{quest.priority}</span>
            </div>
          )}
        </div>

        {quest.description && (
          <div id="quest-description">
            <h3>Description</h3>
            <p>{quest.description}</p>
          </div>
        )}

        {quest.character_quote && (
          <div id="quest-quote">
            <h3>Quote</h3>
            <p><em>"{quest.character_quote}"</em></p>
          </div>
        )}

        {quest.assignee_name && (
          <div id="quest-assignee">
            <h3>Assigned to</h3>
            <p>{quest.assignee_name}</p>
          </div>
        )}

        {quest.location_name && (
          <div id="quest-location">
            <h3>Location</h3>
            <p>{quest.location_name}</p>
          </div>
        )}

        <div id="quest-actions">
          <button 
            className="qds-action-btn"
            onClick={handleLearnMore}
          >
            Learn More
          </button>
        </div>
      </section>
    </aside>
  );
};
