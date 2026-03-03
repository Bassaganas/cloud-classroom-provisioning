export interface User {
  id: number;
  username: string;
  email: string;
  role: string;
  gold?: number;
  created_at?: string;
}

export interface Quest {
  id: number;
  title: string;
  description: string;
  status: 'not_yet_begun' | 'the_road_goes_ever_on' | 'it_is_done' | 'the_shadow_falls' | 'pending' | 'in_progress' | 'completed' | 'blocked'; // Include old values for backward compatibility
  quest_type?: 'The Journey' | 'The Battle' | 'The Fellowship' | 'The Ring' | 'Dark Magic';
  priority?: 'Critical' | 'Important' | 'Standard';
  is_dark_magic?: boolean;
  assigned_to?: number;
  location_id?: number;
  location_name?: string;
  assignee_name?: string;
  character_quote?: string;
  created_at?: string;
  updated_at?: string;
  completed_at?: string;
}

export interface Member {
  id: number;
  name: string;
  race: string;
  role: string;
  status: string;
  description?: string;
  created_at?: string;
}

export interface Location {
  id: number;
  name: string;
  description?: string;
  region: string;
  map_x?: number;  // X coordinate (0-100)
  map_y?: number;  // Y coordinate (0-100)
  created_at?: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  message: string;
  user: User;
}

export type NpcCharacter = 'frodo' | 'sam' | 'gandalf';

export interface NpcSuggestedAction {
  goal_type: string;
  title: string;
  reason: string;
  target?: {
    quest_id?: number;
    route: string;
    query?: Record<string, string | number | boolean>;
  };
}

export interface NpcChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface NpcSuggestedQuest {
  title: string;
  description: string;
  quest_type: 'The Journey' | 'The Battle' | 'The Fellowship' | 'The Ring' | 'Dark Magic';
  priority: 'Critical' | 'Important' | 'Standard';
  location_id?: number;
}

export interface NpcChatResponse {
  conversation_id: string;
  character: NpcCharacter;
  message?: string;
  opener?: string;
  suggested_action: NpcSuggestedAction;
  suggested_quest?: NpcSuggestedQuest;
  messages: NpcChatMessage[];
  negotiation?: {
    item_id?: number;
    item_name?: string;
    owner_character?: string;
    personality_profile?: string;
    current_ask?: number;
    round?: number;
    status?: 'active' | 'accepted' | 'bored' | 'no_items' | 'stop-bargain';
  };
  balance?: {
    gold: number;
  };
  purchase_result?: {
    purchase: InventoryItem;
    balance: {
      gold: number;
    };
    deal_quality: 'good' | 'fair' | 'bad';
  };
  stats?: BargainStats;
  shop_items?: ShopItem[];
  timestamp?: string;
}

export interface ShopItem {
  id: number;
  name: string;
  description?: string;
  owner_character: string;
  personality_profile: string;
  asking_price: number;
  is_sold: boolean;
}

export interface InventoryItem {
  id: number;
  user_id: number;
  item_id: number;
  item_name?: string;
  owner_character?: string;
  description?: string;
  paid_price: number;
  base_price_revealed: number;
  savings_percent: number;
  created_at?: string;
}

export interface BargainStats {
  purchased_count: number;
  best_bargain_percent: number;
  average_savings_percent: number;
}

// Re-export MiddleEarthMap types
export * from './middleEarthMap';
