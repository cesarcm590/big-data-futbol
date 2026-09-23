"""
Convierte la extracción de las tablas `keepers` y `playingtime` de FBref en CSVs por liga-temporada, y mide su cobertura.

    python scripts/convertir_keepers_playingtime.py

Entrada
  data/raw/fbref_keepers_playingtime_2010_2026.json
      Extraído el 2026-09-19 desde el navegador del usuario (mismo método que los ids: fetch() desde una pestaña de
      FBref, una página cada 8-10 s, guardado en IndexedDB y bajado en una sola descarga). Claves "tabla|Liga_temporada"
      ("keepers|Liga-MX_2024-2025"); cada valor trae:
        cols, rows   la tabla completa tal como la muestra FBref (nombres `data-stat`), + player_id y team_id al final
        sin_id       filas sin id de jugador o de equipo
        firma, ok    solo playingtime: huella de las filas con partidos jugados y si coincide con la del panel
        error        si la página no tenía la tabla

Salidas
  data/raw/fbref_keepers/{Liga}_{temporada}.csv       una por liga-temporada, mismo formato que data/raw/fbref_historical/
  data/raw/fbref_playingtime/{Liga}_{temporada}.csv   (columnas de FBref + player_id, team_id + league, season)
  output/cobertura_keepers_playingtime.csv            % de filas con dato, por tabla, liga, temporada y columna

Por qué medir la cobertura: la prueba de la Fase 19 mostró que FBref no tiene los mismos datos en todas las épocas
(en 2010-11 no hay penales atajados ni nada "con el jugador en cancha"). Un análisis que use onGA, por ejemplo, tiene que
saber en qué liga-temporadas existe, en vez de tratar un hueco como un cero.
Para la cobertura de playingtime solo cuentan los jugadores que jugaron: los que solo fueron a la banca tienen minutos
y onGA vacíos por definición, y bajarían el porcentaje sin que falte ningún dato.

Si todo se verifica, el JSON ya no hace falta (los CSV son la fuente): el script lo indica y no lo borra solo.
Se corrió una vez, el 2026-09-19: 224 páginas, 75,239 filas, 0 problemas; después el JSON se retiró del proyecto. Para
una extracción nueva (p. ej. la temporada 2026-27), dejar el JSON nuevo en RUTA_JSON y volver a correrlo.
"""
import json
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
RUTA_JSON = RAIZ / "data" / "raw" / "fbref_keepers_playingtime_2010_2026.json"
CARPETAS = {"keepers": RAIZ / "data" / "raw" / "fbref_keepers", "playingtime": RAIZ / "data" / "raw" / "fbref_playingtime"}
RUTA_COBERTURA = RAIZ / "output" / "cobertura_keepers_playingtime.csv"
RUTA_PANEL = RAIZ / "data" / "processed" / "fbref_panel_2010_2025.csv"


