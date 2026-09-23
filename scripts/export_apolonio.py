"""
Exporta los diagramas de Voronoi en modalidad Apolonio (notebook 17) al JSON que lee la sección 9 de `analisis.html`.

    python scripts/export_apolonio.py             # -> dashboard-predicciones/analisis_apolonio.json

Qué se publica y qué NO
-----------------------
La página **no** recibe imágenes: recibe los sitios (un jugador = un punto del espacio de perfil, con su peso) y
rasteriza el diagrama en el navegador. Así se puede cambiar de temporada, de equipo, de jugador y de modo sin volver
al servidor, y el archivo pesa unos cientos de KB en vez de 112 imágenes.

Para que el dibujo del navegador no pueda desviarse del de Python, cada sitio lleva además el **área que le calcula
`apolonio.etiquetar`** en modo multiplicativo. La página recalcula esas áreas con su propio código y las compara: si
difieren más de lo que explica la resolución, lo avisa en la consola.

Construcción, idéntica a la del notebook 17 (que solo cubría la Liga MX; aquí se repite en las siete):
  - sitios: los 20 mejores atacantes (FW/MF) por puntos fantasy de cada liga-temporada, con 900+ minutos
  - plano: goles sin penal por 90 (x) contra asistencias por 90 (y)
  - peso: los puntos fantasy OFENSIVOS de la temporada (`pts_total`), no el fantasy completo de la Fase 21: el
    completo solo existe desde 2014-15, y para atacantes la parte defensiva vale 0-7 puntos, así que usarlo costaría
    cuatro temporadas a cambio de casi nada
  - dominio FIJO por liga (de 0 al máximo de todas sus temporadas +5%), para que un mismo perfil caiga en el mismo
    lugar en cualquier temporada y las áreas se puedan comparar entre años
"""
import json
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from futbol_bd import apolonio, fantasy, plantillas  # noqa: E402
from export_analisis_liga import limpio  # noqa: E402  (misma conversión a tipos de JSON)

LIGAS = ["Liga MX", "Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1", "Eredivisie"]
SALIDA = RAIZ / "dashboard-predicciones" / "analisis_apolonio.json"

N_SITIOS = 20        # atacantes por temporada; con muchos más las celdas se vuelven ilegibles
MIN_MINUTOS = 900    # por debajo, las tasas por 90 son sobre todo ruido
EJE_X, EJE_Y = "goals_pens_per90", "assists_per90"
RESOLUCION = 300     # la del cálculo de áreas del notebook (el error contra 500 es < 1%)
COLUMNAS = ["jugador", "equipo", "id", "x", "y", "pts", "area"]

LECTURA = {
    "que_es": (
        "Un diagrama de Voronoi reparte un plano entre varios puntos: cada lugar pertenece al más cercano. En la "
        "modalidad de Apolonio cada punto tiene además un PESO y el que más pesa alcanza más lejos, así que las "
        "fronteras dejan de ser rectas y se vuelven círculos de Apolonio. Aquí el plano no es la cancha —el panel de "
        "FBref no trae posiciones— sino un espacio de perfil: goles sin penal por 90 en un eje, asistencias por 90 en "
        "el otro, y el peso son los puntos fantasy de la temporada. La celda de un jugador es la región de perfiles "
        "para los que él es la referencia dominante, combinando parecido (distancia) y producción (peso)."),
    "modos": (
        "Tres formas de repartir el mismo plano. Voronoi normal ignora el peso: solo cuenta quién está más cerca. "
        "El multiplicativo (distancia ÷ peso) es el de defecto porque es invariante a la escala del peso —multiplicar "
        "todos los puntos por 10 no cambia el dibujo—, así que no hay ninguna constante que elegir; sus fronteras son "
        "los círculos de Apolonio. El aditivo (distancia − peso) es el «diagrama de Apolonio» de la geometría "
        "computacional, pero necesita convertir puntos a unidades de distancia con un alcance arbitrario, y con él un "
        "jugador puede quedarse SIN celda si otro mucho más fuerte está muy cerca."),
    "area": (
        "**El área de la celda NO es una medida de rendimiento, y conviene decirlo antes de que alguien la use como "
        "tal.** Depende tanto de quién más apareció ese año como del propio jugador: se puede crecer sin mejorar, "
        "solo porque los vecinos de perfil desaparecieron. En la Liga MX su correlación con los puntos del equipo "
        "quedó en 0.43 (multiplicativo) y es muy volátil — un jugador pasó de 1% a 39% y de vuelta a 1% mientras su "
        "percentil apenas se movía de 98 a 100 y a 95. Para medir a un jugador está el percentil fantasy; el mapa "
        "sirve para ver VECINDARIOS: quién ocupa qué perfil, quién se mueve de zona y quién no tiene competencia "
        "cerca."),
}


def main():
    jt = fantasy.puntos_fantasy(plantillas.cargar_jugadores_temporada())
    salida = {}
    for nombre in LIGAS:
        elegibles = jt[(jt["league"] == nombre) & jt["pos_principal"].isin(fantasy.POSICIONES_ATAQUE)
                       & (jt["minutes"] >= MIN_MINUTOS)]
        sitios = (elegibles.sort_values("pts_total", ascending=False).groupby("season").head(N_SITIOS)
                  .sort_values(["temporada_inicio", "pts_total"], ascending=[True, False]))
        # Dominio fijo de la liga: el mismo perfil cae en el mismo lugar en todas sus temporadas.
        x_max, y_max = sitios[EJE_X].max() * 1.05, sitios[EJE_Y].max() * 1.05

        por_temporada = {}
        for temporada, d in sitios.groupby("season", sort=True):
            u = apolonio.escalar(d[EJE_X], 0, x_max)
            v = apolonio.escalar(d[EJE_Y], 0, y_max)
            etiquetas, _, _ = apolonio.etiquetar(list(zip(u, v)), d["pts_total"].to_numpy(),
                                                 modo="multiplicativo", resolucion=RESOLUCION)
            areas = apolonio.areas(etiquetas, len(d))
            por_temporada[temporada] = [
                [r.player, r.equipo_principal, r.id_jugador, round(float(gx), 4), round(float(gy), 4),
                 round(float(r.pts_total), 1), round(float(a), 5)]
                for r, gx, gy, a in zip(d.itertuples(), d[EJE_X], d[EJE_Y], areas)]

        salida[nombre] = {
            "dominio": {"x_max": round(float(x_max), 4), "y_max": round(float(y_max), 4)},
            "puntos": {"min": round(float(sitios["pts_total"].min()), 1),
                       "max": round(float(sitios["pts_total"].max()), 1)},
            "temporadas": sorted(por_temporada),
            "sitios": por_temporada,
        }

    datos = {
        "meta": {
            "ligas": LIGAS, "columnas": COLUMNAS, "n_sitios": N_SITIOS, "min_minutos": MIN_MINUTOS, "resolucion": RESOLUCION,
            "eje_x": "Goles sin penal por 90 min", "eje_y": "Asistencias por 90 min",
            "generado": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "fuente": "FBref; atacantes (FW/MF) con 900+ minutos, peso = puntos fantasy ofensivos de la temporada",
        },
        "ligas": salida,
        "lectura": LECTURA,
    }
    SALIDA.write_text(json.dumps(limpio(datos), ensure_ascii=False, separators=(",", ":"), allow_nan=False))
    total = sum(len(s) for liga in salida.values() for s in liga["sitios"].values())
    print(f"Apolonio: {total:,} sitios en {len(LIGAS)} ligas -> {SALIDA.relative_to(RAIZ)} "
          f"({SALIDA.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
