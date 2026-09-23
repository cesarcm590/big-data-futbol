"""
Congela las predicciones de partidos FUTUROS en un registro que solo crece (append-only).

POR QUÉ EXISTE
--------------
El histórico del dashboard se recalcula cada semana (walk-forward): si un partido ya jugado se vuelve a
predecir con un modelo reajustado, sus probabilidades pueden cambiar un poco. Eso está bien para el
backtest, pero NO sirve para medir qué tan bien predecimos "en vivo": para eso hay que comparar contra lo
que DIJIMOS ANTES del partido, tal cual. Este registro guarda esas predicciones originales, con la fecha y
hora en que se congelaron, y NUNCA se sobrescriben.

CÓMO SE USA (cada semana, antes de que se jueguen los partidos):
    1) Correr scripts/export_predicciones_historico.py  (genera dashboard-predicciones/data.json con 'futuras')
    2) Correr este script: agrega al registro los partidos futuros que todavía no estén en él.
Después de jugados, el exportador lee este registro y usa las probabilidades CONGELADAS (no las recalculadas)
para esos partidos, marcándolos como "en vivo".

Llave de un partido en el registro: (fecha, equipo local, equipo visitante). Si ya existe, no se toca.

HONESTIDAD: si un partido es de HOY, puede que ya haya empezado cuando se congeló; se marca en la columna
`nota`. Las primeras predicciones congeladas (jornada 9, Apertura 2026) tienen esa limitación.
"""
import json
import os
import sys
from datetime import datetime

import pandas as pd

RAIZ = "/Users/javiercarrillo/Proyectos/Big_data_futbol"
UMBRAL_PAREJO = 0.125    # mismo umbral que usa el dashboard para la marca de "partido parejo"

# Configuración por liga. Uso:  python scripts/congelar_predicciones.py [ligamx|premier|laliga|bundesliga|seriea]   (por defecto ligamx)
# El registro vive FUERA de la carpeta que se despliega a Vercel. `inicio` = fecha desde la cual los partidos
# cuentan en el seguimiento oficial en vivo; lo congelado antes se guarda igual, pero como "previa" (no cuenta).
#  - ligamx: la jornada 10 del Apertura 2026 (25-27 sept), definida con el usuario el 2026-09-18; sus primeros
#            partidos de la J9 se jugaron el mismo día en que se generó la predicción.
#  - premier: desde el sábado 19 sept 2026; Brentford-Chelsea (viernes 18, 20:00 hora del Reino Unido) ya se había
#            jugado cuando se congeló (hora de México), así que queda como "previa".
LIGAS = {
    "ligamx": {"data": f"{RAIZ}/dashboard-predicciones/data.json",
               "registro": f"{RAIZ}/registro/predicciones_congeladas.csv", "inicio": "2026-09-25"},
    "premier": {"data": f"{RAIZ}/dashboard-predicciones/data_premier.json",
                "registro": f"{RAIZ}/registro/predicciones_congeladas_premier.csv", "inicio": "2026-09-19"},
    # La Liga: desde el sábado 19 sept 2026; Espanyol-Elche (viernes 18, 20:00 hora del Reino Unido) ya se había jugado
    # cuando se congeló (hora de México), así que queda como "previa".
    "laliga": {"data": f"{RAIZ}/dashboard-predicciones/data_laliga.json",
               "registro": f"{RAIZ}/registro/predicciones_congeladas_laliga.csv", "inicio": "2026-09-19"},
    # Bundesliga: desde el sábado 19 sept 2026; Bayern-Union Berlin (viernes 18, 19:30 hora del Reino Unido) ya se había
    # jugado cuando se congeló (hora de México), así que queda como "previa".
    "bundesliga": {"data": f"{RAIZ}/dashboard-predicciones/data_bundesliga.json",
                   "registro": f"{RAIZ}/registro/predicciones_congeladas_bundesliga.csv", "inicio": "2026-09-19"},
    # Serie A: desde el sábado 19 sept 2026; Monza-Sassuolo (viernes 18, 19:45 hora del Reino Unido) ya se había jugado
    # cuando se congeló (hora de México), así que queda como "previa".
    "seriea": {"data": f"{RAIZ}/dashboard-predicciones/data_seriea.json",
               "registro": f"{RAIZ}/registro/predicciones_congeladas_seriea.csv", "inicio": "2026-09-19"},
}
liga = sys.argv[1] if len(sys.argv) > 1 else "ligamx"
cfg = LIGAS[liga]
RUTA_DATA, RUTA_REGISTRO, INICIO_EN_VIVO_FECHA = cfg["data"], cfg["registro"], cfg["inicio"]

