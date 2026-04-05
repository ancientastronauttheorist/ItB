# Into the Breach Achievement Bot

## Project Goal

Build an autonomous bot that earns all 70 achievements in Into the Breach using Claude Code's computer use capability (screenshots + mouse/keyboard control). The game runs natively on macOS. The bot reads the screen to extract game state, reasons about optimal moves, and executes them via mouse clicks.

## Important Context

- Into the Breach is a turn-based tactics game on an 8x8 grid. It is fully deterministic with perfect information — every enemy telegraphs their attacks before you move.
- The ITB-ModLoader (Lua-based) only works on Windows. Since we're on Mac, we use **computer vision** to extract game state from screenshots and **mouse control** to execute moves. This is the correct approach for this platform.
- The game is turn-based with no time pressure (except one specific achievement). The bot can take as long as it needs per turn.
- Into the Breach is available on Steam. App ID: 590380.

## Architecture Overview

The system has 4 layers:

### Layer 1: Screen Capture & State Extraction
- Take screenshots of the game window
- Parse the 8x8 grid to identify: terrain type per tile (ground, water, mountain, chasm, forest, sand, ice, lava), occupants (mech type, Vek type, building), HP values, status effects (fire, smoke, acid, frozen, shield), enemy attack telegraphs (direction + damage), emerging Vek indicators (ground cracks), grid power bar (top-left), turn number, objective status
- The game has clean pixel art at fixed resolution with distinct sprites per unit type — template matching or simple CV should work well
- Run the game in windowed mode at a fixed resolution for consistent pixel offsets
- Consider using a sprite atlas approach: screenshot every unique tile state once, then do normalized cross-correlation matching per tile cell

### Layer 2: Game State Model
- Python dataclasses representing the full board state
- Tile grid (8x8), each tile with terrain, occupant (Pawn with type/team/hp/status), building status
- Global state: grid power, turn count, mech weapons/abilities, objectives
- Enemy intents: which tiles are threatened, damage amount, push directions
- This model is the single source of truth the solver operates on

### Layer 3: The Solver (Search Engine)
- Given a board state with known enemy intents, find the optimal sequence of 3 mech actions (move + weapon per mech, order matters)
- Approach: constraint-based threat response → bounded search → evaluation

**Constraint filtering (Phase 1):**
- Identify which buildings are threatened
- For each threat, enumerate neutralization options: kill the Vek, push it (so attack misses), block with mech body, shield the building
- This dramatically prunes the search space

**Search (Phase 2):**
- Among threat-response combinations, search for the action sequence maximizing an evaluation function
- Depth is always exactly 3 (one action per mech) — the branching is in move destinations × weapon targets × mech ordering
- Beam search with aggressive pruning of clearly bad moves

**Evaluation function (Phase 3):**
```
score = (
    buildings_saved * 10000        # existential priority
    + grid_power_preserved * 5000
    + vek_killed * 500
    + emerging_vek_blocked * 400
    + bonus_objectives * 300
    + positional_score * 10        # mech centrality, coverage
    - mech_damage_taken * 100
    - pilot_death_risk * 200
    + achievement_objective * 2000  # injected by achievement planner
)
```

**Multi-turn lookahead (Phase 4, later):**
- After choosing moves, simulate the enemy phase (deterministic — they do what they telegraphed)
- Simulate spawns from visible ground cracks
- Evaluate resulting position for next turn
- 2-3 turns of lookahead with beam search

### Layer 4: Achievement Strategist
- Operates above the solver as a strategic planner
- Reads current achievement target and modifies the solver's evaluation weights
- For example, targeting "Unwitting Allies" (4 enemies die from enemy fire): reward pushing Vek into each other's attack lines instead of killing them directly
- Some achievements require run-level planning (squad selection, island order, shop decisions)
- Some achievements are cumulative across runs and will happen naturally

## Achievement Data

9 of 70 already completed (✓). Remaining 61 sorted by global unlock % (easiest first):

