"""
Exportador del dashboard de una LIGA EUROPEA de football-data.co.uk (Premier League, La Liga...)
-> dashboard-predicciones/<salida_json>   (data_premier.json, data_laliga.json, ...)
Uso:  python scripts/export_predicciones_europa.py [premier|laliga]     (por defecto premier)
La configuración de cada liga (archivos, renombrado de equipos, ventana, inicio del seguimiento en vivo) vive en
scripts/ligas_europa.py.

Mismo formato de datos que el de Liga MX (export_predicciones_historico.py), de modo que la misma página del
dashboard puede mostrar cualquier liga con un selector. Diferencias propias de esta liga:
  - Fuente: CSV de football-data.co.uk (no FBref), que ya incluyen las cuotas de apuestas 1X2.
  - Se agrega el MERCADO (probabilidades implícitas de Bet365, sin margen) a cada partido, para comparar el modelo
    contra las casas de apuestas.
  - Modelo: Poisson + Dixon-Coles (scripts/modelo_goles.py) con 12 variables (las 8 de Liga MX + tiros a puerta a
    favor y en contra) y perfiles con ventana de los últimos 38 partidos en cada lado. Fue la mejor configuración
    en la comparación fuera de muestra (scripts/europa_comparar_con_mercado.py).
  - Jornada: football-data no trae el número de jornada. Se aproxima con el n-ésimo partido de cada equipo en la
    temporada (local y visitante) y se toma el mayor de los dos; puede desajustarse un poco con partidos aplazados.

VALIDACIÓN: igual que Liga MX. Las predicciones de partidos jugados son FUERA DE MUESTRA (walk-forward por
temporada: cada temporada se predice con un modelo ajustado solo con temporadas anteriores; mínimo 300 partidos de
entrenamiento). Los partidos FUTUROS usan el modelo ajustado con todo el histórico disponible.

CALENDARIO FUTURO: se toma de football-data.co.uk/fixtures.csv (descargado a data/raw/fixtures_football_data.csv),
que trae la próxima(s) jornada(s) con cuotas. Los partidos sin perfil (p. ej. un ascendido sin historial reciente)
se listan sin predicción.

SEGUIMIENTO EN VIVO: usa el registro de predicciones congeladas de la liga
(registro/<registro de la liga>, ver scripts/congelar_predicciones.py <liga>).
"""
import json
import sys

import numpy as np
import pandas as pd
from scipy.stats import fisher_exact

from features_europa import construir_features
from ligas_europa import LIGAS_EUROPA, RAIZ, RUTA_FIXTURES, renombrar_equipos
from modelo_goles import ModeloPoissonDC, ajustar_tarjetas, COLS_GOLES, CLASES
from seguimiento_en_vivo import cargar_congeladas, aplicar_congelada, resumen_seguimiento

liga = sys.argv[1] if len(sys.argv) > 1 else "premier"
cfg = LIGAS_EUROPA[liga]
NOMBRE_LIGA = cfg["nombre"]
RUTA_DATOS = f"{RAIZ}/data/processed/{cfg['dataset']}"
SALIDA = f"{RAIZ}/dashboard-predicciones/{cfg['salida_json']}"
RUTA_REGISTRO = f"{RAIZ}/registro/{cfg['registro']}"
print(f"=== Liga: {NOMBRE_LIGA} ===")

VENTANA = cfg["ventana"]  # partidos por lado en la ventana del perfil (None = expandible; 38 = ~2 temporadas)
MIN_PREV = 10           # partidos previos mínimos en ese lado
MAX_DIAS = 730          # perfil obsoleto si el equipo lleva > 2 años sin jugar en ese lado
MIN_ENTRENAMIENTO = 300
INICIO_EN_VIVO_FECHA = cfg["inicio_en_vivo"]   # los partidos desde esta fecha se congelaron antes de jugarse
INICIO_EN_VIVO_LABEL = cfg["inicio_label"]
COLS = COLS_GOLES + ["local_tp_favor", "local_tp_contra", "visita_tp_favor", "visita_tp_contra"]

# --------------------------------------------------------------------------------------------
# 1) Datos: partidos jugados + calendario futuro
# --------------------------------------------------------------------------------------------
jugados = pd.read_csv(RUTA_DATOS, parse_dates=["Date"])
ultima_fecha = jugados["Date"].max()

