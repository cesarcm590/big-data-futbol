import pandas as pd
import numpy as np
import json
import statsmodels.api as sm
from scipy.stats import norm, multivariate_normal, chi2
from scipy.optimize import minimize_scalar

df = pd.read_csv("/Users/javiercarrillo/Proyectos/Big_data_futbol/data/processed/matches_ligamx_2020_2025_v3_arbitraje.csv")

mapa_nombres_arbitro = {
    "Victor Caceres": "Víctor Cáceres",
    "Oscar Mejia": "Oscar Mejía",
    "Marco Ortíz": "Marco Antonio Ortíz",
    "Luis Santander": "Luis Enrique Santander",
    "Erick Miranda": "Erick Yair Miranda",
    "Guillermo Pacheco": "Guillermo Pacheco Larios",
    "Jesus Lopez": "Jesús López",
    "Ismael Lopez": "Ismael López",
}
df["referee"] = df["referee"].replace(mapa_nombres_arbitro)

df["sesgo_localia_partido"] = df["home_total_cards"] - df["away_total_cards"]
df["faltas_totales"] = df["home_fouls"] + df["away_fouls"]
df["rojas_totales"] = df["home_red"] + df["away_red"]
df["tarjeta_por_falta_partido"] = df["total_game_cards"] / df["faltas_totales"].replace(0, np.nan)

patron_score = r"(?:\(\d+\)\s*)?(\d+)\s*[–-]\s*(\d+)(?:\s*\(\d+\))?"
goles = df["score"].str.extract(patron_score)
df["home_goals"] = pd.to_numeric(goles[0], errors="coerce")
df["away_goals"] = pd.to_numeric(goles[1], errors="coerce")

# --- 1. Perfil por árbitro ---
perfil_arbitro = (
    df.groupby("referee")
    .agg(
        partidos=("referee", "size"),
        total_cards_prom=("total_game_cards", "mean"),
        sesgo_localia=("sesgo_localia_partido", "mean"),
        tarjeta_por_falta=("tarjeta_por_falta_partido", "mean"),
        rojas_por_partido=("rojas_totales", "mean"),
    )
    .query("partidos >= 10")
    .sort_values("sesgo_localia")
)
perfil_arbitro["z_sesgo_localia"] = (
    (perfil_arbitro["sesgo_localia"] - perfil_arbitro["sesgo_localia"].mean())
    / perfil_arbitro["sesgo_localia"].std()
)

perfil_json = [
    {"referee": r, **{k: (round(v, 3) if isinstance(v, float) else int(v)) for k, v in row.items()}}
    for r, row in perfil_arbitro.round(3).to_dict(orient="index").items()
]

# --- 2. Series de tiempo por árbitro ---
conteo_temporadas = df.groupby(["referee", "season"]).size().unstack(fill_value=0)
calificados = conteo_temporadas[(conteo_temporadas >= 5).sum(axis=1) >= 2].index.tolist()
temporadas_todas = sorted(df["season"].unique())

serie_arbitro = (
    df[df["referee"].isin(calificados)]
    .groupby(["referee", "season"])
    .agg(partidos=("referee", "size"), total_cards_prom=("total_game_cards", "mean"),
         sesgo_localia=("sesgo_localia_partido", "mean"))
    .reset_index()
)
serie_arbitro = serie_arbitro[serie_arbitro["partidos"] >= 5]

series_json = {}
for arbitro in calificados:
    datos = serie_arbitro[serie_arbitro["referee"] == arbitro].set_index("season").reindex(temporadas_todas)
    series_json[arbitro] = {
        "temporadas": temporadas_todas,
        "sesgo_localia": [None if pd.isna(v) else round(v, 3) for v in datos["sesgo_localia"]],
        "total_cards_prom": [None if pd.isna(v) else round(v, 3) for v in datos["total_cards_prom"]],
        "partidos": [None if pd.isna(v) else int(v) for v in datos["partidos"]],
    }

# --- 3. Pares árbitro-equipo atípicos ---
largo = pd.concat([
    df.rename(columns={
        "home_team": "team", "away_team": "rival",
        "home_total_cards": "tarjetas_recibidas", "home_fouls": "faltas",
    })[["date", "season", "referee", "team", "rival", "tarjetas_recibidas", "faltas"]].assign(es_local=1),
    df.rename(columns={
        "away_team": "team", "home_team": "rival",
        "away_total_cards": "tarjetas_recibidas", "away_fouls": "faltas",
    })[["date", "season", "referee", "team", "rival", "tarjetas_recibidas", "faltas"]].assign(es_local=0),
], ignore_index=True)

