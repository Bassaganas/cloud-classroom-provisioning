/**
 * LoaderScreen Component
 * Initial loading screen with "See Map" button
 */

import React from 'react';
import './LoaderScreen.css';

interface LoaderScreenProps {
  onLoadMap: () => void;
  isLoading: boolean;
}

export const LoaderScreen: React.FC<LoaderScreenProps> = ({ onLoadMap, isLoading }) => {
  return (
    <div id="loader-screen" style={{ opacity: isLoading ? 1 : 0, transition: 'opacity 1s linear' }}>
      <h1>Welcome to Middle-Earth</h1>
      <button id="load-btn" onClick={onLoadMap} style={{ display: isLoading ? 'block' : 'none' }}>
        See Map
      </button>
      <div id="lds-ring" style={{ display: isLoading ? 'none' : 'inline-block' }}>
        <div></div>
        <div></div>
        <div></div>
        <div></div>
      </div>
    </div>
  );
};