### Tier 1: Green Zone (>40% global unlock — should happen naturally with competent play)
- [ ] Island Secure (75.1%) — Complete 1st Corporate Island with Rift Walkers
- [ ] Field Promotion (73.2%) — Have a Pilot reach maximum level
- [ ] Friends in High Places (49.8%) — Spend 50 Reputation across all games [cumulative]
- [ ] Come Together (44.7%) — Unlock 6 additional Pilots [cumulative]
- [ ] Best of the Best (43.9%) — Have 3 Pilots at maximum level simultaneously
- [ ] Good Samaritan (41.7%) — Earn 9 Reputation from missions on a single Corporate Island

### Tier 2: Yellow Zone (20-40% — requires specific squad play or setup)
- [x] ~~Sustainable Energy (39.1%)~~
- [ ] Perfect Battle (36.4%) — Take no Mech or Building Damage in a single battle [Rusting Hulks]
- [ ] Get Over Here (33.9%) — Kill an enemy by pulling it into yourself [Zenith Guard]
- [ ] Overpowered (30.7%) — Overpower Grid twice when full [Rusting Hulks]
- [ ] Shield Mastery (28.5%) — Block damage with Shield 4 times in a battle [Zenith Guard]
- [ ] Ramming Speed (28.4%) — Kill enemy 5+ tiles away with Dash Punch [Rift Walkers]
- [ ] Humanity's Savior (27.8%) — Rescue 100,000 civilians across all games [cumulative]
- [ ] Chain Attack (24.8%) — Chain Whip through 10 tiles [Blitzkrieg]
- [ ] Perfect Strategy (23.3%) — Collect 10 Perfect Island rewards [cumulative]
- [ ] Mass Displacement (23.0%) — Push 3 enemies with single attack [Steel Judoka]
- [ ] Backup Batteries (20.7%) — Earn/buy 10 Grid Power on single island
- [ ] Scorched Earth (20.5%) — End battle with 12 tiles on Fire [Flame Behemoths]
- [ ] I'm getting too old for this... (20.3%) — Same Pilot fights final battle 3 times [cumulative]
- [ ] There is No Try (20.2%) — Finish 3 islands without failing an objective

### Tier 3: Orange Zone (10-20% — deliberate setup needed)
- [ ] Squads Victory (19.0%) — Beat game with 4 different Squads [cumulative]
- [ ] Adaptable Victory (18.8%) — Beat game at each length (2, 3, 4 islands) [cumulative]
- [ ] Cryo Expert (16.9%) — Shoot Cryo-Launcher 4 times in one battle [Frozen Titans]
- [ ] Quantum Entanglement (16.6%) — Teleport unit 4 tiles away [Flame Behemoths]
- [ ] Pacifist (16.6%) — Kill less than 3 enemies in a battle [Frozen Titans]
- [ ] This is Fine (15.7%) — 5 enemies on Fire simultaneously [Flame Behemoths]
- [ ] Stormy Weather (15.4%) — 12 Electric Smoke damage in one battle [Rusting Hulks]
- [ ] Healing (15.1%) — Heal 10 Mech Health in one battle [Hazardous Mechs]
- [ ] Glittering C-Beam (14.8%) — Hit 4 enemies with single laser [Zenith Guard]
- [ ] Untouchable (14.5%) — Finish island without Mech Damage
- [ ] Unwitting Allies (14.2%) — 4 enemies die from enemy fire [Steel Judoka]
- [ ] Hold the Line (14.0%) — Block 4 emerging Vek in single turn [Blitzkrieg]
- [ ] Overkill (12.6%) — 8 damage to a unit with single attack [Hazardous Mechs]
- [ ] Distant Friends (11.3%) — Encounter a familiar face (FTL pilot in time pod)
- [ ] Mech Specialist (11.1%) — Beat game with 3 of same Mech in Custom squad
- [ ] Lightning War (10.5%) — First 2 islands in under 30 min [Blitzkrieg]
- [ ] Change the Odds (10.4%) — Grid Defense to 30%+ [Random squad]
- [ ] Unbreakable (10.2%) — Mech Armor absorbs 5 damage in one battle [Steel Judoka]

