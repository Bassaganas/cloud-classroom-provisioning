/**
 * Easter Eggs - Hidden delights for fellowship adventurers
 */

let gandolfClickCount = 0;
let lastGandolfClick = 0;

/**
 * Track Gandalf name clicks for the "You shall not pass!" animation
 */
export const trackGandolfClick = () => {
  const now = Date.now();
  
  // Reset counter if more than 1 second has passed since last click
  if (now - lastGandolfClick > 1000) {
    gandolfClickCount = 0;
  }
  
  gandolfClickCount++;
  lastGandolfClick = now;
  
  if (gandolfClickCount === 5) {
    triggerGandolfFireworks();
    gandolfClickCount = 0;
  }
};

/**
 * Trigger Gandolf's fireworks animation
 */
const triggerGandolfFireworks = () => {
  // Create a overlay with animation
  const overlay = document.createElement('div');
  overlay.style.cssText = `
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: radial-gradient(circle, rgba(218, 165, 32, 0.6) 0%, transparent 70%);
    z-index: 9999;
    pointer-events: none;
    animation: fadeIn 0.5s ease-out, fadeOut 1s ease-in 1s forwards;
  `;
  
  document.body.appendChild(overlay);
  
  // Add firework particles
  for (let i = 0; i < 20; i++) {
    const particle = document.createElement('div');
    const angle = (i / 20) * Math.PI * 2;
    const distance = 200 + Math.random() * 100;
    const x = window.innerWidth / 2 + Math.cos(angle) * distance;
    const y = window.innerHeight / 2 + Math.sin(angle) * distance;
    
    particle.style.cssText = `
      position: fixed;
      left: ${window.innerWidth / 2}px;
      top: ${window.innerHeight / 2}px;
      width: 12px;
      height: 12px;
      background: #FFD700;
      border-radius: 50%;
      box-shadow: 0 0 10px #DAA520;
      z-index: 9998;
      pointer-events: none;
      animation: firefly 1.5s ease-out forwards;
      --x: ${x - window.innerWidth / 2}px;
      --y: ${y - window.innerHeight / 2}px;
    `;
    
    document.body.appendChild(particle);
    
    setTimeout(() => particle.remove(), 1500);
  }
  
  // Play "You shall not pass!" message
  console.log('%c🧙 "You shall not pass!" ~Gandalf', 'font-size: 20px; color: #FFD700; font-weight: bold; text-shadow: 0 0 10px #DAA520;');
  
  setTimeout(() => overlay.remove(), 1500);
};

/**
 * Get a random Tolkien quote
 */
export const getRandomQuote = (): string => {
  const quotes = [
    '"All we have to decide is what to do with the time that is given us." - Gandalf',
    '"Not all those who wander are lost." - Tolkien',
    '"A wizard is never late, nor is he early." - Gandalf',
    '"I wish it need not have happened in my time," said Frodo. "So do I," said Gandalf, "and so do all who live to see such times."',
    '"Even the smallest person can change the course of the future." - Galadriel',
    '"Courage is found in unlikely places." - Gimli',
    '"There and Back Again" - Bilbo Baggins',
    '"My precious..." - Gollum',
    '"One does not simply walk into Mordor." - Boromir',
    '"I am no man." - Éowyn',
  ];
  
  return quotes[Math.floor(Math.random() * quotes.length)];
};

/**
 * Check for keyboard Easter egg (Konami code variant)
 * Sequence: ArrowUp, ArrowUp, ArrowDown, ArrowDown, ArrowLeft, ArrowRight, ArrowLeft, ArrowRight, b, a
 */
let keySequence: string[] = [];

export const setupKeyboardEasterEgg = () => {
  const konamiCode = ['ArrowUp', 'ArrowUp', 'ArrowDown', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'ArrowLeft', 'ArrowRight', 'b', 'a'];
  
  document.addEventListener('keydown', (e) => {
    keySequence.push(e.key);
    keySequence = keySequence.slice(-konamiCode.length);
    
    if (keySequence.join(',') === konamiCode.join(',')) {
      activateSecretMode();
      keySequence = [];
    }
  });
};

/**
 * Activate secret mode - adds elvish overlay
 */
const activateSecretMode = () => {
  const secret = document.createElement('div');
  secret.style.cssText = `
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    background: rgba(45, 80, 22, 0.95);
    border: 3px solid #FFD700;
    padding: 2rem;
    border-radius: 12px;
    z-index: 99999;
    text-align: center;
    animation: scaleIn 0.4s ease-out;
  `;
  
  secret.innerHTML = `
    <div style="font-family: 'Cinzel', serif; font-size: 2rem; color: #FFD700; text-shadow: 0 0 10px #DAA520; margin-bottom: 1rem;">
      🌟 Secret Discovered 🌟
    </div>
    <div style="font-family: 'Lora', serif; font-size: 1rem; color: #E8D5B7; line-height: 1.8; margin-bottom: 1rem;">
      <p>You have unlocked the Fellowship's Hidden Wisdom!</p>
      <p style="font-style: italic; margin-top: 1rem;">"Not all who wander are lost,<br/>For in the darkness of code,<br/>Gems of joy are revealed to those bold."</p>
    </div>
  `;
  
  document.body.appendChild(secret);
  
  // Auto-remove after 5 seconds
  setTimeout(() => {
    secret.style.animation = 'fadeOut 0.6s ease-out forwards';
    setTimeout(() => secret.remove(), 600);
  }, 5000);
  
  console.log('%c✨ You discovered the secret! Welcome to the Fellowship of the Code! ✨', 'font-size: 16px; color: #FFD700; font-weight: bold; background: #2D5016;');
};

/**
 * Check for quest completion celebration (triggered externally)
 */
export const celebrateQuestCompletion = () => {
  // Create celebration particles
  for (let i = 0; i < 30; i++) {
    const particle = document.createElement('div');
    const angle = (i / 30) * Math.PI * 2;
    const distance = Math.random() * 200 + 100;
    
    particle.style.cssText = `
      position: fixed;
      left: ${window.innerWidth / 2}px;
      top: ${window.innerHeight / 2}px;
      width: 10px;
      height: 10px;
      background: ${['#FFD700', '#10B981', '#FF6B35', '#B19CD9'][Math.floor(Math.random() * 4)]};
      border-radius: 50%;
      box-shadow: 0 0 8px currentColor;
      z-index: 5000;
      pointer-events: none;
      animation: cascade-reveal 1.5s ease-out forwards;
      --x: ${Math.cos(angle) * distance}px;
      --y: ${Math.sin(angle) * distance}px;
    `;
    
    document.body.appendChild(particle);
    setTimeout(() => particle.remove(), 1500);
  }
  
  console.log('%c🎉 Quest Completed! Well done, brave adventurer! 🎉', 'font-size: 18px; color: #10B981; font-weight: bold;');
};

/**
 * Dark magic warning Easter egg
 */
export const triggerDarkMagicAnimation = () => {
  document.documentElement.style.filter = 'hue-rotate(-20deg) saturate(1.2)';
  
  setTimeout(() => {
    document.documentElement.style.filter = 'none';
  }, 3000);
};

// Initialize keyboard Easter egg when the module loads
if (typeof window !== 'undefined') {
  // Delay initialization to ensure DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupKeyboardEasterEgg);
  } else {
    setupKeyboardEasterEgg();
  }
}
