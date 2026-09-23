"""
Liga europea (Premier, La Liga...): ¿el modelo Poisson + Dixon-Coles del proyecto se acerca al mercado de apuestas?
Uso:  python scripts/europa_comparar_con_mercado.py [premier|laliga]     (por defecto premier)

PREGUNTA
--------
En Liga MX no había cuotas gratuitas. En las ligas europeas sí (football-data.co.uk), así que aquí podemos hacer la
prueba más exigente: comparar nuestro modelo contra las probabilidades implícitas de las casas de apuestas.
Se espera que el mercado gane (agrega información que nosotros no tenemos: lesiones, alineaciones, dinero
informado...); lo interesante es CUÁNTO gana y si el modelo aporta algo que el mercado no tiene.

QUÉ SE COMPARA (siempre FUERA de muestra, walk-forward por temporada: cada temporada se predice con un modelo
ajustado solo con temporadas anteriores):
  - Modelo A : Poisson + Dixon-Coles con las MISMAS 8 variables que Liga MX (goles a favor/en contra, corners y
               tarjetas a favor de cada equipo; perfil de local como local y de visitante como visitante).
  - Modelo B : igual que A + tiros a puerta a favor/en contra (la Premier trae tiros; Liga MX vía FBref también
               los tiene, pero no se usaron en el modelo de Liga MX).
  - Mercado  : probabilidades implícitas de las cuotas 1X2, normalizadas para quitar el margen de la casa
               (método proporcional: p_i = (1/cuota_i) / suma(1/cuota_j)). Se usan Bet365 (cuota previa) y
               Pinnacle de cierre (la casa "sharp" de referencia) donde existen.
  - Baseline : frecuencias históricas de Local/Empate/Visitante (sin información del partido).

VARIABLES PRE-PARTIDO (sin fuga de datos): para cada partido, el perfil del equipo local se calcula con SUS
partidos ANTERIORES como local, y el del visitante con sus anteriores como visitante. Se prueban tres ventanas:
expandible (todo el pasado), últimos 38 y últimos 19 partidos en ese lado (~2 y ~1 temporadas). Se exige un
mínimo de partidos previos (MIN_PREV) para que la media sea estable; equipos recién ascendidos sin historial
quedan fuera hasta acumularlo.

MÉTRICAS: acierto del pick, log-loss y Brier (calidad de las probabilidades), RPS (Ranked Probability Score,
la métrica estándar en fútbol porque respeta el orden Local < Empate < Visitante), AUC de P(empate) y la
señal de "partido parejo" (mismo umbral de 12.5 puntos que el dashboard de Liga MX).
"""
import sys

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.metrics import roc_auc_score

from modelo_goles import ModeloPoissonDC, COLS_GOLES, CLASES
from features_europa import construir_features
from ligas_europa import LIGAS_EUROPA, RAIZ

liga = sys.argv[1] if len(sys.argv) > 1 else "premier"
cfg = LIGAS_EUROPA[liga]
RUTA = f"{RAIZ}/data/processed/{cfg['dataset']}"
print(f"=== Liga: {cfg['nombre']} ===")
MIN_PREV = 10                 # partidos previos mínimos (en ese lado) para tener perfil
MIN_ENTRENAMIENTO = 300       # mínimo de partidos con perfil para poder entrenar una temporada de prueba
UMBRAL_PAREJO = 0.125

COLS_B = COLS_GOLES + ["local_tp_favor", "local_tp_contra", "visita_tp_favor", "visita_tp_contra"]

df = pd.read_csv(RUTA, parse_dates=["Date"]).sort_values(["Date", "Time", "HomeTeam"]).reset_index(drop=True)
df["id"] = df.index
df["gl"] = df["FTHG"].astype(int)
df["gv"] = df["FTAG"].astype(int)


# --------------------------------------------------------------------------------------------
# 1) Perfiles pre-partido: construir_features vive en features_europa.py (compartido con el exportador del
#    dashboard). Aquí se usa sin max_dias, igual que en la comparación original.
# --------------------------------------------------------------------------------------------


