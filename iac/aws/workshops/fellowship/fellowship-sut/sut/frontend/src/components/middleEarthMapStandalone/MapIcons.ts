/**
 * Map Icons Configuration
 * TypeScript version of mapIcons.js
 */

import L from 'leaflet';

// Import icon images - using public paths
const battleImg = '/middle-earth-map/icons/swords.svg';
const deathImg = '/middle-earth-map/icons/coffin.svg';
const encounterImg = '/middle-earth-map/icons/eye.svg';
const hobbitImg = '/middle-earth-map/icons/hobbit.svg';
const dwarfImg = '/middle-earth-map/icons/dwarf.svg';
const elfImg = '/middle-earth-map/icons/elf.svg';
const humanImg = '/middle-earth-map/icons/castle.svg';
const darkImg = '/middle-earth-map/icons/evil.svg';

const iconSize: [number, number] = [30, 30];
const iconAnchor: [number, number] = [15, 30];
const popupAnchor: [number, number] = [3, -27];

// Helper to create icon with error handling
const createIcon = (iconUrl: string, name: string) => {
  const icon = L.icon({
    iconUrl: iconUrl,
    iconSize: iconSize,
    iconAnchor: iconAnchor,
    popupAnchor: popupAnchor
  });
  
  // Log icon creation for debugging
  console.log(`Created ${name} icon with URL: ${iconUrl}`);
  return icon;
};

export const battleIcon = createIcon(battleImg, 'battle');

export const deathIcon = createIcon(deathImg, 'death');

export const encounterIcon = createIcon(encounterImg, 'encounter');

export const hobbitIcon = createIcon(hobbitImg, 'hobbit');

export const dwarfIcon = createIcon(dwarfImg, 'dwarf');

export const elfIcon = createIcon(elfImg, 'elf');

export const humanIcon = createIcon(humanImg, 'human');

export const darkIcon = createIcon(darkImg, 'dark');
