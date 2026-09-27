"""
Resultados de competiciones de clubes leídos del wikitexto de Wikipedia, cuando no hay API que valga.

POR QUÉ ESTA FUENTE Y NO LA OFICIAL
-----------------------------------
  CAF        cafonline.com son noticias con widgets de Opta bajo clave de suscripción; no publica resultados.
  CONMEBOL   su web sirve `getOptaFixtures.php`, pero devuelve un CARRUSEL EN HTML de próximos partidos, no un
             feed de resultados.
  CONCACAF   renderiza los partidos en el servidor con Next.js; no expone JSON.
En los tres casos Wikipedia es lo único abierto y estructurado que los tiene.

DOS FORMATOS DISTINTOS, PORQUE WIKIPEDIA NO ES UNA FUENTE SINO MUCHAS
---------------------------------------------------------------------
  {{#invoke:Sports series}}  eliminatorias a doble partido (CAF y Libertadores). Una línea por cruce.
  {{Football box}}           un partido por plantilla, con fecha, marcador, estadio y asistencia (Concacaf).
Y los resultados suelen vivir en SUBARTÍCULOS, no en el principal: la Libertadores transcluye sus fases desde
«… qualifying stages» y «… final stages».

ESTO ES FRÁGIL, Y HAY QUE TRATARLO COMO TAL
-------------------------------------------
No es una API: es el texto fuente de un artículo que cualquiera puede reestructurar. Un cambio de formato no da
error, da SILENCIO —cero partidos, o peor, partidos mal leídos—. Por eso:

  1. Se guarda la REVISIÓN exacta que se parseó (`revid`), para poder reproducir o comparar.
  2. Se contrasta contra el propio artículo: el infobox declara cuántos partidos y cuántos goles lleva la ronda, y
     `control_contra_infobox` compara eso con lo que salió del parseo. Si no cuadra, algo cambió.
  3. Solo se acepta como jugado lo que encaja EXACTAMENTE con un marcador `n–n`. En este artículo, una eliminatoria
     sin decidir aparece como "FR6" y un partido sin jugar muestra la fecha ("3 October"): ambos deben quedar como
     no jugados, nunca interpretarse como un 0-0.

Cuidado con los guiones: el artículo mezcla el largo (–, U+2013) y el normal (-). Aceptar solo uno pierde
partidos en silencio.
"""
import re
from pathlib import Path

import pandas as pd
import requests

API = "https://en.wikipedia.org/w/api.php"
SALIDA = Path(__file__).resolve().parents[1] / "data" / "processed"
CABECERAS = {"User-Agent": "Big_data_futbol/1.0 (proyecto personal de análisis; "
                           "https://github.com/cesarcm590/big-data-futbol)"}
# Cada competición declara sus artículos y con qué parser se lee cada uno.
COMPETICIONES = {
    "caf": {
        "nombre": "CAF Champions League 2026-27", "confederacion": "CAF",
        "articulos": [("Rondas previas", "2026–27 CAF Champions League qualifying rounds", "serie"),
                      ("Fase de grupos", "2026–27 CAF Champions League group stage", "serie")],
    },
    "libertadores": {
        "nombre": "Copa Libertadores 2026", "confederacion": "CONMEBOL",
        # La fase de GRUPOS queda fuera: su artículo no usa ninguna de las dos plantillas y necesitaría un tercer
        # parser. Se dice en la web en vez de dar a entender que están todos los partidos.
        "articulos": [("Fases previas", "2026 Copa Libertadores qualifying stages", "serie"),
                      ("Fases finales", "2026 Copa Libertadores final stages", "serie")],
    },
    "concacaf": {
        "nombre": "Concacaf Champions Cup 2026", "confederacion": "CONCACAF",
        "articulos": [("Torneo", "2026 CONCACAF Champions Cup", "box")],
    },
}
# Acepta los cuatro guiones que aparecen en el artículo: cada editor escribe el suyo. Empezó aceptando solo el
# largo (–, U+2013) y se perdían 8 de 57 partidos, escritos con guion normal. El control contra el infobox fue
# lo que lo destapó; a ojo la tabla parecía correcta, solo incompleta.
MARCADOR = re.compile(r"^(\d+)\s*[–—\-\u2011]\s*(\d+)$")


