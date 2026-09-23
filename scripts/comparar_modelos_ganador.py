"""
Comparación de modelos para predecir el resultado (Local / Empate / Visitante) en Liga MX.

PREGUNTA: ¿un modelo de goles tipo Poisson predice mejor el resultado -y sobre todo los EMPATES-
que la regresión logística multinomial (MNLogit) que usa hoy el dashboard?

MODELOS COMPARADOS (todos con las MISMAS 8 variables pre-partido, calculadas solo con partidos
anteriores a la fecha del partido, sin fuga de datos):
  A) MNLogit            -> modelo actual del dashboard: predice directo la clase (Empate/Local/Visitante).
  B) Poisson indep.     -> dos regresiones de Poisson (goles del local, goles del visitante) y se asume
                           que ambos marcadores son independientes. P(resultado) sale de sumar la matriz
                           de marcadores: P(empate) = P(0-0) + P(1-1) + P(2-2) + ...
  C) Poisson + Dixon-Coles -> igual que B pero corrigiendo la dependencia en marcadores bajos
                           (0-0, 1-0, 0-1, 1-1) con un parámetro rho, que es justo donde el Poisson
                           independiente suele subestimar los empates.
  D) Baseline           -> frecuencias de Local/Empate/Visitante del set de entrenamiento (sin información
                           del partido); es el piso contra el que se mide log-loss.

VALIDACIÓN (la parte importante): el dashboard actual ajusta el modelo UNA sola vez con todo el histórico
y luego "predice" partidos que ya vio (dentro de muestra). Aquí es fuera de muestra: para cada temporada
de prueba se reajusta cada modelo usando SOLO los partidos de temporadas anteriores (walk-forward por
temporada), y se predice esa temporada. Así los coeficientes tampoco "ven el futuro".

MÉTRICAS:
  - accuracy (acierto del pick con mayor probabilidad)
  - log-loss y Brier (calidad de las PROBABILIDADES, no solo del pick; menor = mejor)
  - para el empate: P(empate) media vs tasa real, AUC de P(empate) para detectar empates,
    tasa de empate en el 20% de partidos con mayor P(empate), y cuántas veces el pick es "Empate".
"""
import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.metrics import roc_auc_score
from modelo_goles import matriz_marcadores, probs_desde_matriz, estimar_rho, MAX_GOLES

RUTA_PICKLE = ("/private/tmp/claude-501/-Users-javiercarrillo-Downloads-gds-asset-risk-model-experiment-"
               "november-alerts/f5545e3f-cc04-4967-9df3-6be0ac2556da/scratchpad/features_todas.pkl")
TEMPORADAS_PRUEBA = ["2022-2023", "2023-2024", "2024-2025", "2025-2026", "2026-2027"]
CLASES = ["Empate", "Local", "Visitante"]   # orden fijo de columnas de probabilidad en TODOS los modelos
COLS = ["local_goles_favor", "local_goles_contra", "local_corners_favor", "local_tarjetas_favor",
        "visita_goles_favor", "visita_goles_contra", "visita_corners_favor", "visita_tarjetas_favor"]

# --------------------------------------------------------------------------------------------
# 1) Datos: variables pre-partido + goles reales
# --------------------------------------------------------------------------------------------
df = pd.read_pickle(RUTA_PICKLE).copy()
df["date"] = pd.to_datetime(df["date"])

# El marcador viene como texto ("2–1"); en penales de liguilla puede traer paréntesis "(4) 1–1 (5)".
# Buscamos el patrón "N–M" (guion largo o corto) y tomamos el marcador de los 90+ minutos.
goles = df["score"].astype(str).str.extract(r"(\d+)\s*[–\-]\s*(\d+)")
df["gl"] = goles[0].astype(float)
df["gv"] = goles[1].astype(float)
df = df.dropna(subset=["gl", "gv"]).copy()
df["gl"], df["gv"] = df["gl"].astype(int), df["gv"].astype(int)

