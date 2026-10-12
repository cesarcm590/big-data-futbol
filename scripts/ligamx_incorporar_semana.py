"""
Liga MX: incorpora al proyecto los partidos nuevos que se extrajeron de FBref desde el Chrome del usuario.

    python scripts/ligamx_incorporar_semana.py 2026-10-10          # etiqueta = sufijo de los archivos de entrada
    python scripts/ligamx_incorporar_semana.py 2026-10-10 --solo-validar

POR QUÉ EXISTE
--------------
FBref está detrás de Cloudflare: solo responde desde el navegador del usuario, así que la captura es interactiva y
no se puede meter en el temporizador (ver actualizar_semanal.py, que lo dice en cada corrida). Pero TODO lo que viene
después de la captura sí es mecánico, y las dos primeras veces se hizo con scripts sueltos que se perdieron. Este es el
que queda en el repo.

ENTRADAS (data/raw/ligamx_semana/, las deja la captura; separador "|", sin encabezado)
  schedule_nuevos_<etiqueta>.psv   jornada|dia|fecha|hora|local|marcador|visitante|asistencia|estadio|arbitro|match_id|notas
  reportes_<etiqueta>.psv          match_id|posL|posV|sotL|tiros L|sotV|tiros V|paradasL|tiros a puertaL contra|paradasV|
                                   tiros a puerta V contra|amarillasL|rojasL|amarillasV|rojasV|faltasL|faltasV|corners L|
                                   corners V|centrosL|centrosV|intercepcionesL|intercepcionesV|fuerasL|fuerasV
                                   (un valor ausente en FBref queda VACÍO; no se rellena con 0)
  futuros_<etiqueta>.psv           jornada|fecha|hora|local|visitante  (calendario por jugar; lo lee el exportador)

LO QUE HACE (en este orden; cada paso es idempotente: correrlo dos veces no duplica nada)
  1. Agrega los partidos al calendario maestro (data/raw/matches_ligamx_2020_2025_schedule.csv).
  2. Guarda un CSV por partido en data/raw/match_reports_ligamx/<match_id>.csv.
  3. Reconstruye data/processed/matches_ligamx_2020_2025_completo.csv uniendo calendario y reportes SOLO por match_id
     (los nombres de equipo no siempre coinciden carácter por carácter; unir por nombre dejó 358 partidos sin
     estadísticas en la Fase 12) y comprueba que las filas viejas quedaron idénticas.
  4. Agrega a data/processed/matches_ligamx_2020_2025_v3_arbitraje.csv las filas nuevas con sus columnas derivadas
     (eficiencia = tiros a puerta / tiros, tarjetas totales, tarjetas por falta...).

AVISA, no corrige: árbitros que nunca habían aparecido (FBref a veces agrega acentos o un segundo nombre y eso duplicó
8 árbitros en las Fases 10-11) y partidos cuyas paradas no cuadran con el marcador.
"""
import csv
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
SEMANA = RAIZ / "data" / "raw" / "ligamx_semana"
CALENDARIO = RAIZ / "data" / "raw" / "matches_ligamx_2020_2025_schedule.csv"
REPORTES = RAIZ / "data" / "raw" / "match_reports_ligamx"
COMPLETO = RAIZ / "data" / "processed" / "matches_ligamx_2020_2025_completo.csv"
V3 = RAIZ / "data" / "processed" / "matches_ligamx_2020_2025_v3_arbitraje.csv"

RONDA = "Apertura 2026 Regular Season"      # cambiar al empezar el Clausura 2027 (enero de 2027)
TEMPORADA = "2026-2027"

COLS_CAL = ["round", "gameweek", "dayofweek", "date", "start_time", "home_team", "score", "away_team", "attendance",
            "venue", "referee", "match_report_url", "match_id", "notes", "season"]
COLS_REPORTE = ["match_id", "home_team", "away_team", "home_possession", "away_possession",
                "home_shots_on_target", "home_shots_total", "away_shots_on_target", "away_shots_total",
                "home_saves", "home_saves_total", "away_saves", "away_saves_total",
                "home_yellow", "home_red", "away_yellow", "away_red", "home_fouls", "away_fouls",
                "home_corners", "away_corners", "home_crosses", "away_crosses",
                "home_interceptions", "away_interceptions", "home_offsides", "away_offsides"]
