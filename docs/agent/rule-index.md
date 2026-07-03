# Agent Rule Index

This index maps the historical numbered operational rules to the focused agent docs created during the 2026-05-25 cleanup. Duplicate historical rule numbers are kept and disambiguated by original line number. Use `rg "<rule title>" docs/agent` for the exact entry. The original pre-cleanup file is preserved in `docs/agent/legacy-full-guide.md`.

Duplicate historical numbers: 152, 203, 219, 220, 221.

| Rule | Original line | Title | Focused doc |
|---:|---:|---|---|
| 1 | 107 | Always verify state after each mech action (the bridge does this in `auto_turn` automatica | `docs/agent/solver-reference.md` |
| 2 | 108 | Never execute mech N+1 before the verify for mech N returns PASS, unless you consciously d | `docs/agent/safety-gates.md` |
| 3 | 109 | Click tile centers, not sprites — sprites render 100–170 px above tile center. `click_acti | `docs/agent/live-runbook.md` |
| 4 | 110 | After every failed run, analyze the critical turn. Save a snapshot first. | `docs/agent/live-runbook.md` |
| 5 | 111 | To select a mech in manual play, click its tile on the board. No portraits, no Tab, no key | `docs/agent/live-runbook.md` |
| 6 | 112 | Priority order: buildings > threats > kills > spawns. | `docs/agent/solver-reference.md` |
| 7 | 113 | Default combat | `docs/agent/live-runbook.md` |
| 8 | 114 | Never move onto ACID tiles voluntarily — doubles damage, disables armor. | `docs/agent/solver-reference.md` |
| 9 | 115 | Self-improvement | `docs/agent/solver-reference.md` |
| 10 | 116 | Bridge-to-visual coordinate rule (see Execution Model). Use A1–H8 in all communication. | `docs/agent/live-runbook.md` |
| 11 | 117 | No keyboard during combat. | `docs/agent/live-runbook.md` |
| 12 | 118 | Use all mech actions every turn — even suboptimal moves beat skipping. | `docs/agent/solver-reference.md` |
| 13 | 119 | The solver handles environment hazards via `environment_danger_v2`: each entry is `[x, y,  | `docs/agent/solver-reference.md` |
| 14 | 120 | On crash/timeout recovery, always start with `cmd_read` + `cmd_solve`. Never resume a prev | `docs/agent/solver-reference.md` |
| 15 | 121 | Save file updates only at turn boundaries. Bridge does not have this limit — `verify_actio | `docs/agent/solver-reference.md` |
| 16 | 122 | Deployment | `docs/agent/live-runbook.md` |
| 17 | 123 | Hover-verify-click — for novel UI only. | `docs/agent/live-runbook.md` |
| 18 | 124 | Prefer `game_loop.py read` over screenshots for combat state. | `docs/agent/live-runbook.md` |
| 19 | 125 | Always follow the solver — never override. | `docs/agent/safety-gates.md` |
| 20 | 126 | Research gate — never solve past an unknown. | `docs/agent/safety-gates.md` |
| 21 | 127 | Codex Computer Use coordinate caveat. | `docs/agent/safety-gates.md` |
| 22 | 128 | Simulator version discipline. | `docs/agent/live-runbook.md` |
| 23 | 129 | Grid-drop investigation gate — fire now, not later. | `docs/agent/safety-gates.md` |
| 24 | 131 | Diagnosis loop — "drain the queue", "run the loop", "diagnose this run" all mean the same protocol. | `docs/agent/safety-gates.md` |
| 25 | 144 | New-run setup is achievement-aware: difficulty + Advanced Edition ON + the target squad. | `docs/agent/live-runbook.md` |
| 26 | 145 | Session lock discipline | `docs/agent/safety-gates.md` |
| 27 | 146 | No repo-wide Rust formatting during tactical fixes. | `docs/agent/live-runbook.md` |
| 28 | 147 | Do not chain session-mutating commands. | `docs/agent/safety-gates.md` |
| 29 | 148 | Final-island save phase anomaly. | `docs/agent/solver-reference.md` |
| 30 | 149 | Safety block emergency protocol. | `docs/agent/safety-gates.md` |
| 31 | 150 | Research queue cleanup. | `docs/agent/safety-gates.md` |
| 32 | 151 | Research queue peek still matters. | `docs/agent/safety-gates.md` |
| 33 | 152 | Deployment roster supplementation is built in. | `docs/agent/live-runbook.md` |
| 34 | 153 | Projectile-grapple attacks are line attacks, not melee. | `docs/agent/solver-reference.md` |
| 35 | 154 | Trust engine terrain ids over stale terrain names. | `docs/agent/solver-reference.md` |
| 36 | 155 | Enemy attack intent must be save-gated when available. | `docs/agent/safety-gates.md` |
| 37 | 156 | Dirty-plan acceptance is exact and single-use. | `docs/agent/safety-gates.md` |
| 38 | 157 | Weapon upgrades that change behavior must be explicit in solving and execution. | `docs/agent/achievement-playbook.md` |
| 39 | 158 | Controllable mission allies count if they have weapons. | `docs/agent/safety-gates.md` |
| 40 | 159 | Dirty frontier before dirty consent. | `docs/agent/safety-gates.md` |
| 41 | 160 | Lookahead frontier is diagnostic until promoted. | `docs/agent/safety-gates.md` |
| 42 | 161 | Some weapon-specific kill pushes still corpse-bump live blockers. | `docs/agent/achievement-playbook.md` |
| 43 | 163 | Bridge-executed combat does not guarantee Reset Turn is usable. | `docs/agent/live-runbook.md` |
| 44 | 164 | Time pod recovery UI beats the crossed objective line. | `docs/agent/achievement-playbook.md` |
| 45 | 165 | Manual plan scoring can be invalid-action dirty. | `docs/agent/safety-gates.md` |
| 46 | 166 | Detritus Contraption barrages must target a non-source unit. | `docs/agent/solver-reference.md` |
| 47 | 167 | Soft-disable masks must cover every WId. | `docs/agent/safety-gates.md` |
| 48 | 168 | Normal/Alpha Spiders are pushable. | `docs/agent/solver-reference.md` |
| 49 | 169 | Teleporter move-then-attack targets use the post-swap tile. | `docs/agent/solver-reference.md` |
| 50 | 170 | Every move-then-attack target is relative to the post-move tile. | `docs/agent/solver-reference.md` |
| 51 | 171 | Post-action desyncs are an automatic investigation gate. | `docs/agent/safety-gates.md` |
| 52 | 172 | Partial re-solves must preserve upgraded weapon overlays. | `docs/agent/safety-gates.md` |
| 53 | 173 | ACID pools are non-stoppable for player movement. | `docs/agent/solver-reference.md` |
| 54 | 174 | Smoke on a queued web source releases the web immediately. | `docs/agent/solver-reference.md` |
| 55 | 175 | Rocket Artillery damage upgrades need save overlays and Rocket semantics. | `docs/agent/solver-reference.md` |
| 56 | 176 | Perfect Battle turns treat mech HP loss as blocking. | `docs/agent/safety-gates.md` |
| 57 | 177 | Cannon-Bot Mark I is a projectile with fire. | `docs/agent/solver-reference.md` |
| 58 | 178 | Retire completed achievement blockers immediately. | `docs/agent/safety-gates.md` |
| 59 | 179 | AE Moth/Bouncer recoil is a real queued self-push. | `docs/agent/safety-gates.md` |
| 60 | 180 | Mission_Trapped Coal Plant tiles may need inferred unique-building accounting. | `docs/agent/solver-reference.md` |
| 61 | 181 | Dirty-plan selection should minimize same-class collateral. | `docs/agent/safety-gates.md` |
| 62 | 182 | Leap weapons cannot land on chasm tiles. | `docs/agent/solver-reference.md` |
| 63 | 183 | Rocket Artillery center push does not edge-bump. | `docs/agent/solver-reference.md` |
| 64 | 184 | ACID status is not an instant pool under live targets. | `docs/agent/solver-reference.md` |
| 65 | 185 | Starfish attacks are self-centered diagonal appendages, not melee. | `docs/agent/solver-reference.md` |
| 66 | 186 | Aerial Bombs cannot land on water or lava. | `docs/agent/solver-reference.md` |
| 67 | 187 | Repulse edge pushes do not edge-bump. | `docs/agent/solver-reference.md` |
| 68 | 188 | Web Egg adjacency webs are tile-based, but do not steal active grapples. | `docs/agent/solver-reference.md` |
| 69 | 189 | Burrower Slam hits the perpendicular three-tile row. | `docs/agent/solver-reference.md` |
| 70 | 190 | Save-file upgrade overlays must read pawn mod pips, not only `current.weapons`. | `docs/agent/live-runbook.md` |
| 71 | 191 | Player artillery target areas are cardinal, not diagonal. | `docs/agent/solver-reference.md` |
| 72 | 192 | Diagnostic replay/score must reject impossible player actions. | `docs/agent/solver-reference.md` |
| 73 | 193 | Bridge tile arrays are records, not coordinate-indexed grids. | `docs/agent/solver-reference.md` |
| 74 | 194 | Aerial Bombs bridge transit damage is adaptive. | `docs/agent/safety-gates.md` |
| 75 | 195 | Normal Psions are pushable. | `docs/agent/solver-reference.md` |
| 76 | 196 | Blast Psion explosions chain through eligible non-minor Vek. | `docs/agent/solver-reference.md` |
| 77 | 197 | Dam flood drown deaths still fire death side effects. | `docs/agent/solver-reference.md` |
| 78 | 198 | Direct building damage drains grid per HP; bump exceptions stay narrow. | `docs/agent/safety-gates.md` |
| 79 | 199 | Minor Vek do not receive Psion aura bonuses. | `docs/agent/live-runbook.md` |
| 80 | 200 | Blobber Leader is not an Alpha Blobber alias. | `docs/agent/safety-gates.md` |
| 81 | 201 | Move-status effects can settle after bridge MOVE. | `docs/agent/safety-gates.md` |
| 82 | 202 | Ramming recoil on sand creates smoke. | `docs/agent/solver-reference.md` |
| 83 | 203 | Focused Rust unit tests need the cargo test harness flags. | `docs/agent/achievement-playbook.md` |
| 84 | 204 | Mission preview boards can absorb map clicks as Start Mission. | `docs/agent/live-runbook.md` |
| 85 | 205 | Diagnostic score_plan must include spawn blocking. | `docs/agent/safety-gates.md` |
| 86 | 206 | Shield Projector is a building-defense action, not just unit support. | `docs/agent/safety-gates.md` |
| 87 | 207 | Mission_BoomBots `*_Boom` pawns have Explosive Decay. | `docs/agent/solver-reference.md` |
| 88 | 208 | Burst Beam Ally Immune needs upgraded weapon IDs. | `docs/agent/solver-reference.md` |
| 89 | 209 | Titan Fist Dash needs upgraded weapon IDs. | `docs/agent/solver-reference.md` |
| 90 | 210 | Safety widening must be wide enough before dirty consent. | `docs/agent/safety-gates.md` |
| 91 | 211 | Mission preview mini-board hitboxes are wider than they look. | `docs/agent/live-runbook.md` |
| 92 | 212 | Installed reactor cores are not temporary cross-mech rentals. | `docs/agent/achievement-playbook.md` |
| 93 | 213 | Mountain-destruction objectives need explicit attention until scorer coverage is proven. | `docs/agent/solver-reference.md` |
| 94 | 214 | New Rust weapon IDs must refresh `known_types`. | `docs/agent/safety-gates.md` |
| 95 | 215 | Do not bypass soft-disables during safety widening. | `docs/agent/solver-reference.md` |
| 96 | 216 | Taurus/Artemis edge-push kills are v96 regression anchors. | `docs/agent/solver-reference.md` |
| 97 | 217 | Never double-click End Turn after an ambiguous transition. | `docs/agent/solver-reference.md` |
| 98 | 218 | `execute` is session-mutating; never include it in diagnostic fan-out. | `docs/agent/safety-gates.md` |
| 99 | 219 | Titan Fist Dash uses projectile-path AddCharge, not normal ground charge pathing. | `docs/agent/safety-gates.md` |
| 100 | 220 | Final Cave danger kills flyers. | `docs/agent/solver-reference.md` |
| 101 | 221 | Mission-end commits must push the current branch, never hard-coded main. | `docs/agent/solver-reference.md` |
| 102 | 222 | Timeline Lost pilot carry-forward is click/select UI, not drag setup. | `docs/agent/achievement-playbook.md` |
| 103 | 223 | Stable / guarding units must come from the live bridge, not static pawn stats. | `docs/agent/solver-reference.md` |
| 104 | 224 | Final-turn fire still kills mechs before rewards. | `docs/agent/safety-gates.md` |
| 105 | 225 | Active mission allies must be audited before squad actions cascade. | `docs/agent/safety-gates.md` |
| 106 | 226 | Post-pod pilot assignment is drag-and-drop. | `docs/agent/live-runbook.md` |
| 107 | 227 | Mission_Wind markers are not direct damage. | `docs/agent/safety-gates.md` |
| 108 | 228 | Status-only fuzzy desyncs must not cage weapons. | `docs/agent/safety-gates.md` |
| 109 | 229 | Replay snapshots must preserve Boosted status. | `docs/agent/safety-gates.md` |
| 110 | 230 | Kai Miller Boost is state-based, not one-shot. | `docs/agent/safety-gates.md` |
| 111 | 231 | Arachnid Psion death eggs appear during player actions. | `docs/agent/live-runbook.md` |
| 112 | 232 | Mission_Belt conveyors fire before Vek attacks. | `docs/agent/solver-reference.md` |
| 113 | 233 | Conveyors are tile-driven, not mission-id-driven. | `docs/agent/solver-reference.md` |
| 114 | 234 | Repair platforms do not overheal full-health units. | `docs/agent/solver-reference.md` |
| 115 | 235 | Delayed grid scalars are pending debt, not Grid Defense luck. | `docs/agent/safety-gates.md` |
| 116 | 236 | Safety widening keeps active weights and soft-disable masks. | `docs/agent/safety-gates.md` |
| 117 | 237 | Do not let Region Secured snapshots stall the live run. | `docs/agent/live-runbook.md` |
| 118 | 238 | Leap attacks resolve landing effects and break web. | `docs/agent/solver-reference.md` |
| 119 | 239 | Predicted mech status debt is tactical debt. | `docs/agent/safety-gates.md` |
| 120 | 240 | Aerial Bombs occupied transit smoke is not generic terrain damage. | `docs/agent/solver-reference.md` |
| 121 | 241 | Non-unique multi-HP bump damage can carry delayed grid debt. | `docs/agent/solver-reference.md` |
| 122 | 242 | Reviewed dirty candidates may need exact-rank execution after partial recovery. | `docs/agent/safety-gates.md` |
| 123 | 243 | Bridge-fired Aerial Bombs must not depend on global `Pawn` target-area context. | `docs/agent/safety-gates.md` |
| 124 | 244 | Scarab Leader artillery has adjacent push splash. | `docs/agent/safety-gates.md` |
| 125 | 245 | Synthetic no-belt boards must use `conveyor_dir=-1`. | `docs/agent/solver-reference.md` |
| 126 | 246 | Timeline-collapse plans are not dirty-consent plans except the last-turn final-cave resist Hail Mary. | `docs/agent/safety-gates.md` |
| 127 | 247 | Post-enemy audits are a persistent turn gate. | `docs/agent/safety-gates.md` |
| 128 | 248 | Pre-End-Turn threat coverage audit can hold the click. | `docs/agent/safety-gates.md` |
| 129 | 249 | Hard Rusting Hulks should prefer a third island unless Hive-ready. | `docs/agent/achievement-playbook.md` |
| 130 | 250 | Mission preview clicks must target the intended region or visible Start Mission text. | `docs/agent/live-runbook.md` |
| 131 | 251 | WebbEgg hatch uses `sPawn` fallback, not in-place mutation. | `docs/agent/safety-gates.md` |
| 132 | 252 | Mission_Wind requires live WindDir plus simulator v148+. | `docs/agent/achievement-playbook.md` |
| 133 | 253 | Aerial Bombs transit-smoke is a threat answer. | `docs/agent/safety-gates.md` |
| 134 | 254 | Landing on smoke extinguishes carried unit fire. | `docs/agent/solver-reference.md` |
| 135 | 255 | Reward-screen KIA / failed-objective text is authoritative. | `docs/agent/safety-gates.md` |
| 136 | 256 | Beetle charges push, and Bouncer edge recoil is harmless. | `docs/agent/solver-reference.md` |
| 137 | 257 | Unit-based bonus objectives must be declared in `data/mission_unit_objectives.json`. | `docs/agent/safety-gates.md` |
| 138 | 258 | Mission_Terraform Terraformer is a live fourth actor. | `docs/agent/safety-gates.md` |
| 139 | 259 | Mission_Terraform grassland is a custom-sprite objective, not terrain id. | `docs/agent/achievement-playbook.md` |
| 140 | 260 | Boss leader kills are unit-objective metadata, not just generic boss flavor. | `docs/agent/solver-reference.md` |
| 141 | 262 | Tumblebug live Lua ids are `Dung*`. | `docs/agent/safety-gates.md` |
| 142 | 264 | Tumblebug boulders are neutral explosive pawns. | `docs/agent/safety-gates.md` |
| 143 | 266 | Mission-start save lag is not post-mission stale bridge. | `docs/agent/live-runbook.md` |
| 144 | 268 | Soft-disable safety widening must show the emergency pass. | `docs/agent/safety-gates.md` |
| 145 | 270 | Effective mech max HP comes from saveData when bridge and save disagree. | `docs/agent/solver-reference.md` |
| 146 | 272 | `auto_turn` safety blocks must carry the full dirty frontier. | `docs/agent/safety-gates.md` |
| 147 | 274 | Time Pods are fragile under non-collecting contact. | `docs/agent/solver-reference.md` |
| 148 | 276 | Mission-panel clicks can commit the selected mission. | `docs/agent/live-runbook.md` |
| 149 | 278 | Mite objectives need active cleanup even on quiet turns. | `docs/agent/safety-gates.md` |
| 150 | 280 | Large Goo is a split-on-death boss, not a single kill. | `docs/agent/solver-reference.md` |
| 151 | 281 | Moved queued attackers preserve their original target offset. | `docs/agent/solver-reference.md` |
| 152 | 283 | Blitzkrieg Chain Attack setup should avoid protected-unit missions before Building Chain. | `docs/agent/safety-gates.md` |
| 152 | 285 | Bridge REPAIR must directly mutate HP/status. | `docs/agent/solver-reference.md` |
| 153 | 286 | Bridge REPAIR max HP needs the same fallback as state export. | `docs/agent/solver-reference.md` |
| 154 | 287 | Mission preview overlays can eat adjacent-region clicks. | `docs/agent/live-runbook.md` |
| 155 | 288 | Mission_Disposal gives you a controllable Disintegrator ally. | `docs/agent/solver-reference.md` |
| 156 | 289 | Boost Psion death clears visible Boosted immediately. | `docs/agent/solver-reference.md` |
| 157 | 290 | Disposal_Attack dissolves buildings in its acid cross. | `docs/agent/safety-gates.md` |
| 158 | 291 | Post-enemy audits wait for READY actors and delayed grid settlement. | `docs/agent/safety-gates.md` |
| 159 | 292 | Saved conveyor sprites are not always active belt environments. | `docs/agent/safety-gates.md` |
| 160 | 293 | Tumblebug Leader bridge ids are `DungBoss` / `DungAtkB`. | `docs/agent/safety-gates.md` |
| 161 | 294 | BombRock explosions are immediate under damage+push. | `docs/agent/solver-reference.md` |
| 162 | 295 | Weapon-ignited Forest becomes burning Ground immediately. | `docs/agent/safety-gates.md` |
| 163 | 297 | Threat audit credits lethal pre-attack fire. | `docs/agent/safety-gates.md` |
| 164 | 299 | Off-axis Artemis bridge shots are no-ops. | `docs/agent/solver-reference.md` |
| 165 | 301 | Pending-grid-debt probes must be mission-keyed, not just region/turn. | `docs/agent/solver-reference.md` |
| 166 | 303 | Positive player HP drift is harmless but should not hide damage misses. | `docs/agent/safety-gates.md` |
| 167 | 305 | ACID Storm acidifies newly spawned rocks immediately. | `docs/agent/safety-gates.md` |
| 168 | 307 | Repair does not clear ACID while ACID Storm is active. | `docs/agent/solver-reference.md` |
| 169 | 309 | Disposal teleporter tiles can move mechs during action verification. | `docs/agent/solver-reference.md` |
| 170 | 311 | Status checks are session commands too. | `docs/agent/live-runbook.md` |
| 171 | 312 | Rock Launcher side pushes outrun center Boom Bot decay. | `docs/agent/solver-reference.md` |
| 172 | 313 | Boom Bot post-enemy grid misses can come from newly moved non-queued enemies. | `docs/agent/safety-gates.md` |
| 173 | 314 | After dirty-consent auto_turn output anomalies, read before executing anything manually. | `docs/agent/safety-gates.md` |
| 174 | 316 | Chain Whip is pawn/building-chain damage with narrow terrain side effects. | `docs/agent/solver-reference.md` |
| 175 | 318 | Modeled upgraded weapon IDs must be known to the research gate. | `docs/agent/safety-gates.md` |
| 176 | 320 | Save `primary_power` is base weapon power, not upgrade suffix state. | `docs/agent/solver-reference.md` |
| 177 | 322 | Mosquito Leader is a shield-piercing instant kill. | `docs/agent/safety-gates.md` |
| 178 | 323 | Raw grapple probes beat stale bridge web fallback. | `docs/agent/safety-gates.md` |
| 179 | 324 | Perfect Strategy farming should avoid spawn-block objectives until objective scoring is explicit. | `docs/agent/achievement-playbook.md` |
| 180 | 325 | Mission preview clicks must be title-verified before starting. | `docs/agent/live-runbook.md` |
| 181 | 326 | Volatile Vek missions are disallowed for fire squads unless the objective is itself the target. | `docs/agent/safety-gates.md` |
| 182 | 327 | Avoid mission teleporter pads until move verification models them. | `docs/agent/safety-gates.md` |
| 183 | 328 | After a terminal-action `click_miss`, fresh-read before End Turn. | `docs/agent/safety-gates.md` |
| 184 | 329 | A visible `Start Mission` overlay is a live launch button. | `docs/agent/live-runbook.md` |
| 185 | 330 | `recommend_mission` has no achievement/tag flags. | `docs/agent/achievement-playbook.md` |
| 186 | 331 | Match `research_resolve --kind` to the queued entry. | `docs/agent/safety-gates.md` |
| 187 | 332 | Preview-revealed unit objectives must be mapped before launch. | `docs/agent/live-runbook.md` |
| 188 | 333 | Reviewed dirty consent can intentionally leave the audited ordinary-building hit. | `docs/agent/safety-gates.md` |
| 189 | 334 | Mech-damage-cap objectives are hard objective gates. | `docs/agent/achievement-playbook.md` |
| 190 | 335 | Verify Advanced Content by colored icons, not empty checkboxes. | `docs/agent/live-runbook.md` |
| 191 | 336 | Combat click plans must be visually calibrated in Codex Computer Use. | `docs/agent/live-runbook.md` |
| 192 | 337 | Never advance a dirty threat audit after a weapon `click_miss` desync. | `docs/agent/safety-gates.md` |
| 193 | 338 | Perfect Strategy avoids spawn-block objectives unless progress is hard-gated. | `docs/agent/achievement-playbook.md` |
| 194 | 339 | Perfect Strategy avoids kill-limit objectives unless kill count is hard-gated. | `docs/agent/safety-gates.md` |
| 195 | 340 | When rejecting a mission preview, do not click through its board overlay. | `docs/agent/live-runbook.md` |
| 196 | 341 | Perfect Strategy dirty consent must preserve bonus counters explicitly. | `docs/agent/safety-gates.md` |
| 197 | 342 | Frozen-building thaw objectives are counter objectives, not building safety. | `docs/agent/achievement-playbook.md` |
| 198 | 343 | Perfect Strategy treats tank-defense missions as fragile even with v147 safety. | `docs/agent/safety-gates.md` |
| 199 | 344 | Mission-end `unknown` phase after final enemy cleanup means inspect the reward screen. | `docs/agent/live-runbook.md` |
| 200 | 345 | Perfect Strategy avoids minimum-kill objectives unless kill progress is hard-gated. | `docs/agent/achievement-playbook.md` |
| 201 | 346 | Mid-mission `podReward` alone does not prove a Time Pod objective survived. | `docs/agent/live-runbook.md` |
| 202 | 347 | Pod desyncs are Perfect Strategy hard stops. | `docs/agent/safety-gates.md` |
| 203 | 348 | Destroy-unit objectives need final-turn safety, not just scoring. | `docs/agent/live-runbook.md` |
| 203 | 349 | Perfect Strategy avoids fire-tile counter missions until progress is hard-gated. | `docs/agent/live-runbook.md` |
| 204 | 350 | A live Time Pod on the final turn is not recovered. | `docs/agent/safety-gates.md` |
| 205 | 351 | `recommend_mission` takes profiles, not tags. | `docs/agent/live-runbook.md` |
| 206 | 352 | Use BSD/macOS-compatible file listing commands. | `docs/agent/live-runbook.md` |
| 207 | 353 | Solve recordings are rooted objects, not arrays. | `docs/agent/safety-gates.md` |
| 208 | 354 | `game_loop.py log` takes a positional message. | `docs/agent/live-runbook.md` |
| 209 | 355 | Mission preview overlays are sticky; don't click through them to compare neighbors. | `docs/agent/live-runbook.md` |
| 210 | 356 | `Mission_Tanks` v147 regression check. | `docs/agent/achievement-playbook.md` |
| 211 | 357 | Codex `spawn_agent` full-history forks cannot override type/model/reasoning. | `docs/agent/achievement-playbook.md` |
| 212 | 358 | `cargo test` accepts one positional name filter. | `docs/agent/solver-reference.md` |
| 213 | 359 | Python `MechAction` has no `weapon_id` constructor field. | `docs/agent/solver-reference.md` |
| 214 | 360 | Refresh Computer Use state after long terminal work. | `docs/agent/solver-reference.md` |
| 215 | 361 | Post-loss squad-screen Back exits to main menu. | `docs/agent/achievement-playbook.md` |
| 216 | 362 | Mac save/config path is `IntoTheBreach`, not `Subset Games/Into The Breach`. | `docs/agent/live-runbook.md` |
| 217 | 363 | Own-mech research queue entries are `mech_weapon`, not `behavior_novelty`. | `docs/agent/safety-gates.md` |
| 218 | 364 | `mission_end` has no `--perfect` flag. | `docs/agent/achievement-playbook.md` |
| 219 | 365 | Full Rust regression is a corpus sweep, not a quick smoke test. | `docs/agent/safety-gates.md` |
| 220 | 366 | Prime Flamethrower target-tile fire is flight-sensitive. | `docs/agent/achievement-playbook.md` |
| 221 | 367 | Fire weapons do not create burning water tiles. | `docs/agent/achievement-playbook.md` |
| 219 | 368 | If Computer Use rejects a click after a fresh app-name state read, refresh by bundle id. | `docs/agent/live-runbook.md` |
| 220 | 369 | Verify Corporate HQ is truly active before skipping side missions. | `docs/agent/achievement-playbook.md` |
| 221 | 370 | Mission_Dam `Dam_Pawn` can be a stale behavior-novelty queue item. | `docs/agent/safety-gates.md` |
| 222 | 371 | Close stale subagents before spawning during live play. | `docs/agent/achievement-playbook.md` |
| 223 | 372 | Move-only fuzzy detections can soft-disable `Unknown`; treat as diagnostic noise. | `docs/agent/safety-gates.md` |
| 224 | 373 | Island-selection clicks commit the next island immediately. | `docs/agent/live-runbook.md` |
| 225 | 374 | Quote `game_loop.py log` messages as one shell argument. | `docs/agent/safety-gates.md` |
| 226 | 375 | Empty survival turns can be valid End Turn states. | `docs/agent/live-runbook.md` |
| 227 | 376 | Quote shell patterns that contain backticks. | `docs/agent/live-runbook.md` |
| 228 | 377 | Perfect Strategy avoids Mite counter missions unless progress is hard-gated. | `docs/agent/achievement-playbook.md` |
| 229 | 378 | Status-only mid-action desyncs need a fresh board, not stale-plan panic. | `docs/agent/safety-gates.md` |
| 230 | 379 | Research target coordinates must be visibly confirmed after any miss. | `docs/agent/safety-gates.md` |
| 231 | 380 | Post-enemy blocks after partial re-solves may compare against a stale predicted outcome. | `docs/agent/safety-gates.md` |
| 232 | 381 | Spawn-block objectives are mandatory, not generic spawn hygiene. | `docs/agent/live-runbook.md` |
| 233 | 382 | Bouncer threat audits must include self-bounce collateral. | `docs/agent/safety-gates.md` |
| 234 | 383 | Mission preview clicks can launch; return to map before scouting another region. | `docs/agent/live-runbook.md` |
| 235 | 384 | Find helper paths before opening guessed files during live play. | `docs/agent/live-runbook.md` |
| 236 | 385 | Final-turn Mite objectives need pre-action proof, not post-action regret. | `docs/agent/safety-gates.md` |
| 237 | 386 | Terraform grassland objectives are counter objectives, not just unit-defense. | `docs/agent/safety-gates.md` |
| 238 | 387 | Island-select helper coords are only for the four-island screen. | `docs/agent/live-runbook.md` |
| 239 | 388 | Kill-N objectives are final-turn hard gates, not scoring hints. | `docs/agent/achievement-playbook.md` |
| 240 | 389 | Mission_Force mountain objectives are counter objectives. | `docs/agent/achievement-playbook.md` |
| 241 | 390 | Mission-preview scouting must have a no-launch escape plan. | `docs/agent/live-runbook.md` |
| 242 | 391 | Attack-phase landings can collect Time Pods. | `docs/agent/safety-gates.md` |
| 243 | 392 | Regression scripts can wedge; bound them before live clicks. | `docs/agent/safety-gates.md` |
| 244 | 393 | Burrower missing-after-damage diffs are known conservative board drift. | `docs/agent/achievement-playbook.md` |
| 245 | 394 | Block-spawn objectives are hard gates for no-failed-objective achievements. | `docs/agent/achievement-playbook.md` |
| 246 | 395 | Aerial Bombs over frozen thaw-objective buildings costs deferred grid. | `docs/agent/safety-gates.md` |
| 247 | 396 | Minor Vek kills are not mission.KilledVek. | `docs/agent/achievement-playbook.md` |
| 248 | 397 | Post-enemy audits are exact-turn only. | `docs/agent/safety-gates.md` |
| 249 | 398 | Vek Mites make Repair non-noop even at full HP. | `docs/agent/achievement-playbook.md` |
| 250 | 399 | Stale non-egg web ownership must be repaired before solving. | `docs/agent/achievement-playbook.md` |
| 251 | 400 | Firefly Leader attacks are paired projectiles. | `docs/agent/achievement-playbook.md` |
| 252 | 401 | Mission_Dam's dam is a destroy-objective unit, not optional scenery. | `docs/agent/achievement-playbook.md` |
| 253 | 402 | Science_Swap / Teleporter is cardinal-line only. | `docs/agent/achievement-playbook.md` |
| 254 | 403 | Save pawn `offset` is not a mech loadout offset. | `docs/agent/safety-gates.md` |
| 255 | 404 | FIRE weapon status consumes Sand/Forest into burning Ground. | `docs/agent/achievement-playbook.md` |
| 256 | 405 | Pinnacle FACTION_BOTS do not receive Psion auras. | `docs/agent/achievement-playbook.md` |
| 257 | 406 | Threat audit must account for earlier Bouncer self-bump kills. | `docs/agent/safety-gates.md` |
| 258 | 407 | Threat audit must account for fire-triggered Soldier Psion HP teardown. | `docs/agent/safety-gates.md` |
| 259 | 408 | Threat audit must account for Ice Storm freeze tiles. | `docs/agent/safety-gates.md` |
| 260 | 409 | Threat audit must account for earlier enemy pushes that move a later attacker. | `docs/agent/safety-gates.md` |
| 261 | 410 | Quote decision-log messages that contain punctuation. | `docs/agent/live-runbook.md` |
| 262 | 411 | Kill-limit objective failure is dirty-consentable only outside perfect-objective hunts. | `docs/agent/safety-gates.md` |
| 263 | 412 | Mid-combat save/restart can move effective mech stats to `undoSave.lua`. | `docs/agent/safety-gates.md` |
| 264 | 413 | Dirty consent is consumed only when execution can proceed. | `docs/agent/safety-gates.md` |
| 265 | 414 | Do not run `mission_end` after a map read has auto-advanced the session. | `docs/agent/live-runbook.md` |
| 266 | 415 | Close mission previews before scouting another region. | `docs/agent/live-runbook.md` |
| 267 | 416 | Boosted Flame Thrower damage is conditional, not base damage. | `docs/agent/achievement-playbook.md` |
| 268 | 498 | Fire status can sit on Grid Building tiles. | `docs/agent/safety-gates.md` |
| 269 | 500 | Duplicate mission-unit segments share web state. | `docs/agent/achievement-playbook.md` |
| 270 | 502 | FIRE weapon tile status can sit on intact Mountains. | `docs/agent/safety-gates.md` |
| 271 | 504 | Science Swap breaks web on moved targets. | `docs/agent/achievement-playbook.md` |
| 272 | 506 | Tri-Rocket killed ACID corpses resolve from their pushed destination. | `docs/agent/solver-reference.md` |
| 273 | 508 | Diagnosis queue checks are session-lock commands even during file triage. | `docs/agent/safety-gates.md` |
| 274 | 510 | Seismic Capacitor crack effects damage adjacent Mountains. | `docs/agent/solver-reference.md` |
| 275 | 512 | Threat audit must credit earlier enemy projectiles. | `docs/agent/safety-gates.md` |
| 276 | 514 | Commit and push every concrete live-loop fix before continuing. | `docs/agent/safety-gates.md` |
| 277 | 516 | Tri-Rocket killed adjacent targets corpse-bump center blockers. | `docs/agent/solver-reference.md` |
| 278 | 518 | Tri-Rocket terrain-killed landings do not leave vacated corpse-bumps. | `docs/agent/solver-reference.md` |
| 279 | 520 | VIP trucks move via a weapon skill, not pawn MoveSpeed. | `docs/agent/solver-reference.md` |
| 280 | 522 | Stage helper definitions with their call sites. | `docs/agent/live-runbook.md` |
| 281 | 524 | Protected-objective dirty loss needs an explicit stress flag. | `docs/agent/safety-gates.md` |
| 282 | 526 | Tri-Rocket cannot select an adjacent center target. | `docs/agent/solver-reference.md` |
| 283 | 528 | Bridge queued targets must trust live `GetQueuedShot()` after retarget effects. | `docs/agent/safety-gates.md` |
| 284 | 530 | Tri-Rocket center BombRocks collide forward instead of side-blasting. | `docs/agent/solver-reference.md` |
| 285 | 532 | Cataclysm powered weapons need save overlays before solving. | `docs/agent/achievement-playbook.md` |
| 286 | 534 | Live targeted tiles can disambiguate save-stale flip targets. | `docs/agent/safety-gates.md` |
| 287 | 536 | Mission_Wind raw WindDir needs solver-coordinate conversion. | `docs/agent/solver-reference.md` |
| 288 | 537 | Hydraulic Lifter bridge execution must mirror Boost use. | `docs/agent/solver-reference.md` |
| 289 | 539 | Enemy queued-target origins survive displacement and flips. | `docs/agent/solver-reference.md` |
| 290 | 541 | Hydraulic Lifter forest landings ignite surviving targets. | `docs/agent/solver-reference.md` |
| 291 | 543 | Objective-loss dirty lines need the broad stress flag. | `docs/agent/safety-gates.md` |
| 292 | 545 | Quote live-loop log messages as one shell argument. | `docs/agent/live-runbook.md` |
| 293 | 547 | Objective-loss consent does not waive the threat audit. | `docs/agent/safety-gates.md` |
| 294 | 549 | Untouchable treats mech HP warnings as hard blocks. | `docs/agent/safety-gates.md` |
| 295 | 551 | Island mission previews have a large Start Mission hitbox. | `docs/agent/live-runbook.md` |
| 296 | 553 | Satellite launch blasts spare flying pawns. | `docs/agent/safety-gates.md` |
| 297 | 555 | `tests/test_env_danger.py` is a standalone script, not a pytest module. | `docs/agent/achievement-playbook.md` |
| 298 | 557 | Do not let a silent cargo regression block a live run indefinitely. | `docs/agent/live-runbook.md` |
| 299 | 559 | Rust source mtime is enough to stale the installed wheel. | `docs/agent/achievement-playbook.md` |
| 300 | 561 | Git gc warnings after commit are not the same as commit failure. | `docs/agent/achievement-playbook.md` |
| 301 | 563 | Untouchable dirty consent needs grid buffer, not just clean mech HP. | `docs/agent/safety-gates.md` |
| 302 | 565 | Untouchable dirty consent must distrust unproven kill-push friendly-fire lines. | `docs/agent/safety-gates.md` |
| 303 | 567 | Avoid Pinnacle frozen-building missions for active Untouchable attempts. | `docs/agent/safety-gates.md` |
| 304 | 569 | Avoid webber-heavy islands and dam maps for active Untouchable. | `docs/agent/safety-gates.md` |
| 305 | 571 | Cargo test takes one filter argument. | `docs/agent/live-runbook.md` |
| 306 | 573 | Conveyor sprite directions are engine directions. | `docs/agent/achievement-playbook.md` |
| 307 | 575 | Final-turn pod abandonment is an objective-loss dirty kind. | `docs/agent/safety-gates.md` |
| 308 | 577 | Avoid Old Earth mine / mite missions for active Untouchable. | `docs/agent/safety-gates.md` |
| 309 | 579 | Avoid Bad Repairs for active Untouchable. | `docs/agent/live-runbook.md` |
| 310 | 581 | First-island comparison clicks can commit the island immediately. | `docs/agent/live-runbook.md` |
| 311 | 583 | Untouchable may override solver choices with projected no-HP manual lines. | `docs/agent/safety-gates.md` |
| 312 | 585 | Avoid Defend the Tanks for active Frozen Titans Untouchable unless every alternative is worse. | `docs/agent/safety-gates.md` |
| 313 | 586 | Defensive Shields can absorb Cryo instead of freezing the target. | `docs/agent/achievement-playbook.md` |
| 314 | 587 | If Cargo/maturin sleeps before spawning rustc, switch to a clean target dir. | `docs/agent/live-runbook.md` |
| 315 | 589 | One-off bridge helpers must mirror the harness imports. | `docs/agent/achievement-playbook.md` |
| 316 | 591 | Read output must expose immobilizing mech statuses during Untouchable. | `docs/agent/safety-gates.md` |
| 317 | 593 | Untouchable must avoid mech damage events, not just HP drops. | `docs/agent/achievement-playbook.md` |
| 318 | 595 | Spartan Shield is not a Burnbug/Gastropod attack cancel. | `docs/agent/live-runbook.md` |
| 319 | 596 | Quote decision-log messages that contain shell metacharacters. | `docs/agent/safety-gates.md` |
| 320 | 597 | Tier-1 click-miss fuzzies are stop signs, even with a clean threat audit. | `docs/agent/safety-gates.md` |
| 321 | 598 | Rollback triage still obeys the session lock. | `docs/agent/live-runbook.md` |
| 322 | 599 | Webbed Leap Mech cannot fire Hydraulic Legs. | `docs/agent/solver-reference.md` |
| 323 | 600 | Hydraulic Legs target area is cardinal-line only. | `docs/agent/solver-reference.md` |
| 324 | 601 | Patch Leap_Attack target areas in the bridge context. | `docs/agent/solver-reference.md` |
| 325 | 602 | Do not click through an open mission-preview board. | `docs/agent/live-runbook.md` |
| 326 | 603 | Viscera Nanobots heal after attack kills, including self-damage recoil. | `docs/agent/solver-reference.md` |
| 327 | 604 | Acid Projector pushes already-ACID targets unless the endpoint no-ops. | `docs/agent/solver-reference.md` |
| 328 | 605 | Teleporter pad pairs are mission-scoped. | `docs/agent/solver-reference.md` |
| 329 | 606 | Viscera Nanobots do not heal bump-only kills. | `docs/agent/solver-reference.md` |
| 330 | 607 | Teleporter pad move verifies need a short settle reread. | `docs/agent/safety-gates.md` |
| 331 | 608 | Hydraulic Legs landing effects happen after recoil. | `docs/agent/solver-reference.md` |
| 332 | 609 | Hydraulic Legs kill-pushes move ACID corpse pools. | `docs/agent/solver-reference.md` |
| 333 | 610 | Instant-killed web sources still release grapples. | `docs/agent/solver-reference.md` |
| 334 | 611 | Replay `None` actions as bridge skips. | `docs/agent/live-runbook.md` |
| 335 | 612 | ACID death pools on Sand become Ground; Unstable pushback bump kills can heal. | `docs/agent/solver-reference.md` |
| 336 | 613 | Parallel file searches must not mention `game_loop.py`. | `docs/agent/live-runbook.md` |
| 337 | 614 | Occupied cracked Ground does not collapse from pawn-only weapon damage. | `docs/agent/solver-reference.md` |
| 338 | 615 | Partial re-solves must replace the post-enemy prediction record. | `docs/agent/safety-gates.md` |
| 339 | 616 | Hydraulic Legs self-damage can collapse occupied cracked Ground. | `docs/agent/solver-reference.md` |
| 340 | 617 | Unstable Cannon dead recoil still bumps live blockers before Nanobots heal. | `docs/agent/solver-reference.md` |
| 341 | 618 | Nanobots cannot revive a mech that fell into a fresh chasm. | `docs/agent/solver-reference.md` |
| 342 | 619 | Bump damage does not open occupied cracked Ground. | `docs/agent/solver-reference.md` |
| 343 | 620 | Unstable Cannon direct kills do not leave corpse ACID pools. | `docs/agent/solver-reference.md` |
| 344 | 621 | Kill-count bonus failure can be dirty-consentable for non-perfect achievement runs. | `docs/agent/safety-gates.md` |
| 345 | 622 | Hydraulic Legs Nanobots revive before landing tile fire/ACID pickup. | `docs/agent/solver-reference.md` |
| 346 | 623 | Nanobots revive clears carried negative statuses before landing reapplication. | `docs/agent/solver-reference.md` |
| 347 | 624 | Unstable Cannon edge recoil does not self-bump. | `docs/agent/solver-reference.md` |
| 348 | 625 | Dam flood extinguishes burning flooded tiles. | `docs/agent/solver-reference.md` |
| 349 | 626 | Open mission-preview boards swallow far-away map clicks. | `docs/agent/live-runbook.md` |
| 350 | 627 | Unstable Cannon killed targets can corpse-bump live blockers. | `docs/agent/solver-reference.md` |
| 351 | 628 | Occupied ice absorbs weapon/bump tile breaks. | `docs/agent/solver-reference.md` |
| 352 | 629 | Unstable Cannon ice-origin flooding is not universal. | `docs/agent/solver-reference.md` |
| 353 | 630 | Hydraulic Legs breaks occupied Ice for grounded targets, not flying targets. | `docs/agent/solver-reference.md` |
| 354 | 631 | Blocked Hydraulic Legs pushes leave occupied Ice intact. | `docs/agent/solver-reference.md` |
| 355 | 632 | Do not click anywhere covered by a mission-preview board, even outside the text panel. | `docs/agent/live-runbook.md` |
| 356 | 633 | Hydraulic Legs friendly pushes can enter existing dead-unit tiles. | `docs/agent/solver-reference.md` |
| 357 | 634 | Live broad-regression hangs can yield to focused proof. | `docs/agent/solver-reference.md` |
| 358 | 635 | Hydraulic Legs has no pass-over transit damage. | `docs/agent/solver-reference.md` |
| 359 | 636 | Hydraulic Legs Nanobots cap at Hazardous engine HP; Unstable direct kills can heal to save max. | `docs/agent/achievement-playbook.md` |
| 360 | 637 | Hydraulic Legs BombRock blasts exclude the landing Leap Mech. | `docs/agent/solver-reference.md` |
| 361 | 638 | Unstable Cannon direct edge pushes do not edge-bump. | `docs/agent/solver-reference.md` |
| 362 | 639 | Hydraulic Legs terrain-push kills can heal and leave origin Ice intact. | `docs/agent/solver-reference.md` |
| 363 | 640 | Powered Hazardous weapon IDs must be modeled, not stripped to base. | `docs/agent/safety-gates.md` |
| 364 | 641 | Unstable Cannon Nanobots heals from zero and preserves carried statuses. | `docs/agent/solver-reference.md` |
| 365 | 642 | Acid Projector can push live enemies into dead enemy wrecks. | `docs/agent/solver-reference.md` |
| 366 | 643 | Offline Steam can delay achievement sync. | `docs/agent/achievement-playbook.md` |
| 367 | 644 | Setup verifier screenshots must be visibly game-focused. | `docs/agent/live-runbook.md` |
| 368 | 645 | Threat audit must credit active conveyor pre-shift. | `docs/agent/safety-gates.md` |
| 369 | 647 | Live `game_loop.py log` commands need literal quoting even for short notes. | `docs/agent/live-runbook.md` |
| 370 | 649 | Hold the Line turns need a spawn-banking precheck before `auto_turn`. | `docs/agent/safety-gates.md` |
| 371 | 651 | Hold the Line precheck must happen after enemy-phase waits too. | `docs/agent/live-runbook.md` |
| 372 | 653 | Log-command quoting is mandatory even after a snapshot. | `docs/agent/live-runbook.md` |
| 373 | 655 | Offline triage scripts should import only what they use. | `docs/agent/safety-gates.md` |
| 374 | 657 | Keep live-turn searches out of `recordings/` unless the corpus is the target. | `docs/agent/live-runbook.md` |
| 375 | 659 | Inspect recording keys before ad-hoc JSON summarizers. | `docs/agent/safety-gates.md` |
| 376 | 661 | Confirm Rust source filenames before targeted `rg`. | `docs/agent/live-runbook.md` |
| 377 | 663 | Destroyed objective building ruins block Grappling Hook target scans. | `docs/agent/safety-gates.md` |
| 378 | 665 | Cargo test accepts one filter string. | `docs/agent/live-runbook.md` |
| 379 | 667 | Inspect solve-record action nesting before replay helpers. | `docs/agent/achievement-playbook.md` |
| 380 | 669 | Repo-root `rg .` counts as a broad live-turn search. | `docs/agent/safety-gates.md` |
| 381 | 671 | Probe bridge JSON fields before ad-hoc `jq` tile filters. | `docs/agent/live-runbook.md` |
| 382 | 673 | Do not trust shallow clean lookahead to justify penultimate-turn grid loss at 2 grid. | `docs/agent/safety-gates.md` |
| 383 | 675 | Hold the Line enemy-phase waits must be read-only. | `docs/agent/live-runbook.md` |
| 384 | 677 | Live-turn `rg rust_solver` must exclude build artifacts. | `docs/agent/live-runbook.md` |
| 385 | 679 | Live-turn repo-wide `rg` must exclude generated run corpora. | `docs/agent/live-runbook.md` |
| 386 | 681 | Live UI-coordinate searches should stay out of bulky data folders. | `docs/agent/live-runbook.md` |
| 387 | 683 | Hold the Line HQ and boss deployments use the same read-only wait. | `docs/agent/live-runbook.md` |
| 388 | 685 | Hold the Line has an explicit manual-geometry override. | `docs/agent/achievement-playbook.md` |
| 389 | 687 | HQ leader survival is an objective-loss tradeoff, not automatic timeline loss. | `docs/agent/safety-gates.md` |
| 390 | 689 | Distant Friends beacon pickup is visual-authoritative. | `docs/agent/achievement-playbook.md` |
| 391 | 691 | Resume before End Turn must re-read the bridge. | `docs/agent/safety-gates.md` |
| 392 | 693 | Mech Specialist tolerates failed leader bonuses. | `docs/agent/achievement-playbook.md` |
| 393 | 695 | Triple Ice can close Mech Specialist and Flight Specialist together. | `docs/agent/achievement-playbook.md` |
| 394 | 697 | Computer Use fallback End Turn clicks need refocus and fresh reads. | `docs/agent/live-runbook.md` |
| 395 | 699 | Change the Odds is post-island shop math, not a victory requirement. | `docs/agent/achievement-playbook.md` |
| 396 | 701 | Class Specialist is proven with three Prime mechs. | `docs/agent/achievement-playbook.md` |
| 397 | 703 | Rock Launcher empty rock spawns preserve Forest. | `docs/agent/solver-reference.md` |
| 398 | 705 | Enemy-phase pre-attack deaths clear before later enemy-phase steps. | `docs/agent/solver-reference.md` |
| 399 | 707 | Do not raw-click unsupported Control Shot recoveries. | `docs/agent/safety-gates.md` |
| 400 | 709 | Spawned Arachnoid Bite killed targets can corpse-bump live blockers. | `docs/agent/solver-reference.md` |