def _partir_campos(linea: str) -> list[str]:
    """Parte por `|`, pero NO por los que van dentro de un enlace `[[destino|texto]]`.

    Es el detalle que hacía fallar el parseo entero: un enlace lleva su propio `|`, así que un `split('|')` a secas
    convierte `[[A|a]]` en dos campos y desalinea toda la fila. Se detectó porque el control contra el infobox
    daba 2 partidos donde Wikipedia declaraba 57.
    """
    campos, actual, profundidad = [], [], 0
    i = 0
    while i < len(linea):
        # Hay que proteger enlaces [[...]] Y plantillas {{...}}: las dos llevan `|` dentro. Lo segundo apareció con
        # la Libertadores, cuyo resultado global puede ser "2–2 {{pso|3–5}}" cuando se decidió por penales; sin
        # protegerlo, ese `|` partía el campo y desplazaba el nombre del rival al del marcador.
        if linea.startswith("[[", i) or linea.startswith("{{", i):
            profundidad += 1
            actual.append(linea[i:i + 2])
            i += 2
        elif linea.startswith("]]", i) or linea.startswith("}}", i):
            profundidad -= 1
            actual.append(linea[i:i + 2])
            i += 2
        elif linea[i] == "|" and profundidad == 0:
            campos.append("".join(actual).strip())
            actual = []
            i += 1
        else:
            actual.append(linea[i])
            i += 1
    campos.append("".join(actual).strip())
    return [c for c in campos if c]


def descargar_wikitexto(titulo: str) -> tuple[str, int, str]:
    """Devuelve (wikitexto, id de revisión, fecha de la revisión). Lanza si el artículo no existe."""
    r = requests.get(API, timeout=60, headers=CABECERAS, params={
        "action": "query", "prop": "revisions", "rvprop": "content|ids|timestamp",
        "rvslots": "main", "format": "json", "titles": titulo})
    r.raise_for_status()
    pagina = list(r.json()["query"]["pages"].values())[0]
    if "missing" in pagina:
        raise LookupError(f"Wikipedia no tiene el artículo «{titulo}»")
    rev = pagina["revisions"][0]
    return rev["slots"]["main"]["*"], rev["revid"], rev["timestamp"][:10]