fx = pd.read_csv(RUTA_FIXTURES, encoding="utf-8-sig", on_bad_lines="skip")
fx = fx[fx["Div"] == cfg["div"]].copy()
fx = renombrar_equipos(fx, cfg["nombres"])
fx["Date"] = pd.to_datetime(fx["Date"], dayfirst=True, format="mixed")
fx = fx[fx["Date"] > ultima_fecha].copy()            # solo lo que todavía no está en el dataset de partidos jugados
fx["season"] = jugados["season"].iloc[-1]            # la temporada en curso
fx["es_futuro"] = True
jugados["es_futuro"] = False

# Se juntan jugados + futuros para que el perfil de los futuros salga de la misma función (con shift(1) los
# partidos futuros solo "ven" el pasado). Las estadísticas del partido de los futuros son NaN.
base = pd.concat([jugados, fx], ignore_index=True)
base["Time"] = base["Time"].fillna("")
base = base.sort_values(["Date", "Time", "HomeTeam"]).reset_index(drop=True)
base["id"] = base.index

# Jornada aproximada: n-ésimo partido de cada equipo en la temporada (contando local Y visitante, por eso se arma una
# tabla larga con una fila por equipo y partido); la jornada del partido es el MAYOR de los dos equipos. Así, si un
# equipo tiene un partido aplazado pendiente (lleva un partido menos que el resto), el partido no queda en una
# jornada "suelta" distinta a la de sus vecinos.
largo_j = pd.concat([
    base[["id", "season", "Date", "HomeTeam"]].rename(columns={"HomeTeam": "equipo"}).assign(es_local=True),
    base[["id", "season", "Date", "AwayTeam"]].rename(columns={"AwayTeam": "equipo"}).assign(es_local=False),
]).sort_values(["Date", "id"])
largo_j["orden"] = largo_j.groupby(["season", "equipo"]).cumcount() + 1
jornada_por_partido = largo_j.groupby("id")["orden"].max().rename("jornada").reset_index()
base = base.merge(jornada_por_partido, on="id", how="left")
base["jornada_label"] = "J" + base["jornada"].astype(str)

feat = construir_features(base, VENTANA, MIN_PREV, MAX_DIAS)
feat["total_game_cards_real"] = feat["HY"] + feat["HR"] + feat["AY"] + feat["AR"]
feat["gl"], feat["gv"] = feat["FTHG"], feat["FTAG"]
print(f"Partidos jugados: {int((~feat.es_futuro).sum())} | futuros por predecir: {int(feat.es_futuro.sum())}")

# --------------------------------------------------------------------------------------------
# 2) Mercado: probabilidades implícitas de Bet365 sin margen [Empate, Local, Visitante]
# --------------------------------------------------------------------------------------------
def prob_mercado(d):
    inv = np.column_stack([1 / d["B365D"], 1 / d["B365H"], 1 / d["B365A"]])
    return inv / inv.sum(axis=1, keepdims=True)

feat[["m_emp", "m_loc", "m_vis"]] = prob_mercado(feat)

