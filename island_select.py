#!/usr/bin/env python3
"""Select an island for the next Into the Breach run.

Usage:
    python3 island_select.py          # Pick a random island
    python3 island_select.py --all    # Show all islands with approximate positions
    python3 island_select.py --island archive
    python3 island_select.py --lightning-war --completed archive

Into the Breach has 4 corporate islands. Equal coverage across runs ensures
the bot encounters diverse environments and Vek types, improving solver
robustness and achievement coverage.

Islands:
    Archive Inc       — upper-left   (temperate: forests, water, mountains)
    R.S.T. Corporation — lower-left  (desert: sand, smoke, fire)
    Pinnacle Robotics  — upper-right (ice: frozen tiles, ice storms)
    Detritus Disposal  — right       (acid: A.C.I.D. pools, conveyor belts)
"""

import argparse
import random

ISLANDS = {
    "archive": {
        "name": "Archive Inc",
        "region": "upper-left",
        "mcp": (430, 320),
        "visual": "green/forested island",
        "terrain": "temperate (forests, water, mountains)",
        "hazards": "air support, tidal waves, mines",
    },
    "rst": {
        "name": "R.S.T. Corporation",
        "region": "center-left",
        "mcp": (560, 540),
        "visual": "brown/desert island with hole",
        "terrain": "desert (sand, smoke, fire)",
        "hazards": "lightning storms, cataclysm, sandstorms",
    },
    "pinnacle": {
        "name": "Pinnacle Robotics",
        "region": "center-right",
        "mcp": (850, 400),
        "visual": "white/icy island",
        "terrain": "ice (frozen tiles, cracking ice)",
        "hazards": "ice storms, cryo mines, thawing enemies",
    },
    "detritus": {
        "name": "Detritus Disposal",
        "region": "lower-right",
        "mcp": (1060, 580),
        "visual": "dark/rocky island with green circuits",
        "terrain": "acid (A.C.I.D. pools, conveyor belts)",
        "hazards": "conveyor belts, A.C.I.D. pools, teleporters",
    },
}


def _print_island(key: str) -> None:
    info = ISLANDS[key]
    print(f"{key}")
    print(f"  Island: {info['name']}")
    print(f"  Click: MCP ({info['mcp'][0]}, {info['mcp'][1]})")
    print(f"  Visual: {info['visual']}, {info['region']} area")
    print(f"  Terrain: {info['terrain']}")
    print(f"  Hazards: {info['hazards']}")


def _normalize_completed(values: list[str]) -> set[str]:
    completed: set[str] = set()
    aliases = {
        "archive inc": "archive",
        "archive": "archive",
        "r.s.t.": "rst",
        "r.s.t": "rst",
        "r.s.t. corporation": "rst",
        "rst": "rst",
        "pinnacle robotics": "pinnacle",
        "pinnacle": "pinnacle",
        "detritus disposal": "detritus",
        "detritus": "detritus",
    }
    for value in values:
        for part in value.split(","):
            key = part.strip().lower()
            if not key:
                continue
            completed.add(aliases.get(key, key))
    return completed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true",
                        help="Show every island coordinate")
    parser.add_argument("--island", choices=sorted(ISLANDS),
                        help="Print a specific island coordinate")
    parser.add_argument("--lightning-war", action="store_true",
                        help="Prefer Archive, then R.S.T., for Blitzkrieg speed")
    parser.add_argument("--completed", nargs="*", default=[],
                        help="Completed island keys/names to skip")
    args = parser.parse_args()

    if args.all:
        for key, info in ISLANDS.items():
            print(f"  {info['name']:25s} MCP {info['mcp']}  ({info['region']:12s}) — {info['visual']}")
        return

    if args.island:
        _print_island(args.island)
        return

    if args.lightning_war:
        completed = _normalize_completed(args.completed)
        for choice in ("archive", "rst", "detritus", "pinnacle"):
            if choice not in completed:
                _print_island(choice)
                return

    _print_island(random.choice(list(ISLANDS.keys())))


if __name__ == "__main__":
    main()
