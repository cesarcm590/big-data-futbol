"""
Dashboard de predicciones: arma un archivo navegable por temporada + jornada donde para cada
partido YA JUGADO se muestra la predicción junto al resultado real, y para partidos futuros
(jornada en curso/próxima) solo la predicción.

MODELO (cambio del 2026-09-18): Poisson + corrección Dixon-Coles (ver scripts/modelo_goles.py),
que reemplaza a la regresión logística multinomial que se usaba antes. La comparación fuera de
muestra (scripts/comparar_modelos_ganador.py, adenda de la Fase 13) mostró que predicen igual de
bien el ganador, pero el Poisson da una probabilidad de empate directa a partir de los goles
esperados.

DECISIONES METODOLÓGICAS IMPORTANTES (léelas antes de tocar este script):
1) Perfiles por FECHA: el perfil de cada equipo se recalcula por fecha en vez de por temporada;
   usa TODOS los partidos jugados estrictamente antes de la fecha del partido (ventana
   "expandible" continua; ver notebook 15, sección 8), así la predicción cambia jornada a jornada.
2) Validación FUERA DE MUESTRA (walk-forward por temporada): las predicciones del histórico se
   generan con un modelo ajustado SOLO con partidos de temporadas anteriores a la que se predice.
   Antes se ajustaba una sola vez con todo el histórico y se "predecían" partidos ya vistos; eso
   inflaba el desempeño (p. ej. la señal de "partido parejo" bajaba de 32% a ~27-29% de empates
   al evaluar fuera de muestra). Las primeras temporadas (2020-21 y 2021-22) solo sirven para entrenar:
   hace falta un mínimo de partidos de entrenamiento (UMBRAL_MIN_ENTRENAMIENTO).
3) Los partidos FUTUROS usan un modelo ajustado con TODO el histórico disponible hoy (lo más
   informado posible), que es lo que se usaría en la vida real para predecir lo que viene.
"""
from pathlib import Path
import pandas as pd
import numpy as np
import statsmodels.api as sm
import json
import os
from modelo_goles import ModeloPoissonDC, ajustar_tarjetas, CLASES
from seguimiento_en_vivo import cargar_congeladas, aplicar_congelada, resumen_seguimiento

RAIZ = str(Path(__file__).resolve().parents[1])

df = pd.read_csv(f"{RAIZ}/data/processed/matches_ligamx_2020_2025_v3_arbitraje.csv", dtype=str)

mapa_nombres_arbitro = {
    "Victor Caceres": "Víctor Cáceres", "Oscar Mejia": "Oscar Mejía",
    "Marco Ortíz": "Marco Antonio Ortíz", "Luis Santander": "Luis Enrique Santander",
    "Erick Miranda": "Erick Yair Miranda", "Guillermo Pacheco": "Guillermo Pacheco Larios",
    "Jesus Lopez": "Jesús López", "Ismael Lopez": "Ismael López",
}
df["referee"] = df["referee"].replace(mapa_nombres_arbitro)

columnas_numericas = [
    "home_shots_total", "away_shots_total", "home_yellow", "home_red", "home_total_cards",
    "away_yellow", "away_red", "away_total_cards", "total_game_cards",
    "home_fouls", "away_fouls", "home_corners", "away_corners",
]
for col in columnas_numericas:
    df[col] = pd.to_numeric(df[col], errors="coerce")

patron_score = r"(?:\(\d+\)\s*)?(\d+)\s*[–-]\s*(\d+)(?:\s*\(\d+\))?"
goles = df["score"].str.extract(patron_score)
df["home_goals"] = pd.to_numeric(goles[0], errors="coerce")
df["away_goals"] = pd.to_numeric(goles[1], errors="coerce")
condiciones = [df["home_goals"] > df["away_goals"], df["home_goals"] < df["away_goals"]]
df["ganador"] = np.select(condiciones, ["Local", "Visitante"], default="Empate")
df["date"] = pd.to_datetime(df["date"])

# --- Jornada/ronda: viene del calendario maestro, no de v3 ---
sched = pd.read_csv(f"{RAIZ}/data/raw/matches_ligamx_2020_2025_schedule.csv", dtype=str)
sched["date"] = pd.to_datetime(sched["date"])
sched_slim = sched[["date", "home_team", "away_team", "round", "gameweek"]].drop_duplicates(
    subset=["date", "home_team", "away_team"]
)
# v3 ya trae su propia columna `gameweek` (con más nulos, se limpió en
# Numbers) -- se quita antes del merge para que no choque con la del
# calendario maestro (mismo fix que ya se aplicó en export_dashboard_data.py).
df = df.drop(columns=["gameweek"], errors="ignore")
df = df.merge(sched_slim, on=["date", "home_team", "away_team"], how="left")


