import React, { useEffect, useState } from 'react';
import Login from '../components/Login';
import { User } from '../types';
import { CharacterService, DialogueResponse } from '../services/characterService';

interface LoginPageProps {
  onLogin: (user: User) => void;
}

const LoginPage: React.FC<LoginPageProps> = ({ onLogin }) => {
  const [welcomeDialogue, setWelcomeDialogue] = useState<DialogueResponse | null>(null);

  useEffect(() => {
    const welcome = CharacterService.getWelcomeMessage(
      {
        id: 0,
        username: 'traveler',
        email: 'traveler@middle-earth.local',
        role: 'guest',
      },
      true
    );
    setWelcomeDialogue(welcome);
  }, []);

  const characterEmoji =
    welcomeDialogue?.character === 'sam'
      ? '👨‍🌾'
      : welcomeDialogue?.character === 'gandalf'
      ? '🧙‍♂️'
      : '🧝';

  return (
    <div className="relative min-h-screen overflow-hidden bg-background-primary flex flex-col items-center justify-center px-4 py-10">
      <div className="absolute inset-0 bg-gradient-to-br from-forest/20 via-background-primary to-gold/20" />
      <div className="absolute inset-0 opacity-20">
        <div className="absolute top-10 left-10 h-48 w-48 rounded-full bg-gold/20 blur-3xl animate-pulse" />
        <div className="absolute bottom-10 right-10 h-56 w-56 rounded-full bg-dark-magic/20 blur-3xl animate-pulse" />
      </div>

      {/* Header - Centered at top */}
      <div className="relative z-10 text-center mb-12">
        <h1 className="text-4xl md:text-5xl mb-4 glow-gold">The Fellowship Quest Tracker</h1>
        <p className="text-lg text-parchment">
          Coordinate quests across Middle-earth with a focused, immersive workflow.
        </p>
      </div>

      {/* Login form - Centered */}
      <div className="relative z-10 w-full max-w-md">
        <Login onLogin={onLogin} />
      </div>

      {/* Subtle companion quote at bottom - moved from left side for better readability */}
      {welcomeDialogue && (
        <div className="relative z-10 mt-12 max-w-md text-center">
          <div className="flex items-center justify-center gap-2 mb-2">
            <span className="text-2xl">{characterEmoji}</span>
            <p className="text-xs uppercase tracking-wider text-parchment/70">{welcomeDialogue.character}</p>
          </div>
          <p className="text-sm text-parchment/60 italic">"{welcomeDialogue.message}"</p>
        </div>
      )}
    </div>
  );
};

export default LoginPage;
