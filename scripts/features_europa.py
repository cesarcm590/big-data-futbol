"""
Perfiles pre-partido de las ligas europeas de football-data.co.uk (Premier, La Liga...; sin fuga de datos), compartidos por el script de comparación contra el
mercado y por el exportador del dashboard.

IDEA
----
Para cada partido, el perfil del equipo LOCAL se calcula con sus partidos ANTERIORES jugados como local, y el del
VISITANTE con sus anteriores como visitante (mismo enfoque que Liga MX). Métricas de perfil, siempre promedio por
partido: goles a favor, goles en contra, corners a favor, tarjetas a favor (amarillas + rojas), tiros a puerta a
favor y en contra.

VENTANA: None = promedio expandible de todo el pasado; k = promedio de los últimos k partidos en ese lado (en la
Premier las ventanas cortas, ~1-2 temporadas, predicen mejor que 10 años de historia).
MIN_PREV: partidos previos mínimos en ese lado para que exista perfil.
MAX_DIAS: si el equipo lleva más de MAX_DIAS sin jugar en ese lado (p. ej. un ascendido que estuvo en primera hace
9 años), se descarta su historia anterior a la pausa: hasta acumular MIN_PREV partidos nuevos el partido queda "sin
perfil" en vez de predecir con datos viejos.

Cómo se evita la fuga: shift(1) excluye el partido actual del promedio, y la tabla se ordena por fecha.
"""
import pandas as pd

METRICAS = ["gf", "gc", "cor", "tar", "tpf", "tpc"]


def construir_features(d, ventana=None, min_prev=10, max_dias=None):
    """
    d: DataFrame con Date, HomeTeam, AwayTeam, FTHG, FTAG, HC, AC, HY, HR, AY, AR, HST, AST y una columna `id`
       única (los partidos futuros pueden traer NaN en las estadísticas del partido).
    Devuelve d con las columnas local_* / visita_* del perfil.
    """
    d = d.copy()
    # Tabla "larga": una fila por (equipo, lado, partido) con lo que ese equipo hizo/recibió en ese partido.
    local = pd.DataFrame({
        "id": d.id, "equipo": d.HomeTeam, "lado": "L", "fecha": d.Date,
        "gf": d.FTHG, "gc": d.FTAG, "cor": d.HC, "tar": d.HY + d.HR, "tpf": d.HST, "tpc": d.AST})
    visita = pd.DataFrame({
        "id": d.id, "equipo": d.AwayTeam, "lado": "V", "fecha": d.Date,
        "gf": d.FTAG, "gc": d.FTHG, "cor": d.AC, "tar": d.AY + d.AR, "tpf": d.AST, "tpc": d.HST})
    largo = pd.concat([local, visita], ignore_index=True).sort_values(["fecha", "id"])
    # Si un equipo estuvo más de max_dias sin jugar en ese lado (p. ej. un ascendido que estuvo en primera hace años),
    # su historia ANTERIOR a la pausa se descarta: se reinicia el conteo y el perfil vuelve a existir solo cuando
    # acumule min_prev partidos nuevos. (Solo enmascarar el primer partido tras la pausa no basta: la ventana móvil
    # seguiría mezclando datos viejos en los siguientes.)
    grupo_base = ["equipo", "lado"]
    if max_dias is not None:
        dias = largo.groupby(grupo_base, sort=False)["fecha"].diff().dt.days
        largo["seg"] = (dias > max_dias).groupby([largo["equipo"], largo["lado"]]).cumsum().astype(int)
        grupo_base = ["equipo", "lado", "seg"]
    g = largo.groupby(grupo_base, sort=False)
    for c in METRICAS:
        if ventana is None:
            largo[c + "_m"] = g[c].transform(lambda s: s.shift(1).expanding(min_periods=min_prev).mean())
        else:
            largo[c + "_m"] = g[c].transform(lambda s: s.shift(1).rolling(ventana, min_periods=min_prev).mean())

    loc = largo[largo.lado == "L"].set_index("id")
    vis = largo[largo.lado == "V"].set_index("id")
    d = d.set_index("id")
    d["local_goles_favor"], d["local_goles_contra"] = loc["gf_m"], loc["gc_m"]
    d["local_corners_favor"], d["local_tarjetas_favor"] = loc["cor_m"], loc["tar_m"]
    d["local_tp_favor"], d["local_tp_contra"] = loc["tpf_m"], loc["tpc_m"]
    d["visita_goles_favor"], d["visita_goles_contra"] = vis["gf_m"], vis["gc_m"]
    d["visita_corners_favor"], d["visita_tarjetas_favor"] = vis["cor_m"], vis["tar_m"]
    d["visita_tp_favor"], d["visita_tp_contra"] = vis["tpf_m"], vis["tpc_m"]
    return d.reset_index()
