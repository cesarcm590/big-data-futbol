"""
Calendario de TODA la temporada de las ligas europeas, desde openfootball (GitHub, abierto y sin credenciales).

POR QUÉ HACE FALTA
------------------
`football-data.co.uk/fixtures.csv` solo publica los partidos de los **dos o tres días siguientes**. Un miércoles
trae la jornada de media semana y nada más: el 28 de octubre de 2026 tenía 46 partidos, y de nuestras seis ligas
solo Serie A. Consecuencia visible: el panel no enseñaba ninguna jornada próxima en Premier, La Liga, Bundesliga,
Ligue 1 ni Eredivisie, y el selector de jornada se quedaba en la última jugada —la Bundesliga en la J7— como si
el torneo se hubiera acabado ahí.

openfootball publica el calendario completo de la temporada, así que la próxima jornada se puede enseñar siempre,
no solo cuando la fuente de resultados decide publicarla.

LOS NOMBRES SON EL PROBLEMA, Y POR ESO SE CONTROLAN
---------------------------------------------------
openfootball escribe «Borussia Dortmund» donde football-data escribe «Dortmund». El emparejamiento se hace solo,
por coincidencia de palabras, pero **un nombre mal emparejado o sin emparejar no se descarta en silencio**: el
script lo enseña y se niega a escribir el archivo. Un partido perdido por un nombre es exactamente el fallo que no
se ve —el calendario sale más corto y nadie lo nota—.

Salida: data/raw/fixtures_temporada.csv, en el MISMO formato que fixtures.csv de football-data (Div, Date, Time,
HomeTeam, AwayTeam, con los nombres tal como los escribe football-data) para que el exportador no necesite cambios.

Uso:  python scripts/calendario_temporada.py [--liga premier]
"""
import argparse
import json
import unicodedata
import urllib.request
from pathlib import Path

import pandas as pd

from ligas_europa import LIGAS_EUROPA, RAIZ

URL = "https://raw.githubusercontent.com/openfootball/football.json/master/{temporada}/{codigo}.json"
TEMPORADA_OF = "2026-27"
TEMPORADA_FD = "2627"
SALIDA = Path(RAIZ) / "data" / "raw" / "fixtures_temporada.csv"

# Equipos que el emparejamiento automático no resuelve y se fijan a mano. Se mantiene corto a propósito: cada
# entrada aquí es una coincidencia que el método no vio, y conviene saber cuántas son.
A_MANO = {
    # Los 16 que el método no resuelve, y ninguno por casualidad: todos son pares que comparten ciudad o apellido,
    # justo donde elegir "el más parecido" se equivocaría. Que sean 16 de 114 es el dato útil: el resto sale solo.
    "Manchester City FC": "Man City",                 # empata con Man United en «manchester»
    "Manchester United FC": "Man United",
    "Athletic Club": "Ath Bilbao",                    # «Ath» es Bilbao y Madrid a la vez en football-data
    "Club Atlético de Madrid": "Ath Madrid",
    "Rayo Vallecano de Madrid": "Vallecano",          # lleva «Madrid» y no es ninguno de los dos Madrid
    "Real Betis Balompié": "Betis",                   # «Real» lo comparten cuatro equipos
    "Real Racing Club de Santander": "Santander",
    "Real Sociedad de Fútbol": "Sociedad",
    "Bayer 04 Leverkusen": "Leverkusen",              # «Bayer» se confunde con «Bayern»
    "Borussia Mönchengladbach": "M'gladbach",         # football-data lo abrevia con apóstrofo
    "FC Internazionale Milano": "Inter",              # lleva «Milano» y no es el Milan
    "Paris FC": "Paris FC",                           # dos equipos de París en la misma liga
    "Paris Saint-Germain FC": "Paris SG",
    "Stade Rennais FC 1901": "Rennes",
    "Feyenoord Rotterdam": "Feyenoord",               # choca con Sparta Rotterdam
    "NEC": "Nijmegen",                                # football-data usa la ciudad, no las siglas
    # Este es el peligroso: football-data escribe «Espanol» SIN la y, así que no emparejaba por ahí, pero sí por
    # «Barcelona», que lleva en el nombre. Se iba entero al Barcelona sin empatar con nadie, así que ninguna
    # comprobación de ambigüedad lo veía: el Barça acababa con 66 partidos y el Espanyol con 8.
    "RCD Espanyol de Barcelona": "Espanol",
}


