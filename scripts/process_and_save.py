#!/usr/bin/env python3
"""Toma el match_id y el JSON crudo extraido via JS de la pagina de FBref,
lo normaliza al esquema final, agrega home_team/away_team desde el schedule,
y lo guarda en data/raw/match_reports_ligamx/{match_id}.csv.

Uso: process_and_save.py <match_id> '<raw_json>'
"""
import sys
import json
import re
import csv
import os

BASE = "/Users/javiercarrillo/Proyectos/Big_data_futbol"
LOOKUP = os.path.join(BASE, "scripts/_team_lookup.json")
OUT_DIR = os.path.join(BASE, "data/raw/match_reports_ligamx")

COLUMNS = [
    "match_id", "home_team", "away_team", "home_possession", "away_possession",
    "home_shots_on_target", "home_shots_total", "away_shots_on_target", "away_shots_total",
    "home_saves", "home_saves_total", "away_saves", "away_saves_total",
    "home_yellow", "home_red", "away_yellow", "away_red",
    "home_fouls", "away_fouls", "home_corners", "away_corners",
    "home_crosses", "away_crosses", "home_interceptions", "away_interceptions",
    "home_offsides", "away_offsides",
]


def parse_n_of_m(raw):
    """Extrae (N, M) del patron 'N of M' sin importar el orden con el %."""
    if not raw:
        return "", ""
    m = re.search(r"(\d+)\s+of\s+(\d+)", raw)
    if m:
        return m.group(1), m.group(2)
    return "", ""


def parse_pct(raw):
    if not raw:
        return ""
    m = re.search(r"(\d+)\s*%", raw)
    return m.group(1) if m else raw.strip()


def main():
    match_id = sys.argv[1]
    raw = json.loads(sys.argv[2])

    with open(LOOKUP) as f:
        lookup = json.load(f)
    pair = lookup.get(match_id)
    if pair:
        home_team, away_team = pair
    else:
        home_team = raw.get("home_team_page") or ""
        away_team = raw.get("away_team_page") or ""

    home_sot, home_st = parse_n_of_m(raw.get("home_shots_raw", ""))
    away_sot, away_st = parse_n_of_m(raw.get("away_shots_raw", ""))
    home_sv, home_svt = parse_n_of_m(raw.get("home_saves_raw", ""))
    away_sv, away_svt = parse_n_of_m(raw.get("away_saves_raw", ""))

    data = {
        "match_id": match_id,
        "home_team": home_team,
        "away_team": away_team,
        "home_possession": parse_pct(raw.get("home_possession", "")),
        "away_possession": parse_pct(raw.get("away_possession", "")),
        "home_shots_on_target": home_sot,
        "home_shots_total": home_st,
        "away_shots_on_target": away_sot,
        "away_shots_total": away_st,
        "home_saves": home_sv,
        "home_saves_total": home_svt,
        "away_saves": away_sv,
        "away_saves_total": away_svt,
        "home_yellow": raw.get("home_yellow", ""),
        "home_red": raw.get("home_red", ""),
        "away_yellow": raw.get("away_yellow", ""),
        "away_red": raw.get("away_red", ""),
        "home_fouls": raw.get("home_fouls", ""),
        "away_fouls": raw.get("away_fouls", ""),
        "home_corners": raw.get("home_corners", ""),
        "away_corners": raw.get("away_corners", ""),
        "home_crosses": raw.get("home_crosses", ""),
        "away_crosses": raw.get("away_crosses", ""),
        "home_interceptions": raw.get("home_interceptions", ""),
        "away_interceptions": raw.get("away_interceptions", ""),
        "home_offsides": raw.get("home_offsides", ""),
        "away_offsides": raw.get("away_offsides", ""),
    }

    out_path = os.path.join(OUT_DIR, f"{match_id}.csv")
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerow({c: data.get(c, "") for c in COLUMNS})
    print(f"guardado: {out_path} | {home_team} {data['home_possession']}% - {away_team} {data['away_possession']}%")


if __name__ == "__main__":
    main()
