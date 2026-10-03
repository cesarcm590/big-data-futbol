"""
Figuras del protocolo de evaluación (PROTOCOLO_EVALUACION.md / .tex).

Son tres y cada una responde una pregunta del protocolo, no decoran:
  1. ¿El efecto de los partidos parejos aparece en la muestra independiente?   -> §1.7.2
  2. ¿El modelo le gana al mercado en algún sitio?                              -> §1.6.2 y §1.7.3
  3. ¿Están bien calibradas las probabilidades de empate?                       -> §1.2.2

Todas las barras de error son bootstrap por BLOQUES DE JORNADA, no por partido: los partidos de una misma
jornada no son independientes y remuestrearlos sueltos daría intervalos demasiado estrechos.

Salida: figuras/*.pdf (vectorial, para que no pixele en el documento).
Uso:  python scripts/figuras_protocolo.py
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "figuras"
SALIDA.mkdir(exist_ok=True)
RNG = np.random.default_rng(2026)
N_BOOT = 2000
ORD = ["Local", "Empate", "Visitante"]
UMBRAL_PAREJO = 0.125

# Paleta categórica validada con el script de la guía (banda de luminosidad, croma, separación para daltonismo
# y contraste): azul = nuestro modelo, naranja = el mercado. El gris nunca lleva identidad, solo referencias.
AZUL, NARANJA, GRIS = "#2a78d6", "#eb6834", "#8a8a8a"

plt.rcParams.update({
    "font.family": "serif", "font.size": 9, "mathtext.fontset": "cm",
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.edgecolor": "#444444", "axes.labelcolor": "#222222",
    "xtick.color": "#444444", "ytick.color": "#444444", "text.color": "#222222",
    "axes.grid": True, "grid.color": "#dddddd", "grid.linewidth": 0.6,
    "figure.dpi": 150, "savefig.bbox": "tight",
})

LIGAS = [("Liga MX", "data.json"), ("Premier League", "data_premier.json"), ("La Liga", "data_laliga.json"),
         ("Bundesliga", "data_bundesliga.json"), ("Serie A", "data_seriea.json"),
         ("Ligue 1", "data_ligue1.json"), ("Eredivisie", "data_eredivisie.json")]
EXPLORATORIA = ["Liga MX", "Premier League", "La Liga", "Bundesliga", "Serie A"]
CONFIRMATORIA = ["Ligue 1", "Eredivisie"]


def cargar():
    """Un DataFrame con todos los partidos evaluados fuera de muestra de las siete ligas."""
    filas = []
    for liga, archivo in LIGAS:
        ruta = RAIZ / "dashboard-predicciones" / archivo
        h = pd.DataFrame(json.load(open(ruta))["historico"])
        h = h.dropna(subset=["prob_local", "ganador_real"]).copy()
        P = h[["prob_local", "prob_empate", "prob_visitante"]].values
        h["liga"] = liga
        h["parejo"] = (P.max(1) - P.min(1)) <= UMBRAL_PAREJO
        h["empate"] = h["ganador_real"] == "Empate"
        h["y"] = h["ganador_real"].map({c: i for i, c in enumerate(ORD)})
        h["con_mercado"] = h.get("mercado_prob_local", pd.Series(np.nan, index=h.index)).notna()
        filas.append(h)
    return pd.concat(filas, ignore_index=True)


def rps(P, y):
    oh = np.zeros_like(P)
    oh[np.arange(len(y)), y] = 1
    return 0.5 * ((np.cumsum(P, 1)[:, :2] - np.cumsum(oh, 1)[:, :2]) ** 2).sum(1)


def _bloques(d, cols):
    """Parte el DataFrame en jornadas y devuelve, por jornada, los arreglos de numpy que hagan falta.

    Se trabaja con numpy y no con DataFrames porque el bootstrap concatena mil bloques dos mil veces: con
    `pd.concat` cada réplica cuesta milisegundos y el total se va a horas; con `np.concatenate` sobre índices,
    la figura entera sale en segundos. Es el mismo cálculo, no una aproximación.
    """
    claves = d.groupby(["liga", "season", "jornada"], dropna=False).ngroup().values
    orden = np.argsort(claves, kind="stable")
    cortes = np.unique(claves[orden], return_index=True)[1][1:]
    return [np.split(d[c].values[orden], cortes) for c in cols]


def ic_bloques_arrays(bloques, estimador):
    """IC 95 % remuestreando JORNADAS completas. `bloques` es una lista por columna; `estimador` toma arreglos."""
    n = len(bloques[0])
    idx = np.arange(n)
    reps = []
    for _ in range(N_BOOT):
        s = RNG.choice(idx, n, replace=True)
        v = estimador(*[np.concatenate([col[i] for i in s]) for col in bloques])
        if v is not None and np.isfinite(v):
            reps.append(v)
    return np.percentile(reps, [2.5, 97.5])


def _dif(parejo, empate):
    if not parejo.any() or not (~parejo).any():
        return None
    return 100 * (empate[parejo].mean() - empate[~parejo].mean())


def dif_empate(d):
    return _dif(d["parejo"].values, d["empate"].values)


def ic_dif_empate(d):
    return ic_bloques_arrays(_bloques(d, ["parejo", "empate"]), _dif)


def ic_media(d, col):
    return ic_bloques_arrays(_bloques(d, [col]), lambda x: x.mean())


# ---------------------------------------------------------------- 1. el efecto de los parejos
def figura_parejos(T):
    grupos = [
        ("Exploratoria: 5 ligas\n(donde se encontró)", T[T.liga.isin(EXPLORATORIA)], GRIS),
        ("Confirmatoria: Ligue 1 + Eredivisie", T[T.liga.isin(CONFIRMATORIA)], AZUL),
        ("   Ligue 1", T[T.liga == "Ligue 1"], GRIS),
        ("   Eredivisie", T[T.liga == "Eredivisie"], GRIS),
    ]
    fig, ax = plt.subplots(figsize=(6.0, 2.5))
    for i, (et, d, color) in enumerate(grupos):
        y = len(grupos) - 1 - i
        est = dif_empate(d)
        lo, hi = ic_dif_empate(d)
        principal = color == AZUL
        ax.plot([lo, hi], [y, y], color=color, lw=2.2 if principal else 1.4,
                solid_capstyle="round", zorder=2)
        ax.plot([est], [y], "o", color=color, ms=8 if principal else 6,
                markeredgecolor="white", markeredgewidth=1.2, zorder=3)
        # Etiqueta directa: con cuatro filas no hace falta leyenda y se lee el número sin cruzar la vista.
        ax.annotate(f"{est:+.1f}  [{lo:+.1f}, {hi:+.1f}]", (hi, y), xytext=(6, 0),
                    textcoords="offset points", va="center", fontsize=8, color="#222222")
        print(f"    {et.splitlines()[0]:38s} {est:+5.1f}  [{lo:+5.1f}, {hi:+5.1f}]  n={len(d):5d} "
              f"parejos={int(d.parejo.sum()):4d}")
    ax.axvline(0, color="#999999", lw=1, zorder=1)
    ax.set_yticks(range(len(grupos)))
    ax.set_yticklabels([g[0] for g in reversed(grupos)], fontsize=8)
    ax.set_xlabel("Diferencia en la frecuencia de empate: parejos − resto (puntos porcentuales)")
    ax.set_xlim(-4, 17)
    ax.grid(axis="y", visible=False)
    fig.savefig(SALIDA / "parejos.pdf")
    plt.close(fig)
    print("  figuras/parejos.pdf")


# ---------------------------------------------------------------- 2. contra el mercado
def figura_mercado(T):
    M = T[T.con_mercado].copy()
    M["d"] = rps(M[["prob_local", "prob_empate", "prob_visitante"]].values, M["y"].values) - \
             rps(M[["mercado_prob_local", "mercado_prob_empate", "mercado_prob_visitante"]].values, M["y"].values)
    f = lambda d: d["d"].mean()
    grupos = [(liga, M[M.liga == liga]) for liga in
              ["Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1", "Eredivisie"]]
    grupos += [("Todas · solo parejos", M[M.parejo]), ("Todas · resto", M[~M.parejo])]

    fig, ax = plt.subplots(figsize=(6.0, 3.2))
    for i, (et, d) in enumerate(grupos):
        y = len(grupos) - 1 - i
        est = f(d)
        lo, hi = ic_media(d, "d")
        destacado = et.startswith("Todas")
        color = NARANJA if destacado else AZUL
        ax.plot([lo, hi], [y, y], color=color, lw=2.2 if destacado else 1.4, solid_capstyle="round", zorder=2)
        ax.plot([est], [y], "o", color=color, ms=8 if destacado else 6,
                markeredgecolor="white", markeredgewidth=1.2, zorder=3)
        print(f"    {et:24s} {est:+.4f}  [{lo:+.4f}, {hi:+.4f}]  n={len(d):5d}")
    ax.axvline(0, color="#999999", lw=1, zorder=1)
    ax.set_yticks(range(len(grupos)))
    ax.set_yticklabels([g[0] for g in reversed(grupos)], fontsize=8)
    ax.set_xlabel("RPS del modelo − RPS del mercado   (a la derecha del cero: gana el mercado)")
    ax.text(0.02, 0.06, "ningún intervalo cruza el cero:\nel mercado gana en todas",
            transform=ax.transAxes, fontsize=8, color="#555555", va="bottom")
    ax.grid(axis="y", visible=False)
    fig.savefig(SALIDA / "mercado.pdf")
    plt.close(fig)
    print("  figuras/mercado.pdf")


# ---------------------------------------------------------------- 3. calibración del empate
def figura_calibracion(T):
    M = T[T.con_mercado]
    bordes = np.arange(0.10, 0.401, 0.05)
    fig, ax = plt.subplots(figsize=(4.4, 4.0))
    ax.plot([0.10, 0.40], [0.10, 0.40], color=GRIS, lw=1, ls="--", zorder=1,
            label="calibración perfecta")
    for col, color, et in [("prob_empate", AZUL, "modelo"), ("mercado_prob_empate", NARANJA, "mercado")]:
        xs, ys = [], []
        for a, b in zip(bordes[:-1], bordes[1:]):
            sel = M[(M[col] >= a) & (M[col] < b)]
            if len(sel) < 50:
                continue
            xs.append(sel[col].mean())
            ys.append(sel["empate"].mean())
        ax.plot(xs, ys, "-o", color=color, lw=2, ms=6, markeredgecolor="white",
                markeredgewidth=1, label=et, zorder=3)
    ax.set_xlabel("P(empate) declarada")
    ax.set_ylabel("Frecuencia observada de empate")
    ax.set_xlim(0.12, 0.36)
    ax.set_ylim(0.12, 0.36)
    ax.set_aspect("equal")
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    fig.savefig(SALIDA / "calibracion.pdf")
    plt.close(fig)
    print("  figuras/calibracion.pdf")


if __name__ == "__main__":
    T = cargar()
    print(f"{len(T):,} partidos fuera de muestra en {T.liga.nunique()} ligas "
          f"({T.con_mercado.sum():,} con cuotas de mercado)")
    figura_parejos(T)
    figura_mercado(T)
    figura_calibracion(T)