def normalizar(nombre: str) -> list[str]:
    """'Atlético Madrid' -> ['atletico', 'madrid']. Sin acentos, sin puntuación y sin palabras de relleno."""
    s = unicodedata.normalize("NFKD", str(nombre)).encode("ascii", "ignore").decode().lower()
    s = "".join(c if c.isalnum() else " " for c in s)
    relleno = {"fc", "cf", "sc", "ac", "as", "ss", "ssc", "afc", "cd", "ud", "rc", "sd", "us", "aj", "ogc",
               "losc", "rcd", "vfb", "vfl", "tsg", "sv", "bsc", "de", "el", "la", "los", "club", "1", "04",
               "05", "96", "1899", "1900", "1893", "08", "united", "city"}
    palabras = [p for p in s.split() if p and p not in relleno]
    return palabras or s.split()


def parecidas(a: list[str], b: list[str]) -> int:
    """Cuántas palabras coinciden, aceptando que una sea prefijo de la otra ('ath' con 'athletic')."""
    n = 0
    for x in a:
        for y in b:
            if x == y or (len(x) >= 3 and len(y) >= 3 and (x.startswith(y) or y.startswith(x))):
                n += 1
                break
    return n


def emparejar(nombres_of, nombres_fd):
    """openfootball -> football-data. Devuelve (mapa, sin_resolver)."""
    mapa, sin_resolver = {}, []
    for of in nombres_of:
        if of in A_MANO:
            mapa[of] = A_MANO[of]
            continue
        toks = normalizar(of)
        puntuados = sorted(((parecidas(toks, normalizar(fd)), fd) for fd in nombres_fd), reverse=True)
        mejor, segundo = puntuados[0], (puntuados[1] if len(puntuados) > 1 else (0, None))
        # Se exige que haya coincidencia Y que sea mejor que la siguiente: un empate entre dos candidatos es
        # justamente el caso en el que elegir al azar mete un partido con el equipo equivocado.
        if mejor[0] > 0 and mejor[0] > segundo[0]:
            mapa[of] = mejor[1]
        else:
            sin_resolver.append((of, [c for _, c in puntuados[:3]]))
    # Dos equipos distintos NO pueden ser el mismo: en una liga cada club es uno. Un destino repetido significa
    # que a uno se le robó el nombre del otro, y eso no empata con nadie —no hay ambigüedad que detectar—, así que
    # hay que comprobarlo aparte. Es lo que pasó con el Espanyol cayendo en el Barcelona.
    porque = {}
    for of, fd in mapa.items():
        porque.setdefault(fd, []).append(of)
    for fd, lista in porque.items():
        if len(lista) > 1:
            for of in lista:
                sin_resolver.append((of, [f"CHOCA con {[o for o in lista if o != of]} en «{fd}»"]))
            for of in lista:
                mapa.pop(of, None)
    return mapa, sin_resolver


