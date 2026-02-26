import React, { useState } from 'react';
import { Quest, Location, Member } from '../types';
import './QuestForm.css';

interface QuestFormProps {
  quest?: Quest;
  locations: Location[];
  members: Member[];
  onSubmit: (quest: Partial<Quest>) => Promise<void>;
  onCancel: () => void;
}

const QuestForm: React.FC<QuestFormProps> = ({
  quest,
  locations,
  members,
  onSubmit,
  onCancel,
}) => {
  const [title, setTitle] = useState(quest?.title || '');
  const [description, setDescription] = useState(quest?.description || '');
  const [status, setStatus] = useState<Quest['status']>(quest?.status || 'not_yet_begun');
  const [questType, setQuestType] = useState<Quest['quest_type']>(quest?.quest_type);
  const [priority, setPriority] = useState<Quest['priority']>(quest?.priority);
  const [isDarkMagic, setIsDarkMagic] = useState(quest?.is_dark_magic || false);
  const [characterQuote, setCharacterQuote] = useState(quest?.character_quote || '');
  const [locationId, setLocationId] = useState<number | undefined>(quest?.location_id);
  const [assignedTo, setAssignedTo] = useState<number | undefined>(quest?.assigned_to);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    
    // Validate location is selected
    if (!locationId) {
      setError('Please select a location for this quest. All quests must be associated with a location on the map.');
      return;
    }
    
    setLoading(true);

    try {
      await onSubmit({
        title,
        description,
        status,
        quest_type: questType,
        priority,
        is_dark_magic: isDarkMagic,
        character_quote: characterQuote || undefined,
        location_id: locationId,
        assigned_to: assignedTo,
      });
    } catch (err: any) {
      setError(err.message || 'Failed to save quest');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="quest-form-overlay" onClick={onCancel}>
      <div className="quest-form-modal" onClick={(e) => e.stopPropagation()}>
        <div className="quest-form-header">
          <h2>{quest ? 'Revise the Quest' : 'Propose a Quest'}</h2>
          <button className="close-button" onClick={onCancel}>×</button>
        </div>

        {error && <div className="error-message">{error}</div>}

        <form onSubmit={handleSubmit} className="quest-form">
          <div className="form-group">
            <label htmlFor="title" className="form-label">Title *</label>
            <input
              type="text"
              id="title"
              className="form-input"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="description" className="form-label">Description</label>
            <textarea
              id="description"
              className="form-input form-textarea"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe the quest in epic detail..."
              rows={4}
            />
          </div>

          <div className="form-group">
            <label htmlFor="quest_type" className="form-label">Quest Type *</label>
            <select
              id="quest_type"
              className="form-input"
              value={questType || ''}
              onChange={(e) => setQuestType(e.target.value as Quest['quest_type'])}
              required
            >
              <option value="">Select quest type</option>
              <option value="The Journey">The Journey</option>
              <option value="The Battle">The Battle</option>
              <option value="The Fellowship">The Fellowship</option>
              <option value="The Ring">The Ring</option>
              <option value="Dark Magic">Dark Magic</option>
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="priority" className="form-label">Priority *</label>
            <select
              id="priority"
              className="form-input"
              value={priority || ''}
              onChange={(e) => setPriority(e.target.value as Quest['priority'])}
              required
            >
              <option value="">Select priority</option>
              <option value="Critical">Critical</option>
              <option value="Important">Important</option>
              <option value="Standard">Standard</option>
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="status" className="form-label">Status</label>
            <select
              id="status"
              className="form-input"
              value={status}
              onChange={(e) => setStatus(e.target.value as Quest['status'])}
            >
              <option value="not_yet_begun">Not Yet Begun</option>
              <option value="the_road_goes_ever_on">The Road Goes Ever On...</option>
              <option value="it_is_done">It Is Done</option>
              <option value="the_shadow_falls">The Shadow Falls</option>
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="is_dark_magic" className="form-label">
              <input
                type="checkbox"
                id="is_dark_magic"
                checked={isDarkMagic}
                onChange={(e) => setIsDarkMagic(e.target.checked)}
              />
              <span style={{ marginLeft: '8px' }}>Dark Magic (for testing challenges)</span>
            </label>
          </div>

          <div className="form-group">
            <label htmlFor="character_quote" className="form-label">Character Quote (optional)</label>
            <input
              type="text"
              id="character_quote"
              className="form-input"
              value={characterQuote}
              onChange={(e) => setCharacterQuote(e.target.value)}
              placeholder="Quote to display when quest is completed..."
            />
          </div>

          <div className="form-group">
            <label htmlFor="location" className="form-label">Location *</label>
            <select
              id="location"
              className="form-input"
              value={locationId || ''}
              onChange={(e) => setLocationId(e.target.value ? Number(e.target.value) : undefined)}
              required
            >
              <option value="">Select a location</option>
              {locations.map((location) => (
                <option key={location.id} value={location.id}>
                  {location.name} - {location.region}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="assigned_to" className="form-label">Assign To</label>
            <select
              id="assigned_to"
              className="form-input"
              value={assignedTo || ''}
              onChange={(e) => setAssignedTo(e.target.value ? Number(e.target.value) : undefined)}
            >
              <option value="">Unassigned</option>
              {members.map((member) => (
                <option key={member.id} value={member.id}>
                  {member.name} ({member.role})
                </option>
              ))}
            </select>
          </div>

          <div className="quest-form-actions">
            <button type="button" className="btn btn-secondary" onClick={onCancel}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? 'Saving...' : quest ? 'Revise Quest' : 'Propose Quest'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default QuestForm;