def main():
    paginas = json.loads(RUTA_JSON.read_text())
    esperadas = {f"{t}|{p.stem}" for t in CARPETAS for p in (RAIZ / "data" / "raw" / "fbref_historical").glob("*.csv")}
    faltan = esperadas - set(paginas)
    errores = {k: v for k, v in paginas.items() if "error" in v}
    if faltan or errores:
        print(f"Faltan {len(faltan)} páginas y {len(errores)} tienen error:", sorted(faltan)[:5], list(errores.items())[:5])
        sys.exit(1)

    panel = pd.read_csv(RUTA_PANEL, dtype=str, keep_default_na=False)
    claves_panel = set(zip(panel["league"], panel["season"], panel["player_id"], panel["team_id"]))
    cobertura, problemas = [], []
    for carpeta in CARPETAS.values():
        carpeta.mkdir(parents=True, exist_ok=True)

    for clave, pag in sorted(paginas.items()):
        tabla, pagina = clave.split("|")
        slug_liga, temporada = pagina.split("_")
        liga = slug_liga.replace("-", " ")          # "Liga-MX" -> "Liga MX", igual que la columna `league` del panel
        df = pd.DataFrame(pag["rows"], columns=pag["cols"]).assign(league=liga, season=temporada)
        df.to_csv(CARPETAS[tabla] / f"{pagina}.csv", index=False)

        if pag["sin_id"]:
            problemas.append(f"{clave}: {pag['sin_id']} filas sin id")
        if tabla == "playingtime":
            base = df[df["games"] != "0"]           # los que solo fueron a la banca no cuentan para la cobertura
            # Los que jugaron deben ser EXACTAMENTE las filas del panel de esa liga-temporada. Se compara por
            # (jugador, equipo, partidos, minutos) usando los ids, no por posición ni por nombre: así los cambios
            # conocidos de FBref (PSG -> "Paris SG", jugadores renombrados, filas en otro orden; ver
            # unir_ids_fbref.py) no cuentan como diferencia, y cualquier diferencia real sí.
            p = panel[(panel["league"] == liga) & (panel["season"] == temporada)]
            en_panel = sorted(zip(p["player_id"], p["team_id"], p["games"], p["minutes"]))
            en_fbref = sorted(zip(base["player_id"], base["team_id"], base["games"], base["minutes"]))
            if en_panel != en_fbref:
                problemas.append(f"{clave}: las filas con partidos no coinciden con el panel "
                                 f"({len(set(en_fbref) - set(en_panel))} de más, {len(set(en_panel) - set(en_fbref))} de menos)")
        else:
            base = df
            # Cada portero debería estar en la tabla estándar de esa liga-temporada con el mismo jugador y equipo.
            fuera = [r for r in base[["player_id", "team_id"]].itertuples(index=False)
                     if (liga, temporada, r.player_id, r.team_id) not in claves_panel]
            if fuera:
                problemas.append(f"{clave}: {len(fuera)} porteros no están en el panel con ese equipo")
        for col in pag["cols"]:
            cobertura.append({"tabla": tabla, "league": liga, "season": temporada, "columna": col,
                              "pct_con_dato": round(100 * (base[col] != "").mean(), 1), "filas": len(base)})

    cob = pd.DataFrame(cobertura)
    cob.to_csv(RUTA_COBERTURA, index=False)

    print(f"{len(paginas)} páginas -> {sum(1 for _ in CARPETAS['keepers'].glob('*.csv'))} CSV de keepers y "
          f"{sum(1 for _ in CARPETAS['playingtime'].glob('*.csv'))} de playingtime")
    print("Problemas:", "ninguno" if not problemas else "")
    for p in problemas:
        print("  -", p)

    # Resumen: desde qué temporada hay cada dato clave en cada liga (primera temporada con >= 90% de filas con dato).
    claves_col = {("keepers", "gk_clean_sheets"): "porterías a cero", ("keepers", "gk_saves"): "paradas",
                  ("keepers", "gk_pens_saved"): "penales atajados", ("playingtime", "on_goals_against"): "onGA",
                  ("playingtime", "unused_subs"): "banca sin jugar", ("playingtime", "points_per_game"): "pts/partido"}
    filas = []
    for (tabla, col), nombre in claves_col.items():
        c = cob[(cob["tabla"] == tabla) & (cob["columna"] == col)]
        for liga, g in c.groupby("league"):
            con = g[g["pct_con_dato"] >= 90].sort_values("season")
            filas.append({"dato": nombre, "league": liga,
                          "desde": con["season"].iloc[0] if len(con) else "nunca",
                          "temporadas_con_dato": f"{len(con)}/{len(g)}"})
    resumen = pd.DataFrame(filas).pivot(index="league", columns="dato", values="desde")
    print("\nPrimera temporada con el dato (>= 90% de las filas):")
    print(resumen.to_string())
    if not problemas:
        print(f"\nTodo verificado: {RUTA_JSON.relative_to(RAIZ)} ya no es necesario (los CSV son la fuente).")


if __name__ == "__main__":
    main()
