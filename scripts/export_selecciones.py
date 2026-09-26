"""
Exporta la sección de selecciones del dashboard -> dashboard-predicciones/analisis_selecciones.json

    python scripts/export_selecciones.py

QUÉ ENTRA Y QUÉ NO, Y POR QUÉ
-----------------------------
Solo dos fuentes: la **API pública de UEFA** (Nations League 2026-27) y nuestro **calendario de referencia**
mantenido a mano. El conjunto de Euro y Nations League de Kaggle queda FUERA a propósito, aunque tenga datos más
ricos: está bajo CC BY-NC-SA, cuya cláusula de CompartirIgual alcanzaría a lo que publicáramos a partir de él. Al
no usarlo aquí, el dashboard público no hereda esa licencia. Lo derivado de ese conjunto vive aislado en
`selecciones/`, que no se publica.

Contenido:
  meta          fechas, cuántos partidos, cuándo se generó
  camino        competiciones que quedan hasta el Mundial 2030, con si sus fechas son oficiales o estimadas
  ventanas      cada ventana FIFA y qué se juega en ella
  nations       clasificaciones por grupo, últimos resultados y próximos partidos
  arbitros      control de neutralidad y cuántos han dirigido
  lectura       los textos que explican qué mira y qué no
"""
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from futbol_bd import calendario, nations_league  # noqa: E402
from export_analisis_liga import limpio  # noqa: E402

SALIDA = RAIZ / "dashboard-predicciones" / "analisis_selecciones.json"

LECTURA = {
    "que_es": (
        "El camino al Mundial 2030, que arranca el 8 de junio de 2030 en Uruguay, Argentina y Paraguay con los tres "
        "partidos del centenario, y sigue en Marruecos, Portugal y España. Debajo, la Nations League 2026-27 que se "
        "está jugando ahora. Datos de la API pública de UEFA y de un calendario verificado a mano contra FIFA."),
    "advertencia": (
        "**Un calendario a cuatro años tiene fechas que todavía no existen.** Las que no son oficiales van marcadas: "
        "de la Euro 2028 y la Copa América 2028 se sabe que se juegan ese verano, pero no sus fechas exactas, y de la "
        "clasificación al Mundial 2030 solo se ha anunciado el formato. Cuando dos competiciones aparecen solapadas y "
        "alguna lleva fechas provisionales, **el solapamiento en días no es un dato**: es consecuencia del rango "
        "aproximado que les pusimos. Lo verificado es que ocurren en el mismo verano."),
    "hallazgo": (
        "UEFA designa árbitro de un país neutral, y se cumple: en los partidos con árbitro designado, ninguno es del "
        "país de alguno de los dos equipos. Con los datos históricos de Euro y Nations League probamos si, aun siendo "
        "neutrales, unos árbitros acaban con más victorias locales que otros: la horquilla iba del 17% al 64%, que "
        "parece enorme, pero simulando 10,000 mundos donde ningún árbitro influye la horquilla típica **por puro "
        "azar** es todavía mayor (51 puntos frente a 47 reales, p = 0.67). Con 10-16 partidos por árbitro no hay "
        "nada que ver, y sin la simulación esos porcentajes parecían un hallazgo."),
}


def main():
    cal = calendario.cargar_calendario()
    hoy = pd.Timestamp.today().normalize()

    camino = calendario.cuenta_atras(cal, hoy)
    camino = camino.assign(inicio=camino["inicio"].dt.strftime("%Y-%m-%d"), fin=camino["fin"].dt.strftime("%Y-%m-%d"))

    ventanas = calendario.que_ocupa_cada_ventana(cal)
    ventanas = ventanas.assign(inicio=ventanas["inicio"].dt.strftime("%Y-%m-%d"),
                               fin=ventanas["fin"].dt.strftime("%Y-%m-%d"))

    ruta_nl = nations_league.SALIDA
    if not ruta_nl.exists():
        print(f"✗ falta {ruta_nl.relative_to(RAIZ)}. Corre antes: python scripts/seguir_nations_league.py --forzar")
        return 1
    nl = pd.read_csv(ruta_nl)
    tabla = nations_league.tabla_de_posiciones(nl)
    jugados = nl[nl["jugado"]].sort_values(["fecha", "hora"])
    proximos = nl[~nl["jugado"]].sort_values(["fecha", "hora"])

    cols_res = ["fecha", "liga", "grupo", "local", "goles_local", "goles_visitante", "visitante",
                "arbitro", "arbitro_pais"]
    datos = {
        "meta": {
            "mundial": "2030-06-08",
            "dias_para_el_mundial": int((calendario.MUNDIAL_2030 - hoy).days),
            "competiciones_por_delante": len(camino),
            "con_fechas_no_oficiales": int(camino["es_provisional"].sum()),
            "nations_partidos": len(nl), "nations_jugados": int(nl["jugado"].sum()),
            "generado": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "fuente": "API pública de UEFA (Nations League 2026-27) y calendario verificado contra FIFA",
        },
        "camino": limpio(camino.to_dict("records")),
        "ventanas": limpio(ventanas.to_dict("records")),
        "nations": {
            "clasificacion": limpio(tabla.to_dict("records")),
            "resultados": limpio(jugados[cols_res].to_dict("records")),
            "proximos": limpio(proximos[["fecha", "hora", "liga", "grupo", "local", "visitante"]]
                               .head(40).to_dict("records")),
        },
        "arbitros": {
            "designados": int(nl["arbitro"].notna().sum()),
            "distintos": int(nl["arbitro"].nunique()),
            # Se publica cuántos repiten, no solo el total: "42 partidos y 42 árbitros" parece una errata, y no lo
            # es —hasta ahora UEFA ha puesto uno distinto en cada partido—. El dato interesante es justo ese cero.
            "repiten": int((nl["arbitro"].value_counts() > 1).sum()),
            "fallos_neutralidad": len(nations_league.comprobar_neutralidad(nl)),
        },
        "lectura": LECTURA,
    }
    SALIDA.write_text(json.dumps(datos, ensure_ascii=False, separators=(",", ":"), allow_nan=False))
    print(f"Selecciones -> {SALIDA.relative_to(RAIZ)} ({SALIDA.stat().st_size / 1024:.0f} KB)")
    print(f"  {len(camino)} competiciones por delante · {datos['meta']['dias_para_el_mundial']:,} días al Mundial")
    print(f"  Nations League: {datos['meta']['nations_jugados']}/{datos['meta']['nations_partidos']} jugados, "
          f"{len(tabla)} filas de clasificación en {tabla['grupo'].nunique()} grupos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
