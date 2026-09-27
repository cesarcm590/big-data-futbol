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

from futbol_bd import calendario, clubes_continentales  # noqa: E402
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
        "De momento solo la **AFC Champions League Elite**, porque es la única de las cinco cuya federación publica "
        "una API abierta. La de CAF va por widgets de Opta con clave de suscripción y su web no tiene página de "
        "calendario; UEFA sí se puede y está pendiente. Un aviso sobre la tabla: **AFC no publica la nacionalidad "
        "del árbitro**, así que aquí no se puede hacer el control de neutralidad que sí aparece en selecciones."),
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
                           fin=camino["fin"].dt.strftime("%Y-%m-%d"))

    # Resultados: solo de las confederaciones cuya fuente lo permite (ver clubes_continentales).
    ruta_afc = clubes_continentales.SALIDA / "afc_champions_elite_2026_27.csv"
    afc = pd.read_csv(ruta_afc) if ruta_afc.exists() else pd.DataFrame()
    cols = ["fecha", "fase", "grupo", "local", "goles_local", "goles_visitante", "visitante", "arbitro", "estadio"]
    jugados = afc[afc["jugado"]].sort_values("fecha", ascending=False)[cols] if len(afc) else pd.DataFrame(columns=cols)
    proximos = (afc[~afc["jugado"]].sort_values("fecha")[["fecha", "hora", "fase", "local", "visitante"]].head(30)
                if len(afc) else pd.DataFrame())

    datos = {
        "meta": {
            "competiciones": len(camino),
            "afc_partidos": int(len(afc)), "afc_jugados": int(afc["jugado"].sum()) if len(afc) else 0,
            "confederaciones": int(camino["confederacion"].nunique()),
            "con_fechas_no_oficiales": int(camino["es_provisional"].sum()),
            "en_curso": int(camino["en_curso"].sum()),
            "generado": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "fuente": "calendarios oficiales de UEFA, CAF, AFC, CONMEBOL y Concacaf, verificados a mano",
        },
        "camino": limpio(camino.to_dict("records")),
        "afc": {"nombre": clubes_continentales.AFC["nombre"],
                "resultados": limpio(jugados.to_dict("records")),
                "proximos": limpio(proximos.to_dict("records"))},
        "lectura": LECTURA,
    }
    SALIDA.write_text(json.dumps(datos, ensure_ascii=False, separators=(",", ":"), allow_nan=False))
    print(f"Clubes -> {SALIDA.relative_to(RAIZ)} ({SALIDA.stat().st_size / 1024:.0f} KB)")
    print(f"  AFC: {int(afc['jugado'].sum()) if len(afc) else 0} partidos jugados de {len(afc)}")
    print(f"  {len(camino)} competiciones en {camino['confederacion'].nunique()} confederaciones · "
          f"{int(camino['en_curso'].sum())} en curso · {int(camino['es_provisional'].sum())} sin fechas oficiales")
    return 0


if __name__ == "__main__":
    sys.exit(main())
