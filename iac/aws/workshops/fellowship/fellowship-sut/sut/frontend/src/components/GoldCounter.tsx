import React from 'react';

interface GoldCounterProps {
  gold: number;
}

const GoldCounter: React.FC<GoldCounterProps> = ({ gold }) => {
  return (
    <div className="rounded-lg border border-gold bg-black/20 px-3 py-1 text-xs font-epic text-gold whitespace-nowrap">
      Gold: {gold}
    </div>
  );
};

export default GoldCounter;
