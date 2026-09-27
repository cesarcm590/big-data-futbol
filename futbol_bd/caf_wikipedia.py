"""
Resultados de la CAF Champions League, leídos del wikitexto de Wikipedia.

POR QUÉ ESTA FUENTE Y NO LA OFICIAL
-----------------------------------
cafonline.com no publica calendario ni resultados: es un sitio de noticias con widgets de Opta incrustados, y esos
datos van con clave de suscripción. Wikipedia es lo único abierto que los tiene.

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
ARTICULOS = {
    "Rondas previas": "2026–27 CAF Champions League qualifying rounds",
    "Fase de grupos": "2026–27 CAF Champions League group stage",
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
        if linea.startswith("[[", i):
            profundidad += 1
            actual.append("[[")
            i += 2
        elif linea.startswith("]]", i):
            profundidad -= 1
            actual.append("]]")
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
    return {"partidos_parseados": len(jugados), "partidos_segun_wikipedia": dice,
            "goles_parseados": goles, "goles_segun_wikipedia": dice_goles,
            "infobox_actualizado": m.group(1).strip() if m else None,
            "cuadra": dice is not None and len(jugados) == dice and goles == dice_goles}


def actualizar() -> tuple[pd.DataFrame, dict]:
    """Baja y parsea los artículos disponibles. Los que aún no existen se saltan sin romper.

    La fase de grupos no tiene artículo hasta que empieza (27 de noviembre de 2026): eso no es un error, es que
    todavía no se juega.
    """
    trozos, controles = [], {}
    for ronda, titulo in ARTICULOS.items():
        try:
            txt, rev, fecha = descargar_wikitexto(titulo)
        except LookupError:
            controles[ronda] = {"estado": "el artículo todavía no existe"}
            continue
        d = parsear_eliminatorias(txt, ronda)
        controles[ronda] = {"revision": rev, "revision_fecha": fecha, **control_contra_infobox(txt, d)}
        trozos.append(d)

    todo = pd.concat(trozos, ignore_index=True) if trozos else pd.DataFrame()
    ruta = SALIDA / "caf_champions_2026_27.csv"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    todo.to_csv(ruta, index=False)
    return todo, controles
