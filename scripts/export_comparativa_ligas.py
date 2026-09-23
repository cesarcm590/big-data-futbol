"""
Exporta la comparativa de las 7 ligas (notebook 19) al JSON que lee la sección 6 de `analisis.html`.

    python scripts/export_comparativa_ligas.py        # -> dashboard-predicciones/analisis_comparativa.json

Usa `liga.comparativa`, la misma función del notebook 19, así que la web y el notebook no pueden decir cosas distintas.
Contenido:
  meta      ligas, temporadas (etiquetas cortas) y fecha de generación
  series    por métrica: una lista de valores por liga, en el orden de `meta.temporadas` (null donde no hay dato)
  etiquetas nombre legible de cada métrica
  resumen   una fila por liga: tamaño del panel, estabilidades año a año y correlaciones con los puntos por partido
  lectura   textos de interpretación (los mismos tres bloques que muestra la página)
"""
import json
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from futbol_bd import fantasy, liga, plantillas  # noqa: E402
from export_analisis_liga import limpio  # noqa: E402  (misma conversión a tipos de JSON)

LIGAS = ["Liga MX", "Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1", "Eredivisie"]
SALIDA = RAIZ / "dashboard-predicciones" / "analisis_comparativa.json"

LECTURA = {
    "plantillas": (
        "Rotación: la Eredivisie es la más concentrada (12-14 jugadores para el 80% de los minutos) y la Liga MX la que "
        "más rotó con el tiempo (13.5 → 15-16). Extranjeros: Premier (73%), Ligue 1 (72.6%) y Serie A (70.2%) terminan "
        "con siete de cada diez minutos en pies extranjeros, mientras que La Liga (43%) y la Eredivisie (48%) se quedaron "
        "donde empezaron. Juveniles: la Eredivisie juega en otra categoría, con 20-33.6% de los minutos para menores de "
        "22 años, contra 5-13% de Premier, La Liga, Serie A y Liga MX. Las edades convergen: Liga MX y Serie A empezaron "
        "siendo las más viejas (27-28 años) y hoy están cerca del resto."),
    "porteros": (
        "El % de paradas baja en las siete ligas, entre 2 y 7 puntos en 15 años: una caída general, no de una liga en "
        "particular. La Bundesliga es la más goleada (1.60 goles recibidos por partido en 2025-26) y la Serie A la que "
        "menos (1.21), con su récord de porterías a cero (32.2%). La Ligue 1 hizo el viaje más largo: era la menos "
        "goleada del panel en 2010-11 (1.15) y hoy está en 1.39."),
    "correlaciones": (
        "El resultado más importante: el on-off no mide al jugador en NINGUNA liga (entre −0.03 y 0.08 de una temporada a "
        "la siguiente), ni los puntos del equipo con él (−0.06 a 0.09), mientras que una medida individual —goles sin "
        "penal por 90 de los delanteros— va de 0.49 a 0.69. Sobre los puntos del equipo: lo que se asocia es meter goles "
        "(0.78 a 0.89), rotar mucho va con perder en las siete (−0.28 a −0.47) y depender del goleador no dice nada "
        "(−0.04 a 0.21)."),
}


def main():
    filas = plantillas.unir_tablas_extra(plantillas.limpiar_panel(plantillas.cargar_panel_crudo()))
    jt = fantasy.puntos_fantasy(plantillas.agregar_por_temporada(filas))
    series, resumen = liga.comparativa(filas, jt, LIGAS)

    temporadas = sorted(series["temporada_inicio"].unique())
    etiquetas = [f"{t % 100:02d}-{(t + 1) % 100:02d}" for t in temporadas]
    por_metrica = {}
    for metrica in liga.SERIES_COMPARABLES:
        por_metrica[metrica] = {nombre: (series[series["league"] == nombre].set_index("temporada_inicio")
                                         .reindex(temporadas)[metrica].tolist()) for nombre in LIGAS}

    datos = {
        "meta": {"ligas": LIGAS, "temporadas": etiquetas, "generado": datetime.now().strftime("%Y-%m-%d %H:%M"),
                 "fuente": "FBref (tablas estándar, playingtime y keepers), temporadas 2010-11 a 2025-26"},
        "series": por_metrica,
        "etiquetas": dict(liga.SERIES_COMPARABLES),
        "resumen": resumen.to_dict("records"),
        "lectura": LECTURA,
    }
    SALIDA.write_text(json.dumps(limpio(datos), ensure_ascii=False, separators=(",", ":"), allow_nan=False))
    print(f"Comparativa de {len(LIGAS)} ligas -> {SALIDA.relative_to(RAIZ)} ({SALIDA.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