# --------------------------------------------------------------------------------------------
# 3) Predicciones de partidos JUGADOS: walk-forward por temporada (fuera de muestra)
# --------------------------------------------------------------------------------------------
# Solo partidos con perfil completo Y con estadísticas de tarjetas: p. ej. en la Bundesliga el Unión Berlín-Bochum del
# 2024-12-14 (partido suspendido) viene sin ninguna estadística y haría fallar el ajuste del modelo de tarjetas. Ese
# partido sí alimenta los promedios de perfil de otros (pandas ignora los NaN al promediar), pero no se usa para
# entrenar ni evaluar.
con_perfil = feat[(~feat.es_futuro)].dropna(subset=COLS + ["total_game_cards_real"]).copy()
con_perfil["y"] = con_perfil["ganador"].map({c: i for i, c in enumerate(CLASES)})
bloques, ll_modelo, ll_base, ll_mercado = [], [], [], []
for temporada in sorted(con_perfil["season"].unique()):
    prueba = con_perfil[con_perfil["season"] == temporada].copy()
    entren = con_perfil[con_perfil["Date"] < prueba["Date"].min()]
    if len(entren) < MIN_ENTRENAMIENTO:
        continue
    pred = ModeloPoissonDC(COLS).ajustar(entren).predecir(prueba)
    P = pred["probs"]
    prueba[["p_emp", "p_loc", "p_vis"]] = P
    prueba["lam"], prueba["mu"] = pred["lam"], pred["mu"]
    prueba["tarjetas_pred"] = ajustar_tarjetas(entren)(prueba)
    # Modelo y mercado se comparan en LOS MISMOS partidos: se quitan de la evaluación los pocos partidos sin cuotas
    # (p. ej. algunos de la Serie A 2020-21); con NaN en el mercado el log-loss saldría NaN y su "pick" sería basura.
    prueba = prueba[prueba[["m_emp", "m_loc", "m_vis"]].notna().all(axis=1)].copy()
    P = prueba[["p_emp", "p_loc", "p_vis"]].values
    idx = prueba["y"].values.astype(int)
    ll_modelo += list(-np.log(np.clip(P[np.arange(len(prueba)), idx], 1e-12, None)))
    freq = entren["y"].value_counts(normalize=True).reindex([0, 1, 2]).fillna(0).values
    ll_base += list(-np.log(freq[idx]))
    M = prueba[["m_emp", "m_loc", "m_vis"]].values
    ll_mercado += list(-np.log(np.clip(M[np.arange(len(prueba)), idx], 1e-12, None)))
    bloques.append(prueba)
    print(f"  {temporada}: train={len(entren):4d} test={len(prueba):3d}")
ev = pd.concat(bloques, ignore_index=True)

ev["pick"] = [CLASES[k] for k in ev[["p_emp", "p_loc", "p_vis"]].values.argmax(axis=1)]
ev["pick_mercado"] = [CLASES[k] for k in ev[["m_emp", "m_loc", "m_vis"]].values.argmax(axis=1)]
acc_modelo = float((ev["pick"] == ev["ganador"]).mean())
acc_mercado = float((ev["pick_mercado"] == ev["ganador"]).mean())
baseline_local = float((ev["ganador"] == "Local").mean())
print(f"Fuera de muestra: {len(ev)} partidos | acierto modelo {acc_modelo:.1%} | mercado {acc_mercado:.1%} | "
      f"siempre Local {baseline_local:.1%}")
print(f"Log-loss modelo {np.mean(ll_modelo):.4f} | mercado {np.mean(ll_mercado):.4f} | referencia {np.mean(ll_base):.4f}")

# --------------------------------------------------------------------------------------------
# 4) Modelo FINAL (todo el histórico) para los partidos futuros
# --------------------------------------------------------------------------------------------
modelo_final = ModeloPoissonDC(COLS).ajustar(con_perfil)
tarjetas_final = ajustar_tarjetas(con_perfil)
print(f"Modelo final: {len(con_perfil)} partidos, rho = {modelo_final.rho:+.3f}")


def historial_h2h(local, visita, fecha_limite):
    """Enfrentamientos previos entre ambos (cualquier sede) desde 2015; solo informativo, no entra al modelo."""
    prev = jugados[(jugados["Date"] < fecha_limite) &
                   (((jugados["HomeTeam"] == local) & (jugados["AwayTeam"] == visita)) |
                    ((jugados["HomeTeam"] == visita) & (jugados["AwayTeam"] == local)))]
    if len(prev) == 0:
        return {"n_partidos": 0, "dif_goles": None, "favorito": None}
    dif, vl, e, vv = [], 0, 0, 0
    for _, p in prev.iterrows():
        gf_l = p["FTHG"] if p["HomeTeam"] == local else p["FTAG"]
        gf_v = p["FTAG"] if p["HomeTeam"] == local else p["FTHG"]
        dif.append(gf_l - gf_v)
        vl += gf_l > gf_v
        vv += gf_l < gf_v
        e += gf_l == gf_v
    prom = float(np.mean(dif))
    favorito = local if prom > 0.15 else (visita if prom < -0.15 else "parejo")
    return {"n_partidos": len(prev), "dif_goles": round(prom, 2), "favorito": favorito,
            "victorias_local": int(vl), "empates": int(e), "victorias_visita": int(vv)}


