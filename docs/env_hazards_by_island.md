# Environment Hazards by Island

Reference table for the M5 env-hazard sweep. Each Into the Breach corporate island has a distinct set of environmental effects that are RNG-rolled per mission at mission start. All hazards are **island-exclusive** — no hazard appears on more than one island.

## Mapping

| Hazard | Island | Biome | Effect summary |
|---|---|---|---|
| **Tidal Waves** | Archive Inc | Temperate | Waves wash in from coast, one column flooded per turn (G→F→E→…). Non-obstacle tiles drown any unit on them. |
| **Air Strike** | Archive Inc | Temperate | Old Earth planes bomb a target tile + adjacent each turn. Hits bypass shield, frozen, armor, ACID. |
| **Lightning Storm** | R.S.T. Corporation | Desert | 4 random tiles struck per turn. |
| **Cataclysm** | R.S.T. Corporation | Desert | One row of tiles converts to Chasm each turn; non-flying ground units in that row die. |
| **Sandstorm** | R.S.T. Corporation | Desert | Smoke gradually covers the level, preventing attacks and repair. |
| **Conveyor Belts** | Detritus Disposal | Industrial | Tiles push units 1 step per turn along the belt direction. |
| Ice Storm | Pinnacle Robotics | Ice | 3×3 freeze per turn. Not in the original M5 6-list; bridge warnings populate `environment_freeze`. |

## Sources

- Local KB: `data/islands.json`, `data/wiki_raw/Archive_Inc.json`, `data/wiki_raw/RST.json`, `data/wiki_raw/Detritus.json`, `data/wiki_raw/Pinnacle.json`.
- Web: Into the Breach Fandom wiki (Islands, Environments, R.S.T. Corporation, Detritus Disposal pages); GameFAQs effect pages (slugs like `archive-tidal-waves`, `rst-lightning-storm`, `rst-cataclysm`, `detritus-conveyors`, `pinnacle-ice-storm`).

Both sources agree on all 6 main mappings.

## M5 Sweep Plan

Tracked in `memory/project_m5_env_sweep.md`. Status 2026-07-10: 5/6 confirmed, including live Terratide/Sandstorm evidence on R.S.T. / Beautiful Corner. Air Strike remains outstanding.

**Architectural note surfaced by the sweep:** Environment warnings need effect-specific routing:
- **Per-turn damage hazards** (Tidal Waves, Cataclysm, Lightning Storm, probably Air Strike): queue entries in `environment_danger_v2` each turn with `[x, y, damage, kills, flying_immune]` shape.
- **Status and movement hazards:** Conveyor Belts are tile metadata (`conveyor: N`); Ice Storm uses `environment_freeze`; Terratide's warned row is exposed by `Board:IsEnvironmentDanger` but must be routed to pending smoke, not damage. The resulting smoke is then visible on the raw `tiles` array.

Remaining sweep target:

1. **Archive Inc** (return trip) — Air Strike. Avoid the "Defend the Artillery Support" mission type: that uses a friendly NPC artillery unit, not the Air Strike env hazard, and `environment_danger_v2` stays empty.

Optionally, add **Pinnacle Robotics** for Ice Storm to extend the sweep to 7 types.

## Verifying a hazard works end-to-end

1. Start the mission and run `python3 game_loop.py read` on the first combat turn.
2. Inspect the raw warning channel appropriate to the effect: `environment_danger_v2`, `environment_freeze`, conveyor tile metadata, or Terratide pending smoke.
3. Confirm the solver routes the warning to the correct damage, terrain, movement, freeze, or smoke behavior—not merely that it notices the tiles.
4. Play the turn out, compare the projected effect with the live board, and verify that the appropriate warning channel repopulates for the next turn.