def _jornada_num(fila):
    """Número de jornada dentro de su torneo (Apertura/Clausura), o None
    para partidos de liguilla (no tienen un número de jornada estándar)."""
    if pd.isna(fila["round"]) or "Regular Season" not in str(fila["round"]):
        return None
    return int(float(fila["gameweek"])) if pd.notna(fila["gameweek"]) else None


df["jornada_num"] = df.apply(_jornada_num, axis=1)
df["torneo"] = df["round"].apply(
    lambda r: r.split(" —")[0].split(" Regular")[0] if pd.notna(r) else None
)

_traduccion_fase = {
    "Quarter-finals": "Cuartos de final", "Semi-finals": "Semifinal", "Finals": "Final",
    "Reclassification": "Reclasificación", "7-seed match": "Definición de puesto",
    "8-seed match": "Definición de puesto", "9/10 match": "Definición de puesto",
}


def _jornada_label(fila):
    if pd.isna(fila["round"]):
        return "N/D"
    if "Regular Season" in fila["round"]:
        gw = fila["jornada_num"]
        return f"{fila['torneo']} - J{int(gw)}" if gw is not None else f"{fila['torneo']} - Jornada N/D"
    _, _, fase_en = fila["round"].partition(" — ")
    return f"{fila['torneo']} - {_traduccion_fase.get(fase_en, fase_en)}"


df["jornada_label"] = df.apply(_jornada_label, axis=1)

# --- Perfil de equipo por FECHA (ventana expandible continua, no por temporada) ---
metricas_perfil = ["goals_for", "goals_against", "corners_for", "cards_for"]


def a_formato_largo(partidos):
    local = pd.DataFrame({
        "date": partidos["date"], "team": partidos["home_team"], "rival": partidos["away_team"],
        "es_local": 1, "goals_for": partidos["home_goals"], "goals_against": partidos["away_goals"],
        "corners_for": partidos["home_corners"], "cards_for": partidos["home_total_cards"],
    })
    visitante = pd.DataFrame({
        "date": partidos["date"], "team": partidos["away_team"], "rival": partidos["home_team"],
        "es_local": 0, "goals_for": partidos["away_goals"], "goals_against": partidos["home_goals"],
        "corners_for": partidos["away_corners"], "cards_for": partidos["away_total_cards"],
    })
    return pd.concat([local, visitante], ignore_index=True)


jugados = df[df["home_goals"].notna()].copy().sort_values("date").reset_index(drop=True)
largo_completo = a_formato_largo(jugados)

# Umbral mínimo de partidos-liga antes de arriesgarnos a predecir: con muy
# pocos partidos jugados en toda la liga, el perfil de cualquier equipo es
# puro ruido. 100 partidos ~ equivale a poco más de 10 jornadas completas
# (18 equipos / 2 = 9 partidos por jornada).
UMBRAL_MINIMO_HISTORIA = 100

fechas_unicas = sorted(jugados["date"].unique())
cache_perfil_por_fecha = {}
cache_dureza_por_fecha = {}


def perfil_como_de(fecha):
    if fecha not in cache_perfil_por_fecha:
        anteriores = largo_completo[largo_completo["date"] < fecha]
        if len(anteriores) < UMBRAL_MINIMO_HISTORIA * 2:  # *2 porque largo_completo tiene 2 filas por partido
            cache_perfil_por_fecha[fecha] = None
        else:
            cache_perfil_por_fecha[fecha] = anteriores.groupby(["team", "es_local"])[metricas_perfil].mean()
    return cache_perfil_por_fecha[fecha]


def dureza_arbitro_como_de(fecha):
    if fecha not in cache_dureza_por_fecha:
        anteriores = jugados[jugados["date"] < fecha]
        if len(anteriores) < UMBRAL_MINIMO_HISTORIA:
            cache_dureza_por_fecha[fecha] = None
        else:
            cache_dureza_por_fecha[fecha] = anteriores.groupby("referee")["total_game_cards"].mean()
    return cache_dureza_por_fecha[fecha]


print(f"Partidos jugados totales: {len(jugados)}, fechas únicas: {len(fechas_unicas)}")

