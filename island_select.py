#!/usr/bin/env python3
"""Randomly select an island for the next Into the Breach run.

Usage:
    python3 island_select.py          # Pick a random island
    python3 island_select.py --all    # Show all islands with approximate positions

Into the Breach has 4 corporate islands. Equal coverage across runs ensures
the bot encounters diverse environments and Vek types, improving solver
robustness and achievement coverage.

Islands:
    Archive Inc       — upper-left   (temperate: forests, water, mountains)
    R.S.T. Corporation — lower-left  (desert: sand, smoke, fire)
    Pinnacle Robotics  — upper-right (ice: frozen tiles, ice storms)
    Detritus Disposal  — right       (acid: A.C.I.D. pools, conveyor belts)
"""

import random
import sys

ISLANDS = {
    "archive": {
        "name": "Archive Inc",
        "region": "upper-left",
        "terrain": "temperate (forests, water, mountains)",
        "hazards": "air support, tidal waves, mines",
    },
    "rst": {
        "name": "R.S.T. Corporation",
        "region": "lower-left",
        "terrain": "desert (sand, smoke, fire)",
        "hazards": "lightning storms, air strikes, sandstorms",
    },
    "pinnacle": {
        "name": "Pinnacle Robotics",
        "region": "upper-right",
        "terrain": "ice (frozen tiles, cracking ice)",
        "hazards": "ice storms, conveyor belts, terraformer",
    },
    "detritus": {
        "name": "Detritus Disposal",
        "region": "right",
        "terrain": "acid (A.C.I.D. pools, conveyor belts)",
        "hazards": "acid rain, trash compactors, conveyor belts",
    },
}


def main():
    if "--all" in sys.argv:
        for key, info in ISLANDS.items():
            print(f"  {info['name']:25s} ({info['region']:12s}) — {info['terrain']}")
        return

    choice = random.choice(list(ISLANDS.keys()))
    info = ISLANDS[choice]
    print(f"{choice}")
    print(f"  Island: {info['name']}")
    print(f"  Region: {info['region']} area of world map")
    print(f"  Terrain: {info['terrain']}")
    print(f"  Hazards: {info['hazards']}")


if __name__ == "__main__":
    main()