# Orden de los campos de reportes_*.psv (después del match_id), igual que COLS_REPORTE[3:]
ORDEN_PSV = ["home_possession", "away_possession", "home_shots_on_target", "home_shots_total",
             "away_shots_on_target", "away_shots_total", "home_saves", "home_saves_total", "away_saves",
             "away_saves_total", "home_yellow", "home_red", "away_yellow", "away_red", "home_fouls", "away_fouls",
             "home_corners", "away_corners", "home_crosses", "away_crosses", "home_interceptions",
             "away_interceptions", "home_offsides", "away_offsides"]
assert ORDEN_PSV == COLS_REPORTE[3:], "el orden del .psv y del esquema de reportes debe coincidir"


def leer_psv(ruta, columnas):
    filas = []
    for n, linea in enumerate(ruta.read_text(encoding="utf-8").splitlines(), 1):
        if not linea.strip():
            continue
        campos = linea.split("|")
        if len(campos) != len(columnas):
            raise SystemExit(f"{ruta.name} línea {n}: {len(campos)} campos, se esperaban {len(columnas)}")
        filas.append(dict(zip(columnas, campos)))
    return filas


def main():
    etiqueta = sys.argv[1]
    solo_validar = "--solo-validar" in sys.argv
    nuevos = leer_psv(SEMANA / f"schedule_nuevos_{etiqueta}.psv",
                      ["gameweek", "dayofweek", "date", "start_time", "home_team", "score", "away_team", "attendance",
                       "venue", "referee", "match_id", "notes"])
    reportes = {r["match_id"]: r for r in leer_psv(SEMANA / f"reportes_{etiqueta}.psv", ["match_id"] + ORDEN_PSV)}

    # --- Validaciones de entrada: todo partido nuevo trae reporte y viceversa, sin ids repetidos ---
    ids = [n["match_id"] for n in nuevos]
    assert len(ids) == len(set(ids)), "match_id repetido en el calendario nuevo"
    faltan = set(ids) - set(reportes)
    sobran = set(reportes) - set(ids)
    if faltan or sobran:
        raise SystemExit(f"calendario y reportes no coinciden. Sin reporte: {sorted(faltan)} | sin calendario: {sorted(sobran)}")

    cal = pd.read_csv(CALENDARIO, dtype=str)
    ya = set(cal["match_id"].dropna())
    a_agregar = [n for n in nuevos if n["match_id"] not in ya]
    print(f"Partidos en la captura: {len(nuevos)} | ya estaban: {len(nuevos) - len(a_agregar)} | nuevos: {len(a_agregar)}")

    # --- Avisos (no corrigen): árbitros nunca vistos y paradas que no cuadran con el marcador ---
    conocidos = set(cal["referee"].dropna())
    for n in a_agregar:
        if n["referee"] not in conocidos:
            print(f"   ! árbitro NUEVO: «{n['referee']}» (revisar que no sea un duplicado con acento o segundo nombre)")
    for n in a_agregar:
        gl, gv = [int(x) for x in n["score"].replace("-", "–").split("–")[:2]]
        r = reportes[n["match_id"]]
        for lado, goles_en_contra in (("home", gv), ("away", gl)):
            sv, tot = r[f"{lado}_saves"], r[f"{lado}_saves_total"]
            if sv != "" and tot != "" and int(tot) - int(sv) != goles_en_contra:
                print(f"   ~ {n['home_team']}–{n['away_team']}: el portero {lado} tiene {tot} a puerta y {sv} paradas, "
                      f"pero recibió {goles_en_contra} goles (¿autogol o dato de FBref?)")
    if solo_validar:
        print("(--solo-validar) no se escribió nada.")
        return

    # --- 1. Calendario maestro ---
    if a_agregar:
        filas = [{"round": RONDA, "gameweek": n["gameweek"], "dayofweek": n["dayofweek"], "date": n["date"],
                  "start_time": n["start_time"], "home_team": n["home_team"], "score": n["score"],
                  "away_team": n["away_team"], "attendance": n["attendance"] or np.nan, "venue": n["venue"],
                  "referee": n["referee"], "match_report_url": f"https://fbref.com/en/matches/{n['match_id']}",
                  "match_id": n["match_id"], "notes": np.nan, "season": TEMPORADA} for n in a_agregar]
        cal = pd.concat([cal, pd.DataFrame(filas, columns=COLS_CAL)], ignore_index=True)
        cal.to_csv(CALENDARIO, index=False)
        print(f"1. calendario maestro: {len(cal)} partidos")

    # --- 2. Un CSV por reporte (se escribe cada uno antes de pasar al siguiente) ---
    nombres = {n["match_id"]: (n["home_team"], n["away_team"]) for n in nuevos}
    for mid, r in reportes.items():
        h, a = nombres[mid]
        with open(REPORTES / f"{mid}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=COLS_REPORTE)
            w.writeheader()
            w.writerow({**r, "home_team": h, "away_team": a})
    print(f"2. reportes guardados: {len(reportes)} (total en carpeta: {len(list(REPORTES.glob('*.csv')))})")

    # --- 3. Recombinar calendario + reportes SOLO por match_id y verificar que lo viejo no cambió ---
    todos = pd.concat([pd.read_csv(p, dtype=str) for p in sorted(REPORTES.glob("*.csv"))], ignore_index=True)
    todos = todos.drop(columns=["home_team", "away_team"]).drop_duplicates("match_id")
    completo = cal.merge(todos, on="match_id", how="left")
    viejo = pd.read_csv(COMPLETO, dtype=str)
    comunes = viejo.merge(completo, on="match_id", suffixes=("_v", "_n"))
    cols_stats = [c for c in viejo.columns if c.startswith(("home_", "away_")) and c not in ("home_team", "away_team")]
    difieren = 0
    for c in cols_stats:
        a, b = comunes[f"{c}_v"].fillna(""), comunes[f"{c}_n"].fillna("")
        difieren += int((a != b).sum())
    if difieren:
        raise SystemExit(f"3. ABORTADO: {difieren} celdas de partidos viejos cambiaron al recombinar; no se escribió el completo.")
    sin_stats = int(completo["home_possession"].isna().sum())
    completo.to_csv(COMPLETO, index=False)
    print(f"3. completo: {len(completo)} partidos, {len(completo) - sin_stats} con estadísticas (viejos idénticos)")

    # --- 4. v3: filas nuevas con las columnas derivadas ---
    v3 = pd.read_csv(V3, dtype=str)
    llave = lambda d: set(zip(d["date"], d["home_team"], d["away_team"]))
    nuevas = completo[[k not in llave(v3) for k in zip(completo["date"], completo["home_team"], completo["away_team"])]].copy()
    num = lambda s: pd.to_numeric(s, errors="coerce")
    for lado in ("home", "away"):
        nuevas[f"{lado}_total_cards"] = num(nuevas[f"{lado}_yellow"]) + num(nuevas[f"{lado}_red"])
        nuevas[f"{lado}_efficency"] = num(nuevas[f"{lado}_shots_on_target"]) / num(nuevas[f"{lado}_shots_total"])
    nuevas["total_game_cards"] = nuevas["home_total_cards"] + nuevas["away_total_cards"]
    nuevas["home_card_game_per_fouls"] = nuevas["total_game_cards"] / num(nuevas["home_fouls"])
    nuevas["away_card_game_per_foul"] = nuevas["total_game_cards"] / num(nuevas["away_fouls"])
    nuevas = nuevas.replace([np.inf, -np.inf], np.nan)
    v3_nuevo = pd.concat([v3, nuevas[v3.columns]], ignore_index=True)
    v3_nuevo.to_csv(V3, index=False)
    print(f"4. v3: {len(v3)} -> {len(v3_nuevo)} partidos (+{len(nuevas)})")


if __name__ == "__main__":
    main()