futuras = []
for _, f in feat[feat.es_futuro].iterrows():
    base_entrada = {
        "jornada": int(f["jornada"]), "jornada_label": f["jornada_label"], "season": f["season"],
        "torneo": NOMBRE_LIGA, "date": f["Date"].strftime("%Y-%m-%d"), "hora_uk": f["Time"],
        "home_team": f["HomeTeam"], "away_team": f["AwayTeam"],
    }
    if f[COLS].isna().any():
        futuras.append({**base_entrada, "sin_perfil": True})
        continue
    fila = pd.DataFrame([f[COLS]])
    pred = modelo_final.predecir(fila)
    P = pred["probs"][0]
    entrada = {
        **base_entrada, "sin_perfil": False,
        "prob_empate": round(float(P[0]), 3), "prob_local": round(float(P[1]), 3), "prob_visitante": round(float(P[2]), 3),
        "prediccion_ganador": CLASES[int(np.argmax(P))],
        "tarjetas_esperadas": round(float(tarjetas_final(fila.assign(total_game_cards_real=0.0))[0]), 2),
        "goles_esperados_local": round(float(pred["lam"][0]), 2), "goles_esperados_visita": round(float(pred["mu"][0]), 2),
        "local_goles_favor_hist": round(float(f["local_goles_favor"]), 2),
        "local_goles_contra_hist": round(float(f["local_goles_contra"]), 2),
        "visita_goles_favor_hist": round(float(f["visita_goles_favor"]), 2),
        "visita_goles_contra_hist": round(float(f["visita_goles_contra"]), 2),
        "h2h": historial_h2h(f["HomeTeam"], f["AwayTeam"], f["Date"]),
    }
    if not pd.isna(f["m_emp"]):
        Mk = [float(f["m_emp"]), float(f["m_loc"]), float(f["m_vis"])]
        entrada.update(mercado_prob_empate=round(Mk[0], 3), mercado_prob_local=round(Mk[1], 3),
                       mercado_prob_visitante=round(Mk[2], 3), mercado_pick=CLASES[int(np.argmax(Mk))])
    futuras.append(entrada)

# --------------------------------------------------------------------------------------------
# 5) Histórico en el mismo formato que Liga MX (+ campos del mercado)
# --------------------------------------------------------------------------------------------
historico = []
for _, r in ev.iterrows():
    historico.append({
        "season": r["season"], "torneo": NOMBRE_LIGA, "jornada": int(r["jornada"]),
        "jornada_label": r["jornada_label"], "round": "", "date": r["Date"].strftime("%Y-%m-%d"),
        "home_team": r["HomeTeam"], "away_team": r["AwayTeam"], "score": f"{int(r['FTHG'])}–{int(r['FTAG'])}",
        "ganador_real": r["ganador"],
        "prob_empate": round(float(r["p_emp"]), 3), "prob_local": round(float(r["p_loc"]), 3),
        "prob_visitante": round(float(r["p_vis"]), 3),
        "prediccion_ganador": r["pick"], "acerto": bool(r["pick"] == r["ganador"]),
        "tarjetas_esperadas": round(float(r["tarjetas_pred"]), 2),
        "goles_esperados_local": round(float(r["lam"]), 2), "goles_esperados_visita": round(float(r["mu"]), 2),
        "total_game_cards_real": float(r["total_game_cards_real"]),
        "mercado_prob_empate": round(float(r["m_emp"]), 3), "mercado_prob_local": round(float(r["m_loc"]), 3),
        "mercado_prob_visitante": round(float(r["m_vis"]), 3), "mercado_pick": r["pick_mercado"],
    })

# --------------------------------------------------------------------------------------------
# 6) Seguimiento en vivo (predicciones congeladas antes del partido)
# --------------------------------------------------------------------------------------------
congeladas = cargar_congeladas(RUTA_REGISTRO)
historico = [aplicar_congelada(h, True, congeladas) for h in historico]
futuras = [aplicar_congelada(f, False, congeladas) for f in futuras]
seguimiento = resumen_seguimiento(historico, futuras, INICIO_EN_VIVO_FECHA, INICIO_EN_VIVO_LABEL)
print(f"Seguimiento en vivo: {seguimiento['n_jugados']} jugados, {seguimiento['n_pendientes']} pendientes congelados")

