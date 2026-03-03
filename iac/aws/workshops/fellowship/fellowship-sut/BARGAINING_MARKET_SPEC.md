# Fellowship SUT - Bargaining Market Game Specification

## Objective
Add a map-based bargaining mini-game where users negotiate with LOTR characters to buy unique second-hand premium items.

## Core Rules
1. Every user starts with a persistent `Gold` balance of `500`.
2. Items are unique and belong to LOTR characters (NPC sellers).
3. Users negotiate with NPCs from character markers on the map (not quest or location markers).
4. The user does **not** see the real/base price before committing to buy.
5. After purchase, the user sees if they made a good or bad deal.
6. Purchases are final (no resale).
7. Users gain money only by completing quests.

## Price & Bargaining Model
- Each item has a hidden `base_price` (real price).
- NPC shown asking price is computed from `base_price` + personality markup + randomness.
- Personality profiles:
  - `stingy`
  - `bargainer`
  - `generous`
  - `sentimental`
- Mood model is dynamic during chat:
  - NPC can counter-offer for several rounds.
  - NPC can get bored and stop selling.
  - NPC can rarely accept a very low offer after long negotiation.

## Personal Stats (Per User only)
Track and display:
- Current gold balance.
- Total number of purchased items.
- Best bargain percentage (highest percentage saved over base price).
- Average savings percentage across purchases.

No public leaderboard in this phase.

## UX Requirements

### Header
Display a clear gold counter in app header on key pages:
- Dashboard
- Map
- Quests
- Inventory

### Map
- Add dedicated character seller markers on the map.
- Clicking a character marker opens interaction context for bargaining.
- Character marker interactions must be separate from quest/location marker interactions.

### NPC Chat
- Bargaining must be integrated in NPC chat panel.
- Chat supports commands/intents for bargaining, including making offers.
- Chat should show negotiation progression and sale outcome.

### Inventory
- Add a dedicated inventory page where the user can see bought items.
- Show for each purchase:
  - item name
  - seller character
  - paid price
  - revealed base price
  - percentage saved (or overpaid)

## Backend API Requirements

### User Economy
- Persist `gold` on user model.
- Return `gold` in authenticated user payload.

### Shop APIs
- `GET /api/shop/items` -> list available unique items with visible asking metadata only.
- `GET /api/shop/items/<item_id>` -> item details excluding hidden base price before purchase.
- `POST /api/shop/purchase` -> finalize purchase after accepted negotiation.
- `GET /api/shop/inventory` -> user-owned purchased items + revealed deal metrics.
- `GET /api/shop/stats` -> personal bargaining stats.
- `GET /api/shop/balance` -> current user gold balance.

### Chat APIs
Extend NPC chat responses with optional negotiation payload:
- current asking price
- round count
- status (`active`, `accepted`, `declined`, `bored`)
- purchase result if completed

## Persistence Model
Add tables:
- `items` (unique sellable records)
- `inventory_items` (purchase records)

Suggested fields:
- items: `id`, `name`, `description`, `owner_character`, `personality_profile`, `base_price`, `current_ask_price`, `is_sold`, timestamps
- inventory_items: `id`, `user_id`, `item_id`, `paid_price`, `base_price_revealed`, `savings_percent`, timestamps

## Initial Item Seed (starter list)
- Aragorn: Andúril (worn)
- Bilbo: Elven Locket
- Gimli: Dwarven Ale Stein
- Gandalf: Scuffed Wizard Hat
- Legolas: Quiver of Worn Arrows
- Boromir: Gondorian Horn Fragments
- Éowyn: White Lady Cloak
- Faramir: Ranger Field Journal

## Acceptance Criteria
1. Logging in as a seeded user shows `Gold: 500`.
2. Character markers appear on map and are clickable.
3. User can start bargaining in NPC chat from a character marker.
4. User can commit purchase without seeing base price beforehand.
5. After purchase, system reveals deal quality and updates gold.
6. Inventory page shows purchased items and deal outcomes.
7. Personal stats show best bargain percentage and update after purchases.
8. New tests for map character markers and bargaining flow pass.
