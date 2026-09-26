"""
Cuerpo arbitral de Euro y Nations League: quién dirige, de dónde es, y si eso se nota en el resultado.

OBRA DERIVADA — ver LICENSE en esta misma carpeta (CC BY-NC-SA 4.0, Petro Ivaniuk).

Por qué existe: el proyecto ya miró el sesgo arbitral en Liga MX (notebook 14). El fútbol de selecciones permite una
pregunta que en clubes no se puede hacer, porque UEFA designa árbitro NEUTRAL: se puede comprobar que la neutralidad
se cumple, y medir si aun así unos árbitros acaban con más victorias locales que otros.

Un aviso que vale más que el propio análisis: con 10-16 partidos por árbitro, la diferencia entre el que menos
victorias locales acumula (17%) y el que más (64%) es **ruido**. `dispersion_es_azar` lo demuestra simulando el
mundo en el que ningún árbitro influye, en vez de dejar que los porcentajes sugieran un hallazgo que no existe.
"""
import ast
import glob
from pathlib import Path

import numpy as np
import pandas as pd

CRUDOS = Path(__file__).resolve().parents[1] / "data" / "raw" / "euro_nations_kaggle" / "matches" / "matches"


def cargar_partidos(carpetas=("nations", "euro")) -> pd.DataFrame:
    """Partidos de Euro y Nations League con el árbitro principal y su país ya extraídos."""
    arch = [f for c in carpetas for f in sorted(glob.glob(str(CRUDOS / c / "*.csv")))]
    if not arch:
        raise FileNotFoundError("No hay datos. Corre antes: python scripts/descargar_euro_nations.py")
    d = pd.concat([pd.read_csv(f) for f in arch], ignore_index=True)
    d = d[d["game_referees"].notna() & d["home_score"].notna()].copy()
    # `game_referees` viene como el texto de una lista de diccionarios, no como JSON: se lee con ast, no con json.
    # Ojo con el nombre del campo de país: la fuente lo escribe mal, "counrty_code".
    equipo = d["game_referees"].apply(ast.literal_eval)
    d["arbitro"] = equipo.apply(lambda rs: next((r.get("name") for r in rs if r.get("role") == "REFEREE"), None))
    d["arbitro_pais"] = equipo.apply(lambda rs: next((r.get("counrty_code") for r in rs if r.get("role") == "REFEREE"), None))
    d["local_gana"] = d["home_score"] > d["away_score"]
    return d


def neutralidad(d: pd.DataFrame) -> pd.DataFrame:
    """Partidos donde el árbitro era del país de alguno de los dos equipos. Debe salir vacío."""
    return d[(d["arbitro_pais"] == d["home_team_code"]) | (d["arbitro_pais"] == d["away_team_code"])]


def dispersion_es_azar(d: pd.DataFrame, min_partidos: int = 10, simulaciones: int = 10_000,
                       semilla: int = 7) -> dict:
    """¿La diferencia de victorias locales entre árbitros es mayor de lo que daría el puro azar?

    Se compara la horquilla observada (máximo menos mínimo) contra la de miles de mundos simulados en los que todos
    los árbitros son idénticos y solo actúa el azar, respetando cuántos partidos dirigió cada uno. Es la forma
    honesta de mirar un porcentaje calculado sobre docenas de partidos: sin esto, cualquier muestra pequeña produce
    extremos llamativos.
    """
    rng = np.random.default_rng(semilla)
    cuenta = d["arbitro"].value_counts()
    cuenta = cuenta[cuenta >= min_partidos]
    obs = d[d["arbitro"].isin(cuenta.index)].groupby("arbitro")["local_gana"].mean()
    p = d["local_gana"].mean()
    real = obs.max() - obs.min()
    sim = np.array([[rng.binomial(n, p) / n for n in cuenta.values] for _ in range(simulaciones)])
    rangos = sim.max(axis=1) - sim.min(axis=1)
    return {"arbitros": len(cuenta), "media_local": p, "horquilla_real": real,
            "horquilla_azar_mediana": float(np.median(rangos)),
            "horquilla_azar_p95": float(np.quantile(rangos, 0.95)),
            "p_valor": float((rangos >= real).mean())}
