import { describe, it, expect } from 'vitest';
import { getMissionObjective } from '@/utils/missionObjective';
import { Quest } from '@/types';

const baseQuest: Quest = {
  id: 101,
  title: 'Scout Osgiliath',
  description: 'Assess defenses and report threats.',
  status: 'not_yet_begun',
  quest_type: 'The Journey',
  priority: 'Important',
  is_dark_magic: false,
  location_id: 10,
  location_name: 'Osgiliath',
};

describe('getMissionObjective', () => {
  it('returns quest setup objective when no quests exist', () => {
    const objective = getMissionObjective([]);

    expect(objective.title).toContain('Forge the Fellowship Plan');
    expect(objective.route).toBe('/quests');
    expect(objective.mode).toBe('quests');
  });

  it('prioritizes dark magic containment', () => {
    const objective = getMissionObjective([
      { ...baseQuest, id: 201, status: 'the_shadow_falls', is_dark_magic: true },
      { ...baseQuest, id: 202, status: 'the_road_goes_ever_on' },
    ]);

    expect(objective.title).toContain('Contain the Shadow');
    expect(objective.route).toBe('/quests?status=the_shadow_falls');
    expect(objective.mode).toBe('quests');
  });

  it('routes in-progress objective to map scouting', () => {
    const objective = getMissionObjective([
      { ...baseQuest, id: 301, status: 'the_road_goes_ever_on', location_id: 22, location_name: 'Minas Tirith' },
    ]);

    expect(objective.ctaLabel).toBe('Scout on Map');
    expect(objective.mode).toBe('map');
    expect(objective.route).toContain('/map?');
    expect(objective.route).toContain('zoomToLocation=22');
    expect(objective.route).toContain('selectedQuestId=301');
  });

  it('falls back to proposal objective when all quests are complete', () => {
    const objective = getMissionObjective([
      { ...baseQuest, id: 401, status: 'it_is_done', location_id: undefined },
      { ...baseQuest, id: 402, status: 'completed', location_id: 35 },
    ]);

    expect(objective.title).toContain('Set the Next Chapter');
    expect(objective.mode).toBe('quests');
    expect(objective.route).toContain('/quests?');
    expect(objective.route).toContain('propose=1');
    expect(objective.route).toContain('seedLocationId=35');
  });
});
