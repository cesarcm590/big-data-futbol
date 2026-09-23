"""
REGISTRO PERSONAL DE APUESTAS (privado): califica cada jugada con el resultado real y busca patrones.

DÓNDE VIVE
----------
  registro_personal/jugadas.csv            -> lo llenamos cuando me digas en qué jugaste. Esta carpeta NO está dentro de
                                              dashboard*/ ni de ninguna carpeta que se despliegue: nunca se publica.
  registro_personal/jugadas_calificadas.csv -> se regenera cada vez que corres este script (resultado de cada jugada).

COLUMNAS de jugadas.csv (una fila por jugada; una combinada = varias filas con el mismo combinada_id)
  date          fecha del partido (AAAA-MM-DD)
  liga          ligamx | premier | laliga | bundesliga | seriea
  home_team     equipo local, escrito igual que en el dashboard
  away_team     equipo visitante
  tipo          1x2 | doble_oportunidad | over_under_goles | ambos_anotan | handicap | tarjetas_over_under |
                corners_over_under | marcador_exacto | otro          ("otro" se registra pero no se califica)
  seleccion     1x2: Local|Empate|Visitante · doble_oportunidad: 1X|X2|12 · over/under: Over|Under ·
                ambos_anotan: Si|No · handicap: Local|Visitante · marcador_exacto: "2-1"
  linea         over/under: 2.5, 3.5, ... · handicap: la línea aplicada a la selección (p. ej. -1.5, +0.5)
                Solo se califican líneas con .5 (sin empate posible); líneas enteras/cuartos quedan "no calificable".
  cuota         cuota decimal de ESA jugada (en una combinada, la de cada pata)
  monto         cuánto jugaste (en una combinada, ponlo en una sola fila del grupo)
  combinada_id  texto que agrupa las patas de una combinada (vacío en una apuesta simple)
  cuota_total   (opcional, solo en una fila de la combinada) cuota total real si difiere del producto de las patas
  situacion     texto libre para buscar patrones: "parejo", "favorito claro", "corazonada", "seguí al modelo"...
  nota          lo que quieras

QUÉ HACE EL SCRIPT
  1. Busca el resultado real de cada partido (goles, corners, tarjetas) en los datasets del proyecto. Si el partido no
     está todavía en el dataset, la jugada queda "pendiente" (se resuelve tras la siguiente actualización).
  2. Califica cada pata: gano / perdio / push (línea exacta) / pendiente / no calificable.
  3. Para cada pata calcula la probabilidad que el MODELO le daba (1X2 y doble oportunidad: del modelo; goles
     over/under, ambos anotan, marcador exacto y hándicap: del Poisson con los goles esperados del modelo; tarjetas:
     Poisson con las tarjetas esperadas; corners: no hay modelo) y la compara con la probabilidad implícita de tu
     cuota (1/cuota, que incluye el margen de la casa): edge = prob_modelo - 1/cuota.
  4. Resume por tipo de apuesta, liga, rango de cuota, edge, coincidencia con el modelo, partido parejo y
     situación: acierto, ganancia y ROI. Una combinada cuenta como UNA apuesta (gana si ganan todas sus patas).

ADVERTENCIAS HONESTAS
  - Con pocas apuestas los porcentajes son puro ruido (el script marca con * los grupos con menos de 30 apuestas).
  - Las tarjetas de las casas de apuestas pueden contarse distinto (p. ej. roja = 2 puntos); aquí total = amarillas +
    rojas del dataset, así que una jugada de tarjetas puede calificarse distinto a como la resolvió tu casa.
  - Este registro sirve para ver TUS hábitos (¿te va peor contra el modelo? ¿en qué tipo de apuesta?), no para
    concluir que un patrón "funciona" sin una muestra grande.

USO:  python scripts/resumen_registro_personal.py            (usa registro_personal/jugadas.csv)
      python scripts/resumen_registro_personal.py otra.csv   (para probar con otro archivo)
"""
import json
import re
import sys

import numpy as np
import pandas as pd
from scipy.stats import poisson

from ligas_europa import LIGAS_EUROPA, RAIZ
from modelo_goles import matriz_marcadores

