"""
Estilo común de las figuras del proyecto (notebooks 17 en adelante), para que todas se lean igual.

Reglas que aplica (vienen de una guía de visualización con paleta validada para daltonismo):
  - Tintas neutras para texto, ejes y rejilla; el color se reserva para los DATOS.
  - Identidad (un color por jugador/equipo seguido): los 3 primeros tonos de una paleta categórica cuyo orden se validó
    para que cualquier par se distinga con deuteranopia/protanopia. Más de 3 en una misma figura -> otra forma
    (small multiples o resaltar uno y dejar el resto en gris).
  - Magnitud (más/menos): una rampa de UN solo tono, azul claro -> oscuro. Nunca un arcoíris.
  - Un solo eje Y por gráfica: dos medidas de escala distinta van en paneles separados.
"""
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

SUPERFICIE, TINTA, TINTA_2, TENUE, REJILLA, EJE = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
AZUL, NARANJA, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
# Paleta categórica completa, en el orden validado (cualquier par contiguo se distingue con daltonismo). Se usa solo
# cuando hay que dibujar varias entidades a la vez y ninguna es "la protagonista", como las 7 ligas en la comparativa;
# para 2-3 series basta con AZUL/NARANJA/AQUA.
CATEGORICA = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
# Tonos de la misma rampa azul, para bandas (rango intercuartil) detrás de una línea azul.
AZUL_CLARO = "#cde2fb"
RAMPA_AZUL = LinearSegmentedColormap.from_list(
    "azul", ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95"])


def aplicar():
    """Configura matplotlib con el estilo del proyecto (llamar una vez al inicio del notebook)."""
    plt.rcParams.update({
        "figure.facecolor": SUPERFICIE, "axes.facecolor": SUPERFICIE, "savefig.facecolor": SUPERFICIE,
        "axes.edgecolor": EJE, "axes.labelcolor": TINTA_2, "xtick.color": TENUE, "ytick.color": TENUE,
        "axes.spines.top": False, "axes.spines.right": False, "axes.titlesize": 11, "axes.titlecolor": TINTA,
        "axes.titlelocation": "left", "font.size": 10, "legend.frameon": False,
    })


def rejilla_y(ax):
    """Rejilla horizontal fina y detrás de los datos (ayuda a leer valores sin competir con las marcas)."""
    ax.grid(axis="y", color=REJILLA, linewidth=0.8)
    ax.set_axisbelow(True)


def etiquetas_temporada(ax, temporadas, rotacion=45):
    """Eje X con temporadas cortas: 2024 -> '24-25'."""
    ax.set_xticks(list(temporadas))
    ax.set_xticklabels([f"{t % 100:02d}-{(t + 1) % 100:02d}" for t in temporadas], rotation=rotacion)
