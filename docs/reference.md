# ItB Bot — Reference Material

Deep reference. CLAUDE.md covers operational rules; this file covers project layout
and data sources. Read when you need to find where something lives or look up
detailed game data.

## File Structure

```
itb-bot/
├── CLAUDE.md              # Operational manual (loaded every turn — keep lean)
├── TODO.md                # Roadmap + achievement checklist
├── game_loop.py           # CLI entry — dispatches to src/loop/
├── island_select.py       # Random island picker
├── src/
│   ├── loop/              # CLI command implementations
│   │   ├── session.py     # RunSession state, file-locked persistence
│   │   ├── logger.py      # Append-only markdown decision log
│   │   └── commands.py    # All CLI subcommand bodies
│   ├── bridge/            # Lua bridge — state extraction + action execution
│   │   ├── modloader.lua  # Game-side Lua that dumps state & executes commands
│   │   ├── protocol.py    # File-based IPC (/tmp/itb_state.json etc.)
│   │   ├── reader.py      # Bridge state → Board
│   │   └── writer.py      # Python → bridge commands
│   ├── capture/
│   │   └── save_parser.py # Lua save file fallback when bridge unavailable
│   ├── vision/            # Sprite matching for shop/reward screens
│   ├── model/             # Board, Unit, WeaponDef dataclasses
│   ├── solver/            # Threat analysis, search, evaluation (thin wrapper
│   │                      # over Rust; simulate.py is a parallel Python impl)
│   ├── control/
│   │   └── executor.py    # grid_to_mcp + click planning (calibrated <2px)
│   ├── strategy/          # Achievement planner, run-level decisions
│   └── main.py            # Legacy entry (kept for backward compat)
├── rust_solver/           # Primary solver — pyo3 extension, installed as itb_solver
│   └── src/
│       ├── solver.rs      # Search loop
│       ├── simulate.rs    # Weapon + push + damage simulation
│       ├── evaluate.rs    # Scoring (EvalWeights)
│       ├── enemy.rs       # Enemy phase resolution
│       └── weapons.rs     # All weapon defs (damage, push, AOE flags)
├── sessions/              # Per-run JSON (active_session.json)
├── logs/                  # Per-run markdown decision logs
├── recordings/            # Per-turn state + solve recordings (replay / tuner)
│   └── failure_db.jsonl   # Tuner training corpus
├── snapshots/             # Saved states for regression
├── weights/               # EvalWeights JSON (active.json + versioned)
├── tests/                 # Unit + regression tests
├── scripts/
│   ├── install_modloader.sh  # Deploy bridge Lua into Steam app bundle
│   ├── regression.sh         # Full regression suite (used by pre-commit hook)
│   └── hooks/pre-commit      # Runs regression when solver code changes
└── data/
    ├── achievements_detailed.json
    ├── board_state_test.json
    ├── grid_reference.json
    ├── islands.json
    ├── mechanics.json
    ├── pilots.json
    ├── squads.json
    ├── terrain_status_mechanics.json
    ├── vek.json
    ├── ref_*.md               # Markdown reference files (see below)
    └── wiki_raw/              # 135 raw wiki JSON dumps
```

## Knowledge Base

Markdown reference files in `data/` — read when you need detailed game data:

| File | Contents | Read when... |
|------|----------|-------------|
| `data/ref_squads_and_mechs.md` | All 13 squads, mechs, weapons, upgrades, squad achievements | Working on specific squad, achievement planning |
| `data/ref_vek_bestiary.md` | All Vek (HP/move/attack), alphas, Psions, Leaders, Bosses, Bots | Solver/vision work, threat analysis |
| `data/ref_pilots.md` | All pilots, abilities, corporations, power costs | Pilot selection, run planning |
| `data/ref_game_mechanics.md` | Full terrain/status/damage/push rules, turn structure, grid, islands | Debugging solver, verifying rules |
| `data/ref_achievement_strategies.md` | Per-achievement strategy, bot approach, setup, difficulty | Achievement strategist, run config |

Structured JSON data in `data/` — machine-readable for code:

| File | Contents |
|------|----------|
| `data/squads.json` | All squads with mechs, weapons, upgrades, achievements |
| `data/vek.json` | All Vek with stats, attacks, alpha variants |
| `data/pilots.json` | Pilot system, XP, all pilots with abilities |
| `data/mechanics.json` | Terrain, status effects, damage rules |
| `data/terrain_status_mechanics.json` | Extended terrain + status interactions |
| `data/islands.json` | Island structure, environments, missions |
| `data/achievements_detailed.json` | All 70 achievements with metadata |
| `data/grid_reference.json` | Game window/grid pixel coordinates |
| `data/board_state_test.json` | Test board state for solver development |

`data/wiki_raw/*.json` (135 files) — individual unit deep-dives, last-resort lookup.

## Related docs

- `docs/lua_bridge_architecture.md` — bridge IPC design, protocol, file formats
- `docs/env_hazards_by_island.md` — environment hazard matrix per island
- `docs/self_improvement_plan.md` — roadmap for self-correcting system