ahora = datetime.now()
hoy = ahora.strftime("%Y-%m-%d")

data = json.load(open(RUTA_DATA, encoding="utf-8"))
futuras = [f for f in data["futuras"] if not f.get("sin_perfil")]

nuevas = []
for f in futuras:
    probs = [f["prob_local"], f["prob_empate"], f["prob_visitante"]]
    nuevas.append({
        "congelada_el": ahora.strftime("%Y-%m-%d %H:%M"),
        "modelo": data["meta"].get("modelo", "Poisson + Dixon-Coles"),
        "season": f["season"], "torneo": f["torneo"], "jornada_label": f["jornada_label"],
        "date": f["date"], "home_team": f["home_team"], "away_team": f["away_team"],
        "prob_local": f["prob_local"], "prob_empate": f["prob_empate"], "prob_visitante": f["prob_visitante"],
        "prediccion_ganador": f["prediccion_ganador"],
        "parejo": (max(probs) - min(probs)) <= UMBRAL_PAREJO,
        "cuenta_en_vivo": f["date"] >= INICIO_EN_VIVO_FECHA,
        "tarjetas_esperadas": f["tarjetas_esperadas"],
        "goles_esperados_local": f.get("goles_esperados_local"),
        "goles_esperados_visita": f.get("goles_esperados_visita"),
        "nota": ("previa al inicio del seguimiento oficial (no cuenta en la tendencia en vivo)"
                 + ("; partido de HOY: pudo haber iniciado antes de congelar" if f["date"] <= hoy else ""))
                if f["date"] < INICIO_EN_VIVO_FECHA else "",
    })
nuevas = pd.DataFrame(nuevas)

# Sin partidos futuros no hay nada que congelar, y hay que salir ANTES de comparar llaves: un DataFrame vacío no
# tiene ni columna "date", así que `nuevas["date"]` reventaría con KeyError. Pasa de verdad y de forma rutinaria —
# football-data publica el calendario a mitad de semana, así que entre el final de una jornada y esa publicación no
# hay futuros. No es un error: el registro se queda como está.
if nuevas.empty:
    print(f"No hay partidos futuros con perfil en {RUTA_DATA.split('/')[-1]}: el registro no se toca "
          f"({len(pd.read_csv(RUTA_REGISTRO)) if os.path.exists(RUTA_REGISTRO) else 0} congeladas).")
    sys.exit(0)

os.makedirs(os.path.dirname(RUTA_REGISTRO), exist_ok=True)
if os.path.exists(RUTA_REGISTRO):
    previo = pd.read_csv(RUTA_REGISTRO, dtype={"nota": str}).fillna({"nota": ""})
    llaves_previas = set(zip(previo["date"], previo["home_team"], previo["away_team"]))
    solo_nuevas = nuevas[[(d, h, a) not in llaves_previas
                          for d, h, a in zip(nuevas["date"], nuevas["home_team"], nuevas["away_team"])]]
    registro = pd.concat([previo, solo_nuevas], ignore_index=True)
    print(f"Registro previo: {len(previo)} | nuevas congeladas: {len(solo_nuevas)} | total: {len(registro)}")
else:
    registro = nuevas
    print(f"Registro creado con {len(registro)} predicciones congeladas")

registro.to_csv(RUTA_REGISTRO, index=False)
print(registro[["congelada_el", "jornada_label", "date", "home_team", "away_team", "prediccion_ganador", "parejo"]].to_string(index=False))
