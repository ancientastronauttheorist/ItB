# Agent Docs

The top-level `AGENTS.md` is now the compact field guide. These focused files hold the detailed material that used to make `AGENTS.md` too heavy to scan during live play.

- `live-runbook.md` - phase flow, command reference, UI/click rules, session locking, and live shell/search hygiene.
- `safety-gates.md` - research gates, diagnosis loop, investigations, dirty-plan consent, post-enemy blocks, and threat audits.
- `solver-reference.md` - architecture, Rust build/test discipline, core mechanics, simulator rules, bridge/parser rules, and weapon case law.
- `achievement-playbook.md` - run setup, achievement targeting, shop priorities, and named-achievement exceptions.
- `lightning-war-autonomous-speedrun.md` - design plan for a pause-safe Python
  speedrun conductor, telemetry, screenshots, restart policy, and AE-off
  Lightning War attempts.
- `lightning-war-runner.md` - implemented baseline/speed runner commands,
  assumptions, telemetry, and recovery result meanings.
- `lightning-war-progress-economy.md` - control philosophy for maximizing
  verified Lightning War progress per in-game timer second.
- `rule-index.md` - historical rule-number lookup table pointing to the focused doc for each rule.
- `legacy-full-guide.md` - verbatim snapshot of the pre-cleanup `AGENTS.md` for audit/recovery.

When adding a new guard, update the narrowest focused file first. Touch `AGENTS.md` only when the rule changes the global live-loop contract every agent must load immediately.
