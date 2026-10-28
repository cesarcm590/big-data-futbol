"""
Reconstruye data/processed/matches_ligamx_2020_2025_v3_arbitraje.csv a partir de `..._completo.csv`.

POR QUÉ EXISTE ESTE SCRIPT
--------------------------
El 28 de octubre de 2026 ese archivo **había desaparecido del disco** y nada en el repositorio sabía crearlo: cinco
scripts lo LEEN (el exportador del panel, el histórico, el calificador de apuestas y el incorporador semanal) y
ninguno lo escribía desde cero. `ligamx_incorporar_semana.py` solo le AÑADE filas, así que sin el archivo abortaba
en su paso 4 y Liga MX se quedó congelada en los datos del 16 de octubre.

Un archivo del que dependen cinco scripts y que nadie puede regenerar es una bomba de relojería: mientras esté,
todo funciona; el día que no esté, no hay forma de volver. `data/` no se versiona (son ~87 MB), así que tampoco
había copia en git.

QUÉ ES v3 EXACTAMENTE
---------------------
`completo` más siete columnas derivadas, con las MISMAS fórmulas que usa `ligamx_incorporar_semana.py` para las
filas nuevas (se copiaron de ahí, no se reinventaron):

    home/away_total_cards        amarillas + rojas de cada lado
    home/away_efficency          tiros a puerta / tiros totales   (el nombre lleva la errata de origen)
    total_game_cards             tarjetas de los dos lados
    home_card_game_per_fouls     tarjetas del partido / faltas del local
    away_card_game_per_foul      tarjetas del partido / faltas del visitante   (singular, también de origen)

Los nombres con errata y la asimetría `fouls`/`foul` se conservan a propósito: cambiarlos rompería los cinco
consumidores en silencio.

El original tenía 41 columnas; este trae las de `completo` (menos `round`, ver abajo) más las siete, porque `completo` ganó columnas
después (centros, intercepciones, fueras de lugar). Es un superconjunto: los consumidores leen por nombre, así que
una columna de más no molesta, y `ligamx_incorporar_semana.py` seguirá cuadrando porque toma `v3.columns`.

Los cocientes 0/0 quedan en blanco, y los flotantes se escriben con %.15g, como el archivo original.

Uso:  python scripts/ligamx_reconstruir_v3.py [--forzar]
      Sin --forzar se niega a sobrescribir un v3 que ya exista.
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
COMPLETO = RAIZ / "data" / "processed" / "matches_ligamx_2020_2025_completo.csv"
V3 = RAIZ / "data" / "processed" / "matches_ligamx_2020_2025_v3_arbitraje.csv"


def derivar(d: pd.DataFrame) -> pd.DataFrame:
    """Las siete columnas derivadas. Mismas fórmulas que `ligamx_incorporar_semana.py`."""
    d = d.copy()
    num = lambda s: pd.to_numeric(s, errors="coerce")
    for lado in ("home", "away"):
        d[f"{lado}_total_cards"] = num(d[f"{lado}_yellow"]) + num(d[f"{lado}_red"])
        d[f"{lado}_efficency"] = num(d[f"{lado}_shots_on_target"]) / num(d[f"{lado}_shots_total"])
    d["total_game_cards"] = d["home_total_cards"] + d["away_total_cards"]
    d["home_card_game_per_fouls"] = d["total_game_cards"] / num(d["home_fouls"])
    d["away_card_game_per_foul"] = d["total_game_cards"] / num(d["away_fouls"])
    # Un 0/0 da inf o NaN según el caso; los dos deben quedar en blanco, no en un número inventado.
    return d.replace([np.inf, -np.inf], np.nan)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--forzar", action="store_true", help="sobrescribe un v3 existente")
    a = ap.parse_args()

    if V3.exists() and not a.forzar:
        raise SystemExit(f"{V3.name} ya existe ({len(pd.read_csv(V3)):,} filas). Usa --forzar si de verdad quieres "
                         "rehacerlo: el incorporador semanal le añade filas y rehacerlo las recalcula todas.")
    if not COMPLETO.exists():
        raise SystemExit(f"falta {COMPLETO}, que es la fuente: no hay nada que derivar")

    # dtype=str para no reformatear los valores que ya venían: el original se cuidó de no tocarlos y aquí tampoco.
    completo = pd.read_csv(COMPLETO, dtype=str)
    # `round` NO va en v3, y esto no es cosmético: los exportadores lo traen del calendario maestro con un merge
    # (`sched_slim`), así que si v3 ya lo tuviera, pandas crearía `round_x`/`round_y` y la línea siguiente moriría
    # con KeyError: 'round'. Pasó al reconstruirlo la primera vez. El comentario del exportador ya lo decía:
    # «Jornada/ronda: viene del calendario maestro, no de v3».
    v3 = derivar(completo.drop(columns=["round"], errors="ignore"))
    V3.parent.mkdir(parents=True, exist_ok=True)
    v3.to_csv(V3, index=False, float_format="%.15g")

    print(f"{V3.name}: {len(v3):,} filas, {len(v3.columns)} columnas")
    print(f"  duplicados por (fecha, local, visitante): "
          f"{int(v3.duplicated(['date', 'home_team', 'away_team']).sum())}")
    for c in ["total_game_cards", "home_efficency", "home_card_game_per_fouls"]:
        s = pd.to_numeric(v3[c], errors="coerce")
        print(f"  {c:26s} {s.notna().sum():,} con valor · media {s.mean():.3f} · vacíos {s.isna().sum():,}")


if __name__ == "__main__":
    main()