def _nombre(celda: str) -> str:
    """'[[Atlético Petróleos de Luanda|Petro de Luanda]]' -> 'Petro de Luanda'."""
    m = re.search(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", celda)
    return (m.group(2) or m.group(1)).strip() if m else celda.strip()


def _marcador(celda: str) -> tuple[int | None, int | None]:
    """Solo acepta 'n–n'. Una fecha, un código de eliminatoria o un texto cualquiera devuelven (None, None)."""
    texto = re.sub(r"\[\[[^\]|]*\|?", "", celda).replace("]]", "").strip()
    texto = re.sub(r"\(.*?\)", "", texto).strip()      # quita notas como "(a)" de goles fuera o "(p)" de penales
    m = MARCADOR.match(texto)
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def parsear_eliminatorias(txt: str, ronda: str) -> pd.DataFrame:
    """Una fila por PARTIDO (no por eliminatoria): cada cruce a doble partido da hasta dos filas."""
    filas = []
    for bloque in re.findall(r"\{\{#invoke:Sports series\|main(.*?)\n\}\}", txt, re.S):
        for linea in bloque.split("\n"):
            partes = _partir_campos(linea)
            # Una eliminatoria son 7 campos: local, país, global, visitante, país, ida, vuelta.
            if len(partes) < 7 or "[[" not in partes[0]:
                continue
            local, pais_l, visitante, pais_v = _nombre(partes[0]), partes[1], _nombre(partes[3]), partes[4]
            for i, (mano, invertido) in enumerate([(partes[5], False), (partes[6], True)], start=1):
                gl, gv = _marcador(mano)
                # En la vuelta los equipos cambian de campo: el visitante del cruce juega en casa.
                filas.append({
                    "ronda": ronda, "partido": f"{'Ida' if i == 1 else 'Vuelta'}",
                    "local": visitante if invertido else local,
                    "visitante": local if invertido else visitante,
                    "local_pais": pais_v if invertido else pais_l,
                    "visitante_pais": pais_l if invertido else pais_v,
                    "goles_local": gl, "goles_visitante": gv,
                })
    d = pd.DataFrame(filas)
    if len(d):
        d["jugado"] = d["goles_local"].notna() & d["goles_visitante"].notna()
    return d


def control_contra_infobox(txt: str, d: pd.DataFrame) -> dict:
    """Compara lo parseado con lo que el propio artículo declara en su infobox. Es la red de seguridad del método."""
    def campo(nombre):
        m = re.search(rf"\|\s*{nombre}\s*=\s*(\d+)", txt)
        return int(m.group(1)) if m else None

    jugados = d[d["jugado"]] if len(d) else d
    goles = int((jugados["goles_local"] + jugados["goles_visitante"]).sum()) if len(jugados) else 0
    dice, dice_goles = campo("matches"), campo("goals")
    # El infobox lo mantiene una persona a mano y trae su propia fecha de actualización, que suele ir por detrás del
    # cuerpo del artículo. Se publica esa fecha junto a los números para que un desfase pequeño se pueda interpretar
    # en vez de parecer un fallo del parseo. Lo que NO se hace es aflojar la comparación: un desfase grande tiene que
    # cantar.
    m = re.search(r"\|\s*updated\s*=\s*(.+)", txt)
    # Tres estados, no dos. "sin control" NO es lo mismo que "no cuadra": significa que el artículo no declara
    # totales (los subartículos de la Libertadores, por ejemplo), así que no hay nada contra lo que contrastar y la
    # cifra se publica a ciegas. Mezclarlo con "no cuadra" ocultaría que ahí no hay red de seguridad.
    if dice is None and dice_goles is None:
        estado = "sin control"
    elif len(jugados) == dice and goles == dice_goles:
        estado = "cuadra"
    else:
        estado = "no cuadra"
    return {"partidos_parseados": len(jugados), "partidos_segun_wikipedia": dice,
            "goles_parseados": goles, "goles_segun_wikipedia": dice_goles,
            "infobox_actualizado": m.group(1).strip() if m else None,
            "control": estado, "cuadra": estado == "cuadra"}


def parsear_football_box(txt: str, ronda: str) -> pd.DataFrame:
    """Un partido por plantilla `{{Football box}}`: fecha, equipos, marcador, estadio y asistencia.

    Es el formato de Concacaf. Más rico que `Sports series`, pero también más verboso: los campos van con nombre,
    así que se leen por clave y no por posición.
    """
    filas = []
    for bloque in re.findall(r"\{\{[Ff]ootball box(.*?)\n\}\}", txt, re.S):
        campos = {}
        for linea in bloque.split("\n|"):
            if "=" not in linea:
                continue
            k, _, v = linea.partition("=")
            campos[k.strip().lstrip("|").strip()] = v.strip()
        gl, gv = _marcador(campos.get("score", ""))
        f = re.search(r"\{\{Start date\|(\d+)\|(\d+)\|(\d+)", campos.get("date", ""))
        filas.append({
            "ronda": ronda, "partido": "",
            "fecha": f"{f.group(1)}-{int(f.group(2)):02d}-{int(f.group(3)):02d}" if f else None,
            "local": _nombre(campos.get("team1", "")),
            "visitante": _nombre(campos.get("team2", "")),
            "local_pais": (re.search(r"fbaicon\|(\w+)", campos.get("team1", "")) or [None, None])[1],
            "visitante_pais": (re.search(r"fbaicon\|(\w+)", campos.get("team2", "")) or [None, None])[1],
            "goles_local": gl, "goles_visitante": gv,
        })
    d = pd.DataFrame(filas)
    if len(d):
        d["jugado"] = d["goles_local"].notna() & d["goles_visitante"].notna()
    return d


PARSERS = {"serie": parsear_eliminatorias, "box": parsear_football_box}


def actualizar(clave: str) -> tuple[pd.DataFrame, dict]:
    """Baja y parsea los artículos de una competición. Los que aún no existen se saltan sin romper.

    Un artículo ausente no es un error: la fase de grupos de CAF no existe hasta que empieza (27 nov 2026).
    """
    cfg = COMPETICIONES[clave]
    trozos, controles = [], {}
    for ronda, titulo, tipo in cfg["articulos"]:
        try:
            txt, rev, fecha = descargar_wikitexto(titulo)
        except LookupError:
            controles[ronda] = {"estado": "el artículo todavía no existe"}
            continue
        d = PARSERS[tipo](txt, ronda)
        controles[ronda] = {"revision": rev, "revision_fecha": fecha, **control_contra_infobox(txt, d)}
        trozos.append(d)

    todo = pd.concat(trozos, ignore_index=True) if trozos else pd.DataFrame()
    ruta = SALIDA / f"wikipedia_{clave}.csv"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    todo.to_csv(ruta, index=False)
    return todo, controles
