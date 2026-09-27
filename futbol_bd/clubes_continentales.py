"""
Resultados de las competiciones continentales de clubes, confederación por confederación.

POR QUÉ NO HAY UNA SOLA FUENTE
------------------------------
Cada confederación publica lo suyo a su manera, así que esto crece de una en una y no de golpe:

  AFC   API pública y limpia. `api.the-afc.com/sportdb-connector/api/v1/live/fixtures` acepta competición,
        temporada y rango de fechas, y devuelve resultado, árbitros, estadio y fase. Internamente los datos son de
        Opta, pero AFC los expone sin clave.
  CAF   NO se pudo. cafonline.com es un sitio de noticias con widgets de Opta incrustados
        (`secure.widget.cloud.opta.net`), y esos datos van con clave de suscripción. No se encontró ninguna página
        pública de calendario o resultados de la que leerlos.
  UEFA  el mismo `match.uefa.com/v5/matches` de la Nations League, cambiando `competitionId` a 1 (Champions) y
        `seasonYear` a 2027. Es la única de las tres que además publica la NACIONALIDAD del árbitro, así que aquí
        sí se puede comprobar que UEFA designa colegiados neutrales; con AFC no se puede y con CAF tampoco.
  CONMEBOL y CONCACAF  por mirar.

El calendario de todas ellas sí está, en `referencia/calendario_internacional.csv`: qué se juega y cuándo. Lo que
falta es el detalle partido a partido.
"""
from pathlib import Path

import pandas as pd
import requests

SALIDA = Path(__file__).resolve().parents[1] / "data" / "processed"
# Mismo criterio que con UEFA: una cabecera que identifique el proyecto, no un disfraz de navegador.
CABECERAS = {
    "Accept": "application/json",
    "User-Agent": "Big_data_futbol/1.0 (proyecto personal de análisis; "
                  "https://github.com/cesarcm590/big-data-futbol)",
}

AFC = {
    "url": "https://api.the-afc.com/sportdb-connector/api/v1/live/fixtures",
    "competicion": "afc-champions-league-elite",
    "temporada": 20262027,
    "nombre": "AFC Champions League Elite 2026-27",
}


def descargar_afc(cfg: dict = AFC, desde: str = "2026-08-01", hasta: str = "2027-06-30") -> list[dict]:
    """Todos los partidos de la edición. El rango de fechas es obligatorio en esta API, no opcional."""
    r = requests.get(cfg["url"], timeout=60, headers=CABECERAS, params={
        "competitionCodes": cfg["competicion"], "season": cfg["temporada"], "locale": "en",
        "dateFrom": desde, "dateTo": hasta, "limitBefore": 500, "limitAfter": 500,
    })
    r.raise_for_status()
    return r.json().get("data", [])


def a_tabla_afc(crudo: list[dict]) -> pd.DataFrame:
    """Una fila por partido. `result` solo trae marcador cuando el partido se jugó."""
    filas = []
    for m in crudo:
        res = m.get("result") or {}
        # El árbitro principal tiene role exactamente "Referee"; los asistentes son "Assistant referee 1" y 2, así
        # que no vale un `in`: hay que comparar el rol entero o se cuela el primer asistente.
        arb = next((a for a in (m.get("referees") or []) if str(a.get("role", "")).strip().lower() == "referee"), None)
        filas.append({
            "match_id": m.get("matchId"),
            "fecha": m.get("dateVenue"),
            "hora": (m.get("timeVenueUTC") or "")[:5],
            "fase": (m.get("stage") or {}).get("name") or "",
            "grupo": (m.get("group") or {}).get("name") or "",   # null en las rondas previas
            "local": (m.get("homeTeam") or {}).get("name"),
            "visitante": (m.get("awayTeam") or {}).get("name"),
            "local_pais": (m.get("homeTeam") or {}).get("countryCode"),
            "visitante_pais": (m.get("awayTeam") or {}).get("countryCode"),
            "goles_local": res.get("homeGoals"),
            "goles_visitante": res.get("awayGoals"),
            "estado": m.get("status"),
            "estadio": (m.get("stadium") or {}).get("name"),
            "arbitro": (arb or {}).get("refereeName"),
            # AFC NO publica la nacionalidad del árbitro, a diferencia de UEFA. Se deja la columna para que el
            # formato sea el mismo, pero queda vacía: el control de neutralidad no se puede hacer con estos datos.
            "arbitro_pais": (arb or {}).get("countryCode"),
        })
    d = pd.DataFrame(filas).sort_values(["fecha", "hora"]).reset_index(drop=True)
    # `status` vale 'played', 'fixture', 'playing'... Se normaliza a un booleano para no depender de sus literales.
    d["jugado"] = d["estado"].eq("played") & d["goles_local"].notna()
    return d


