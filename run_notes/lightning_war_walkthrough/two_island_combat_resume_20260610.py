import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.lightning_war_fast_walkthrough import (
    build_parser,
    clear_mission_result_to_island_map,
    run_current_mission_from_island_map,
    solve_execute_and_end_turn,
)


mission_index = int(sys.argv[1]) if len(sys.argv) > 1 else 2
start_turn_index = int(sys.argv[2]) if len(sys.argv) > 2 else 2
stop_before = int(sys.argv[3]) if len(sys.argv) > 3 else 12

args = build_parser().parse_args(
    [
        "--full-mission",
        "--continue-after-island",
        "--post-end-turn-wait-seconds",
        "2.0",
        "--post-end-turn-max-wait-seconds",
        "45",
        "--result-screenshot-cadence",
        "1.0",
        "--terminal-visual-settle-seconds",
        "3.0",
        "--opening-enemy-wait-seconds",
        "8.0",
        "--opening-enemy-max-wait-seconds",
        "35.0",
        "--deploy-ready-wait-seconds",
        "1.0",
        "--preview-settle-seconds",
        "1.0",
        "--max-mission-turns",
        "7",
        "--time-limit",
        "30",
    ]
)

timer_start = time.perf_counter()
missions = []
transitions = []

turns = []
for turn_index in range(start_turn_index, args.max_mission_turns + 1):
    turn_record = solve_execute_and_end_turn(
        turn_index=turn_index,
        timer_start=timer_start,
        args=args,
    )
    turns.append(turn_record)
    if turn_record["post_end_turn"].get("status") != "PLAYER_TURN_READY":
        break
else:
    print(
        json.dumps(
            {
                "status": "STOPPED",
                "reason": "max_turns_current_combat",
                "mission_index": mission_index,
                "turns": turns,
            },
            indent=2,
            default=str,
        )
    )
    raise SystemExit(0)

missions.append(
    {
        "status": "OK",
        "reason": "terminal_or_clear_after_end_turn",
        "mission_index": mission_index,
        "terminal_turn_index": turns[-1]["turn_index"],
        "turns": turns,
    }
)

transition = clear_mission_result_to_island_map(
    mission_index=mission_index,
    timer_start=timer_start,
    continue_after_island=True,
)
transitions.append(transition)
preview_already_open = transition.get("status") == "MISSION_PREVIEW_OPENED"

if not preview_already_open:
    print(
        json.dumps(
            {
                "status": "STOPPED",
                "reason": "transition",
                "mission_index": mission_index,
                "transition_status": transition.get("status"),
                "missions": missions,
                "transitions": transitions,
            },
            indent=2,
            default=str,
        )
    )
    raise SystemExit(0)

for next_mission_index in range(mission_index + 1, stop_before):
    mission = run_current_mission_from_island_map(
        mission_index=next_mission_index,
        timer_start=timer_start,
        args=args,
        preview_already_open=preview_already_open,
    )
    missions.append(mission)
    if mission.get("status") not in {"OK", "STOPPED_AFTER_PAUSE"}:
        print(
            json.dumps(
                {
                    "status": "STOPPED",
                    "reason": "mission",
                    "mission_index": next_mission_index,
                    "missions": missions,
                    "transitions": transitions,
                },
                indent=2,
                default=str,
            )
        )
        break

    transition = clear_mission_result_to_island_map(
        mission_index=next_mission_index,
        timer_start=timer_start,
        continue_after_island=True,
    )
    transitions.append(transition)
    if transition.get("status") == "MISSION_PREVIEW_OPENED":
        preview_already_open = True
        continue

    print(
        json.dumps(
            {
                "status": "STOPPED",
                "reason": "transition",
                "mission_index": next_mission_index,
                "transition_status": transition.get("status"),
                "missions": missions,
                "transitions": transitions,
            },
            indent=2,
            default=str,
        )
    )
    break
else:
    print(
        json.dumps(
            {
                "status": "MAX_MISSIONS_REACHED",
                "missions": missions,
                "transitions": transitions,
            },
            indent=2,
            default=str,
        )
    )