# --------------------------------------------------------------------------------------------
# 2) Mercado: probabilidades implícitas normalizadas [Empate, Local, Visitante]
# --------------------------------------------------------------------------------------------
def prob_mercado(d, h, x, a):
    """Cuotas decimales -> probabilidades sin margen. Devuelve arreglo n x 3 (NaN si faltan cuotas)."""
    inv = np.column_stack([1 / d[x], 1 / d[h], 1 / d[a]])       # orden Empate, Local, Visitante
    return inv / inv.sum(axis=1, keepdims=True)


MERCADOS = {
    "Mercado Bet365 (previa)": ("B365H", "B365D", "B365A"),
    "Mercado Pinnacle (cierre)": ("PSCH", "PSCD", "PSCA"),
}
for nombre, (h, x, a) in MERCADOS.items():
    df[[f"pm_{nombre}_emp", f"pm_{nombre}_loc", f"pm_{nombre}_vis"]] = prob_mercado(df, h, x, a)


# --------------------------------------------------------------------------------------------
# 3) Walk-forward por temporada del modelo de goles
# --------------------------------------------------------------------------------------------
def walk_forward(feat, cols):
    """Predice cada temporada con un modelo ajustado solo con temporadas anteriores. Devuelve DataFrame con
    id, season, p_emp, p_loc, p_vis para los partidos con perfil disponible en las temporadas de prueba."""
    bloques = []
    con_perfil = feat.dropna(subset=cols)
    for temporada in sorted(con_perfil.season.unique()):
        prueba = con_perfil[con_perfil.season == temporada]
        entren = con_perfil[con_perfil.Date < prueba.Date.min()]
        if len(entren) < MIN_ENTRENAMIENTO:
            continue
        pred = ModeloPoissonDC(cols).ajustar(entren).predecir(prueba)
        b = prueba[["id", "season"]].copy()
        b[["p_emp", "p_loc", "p_vis"]] = pred["probs"]
        bloques.append(b)
    return pd.concat(bloques, ignore_index=True)


# Ventanas de perfil: la de la config de la liga (~2 temporadas de partidos por sede) y la mitad (~1 temporada).
V, V2 = cfg["ventana"], cfg["ventana"] // 2
configs = {
    "Modelo A expandible (8 var)": (None, COLS_GOLES),
    f"Modelo A ventana {V} (8 var)": (V, COLS_GOLES),
    f"Modelo A ventana {V2} (8 var)": (V2, COLS_GOLES),
    "Modelo B expandible (+tiros a puerta)": (None, COLS_B),
    f"Modelo B ventana {V} (+tiros a puerta)": (V, COLS_B),
}
predicciones = {}
for nombre, (ventana, cols) in configs.items():
    feat = construir_features(df, ventana)
    predicciones[nombre] = walk_forward(feat, cols)
    n = len(predicciones[nombre])
    print(f"{nombre:42s}: {n} partidos evaluados, temporadas {predicciones[nombre].season.min()} -> {predicciones[nombre].season.max()}")


# --------------------------------------------------------------------------------------------
# 4) Métricas
# --------------------------------------------------------------------------------------------
def metricas(y, P):
    """y: 0=Empate,1=Local,2=Visitante ; P: n x 3 en el mismo orden."""
    n = len(y)
    pick = P.argmax(axis=1)
    acierto = (pick == y).mean()
    logloss = -np.log(np.clip(P[np.arange(n), y], 1e-12, None)).mean()
    onehot = np.eye(3)[y]
    brier = ((P - onehot) ** 2).sum(axis=1).mean()
    # RPS con el orden Local < Empate < Visitante: columnas [Local, Empate, Visitante] = [1, 0, 2]
    Po, Oo = P[:, [1, 0, 2]], onehot[:, [1, 0, 2]]
    rps = 0.5 * ((np.cumsum(Po, axis=1)[:, :2] - np.cumsum(Oo, axis=1)[:, :2]) ** 2).sum(axis=1).mean()
    es_emp = (y == 0)
    auc = roc_auc_score(es_emp, P[:, 0]) if es_emp.any() and len(np.unique(P[:, 0])) > 1 else np.nan
    rango = P.max(axis=1) - P.min(axis=1)
    par = rango <= UMBRAL_PAREJO
    return {
        "n": n, "acierto": acierto, "logloss": logloss, "brier": brier, "RPS": rps,
        "AUC empate": auc, "P(emp) media": P[:, 0].mean(), "emp reales": es_emp.mean(),
        "n parejos": int(par.sum()), "emp% parejos": es_emp[par].mean() if par.any() else np.nan,
        "emp% resto": es_emp[~par].mean() if (~par).any() else np.nan,
    }