# --- Construir features para TODOS los partidos jugados (retrospectivo) ---
filas = []
for _, partido in jugados.iterrows():
    perfil = perfil_como_de(partido["date"])
    if perfil is None:
        continue
    try:
        local_perfil = perfil.loc[(partido["home_team"], 1)]
        visita_perfil = perfil.loc[(partido["away_team"], 0)]
    except KeyError:
        continue
    dureza = dureza_arbitro_como_de(partido["date"])
    dureza_arbitro = dureza.get(partido["referee"]) if dureza is not None else None

    filas.append({
        "date": partido["date"], "season": partido["season"], "torneo": partido["torneo"],
        "jornada_num": partido["jornada_num"], "round": partido["round"],
        "jornada_label": partido["jornada_label"],
        "home_team": partido["home_team"], "away_team": partido["away_team"],
        "score": partido["score"], "ganador_real": partido["ganador"],
        "total_game_cards_real": partido["total_game_cards"],
        "local_goles_favor": local_perfil["goals_for"], "local_goles_contra": local_perfil["goals_against"],
        "local_corners_favor": local_perfil["corners_for"], "local_tarjetas_favor": local_perfil["cards_for"],
        "visita_goles_favor": visita_perfil["goals_for"], "visita_goles_contra": visita_perfil["goals_against"],
        "visita_corners_favor": visita_perfil["corners_for"], "visita_tarjetas_favor": visita_perfil["cards_for"],
        "arbitro_dureza": dureza_arbitro,
    })

features_todas = pd.DataFrame(filas)
print(f"Partidos con feature disponible (>= {UMBRAL_MINIMO_HISTORIA} partidos de historia previa): {len(features_todas)}")

# --- Goles reales del partido (variable objetivo del modelo Poisson) ---
# El marcador puede venir con penales de liguilla, p. ej. "(4) 1–1 (5)"; patron_score ya los ignora.
g = features_todas["score"].astype(str).str.extract(patron_score)
features_todas["gl"] = pd.to_numeric(g[0], errors="coerce")
features_todas["gv"] = pd.to_numeric(g[1], errors="coerce")
features_todas = features_todas.dropna(subset=["gl", "gv"]).sort_values("date").reset_index(drop=True)
features_completas = features_todas.copy()   # con TODAS las temporadas: para el modelo final (futuros)

# --- Predicciones del histórico FUERA DE MUESTRA: walk-forward por temporada ---
UMBRAL_MIN_ENTRENAMIENTO = 300   # mínimo de partidos de entrenamiento; con menos (p. ej. 241 en 2021-22) rho y coeficientes salen inestables
bloques = []
logloss_modelo, logloss_baseline = [], []
for temporada in sorted(features_todas["season"].unique()):
    prueba = features_todas[features_todas["season"] == temporada].copy()
    entren = features_todas[features_todas["date"] < prueba["date"].min()]   # solo el pasado
    if len(entren) < UMBRAL_MIN_ENTRENAMIENTO:
        print(f"  {temporada}: solo entrena (train previo = {len(entren)} < {UMBRAL_MIN_ENTRENAMIENTO})")
        continue
    modelo_t = ModeloPoissonDC().ajustar(entren)
    pred = modelo_t.predecir(prueba)
    probs = pred["probs"]                                                       # [Empate, Local, Visitante]
    prueba["prob_empate"], prueba["prob_local"], prueba["prob_visitante"] = probs.T
    prueba["goles_esperados_local"], prueba["goles_esperados_visita"] = pred["lam"], pred["mu"]
    prueba["prediccion_ganador"] = [CLASES[k] for k in probs.argmax(axis=1)]
    prueba["acerto"] = prueba["prediccion_ganador"] == prueba["ganador_real"]
    prueba["tarjetas_esperadas"] = ajustar_tarjetas(entren)(prueba)
    # Log-loss del modelo y de la referencia (frecuencias del entrenamiento, sin información del partido)
    idx_real = prueba["ganador_real"].map({c: i for i, c in enumerate(CLASES)}).values
    logloss_modelo += list(-np.log(np.clip(probs[np.arange(len(prueba)), idx_real], 1e-12, None)))
    freq = entren["ganador_real"].value_counts(normalize=True).reindex(CLASES).values
    logloss_baseline += list(-np.log(freq[idx_real]))
    bloques.append(prueba)
    print(f"  {temporada}: train={len(entren):4d} test={len(prueba):3d} rho={modelo_t.rho:+.3f} "
          f"accuracy={prueba['acerto'].mean():.1%}")

