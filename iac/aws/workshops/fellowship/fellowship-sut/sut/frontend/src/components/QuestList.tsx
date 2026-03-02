import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Quest } from '../types';
import { Card } from './ui/Card';
import { Button } from './ui/Button';
import { Badge } from './ui/Badge';
import { motion } from 'framer-motion';

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

// Helper function to get priority badge variant
const getPriorityVariant = (priority?: string): 'critical' | 'important' | 'standard' => {
  const priorityMap: { [key: string]: 'critical' | 'important' | 'standard' } = {
    'Critical': 'critical',
    'Important': 'important',
    'Standard': 'standard'
  };
  return priorityMap[priority || ''] || 'standard';
};

// Helper function to get status badge variant
const getStatusVariant = (status: string): 'ready' | 'inprogress' | 'blocked' | 'pending' => {
  const statusMap: { [key: string]: 'ready' | 'inprogress' | 'blocked' | 'pending' } = {
    'it_is_done': 'ready',
    'the_road_goes_ever_on': 'inprogress',
    'the_shadow_falls': 'blocked',
    'not_yet_begun': 'pending',
    'completed': 'ready',
    'in_progress': 'inprogress',
    'blocked': 'blocked',
    'pending': 'pending'
  };
  return statusMap[status] || 'pending';
};

const QuestList: React.FC<QuestListProps> = ({ quests, onEdit, onDelete, onComplete, onLocationClick }) => {
  const navigate = useNavigate();

  const handleLocationClick = (locationId: number) => {
    if (onLocationClick) {
      onLocationClick(locationId);
    } else {
      navigate(`/map`, { state: { zoomToLocation: locationId } });
    }
  };

  if (quests.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-lg sm:text-2xl text-text-secondary font-readable px-4">
          No quests found. Propose your first quest to begin the journey! 📜
        </p>
      </div>
    );
  }

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1,
      },
    },
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { duration: 0.5, ease: 'easeOut' },
    },
  };

  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="visible"
      className="grid grid-cols-1 lg:grid-cols-2 gap-4 auto-rows-fr"
    >
      {quests.map((quest) => (
        <motion.div key={quest.id} variants={itemVariants} className="h-full">
          <Card
            variant={quest.is_dark_magic ? 'dark' : 'parchment'}
            className="hover:shadow-lg transition-shadow h-full flex flex-col"
          >
            <div className="space-y-3 sm:space-y-4 min-w-0 flex-1 flex flex-col">
              {/* Header with Title and Priority */}
              <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 sm:gap-4 min-w-0">
                <div className="flex-1 min-w-0">
                  <h3 className="font-epic text-lg sm:text-xl text-forest-dark mb-2 break-words">
                    {getQuestTypeIcon(quest.quest_type)} {quest.title}
                  </h3>
                  <p className="font-readable text-text-secondary text-sm break-words line-clamp-3">{quest.description}</p>
                </div>
                {quest.priority && (
                  <div className="flex-shrink-0 self-start">
                    <Badge variant={getPriorityVariant(quest.priority)}>
                      {quest.priority === 'Critical' ? '🔴' : quest.priority === 'Important' ? '🟡' : '⚪'} {quest.priority}
                    </Badge>
                  </div>
                )}
              </div>

              {/* Status and Type Badges */}
              <div className="flex gap-2 flex-wrap items-center">
                {quest.quest_type && (
                  <Badge variant="standard" className="text-xs">
                    {quest.quest_type}
                  </Badge>
                )}
                <Badge variant={getStatusVariant(quest.status)}>
                  {getStatusText(quest.status)}
                </Badge>
                {quest.is_dark_magic && (
                  <Badge variant="critical" className="text-xs">
                    👁️ Dark Magic
                  </Badge>
                )}
              </div>

              {/* Character Quote (if completed) */}
              {quest.character_quote && (quest.status === 'it_is_done' || quest.status === 'completed') && (
                <div className="p-3 bg-forest/10 rounded border-l-4 border-gold">
                  <em className="text-sm text-text-secondary block break-words line-clamp-3">
                    "{quest.character_quote}"
                  </em>
                </div>
              )}

              {/* Meta Information */}
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 text-xs sm:text-sm text-text-secondary flex-1">
                {quest.location_name && quest.location_id && (
                  <button
                    className="text-left hover:text-gold transition-colors cursor-pointer break-words"
                    onClick={() => handleLocationClick(quest.location_id!)}
                    title="Click to view on map"
                  >
                    📍 {quest.location_name}
                  </button>
                )}
                {quest.assignee_name && (
                  <div className="break-words">👤 {quest.assignee_name}</div>
                )}
              </div>

              {/* Action Buttons */}
              {(onEdit || onDelete || onComplete) && (
                <div className="flex flex-col sm:flex-row gap-2 pt-4 border-t border-text-secondary/20 mt-auto">
                  {onComplete && quest.status !== 'it_is_done' && quest.status !== 'completed' && (
                    <Button
                      variant="epic"
                      className="text-sm w-full sm:flex-1"
                      onClick={() => onComplete(quest.id)}
                    >
                      ✓ Complete Quest
                    </Button>
                  )}
                  {onEdit && (
                    <Button
                      variant="secondary"
                      className="text-sm w-full sm:flex-1"
                      onClick={() => onEdit(quest)}
                    >
                      ✏️ Revise
                    </Button>
                  )}
                  {onDelete && (
                    <Button
                      variant="danger"
                      className="text-sm w-full sm:flex-1"
                      onClick={() => onDelete(quest.id)}
                    >
                      ✕ Abandon
                    </Button>
                  )}
                </div>
              )}
            </div>
          </Card>
        </motion.div>
      ))}
    </motion.div>
  );
};

export default QuestList;
