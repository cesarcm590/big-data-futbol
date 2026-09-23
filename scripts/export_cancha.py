"""
Exporta los mapas de Apolonio sobre la cancha (notebook 22) a los JSON que lee la sección 10 de `analisis.html`.

    python scripts/export_cancha.py      # -> dashboard-predicciones/analisis_cancha_{laliga,premier}.json

Un archivo por liga (~400 KB cada uno) porque son 380 partidos × 22 titulares: la página carga solo el de la liga que
se esté mirando, igual que hace con los análisis por liga.

Como en la sección 9, el servidor manda **sitios y no imágenes**: la posición media de cada titular y su peso, y el
navegador rasteriza el diagrama. La diferencia con el mapa de perfiles es que aquí **no se normalizan los ejes**: los
dos están en metros, así que la distancia se calcula directamente sobre la cancha de 120 × 80.

Contenido:
  meta      liga, dimensiones de la cancha, cuántos partidos y la advertencia sobre qué mide el mapa
  partidos  una fila por partido (id, fecha, equipos y marcador), de la más reciente a la más antigua
  sitios    {match_id: {equipo: [[jugador, puesto, x, y, exitosas, x_desv, y_desv], ...]}} solo titulares
  lectura   textos de interpretación (los mismos bloques que muestra la página)
"""
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from futbol_bd import cancha  # noqa: E402
from export_analisis_liga import limpio  # noqa: E402  (misma conversión a tipos de JSON)

# Las CUATRO temporadas que StatsBomb Open Data publica completas, todas 2015/16. Lo demás que publica en
# abierto son temporadas parciales de un equipo, que no sirven para un mapa de reparto por liga.
LIGAS = {"laliga": "La Liga 2015/16", "premier": "Premier League 2015/16",
         "seriea": "Serie A 2015/16", "ligue1": "Ligue 1 2015/16"}
PROCESADOS = RAIZ / "data" / "processed"
# `minutos`, `estado` y `salio` vienen de las alineaciones (ver descargar_statsbomb_posiciones.descargar_participacion):
# sin ellos un titular sustituido al 25' se ve igual que uno que jugó los 90, y su posición media sale de muchos
# menos eventos. `estado`: C = completó, S = lo sustituyeron, X = salió por roja o lesión sin reemplazo.
COLUMNAS = ["jugador", "puesto", "x", "y", "exitosas", "x_desv", "y_desv", "minutos", "estado", "salio"]
CODIGO_ESTADO = {"titular_completo": "C", "titular_sustituido": "S", "titular_salio": "X"}

LECTURA = {
    "que_es": (
        "El mismo diagrama de Apolonio de la sección 9, pero sobre la cancha de verdad, que es su uso original en "
        "fútbol (la «dominant region» de Taki y Hasegawa, 2000). Cada sitio es la posición MEDIA de un titular durante "
        "el partido, calculada con los eventos en los que tocó el balón, y su peso son las acciones que le salieron "
        "bien: pases completados, conducciones, regates, recuperaciones, despejes, bloqueos, duelos ganados y tiros a "
        "puerta. Datos de StatsBomb Open Data: las cuatro temporadas de liga que publica completas, todas de "
        "2015/16 (La Liga, Premier, Serie A y Ligue 1). El resto de su catálogo abierto son temporadas "
        "parciales centradas en un equipo, que no sirven para comparar el reparto de una liga."),
    "advertencia": (
        "**Dos cosas que este mapa NO dice.** La posición media no es dónde estuvo el jugador: es el centro de sus "
        "acciones, y su dispersión típica cubre un tercio de la cancha (pásale el cursor a un jugador para verla). Un "
        "lateral que sube y baja toda la banda aparece a media altura, en un punto donde quizá no estuvo nunca. Y el "
        "peso es participación con éxito, no calidad: quien más toca el balón domina más mapa aunque el partido lo "
        "haya decidido otro con tres toques. El área mide territorio de participación."),
    "hallazgo": (
        "Lo que sí se pudo medir con esto (notebook 22, 1,517 partidos de cuatro ligas): el área que domina un "
        "jugador en UN partido es "
        "casi ruido —se repite 0.35 de un partido al siguiente— pero su MEDIA de la temporada es muy fiable (0.91), y "
        "sigue siéndolo al quitarle la media de su puesto (0.86) y la de su equipo en esa línea (0.87). Es decir: dos "
        "jugadores del mismo puesto y del mismo equipo dominan cantidades de territorio distintas, y lo hacen de "
        "forma consistente. Es la métrica individual que mejor ha pasado la prueba de «¿mide al jugador?» en todo el "
        "proyecto."),
}


