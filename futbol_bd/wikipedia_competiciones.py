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

Además un artículo puede TRANSCLUIR otro entero con `{{:Título}}`, y `prop=revisions` devuelve el wikitexto sin
expandir: lo transcluido no está en el texto que se parsea. Así se perdía la final de la Concacaf, que vive en su
propio artículo y entra en el principal como `{{:2026 CONCACAF Champions Cup final}}`. Por eso se resuelven antes
de parsear; ver `resolver_transclusiones`.

Y un artículo puede mezclar los dos formatos: el de fases finales de la Libertadores lleva sus eliminatorias en
`Sports series` pero la final, que es a partido único, en un `{{Football box}}` suelto. Parsear el artículo entero
con los dos parsers duplicaría todo —en el de CAF conviven 2 `Sports series` con 90 `Football box`, que son los
mismos partidos contados dos veces—, así que cada entrada de `articulos` puede declarar además UNA SECCIÓN, y solo
esa se lee con el otro parser. Se recorta por las marcas `<section begin=… />` del propio artículo.

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
        # La FINAL es a partido único y va en un `{{Football box}}` dentro del mismo artículo de fases finales, que
        # se lee con el parser de eliminatorias. Sin esta entrada se perdía en silencio el 28 nov 2026, y ahí no hay
        # control que avise porque el artículo no declara totales.
        "articulos": [("Fases previas", "2026 Copa Libertadores qualifying stages", "serie"),
                      ("Fases finales", "2026 Copa Libertadores final stages", "serie"),
                      ("Final", "2026 Copa Libertadores final stages", "box", "Final")],
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


# Una línea que es solo `{{:Título}}` transcluye ese artículo COMPLETO. Wikipedia lo usa para que la sección «Match»
# de la final muestre el artículo propio de la final en vez de duplicarlo. Ojo con lo que NO es esto: `{{main|X}}`
# es un simple «véase» y no aporta contenido, y `{{Plantilla|...}}` (sin los dos puntos) es una plantilla normal.
TRANSCLUSION = re.compile(r"^\{\{:\s*([^}|\n]+?)\s*\}\}\s*$", re.M)


def resolver_transclusiones(txt: str, descargar=descargar_wikitexto) -> tuple[str, dict]:
    """Sustituye cada `{{:Título}}` por el wikitexto de ese artículo, como hace MediaWiki al renderizar.

    POR QUÉ EXISTE: sin esto los partidos transcluidos no existen para el parseo, y no da error, da un número más
    bajo. Es el fallo que dejaba la Concacaf en 50 partidos de 51 —faltaba la final, Toluca 1–1 Tigres, sus 2 goles
    eran exactamente el desfase de 147 a 149 que cantaba el control—.

    UN SOLO NIVEL, a propósito: encadenar transclusiones multiplicaría las descargas y abriría la puerta a un ciclo.
    Si algún día hiciera falta más profundidad, el control contra el infobox volverá a avisar.

    Devuelve el texto expandido y las revisiones de lo que se incrustó, porque la revisión del artículo principal ya
    no basta para reproducir el parseo.
    """
    incrustados = {}

    def sustituir(m):
        titulo = m.group(1).strip()
        try:
            sub, rev, fecha = descargar(titulo)
        except LookupError:
            # Un rojo en Wikipedia: la sección queda vacía. Se anota, no se rompe.
            incrustados[titulo] = {"estado": "el artículo transcluido no existe"}
            return ""
        incrustados[titulo] = {"revision": rev, "revision_fecha": fecha}
        return sub

    return TRANSCLUSION.sub(sustituir, txt), incrustados


# Lo que va en un comentario HTML no se renderiza, así que tampoco debe parsearse. Hoy no cambia ninguna cifra (lo
# comprobé artículo por artículo), pero los tres artículos tienen transclusiones comentadas —instrucciones para
# editores, del tipo «para incluir esta tabla usa {{:…}}»—, y una de ellas a solas en su línea entraría por
# `resolver_transclusiones` e incrustaría un artículo que el lector no ve. Se quitan ANTES de resolver nada.
COMENTARIO = re.compile(r"<!--.*?-->", re.S)
# Wikipedia marca las secciones transcluibles así, con el nombre entre comillas o sin ellas según quién lo escribió.
SECCION = r"<section\s+begin\s*=\s*[\"']?{n}[\"']?\s*/>(.*?)<section\s+end\s*=\s*[\"']?{n}[\"']?\s*/>"


