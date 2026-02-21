import React, { useState, useEffect } from 'react';
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
  const [status, setStatus] = useState<Quest['status']>(quest?.status || 'pending');
  const [locationId, setLocationId] = useState<number | undefined>(quest?.location_id);
  const [assignedTo, setAssignedTo] = useState<number | undefined>(quest?.assigned_to);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await onSubmit({
        title,
        description,
        status,
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
          <h2>{quest ? 'Edit Quest' : 'Create New Quest'}</h2>
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
              rows={4}
            />
          </div>

          <div className="form-group">
            <label htmlFor="status" className="form-label">Status</label>
            <select
              id="status"
              className="form-input"
              value={status}
              onChange={(e) => setStatus(e.target.value as Quest['status'])}
            >
              <option value="pending">Pending</option>
              <option value="in_progress">In Progress</option>
              <option value="completed">Completed</option>
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="location" className="form-label">Location</label>
            <select
              id="location"
              className="form-input"
              value={locationId || ''}
              onChange={(e) => setLocationId(e.target.value ? Number(e.target.value) : undefined)}
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
              {loading ? 'Saving...' : quest ? 'Update Quest' : 'Create Quest'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default QuestForm;
