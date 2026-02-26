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
    'the_road_goes_ever_on': 'In Progress',
    'it_is_done': 'Completed',
    'the_shadow_falls': 'Failed'
  };
  return statusMap[status] || status;
};

const getStatusColor = (status: string): string => {
  const colorMap: Record<string, string> = {
    'not_yet_begun': '#999',
    'the_road_goes_ever_on': '#e74c3c',
    'it_is_done': '#27ae60',
    'the_shadow_falls': '#2c3e50'
  };
  return colorMap[status] || '#999';
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
          <span 
            id="quest-status" 
            style={{ backgroundColor: getStatusColor(quest.status) }}
          >
            {getStatusLabel(quest.status)}
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

        <div id="quest-actions" style={{ marginTop: '20px', display: 'flex', gap: '10px' }}>
          <button 
            onClick={handleLearnMore}
            style={{
              flex: 1,
              padding: '10px',
              backgroundColor: '#8B4513',
              color: '#fff',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '14px',
              fontWeight: 'bold'
            }}
          >
            Learn More
          </button>
        </div>
      </section>
    </aside>
  );
};
