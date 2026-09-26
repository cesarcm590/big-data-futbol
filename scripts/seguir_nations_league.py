"""
Actualiza el seguimiento de la Nations League 2026-27, pero SOLO cuando hay fecha FIFA.

    python scripts/seguir_nations_league.py            # solo actúa si estamos en ventana
    python scripts/seguir_nations_league.py --forzar   # actualiza igualmente

POR QUÉ SE ATA AL CALENDARIO
----------------------------
Entre ventanas no se juega un solo partido de selecciones: pedir los datos cada día sería tráfico inútil contra
UEFA y ruido en el log. `futbol_bd/calendario.ventana_activa` decide, usando el mismo calendario verificado que
alimenta el análisis a 2030, y deja un margen de días tras el cierre porque los datos de la última jornada tardan
en cuadrar.

Pensado para colgarlo del temporizador que ya corre lunes y viernes: en semana sin ventana no hace nada y lo dice.
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from futbol_bd import calendario, nations_league  # noqa: E402


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--forzar", action="store_true", help="actualiza aunque no haya ventana FIFA")
    args = a.parse_args()

    cal = calendario.cargar_calendario()
    hoy = pd.Timestamp.today().normalize()
    ventana = calendario.ventana_activa(cal, hoy)

    if ventana is None and not args.forzar:
        prox = cal[(cal["tipo"] == "ventana") & (cal["inicio"] > hoy)]
        if len(prox):
            v = prox.iloc[0]
            print(f"Sin fecha FIFA hoy. La próxima ventana es {v['edicion']}: "
                  f"{v['inicio'].date()} a {v['fin'].date()} (faltan {(v['inicio'] - hoy).days} días).")
        else:
            print("Sin fecha FIFA hoy y no quedan ventanas en el calendario.")
        return 0

    if ventana is not None:
        print(f"Fecha FIFA {ventana['edicion']} ({ventana['inicio'].date()} a {ventana['fin'].date()}, "
              f"{ventana['fase']})")
    else:
        print("(--forzar) fuera de ventana, se actualiza igualmente")

    try:
        d, r = nations_league.actualizar()
    except Exception as e:
        print(f"✗ no se pudo actualizar ({type(e).__name__}: {str(e)[:80]})")
        return 1

    print(f"  {r['partidos']} partidos · {r['jugados']} jugados · {r['en_vivo']} en vivo · "
          f"{r['nuevos_resultados']} resultados nuevos desde la última vez")
    if r["fallos_neutralidad"]:
        print(f"  ! {r['fallos_neutralidad']} partidos con árbitro del país de un equipo: revisar, no debería pasar")

    jugados = d[d["jugado"]]
    if len(jugados):
        por_liga = jugados.groupby("liga").size().to_dict()
        print(f"  por liga: {por_liga}")
        ult = jugados.tail(3)
        for f in ult.itertuples():
            print(f"    {f.fecha}  {f.local} {f.goles_local:.0f}-{f.goles_visitante:.0f} {f.visitante}"
                  f"  ({f.arbitro}, {f.arbitro_pais})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