filas = []
for (arbitro, equipo), grupo in largo.groupby(["referee", "team"]):
    if len(grupo) < 4:
        continue
    resto = largo[(largo["team"] == equipo) & (largo["referee"] != arbitro)]
    if len(resto) < 4:
        continue
    diferencia = grupo["tarjetas_recibidas"].mean() - resto["tarjetas_recibidas"].mean()
    filas.append({
        "referee": arbitro, "team": equipo,
        "partidos_con_arbitro": len(grupo),
        "tarjetas_con_arbitro": round(grupo["tarjetas_recibidas"].mean(), 2),
        "tarjetas_con_otros": round(resto["tarjetas_recibidas"].mean(), 2),
        "diferencia": round(diferencia, 2),
    })
pares_df = pd.DataFrame(filas).sort_values("diferencia")
pares_extremos = pd.concat([pares_df.head(8), pares_df.tail(8)]).to_dict(orient="records")

# --- 4. Matriz policórica (dureza árbitro / propensión equipos vs total_cards) ---
def a_terciles(serie):
    return pd.qcut(serie.rank(method="first"), 3, labels=[0, 1, 2]).astype(int)

def umbrales(conteos):
    proporciones = np.cumsum(conteos) / conteos.sum()
    z = norm.ppf(proporciones[:-1])
    return np.concatenate([[-8.0], z, [8.0]])

def prob_rectangulo(mvn, x0, x1, y0, y1):
    return mvn.cdf([x1, y1]) - mvn.cdf([x0, y1]) - mvn.cdf([x1, y0]) + mvn.cdf([x0, y0])

def correlacion_policorica(x, y):
    tabla = pd.crosstab(x, y).values
    umbral_x = umbrales(tabla.sum(axis=1))
    umbral_y = umbrales(tabla.sum(axis=0))
    def neg_log_verosimilitud(r):
        mvn = multivariate_normal(mean=[0, 0], cov=[[1, r], [r, 1]])
        ll = 0.0
        for i in range(tabla.shape[0]):
            for j in range(tabla.shape[1]):
                if tabla[i, j] == 0:
                    continue
                p = prob_rectangulo(mvn, umbral_x[i], umbral_x[i + 1], umbral_y[j], umbral_y[j + 1])
                ll -= tabla[i, j] * np.log(max(p, 1e-12))
        return ll
    resultado = minimize_scalar(neg_log_verosimilitud, bounds=(-0.999, 0.999), method="bounded")
    return resultado.x

dureza_arbitro = df.groupby("referee")["total_game_cards"].transform("mean")
prom_equipo = largo.groupby("team")["tarjetas_recibidas"].mean()
propension_equipos_partido = df["home_team"].map(prom_equipo) + df["away_team"].map(prom_equipo)

df["dureza_arbitro_niv"] = a_terciles(dureza_arbitro)
df["propension_equipos_niv"] = a_terciles(propension_equipos_partido)
df["total_cards_niv"] = a_terciles(df["total_game_cards"])

r_arbitro = correlacion_policorica(df["dureza_arbitro_niv"], df["total_cards_niv"])
r_equipos = correlacion_policorica(df["propension_equipos_niv"], df["total_cards_niv"])

# --- 5. GLM anidados ---
df_modelo = df.dropna(subset=["total_game_cards", "faltas_totales", "referee", "home_team", "away_team"]).copy()
X_equipos = pd.get_dummies(df_modelo[["home_team", "away_team"]], drop_first=True).astype(float)
X_arbitro = pd.get_dummies(df_modelo[["referee"]], drop_first=True).astype(float)

def X_con(*bloques):
    partes = [pd.DataFrame({"const": 1.0}, index=df_modelo.index)]
    partes.extend(bloques)
    return pd.concat(partes, axis=1)

y = df_modelo["total_game_cards"]
modelos = {
    "M0_nulo": X_con(),
    "M1_faltas": X_con(df_modelo[["faltas_totales"]]),
    "M2_equipos": X_con(df_modelo[["faltas_totales"]], X_equipos),
    "M3_arbitro": X_con(df_modelo[["faltas_totales"]], X_arbitro),
    "M4_completo": X_con(df_modelo[["faltas_totales"]], X_equipos, X_arbitro),
}
resultados = {n: sm.GLM(y, X.astype(float), family=sm.families.Poisson()).fit() for n, X in modelos.items()}
ll_nulo = resultados["M0_nulo"].llf
glm_json = [
    {"modelo": n, "n_parametros": int(m.df_model + 1), "aic": round(m.aic, 1),
     "pseudo_r2_mcfadden": round(1 - m.llf / ll_nulo, 4)}
    for n, m in resultados.items()
]

# --- 5b. Jornada/ronda de cada partido (para poder ubicar puntualmente un caso) ---
sched = pd.read_csv(
    "/Users/javiercarrillo/Proyectos/Big_data_futbol/data/raw/matches_ligamx_2020_2025_schedule.csv",
    dtype=str,
)
sched_slim = sched[["date", "home_team", "away_team", "round", "gameweek"]].copy()
df["date"] = df["date"].astype(str)
sched_slim["date"] = sched_slim["date"].astype(str)
df = df.drop(columns=["gameweek"], errors="ignore")
df = df.merge(sched_slim, on=["date", "home_team", "away_team"], how="left")

