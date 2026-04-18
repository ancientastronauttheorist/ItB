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

## Weapon-def overrides (Phase 3 self-healing loop)

Runtime patches to the Rust `WEAPONS` table so the solver can be
corrected between solves without a `maturin build`. Applied
per-field over the compile-time defaults; an empty overlay keeps
the fast path (`&WEAPONS` directly, no allocation).

**Precedence (lowest → highest):**

1. Compile-time `rust_solver/src/weapons.rs::WEAPONS`.
2. `data/weapon_overrides.json` — committed, human-reviewed, loaded
   on every `itb_solver.solve` via `src/solver/weapon_overrides.py::
   load_base_overrides`.
3. Per-solve runtime entries passed as `weapon_overrides_runtime`
   in the bridge JSON (reserved for future Tier-3 hot-patch work;
   not wired into the loop today).

Rust reports both layers' applied patches in each solution JSON as
`applied_overrides: [{weapon_id, fields, source}]`. Empty overlay
omits the field entirely.

**Paths and CLIs:**

| Path | Purpose |
|---|---|
| `data/weapon_overrides.json` | Committed base layer. Array of `{weapon_id, <field>: <value>, ...}` entries. |
| `data/weapon_overrides_staged.jsonl` | Auto-staged candidates awaiting review (one JSON per line). |
| `tests/weapon_overrides/<weapon_id>_<case>.json` | Regression-board fixtures. Every committed override needs one. Format: `tests/weapon_overrides/README.md`. |
| `src/solver/weapon_overrides.py` | Loader, validator, staging helper, Python parity overlay. |
| `rust_solver/src/weapons.rs::PartialWeaponDef` | Rust patch struct + `build_overlay_table`. |

**Review flow:**

1. `cmd_research_submit` runs the comparator. A
   `severity=high` mismatch whose `field` is stageable (today: only
   `damage`) gets appended to `weapon_overrides_staged.jsonl`.
2. `python3 game_loop.py review_overrides` lists pending candidates.
3. `python3 game_loop.py review_overrides accept <index>` promotes
   one into `data/weapon_overrides.json`. Refuses without a matching
   regression board (`--force` bypasses only for bootstrap).
4. `python3 game_loop.py review_overrides reject <index>` drops the
   candidate.
5. After acceptance, `pytest tests/test_weapon_overrides_regression.py`
   validates the new entry. Next solve applies it — no rebuild needed.
6. Human then `git commit data/weapon_overrides.json` —
   never auto-committed.

**Constraints (enforced in code):**

- Unknown `weapon_id` or flag name → entry silently dropped. A typo
  can never brick a live solve.
- Schema validation fires at load time in Python and on accept via
  `load_base_overrides` — a malformed `data/weapon_overrides.json`
  fails loud at the CLI, not silently mid-run.
- Regression-board gate runs in CI via
  `tests/test_weapon_overrides_regression.py` — an override without
  a fixture or with no observable effect fails the suite.

**Design doc:** `docs/self_healing_loop_design.md` (Phase 3 section).

## Related docs

- `docs/lua_bridge_architecture.md` — bridge IPC design, protocol, file formats
- `docs/env_hazards_by_island.md` — environment hazard matrix per island
- `docs/self_improvement_plan.md` — roadmap for self-correcting system
- `docs/self_healing_loop_design.md` — self-healing research + override pipeline (Phases 0–3)