features_todas = pd.concat(bloques, ignore_index=True)
for c in ["prob_empate", "prob_local", "prob_visitante"]:
    features_todas[c] = features_todas[c].round(3)
features_todas["tarjetas_esperadas"] = features_todas["tarjetas_esperadas"].round(2)
features_todas["goles_esperados_local"] = features_todas["goles_esperados_local"].round(2)
features_todas["goles_esperados_visita"] = features_todas["goles_esperados_visita"].round(2)

primera_temporada_eval = features_todas["season"].min()
print(f"Accuracy FUERA de muestra: {features_todas['acerto'].mean():.1%} sobre {len(features_todas)} partidos "
      f"(desde {primera_temporada_eval}) | referencia 'siempre Local': "
      f"{(features_todas['ganador_real'] == 'Local').mean():.1%}")
print(f"Log-loss modelo {np.mean(logloss_modelo):.4f} vs referencia {np.mean(logloss_baseline):.4f}")

# --- Modelo FINAL (para los partidos futuros): ajustado con TODO el histórico disponible ---
modelo_final = ModeloPoissonDC().ajustar(features_completas)
predecir_tarjetas_final = ajustar_tarjetas(features_completas)
print(f"Modelo final: {len(features_completas)} partidos de entrenamiento, rho = {modelo_final.rho:+.3f}")

# --- Historial cabeza a cabeza (informativo, no entra al modelo -- ver conversación) ---
def historial_h2h(equipo_local, equipo_visita, fecha_limite):
    anteriores = jugados[
        (jugados["date"] < fecha_limite) &
        (((jugados["home_team"] == equipo_local) & (jugados["away_team"] == equipo_visita)) |
         ((jugados["home_team"] == equipo_visita) & (jugados["away_team"] == equipo_local)))
    ]
    if len(anteriores) == 0:
        return {"n_partidos": 0, "dif_goles": None, "favorito": None}
    dif_goles, vl, e, vv = [], 0, 0, 0
    for _, p in anteriores.iterrows():
        gf_l = p["home_goals"] if p["home_team"] == equipo_local else p["away_goals"]
        gf_v = p["away_goals"] if p["home_team"] == equipo_local else p["home_goals"]
        dif_goles.append(gf_l - gf_v)
        if gf_l > gf_v: vl += 1
        elif gf_l < gf_v: vv += 1
        else: e += 1
    prom = float(np.mean(dif_goles))
    favorito = equipo_local if prom > 0.15 else (equipo_visita if prom < -0.15 else "parejo")
    return {"n_partidos": len(anteriores), "dif_goles": round(prom, 2), "favorito": favorito,
            "victorias_local": vl, "empates": e, "victorias_visita": vv}


# --- Partidos futuros: jornada 9 y 10, ya calendarizadas en FBref aunque sin jugar ---
# (obtenidas en vivo de FBref el 2026-09-17 -- no están en el calendario local
# todavía porque solo se scrapea lo que ya se jugó)
partidos_futuros_raw = [
    # Jornada 9 (Apertura 2026), 18-20 sept 2026
    {"jornada": 9, "date": "2026-09-18", "home_team": "Puebla", "away_team": "Atlante"},
    {"jornada": 9, "date": "2026-09-18", "home_team": "FC Juárez", "away_team": "UANL"},
    {"jornada": 9, "date": "2026-09-19", "home_team": "Atlas", "away_team": "UNAM"},
    {"jornada": 9, "date": "2026-09-19", "home_team": "Atlético San Luis", "away_team": "Necaxa"},
    {"jornada": 9, "date": "2026-09-19", "home_team": "Monterrey", "away_team": "Cruz Azul"},
    {"jornada": 9, "date": "2026-09-19", "home_team": "América", "away_team": "Guadalajara"},
    {"jornada": 9, "date": "2026-09-20", "home_team": "Pachuca", "away_team": "Tijuana"},
    {"jornada": 9, "date": "2026-09-20", "home_team": "Toluca", "away_team": "Santos Laguna"},
    {"jornada": 9, "date": "2026-09-20", "home_team": "Querétaro", "away_team": "León"},
    # Jornada 10 (Apertura 2026), 25-27 sept 2026
    {"jornada": 10, "date": "2026-09-25", "home_team": "Atlante", "away_team": "Monterrey"},
    {"jornada": 10, "date": "2026-09-25", "home_team": "Tijuana", "away_team": "Atlas"},
    {"jornada": 10, "date": "2026-09-26", "home_team": "Cruz Azul", "away_team": "Toluca"},
    {"jornada": 10, "date": "2026-09-26", "home_team": "Guadalajara", "away_team": "Querétaro"},
    {"jornada": 10, "date": "2026-09-26", "home_team": "Santos Laguna", "away_team": "Pachuca"},
    {"jornada": 10, "date": "2026-09-26", "home_team": "UANL", "away_team": "Puebla"},
    {"jornada": 10, "date": "2026-09-27", "home_team": "UNAM", "away_team": "Atlético San Luis"},
    {"jornada": 10, "date": "2026-09-27", "home_team": "León", "away_team": "FC Juárez"},
    {"jornada": 10, "date": "2026-09-27", "home_team": "Necaxa", "away_team": "América"},
]