def _seccion(txt: str, nombre: str) -> str:
    """Recorta lo que hay entre `<section begin=Nombre />` y `<section end=Nombre />`; "" si no están.

    Sirve para leer con OTRO parser una sección de un artículo sin tocar el resto. Caso real: la final de la
    Libertadores es a partido único y va en un `{{Football box}}`, dentro de un artículo cuyas eliminatorias se leen
    con `Sports series`. Aplicar los dos parsers al artículo completo contaría los mismos partidos dos veces.

    Se usan las marcas del propio artículo y no el encabezado `==Final==` porque las marcas existen justamente para
    que otros artículos transcluyan ese trozo: mientras alguien las use, nadie las quita sin darse cuenta.
    """
    m = re.search(SECCION.format(n=re.escape(nombre)), txt, re.S)
    return m.group(1) if m else ""


def _nombre(celda: str) -> str:
    """'[[Atlético Petróleos de Luanda|Petro de Luanda]]' -> 'Petro de Luanda'.

    Sin enlace se devuelve el texto, pero sin las plantillas que lo acompañan: un equipo aún por decidir se escribe
    `Higher-seeded finalist {{fbaicon|}}` (la bandera vacía), y arrastrar ese `{{fbaicon|}}` al nombre lo ensucia.
    """
    m = re.search(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", celda)
    if m:
        return (m.group(2) or m.group(1)).strip()
    return re.sub(r"\s+", " ", re.sub(r"\{\{[^{}]*\}\}", "", celda)).strip()


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
                # En la vuelta los equipos cambian de campo: el visitante del cruce juega en casa. Y HAY QUE DAR LA
                # VUELTA TAMBIÉN AL MARCADOR: en esta plantilla las dos manos se escriben SIEMPRE desde el primer
                # equipo de la fila, no desde el local de cada partido. El artículo lo confirma en sus propias cajas:
                # la fila dice «Wiliete … 4–0 | 1–0» y la caja del 10 sep dice «Foresters 0–1 Wiliete».
                # Sin este cambio la vuelta salía invertida: ganador y perdedor al revés en la mitad de los partidos.
                if invertido:
                    gl, gv = gv, gl
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


def control_cruzado_con_cajas(txt: str, d: pd.DataFrame) -> dict | None:
    """Contrasta la tabla de eliminatorias con el DETALLE partido a partido del mismo artículo.

    POR QUÉ HACE FALTA OTRO CONTROL. El de `control_contra_infobox` compara cuántos partidos y cuántos goles, y hay
    un error que no puede ver: **dar la vuelta a un marcador**. El número de partidos no cambia y la suma de goles
    tampoco; solo cambian el ganador y el perdedor. Así se publicaron las vueltas invertidas de CAF y Libertadores
    con el control en verde.

    Lo que sí lo ve es que el artículo cuenta los mismos partidos DOS VECES: la tabla de eliminatorias
    (`Sports series`) resume el cruce, y debajo hay un `{{Football box}}` por partido con su fecha y su estadio. Dos
    representaciones independientes de lo mismo: si no coinciden en equipos, orden y marcador, una de las dos está
    mal leída.

    Devuelve None cuando no hay con qué cruzar (un artículo sin cajas), que no es lo mismo que cruzar y no cuadrar.
    """
    if not len(d):
        return None
    cajas = parsear_football_box(txt, "")
    cajas = cajas[cajas["jugado"]] if len(cajas) else cajas
    if not len(cajas):
        return None

    # Multiconjunto: un mismo par de equipos puede aparecer dos veces (ida y vuelta con el mismo campo nominal).
    pendientes: dict[tuple, list] = {}
    for c in cajas.itertuples():
        pendientes.setdefault((c.local, c.visitante), []).append((int(c.goles_local), int(c.goles_visitante)))

    coinciden, discrepan, sin_caja = 0, [], 0
    for r in d[d["jugado"]].itertuples():
        marcador = (int(r.goles_local), int(r.goles_visitante))
        lista = pendientes.get((r.local, r.visitante))
        if not lista:
            # No hay caja de ese partido con ese local: puede ser que el artículo lo escriba con otro nombre.
            sin_caja += 1
        elif marcador in lista:
            lista.remove(marcador)
            coinciden += 1
        else:
            discrepan.append(f"{r.local} {marcador[0]}-{marcador[1]} {r.visitante}; "
                             f"la caja dice {lista[0][0]}-{lista[0][1]}")
    # Tres estados, como en el otro control. Un partido SIN CAJA no contradice nada: puede ser que el artículo aún
    # no la haya escrito. Una DISCREPANCIA sí: dos partes del mismo artículo dicen cosas distintas. Meterlos en el
    # mismo saco haría saltar la alarma por un artículo a medio escribir y le quitaría valor a la de verdad.
    estado = "no cuadra" if discrepan else ("cruzado en parte" if sin_caja else "cuadra")
    return {"cruzados_con_caja": coinciden, "sin_caja": sin_caja,
            "discrepan": len(discrepan), "ejemplos": discrepan[:3], "cruce": estado}


PARSERS = {"serie": parsear_eliminatorias, "box": parsear_football_box}


def leer_articulos(clave: str) -> tuple[pd.DataFrame, dict]:
    """Baja, expande y parsea los artículos de una competición. Los que aún no existen se saltan sin romper.

    Un artículo ausente no es un error: la fase de grupos de CAF no existe hasta que empieza (27 nov 2026).

    Está separado de `actualizar` porque el exportador del dashboard necesita justo esto —recalcular el control
    contra el artículo vivo— sin reescribir el CSV. Antes tenía su propia copia del bucle, y una copia es un sitio
    más donde arreglar el mismo fallo: la corrección de las transclusiones habría entrado solo en uno de los dos.
    """
    cfg = COMPETICIONES[clave]
    trozos, controles = [], {}
    bajados: dict[str, tuple] = {}     # un artículo puede aparecer en dos entradas (las fases y la final): una descarga
    # Cada entrada es (ronda, artículo, parser) y opcionalmente una CUARTA: la sección a recortar. Sin ella se lee el
    # artículo entero, que es el caso normal.
    for ronda, titulo, tipo, *resto in cfg["articulos"]:
        seccion = resto[0] if resto else None
        try:
            if titulo not in bajados:
                bajados[titulo] = descargar_wikitexto(titulo)
            txt, rev, fecha = bajados[titulo]
        except LookupError:
            controles[ronda] = {"estado": "el artículo todavía no existe"}
            continue
        txt = COMENTARIO.sub("", txt)
        # Antes de parsear: traer lo que el artículo transcluye de otros. Si no, esos partidos no existen.
        txt, incrustados = resolver_transclusiones(txt)
        if seccion:
            recorte = _seccion(txt, seccion)
            if not recorte:
                # No se devuelven 0 partidos en silencio: que la marca desaparezca es exactamente el fallo del que
                # esto protege, así que se dice. Aquí no hay infobox contra el que contrastar que lo cante.
                controles[ronda] = {"revision": rev, "revision_fecha": fecha,
                                    "estado": f"la sección «{seccion}» ya no está marcada en el artículo"}
                continue
            txt = recorte
        d = PARSERS[tipo](txt, ronda)
        if seccion and not len(d):
            # La marca sigue ahí pero dentro ya no hay ninguna plantilla de partido. Como el control de un recorte es
            # siempre «sin control» (no hay infobox que recortar), un 0 aquí no lo cantaría nadie más.
            controles[ronda] = {"revision": rev, "revision_fecha": fecha,
                                "estado": f"la sección «{seccion}» no tiene ningún partido"}
            continue
        cruce = control_cruzado_con_cajas(txt, d) if tipo == "serie" else None
        controles[ronda] = {"revision": rev, "revision_fecha": fecha,
                            **control_contra_infobox(txt, d),
                            **(cruce or {}),
                            # Un recorte publica cuántas filas salieron, jugadas o no: es lo único que distingue
                            # «la final está ahí, aún sin jugar» de «la final se perdió».
                            **({"seccion": seccion, "partidos_en_seccion": len(d)} if seccion else {}),
                            **({"transcluye": incrustados} if incrustados else {})}
        trozos.append(d)

    todo = pd.concat(trozos, ignore_index=True) if trozos else pd.DataFrame()
    return todo, controles


def actualizar(clave: str) -> tuple[pd.DataFrame, dict]:
    """`leer_articulos` y además deja el CSV en data/processed, que es lo que lee el exportador."""
    todo, controles = leer_articulos(clave)
    ruta = SALIDA / f"wikipedia_{clave}.csv"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    todo.to_csv(ruta, index=False)
    return todo, controles