RUTA_JUGADAS = sys.argv[1] if len(sys.argv) > 1 else f"{RAIZ}/registro_personal/jugadas.csv"
RUTA_SALIDA = f"{RAIZ}/registro_personal/jugadas_calificadas.csv"
MIN_MUESTRA = 30   # por debajo de esto un porcentaje es ruido (se marca con *)

JSON_LIGA = {"ligamx": "data.json", **{k: v["salida_json"] for k, v in LIGAS_EUROPA.items()}}
TIPOS = ["1x2", "doble_oportunidad", "over_under_goles", "ambos_anotan", "handicap",
         "tarjetas_over_under", "corners_over_under", "marcador_exacto", "otro"]


# --------------------------------------------------------------------------------------------
# 1) Resultados reales por liga: goles, corners y tarjetas de cada partido
# --------------------------------------------------------------------------------------------
def cargar_resultados(liga):
    """DataFrame con date (AAAA-MM-DD), home_team, away_team, gl, gv, corners, tarjetas (amarillas + rojas)."""
    if liga == "ligamx":
        d = pd.read_csv(f"{RAIZ}/data/processed/matches_ligamx_2020_2025_v3_arbitraje.csv", dtype=str)
        goles = d["score"].str.extract(r"(?:\(\d+\)\s*)?(\d+)\s*[–-]\s*(\d+)(?:\s*\(\d+\))?")   # ignora penales
        out = pd.DataFrame({
            "date": pd.to_datetime(d["date"]).dt.strftime("%Y-%m-%d"), "home_team": d["home_team"],
            "away_team": d["away_team"], "gl": pd.to_numeric(goles[0]), "gv": pd.to_numeric(goles[1]),
            "corners": pd.to_numeric(d["home_corners"], errors="coerce") + pd.to_numeric(d["away_corners"], errors="coerce"),
            "tarjetas": pd.to_numeric(d["total_game_cards"], errors="coerce"),
        })
    else:
        d = pd.read_csv(f"{RAIZ}/data/processed/{LIGAS_EUROPA[liga]['dataset']}", parse_dates=["Date"])
        out = pd.DataFrame({
            "date": d["Date"].dt.strftime("%Y-%m-%d"), "home_team": d["HomeTeam"], "away_team": d["AwayTeam"],
            "gl": d["FTHG"], "gv": d["FTAG"], "corners": d["HC"] + d["AC"],
            "tarjetas": d["HY"] + d["HR"] + d["AY"] + d["AR"],
        })
    return out.set_index(["date", "home_team", "away_team"])


_cache_modelo = {}

def cargar_modelo(liga):
    """Predicciones del dashboard por partido (jugados y futuros). Para los 'en vivo' ya son las CONGELADAS."""
    if liga not in _cache_modelo:
        d = json.load(open(f"{RAIZ}/dashboard-predicciones/{JSON_LIGA[liga]}", encoding="utf-8"))
        regs = {}
        for r in d["historico"] + [f for f in d["futuras"] if not f.get("sin_perfil")]:
            regs[(r["date"], r["home_team"], r["away_team"])] = r
        _cache_modelo[liga] = (regs, d["meta"].get("rho_modelo_final", 0.0))
    return _cache_modelo[liga]


# --------------------------------------------------------------------------------------------
# 2) Calificar una pata con el resultado real
# --------------------------------------------------------------------------------------------
def calificar(tipo, sel, linea, res):
    """Devuelve 'gano' | 'perdio' | 'push' | 'no calificable'. `res` = fila de resultados (goles, corners, tarjetas)."""
    gl, gv = res["gl"], res["gv"]
    real = "Local" if gl > gv else ("Visitante" if gl < gv else "Empate")
    if tipo == "1x2":
        return "gano" if sel == real else "perdio"
    if tipo == "doble_oportunidad":
        cubre = {"1X": {"Local", "Empate"}, "X2": {"Empate", "Visitante"}, "12": {"Local", "Visitante"}}.get(str(sel).upper())
        return "no calificable" if cubre is None else ("gano" if real in cubre else "perdio")
    if tipo in ("over_under_goles", "tarjetas_over_under", "corners_over_under"):
        total = {"over_under_goles": gl + gv, "tarjetas_over_under": res["tarjetas"], "corners_over_under": res["corners"]}[tipo]
        if pd.isna(total) or pd.isna(linea):
            return "no calificable"
        if total == linea:
            return "push"
        return "gano" if ((total > linea) == (str(sel).lower() == "over")) else "perdio"
    if tipo == "ambos_anotan":
        btts = gl > 0 and gv > 0
        return "gano" if btts == (str(sel).lower() in ("si", "sí")) else "perdio"
    if tipo == "handicap":
        if pd.isna(linea) or abs(linea * 2 % 2 - 1) > 1e-9:      # solo líneas x.5
            return "no calificable"
        if sel == "Local":
            return "gano" if gl + linea > gv else "perdio"
        if sel == "Visitante":
            return "gano" if gv + linea > gl else "perdio"
        return "no calificable"
    if tipo == "marcador_exacto":
        return "gano" if str(sel).replace(" ", "") == f"{int(gl)}-{int(gv)}" else "perdio"
    return "no calificable"


