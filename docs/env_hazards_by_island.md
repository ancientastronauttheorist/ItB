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
| Ice Storm | Pinnacle Robotics | Ice | 3×3 freeze per turn. Not in the original M5 6-list but populates `environment_danger_v2`. |

## Sources

- Local KB: `data/islands.json`, `data/wiki_raw/Archive_Inc.json`, `data/wiki_raw/RST.json`, `data/wiki_raw/Detritus.json`, `data/wiki_raw/Pinnacle.json`.
- Web: Into the Breach Fandom wiki (Islands, Environments, R.S.T. Corporation, Detritus Disposal pages); GameFAQs effect pages (slugs like `archive-tidal-waves`, `rst-lightning-storm`, `rst-cataclysm`, `detritus-conveyors`, `pinnacle-ice-storm`).

Both sources agree on all 6 main mappings.

## M5 Sweep Plan

Tracked in `memory/project_m5_env_sweep.md`. Status 2026-04-11: 1/6 confirmed (Tidal Waves on Archive Inc / Forgotten Hills).

Optimal order for the remaining 5:

1. **R.S.T. Corporation** — covers Lightning Storm, Cataclysm, Sandstorm (3 hazards). RNG per mission, may need re-rolls to surface all three in one run.
2. **Detritus Disposal** — Conveyor Belts.
3. **Archive Inc** (return trip) — Air Strike. Avoid the "Defend the Artillery Support" mission type: that uses a friendly NPC artillery unit, not the Air Strike env hazard, and `environment_danger_v2` stays empty.

Optionally, add **Pinnacle Robotics** for Ice Storm to extend the sweep to 7 types.

## Verifying a hazard works end-to-end

1. Start the mission and run `python3 game_loop.py read` on the first combat turn.
2. Look for the `ENVIRONMENT DANGER (N tiles)` section in stdout and the `environment_danger_v2` array in the JSON payload.
3. Confirm the solver acknowledges it: the `solve` output should print `Environment danger: N tiles` and retreat/avoid plans.
4. Play the turn out — the hazard fires at end of player turn, `env_danger_v2` should re-populate with the next step's targets.