perfil_actual = perfil_como_de(pd.Timestamp("2026-09-18"))  # todo lo jugado hasta la fecha de hoy

predicciones_futuras = []
for p in partidos_futuros_raw:
    try:
        local_perfil = perfil_actual.loc[(p["home_team"], 1)]
        visita_perfil = perfil_actual.loc[(p["away_team"], 0)]
    except KeyError:
        predicciones_futuras.append({
            "jornada": p["jornada"], "jornada_label": f"Apertura 2026 - J{p['jornada']}",
            "season": "2026-2027", "torneo": "Apertura 2026",
            "date": p["date"], "home_team": p["home_team"], "away_team": p["away_team"],
            "sin_perfil": True,
        })
        continue

    fila = {
        "local_goles_favor": local_perfil["goals_for"], "local_goles_contra": local_perfil["goals_against"],
        "local_corners_favor": local_perfil["corners_for"], "local_tarjetas_favor": local_perfil["cards_for"],
        "visita_goles_favor": visita_perfil["goals_for"], "visita_goles_contra": visita_perfil["goals_against"],
        "visita_corners_favor": visita_perfil["corners_for"], "visita_tarjetas_favor": visita_perfil["cards_for"],
    }
    df_fila = pd.DataFrame([fila])
    pred_f = modelo_final.predecir(df_fila)
    probs = pred_f["probs"][0]                                   # [Empate, Local, Visitante]
    cards_pred = float(predecir_tarjetas_final(df_fila)[0])
    h2h = historial_h2h(p["home_team"], p["away_team"], pd.Timestamp(p["date"]))

    predicciones_futuras.append({
        "jornada": p["jornada"], "jornada_label": f"Apertura 2026 - J{p['jornada']}",
        "season": "2026-2027", "torneo": "Apertura 2026",
        "date": p["date"], "home_team": p["home_team"], "away_team": p["away_team"],
        "sin_perfil": False,
        "prob_empate": round(float(probs[0]), 3), "prob_local": round(float(probs[1]), 3),
        "prob_visitante": round(float(probs[2]), 3),
        "prediccion_ganador": CLASES[int(np.argmax(probs))],
        "tarjetas_esperadas": round(cards_pred, 2),
        "goles_esperados_local": round(float(pred_f["lam"][0]), 2),
        "goles_esperados_visita": round(float(pred_f["mu"][0]), 2),
        "local_goles_favor_hist": round(float(fila["local_goles_favor"]), 2),
        "local_goles_contra_hist": round(float(fila["local_goles_contra"]), 2),
        "visita_goles_favor_hist": round(float(fila["visita_goles_favor"]), 2),
        "visita_goles_contra_hist": round(float(fila["visita_goles_contra"]), 2),
        "h2h": h2h,
    })

print(f"\n{len(predicciones_futuras)} predicciones futuras generadas (jornadas 9 y 10)")

# --- Armar el histórico retrospectivo agrupado por temporada + jornada ---
features_todas["date_str"] = features_todas["date"].dt.strftime("%Y-%m-%d")
historico = []
for _, fila in features_todas.iterrows():
    historico.append({
        "season": fila["season"], "torneo": fila["torneo"], "jornada": fila["jornada_num"],
        "jornada_label": fila["jornada_label"],
        "round": fila["round"], "date": fila["date_str"],
        "home_team": fila["home_team"], "away_team": fila["away_team"], "score": fila["score"],
        "ganador_real": fila["ganador_real"],
        "prob_empate": fila["prob_empate"], "prob_local": fila["prob_local"], "prob_visitante": fila["prob_visitante"],
        "prediccion_ganador": fila["prediccion_ganador"], "acerto": bool(fila["acerto"]),
        "tarjetas_esperadas": fila["tarjetas_esperadas"],
        "goles_esperados_local": fila["goles_esperados_local"], "goles_esperados_visita": fila["goles_esperados_visita"],
        "total_game_cards_real": None if pd.isna(fila["total_game_cards_real"]) else float(fila["total_game_cards_real"]),
    })