# --------------------------------------------------------------------------------------------
# 3) Probabilidad que el modelo daba a la pata
# --------------------------------------------------------------------------------------------
def prob_modelo(tipo, sel, linea, rec, rho):
    """Probabilidad del modelo para la selección, o NaN si el modelo no cubre ese mercado."""
    if rec is None:
        return np.nan
    if tipo == "1x2":
        return {"Local": rec["prob_local"], "Empate": rec["prob_empate"], "Visitante": rec["prob_visitante"]}.get(sel, np.nan)
    if tipo == "doble_oportunidad":
        pl, pe, pv = rec["prob_local"], rec["prob_empate"], rec["prob_visitante"]
        return {"1X": pl + pe, "X2": pe + pv, "12": pl + pv}.get(str(sel).upper(), np.nan)
    if tipo == "tarjetas_over_under":
        if pd.isna(linea) or rec.get("tarjetas_esperadas") is None:
            return np.nan
        p_over = 1 - poisson.cdf(np.floor(linea), rec["tarjetas_esperadas"])   # Poisson simple (ignora sobredispersión)
        return p_over if str(sel).lower() == "over" else 1 - p_over
    if tipo in ("over_under_goles", "ambos_anotan", "handicap", "marcador_exacto"):
        lam, mu = rec.get("goles_esperados_local"), rec.get("goles_esperados_visita")
        if lam is None or mu is None:
            return np.nan
        m = matriz_marcadores(np.array([lam]), np.array([mu]), rho)[0]      # P(local anota i, visita anota j)
        i, j = np.indices(m.shape)
        if tipo == "over_under_goles":
            p_over = m[(i + j) > linea].sum()
            return p_over if str(sel).lower() == "over" else 1 - p_over
        if tipo == "ambos_anotan":
            p_si = m[(i > 0) & (j > 0)].sum()
            return p_si if str(sel).lower() in ("si", "sí") else 1 - p_si
        if tipo == "handicap":
            return m[(i + linea) > j].sum() if sel == "Local" else m[(j + linea) > i].sum()
        mm = re.fullmatch(r"(\d+)-(\d+)", str(sel).replace(" ", ""))
        return m[int(mm.group(1)), int(mm.group(2))] if mm else np.nan
    return np.nan                                                            # corners: no hay modelo


# --------------------------------------------------------------------------------------------
# 4) Armar la tabla de patas calificadas
# --------------------------------------------------------------------------------------------
def a_decimal(x):
    """Convierte un momio a cuota decimal. Acepta decimal (1.85), americano (+150, -120) y fraccionario (5/2)."""
    if pd.isna(x) or str(x).strip() == "":
        return np.nan
    t = str(x).strip().replace(",", ".")
    try:
        if "/" in t:
            a, b = t.split("/")
            return 1 + float(a) / float(b)
        v = float(t)
    except ValueError:
        return np.nan
    if abs(v) >= 100:                                    # americano: +150 -> 2.50 ; -120 -> 1.83
        return 1 + v / 100 if v > 0 else 1 + 100 / abs(v)
    return v if v > 1 else np.nan                        # decimal válido siempre es > 1


def a_monto(x):
    """Convierte '$100', '1,000' o '100' a número."""
    t = re.sub(r"[^\d.]", "", str(x).replace(",", "")) if pd.notna(x) else ""
    return float(t) if t else np.nan


