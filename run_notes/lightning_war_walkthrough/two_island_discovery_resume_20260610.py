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
)


start_mission = int(sys.argv[1]) if len(sys.argv) > 1 else 5
stop_before = int(sys.argv[2]) if len(sys.argv) > 2 else 12

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
preview_already_open = False

for mission_index in range(start_mission, stop_before):
    mission = run_current_mission_from_island_map(
        mission_index=mission_index,
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
                    "mission_index": mission_index,
                    "missions": missions,
                    "transitions": transitions,
                },
                indent=2,
                default=str,
            )
        )
        break

    transition = clear_mission_result_to_island_map(
        mission_index=mission_index,
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
                "mission_index": mission_index,
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
