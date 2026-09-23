#!/usr/bin/env python3
"""Guarda un partido extraido en su propio CSV. Uso:
    save_match.py '<json_con_datos_del_partido>'
El JSON debe traer las claves exactas de las columnas del esquema.
"""
import sys
import json
import csv
import os

COLUMNS = [
    "match_id", "home_team", "away_team", "home_possession", "away_possession",
    "home_shots_on_target", "home_shots_total", "away_shots_on_target", "away_shots_total",
    "home_saves", "home_saves_total", "away_saves", "away_saves_total",
    "home_yellow", "home_red", "away_yellow", "away_red",
    "home_fouls", "away_fouls", "home_corners", "away_corners",
    "home_crosses", "away_crosses", "home_interceptions", "away_interceptions",
    "home_offsides", "away_offsides",
]

OUT_DIR = "/Users/javiercarrillo/Proyectos/Big_data_futbol/data/raw/match_reports_ligamx"

def main():
    data = json.loads(sys.argv[1])
    match_id = data["match_id"]
    out_path = os.path.join(OUT_DIR, f"{match_id}.csv")
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerow({c: data.get(c, "") for c in COLUMNS})
    print(f"guardado: {out_path}")

if __name__ == "__main__":
    main()