jugadas = pd.read_csv(RUTA_JUGADAS, dtype={"combinada_id": str, "seleccion": str, "linea": float,
                                           "cuota": str, "cuota_total": str, "monto": str})
if jugadas.empty:
    print("Todavía no hay jugadas registradas en", RUTA_JUGADAS)
    sys.exit(0)
for c in ["cuota", "cuota_total"]:
    jugadas[c] = jugadas[c].map(a_decimal) if c in jugadas else np.nan
jugadas["monto"] = jugadas["monto"].map(a_monto)
jugadas["tipo"] = jugadas["tipo"].str.strip().str.lower()
malos = jugadas[~jugadas["tipo"].isin(TIPOS)]
if len(malos):
    print("AVISO: tipos no reconocidos (se tratan como 'otro'):", sorted(malos["tipo"].unique()))
    jugadas.loc[~jugadas["tipo"].isin(TIPOS), "tipo"] = "otro"

resultados, patas = {}, []
for _, j in jugadas.iterrows():
    liga = j["liga"]
    if liga not in resultados:
        resultados[liga] = cargar_resultados(liga)
    llave = (j["date"], j["home_team"], j["away_team"])
    regs, rho = cargar_modelo(liga)
    rec = regs.get(llave)          # predicción del modelo para este partido (None si no hay)
    if llave not in resultados[liga].index:
        estado = "pendiente"
    else:
        estado = calificar(j["tipo"], j["seleccion"], j["linea"], resultados[liga].loc[llave])
    p_mod = prob_modelo(j["tipo"], j["seleccion"], j["linea"], rec, rho)
    p_impl = 1 / j["cuota"] if pd.notna(j["cuota"]) and j["cuota"] > 0 else np.nan
    probs = [rec["prob_local"], rec["prob_empate"], rec["prob_visitante"]] if rec else [np.nan] * 3
    patas.append({**j.to_dict(), "estado": estado, "prob_modelo": p_mod, "prob_implicita": p_impl,
                  "edge": p_mod - p_impl if pd.notna(p_mod) and pd.notna(p_impl) else np.nan,
                  "pick_modelo": rec["prediccion_ganador"] if rec else None,
                  "parejo": (max(probs) - min(probs) <= 0.125) if rec else None,
                  "coincide_modelo": (j["seleccion"] == rec["prediccion_ganador"]) if (rec and j["tipo"] == "1x2") else None})
P = pd.DataFrame(patas)
P.to_csv(RUTA_SALIDA, index=False)

print("=== Patas registradas ===")
cols = ["date", "liga", "home_team", "away_team", "tipo", "seleccion", "linea", "cuota", "estado", "prob_modelo", "edge", "situacion"]
print(P[cols].round(3).to_string(index=False))

# --------------------------------------------------------------------------------------------
# 5) Unidades de apuesta: simples = una fila; combinada = todas sus patas juntas
# --------------------------------------------------------------------------------------------
unidades = []
simples = P[P["combinada_id"].isna() | (P["combinada_id"] == "")]
for _, r in simples.iterrows():
    unidades.append({"date": r["date"], "tipo": r["tipo"], "liga": r["liga"], "situacion": r["situacion"], "estado": r["estado"],
                     "cuota": r["cuota"], "monto": r["monto"], "edge": r["edge"], "coincide_modelo": r["coincide_modelo"],
                     "parejo": r["parejo"], "n_patas": 1})
for cid, g in P[P["combinada_id"].notna() & (P["combinada_id"] != "")].groupby("combinada_id"):
    if (g["estado"] == "perdio").any():
        estado = "perdio"
    elif (g["estado"].isin(["pendiente", "no calificable"])).any():
        estado = "pendiente" if (g["estado"] == "pendiente").any() else "no calificable"
    else:
        estado = "gano"                                         # todas ganaron (los push se descartan de la combinada)
    cuota = g["cuota_total"].dropna().iloc[0] if g["cuota_total"].notna().any() else g.loc[g["estado"] != "push", "cuota"].prod()
    unidades.append({"date": g["date"].min(), "tipo": "combinada", "liga": ",".join(sorted(g["liga"].unique())),
                     "situacion": g["situacion"].dropna().iloc[0] if g["situacion"].notna().any() else None,
                     "estado": estado, "cuota": cuota, "monto": g["monto"].dropna().max() if g["monto"].notna().any() else np.nan,
                     "edge": np.nan, "coincide_modelo": None, "parejo": None, "n_patas": len(g)})
