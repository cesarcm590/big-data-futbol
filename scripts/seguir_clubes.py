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

from futbol_bd import clubes_continentales, wikipedia_competiciones  # noqa: E402


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

    # Las de Wikipedia SIEMPRE enseñan su control: es lo único que avisa de que el artículo cambió de formato.
    # Tres estados: cuadra, no cuadra, o "sin control" cuando el artículo no declara totales contra los que medir.
    for clave, cfg in wikipedia_competiciones.COMPETICIONES.items():
        try:
            d, ctl = wikipedia_competiciones.actualizar(clave)
        except Exception as e:
            print(f"✗ {cfg['nombre']}: no se pudo ({type(e).__name__}: {str(e)[:60]})")
            fallos += 1
            continue
        print(f"{cfg['nombre']} (Wikipedia): {int(d['jugado'].sum()) if len(d) else 0} partidos jugados")
        for ronda, c in ctl.items():
            if "estado" in c:
                print(f"   {ronda}: {c['estado']}")
            else:
                señal = {"cuadra": "✓", "no cuadra": "!", "sin control": "?"}[c["control"]]
                detalle = (f"{c['partidos_parseados']} partidos; el artículo declara "
                           f"{c['partidos_segun_wikipedia']}" if c["control"] != "sin control"
                           else f"{c['partidos_parseados']} partidos; el artículo NO declara totales")
                print(f"   {señal} {ronda}: {detalle} · revisión {c['revision']}")
                # Lo transcluido se enseña con su propia revisión: el artículo principal no la lleva, y sin ella la
                # cifra no es reproducible. También sirve de aviso si un día deja de transcluirse.
                for titulo, inc in c.get("transcluye", {}).items():
                    marca = inc.get("estado") or f"revisión {inc['revision']}"
                    print(f"        + transcluye «{titulo}» · {marca}")

    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