# Comprobación de consistencia: el ganador derivado de los goles debe coincidir con ganador_real.
derivado = np.where(df.gl > df.gv, "Local", np.where(df.gl < df.gv, "Visitante", "Empate"))
n_incons = int((derivado != df["ganador_real"].values).sum())
print(f"Partidos: {len(df)} | inconsistencias goles vs ganador_real: {n_incons}")
df = df[derivado == df["ganador_real"].values].copy()   # se descartan las (si las hay) para no contaminar
df["y"] = df["ganador_real"].map({c: i for i, c in enumerate(CLASES)}).astype(int)


# --------------------------------------------------------------------------------------------
# 2) Utilidades de los modelos de goles
# --------------------------------------------------------------------------------------------
# (las funciones matriz_marcadores / probs_desde_matriz / estimar_rho viven en modelo_goles.py,
#  compartido con el exportador del dashboard, para no mantener dos copias del mismo modelo)


# --------------------------------------------------------------------------------------------
# 3) Walk-forward por temporada
# --------------------------------------------------------------------------------------------
resultados = []
for temporada in TEMPORADAS_PRUEBA:
    prueba = df[df.season == temporada]
    if prueba.empty:
        continue
    entren = df[df.date < prueba.date.min()]              # SOLO partidos anteriores a la temporada
    if len(entren) < 300:
        continue
    Xtr = sm.add_constant(entren[COLS].astype(float), has_constant="add")
    Xte = sm.add_constant(prueba[COLS].astype(float), has_constant="add")

    # A) MNLogit --------------------------------------------------------------------------
    mn = sm.MNLogit(entren["y"], Xtr).fit(disp=False, maxiter=200)
    p_mn = np.asarray(mn.predict(Xte))                    # columnas = clases 0,1,2 = Empate,Local,Visitante

    # B) Poisson independiente -------------------------------------------------------------
    g_loc = sm.GLM(entren["gl"], Xtr, family=sm.families.Poisson()).fit()
    g_vis = sm.GLM(entren["gv"], Xtr, family=sm.families.Poisson()).fit()
    lam_te, mu_te = g_loc.predict(Xte).values, g_vis.predict(Xte).values
    p_po = probs_desde_matriz(matriz_marcadores(lam_te, mu_te))

    # C) Poisson + Dixon-Coles -------------------------------------------------------------
    rho = estimar_rho(entren["gl"].values, entren["gv"].values,
                      g_loc.predict(Xtr).values, g_vis.predict(Xtr).values)
    p_dc = probs_desde_matriz(matriz_marcadores(lam_te, mu_te, rho))

    # D) Baseline: frecuencias del entrenamiento -------------------------------------------
    freq = entren["y"].value_counts(normalize=True).reindex([0, 1, 2]).values
    p_bs = np.tile(freq, (len(prueba), 1))

    for nombre, p in [("A) MNLogit (actual)", p_mn), ("B) Poisson indep.", p_po),
                      ("C) Poisson + Dixon-Coles", p_dc), ("D) Baseline frecuencias", p_bs)]:
        t = prueba[["season", "date", "y", "gl", "gv"]].copy()
        t["modelo"] = nombre
        t[["p_emp", "p_loc", "p_vis"]] = p
        t["rho"] = rho if nombre.startswith("C") else np.nan
        resultados.append(t)
    print(f"  {temporada}: train={len(entren):4d} test={len(prueba):3d} | rho DC={rho:+.3f} | "
          f"goles medios pred. local {lam_te.mean():.2f} / visita {mu_te.mean():.2f}")

R = pd.concat(resultados, ignore_index=True)
R["rango"] = R[["p_emp", "p_loc", "p_vis"]].max(axis=1) - R[["p_emp", "p_loc", "p_vis"]].min(axis=1)
R["pick"] = R[["p_emp", "p_loc", "p_vis"]].values.argmax(axis=1)   # 0=Empate, 1=Local, 2=Visitante
R["acierto"] = (R["pick"] == R["y"]).astype(int)
R["es_empate"] = (R["y"] == 0).astype(int)
P = R[["p_emp", "p_loc", "p_vis"]].values
R["logloss"] = -np.log(np.clip(P[np.arange(len(R)), R["y"].values], 1e-12, None))
onehot = np.eye(3)[R["y"].values]
R["brier"] = ((P - onehot) ** 2).sum(axis=1)

