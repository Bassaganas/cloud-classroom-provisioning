import React from 'react';
import { Quest } from '../types';
import './QuestList.css';

interface QuestListProps {
  quests: Quest[];
  onEdit?: (quest: Quest) => void;
  onDelete?: (id: number) => void;
}

const QuestList: React.FC<QuestListProps> = ({ quests, onEdit, onDelete }) => {
  if (quests.length === 0) {
    return (
      <div className="quest-list-empty">
        <p>No quests found. Create your first quest to begin the journey!</p>
      </div>
    );
  }

  return (
    <div className="quest-list">
      {quests.map((quest) => (
        <div key={quest.id} className="quest-card">
          <div className="quest-card-header">
            <h3>{quest.title}</h3>
            <span className={`quest-status quest-status-${quest.status}`}>
              {quest.status.replace('_', ' ')}
            </span>
          </div>
          <p className="quest-description">{quest.description}</p>
          <div className="quest-meta">
            {quest.location_name && (
              <span className="quest-meta-item">📍 {quest.location_name}</span>
            )}
            {quest.assignee_name && (
              <span className="quest-meta-item">👤 {quest.assignee_name}</span>
            )}
          </div>
          {(onEdit || onDelete) && (
            <div className="quest-actions">
              {onEdit && (
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => onEdit(quest)}
                >
                  Edit
                </button>
              )}
              {onDelete && (
                <button
                  className="btn btn-danger btn-sm"
                  onClick={() => onDelete(quest.id)}
                >
                  Delete
                </button>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
};

export default QuestList;
