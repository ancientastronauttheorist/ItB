"""
Scrape Into the Breach fandom wiki using Playwright (headed mode for Cloudflare).
"""

import json
import re
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from bs4 import BeautifulSoup

OUTPUT_DIR = Path("data/wiki_raw")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

WIKI_BASE = "https://intothebreach.fandom.com/wiki"

PAGES = {
    # Core index pages
    "Vek": f"{WIKI_BASE}/Vek",
    "Pilots": f"{WIKI_BASE}/Pilots",
    "Squads": f"{WIKI_BASE}/Squads",
    "Weapons": f"{WIKI_BASE}/Weapons",
    "Achievements": f"{WIKI_BASE}/Achievements",
    "Status_Effects": f"{WIKI_BASE}/Status_Effects",
    "Terrain": f"{WIKI_BASE}/Terrain",
    "Islands": f"{WIKI_BASE}/Islands",
    "Psion": f"{WIKI_BASE}/Psion",

    # Base Vek
    "Firefly": f"{WIKI_BASE}/Firefly",
    "Hornet": f"{WIKI_BASE}/Hornet",
    "Scarab": f"{WIKI_BASE}/Scarab",
    "Leaper": f"{WIKI_BASE}/Leaper",
    "Scorpion": f"{WIKI_BASE}/Scorpion",
    "Centipede": f"{WIKI_BASE}/Centipede",
    "Spider": f"{WIKI_BASE}/Spider",
    "Beetle": f"{WIKI_BASE}/Beetle",
    "Blobber": f"{WIKI_BASE}/Blobber",
    "Digger": f"{WIKI_BASE}/Digger",
    "Burrower": f"{WIKI_BASE}/Burrower",
    "Crab": f"{WIKI_BASE}/Crab",
    "Volatile_Vek": f"{WIKI_BASE}/Volatile_Vek",

    # AE Vek
    "Bouncer": f"{WIKI_BASE}/Bouncer",
    "Moth": f"{WIKI_BASE}/Moth",
    "Gastropod": f"{WIKI_BASE}/Gastropod",
    "Mosquito": f"{WIKI_BASE}/Mosquito",
    "Plasmodia": f"{WIKI_BASE}/Plasmodia",
    "Starfish": f"{WIKI_BASE}/Starfish",
    "Tumblebug": f"{WIKI_BASE}/Tumblebug",
    "Bot": f"{WIKI_BASE}/Bot",

    # Alpha Vek
    "Alpha_Firefly": f"{WIKI_BASE}/Alpha_Firefly",
    "Alpha_Hornet": f"{WIKI_BASE}/Alpha_Hornet",
    "Alpha_Leaper": f"{WIKI_BASE}/Alpha_Leaper",
    "Alpha_Beetle": f"{WIKI_BASE}/Alpha_Beetle",
    "Alpha_Scorpion": f"{WIKI_BASE}/Alpha_Scorpion",
    "Alpha_Centipede": f"{WIKI_BASE}/Alpha_Centipede",
    "Alpha_Burrower": f"{WIKI_BASE}/Alpha_Burrower",
    "Alpha_Scarab": f"{WIKI_BASE}/Alpha_Scarab",
    "Alpha_Blobber": f"{WIKI_BASE}/Alpha_Blobber",
    "Alpha_Spider": f"{WIKI_BASE}/Alpha_Spider",
    "Alpha_Moth": f"{WIKI_BASE}/Alpha_Moth",
    "Alpha_Bouncer": f"{WIKI_BASE}/Alpha_Bouncer",

    # Psions
    "Soldier_Psion": f"{WIKI_BASE}/Soldier_Psion",
    "Blood_Psion": f"{WIKI_BASE}/Blood_Psion",
    "Shell_Psion": f"{WIKI_BASE}/Shell_Psion",
    "Blast_Psion": f"{WIKI_BASE}/Blast_Psion",
    "Smoldering_Psion": f"{WIKI_BASE}/Smoldering_Psion",
    "Arachnid_Psion": f"{WIKI_BASE}/Arachnid_Psion",
    "Raging_Psion": f"{WIKI_BASE}/Raging_Psion",
    "Psion_Tyrant": f"{WIKI_BASE}/Psion_Tyrant",

    # Leaders
    "Beetle_Leader": f"{WIKI_BASE}/Beetle_Leader",
    "Firefly_Leader": f"{WIKI_BASE}/Firefly_Leader",
    "Hornet_Leader": f"{WIKI_BASE}/Hornet_Leader",
    "Scorpion_Leader": f"{WIKI_BASE}/Scorpion_Leader",
    "Spider_Leader": f"{WIKI_BASE}/Spider_Leader",
    "Psion_Abomination": f"{WIKI_BASE}/Psion_Abomination",
    "Large_Goo": f"{WIKI_BASE}/Large_Goo",

    # Squads
    "Rift_Walkers": f"{WIKI_BASE}/Rift_Walkers",
    "Rusting_Hulks": f"{WIKI_BASE}/Rusting_Hulks",
    "Zenith_Guard": f"{WIKI_BASE}/Zenith_Guard",
    "Blitzkrieg": f"{WIKI_BASE}/Blitzkrieg",
    "Steel_Judoka": f"{WIKI_BASE}/Steel_Judoka",
    "Flame_Behemoths": f"{WIKI_BASE}/Flame_Behemoths",
    "Frozen_Titans": f"{WIKI_BASE}/Frozen_Titans",
    "Hazardous_Mechs": f"{WIKI_BASE}/Hazardous_Mechs",
    "Bombermechs": f"{WIKI_BASE}/Bombermechs",
    "Arachnophiles": f"{WIKI_BASE}/Arachnophiles",
    "Mist_Eaters": f"{WIKI_BASE}/Mist_Eaters",
    "Heat_Sinkers": f"{WIKI_BASE}/Heat_Sinkers",
    "Cataclysm_(squad)": f"{WIKI_BASE}/Cataclysm_(squad)",
    "Secret_Squad": f"{WIKI_BASE}/Secret_Squad",

    # Mechs
    "Combat_Mech": f"{WIKI_BASE}/Combat_Mech",
    "Cannon_Mech": f"{WIKI_BASE}/Cannon_Mech",
    "Artillery_Mech": f"{WIKI_BASE}/Artillery_Mech",
    "Jet_Mech": f"{WIKI_BASE}/Jet_Mech",
    "Rocket_Mech": f"{WIKI_BASE}/Rocket_Mech",
    "Pulse_Mech": f"{WIKI_BASE}/Pulse_Mech",
    "Laser_Mech": f"{WIKI_BASE}/Laser_Mech",
    "Charge_Mech": f"{WIKI_BASE}/Charge_Mech",
    "Defense_Mech": f"{WIKI_BASE}/Defense_Mech",
    "Lightning_Mech": f"{WIKI_BASE}/Lightning_Mech",
    "Hook_Mech": f"{WIKI_BASE}/Hook_Mech",
    "Boulder_Mech": f"{WIKI_BASE}/Boulder_Mech",
    "Judo_Mech": f"{WIKI_BASE}/Judo_Mech",
    "Siege_Mech": f"{WIKI_BASE}/Siege_Mech",
    "Gravity_Mech": f"{WIKI_BASE}/Gravity_Mech",
    "Flame_Mech": f"{WIKI_BASE}/Flame_Mech",
    "Meteor_Mech": f"{WIKI_BASE}/Meteor_Mech",
    "Swap_Mech": f"{WIKI_BASE}/Swap_Mech",
    "Aegis_Mech": f"{WIKI_BASE}/Aegis_Mech",
    "Mirror_Mech": f"{WIKI_BASE}/Mirror_Mech",
    "Ice_Mech": f"{WIKI_BASE}/Ice_Mech",
    "Leap_Mech": f"{WIKI_BASE}/Leap_Mech",
    "Unstable_Mech": f"{WIKI_BASE}/Unstable_Mech",
    "Nano_Mech": f"{WIKI_BASE}/Nano_Mech",
    "Pierce_Mech": f"{WIKI_BASE}/Pierce_Mech",
    "Bombling_Mech": f"{WIKI_BASE}/Bombling_Mech",
    "Exchange_Mech": f"{WIKI_BASE}/Exchange_Mech",
    "Bulk_Mech": f"{WIKI_BASE}/Bulk_Mech",
    "Arachnoid_Mech": f"{WIKI_BASE}/Arachnoid_Mech",
    "Slide_Mech": f"{WIKI_BASE}/Slide_Mech",
    "Thruster_Mech": f"{WIKI_BASE}/Thruster_Mech",
    "Smog_Mech": f"{WIKI_BASE}/Smog_Mech",
    "Control_Mech": f"{WIKI_BASE}/Control_Mech",
    "Dispersal_Mech": f"{WIKI_BASE}/Dispersal_Mech",
    "Quick-Fire_Mech": f"{WIKI_BASE}/Quick-Fire_Mech",
    "Napalm_Mech": f"{WIKI_BASE}/Napalm_Mech",
    "Pitcher_Mech": f"{WIKI_BASE}/Pitcher_Mech",
    "Triptych_Mech": f"{WIKI_BASE}/Triptych_Mech",
    "Drill_Mech": f"{WIKI_BASE}/Drill_Mech",

    # Pilots
    "Ralph_Karlsson": f"{WIKI_BASE}/Ralph_Karlsson",
    "Bethany_Jones": f"{WIKI_BASE}/Bethany_Jones",
    "Silica": f"{WIKI_BASE}/Silica",
    "Prospero": f"{WIKI_BASE}/Prospero",
    "Isaac_Jones": f"{WIKI_BASE}/Isaac_Jones",
    "Camila_Vera": f"{WIKI_BASE}/Camila_Vera",
    "Abe_Isamu": f"{WIKI_BASE}/Abe_Isamu",
    "Kazaaakpleth": f"{WIKI_BASE}/Kazaaakpleth",
    "Mafan": f"{WIKI_BASE}/Mafan",
    "Ariadne": f"{WIKI_BASE}/Ariadne",

    # Islands
    "Archive_Inc": f"{WIKI_BASE}/Archive,_Inc.",
    "RST": f"{WIKI_BASE}/R.S.T._Corporation",
    "Pinnacle": f"{WIKI_BASE}/Pinnacle_Robotics",
    "Detritus": f"{WIKI_BASE}/Detritus_Disposal",
    "Volcanic_Hive": f"{WIKI_BASE}/Volcanic_Hive",

    # Mechanics
    "Experience": f"{WIKI_BASE}/Experience",
    "Difficulty": f"{WIKI_BASE}/Difficulty",
    "Grid_Power": f"{WIKI_BASE}/Grid_Power",
    "Reactor_Cores": f"{WIKI_BASE}/Reactor_Core",
    "Time_Pods": f"{WIKI_BASE}/Time_Pod",
    "Combat": f"{WIKI_BASE}/Combat",
}


