/**
 * FilterSidebar Component
 * Filter sidebar with all checkboxes for places, events, quests, and paths
 */

import React from 'react';
import type { FilterState, FilterCategory } from './types';
import './FilterSidebar.css';

interface FilterSidebarProps {
  filters: FilterState;
  onFilterChange: (category: FilterCategory, filter: string, checked: boolean) => void;
  isOpen: boolean;
  onClose: () => void;
}

interface FilterOption {
  id: string;
  label: string;
  filter: string;
}

const filterOptions: Record<FilterCategory, FilterOption[]> = {
  quests: [
    { id: 'all-quests', label: 'All', filter: 'all' },
    { id: 'erebor-quest', label: 'Quest for Erebor', filter: 'erebor' },
    { id: 'ring-quest', label: 'Quest of the Ring', filter: 'ring' }
  ],
  places: [
    { id: 'all-places', label: 'All', filter: 'all' },
    { id: 'human-places', label: 'Humans', filter: 'human' },
    { id: 'elven-places', label: 'Elves', filter: 'elven' },
    { id: 'dwarven-places', label: 'Dwarves', filter: 'dwarven' },
    { id: 'hobbit-places', label: 'Hobbits', filter: 'hobbit' },
    { id: 'dark-places', label: 'Evil', filter: 'dark' }
  ],
  events: [
    { id: 'all-events', label: 'All', filter: 'all' },
    { id: 'battle-events', label: 'Battles', filter: 'battle' },
    { id: 'death-events', label: 'Deaths', filter: 'death' },
    { id: 'encounter-events', label: 'Encounters', filter: 'encounter' }
  ],
  paths: [
    { id: 'all-paths', label: 'All', filter: 'all' },
    { id: 'thorin-path', label: 'Thorin and Company', filter: 'thorin' },
    { id: 'frodo_sam-path', label: 'Frodo & Sam', filter: 'frodo_sam' },
    { id: 'merry_pippin-path', label: 'Merry & Pippin', filter: 'merry_pippin' },
    { id: 'legolas_gimli-path', label: 'Gimli & Legolas', filter: 'legolas_gimli' },
    { id: 'boromir-path', label: 'Boromir', filter: 'boromir' },
    { id: 'aragorn-path', label: 'Aragorn', filter: 'aragorn' },
    { id: 'gandalf_grey-path', label: 'Gandalf the Grey', filter: 'gandalf_grey' },
    { id: 'gandalf_white-path', label: 'Gandalf the White', filter: 'gandalf_white' }
  ],
  questStatus: [
    { id: 'all-quest-status', label: 'All', filter: 'all' },
    { id: 'not-yet-begun', label: 'Not Yet Begun', filter: 'not_yet_begun' },
    { id: 'in-progress', label: 'In Progress', filter: 'the_road_goes_ever_on' },
    { id: 'completed', label: 'Completed', filter: 'it_is_done' },
    { id: 'failed', label: 'Failed', filter: 'the_shadow_falls' }
  ]
};