# --- Registro de predicciones CONGELADAS (seguimiento en vivo) ---
# scripts/congelar_predicciones.py guarda, ANTES de cada jornada, lo que el modelo dijo. Para los partidos que estén
# en ese registro se usan esas probabilidades originales (no las recalculadas por el walk-forward), de modo que
# "en vivo" se mide contra lo que realmente se dijo antes del partido. Lógica compartida con la Premier en
# scripts/seguimiento_en_vivo.py.
INICIO_EN_VIVO_FECHA = "2026-09-25"     # inicio del seguimiento oficial (jornada 10, Apertura 2026)
congeladas = cargar_congeladas(f"{RAIZ}/registro/predicciones_congeladas.csv")
historico = [aplicar_congelada(h, True, congeladas) for h in historico]
predicciones_futuras = [aplicar_congelada(f, False, congeladas) for f in predicciones_futuras]
seguimiento_en_vivo = resumen_seguimiento(historico, predicciones_futuras, INICIO_EN_VIVO_FECHA, "Apertura 2026 - J10")
print(f"Seguimiento en vivo: {seguimiento_en_vivo['n_jugados']} partidos jugados, "
      f"{seguimiento_en_vivo['n_pendientes']} pendientes congelados")

# --- Volcado final ---
salida = {
    "meta": {
        "generado": "2026-09-18",
        "liga": "Liga MX", "fuente": "FBref",
        "modelo": "Poisson + Dixon-Coles",
        "partidos_evaluados": int(len(features_todas)),
        "primera_temporada_evaluada": primera_temporada_eval,
        "accuracy_fuera_muestra": round(float(features_todas["acerto"].mean()), 4),
        "baseline_local": round(float((features_todas["ganador_real"] == "Local").mean()), 4),
        "logloss_modelo": round(float(np.mean(logloss_modelo)), 4),
        "logloss_baseline": round(float(np.mean(logloss_baseline)), 4),
        "rho_modelo_final": round(float(modelo_final.rho), 4),
        "umbral_minimo_historia": UMBRAL_MINIMO_HISTORIA,
        "nota_metodologica": (
            "Modelo de goles Poisson con corrección Dixon-Coles: se estiman los goles esperados de "
            "cada equipo y de ahí salen las probabilidades de Local/Empate/Visitante (el empate es la "
            "suma de los marcadores 0-0, 1-1, 2-2...). Las predicciones de partidos ya jugados son FUERA "
            "DE MUESTRA: cada temporada se predice con un modelo ajustado solo con temporadas anteriores, "
            "y el perfil de cada equipo usa solo partidos previos a la fecha del partido. Por eso 2020-21 "
            "y 2021-22 no aparecen (solo sirvieron para entrenar). Los partidos futuros usan el modelo ajustado con "
            "todo el histórico de hoy."
        ),
        "nota_arbitro": "El árbitro de los partidos futuros aún no está asignado por FBref, así que su predicción de tarjetas usa solo el perfil de equipos.",
        "nota_h2h": "El historial cabeza a cabeza es solo informativo: no cambia las probabilidades calculadas por el modelo.",
    },
    "seguimiento_en_vivo": seguimiento_en_vivo,
    "historico": historico,
    "futuras": predicciones_futuras,
}

# Los partidos de liguilla no tienen número de jornada: pandas los deja como NaN, que NO es
# JSON válido (el navegador falla al parsear). Se convierten a null (None) recursivamente y
# allow_nan=False hace que Python falle ruidosamente si se cuela alguno más.
def _sanear_nan(x):
    if isinstance(x, dict):
        return {k: _sanear_nan(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_sanear_nan(v) for v in x]
    if isinstance(x, float) and x != x:
        return None
    return x

with open(f"{RAIZ}/dashboard-predicciones/data.json", "w", encoding="utf-8") as f:
    json.dump(_sanear_nan(salida), f, ensure_ascii=False, indent=2, allow_nan=False)

print(f"\ndata.json exportado: {len(historico)} partidos históricos + {len(predicciones_futuras)} futuros")