### Tier 4: Red Zone (<10% — hardest achievements, endgame goals)
- [ ] Class Specialist (9.8%) — Beat game with 3 Mechs from same class in Custom
- [ ] Trusted Equipment (9.7%) — 3 islands without equipping new Pilots/weapons
- [ ] Immortal (9.6%) — 4 islands without Mech destroyed [Hazardous Mechs]
- [ ] Loot Boxes! (9.4%) — Open 5 Time Pods in single game [Random]
- [ ] Engineering Dropout (9.3%) — 3 islands without powering Weapon Modification
- [ ] Trick Shot (9.2%) — Kill 3 enemies with single Janus Cannon [Frozen Titans]
- [ ] Hard Victory (9.0%) — Beat game on Hard
- [ ] Powered Blast (8.8%) — Pierce Walking Bomb with AP Cannon to kill Enemy [Bombermechs]
- [ ] On the Backburner (8.2%) — 4 damage with Reverse Thrusters [Mist Eaters]
- [ ] Unstable Ground (7.9%) — Crack 10 tiles in one mission [Cataclysm]
- [ ] Flight Specialist (7.8%) — Beat game with 3 flying Mechs in Custom
- [ ] Lucky Start (7.3%) — Beat game without spending Reputation [Random]
- [ ] Complete Victory (7.2%) — Beat game with all 10 primary Squads [cumulative]
- [ ] Stay With Me! (7.2%) — Heal 12 damage over single Island [Mist Eaters]
- [ ] Chronophobia (6.7%) — 3 islands, destroy every Time Pod
- [ ] Spider Breeding (6.7%) — Spawn 15 Arachnoids in one Island [Arachnophile]
- [ ] Let's Walk (5.8%) — Control Shot move enemies 120 spaces in one game [Mist Eaters]
- [ ] Hold the Door (5.4%) — Block 30 Emerging Vek by end of Island 2 [Bombermechs]
- [ ] Core of the Earth (5.2%) — Drop 10 Enemies into pits on one Island [Cataclysm]
- [ ] No Survivors (5.1%) — 7 units die in single turn [Bombermechs]
- [ ] Working Together (5.0%) — Area Shift 4 units at once [Arachnophile]
- [ ] Efficient Explosives (4.8%) — Kill 3 Enemies with 1 Ricochet Rocket [Arachnophile]
- [ ] Boosted (4.6%) — Boost 8 Mechs in one mission [Heat Sinkers]
- [ ] Feed the Flame (4.5%) — Light 3 Enemies on fire with single attack [Heat Sinkers]
- [ ] Maximum Firepower (4.5%) — 8 damage with single Quick-Fire Rockets [Heat Sinkers]
- [ ] Miner Inconvenience (4.0%) — Destroy 20 mountains in one game [Cataclysm]

### Already Completed (confirmed from Steam profile)
- [x] Watery Grave (68.1%)
- [x] Emerging Technologies (63.6%)
- [x] Perfect Island (61.3%)
- [x] Victory (50.1%)
- [x] The Defenders (49.8%)
- [x] Immovable Objects (41.7%)
- [x] Sustainable Energy (39.1%)
- [x] Plus 2 more not visible in screenshot (likely Island Secure and Field Promotion — verify with user)

## Development Phases

### Phase 1: Game Window Detection & Screenshot Pipeline
- Detect the Into the Breach game window on macOS
- Take reliable screenshots at consistent intervals
- Determine the game's grid coordinates and pixel offsets
- Verify we can capture the game in windowed mode at a known resolution
- **Deliverable:** A script that captures the game screen and highlights the detected 8x8 grid overlay

### Phase 2: Tile State Extraction (Core CV)
- Build a sprite atlas by capturing reference images for each tile type
- Implement per-tile classification: terrain, occupant, status effects
- Parse HP numbers (small pixel font, few possibilities — template match)
- Parse the grid power bar
- Parse enemy attack telegraph arrows (direction + damage indicators)
- Parse emerging Vek indicators (ground cracks)
- **Deliverable:** A full board state JSON dump from any in-game screenshot, validated by visual overlay

### Phase 3: Single-Turn Solver (No Lookahead)
- Implement the game state model in Python
- Implement threat identification from enemy telegraphs
- Implement threat neutralization enumeration (kill, push, block, shield)
- Implement the constraint-based search
- Implement the evaluation function
- Test against saved screenshots — can it find the move that saves all buildings?
- **Deliverable:** Given a board state, output the optimal 3-mech action sequence