y_todo = df["ganador"].map({c: i for i, c in enumerate(CLASES)}).values
df["y"] = y_todo

# Subconjunto común de evaluación: partidos donde TODOS los modelos y el mercado Bet365 tienen predicción.
ids_comunes = set(df.id)
for p in predicciones.values():
    ids_comunes &= set(p.id)
ids_comunes &= set(df.dropna(subset=["B365H", "B365D", "B365A"]).id)
ids_comunes = np.array(sorted(ids_comunes))
sub = df.set_index("id").loc[ids_comunes]
print(f"\nSubconjunto común de evaluación: {len(ids_comunes)} partidos, {sub.season.min()} -> {sub.season.max()}")

filas = {}
for nombre, p in predicciones.items():
    P = p.set_index("id").loc[ids_comunes, ["p_emp", "p_loc", "p_vis"]].values
    filas[nombre] = metricas(sub["y"].values, P)
for nombre in MERCADOS:
    P = sub[[f"pm_{nombre}_emp", f"pm_{nombre}_loc", f"pm_{nombre}_vis"]].values
    if not np.isnan(P).any():
        filas[nombre] = metricas(sub["y"].values, P)

# Baseline: frecuencias del entrenamiento (todas las temporadas previas a cada temporada de prueba)
P_bs = np.zeros((len(sub), 3))
for temporada in sub.season.unique():
    idx = (sub.season == temporada).values
    previo = df[df.Date < sub.loc[idx, "Date"].min()]
    freq = previo["y"].value_counts(normalize=True).reindex([0, 1, 2]).fillna(0).values
    P_bs[idx] = freq
filas["Baseline frecuencias"] = metricas(sub["y"].values, P_bs)

pd.set_option("display.width", 250)
tabla = pd.DataFrame(filas).T
print("\n=== Subconjunto común (mismos partidos para todos), FUERA de muestra ===")
print(tabla.round(4).to_string())

# Pinnacle de cierre: no existe completo en 2025-26 -> se evalúa aparte en el subconjunto que sí lo tiene.
mejor_modelo = tabla.loc[[k for k in tabla.index if k.startswith("Modelo")], "logloss"].idxmin()
print(f"\nMejor modelo por log-loss: {mejor_modelo}")
ids_ps = np.array(sorted(set(ids_comunes) & set(df.dropna(subset=["PSCH", "PSCD", "PSCA"]).id)))
sub_ps = df.set_index("id").loc[ids_ps]
P_m = predicciones[mejor_modelo].set_index("id").loc[ids_ps, ["p_emp", "p_loc", "p_vis"]].values
P_ps = sub_ps[["pm_Mercado Pinnacle (cierre)_emp", "pm_Mercado Pinnacle (cierre)_loc", "pm_Mercado Pinnacle (cierre)_vis"]].values
print(f"\n=== Subconjunto con Pinnacle de cierre ({len(ids_ps)} partidos) ===")
print(pd.DataFrame({mejor_modelo: metricas(sub_ps['y'].values, P_m), "Pinnacle (cierre)": metricas(sub_ps['y'].values, P_ps)}).T.round(4).to_string())

