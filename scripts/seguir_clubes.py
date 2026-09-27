"""
Actualiza los resultados de las competiciones continentales de clubes que tienen fuente.

    python scripts/seguir_clubes.py

A diferencia de `seguir_nations_league.py`, este NO se ata a las ventanas FIFA: las competiciones de clubes se
juegan entre semana durante casi todo el año, justo cuando las selecciones paran. Por eso se corre siempre.

Ahora mismo solo AFC. Las demás, cuando haya de dónde sacarlas (ver `futbol_bd/clubes_continentales`).
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from futbol_bd import clubes_continentales  # noqa: E402


def main():
    try:
        _, r = clubes_continentales.actualizar_afc()
    except Exception as e:
        print(f"✗ AFC: no se pudo actualizar ({type(e).__name__}: {str(e)[:70]})")
        return 1
    print(f"{r['competicion']}: {r['jugados']} jugados de {r['partidos']} · "
          f"{r['nuevos']} resultados nuevos · {r['con_arbitro']} con árbitro")
    return 0


if __name__ == "__main__":
    sys.exit(main())