### Phase 4: Mouse Control & Execution Loop
- Map grid coordinates to screen pixels for click targets
- Implement mech selection (click mech), movement (click destination), weapon firing (click weapon icon, click target)
- Handle the end-turn button
- Build the full turn loop: screenshot → extract state → solve → execute clicks → wait for animations → repeat
- **Deliverable:** Bot plays a full mission autonomously

### Phase 5: Full Run Automation
- Handle menus: squad selection, island selection, mission selection
- Handle shop/upgrade screens between islands (buy weapons, cores, grid repair)
- Handle pilot management
- Handle the end-of-run screen and starting new runs
- **Deliverable:** Bot plays full runs from main menu to victory/defeat, then starts another

### Phase 6: Multi-Turn Lookahead
- Implement forward simulation of enemy attacks and spawns
- Add 2-3 turn lookahead with beam search
- Tune evaluation weights
- **Deliverable:** Measurably better play (fewer buildings lost per run)

### Phase 7: Achievement Hunter
- Implement achievement-specific objective injection
- Build the achievement strategist that modifies evaluation weights per target
- Start with easy achievements (Tier 1 green zone) to validate the system
- Progress through tiers, using each achievement as a test of increasing bot sophistication
- Track completion via Steam API: GET https://api.steampowered.com/ISteamUserStats/GetPlayerAchievements/v1/?appid=590380&key=API_KEY&steamid=STEAM64_ID
- **Deliverable:** Systematic achievement completion, tracked and verified

## Technical Notes

- **Game resolution:** Run in windowed mode at a consistent resolution. The 8x8 grid will be at fixed pixel positions. Identify these once and hardcode the offsets.
- **Animation timing:** After executing moves, the game plays attack animations. Wait for animations to complete before taking the next screenshot. A simple approach: take screenshots repeatedly until the board state stops changing.
- **Turn structure:** Player moves all 3 mechs → enemy attacks (pre-telegraphed) → new enemies spawn → new enemies telegraph → next player turn.
- **Grid Defense RNG:** Buildings have a % chance to resist damage. The solver should assume buildings never resist (pessimistic) and treat resistance as a bonus.
- **The Reset Turn button:** The game allows undoing your entire turn once. The bot could use this to try multiple approaches per turn, but for simplicity start without it.
- **Save/Load:** The game auto-saves. If the bot needs to retry a scenario, it can force-quit and reload.

## Core Game Rules (Solver-Critical)

These rules directly affect solver correctness. Always apply them.

**Terrain kills:** Water and Chasm kill non-flying ground units. Lava kills like water but also sets flying units on Fire. Pushing enemies into these is a primary kill method.

**Push mechanics:** Pushing moves a unit 1 tile in a direction. If blocked (by another unit, mountain, or edge), the pushed unit takes 1 bump damage instead of moving. Chain pushing: if A is pushed into B, B does NOT move — A takes bump damage. Push damage is NOT affected by Armor or ACID.

**Damage types:**
- Weapon damage: reduced by Armor (-1), doubled by ACID
- Push/bump damage (1): ignores Armor and ACID
- Fire damage (1/turn): ignores Armor and ACID
- Blocking damage (1): when a Vek tries to emerge on an occupied tile — ignores Armor and ACID

**Key status effects:**
- Fire: 1 damage/turn start. Removed by repair, water, or freezing
- Frozen: invincible + immobilized. Any damage frees the unit (dealing 0 damage)
- ACID: doubles weapon damage. Persists until unit dies
- Smoke: prevents attack AND repair. Cancels Vek attacks if on smoke tile at execution
- Shield: blocks one instance of damage + all negative effects. Removed by direct damage
- Armor: -1 weapon damage (minimum 0). Does NOT reduce push/fire/blocking damage
- Webbed: cannot move, CAN still attack. Breaks if pushed away from webber

**Mountains:** 2 HP obstacles. Block movement. Can be damaged/destroyed. Become rubble (ground) when destroyed.

