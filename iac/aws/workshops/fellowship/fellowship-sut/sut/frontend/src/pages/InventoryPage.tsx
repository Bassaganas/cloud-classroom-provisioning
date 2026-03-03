import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiService } from '../services/api';
import { BargainStats, InventoryItem, User } from '../types';
import { Button } from '../components/ui/Button';
import GoldCounter from '../components/GoldCounter';

interface InventoryPageProps {
  user: User;
  onLogout: () => void;
}

const InventoryPage: React.FC<InventoryPageProps> = ({ user, onLogout }) => {
  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [stats, setStats] = useState<BargainStats>({
    purchased_count: 0,
    best_bargain_percent: 0,
    average_savings_percent: 0,
  });
  const [gold, setGold] = useState<number>(user.gold || 0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const [items, currentStats, currentGold] = await Promise.all([
          apiService.getInventory(),
          apiService.getBargainStats(),
          apiService.getGoldBalance(),
        ]);
        setInventory(items);
        setStats(currentStats);
        setGold(currentGold);
      } catch (error) {
        console.error('Failed to load inventory:', error);
      } finally {
        setLoading(false);
      }
    };

    load();
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <p className="text-text-primary font-readable">Gathering your purchased relics...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <nav className="bg-gradient-to-r from-forest to-forest-dark shadow-lg border-b-2 border-gold">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Link to="/dashboard" className="font-epic text-2xl text-gold hover:text-gold-light transition-colors">
              Fellowship Inventory
            </Link>
          </div>
          <div className="flex items-center gap-4">
            <Link to="/dashboard" className="text-parchment hover:text-gold transition-colors font-readable">
              Council Chamber
            </Link>
            <Link to="/quests" className="text-parchment hover:text-gold transition-colors font-readable">
              Scrolls of Middle-earth
            </Link>
            <Link to="/map" className="text-parchment hover:text-gold transition-colors font-readable">
              Map of Middle-earth
            </Link>
            <Link to="/inventory" className="text-gold font-readable font-bold">
              Inventory
            </Link>
            <GoldCounter gold={gold} />
            <Button onClick={onLogout} variant="secondary" className="text-sm">
              Leave Fellowship
            </Button>
          </div>
        </div>
      </nav>

      <div className="max-w-7xl mx-auto px-4 py-8 space-y-6">
        <h1 className="font-epic text-3xl text-gold">Inventory</h1>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-parchment-light rounded-lg p-4 border border-gold-dark/30">
            <p className="text-xs uppercase text-text-secondary">Items Purchased</p>
            <p className="font-epic text-2xl text-forest-dark">{stats.purchased_count}</p>
          </div>
          <div className="bg-parchment-light rounded-lg p-4 border border-gold-dark/30">
            <p className="text-xs uppercase text-text-secondary">Best Bargain</p>
            <p className="font-epic text-2xl text-forest-dark">{stats.best_bargain_percent.toFixed(2)}%</p>
          </div>
          <div className="bg-parchment-light rounded-lg p-4 border border-gold-dark/30">
            <p className="text-xs uppercase text-text-secondary">Average Savings</p>
            <p className="font-epic text-2xl text-forest-dark">{stats.average_savings_percent.toFixed(2)}%</p>
          </div>
        </div>

        <div className="bg-parchment-light rounded-lg border border-gold-dark/30 overflow-hidden">
          <table className="w-full">
            <thead className="bg-forest/10">
              <tr>
                <th className="text-left p-3">Item</th>
                <th className="text-left p-3">Seller</th>
                <th className="text-left p-3">Paid</th>
                <th className="text-left p-3">Real Price</th>
                <th className="text-left p-3">Deal %</th>
              </tr>
            </thead>
            <tbody>
              {inventory.length === 0 ? (
                <tr>
                  <td colSpan={5} className="p-4 text-text-secondary">
                    No purchased items yet. Visit character markers on the map to start bargaining.
                  </td>
                </tr>
              ) : (
                inventory.map((entry) => (
                  <tr key={entry.id} className="border-t border-gold-dark/20">
                    <td className="p-3">{entry.item_name}</td>
                    <td className="p-3 capitalize">{entry.owner_character}</td>
                    <td className="p-3">{entry.paid_price} Gold</td>
                    <td className="p-3">{entry.base_price_revealed} Gold</td>
                    <td className={`p-3 ${entry.savings_percent >= 0 ? 'text-green-700' : 'text-red-700'}`}>
                      {entry.savings_percent.toFixed(2)}%
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default InventoryPage;