U = pd.DataFrame(unidades)
U["resuelta"] = U["estado"].isin(["gano", "perdio"])
U["gano"] = np.where(U["resuelta"], (U["estado"] == "gano").astype(float), np.nan)
U["ganancia"] = np.where(U["resuelta"] & U["cuota"].notna() & U["monto"].notna(),
                         np.where(U["estado"] == "gano", U["monto"] * (U["cuota"] - 1), -U["monto"]), np.nan)
U["prob_implicita"] = 1 / U["cuota"]

R = U[U["resuelta"]]
print(f"\n=== Resumen: {len(U)} apuestas ({len(R)} resueltas, {int((U['estado'] == 'pendiente').sum())} pendientes) ===")
if len(R) == 0:
    print("Aún no hay apuestas resueltas.")
    sys.exit(0)


def tabla(df, por):
    g = df.groupby(por, dropna=False).agg(
        n=("gano", "size"), acierto=("gano", "mean"), impl=("prob_implicita", "mean"),
        ganancia=("ganancia", "sum"), jugado=("monto", lambda s: s[df.loc[s.index, "ganancia"].notna()].sum()))
    g["ROI"] = np.where(g["jugado"] > 0, g["ganancia"] / g["jugado"], np.nan)
    g["ruido"] = np.where(g["n"] < MIN_MUESTRA, "*", "")
    return g.rename(columns={"impl": "prob_impl_media"})


print(f"Global: acierto {R['gano'].mean():.1%} | prob. implícita media de tus cuotas {R['prob_implicita'].mean():.1%} | "
      f"ganancia {R['ganancia'].sum():+.2f} sobre {R.loc[R['ganancia'].notna(), 'monto'].sum():.2f} jugados")
print("(si tu acierto supera la prob. implícita media, tus cuotas estaban 'baratas' respecto a lo que pasó; con pocos "
      "datos es ruido)")

# Factores que se calculan solos (no tienes que anotarlos): día de la semana del partido, estructura de la apuesta
# (simple o combinada de N patas) y tamaño del monto (tercios bajo/medio/alto, solo con >= 9 apuestas resueltas).
DIAS = {0: "1 lunes", 1: "2 martes", 2: "3 miércoles", 3: "4 jueves", 4: "5 viernes", 5: "6 sábado", 6: "7 domingo"}
R = R.assign(dia_semana=pd.to_datetime(R["date"]).dt.dayofweek.map(DIAS),
             estructura=np.where(R["n_patas"] == 1, "simple", "combinada " + R["n_patas"].clip(upper=4).astype(str).str.replace("4", "4+")))
if R["monto"].notna().sum() >= 9:
    R["monto_nivel"] = pd.qcut(R["monto"], 3, labels=["bajo", "medio", "alto"], duplicates="drop")
R = R.assign(rango_cuota=pd.cut(R["cuota"], [0, 1.5, 2.0, 3.0, 100], labels=["<1.5", "1.5-2", "2-3", ">=3"]),
             edge_signo=np.select([R["edge"] > 0, R["edge"] <= 0], ["edge > 0 (el modelo lo veía barato)", "edge <= 0"], "sin modelo"))
for titulo, col in [("Tipo de apuesta", "tipo"), ("Liga", "liga"), ("Rango de cuota", "rango_cuota"),
                    ("Edge según el modelo", "edge_signo"), ("Coincidiste con el pick del modelo (solo 1X2)", "coincide_modelo"),
                    ("Partido parejo", "parejo"), ("Situación", "situacion"), ("Día de la semana", "dia_semana"),
                    ("Estructura", "estructura"), ("Monto", "monto_nivel")]:
    if col in R.columns and R[col].notna().any():
        print(f"\nPor {titulo}:")
        print(tabla(R, col).round(3).to_string())
print(f"\n(* = menos de {MIN_MUESTRA} apuestas: el porcentaje es ruido.)  Detalle por pata en {RUTA_SALIDA}")