**Buildings:** 1 HP. Damage reduces Grid Power. Grid Defense % gives chance to resist (solver assumes 0%).

**Repair action:** Any mech can repair instead of attacking. Heals 1 HP, removes Fire and ACID. Cannot repair if smoked.

## Knowledge Base

Compiled reference files in `data/` — read the relevant file when you need detailed game data:

| File | Contents | Read when... |
|------|----------|-------------|
| `data/ref_squads_and_mechs.md` | All 13 squads, mechs (class/HP/move), weapons (damage/effect/upgrades), squad achievements, strategies | Working on specific squad, achievement planning, weapon logic |
| `data/ref_vek_bestiary.md` | All Vek (HP/move/attack/damage), alphas, Psions, Leaders, Bosses, Bots | Building solver, vision system, threat analysis |
| `data/ref_pilots.md` | All pilots, abilities, corporations, power costs | Pilot selection, run planning |
| `data/ref_game_mechanics.md` | Full terrain/status/damage/push rules, turn structure, grid defense, reputation, islands | Building/debugging solver, verifying rules |
| `data/ref_achievement_strategies.md` | Per-achievement strategy, bot approach, setup, difficulty rating | Achievement strategist, run configuration |

Curated JSON data in `data/` — structured, verified game data (machine-readable for code):

| File | Contents |
|------|----------|
| `data/squads.json` | All squads with mechs, weapons, upgrades, achievements (1092 lines) |
| `data/vek.json` | All Vek with stats, attacks, alpha variants (630 lines) |
| `data/pilots.json` | Pilot system, XP, all pilots with abilities (252 lines) |
| `data/mechanics.json` | Terrain, status effects, damage rules (387 lines) |
| `data/terrain_status_mechanics.json` | Extended terrain + status interactions (1374 lines) |
| `data/islands.json` | Island structure, environments, missions (474 lines) |
| `data/achievements_detailed.json` | All 70 achievements with detailed metadata (751 lines) |
| `data/grid_reference.json` | Game window/grid pixel coordinates (108 lines) |
| `data/board_state_test.json` | Test board state for solver development (1031 lines) |

Raw wiki data in `data/wiki_raw/*.json` (135 files) for individual unit deep-dives.

## File Structure
```
itb-bot/
├── CLAUDE.md              # This file
├── src/
│   ├── capture/           # Screenshot and window detection
│   ├── vision/            # Tile extraction, sprite matching, state parsing
│   ├── model/             # Game state dataclasses
│   ├── solver/            # Threat analysis, search, evaluation
│   ├── control/           # Mouse/keyboard execution
│   ├── strategy/          # Achievement planner, run-level decisions
│   └── main.py            # Main bot loop
├── assets/
│   ├── sprites/           # Reference sprite atlas
│   └── screenshots/       # Saved screenshots for testing
├── tests/                 # Unit tests for solver, state extraction
└── data/
    ├── ref_squads_and_mechs.md      # Compiled squad/mech/weapon reference (human-readable)
    ├── ref_vek_bestiary.md          # Compiled Vek bestiary (human-readable)
    ├── ref_pilots.md                # Compiled pilot reference (human-readable)
    ├── ref_game_mechanics.md        # Compiled game rules reference (human-readable)
    ├── ref_achievement_strategies.md # Per-achievement bot strategies (human-readable)
    ├── squads.json                  # Curated squad data (machine-readable)
    ├── vek.json                     # Curated Vek data (machine-readable)
    ├── pilots.json                  # Curated pilot data (machine-readable)
    ├── mechanics.json               # Curated game mechanics (machine-readable)
    ├── terrain_status_mechanics.json # Extended terrain/status rules (machine-readable)
    ├── islands.json                 # Island structure/environments (machine-readable)
    ├── achievements_detailed.json   # All 70 achievements with metadata (machine-readable)
    ├── grid_reference.json          # Game window/grid pixel coordinates
    ├── board_state_test.json        # Test board state for solver dev
    └── wiki_raw/                    # 135 raw wiki JSON files
```

## Current Status
Phase 4 proof-of-concept complete (MCP mouse/keyboard control). Into the Breach is installed via Steam. Knowledge base compiled from wiki data.
