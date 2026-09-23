"""
Construye el dataset de una liga europea (2015-16 -> temporada en curso) a partir de los CSV de
football-data.co.uk que están en data/raw/<carpeta_raw>/<prefijo>_AAAA.csv (AAAA = "1516", "2526", etc.).
Uso:  python scripts/europa_construir_dataset.py [premier|laliga]     (por defecto premier)
La configuración de cada liga está en scripts/ligas_europa.py.

POR QUÉ ESTA FUENTE Y NO FBREF
Estos CSV ya traen, por partido: goles, tiros, tiros a puerta, faltas, corners, tarjetas amarillas y
rojas, árbitro, Y las cuotas de las casas de apuestas (Bet365, Pinnacle, promedio del mercado...). Para
Liga MX no había cuotas gratuitas; aquí sí, y permiten comparar el modelo contra el mercado, que es la
prueba más exigente. Como ya está todo en CSV, no hace falta scrapear FBref para esta liga.

LO QUE HACE ESTE SCRIPT
  1. Lee cada CSV (las columnas cambian un poco entre temporadas: se toma la unión y se deja NaN donde falta).
  2. Estandariza fechas (dd/mm/aaaa o dd/mm/aa) y agrega la etiqueta de temporada "2025-2026".
  3. Guarda todo en data/processed/<dataset>.csv, ordenado por fecha (con nombres de equipo completos si la liga los define).

DATOS QUE NO SIEMPRE TRAE: el árbitro (La Liga no lo incluye). Frente a Liga MX / FBref tampoco trae posesión, atajadas, centros, intercepciones, fueras de lugar.
El modelo del proyecto solo usa goles, corners y tarjetas, así que no se necesitan.
"""
import glob
import os
import sys
import pandas as pd

from ligas_europa import LIGAS_EUROPA, RAIZ, renombrar_equipos

liga = sys.argv[1] if len(sys.argv) > 1 else "premier"
cfg = LIGAS_EUROPA[liga]
CARPETA_RAW = f"{RAIZ}/data/raw/{cfg['carpeta_raw']}"
SALIDA = f"{RAIZ}/data/processed/{cfg['dataset']}"

COLUMNAS = [
    "Date", "Time", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR", "Referee",
    "HS", "AS", "HST", "AST", "HF", "AF", "HC", "AC", "HY", "AY", "HR", "AR", "HxG", "AxG",
    # Cuotas 1X2 (local / empate / visitante). Sufijo C = cuota de CIERRE (justo antes del partido, la más informada).
    "B365H", "B365D", "B365A", "PSH", "PSD", "PSA", "AvgH", "AvgD", "AvgA",
    "PSCH", "PSCD", "PSCA", "AvgCH", "AvgCD", "AvgCA", "B365CH", "B365CD", "B365CA",
]


def etiqueta_temporada(codigo):
    """'2526' -> '2025-2026'; '1516' -> '2015-2016'."""
    a, b = int(codigo[:2]), int(codigo[2:])
    return f"20{a:02d}-20{b:02d}"


partes = []
for ruta in sorted(glob.glob(f"{CARPETA_RAW}/{cfg['prefijo']}_*.csv")):
    codigo = os.path.basename(ruta).split('_')[1][:4]
    d = pd.read_csv(ruta, encoding="utf-8-sig", on_bad_lines="skip")
    d = d.dropna(subset=["HomeTeam", "FTHG", "FTAG"]).copy()          # solo partidos ya jugados
    for c in COLUMNAS:
        if c not in d.columns:
            d[c] = float("nan")                                        # columna ausente en esa temporada
    d = d[COLUMNAS].copy()
    d["season"] = etiqueta_temporada(codigo)
    partes.append(d)

df = pd.concat(partes, ignore_index=True)
df = renombrar_equipos(df, cfg["nombres"])
df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, format="mixed")
for c in ["FTHG", "FTAG", "HS", "AS", "HST", "AST", "HF", "AF", "HC", "AC", "HY", "AY", "HR", "AR"]:
    df[c] = pd.to_numeric(df[c], errors="coerce")

# Resultado derivado de los goles (más confiable que FTR si hubiera alguna fila rara) + control de consistencia.
df["ganador"] = df.apply(lambda r: "Local" if r.FTHG > r.FTAG else ("Visitante" if r.FTHG < r.FTAG else "Empate"), axis=1)
mapa_ftr = {"H": "Local", "A": "Visitante", "D": "Empate"}
inconsistentes = int((df["FTR"].map(mapa_ftr) != df["ganador"]).sum())
print(f"Liga: {cfg['nombre']} | Filas: {len(df)} | inconsistencias FTR vs goles: {inconsistentes}")

df = df.sort_values(["Date", "Time", "HomeTeam"]).reset_index(drop=True)
df.to_csv(SALIDA, index=False)
print(df.groupby("season").size().to_string())
print("Guardado en", SALIDA)