def actualizar_afc() -> tuple[pd.DataFrame, dict]:
    ruta = SALIDA / "afc_champions_elite_2026_27.csv"
    nueva = a_tabla_afc(descargar_afc())
    antes = pd.read_csv(ruta) if ruta.exists() else None
    ruta.parent.mkdir(parents=True, exist_ok=True)
    nueva.to_csv(ruta, index=False)
    resumen = {"competicion": AFC["nombre"], "partidos": len(nueva), "jugados": int(nueva["jugado"].sum()),
               "con_arbitro": int(nueva["arbitro"].notna().sum()), "nuevos": 0}
    if antes is not None:
        ya = set(antes.loc[antes["jugado"] == True, "match_id"])  # noqa: E712  (viene de CSV, puede ser texto)
        resumen["nuevos"] = int((~nueva.loc[nueva["jugado"], "match_id"].isin(ya)).sum())
    return nueva, resumen


# --- UEFA Champions League ---------------------------------------------------------------------------------------
UCL = {"competicion": 1, "temporada": 2027, "nombre": "UEFA Champions League 2026-27"}


def descargar_ucl(cfg: dict = UCL) -> list[dict]:
    """Reutiliza el endpoint de UEFA que ya usa la Nations League; solo cambian competición y temporada."""
    from futbol_bd import nations_league
    return nations_league.descargar(cfg["competicion"], cfg["temporada"])


def a_tabla_ucl(crudo: list[dict]) -> pd.DataFrame:
    """Una fila por partido. Mismo formato que AFC para que la web pueda tratarlas igual."""
    from futbol_bd.nations_league import _texto

    filas = []
    for m in crudo:
        arb = next((r for r in (m.get("referees") or []) if r.get("role") == "REFEREE"), None)
        persona = (arb or {}).get("person", {})
        total = (m.get("score") or {}).get("total") or {}
        filas.append({
            "match_id": m.get("id"),
            "fecha": (m.get("kickOffTime") or {}).get("dateTime", "")[:10],
            "hora": (m.get("kickOffTime") or {}).get("dateTime", "")[11:16],
            # En la Champions la "fase" es la ronda (fase de liga, octavos...) y el "grupo" es siempre "League"
            # durante la fase de liga: se guarda la ronda, que es lo que distingue de verdad.
            "fase": _texto(m, "round", "translations", "name") or (m.get("round") or {}).get("metaData", {}).get("name", ""),
            "grupo": ((m.get("group") or {}).get("metaData") or {}).get("groupName") or "",
            "local": _texto(m, "homeTeam", "translations", "displayName") or (m.get("homeTeam") or {}).get("internationalName"),
            "visitante": _texto(m, "awayTeam", "translations", "displayName") or (m.get("awayTeam") or {}).get("internationalName"),
            "local_pais": (m.get("homeTeam") or {}).get("countryCode"),
            "visitante_pais": (m.get("awayTeam") or {}).get("countryCode"),
            "goles_local": total.get("home"),
            "goles_visitante": total.get("away"),
            "estado": m.get("status"),
            "estadio": _texto(m, "stadium", "translations", "officialName"),
            "arbitro": _texto(persona, "translations", "name"),
            "arbitro_pais": persona.get("countryCode"),
            "asistencia": m.get("matchAttendance"),
        })
    d = pd.DataFrame(filas).sort_values(["fecha", "hora"]).reset_index(drop=True)
    d["jugado"] = d["estado"].eq("FINISHED") & d["goles_local"].notna()
    return d


def neutralidad_ucl(d: pd.DataFrame) -> pd.DataFrame:
    """Partidos con árbitro del país de alguno de los dos clubes. UEFA designa neutral, así que debe salir vacío."""
    con = d[d["arbitro_pais"].notna()]
    return con[(con["arbitro_pais"] == con["local_pais"]) | (con["arbitro_pais"] == con["visitante_pais"])]


def actualizar_ucl() -> tuple[pd.DataFrame, dict]:
    ruta = SALIDA / "uefa_champions_2026_27.csv"
    nueva = a_tabla_ucl(descargar_ucl())
    antes = pd.read_csv(ruta) if ruta.exists() else None
    ruta.parent.mkdir(parents=True, exist_ok=True)
    nueva.to_csv(ruta, index=False)
    resumen = {"competicion": UCL["nombre"], "partidos": len(nueva), "jugados": int(nueva["jugado"].sum()),
               "fallos_neutralidad": len(neutralidad_ucl(nueva)), "nuevos": 0}
    if antes is not None and "jugado" in antes:
        ya = set(antes.loc[antes["jugado"] == True, "match_id"])  # noqa: E712
        resumen["nuevos"] = int((~nueva.loc[nueva["jugado"], "match_id"].isin(ya)).sum())
    return nueva, resumen