export const FilterSidebar: React.FC<FilterSidebarProps> = ({
  filters,
  onFilterChange,
  isOpen,
  onClose
}) => {
  const handleCheckboxChange = (category: FilterCategory, filter: string, checked: boolean) => {
    if (filter === 'all') {
      // Handle "All" checkbox logic
      const categoryOptions = filterOptions[category];
      const categoryFilters = filters[category];
      
      if (categoryFilters) {
        categoryOptions.forEach((option: FilterOption) => {
          if (option.filter !== 'all') {
            const isCurrentlyChecked = categoryFilters.includes(option.filter);
            if (checked && !isCurrentlyChecked) {
              onFilterChange(category, option.filter, true);
            } else if (!checked && isCurrentlyChecked) {
              onFilterChange(category, option.filter, false);
            }
          }
        });
      }
    }
    onFilterChange(category, filter, checked);
  };

  const isChecked = (category: FilterCategory, filter: string): boolean => {
    const categoryFilters = filters[category];
    return categoryFilters ? categoryFilters.includes(filter) : false;
  };

  const isAllChecked = (category: FilterCategory): boolean => {
    const categoryOptions = filterOptions[category];
    const categoryFilters = filters[category];
    
    if (!categoryFilters) {
      return false;
    }
    
    return categoryOptions.every((option: FilterOption) => 
      option.filter === 'all' || categoryFilters.includes(option.filter)
    );
  };

  return (
    <aside id="filters-container" className={isOpen ? 'active' : ''}>
      <span className="material-symbols-outlined" id="close-btn" onClick={onClose}>
        <img alt="close filters" src="/middle-earth-map/icons/close.svg" />
      </span>
      <section id="filters">
        <h1 id="main-title">Middle-Earth interactive map</h1>
        <div id="site-description">Discover Middle-Earth during the Third Age</div>

        <fieldset id="filters-quests">
          <legend>Quests</legend>
          {filterOptions.quests.map(option => (
            <div key={option.id}>
              <input
                data-category="quests"
                data-filter={option.filter}
                id={option.id}
                name={option.id}
                type="checkbox"
                checked={option.filter === 'all' ? isAllChecked('quests') : isChecked('quests', option.filter)}
                onChange={(e) => handleCheckboxChange('quests', option.filter, e.target.checked)}
                disabled={option.filter !== 'all' && isAllChecked('quests')}
              />
              <label htmlFor={option.id}>{option.label}</label>
            </div>
          ))}
        </fieldset>

        <fieldset id="filters-places">
          <legend>Places</legend>
          {filterOptions.places.map(option => (
            <div key={option.id}>
              <input
                data-category="places"
                data-filter={option.filter}
                id={option.id}
                name={option.id}
                type="checkbox"
                checked={option.filter === 'all' ? isAllChecked('places') : isChecked('places', option.filter)}
                onChange={(e) => handleCheckboxChange('places', option.filter, e.target.checked)}
                disabled={option.filter !== 'all' && isAllChecked('places')}
              />
              <label htmlFor={option.id}>{option.label}</label>
            </div>
          ))}
        </fieldset>

        <fieldset id="filters-events">
          <legend>Events</legend>
          {filterOptions.events.map(option => (
            <div key={option.id}>
              <input
                data-category="events"
                data-filter={option.filter}
                id={option.id}
                name={option.id}
                type="checkbox"
                checked={option.filter === 'all' ? isAllChecked('events') : isChecked('events', option.filter)}
                onChange={(e) => handleCheckboxChange('events', option.filter, e.target.checked)}
                disabled={option.filter !== 'all' && isAllChecked('events')}
              />
              <label htmlFor={option.id}>{option.label}</label>
            </div>
          ))}
        </fieldset>

        <fieldset id="filters-paths">
          <legend>Paths</legend>
          {filterOptions.paths.map(option => (
            <div key={option.id}>
              <input
                data-category="paths"
                data-filter={option.filter}
                id={option.id}
                name={option.id}
                type="checkbox"
                checked={option.filter === 'all' ? isAllChecked('paths') : isChecked('paths', option.filter)}
                onChange={(e) => handleCheckboxChange('paths', option.filter, e.target.checked)}
                disabled={option.filter !== 'all' && isAllChecked('paths')}
              />
              <label htmlFor={option.id}>{option.label}</label>
            </div>
          ))}
        </fieldset>

        <fieldset id="filters-questStatus">
          <legend>Quest Status</legend>
          {filterOptions.questStatus.map(option => (
            <div key={option.id}>
              <input
                data-category="questStatus"
                data-filter={option.filter}
                id={option.id}
                name={option.id}
                type="checkbox"
                checked={option.filter === 'all' ? isAllChecked('questStatus') : isChecked('questStatus', option.filter)}
                onChange={(e) => handleCheckboxChange('questStatus', option.filter, e.target.checked)}
                disabled={option.filter !== 'all' && isAllChecked('questStatus')}
              />
              <label htmlFor={option.id}>{option.label}</label>
            </div>
          ))}
        </fieldset>

        <footer>
          <p className="credits">
            Credits to Emil Johansson, creator of{' '}
            <a href="http://lotrproject.com" rel="noopener noreferrer" target="_blank">
              lotrproject.com
            </a>
            , for creating the map used in this website.
          </p>
          Created by{' '}
          <a href="https://yohannbethoule.com" rel="noopener noreferrer" target="_blank">
            Yohann Bethoule
          </a>
          , 2022
        </footer>
      </section>
    </aside>
  );
};
