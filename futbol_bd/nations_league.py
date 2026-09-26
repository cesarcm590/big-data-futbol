"""
Seguimiento de la UEFA Nations League en curso, desde la API pública de UEFA.

POR QUÉ NO SALE DEL CONJUNTO DE KAGGLE
--------------------------------------
El conjunto de Euro y Nations League (`selecciones/`) llega hasta 2025: la edición 2026-27 no está. Esta se toma de
UEFA directamente, y por eso vive AQUÍ y no en `selecciones/`: aquella carpeta es obra derivada de un conjunto
CC BY-NC-SA y mezclar ambas fuentes borraría esa frontera, que existe precisamente para no contagiar la licencia al
resto del proyecto.

CÓMO SE ENCONTRÓ EL ENDPOINT
----------------------------
La web de UEFA no incrusta los datos ni expone parámetros en el HTML, así que se localizó por sondeo:
  1. `comp.uefa.com/v2/competitions` (200) lista las competiciones -> Nations League es competitionId 2014.
  2. `comp.uefa.com/v2/competitions/2014/seasons` da las temporadas -> la actual es seasonYear 2027.
  3. `match.uefa.com/v5/matches` responde SOLO con competitionId + seasonYear + limit + offset. Añadirle el
     `phase=ALL` que aparece en otros ejemplos devuelve 404.
`robots.txt` de UEFA no prohíbe estas rutas. Una sola petición trae los 156 partidos de la edición, así que el
seguimiento no necesita insistir: se pide todo de una vez.
"""
from pathlib import Path

import pandas as pd
import requests

COMPETICION_NATIONS = 2014
TEMPORADA_ACTUAL = 2027                 # la edición 2026-27; UEFA la nombra por el año en que termina
URL = "https://match.uefa.com/v5/matches"
SALIDA = Path(__file__).resolve().parents[1] / "data" / "processed" / "nations_league_2026_27.csv"
ROLES = {"REFEREE": "arbitro", "ASSISTANT_REFEREE_1": "asistente_1", "ASSISTANT_REFEREE_2": "asistente_2",
         "FOURTH_OFFICIAL": "cuarto", "VIDEO_ASSISTANT_REFEREE": "var"}

# UEFA rechaza con 403 el User-Agent que `requests` manda por defecto ("python-requests/x.y"), pero acepta cualquier
# otro. Se pone uno que DIGA QUIÉN LLAMA y dónde está el proyecto, en vez de disfrazarse de navegador: si a UEFA le
# molesta este tráfico, que pueda identificarlo y no tenga que bloquear a ciegas.
CABECERAS = {
    "Accept": "application/json",
    "User-Agent": "Big_data_futbol/1.0 (proyecto personal de análisis; "
                  "https://github.com/cesarcm590/big-data-futbol)",
}


IDIOMA = "ES"                           # UEFA traduce nombres de equipo, liga y jornada; el dashboard va en español


def _texto(x, *claves, idioma=IDIOMA):
    """Saca un campo traducido del anidamiento de UEFA, devolviendo None en vez de reventar si falta un nivel.

    Si el idioma pedido no está, cae a inglés y luego a cualquier valor disponible. No es cosmético: pedir 'ES' a
    secas dejaba vacío el nombre del árbitro en cuanto UEFA no traducía ese campo, y un nombre ausente no se nota
    hasta que alguien mira la tabla.
    """
    for c in claves:
        x = x.get(c) if isinstance(x, dict) else None
        if x is None:
            return None
    if not isinstance(x, dict):
        return x
    return x.get(idioma) or x.get("EN") or next((v for v in x.values() if v), None)


def descargar(competicion: int = COMPETICION_NATIONS, temporada: int = TEMPORADA_ACTUAL) -> list[dict]:
    r = requests.get(URL, params={"competitionId": competicion, "seasonYear": temporada,
                                  "limit": 500, "offset": 0}, timeout=60, headers=CABECERAS)
    r.raise_for_status()
    return r.json()


