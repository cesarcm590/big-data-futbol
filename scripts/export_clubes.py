"""
Exporta la página de competiciones continentales de CLUBES -> dashboard-predicciones/analisis_clubes.json

    python scripts/export_clubes.py

POR QUÉ ES UNA PÁGINA APARTE DE SELECCIONES
-------------------------------------------
Coinciden en el calendario pero no responden a la misma pregunta ni las juegan los mismos: una Champions y una
eliminatoria mundialista se solapan en el año y no se comparan en ningún análisis. Mezclarlas repetiría el error que
ya se corrigió en la Fase 32 (selecciones colgando dentro de "Análisis por liga").

De momento esto es CALENDARIO, no resultados: qué se juega en cada confederación y cuándo. Cada federación publica
sus datos a su manera (UEFA tiene API, Concacaf renderiza en el servidor, CAF y AFC están por mirar), así que los
resultados partido a partido se irán añadiendo confederación por confederación, no de golpe.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from futbol_bd import calendario, clubes_continentales, wikipedia_competiciones  # noqa: E402
from export_analisis_liga import limpio  # noqa: E402

SALIDA = RAIZ / "dashboard-predicciones" / "analisis_clubes.json"

LECTURA = {
    "que_es": (
        "Las máximas competiciones de clubes de cada confederación, en una sola línea temporal: la Champions de "
        "UEFA, la Libertadores de CONMEBOL, la Champions League de CAF, la Champions League Elite de AFC y la "
        "Champions Cup de Concacaf, donde juegan los equipos de Liga MX. Más el Mundial de Clubes de 2029."),
    "advertencia": (
        "**Esto es calendario, no resultados.** Dice qué se juega y cuándo, con la misma marca de fechas no "
        "oficiales que la página de selecciones. Los resultados partido a partido se irán añadiendo confederación "
        "por confederación: cada federación publica sus datos de forma distinta y no hay una fuente única que las "
        "cubra todas. La Champions Cup de Concacaf 2027 aparece con fechas **estimadas** a partir de las ediciones "
        "de 2024 y 2025, porque las suyas todavía no se han anunciado."),
    "resultados": (
        "Cinco competiciones, con fuentes de fiabilidad muy distinta y conviene saber cuál es cuál. La **UEFA "
        "Champions League** y la **AFC Champions League Elite** vienen de la API abierta de sus propias "
        "federaciones. La **CAF Champions League**, la **Copa Libertadores** y la **Concacaf Champions Cup** vienen "
        "de **Wikipedia**, porque ninguna de las tres federaciones publica resultados utilizables: CAF son noticias "
        "con widgets de Opta bajo clave de suscripción, CONMEBOL sirve un carrusel en HTML de próximos partidos y "
        "Concacaf renderiza en el servidor sin exponer datos. Wikipedia no es una API: es un artículo que cualquiera "
        "puede reestructurar, y si cambia el formato el parseo falla en silencio. Por eso debajo se muestra el "
        "contraste entre lo que leímos y lo que el propio artículo declara: si no cuadra, la cifra es sospechosa, y "
        "si el artículo no declara totales se dice también, porque entonces esa cifra va a ciegas. Otro aviso: "
        "**solo UEFA publica la nacionalidad del árbitro**. Por eso el control de neutralidad —comprobar que el "
        "colegiado no es del país de ninguno de los dos clubes— aparece en la Champions y no en las demás: no es "
        "que no interese, es que esos datos no lo permiten."),
    "hallazgo": (
        "Puestas una al lado de otra se ve algo que por separado no: **las cinco confederaciones juegan su "
        "competición en ventanas distintas**. UEFA y AFC arrancan en septiembre y terminan en mayo; CAF empieza "
        "antes, en las preliminares de septiembre, y cierra a la vez; CONMEBOL va de febrero a noviembre, "
        "desplazada medio año respecto a Europa. Por eso un jugador que cambia de continente puede encadenar dos "
        "temporadas seguidas casi sin parar."),
}


def main():
    cal = calendario.cargar_calendario()
    hoy = pd.Timestamp.today().normalize()
    camino = calendario.cuenta_atras(cal, hoy, ambito="club")
    camino = camino.assign(inicio=camino["inicio"].dt.strftime("%Y-%m-%d"),
                           fin=camino["fin"].dt.strftime("%Y-%m-%d"),
                           # La región va en los datos y no en el HTML para que la página y el terminal llamen a
                           # cada confederación igual, y para no tener el mismo diccionario escrito en dos sitios.
                           region=camino["confederacion"].map(calendario.region))

    # Resultados: solo de las confederaciones cuya fuente lo permite (ver clubes_continentales).
    ruta_ucl = clubes_continentales.SALIDA / "uefa_champions_2026_27.csv"
    ucl = pd.read_csv(ruta_ucl) if ruta_ucl.exists() else pd.DataFrame()
    cols_ucl = ["fecha", "fase", "local", "goles_local", "goles_visitante", "visitante", "arbitro", "arbitro_pais"]
    ucl_jug = (ucl[ucl["jugado"]].sort_values("fecha", ascending=False)[cols_ucl]
               if len(ucl) else pd.DataFrame(columns=cols_ucl))
    ucl_prox = (ucl[~ucl["jugado"]].sort_values("fecha")[["fecha", "hora", "fase", "local", "visitante"]].head(30)
                if len(ucl) else pd.DataFrame())

    ruta_afc = clubes_continentales.SALIDA / "afc_champions_elite_2026_27.csv"
    afc = pd.read_csv(ruta_afc) if ruta_afc.exists() else pd.DataFrame()
    cols = ["fecha", "fase", "grupo", "local", "goles_local", "goles_visitante", "visitante", "arbitro", "estadio"]
    jugados = afc[afc["jugado"]].sort_values("fecha", ascending=False)[cols] if len(afc) else pd.DataFrame(columns=cols)
    proximos = (afc[~afc["jugado"]].sort_values("fecha")[["fecha", "hora", "fase", "local", "visitante"]].head(30)
                if len(afc) else pd.DataFrame())

    # Las de Wikipedia: además de los partidos se publica el CONTROL, porque sin él una tabla incompleta no se
    # distingue de una correcta. Se lee del CSV que deja `seguir_clubes.py` y el control se recalcula contra el
    # artículo vivo.
    wiki = {}
    cols_w = ["ronda", "partido", "fecha", "local", "goles_local", "goles_visitante", "visitante"]
    cols_p = ["ronda", "partido", "fecha", "local", "visitante"]
    for clave, cfg in wikipedia_competiciones.COMPETICIONES.items():
        ruta = wikipedia_competiciones.SALIDA / f"wikipedia_{clave}.csv"
        dd = pd.read_csv(ruta) if ruta.exists() else pd.DataFrame()
        jug = dd[dd["jugado"]] if len(dd) else dd
        jug = jug.reindex(columns=cols_w)
        # De lo que falta solo se anuncia lo que tiene FECHA. Las tablas de eliminatoria de Wikipedia son cruces, no
        # partidos con día: anunciar «Ida» sin fecha no dice nada. La final de la Libertadores sí la trae, porque es a
        # partido único y va en su propia caja. El `reindex` es necesario porque una competición leída solo con el
        # parser de eliminatorias no tiene ni columna `fecha`.
        prox = (dd[~dd["jugado"]] if len(dd) else dd).reindex(columns=cols_p)
        prox = prox[prox["fecha"].notna()].sort_values("fecha") if len(prox) else prox
        ctl = {}
        try:
            # El mismo camino que usa `seguir_clubes.py`, no una copia: si el parseo cambia, el control cambia con
            # él. Aquí solo interesa el control; los partidos se leen del CSV de arriba.
            ctl = wikipedia_competiciones.leer_articulos(clave)[1]
        except Exception as e:
            ctl["error"] = {"estado": f"no se pudo comprobar contra Wikipedia: {type(e).__name__}"}
        # Cuántos quedan sin jugar Y sin fecha: es lo que distingue «la edición terminó» de «falta gente pero el
        # artículo no dice cuándo». Sin este número la página daría el mismo mensaje en los dos casos, y uno es falso.
        sin_fecha = int(len(dd[~dd["jugado"]]) - len(prox)) if len(dd) else 0
        wiki[clave] = {"nombre": cfg["nombre"], "confederacion": cfg["confederacion"],
                       "region": calendario.region(cfg["confederacion"]),
                       "resultados": limpio(jug.to_dict("records")),
                       "proximos": limpio(prox.to_dict("records")), "sin_fecha": sin_fecha,
                       "control": limpio(ctl)}

    datos = {
        "meta": {
            "ucl_jugados": int(len(ucl_jug)),
            "wiki_jugados": {k: len(v["resultados"]) for k, v in wiki.items()},
            "competiciones": len(camino),
            "afc_partidos": int(len(afc)), "afc_jugados": int(afc["jugado"].sum()) if len(afc) else 0,
            "confederaciones": int(camino["confederacion"].nunique()),
            "con_fechas_no_oficiales": int(camino["es_provisional"].sum()),
            "en_curso": int(camino["en_curso"].sum()),
            "generado": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "fuente": "calendarios oficiales de UEFA, CAF, AFC, CONMEBOL y Concacaf, verificados a mano",
            "regiones": calendario.REGIONES,
        },
        "camino": limpio(camino.to_dict("records")),
        "ucl": {"nombre": clubes_continentales.UCL["nombre"], "region": calendario.region("UEFA"),
                "resultados": limpio(ucl_jug.to_dict("records")),
                "proximos": limpio(ucl_prox.to_dict("records")),
                "fallos_neutralidad": len(clubes_continentales.neutralidad_ucl(ucl)) if len(ucl) else 0},
        "wiki": wiki,
        "afc": {"nombre": clubes_continentales.AFC["nombre"], "region": calendario.region("AFC"),
                "resultados": limpio(jugados.to_dict("records")),
                "proximos": limpio(proximos.to_dict("records"))},
        "lectura": LECTURA,
    }
    SALIDA.write_text(json.dumps(datos, ensure_ascii=False, separators=(",", ":"), allow_nan=False))
    print(f"Clubes -> {SALIDA.relative_to(RAIZ)} ({SALIDA.stat().st_size / 1024:.0f} KB)")
    print(f"  UEFA: {len(ucl_jug)} partidos jugados de {len(ucl)}")
    print(f"  AFC: {int(afc['jugado'].sum()) if len(afc) else 0} partidos jugados de {len(afc)}")
    for k, v in wiki.items():
        print(f"  {v['nombre']}: {len(v['resultados'])} partidos (Wikipedia)")
    print(f"  {len(camino)} competiciones en {camino['confederacion'].nunique()} confederaciones · "
          f"{int(camino['en_curso'].sum())} en curso · {int(camino['es_provisional'].sum())} sin fechas oficiales")
    return 0


if __name__ == "__main__":
    sys.exit(main())
