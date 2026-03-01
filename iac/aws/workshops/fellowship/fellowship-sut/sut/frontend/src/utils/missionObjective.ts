import { Quest } from '../types';

export interface MissionObjective {
  title: string;
  description: string;
  ctaLabel: string;
  route: string;
  mode: 'map' | 'quests';
}

const normalizeStatus = (status?: string): string => {
  const statusMap: Record<string, string> = {
    pending: 'not_yet_begun',
    in_progress: 'the_road_goes_ever_on',
    completed: 'it_is_done',
    blocked: 'the_shadow_falls',
  };

  if (!status) {
    return '';
  }

  return statusMap[status] || status;
};

const isCompleted = (quest: Quest): boolean => normalizeStatus(quest.status) === 'it_is_done';

const buildMapRoute = (quest: Quest): string => {
  const params = new URLSearchParams();

  if (quest.location_id) {
    params.set('zoomToLocation', String(quest.location_id));
  }
  params.set('selectedQuestId', String(quest.id));

  return `/map?${params.toString()}`;
};

export const getMissionObjective = (quests: Quest[]): MissionObjective => {
  if (quests.length === 0) {
    return {
      title: 'Forge the Fellowship Plan',
      description: 'Begin your journey by creating the first quest objective for the council.',
      ctaLabel: 'Open Quest Scrolls',
      route: '/quests',
      mode: 'quests',
    };
  }

  const activeQuests = quests.filter((quest) => !isCompleted(quest));
  const darkMagicQuest = activeQuests.find((quest) => quest.is_dark_magic);
  if (darkMagicQuest) {
    return {
      title: 'Contain the Shadow',
      description: 'A dark-magic objective needs immediate focus before it spreads further.',
      ctaLabel: 'Resolve in Quest Scrolls',
      route: '/quests?status=the_shadow_falls',
      mode: 'quests',
    };
  }

  const inProgressQuest = activeQuests.find(
    (quest) => normalizeStatus(quest.status) === 'the_road_goes_ever_on'
  );
  if (inProgressQuest) {
    const locationName = inProgressQuest.location_name || 'the marked region';
    return {
      title: 'Advance the Active Journey',
      description: `Scout ${locationName} and push the active objective toward completion.`,
      ctaLabel: 'Scout on Map',
      route: buildMapRoute(inProgressQuest),
      mode: 'map',
    };
  }

  const readyQuest = activeQuests.find(
    (quest) => normalizeStatus(quest.status) === 'not_yet_begun'
  );
  if (readyQuest) {
    if (readyQuest.location_id) {
      const locationName = readyQuest.location_name || 'its location';
      return {
        title: 'Scout the Next Objective',
        description: `Review ${locationName} on the map before beginning the objective.`,
        ctaLabel: 'Scout on Map',
        route: buildMapRoute(readyQuest),
        mode: 'map',
      };
    }

    return {
      title: 'Open the Next Quest',
      description: 'Review details and assign your next objective in the quest scrolls.',
      ctaLabel: 'Open Quest Scrolls',
      route: `/quests?focusQuestId=${readyQuest.id}`,
      mode: 'quests',
    };
  }

  const completedWithLocation = quests.find((quest) => isCompleted(quest) && quest.location_id);
  const proposalParams = new URLSearchParams({
    propose: '1',
    seedTitle: 'Scout a new frontier',
    seedDescription: 'Define the next objective for the Fellowship and keep momentum alive.',
    seedType: 'The Journey',
    seedPriority: 'Important',
  });

  if (completedWithLocation?.location_id) {
    proposalParams.set('seedLocationId', String(completedWithLocation.location_id));
  }

  return {
    title: 'Set the Next Chapter',
    description: 'All known objectives are complete. Propose a new side quest to continue the journey.',
    ctaLabel: 'Create Side Quest',
    route: `/quests?${proposalParams.toString()}`,
    mode: 'quests',
  };
};
