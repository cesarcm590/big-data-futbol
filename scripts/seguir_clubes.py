"""
Actualiza los resultados de las competiciones continentales de clubes que tienen fuente.

    python scripts/seguir_clubes.py

A diferencia de `seguir_nations_league.py`, este NO se ata a las ventanas FIFA: las competiciones de clubes se
juegan entre semana durante casi todo el año, justo cuando las selecciones paran. Por eso se corre siempre.

Ahora: UEFA y AFC por API de su federación, CAF por Wikipedia. CONMEBOL y Concacaf, por mirar.
Si una falla, las demás siguen: son fuentes independientes y no tiene sentido que una caída las tire todas.
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from futbol_bd import caf_wikipedia, clubes_continentales  # noqa: E402


def main():
    fallos = 0
    try:
        _, r = clubes_continentales.actualizar_ucl()
        print(f"{r['competicion']}: {r['jugados']} jugados de {r['partidos']} · "
              f"{r['nuevos']} resultados nuevos · {r['fallos_neutralidad']} fallos de neutralidad")
    except Exception as e:
        print(f"✗ UEFA: no se pudo actualizar ({type(e).__name__}: {str(e)[:70]})")
        fallos += 1

    try:
        _, r = clubes_continentales.actualizar_afc()
        print(f"{r['competicion']}: {r['jugados']} jugados de {r['partidos']} · "
              f"{r['nuevos']} resultados nuevos · {r['con_arbitro']} con árbitro")
    except Exception as e:
        print(f"✗ AFC: no se pudo actualizar ({type(e).__name__}: {str(e)[:70]})")
        fallos += 1

    # CAF sale de Wikipedia, así que SIEMPRE se enseña el control contra el infobox: es lo único que avisa de que
    # el artículo cambió de formato y el parseo dejó de leer bien.
    try:
        d, ctl = caf_wikipedia.actualizar()
    except Exception as e:
        print(f"✗ CAF: no se pudo actualizar ({type(e).__name__}: {str(e)[:70]})")
        return 1 + fallos
    print(f"CAF Champions League 2026-27 (Wikipedia): {int(d['jugado'].sum()) if len(d) else 0} partidos jugados")
    for ronda, c in ctl.items():
        if "estado" in c:
            print(f"   {ronda}: {c['estado']}")
        else:
            señal = "✓" if c["cuadra"] else "!"
            print(f"   {señal} {ronda}: {c['partidos_parseados']} partidos y {c['goles_parseados']} goles; "
                  f"el artículo dice {c['partidos_segun_wikipedia']} y {c['goles_segun_wikipedia']} "
                  f"(infobox actualizado el {c['infobox_actualizado']}) · revisión {c['revision']}")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