# --------------------------------------------------------------------------------------------
# 4) Resumen de métricas
# --------------------------------------------------------------------------------------------
def resumen(g):
    top = g[g.p_emp >= g.p_emp.quantile(0.8)]              # 20% de partidos con mayor P(empate)
    parejos = g[g.rango <= 0.125]
    return pd.Series({
        "n": len(g),
        "accuracy": g.acierto.mean(),
        "logloss": g.logloss.mean(),
        "brier": g.brier.mean(),
        "P(emp) media": g.p_emp.mean(),
        "emp. reales": g.es_empate.mean(),
        "AUC empate": roc_auc_score(g.es_empate, g.p_emp) if g.es_empate.nunique() > 1 and g.p_emp.nunique() > 1 else np.nan,
        "emp% top20 P(emp)": top.es_empate.mean(),
        "n picks Empate": int((g.pick == 0).sum()),
        "n parejos": len(parejos),
        "emp% parejos": parejos.es_empate.mean() if len(parejos) else np.nan,
    })

print("\n=== FUERA DE MUESTRA (walk-forward por temporada), todas las temporadas de prueba ===")
tabla = R.groupby("modelo").apply(resumen, include_groups=False)
pd.set_option("display.width", 220)
print(tabla.round(3).to_string())

print("\n=== Accuracy y log-loss por temporada de prueba ===")
print(R.pivot_table(index="season", columns="modelo", values="acierto", aggfunc="mean").round(3).to_string())
print()
print(R.pivot_table(index="season", columns="modelo", values="logloss", aggfunc="mean").round(3).to_string())

# --------------------------------------------------------------------------------------------
# 5) ¿Las diferencias son reales o ruido? Bootstrap pareado (mismos partidos en cada modelo)
# --------------------------------------------------------------------------------------------
print("\n=== Bootstrap pareado (2000 remuestreos de partidos): diferencia vs MNLogit ===")
base = R[R.modelo.str.startswith("A)")].reset_index(drop=True)
rng = np.random.default_rng(42)
for nombre in ["B) Poisson indep.", "C) Poisson + Dixon-Coles", "D) Baseline frecuencias"]:
    otro = R[R.modelo == nombre].reset_index(drop=True)
    assert (base.date.values == otro.date.values).all() and (base.y.values == otro.y.values).all()
    for metrica in ["acierto", "logloss"]:
        d = otro[metrica].values - base[metrica].values
        boot = np.array([d[rng.integers(0, len(d), len(d))].mean() for _ in range(2000)])
        lo, hi = np.percentile(boot, [2.5, 97.5])
        print(f"  {nombre:26s} {metrica:8s} dif media = {d.mean():+.4f}  IC95% [{lo:+.4f}, {hi:+.4f}]")

# --------------------------------------------------------------------------------------------
# 6) Regla de "partido parejo": ¿algún modelo logra que ⚖ señale empates de forma útil?
# --------------------------------------------------------------------------------------------
print("\n=== ¿Qué tan útil es la marca 'parejo' (rango <= 12.5 pts) según cada modelo? ===")
for nombre, g in R.groupby("modelo"):
    par, res = g[g.rango <= 0.125], g[g.rango > 0.125]
    if len(par) == 0:
        continue
    print(f"  {nombre:26s} parejos={len(par):4d} ({len(par)/len(g):.0%}) | empates en parejos={par.es_empate.mean():.3f} "
          f"vs resto={res.es_empate.mean():.3f}")

R.to_pickle(RUTA_PICKLE.replace("features_todas.pkl", "comparacion_resultados.pkl"))
