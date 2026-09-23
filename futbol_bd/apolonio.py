"""
Diagramas de Voronoi ponderados — "modalidad Apolonio" — y el área de dominio de cada jugador.

La idea
-------
Un diagrama de Voronoi normal reparte un plano entre varios puntos ("sitios"): cada lugar del plano pertenece al sitio
más cercano. Todos los sitios valen lo mismo, así que las fronteras son mediatrices (líneas rectas a medio camino).

En la versión ponderada cada sitio tiene un peso, y un sitio con más peso "alcanza" más lejos. Hay dos maneras
clásicas de meter el peso, y las dos se asocian con Apolonio de Perga:

  modo            regla: el lugar x pertenece al sitio i que minimiza    frontera entre dos sitios
  --------------  -----------------------------------------------------  ---------------------------------------------
  multiplicativo  d(x, p_i) / w_i                                        CÍRCULO DE APOLONIO: el lugar donde
                                                                         d_i / d_j = w_i / w_j es un círculo que
                                                                         encierra al sitio más débil
  aditivo         d(x, p_i) − w_i                                        rama de HIPÉRBOLA (d_i − d_j = w_i − w_j);
                                                                         es el "diagrama de Apolonio" de la geometría
                                                                         computacional (CGAL: Apollonius_graph_2)
  voronoi         d(x, p_i)                                              mediatriz (recta) — el caso sin pesos

En fútbol el multiplicativo es el conocido: es el "dominant region" de Taki y Hasegawa (2000), donde el peso es la
velocidad del jugador y d/w es el tiempo que tarda en llegar a cada punto de la cancha. Aquí el plano NO es la cancha
(el panel de FBref no trae posiciones), sino un **espacio de perfil**: cada eje es una tasa por 90 minutos y el peso es
el rendimiento fantasy de la temporada. La celda de un jugador es la región de perfiles que "le pertenecen" — los
perfiles para los que él es la referencia dominante, combinando parecido (distancia) y producción (peso).

Por qué el multiplicativo es el de defecto: es invariante a la escala del peso. Multiplicar todos los pesos por 10 no
cambia nada, así que se pueden usar los puntos fantasy directamente, sin elegir una constante. El aditivo sí necesita
convertir puntos a unidades de distancia (`pesos_aditivos`, parámetro `alcance`), y el dibujo depende de esa elección.
Otra diferencia útil: en el aditivo un jugador puede quedarse SIN celda (si otro, mucho más fuerte, está muy cerca:
w_j − w_i ≥ d(p_i, p_j)); en el multiplicativo todos conservan al menos un círculo alrededor de su punto.

Cómo se calcula
---------------
Por rasterización: se cubre el dominio con una rejilla fina (p. ej. 500 × 500 píxeles) y cada píxel se asigna al sitio
que minimiza la regla. Es exacto salvo en el borde de un píxel, funciona igual para los tres modos (las fronteras
curvas y las celdas partidas en varias islas no requieren casos especiales), y el área de cada celda es simplemente
la fracción de píxeles que ganó. La alternativa analítica (CGAL) no tiene una interfaz estable para Python.
"""
from __future__ import annotations

import numpy as np

MODOS = ("multiplicativo", "aditivo", "voronoi")


def escalar(valores, limite_inferior, limite_superior):
    """Lleva `valores` al intervalo [0, 1] con límites FIJOS.

    Los límites se fijan por fuera (p. ej. el máximo de toda la liga en todas las temporadas) para que el mismo perfil
    caiga en el mismo lugar en todos los paneles; si cada temporada se escalara por separado, las posiciones y las
    áreas no se podrían comparar entre temporadas.
    """
    v = np.asarray(valores, dtype=float)
    return (v - limite_inferior) / (limite_superior - limite_inferior)


def pesos_aditivos(puntos, alcance: float = 0.15):
    """Convierte puntos fantasy a pesos aditivos (unidades de distancia del espacio escalado a [0, 1]).

    El peor del grupo recibe 0 y el mejor `alcance`: es la "ventaja de salida" del mejor jugador, en la misma unidad
    que las distancias. Con 0.15, el mejor le gana su celda a un rival que esté hasta 0.15 más cerca de ese punto.
    """
    p = np.asarray(puntos, dtype=float)
    rango = p.max() - p.min()
    return np.zeros_like(p) if rango == 0 else alcance * (p - p.min()) / rango