def de_una_liga(clave: str, cfg: dict, verboso=True):
    codigo = cfg.get("openfootball")
    if not codigo:
        return pd.DataFrame(), []
    crudo = Path(RAIZ) / "data" / "raw" / cfg["carpeta_raw"] / f"{cfg['prefijo']}_{TEMPORADA_FD}.csv"
    if not crudo.exists():
        return pd.DataFrame(), [(f"(falta {crudo.name})", [])]
    jugados = pd.read_csv(crudo, encoding="utf-8-sig")
    nombres_fd = sorted(set(jugados["HomeTeam"].dropna()) | set(jugados["AwayTeam"].dropna()))

    with urllib.request.urlopen(URL.format(temporada=TEMPORADA_OF, codigo=codigo), timeout=60) as r:
        datos = json.load(r)
    partidos = datos.get("matches", [])
    nombres_of = sorted({m["team1"] for m in partidos} | {m["team2"] for m in partidos})

    mapa, sin_resolver = emparejar(nombres_of, nombres_fd)
    if verboso:
        print(f"{cfg['nombre']:16s} {len(partidos):3d} partidos · {len(nombres_of)} equipos · "
              f"{len(mapa)} emparejados" + (f" · {len(sin_resolver)} SIN RESOLVER" if sin_resolver else ""))
    if sin_resolver:
        return pd.DataFrame(), sin_resolver

    # Se descarta por CRUCE, no por fecha. Filtrar por «fecha posterior al último resultado» deja pasar los
    # partidos que ya se jugaron antes de lo previsto: openfootball mantenía ocho del Barcelona en su fecha
    # original de primavera cuando se habían adelantado a agosto, y el panel los contaba dos veces. Un cruce
    # local-visitante ocurre una sola vez por temporada, así que esa es la clave buena.
    ya_jugados = set(zip(jugados["HomeTeam"], jugados["AwayTeam"]))
    filas, repetidos = [], 0
    for m in partidos:
        f = pd.to_datetime(m.get("date"), errors="coerce")
        local, visita = mapa[m["team1"]], mapa[m["team2"]]
        if (local, visita) in ya_jugados:
            repetidos += 1
            continue
        if pd.isna(f):
            continue
        filas.append({"Div": cfg["div"], "Date": f.strftime("%d/%m/%Y"), "Time": m.get("time", "") or "",
                      "HomeTeam": local, "AwayTeam": visita})
    d = pd.DataFrame(filas)

    # Control: con el calendario entero, cada equipo tiene que sumar 2*(N-1) partidos entre jugados y por jugar, y
    # ningún cruce puede repetirse. Es la cuenta que usa el propio organizador para el sorteo, así que no la cumple
    # nada por casualidad; si falla, el calendario y los resultados no hablan del mismo torneo.
    equipos = sorted(set(nombres_fd) | set(mapa.values()))
    esperado = 2 * (len(equipos) - 1)
    largo = pd.concat([
        pd.concat([jugados[["HomeTeam", "AwayTeam"]], d[["HomeTeam", "AwayTeam"]]], ignore_index=True)
          .rename(columns={"HomeTeam": "eq"})[["eq"]],
        pd.concat([jugados[["HomeTeam", "AwayTeam"]], d[["HomeTeam", "AwayTeam"]]], ignore_index=True)
          .rename(columns={"AwayTeam": "eq"})[["eq"]],
    ], ignore_index=True)
    cuenta = largo["eq"].value_counts()
    descuadrados = cuenta[cuenta != esperado]
    if verboso:
        extra = f" · {repetidos} ya jugados descartados" if repetidos else ""
        estado = "✓" if descuadrados.empty else f"! {len(descuadrados)} equipos no suman {esperado}"
        print(f"   {estado} {len(equipos)} equipos, {len(d)} por jugar{extra}")
        if not descuadrados.empty:
            for eq, n in descuadrados.head(6).items():
                print(f"       {eq}: {n} partidos")
    return d, []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--liga", help="solo una liga (por defecto, todas las que tengan código de openfootball)")
    a = ap.parse_args()

    ligas = {a.liga: LIGAS_EUROPA[a.liga]} if a.liga else LIGAS_EUROPA
    trozos, problemas = [], {}
    for clave, cfg in ligas.items():
        d, sin_resolver = de_una_liga(clave, cfg)
        if sin_resolver:
            problemas[cfg["nombre"]] = sin_resolver
        elif len(d):
            trozos.append(d)

    if problemas:
        print("\n✗ NO se escribió nada: hay equipos sin emparejar y un partido perdido por un nombre no se ve.")
        for liga, lista in problemas.items():
            for nombre, candidatos in lista:
                print(f"   {liga}: «{nombre}» -> candidatos: {candidatos}")
        print("\n   Añádelos a A_MANO en este script y vuelve a correrlo.")
        return 1

    todo = pd.concat(trozos, ignore_index=True) if trozos else pd.DataFrame(
        columns=["Div", "Date", "Time", "HomeTeam", "AwayTeam"])
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    todo.to_csv(SALIDA, index=False)
    print(f"\n✓ {SALIDA.relative_to(RAIZ)}: {len(todo)} partidos por jugar")
    if len(todo):
        f = pd.to_datetime(todo["Date"], dayfirst=True)
        print(f"   del {f.min():%Y-%m-%d} al {f.max():%Y-%m-%d}")
        print(todo.groupby("Div").size().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
