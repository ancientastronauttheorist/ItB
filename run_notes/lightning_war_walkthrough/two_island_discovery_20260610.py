import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.lightning_war_fast_walkthrough import build_parser, run_from_main_menu
args = build_parser().parse_args([
    '--full-mission',
    '--island-loop',
    '--continue-after-island',
    '--post-end-turn-wait-seconds','2.0',
    '--post-end-turn-max-wait-seconds','45',
    '--result-screenshot-cadence','1.0',
    '--terminal-visual-settle-seconds','3.0',
    '--opening-enemy-wait-seconds','8.0',
    '--opening-enemy-max-wait-seconds','35.0',
    '--deploy-ready-wait-seconds','1.0',
    '--preview-settle-seconds','1.0',
    '--max-mission-turns','7',
    '--max-island-missions','10',
    '--time-limit','30',
])
result = run_from_main_menu(args)
print('---TWO_ISLAND_DISCOVERY_RESULT---')
print(json.dumps(result, indent=2, default=str))