def etiquetar(sitios, pesos=None, modo: str = "multiplicativo", resolucion: int = 500,
              limites=((0.0, 1.0), (0.0, 1.0))):
    """Asigna cada píxel del dominio al sitio que lo domina.

    Parámetros
      sitios      array (n, 2) con las coordenadas (x, y) de cada sitio, en las unidades de `limites`
      pesos       array (n,) — obligatorio salvo en modo 'voronoi'. En 'multiplicativo' deben ser > 0.
      modo        'multiplicativo' | 'aditivo' | 'voronoi'
      resolucion  píxeles por lado
      limites     ((x_min, x_max), (y_min, y_max)) del dominio

    Devuelve (etiquetas, xs, ys): `etiquetas[fila, col]` es el índice del sitio dueño del píxel cuyo centro está en
    (xs[col], ys[fila]). Se usan CENTROS de píxel para que la fracción de píxeles sea un estimador sin sesgo del área.

    Se recorre sitio por sitio guardando el mejor valor visto (en vez de construir un arreglo n × res × res): la memoria
    queda en O(res²) aunque haya cientos de sitios. En caso de empate exacto gana el sitio de menor índice.
    """
    if modo not in MODOS:
        raise ValueError(f"modo debe ser uno de {MODOS}, no {modo!r}")
    sitios = np.asarray(sitios, dtype=float)
    n = len(sitios)
    if modo == "voronoi":
        pesos = np.ones(n)
    elif pesos is None:
        raise ValueError(f"el modo {modo!r} necesita pesos")
    pesos = np.asarray(pesos, dtype=float)
    if modo == "multiplicativo" and np.any(pesos <= 0):
        raise ValueError("en modo multiplicativo todos los pesos deben ser positivos (d / w)")

    (x0, x1), (y0, y1) = limites
    xs = x0 + (np.arange(resolucion) + 0.5) * (x1 - x0) / resolucion
    ys = y0 + (np.arange(resolucion) + 0.5) * (y1 - y0) / resolucion
    X, Y = np.meshgrid(xs, ys)

    mejor = np.full(X.shape, np.inf)
    etiquetas = np.full(X.shape, -1, dtype=np.int32)
    for k, ((sx, sy), w) in enumerate(zip(sitios, pesos)):
        d = np.hypot(X - sx, Y - sy)
        if modo == "multiplicativo":
            valor = d / w
        elif modo == "aditivo":
            valor = d - w
        else:
            valor = d
        gana = valor < mejor
        mejor[gana] = valor[gana]
        etiquetas[gana] = k
    return etiquetas, xs, ys


def areas(etiquetas, n_sitios: int):
    """Fracción del dominio que ocupa cada celda (suman 1). Un sitio sin celda (posible en modo aditivo) tiene 0."""
    return np.bincount(etiquetas.ravel(), minlength=n_sitios) / etiquetas.size


def circulo_apolonio(sitio_debil, peso_debil, sitio_fuerte, peso_fuerte):
    """Centro y radio de la frontera multiplicativa entre dos sitios (el círculo de Apolonio que rodea al débil).

    Con k = w_débil / w_fuerte < 1, la frontera es el conjunto de puntos x con |x − a| / |x − b| = k (a = débil,
    b = fuerte). Desarrollando el cuadrado se llega a un círculo con
        centro = (a − k² b) / (1 − k²)        radio = k |a − b| / (1 − k²)
    Si k → 0 el círculo se encoge sobre a; si k → 1 el radio explota y el círculo tiende a la mediatriz (Voronoi normal).
    Se usa para validar la rasterización en `tests/test_apolonio.py` y para explicar el modo en el notebook.
    """
    a, b = np.asarray(sitio_debil, float), np.asarray(sitio_fuerte, float)
    k = peso_debil / peso_fuerte
    if not 0 < k < 1:
        raise ValueError("el primer sitio debe ser el de menor peso (0 < w_débil < w_fuerte)")
    centro = (a - k**2 * b) / (1 - k**2)
    radio = k * np.linalg.norm(a - b) / (1 - k**2)
    return centro, radio


def mascara_fronteras(etiquetas):
    """Píxeles donde cambia el dueño respecto al vecino de la derecha o de arriba — para dibujar las fronteras."""
    borde = np.zeros(etiquetas.shape, dtype=bool)
    borde[:, 1:] |= etiquetas[:, 1:] != etiquetas[:, :-1]
    borde[1:, :] |= etiquetas[1:, :] != etiquetas[:-1, :]
    return borde


def dibujar(ax, etiquetas, xs, ys, valor_por_celda, cmap, norm, color_frontera="#fcfcfb"):
    """Pinta las celdas con un color por celda (p. ej. los puntos fantasy del dueño) y las fronteras como líneas finas.

    Las fronteras se dibujan en el color de fondo (no en negro): una separación de "aire" entre áreas de color se lee
    más limpia que un contorno oscuro. Devuelve el objeto de imagen para poder agregarle una barra de color.
    """
    extent = (xs[0] - (xs[1] - xs[0]) / 2, xs[-1] + (xs[1] - xs[0]) / 2,
              ys[0] - (ys[1] - ys[0]) / 2, ys[-1] + (ys[1] - ys[0]) / 2)
    valores = np.asarray(valor_por_celda, dtype=float)[etiquetas]
    img = ax.imshow(valores, origin="lower", extent=extent, cmap=cmap, norm=norm, interpolation="nearest",
                    aspect="auto", zorder=0)
    borde = mascara_fronteras(etiquetas)
    capa = np.zeros(borde.shape + (4,))
    capa[borde] = _hex_a_rgba(color_frontera)
    ax.imshow(capa, origin="lower", extent=extent, interpolation="nearest", aspect="auto", zorder=1)
    return img


def _hex_a_rgba(color):
    color = color.lstrip("#")
    return [int(color[i:i + 2], 16) / 255 for i in (0, 2, 4)] + [1.0]