# --------------------------------------------------------------------------------------------
# 5) Por temporada: log-loss del mejor modelo vs. Bet365
# --------------------------------------------------------------------------------------------
print("\n=== Log-loss por temporada: modelo vs Bet365 ===")
P_mm = predicciones[mejor_modelo].set_index("id").loc[ids_comunes, ["p_emp", "p_loc", "p_vis"]].values
P_b3 = sub[["pm_Mercado Bet365 (previa)_emp", "pm_Mercado Bet365 (previa)_loc", "pm_Mercado Bet365 (previa)_vis"]].values
n = len(sub)
ll_m = -np.log(np.clip(P_mm[np.arange(n), sub.y.values], 1e-12, None))
ll_b = -np.log(np.clip(P_b3[np.arange(n), sub.y.values], 1e-12, None))
por_temp = pd.DataFrame({"season": sub.season.values, "modelo": ll_m, "bet365": ll_b}).groupby("season").mean()
por_temp["dif (modelo - mercado)"] = por_temp.modelo - por_temp.bet365
print(por_temp.round(4).to_string())

# Bootstrap pareado: ¿la diferencia con el mercado es ruido?
rng = np.random.default_rng(7)
d = ll_m - ll_b
boot = np.array([d[rng.integers(0, n, n)].mean() for _ in range(2000)])
print(f"\nDiferencia media de log-loss (modelo - Bet365) = {d.mean():+.4f}, IC95% [{np.percentile(boot, 2.5):+.4f}, {np.percentile(boot, 97.5):+.4f}]")

# --------------------------------------------------------------------------------------------
# 6) ¿El modelo aporta algo que el mercado no tiene? (regresión de apilado, walk-forward)
# --------------------------------------------------------------------------------------------
# Se ajusta un logit multinomial del resultado usando las razones de log-probabilidad (vs empate) del mercado
# solo, y del mercado + modelo. Si agregar el modelo baja el log-loss fuera de muestra, aporta información
# adicional; si no, el mercado ya lo contenía todo.
def log_razones(P):
    return np.column_stack([np.log(P[:, 1] / P[:, 0]), np.log(P[:, 2] / P[:, 0])])

Xm = log_razones(P_b3)
Xmm = np.column_stack([Xm, log_razones(P_mm)])
y_sub = sub.y.values
temps = sorted(sub.season.unique())
ll_solo, ll_ambos, ll_mercado_crudo = [], [], []
for t in temps[1:]:                                        # la primera temporada solo entrena
    tr = (sub.season < t).values
    te = (sub.season == t).values
    if tr.sum() < 300:
        continue
    for X, acum in [(Xm, ll_solo), (Xmm, ll_ambos)]:
        mod = sm.MNLogit(y_sub[tr], sm.add_constant(X[tr], has_constant="add")).fit(disp=False, maxiter=200)
        pr = np.asarray(mod.predict(sm.add_constant(X[te], has_constant="add")))
        acum += list(-np.log(np.clip(pr[np.arange(te.sum()), y_sub[te]], 1e-12, None)))
    ll_mercado_crudo += list(ll_b[te])
print(f"\n=== ¿El modelo agrega información sobre el mercado? ({len(ll_solo)} partidos, temporadas {temps[1]} -> {temps[-1]}) ===")
print(f"Log-loss mercado crudo (Bet365):        {np.mean(ll_mercado_crudo):.4f}")
print(f"Log-loss mercado recalibrado (logit):    {np.mean(ll_solo):.4f}")
print(f"Log-loss mercado + modelo (logit):       {np.mean(ll_ambos):.4f}")
dd = np.array(ll_ambos) - np.array(ll_solo)
boot2 = np.array([dd[rng.integers(0, len(dd), len(dd))].mean() for _ in range(2000)])
print(f"Diferencia (mercado+modelo) - (mercado): {dd.mean():+.4f}, IC95% [{np.percentile(boot2, 2.5):+.4f}, {np.percentile(boot2, 97.5):+.4f}]  (negativo = el modelo aporta)")

sub_out = sub.reset_index()[["id", "season", "Date", "HomeTeam", "AwayTeam", "y"]].copy()
sub_out[["mod_emp", "mod_loc", "mod_vis"]] = P_mm
sub_out[["bet_emp", "bet_loc", "bet_vis"]] = P_b3
sub_out.to_csv(f"{RAIZ}/data/processed/{liga}_comparacion_modelo_vs_mercado.csv", index=False)
print(f"\nResultados guardados en data/processed/{liga}_comparacion_modelo_vs_mercado.csv")
