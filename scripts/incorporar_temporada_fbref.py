"""
Incorpora una temporada nueva de FBref al proyecto, a partir de una extracción hecha desde el navegador.

    python scripts/incorporar_temporada_fbref.py data/raw/fbref_2026_2027.json --temporada 2026-2027
    python scripts/incorporar_temporada_fbref.py data/raw/fbref_2026_2027.json --temporada 2026-2027 --reemplazar

Entrada: un JSON {"<tabla>|<Liga-Con-Guiones>": "<csv>"} con tabla en (stats, keepers, playingtime), que es lo que
produce el driver de `scripts/fbref_extraer_tabla.js` (fetch() desde una pestaña de FBref, una página cada 8-10 s,
acumulado en localStorage y bajado de una sola vez).

Salidas:
  data/raw/fbref_historical/{Liga}_{temporada}.csv     copia cruda de la tabla estándar
  data/raw/fbref_keepers/{Liga}_{temporada}.csv        las lee `plantillas.cargar_tabla_fbref`
  data/raw/fbref_playingtime/{Liga}_{temporada}.csv
  data/processed/fbref_panel_2010_2025.csv             se le AÑADEN las filas de la temporada nueva

Comprobaciones antes de escribir nada (si alguna falla, no se toca ningún archivo):
  - las 7 ligas × 3 tablas están presentes
  - las columnas de la tabla estándar son exactamente las del panel que ya existe
  - la temporada no está ya en el panel (salvo que se pase --reemplazar)
  - ninguna fila se queda sin `player_id`

Ojo con una temporada EN CURSO: las filas entran igual, pero con 4 o 5 jornadas jugadas las tasas por 90 y los
percentiles son casi ruido. Los análisis del proyecto ya filtran por minutos (900 para percentiles, 1,500 para las
estabilidades), así que la temporada parcial aparece en el panel y en el explorador pero no contamina las
comparaciones; lo que sí cambia es `partidos_liga`, que pasa a ser el máximo jugado hasta hoy.
"""
import argparse
import io
import json
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

RUTA_PANEL = RAIZ / "data" / "processed" / "fbref_panel_2010_2025.csv"
CARPETAS = {"stats": RAIZ / "data" / "raw" / "fbref_historical",
            "keepers": RAIZ / "data" / "raw" / "fbref_keepers",
            "playingtime": RAIZ / "data" / "raw" / "fbref_playingtime"}
# Clave del archivo (con guiones, como los nombres de archivo) -> valor de la columna `league` del panel.
LIGAS = {"Premier-League": "Premier League", "La-Liga": "La Liga", "Serie-A": "Serie A",
         "Bundesliga": "Bundesliga", "Ligue-1": "Ligue 1", "Eredivisie": "Eredivisie", "Liga-MX": "Liga MX"}
TIPOS_ID = {"player_id": "string", "team_id": "string"}


def leer(csv_texto: str, liga: str, temporada: str) -> pd.DataFrame:
    """CSV de FBref -> DataFrame con `league` y `season` al final, como el resto del proyecto."""
    d = pd.read_csv(io.StringIO(csv_texto), dtype=TIPOS_ID)
    return d.assign(league=LIGAS[liga], season=temporada)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("json", type=Path)
    p.add_argument("--temporada", required=True, help="p. ej. 2026-2027")
    p.add_argument("--reemplazar", action="store_true", help="si la temporada ya está en el panel, rehacerla")
    a = p.parse_args()

    bruto = json.loads(Path(a.json).read_text())
    tablas = {clave: leer(csv, clave.split("|")[1], a.temporada) for clave, csv in bruto.items()}

    errores = []
    faltan = {f"{t}|{l}" for t in CARPETAS for l in LIGAS} - set(tablas)
    if faltan:
        errores.append(f"faltan {len(faltan)} páginas: {sorted(faltan)}")

    panel = pd.read_csv(RUTA_PANEL, dtype=TIPOS_ID)
    for clave, d in tablas.items():
        if clave.startswith("stats|"):
            # Se comparan CONJUNTOS y luego se reordena: la extracción deja los ids antes de league/season y el panel
            # al revés, y eso es cosmético. Lo que no puede cambiar es qué columnas hay (FBref añade y quita campos
            # entre temporadas, y una columna nueva o ausente sí rompería el panel).
            if set(d.columns) != set(panel.columns):
                errores.append(f"{clave}: columnas distintas a las del panel\n"
                               f"  sobran: {sorted(set(d.columns) - set(panel.columns))}\n"
                               f"  faltan: {sorted(set(panel.columns) - set(d.columns))}")
            else:
                tablas[clave] = d[list(panel.columns)]
        sin_id = d["player_id"].isna().sum() if "player_id" in d else len(d)
        if sin_id:
            errores.append(f"{clave}: {sin_id} filas sin player_id")
    ya_esta = (panel["season"] == a.temporada).sum()
    if ya_esta and not a.reemplazar:
        errores.append(f"la temporada {a.temporada} ya tiene {ya_esta:,} filas en el panel (usa --reemplazar)")
    if errores:
        print("\n✗ No se escribió nada:")
        for e in errores:
            print(f"  - {e}")
        sys.exit(1)

    for clave, d in tablas.items():
        tabla, liga = clave.split("|")
        CARPETAS[tabla].mkdir(parents=True, exist_ok=True)
        d.to_csv(CARPETAS[tabla] / f"{liga}_{a.temporada}.csv", index=False)
    nuevas = pd.concat([d for c, d in tablas.items() if c.startswith("stats|")], ignore_index=True)
    panel = pd.concat([panel[panel["season"] != a.temporada], nuevas], ignore_index=True)
    panel.to_csv(RUTA_PANEL, index=False)

    print(f"✓ {a.temporada} incorporada")
    for tabla in CARPETAS:
        d = pd.concat([v for c, v in tablas.items() if c.startswith(f"{tabla}|")])
        print(f"   {tabla:12s} {len(d):6,} filas en {d['league'].nunique()} ligas")
    print(f"   panel        {len(panel):,} filas, {panel['season'].nunique()} temporadas "
          f"-> {RUTA_PANEL.relative_to(RAIZ)}")
    print(f"   jornadas jugadas por liga: "
          f"{dict(nuevas.groupby('league')['games'].max().sort_values().items())}")


if __name__ == "__main__":
    main()