# --------------------------------------------------------------------------------------------
# 7) Volcado (los NaN no son JSON válido: se convierten a null y allow_nan=False falla si se cuela alguno)
# --------------------------------------------------------------------------------------------
# Señal de "partido parejo" (las 3 probabilidades a < 12.5 pts entre sí): empates en parejos vs resto, con el MERCADO
# y con el modelo. La frase del dashboard se redacta según lo que realmente salga (Fisher, p < 0.05 = señal clara).
def _senal_parejo(P):
    rg = P.max(axis=1) - P.min(axis=1)
    par = rg <= 0.125
    emp = (ev["ganador"] == "Empate").values
    tabla = [[emp[par].sum(), (~emp[par]).sum()], [emp[~par].sum(), (~emp[~par]).sum()]]
    return emp[par].mean(), emp[~par].mean(), fisher_exact(tabla)[1]

_pm, _rm, _p_mercado = _senal_parejo(ev[["m_emp", "m_loc", "m_vis"]].values)
_pmo, _rmo, _p_modelo = _senal_parejo(ev[["p_emp", "p_loc", "p_vis"]].values)
if _p_mercado < 0.05 and _p_modelo >= 0.05:
    nota_parejo_extra = (f"En {cfg['en_texto']}, con las probabilidades del MERCADO la señal de partido parejo es clara "
                         f"({_pm:.0%} vs {_rm:.0%} de empates); con este modelo es más débil ({_pmo:.0%} vs {_rmo:.0%}).")
elif _p_mercado < 0.05 and _p_modelo < 0.05:
    nota_parejo_extra = (f"En {cfg['en_texto']} la señal de partido parejo se ve tanto con el mercado ({_pm:.0%} vs {_rm:.0%}) "
                         f"como con el modelo ({_pmo:.0%} vs {_rmo:.0%} de empates).")
else:
    nota_parejo_extra = f"En {cfg['en_texto']} la señal de partido parejo no es estadísticamente clara ni con el modelo ni con el mercado."
print(f"Parejos: mercado {_pm:.1%} vs {_rm:.1%} (p={_p_mercado:.4f}) | modelo {_pmo:.1%} vs {_rmo:.1%} (p={_p_modelo:.4f})")

salida = {
    "meta": {
        "liga": NOMBRE_LIGA, "generado": pd.Timestamp.now().strftime("%Y-%m-%d"),
        "modelo": "Poisson + Dixon-Coles (con tiros a puerta)",
        "partidos_evaluados": int(len(ev)), "primera_temporada_evaluada": str(ev["season"].min()),
        "accuracy_fuera_muestra": round(acc_modelo, 4), "baseline_local": round(baseline_local, 4),
        "logloss_modelo": round(float(np.mean(ll_modelo)), 4), "logloss_baseline": round(float(np.mean(ll_base)), 4),
        "accuracy_mercado": round(acc_mercado, 4), "logloss_mercado": round(float(np.mean(ll_mercado)), 4),
        "rho_modelo_final": round(float(modelo_final.rho), 4),
        "fuente": "football-data.co.uk",
        "nota_metodologica": (
            "Modelo de goles Poisson con corrección Dixon-Coles (goles esperados de cada equipo -> probabilidades de "
            "Local/Empate/Visitante), con perfiles de los últimos partidos de cada equipo en su sede (incluye tiros a "
            "puerta). Las predicciones de partidos ya jugados son FUERA DE MUESTRA: cada temporada se predice con un "
            "modelo ajustado solo con temporadas anteriores. El MERCADO son las probabilidades implícitas de las cuotas "
            f"de Bet365 sin margen de la casa: es el referente a vencer; {cfg['nota_mercado']}."),
        "nota_arbitro": "El calendario futuro no trae árbitro asignado, así que las tarjetas esperadas usan solo el perfil de los equipos.",
        "nota_h2h": "El historial cabeza a cabeza (desde 2015-16) es solo informativo: no cambia las probabilidades del modelo.",
        "nota_parejo_extra": nota_parejo_extra,
    },
    "seguimiento_en_vivo": seguimiento,
    "historico": historico,
    "futuras": futuras,
}


def sanear(x):
    if isinstance(x, dict):
        return {k: sanear(v) for k, v in x.items()}
    if isinstance(x, list):
        return [sanear(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        return None if x != x else float(x)
    if isinstance(x, (np.bool_,)):
        return bool(x)
    return x


with open(SALIDA, "w", encoding="utf-8") as fh:
    json.dump(sanear(salida), fh, ensure_ascii=False, indent=1, allow_nan=False)
print(f"{cfg['salida_json']} exportado: {len(historico)} históricos + {len(futuras)} futuros")