def a_tabla(crudo: list[dict]) -> pd.DataFrame:
    """Una fila por partido, con el árbitro principal y su país ya resueltos."""
    filas = []
    for m in crudo:
        arb = next((r for r in (m.get("referees") or []) if r.get("role") == "REFEREE"), None)
        persona = (arb or {}).get("person", {})
        marcador = m.get("score") or {}
        total = marcador.get("total") or {}
        filas.append({
            "match_id": m.get("id"),
            "fecha": (m.get("kickOffTime") or {}).get("dateTime", "")[:10],
            "hora": (m.get("kickOffTime") or {}).get("dateTime", "")[11:16],
            # `leagueName` NO está traducido (siempre "League A"); el nombre en español vive en translations.
            "liga": _texto(m, "group", "league", "translations", "name")
                    or ((m.get("group") or {}).get("league") or {}).get("metaData", {}).get("leagueName") or "",
            # Ojo: el grupo es `metaData.groupName`, no `metaData.name`. Con la clave equivocada salía vacío y las
            # tablas de posiciones habrían agrupado los 54 equipos en cuatro bloques en vez de en catorce grupos.
            "grupo": ((m.get("group") or {}).get("metaData") or {}).get("groupName") or "",
            "jornada": (m.get("matchday") or {}).get("longName", ""),
            "local": _texto(m, "homeTeam", "translations", "displayName") or (m.get("homeTeam") or {}).get("internationalName"),
            "visitante": _texto(m, "awayTeam", "translations", "displayName") or (m.get("awayTeam") or {}).get("internationalName"),
            "local_cod": (m.get("homeTeam") or {}).get("countryCode"),
            "visitante_cod": (m.get("awayTeam") or {}).get("countryCode"),
            "goles_local": total.get("home"),
            "goles_visitante": total.get("away"),
            "estado": m.get("status"),
            "arbitro": _texto(persona, "translations", "name") or persona.get("internationalName"),
            "arbitro_pais": persona.get("countryCode"),
            "estadio": _texto(m, "stadium", "translations", "officialName"),
        })
    d = pd.DataFrame(filas).sort_values(["fecha", "hora"]).reset_index(drop=True)
    d["jugado"] = d["estado"].eq("FINISHED")
    return d


def comprobar_neutralidad(d: pd.DataFrame) -> pd.DataFrame:
    """UEFA designa árbitro neutral. Si esto devuelve algo, o hay un error de datos o una excepción que explicar."""
    con = d[d["arbitro_pais"].notna()]
    return con[(con["arbitro_pais"] == con["local_cod"]) | (con["arbitro_pais"] == con["visitante_cod"])]


def actualizar(ruta: Path = SALIDA) -> tuple[pd.DataFrame, dict]:
    """Baja, guarda y dice qué cambió respecto a la instantánea anterior."""
    nueva = a_tabla(descargar())
    antes = pd.read_csv(ruta) if ruta.exists() else None
    ruta.parent.mkdir(parents=True, exist_ok=True)
    nueva.to_csv(ruta, index=False)
    resumen = {"partidos": len(nueva), "jugados": int(nueva["jugado"].sum()),
               "en_vivo": int(nueva["estado"].eq("LIVE").sum()),
               "nuevos_resultados": 0, "fallos_neutralidad": len(comprobar_neutralidad(nueva))}
    if antes is not None:
        ya = set(antes.loc[antes["estado"].eq("FINISHED"), "match_id"])
        resumen["nuevos_resultados"] = int((~nueva.loc[nueva["jugado"], "match_id"].isin(ya)).sum())
    return nueva, resumen


def tabla_de_posiciones(d: pd.DataFrame) -> pd.DataFrame:
    """Clasificación por grupo, contando solo lo jugado. Tres puntos por victoria, uno por empate.

    No aplica los desempates completos de UEFA (que empiezan por el enfrentamiento directo, no por la diferencia
    general de goles): con la fase de liga a medias no tendría sentido fingir una precisión que no cambia nada.
    Se ordena por puntos y diferencia, y así se dice en la página.
    """
    j = d[d["jugado"] & d["grupo"].notna() & d["grupo"].ne("")]
    filas = []
    for lado, gf, gc in [("local", "goles_local", "goles_visitante"), ("visitante", "goles_visitante", "goles_local")]:
        t = j[["liga", "grupo", lado, gf, gc]].rename(columns={lado: "equipo", gf: "a_favor", gc: "en_contra"})
        filas.append(t)
    t = pd.concat(filas, ignore_index=True)
    t["puntos"] = (t["a_favor"] > t["en_contra"]) * 3 + (t["a_favor"] == t["en_contra"]) * 1
    g = t.groupby(["liga", "grupo", "equipo"], as_index=False).agg(
        pj=("puntos", "size"), puntos=("puntos", "sum"),
        a_favor=("a_favor", "sum"), en_contra=("en_contra", "sum"))
    g["dif"] = g["a_favor"] - g["en_contra"]
    return g.sort_values(["liga", "grupo", "puntos", "dif", "a_favor"],
                         ascending=[True, True, False, False, False]).reset_index(drop=True)