def extract_content(html):
    """Extract all useful data from a fandom wiki page."""
    soup = BeautifulSoup(html, "lxml")
    content = soup.find("div", class_="mw-parser-output")
    if not content:
        return None

    # --- Infobox ---
    infobox = {}
    ib_el = content.find("aside", class_="portable-infobox")
    if ib_el:
        title = ib_el.find(class_="pi-title")
        if title:
            infobox["_title"] = title.get_text(strip=True)
        for item in ib_el.find_all("div", class_="pi-item"):
            label = item.find(class_="pi-data-label")
            value = item.find(class_="pi-data-value")
            if label and value:
                infobox[label.get_text(strip=True)] = value.get_text(strip=True)

    # --- Tables ---
    tables = []
    for table in content.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue
        headers = [th.get_text(strip=True) for th in rows[0].find_all(["th", "td"])]
        if not headers:
            continue
        data = []
        for row in rows[1:]:
            cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
            if cells and len(cells) >= 2:
                data.append(dict(zip(headers, cells)))
        if data:
            tables.append({"headers": headers, "rows": data})

    # --- Sections ---
    sections = {}
    cur = "intro"
    buf = []
    for el in content.children:
        if not hasattr(el, "name") or not el.name:
            continue
        if el.name in ("h1", "h2", "h3", "h4"):
            if buf:
                sections[cur] = "\n".join(buf)
            hl = el.find(class_="mw-headline") or el
            cur = re.sub(r"\[edit\]", "", hl.get_text(strip=True)).strip()
            buf = []
        elif el.name == "p":
            t = el.get_text(strip=True)
            if t:
                buf.append(t)
        elif el.name in ("ul", "ol"):
            for li in el.find_all("li", recursive=False):
                t = li.get_text(strip=True)
                if t:
                    buf.append(f"  - {t}")
        elif el.name == "aside":
            pass  # infobox handled above
    if buf:
        sections[cur] = "\n".join(buf)

    # --- Full text (fallback for pages with unusual structure) ---
    full_text = content.get_text(separator="\n", strip=True)

    return {
        "infobox": infobox if infobox else None,
        "tables": tables,
        "sections": sections,
        "full_text": full_text[:5000] if full_text else "",
    }