_traduccion_fase = {
    "Quarter-finals": "Cuartos de final",
    "Semi-finals": "Semifinal",
    "Finals": "Final",
    "Reclassification": "Reclasificación",
    "7-seed match": "Definición de puesto",
    "8-seed match": "Definición de puesto",
    "9/10 match": "Definición de puesto",
}

def _jornada_display(fila):
    ronda = fila["round"]
    if pd.isna(ronda):
        return "N/D"
    if "Regular Season" in ronda:
        torneo = ronda.replace(" Regular Season", "")
        gw = fila["gameweek"]
        return f"{torneo} - J{int(float(gw))}" if pd.notna(gw) else f"{torneo} - Jornada N/D"
    torneo, _, fase_en = ronda.partition(" — ")
    fase_es = _traduccion_fase.get(fase_en, fase_en)
    return f"{torneo} - {fase_es}"

df["jornada_display"] = df.apply(_jornada_display, axis=1)

# --- 5c. Detalle partido por partido, y casos extremos por árbitro ---
UMBRAL_CASO_EXTREMO = 4

casos_por_arbitro = {}
for arbitro in perfil_arbitro.index:
    partidos_arbitro = df[df["referee"] == arbitro].copy()
    ordenado = partidos_arbitro.sort_values("sesgo_localia_partido")

    def _empaquetar(fila):
        return {
            "season": fila["season"], "jornada": fila["jornada_display"],
            "home_team": fila["home_team"], "away_team": fila["away_team"],
            "home_cards": int(fila["home_total_cards"]), "away_cards": int(fila["away_total_cards"]),
            "sesgo": int(fila["sesgo_localia_partido"]), "date": fila["date"],
        }

    favorece_local = [_empaquetar(f) for _, f in ordenado.head(6).iterrows() if f["sesgo_localia_partido"] < 0]
    perjudica_local = [_empaquetar(f) for _, f in ordenado.tail(6).iloc[::-1].iterrows() if f["sesgo_localia_partido"] > 0]

    extremos = partidos_arbitro[partidos_arbitro["sesgo_localia_partido"].abs() >= UMBRAL_CASO_EXTREMO].copy()
    extremos["equipo_favorecido"] = np.where(
        extremos["sesgo_localia_partido"] < 0, extremos["home_team"], extremos["away_team"]
    )
    if len(extremos) > 0:
        conteo_equipos = extremos["equipo_favorecido"].value_counts()
        equipo_top = conteo_equipos.index[0]
        veces_top = int(conteo_equipos.iloc[0])
    else:
        equipo_top, veces_top = None, 0

    casos_por_arbitro[arbitro] = {
        "favorece_local": favorece_local,
        "perjudica_local": perjudica_local,
        "partidos_extremos_totales": int(len(extremos)),
        "equipo_mas_favorecido": equipo_top,
        "veces_equipo_mas_favorecido": veces_top,
    }

# --- 6. Tendencia por temporada ---
df["dif_goles_local"] = df["home_goals"] - df["away_goals"]
df["gano_local"] = (df["dif_goles_local"] > 0).astype(float)
por_temporada = df.groupby("season").agg(
    partidos=("season", "size"),
    sesgo_localia_tarjetas=("sesgo_localia_partido", "mean"),
    total_cards_prom=("total_game_cards", "mean"),
    dif_goles_local_prom=("dif_goles_local", "mean"),
    tasa_victoria_local=("gano_local", "mean"),
).round(4)
por_temporada_json = por_temporada.reset_index().to_dict(orient="records")

# --- Volcado final ---
salida = {
    "meta": {
        "partidos_totales": int(len(df)),
        "arbitros_unicos": int(df["referee"].nunique()),
        "temporadas": temporadas_todas,
        "generado": "notebook 14 - sesgo arbitral Liga MX",
    },
    "perfil_arbitro": perfil_json,
    "atipicos": perfil_arbitro[perfil_arbitro["z_sesgo_localia"].abs() > 2].index.tolist(),
    "series_tiempo": series_json,
    "pares_arbitro_equipo_extremos": pares_extremos,
    "policorica": {"arbitro_vs_tarjetas": round(r_arbitro, 3), "equipos_vs_tarjetas": round(r_equipos, 3)},
    "glm": glm_json,
    "por_temporada": por_temporada_json,
    "casos_extremos_por_arbitro": casos_por_arbitro,
    "umbral_caso_extremo": UMBRAL_CASO_EXTREMO,
}

with open("/Users/javiercarrillo/Proyectos/Big_data_futbol/dashboard/data.json", "w", encoding="utf-8") as f:
    json.dump(salida, f, ensure_ascii=False, indent=2)

print("data.json exportado")
print("meta:", salida["meta"])
print("atípicos:", salida["atipicos"])
print("policórica:", salida["policorica"])
