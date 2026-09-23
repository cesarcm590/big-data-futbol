"""
Lógica compartida del SEGUIMIENTO EN VIVO (predicciones congeladas antes del partido), usada por los exportadores de
todas las ligas del dashboard.

- cargar_congeladas(ruta): lee el registro CSV (append-only) y lo indexa por (fecha, local, visitante).
- aplicar_congelada(entrada, ya_jugado, congeladas): si el partido está en el registro, sustituye las probabilidades
  por las CONGELADAS (lo que se dijo antes del partido) y lo marca `congelada` / `en_vivo`; si ya se jugó, recalcula
  el acierto contra esas probabilidades originales.
- resumen_seguimiento(...): acierto por jornada de los partidos en vivo ya jugados + pendientes congelados.

Ver scripts/congelar_predicciones.py para cómo se crea el registro y por qué nunca se sobrescribe.
"""
import os

import pandas as pd

CAMPOS_PRED = ["prob_local", "prob_empate", "prob_visitante", "prediccion_ganador", "tarjetas_esperadas",
               "goles_esperados_local", "goles_esperados_visita"]
UMBRAL_PAREJO = 0.125


def cargar_congeladas(ruta):
    if not os.path.exists(ruta):
        return {}
    return {(r["date"], r["home_team"], r["away_team"]): r for r in pd.read_csv(ruta).to_dict("records")}


def aplicar_congelada(entrada, ya_jugado, congeladas):
    c = congeladas.get((entrada["date"], entrada["home_team"], entrada["away_team"]))
    if c is None or entrada.get("sin_perfil"):
        return entrada
    for k in CAMPOS_PRED:
        if k in c and not pd.isna(c[k]):
            entrada[k] = c[k]
    entrada["congelada"] = True
    entrada["congelada_el"] = c["congelada_el"]
    entrada["en_vivo"] = bool(c["cuenta_en_vivo"])
    if ya_jugado:
        entrada["acerto"] = entrada["prediccion_ganador"] == entrada["ganador_real"]
    return entrada


def _es_parejo(h):
    ps = [h["prob_local"], h["prob_empate"], h["prob_visitante"]]
    return max(ps) - min(ps) <= UMBRAL_PAREJO


def resumen_seguimiento(historico, futuras, inicio_fecha, inicio_label):
    jugados = [h for h in historico if h.get("en_vivo")]
    por_jornada = {}
    for h in jugados:
        j = por_jornada.setdefault((h["season"], h["jornada_label"]), {"n": 0, "aciertos": 0, "fecha": h["date"]})
        j["n"] += 1
        j["aciertos"] += int(h["acerto"])
        j["fecha"] = min(j["fecha"], h["date"])
    return {
        "inicio_fecha": inicio_fecha,
        "inicio_label": inicio_label,
        "n_jugados": len(jugados),
        "aciertos": int(sum(h["acerto"] for h in jugados)),
        "baseline_local": (round(sum(h["ganador_real"] == "Local" for h in jugados) / len(jugados), 4)
                           if jugados else None),
        "n_parejos": int(sum(_es_parejo(h) for h in jugados)),
        "empates_en_parejos": int(sum(_es_parejo(h) and h["ganador_real"] == "Empate" for h in jugados)),
        "n_pendientes": int(sum(1 for f in futuras if f.get("en_vivo"))),
        "por_jornada": [
            {"season": k[0], "jornada_label": k[1], "n": v["n"], "aciertos": v["aciertos"], "fecha": v["fecha"]}
            for k, v in sorted(por_jornada.items(), key=lambda kv: kv[1]["fecha"])
        ],
    }