def main():
    for clave, nombre in LIGAS.items():
        pos = pd.read_csv(PROCESADOS / f"statsbomb_{clave}_posiciones.csv")
        par = pd.read_csv(PROCESADOS / f"statsbomb_{clave}_partidos.csv").sort_values("match_date", ascending=False)
        # En los eventos StatsBomb trae el nombre legal completo ("Lionel Andrés Messi Cuccittini"); el nombre con el
        # que se le conoce está en las alineaciones, que `descargar_statsbomb_posiciones.py` guarda aparte.
        nombres = pd.read_csv(PROCESADOS / f"statsbomb_{clave}_jugadores.csv").set_index("player_id")["nombre"]
        pos["nombre"] = pos["player_id"].map(nombres).fillna(pos["player"])

        # Minutos y cambios. Se une por (partido, jugador); la titularidad se toma de AQUÍ y no de la columna
        # `titular` de los eventos, porque esta viene de las alineaciones y se validó contra los 11 por equipo.
        part = pd.read_csv(PROCESADOS / f"statsbomb_{clave}_participacion.csv")
        part["nombre"] = part["player_id"].map(nombres)
        pos = pos.merge(part[["match_id", "player_id", "minutos", "estado", "entro", "salio"]],
                        on=["match_id", "player_id"], how="left")
        titulares = pos[pos["estado"].isin(CODIGO_ESTADO)]

        sitios = {}
        for (match_id, equipo), d in titulares.groupby(["match_id", "team"], sort=False):
            d = d.sort_values("exitosas", ascending=False)
            sitios.setdefault(str(int(match_id)), {})[equipo] = [
                [r.nombre, r.posicion, round(r.x, 1), round(r.y, 1), int(r.exitosas),
                 round(r.x_desv, 1), round(r.y_desv, 1), round(r.minutos), CODIGO_ESTADO[r.estado],
                 round(r.salio)] for r in d.itertuples()]

        # Los suplentes no van al mapa —el diagrama de Apolonio es del once— pero sí a la lista desplegable de cada
        # partido, para poder leer un cambio completo: quién salió, quién entró y en qué minuto.
        # Los suplentes salen de `part` y NO de `pos`: la tabla de posiciones solo tiene a quien tocó el balón, así
        # que un suplente que entra al 82' y no completa ninguna acción no aparecería. En el ejemplo que lo destapó
        # (Espanyol, partido 3825908) había 3 cambios y solo 1 tenía eventos.
        sup = part[part["estado"] == "suplente"].sort_values("entro")
        sup = sup[sup["nombre"].notna()]
        suplentes = {}
        for (match_id, equipo), d in sup.groupby(["match_id", "team"], sort=False):
            suplentes.setdefault(str(int(match_id)), {})[equipo] = [
                [r.nombre, round(r.entro), round(r.minutos)] for r in d.itertuples()]

        # Solo se publican los partidos que tienen los dos onces completos: uno a medias daría un mapa engañoso.
        completos = {m for m, eq in sitios.items() if len(eq) == 2 and all(len(v) == 11 for v in eq.values())}
        partidos = [[int(r.match_id), r.match_date, r.home_team, r.away_team, int(r.home_score), int(r.away_score)]
                    for r in par.itertuples() if str(int(r.match_id)) in completos]

        datos = {
            "meta": {
                "liga": nombre, "cancha": {"largo": cancha.LARGO, "ancho": cancha.ANCHO},
                "columnas": COLUMNAS, "partidos": len(partidos),
                "generado": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "fuente": "StatsBomb Open Data · posición media de cada titular y acciones exitosas del partido",
            },
            "partidos": partidos,
            "sitios": {m: sitios[m] for m in (str(p[0]) for p in partidos)},
            "columnas_suplentes": ["jugador", "entro", "minutos"],
            "suplentes": {m: suplentes.get(m, {}) for m in (str(p[0]) for p in partidos)},
            "lectura": LECTURA,
        }
        salida = RAIZ / "dashboard-predicciones" / f"analisis_cancha_{clave}.json"
        salida.write_text(json.dumps(limpio(datos), ensure_ascii=False, separators=(",", ":"), allow_nan=False))
        print(f"{nombre}: {len(partidos)} partidos completos -> {salida.relative_to(RAIZ)} "
              f"({salida.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
