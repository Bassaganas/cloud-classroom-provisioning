import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Quest } from '../types';
import './QuestList.css';

interface QuestListProps {
  quests: Quest[];
  onEdit?: (quest: Quest) => void;
  onDelete?: (id: number) => void;
  onComplete?: (id: number) => void;
  onLocationClick?: (locationId: number) => void;
}

// Helper function to get status display text
const getStatusText = (status: string): string => {
  const statusMap: { [key: string]: string } = {
    'not_yet_begun': 'Not Yet Begun',
    'the_road_goes_ever_on': 'The Road Goes Ever On...',
    'it_is_done': 'It Is Done',
    'the_shadow_falls': 'The Shadow Falls',
    // Backward compatibility
    'pending': 'Not Yet Begun',
    'in_progress': 'The Road Goes Ever On...',
    'completed': 'It Is Done',
    'blocked': 'The Shadow Falls'
  };
  return statusMap[status] || String(status).replace(/_/g, ' ');
};

// Helper function to get quest type icon
const getQuestTypeIcon = (questType?: string): string => {
  const iconMap: { [key: string]: string } = {
    'The Journey': '🧭',
    'The Battle': '⚔️',
    'The Fellowship': '👥',
    'The Ring': '💍',
    'Dark Magic': '👁️'
  };
  return iconMap[questType || ''] || '📜';
};

// Helper function to get priority ring color
const getPriorityClass = (priority?: string): string => {
  const priorityMap: { [key: string]: string } = {
    'Critical': 'priority-critical',
    'Important': 'priority-important',
    'Standard': 'priority-standard'
  };
  return priorityMap[priority || ''] || '';
};

const QuestList: React.FC<QuestListProps> = ({ quests, onEdit, onDelete, onComplete, onLocationClick }) => {
  const navigate = useNavigate();

  const handleLocationClick = (locationId: number) => {
    if (onLocationClick) {
      onLocationClick(locationId);
    } else {
      navigate(`/map?location=${locationId}`);
    }
  };

  if (quests.length === 0) {
    return (
      <div className="quest-list-empty">
        <p>No quests found. Propose your first quest to begin the journey!</p>
      </div>
    );
  }

  return (
    <div className="quest-list">
      {quests.map((quest) => {
        const isDarkMagic = quest.is_dark_magic;
        const cardClass = `quest-card ${isDarkMagic ? 'quest-card-dark-magic' : ''}`;
        
        return (
          <div key={quest.id} className={cardClass}>
            <div className="quest-card-header">
              <div className="quest-title-row">
                <h3>{quest.title}</h3>
                {quest.priority && (
                  <span className={`priority-ring ${getPriorityClass(quest.priority)}`} title={quest.priority}>
                    {quest.priority === 'Critical' ? '🔴' : quest.priority === 'Important' ? '🟡' : '⚪'}
                  </span>
                )}
              </div>
              <div className="quest-badges">
                {quest.quest_type && (
                  <span className="quest-type-badge" title={quest.quest_type}>
                    {getQuestTypeIcon(quest.quest_type)} {quest.quest_type}
                  </span>
                )}
                {isDarkMagic && (
                  <span className="dark-magic-badge" title="Dark Magic">
                    👁️ Dark Magic
                  </span>
                )}
                <span className={`quest-status quest-status-${quest.status}`}>
                  {getStatusText(quest.status)}
                </span>
              </div>
            </div>
            <p className="quest-description">{quest.description}</p>
            {quest.character_quote && quest.status === 'it_is_done' && (
              <div className="character-quote">
                <em>"{quest.character_quote}"</em>
              </div>
            )}
            <div className="quest-meta">
              {quest.location_name && quest.location_id && (
                <span 
                  className="quest-meta-item quest-location-clickable" 
                  onClick={() => handleLocationClick(quest.location_id!)}
                  title="Click to view on map"
                >
                  📍 {quest.location_name}
                </span>
              )}
              {quest.assignee_name && (
                <span className="quest-meta-item">👤 {quest.assignee_name}</span>
              )}
            </div>
            {(onEdit || onDelete || onComplete) && (
              <div className="quest-actions">
                {onComplete && quest.status !== 'it_is_done' && quest.status !== 'completed' && (
                  <button
                    className="btn btn-primary btn-sm"
                    onClick={() => onComplete(quest.id)}
                  >
                    Mark Complete
                  </button>
                )}
                {onEdit && (
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={() => onEdit(quest)}
                  >
                    Revise Quest
                  </button>
                )}
                {onDelete && (
                  <button
                    className="btn btn-danger btn-sm"
                    onClick={() => onDelete(quest.id)}
                  >
                    Abandon Quest
                  </button>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

export default QuestList;