def main():
    print("=" * 60)
    print("ITB Fandom Wiki Scraper (headed browser + CF bypass)")
    print(f"Pages: {len(PAGES)}")
    print("=" * 60)

    results = {}
    failed = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900},
        )
        ctx.add_init_script('Object.defineProperty(navigator, "webdriver", { get: () => undefined })')
        page = ctx.new_page()

        for i, (name, url) in enumerate(PAGES.items(), 1):
            print(f"[{i}/{len(PAGES)}] {name}...", end=" ", flush=True)
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)

                # Wait for real content (CF challenge auto-resolves in headed mode)
                try:
                    page.wait_for_selector(".mw-parser-output", timeout=30000)
                except PWTimeout:
                    # Maybe CF is still processing
                    print("waiting...", end=" ", flush=True)
                    time.sleep(10)
                    try:
                        page.wait_for_selector(".mw-parser-output", timeout=15000)
                    except PWTimeout:
                        print("TIMEOUT")
                        failed.append(name)
                        continue

                html = page.content()
                parsed = extract_content(html)

                if parsed:
                    (OUTPUT_DIR / f"{name}.html").write_text(html, encoding="utf-8")
                    result = {"name": name, "url": url, **parsed}
                    (OUTPUT_DIR / f"{name}.json").write_text(
                        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
                    )
                    s = len(parsed["sections"])
                    t = len(parsed["tables"])
                    ib = "yes" if parsed["infobox"] else "no"
                    ft = len(parsed["full_text"])
                    print(f"OK ({s}s {t}t ib={ib} {ft}c)")
                    results[name] = result
                else:
                    print("NO CONTENT")
                    failed.append(name)

            except Exception as e:
                print(f"ERR: {e}")
                failed.append(name)

            # Be polite to avoid CF rate limits
            time.sleep(1.5)

        browser.close()

    print()
    print("=" * 60)
    print(f"Done: {len(results)} OK, {len(failed)} failed")
    if failed:
        print(f"Failed: {', '.join(failed)}")

    (OUTPUT_DIR / "_index.json").write_text(json.dumps({
        "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(PAGES),
        "ok": len(results),
        "failed": failed,
    }, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
