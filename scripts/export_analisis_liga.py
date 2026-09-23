"""
Exporta el análisis de una liga (notebooks 18_analisis_liga_<liga>.ipynb) al JSON que lee la página `analisis.html` del dashboard.

    python scripts/export_analisis_liga.py ligamx          # -> dashboard-predicciones/analisis_ligamx.json

Mismo cálculo que el notebook 18 (todo sale de `futbol_bd.liga`), en el formato que necesita el navegador:
  meta          liga, temporadas, conteos, fecha de generación
  control       por temporada: equipos, partidos por equipo y cobertura de minutos (control de calidad)
  plantillas    series por temporada (mediana y p25-p75 de los equipos) + tablas de equipos
  porteros      series de la liga, carreras, última temporada, estabilidad y desacuerdos de datos
  impacto       pares (temporada t, t+1) de on-off, puntos con él − del equipo y goles sin penal/90 de delanteros
  dependencia   un punto por equipo-temporada (dependencia del goleador, goles, puntos) + mejor fantasy por equipo
  explorador    una fila por jugador-EQUIPO-temporada (columnas en `explorador.columnas`), para la sección
                "Explorador de plantillas": elegir temporada y equipo, ver a sus jugadores y la trayectoria de cada uno.
                Los puntos fantasy de cada fila son los de ESE equipo; el percentil es el de su temporada completa.
  lectura       textos de interpretación por sección, escritos a mano para cada liga (LECTURAS, abajo). Una liga sin
                textos se publica igual: la página muestra solo los datos.

Los NaN se escriben como null (NaN no es JSON válido y el despliegue lo rechaza). Para agregar una liga al análisis
web: correr este script con su clave, registrarla en LIGAS_ANALISIS de analisis.html y desplegar con
`python scripts/desplegar_dashboard.py`.
"""
import json
import math
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from futbol_bd import fantasy, liga, plantillas  # noqa: E402

CLAVES = {"ligamx": "Liga MX", "premier": "Premier League", "laliga": "La Liga", "seriea": "Serie A",
          "bundesliga": "Bundesliga", "ligue1": "Ligue 1", "eredivisie": "Eredivisie"}
SALIDA = RAIZ / "dashboard-predicciones"

# Textos de interpretación por liga y sección. Van escritos a mano después de revisar los resultados de cada liga
# (igual que en el notebook): un texto genérico diría cosas falsas en alguna liga.
LECTURAS = {
    "Liga MX": {
        "plantillas": (
            "Los equipos rotan más que nunca: la mediana de jugadores usados pasó de 28-30 (hasta 2019-20) a 33-35, y "
            "los necesarios para el 80% de los minutos de 13-14 a 15-16. El salto coincide con los cinco cambios por "
            "partido (2020). Los minutos de extranjeros subieron del 30% (2010-14) a un máximo de 54% (2019-20) y hoy "
            "rondan el 45%. Rotar mucho va de la mano con perder: correlación de −0.47 con los puntos por partido "
            "(probablemente en los dos sentidos: el que pierde cambia jugadores y el que gana no toca su once)."),
        "porteros": (
            "El % de paradas de la liga bajó de 74% (2010-11) a 67% (2025-26). Nahuel Guzmán es el mejor portero del "
            "periodo en las tres métricas entre los 39 con 100+ partidos. El % de paradas es en parte del portero "
            "(correlación de 0.30 entre una temporada y la siguiente); las porterías a cero dependen más de la defensa "
            "(0.22). 2018-19 no tiene paradas en FBref: el hueco es a propósito. Los desacuerdos de FBref en goles "
            "recibidos se concentran en 2014-15 y 2015-16."),
        "impacto": (
            "El efecto con/sin el jugador (on-off) y los puntos de su equipo con él casi no se repiten de un año al "
            "siguiente (0.02 y 0.09), mientras que los goles por 90 de un delantero sí (0.52). Con datos de temporada, "
            "esas medidas no miden al jugador: por eso aquí no hay ranking de 'impacto'. Medirlo en serio exige los "
            "minutos compartidos partido a partido (alineaciones y cambios)."),
        "dependencia": (
            "Depender del goleador no se asocia con sumar puntos (0.04); lo que sí se asocia es cuántos goles mete el "
            "equipo (0.78). Iván Alonso hizo el 60% de los goles del Toluca 2011-12 y João Pedro el 54% del San Luis "
            "2025-26, y ninguno de esos equipos pasó de 1.24 puntos por partido. Los goles están hoy más repartidos: "
            "la dependencia mediana bajó de 25-32% a 19-24% desde 2021-22."),
    },
    "Premier League": {
        "plantillas": (
            "A diferencia de la Liga MX, la rotación no creció: 25-29 jugadores usados y 13-14 para el 80% de los minutos "
            "en todo el periodo. Lo que sí cambió: los minutos de extranjeros (fuera del Reino Unido) pasaron del 50-59% "
            "(2010-14) al 73% en 2025-26, y los equipos son más jóvenes (edad de quien juega 26.7 → 25.6). Rotar se asocia "
            "con perder (−0.29), menos que en la Liga MX: el Leicester campeón de 2015-16 repartió el 80% de sus minutos "
            "entre solo 10 jugadores."),
        "porteros": (
            "El % de paradas de la liga también cae (71% → 66%). Petr Čech tiene el mejor % de paradas de los 45 porteros "
            "con 100+ partidos (74.4%), y Ederson las mejores porterías a cero (44.6%) y la menor cantidad de goles "
            "recibidos por 90 (0.79). Las porterías a cero son más estables año a año que en la Liga MX (0.36 contra 0.22): "
            "las diferencias entre equipos se sostienen. 2023-24 fue la temporada más goleadora (1.61 goles recibidos por "
            "partido). Las dos tablas de FBref casi siempre coinciden en los goles recibidos."),
        "impacto": (
            "Igual que en la Liga MX: el on-off y los puntos del equipo con el jugador no se repiten de un año al siguiente "
            "(0.02 y 0.04, con más de 1,400 pares cada uno), mientras que los goles sin penal por 90 de un delantero sí "
            "(0.62). Con datos de temporada no miden al jugador; no hay ranking de 'impacto'."),
        "dependencia": (
            "Depender del goleador no da puntos (0.05); lo que cuenta son los goles del equipo (0.87, más que en la Liga "
            "MX). De los seis equipos más dependientes, cuatro descendieron (Defoe hizo el 54% de los goles del Sunderland "
            "2016-17); la excepción notable es Harry Kane, con el 44% de los goles del Tottenham 2022-23. En 2025-26, "
            "Haaland aportó el 15% de los puntos fantasy del Manchester City."),
    },
    "La Liga": {
        "plantillas": (
            "La rotación creció, pero menos que en la Liga MX: 26-28 jugadores usados (2010-18) frente a 29-31 (2020-26). "
            "Es la liga más local de las tres publicadas: los minutos de extranjeros oscilan entre 36% y 47% sin tendencia, "
            "lejos del 73% de la Premier. Rotar se asocia con perder (−0.28): Las Palmas 2017-18 y Valladolid 2024-25 "
            "necesitaron 19 jugadores para el 80% de los minutos y descendieron, mientras que el Atlético campeón de "
            "2013-14 usó 11. Nota: cuatro equipos de 2011-12 (Mallorca, Getafe, Levante y Real Betis) aparecen sin puntos "
            "por partido porque FBref no tiene los resultados de sus porteros."),
        "porteros": (
            "El % de paradas cae menos que en las otras ligas (71.7% → 68.6%) y es la liga con menos goles recibidos por "
            "partido (1.22-1.30 entre 2018-19 y 2024-25). Keylor Navas tiene el mejor % de paradas de los 44 porteros con "
            "100+ partidos (76.7%), pero Jan Oblak domina porterías a cero (46.1%) y goles recibidos por 90 (0.79) en 399 "
            "partidos. Las porterías a cero son lo más estable año a año de las tres ligas (0.40): pesa más el equipo que "
            "el portero. En 2025-26 encabeza Joan García (Barcelona, 77.9%)."),
        "impacto": (
            "Tercera liga, mismo resultado: on-off 0.04 y puntos del equipo con el jugador 0.07 de una temporada a la "
            "siguiente, mientras que los goles sin penal por 90 de un delantero llegan a 0.69, la referencia más alta de "
            "las tres ligas. No es un problema de una liga: es lo que pasa al medir 'impacto' con totales de temporada."),
        "dependencia": (
            "Depender del goleador tampoco da puntos (0.11); los goles del equipo sí (0.82). Rubén Castro hizo el 56% de "
            "los goles del Betis 2015-16 y Vedat Muriqi el 49% del Mallorca 2025-26; el caso más productivo es Falcao, con "
            "el 47% de los goles del Atlético 2011-12 y 1.47 puntos por partido. En 2025-26 los mejores puntajes fantasy "
            "son de Mbappé (169) y Lamine Yamal (164)."),
    },
    "Serie A": {
        "plantillas": (
            "Rotación alta y estable (13.5-15 jugadores para el 80% de los minutos), extranjeros del 42.8% al 70.2% de los "
            "minutos y plantillas mucho más jóvenes que al inicio (de 27.7 a 25.8-26.0 años). Rotar se asocia con perder con "
            "fuerza (−0.41): Benevento 2017-18 necesitó 22 jugadores para el 80% de sus minutos y descendió, mientras que la "
            "Juventus campeona sin derrotas de 2011-12 usó 11."),
        "porteros": (
            "Gianluigi Buffon domina las tres métricas entre los 45 porteros con 100+ partidos —77.8% de paradas, 50.4% de "
            "porterías a cero y 0.65 goles recibidos por 90 en 252 partidos—, algo que no pasa en las demás ligas. Las "
            "porterías a cero son lo más estable año a año de las siete ligas (0.45). En 2025-26 encabeza Mile Svilar (Roma, "
            "77.5% y 18 porterías a cero), y la liga firmó su récord de porterías a cero (32.2%)."),
        "impacto": (
            "On-off 0.05 y puntos del equipo con el jugador 0.03 de una temporada a la siguiente. Aquí incluso la referencia "
            "individual es baja (0.49 de goles sin penal por 90 de los delanteros, contra 0.69 de La Liga)."),
        "dependencia": (
            "La dependencia del goleador es la más plana del panel (−0.04) y los goles del equipo, lo más asociado a los "
            "puntos de las siete ligas (0.89). Immobile (47% del Lazio 2019-20) e Higuaín (46% del Napoli 2015-16), ambos con "
            "36 goles, son los casos de alta dependencia con mejores resultados. Es también la liga con los puntos fantasy más "
            "repartidos: el mejor de cada equipo aporta entre 6% y 10%."),
    },
    "Bundesliga": {
        "plantillas": (
            "La rotación más estable de las siete ligas: 13-14 jugadores para el 80% de los minutos en las 16 temporadas. Es "
            "la segunda liga más joven, con hasta 21.7% de los minutos para jugadores de 21 años o menos. Extranjeros entre "
            "51.5% y 64.6%. Rotar se asocia con perder (−0.39): el Schalke 2020-21 usó 19 jugadores y sumó 0.5 puntos por "
            "partido; el Dortmund campeón de 2010-11 usó 11, con la plantilla más joven del panel (22.9 años)."),
        "porteros": (
            "Es la liga donde más se marca: el % de paradas es el más bajo del panel (70.4% → 65.4%), los goles recibidos por "
            "partido los más altos (1.36-1.60) y las porterías a cero las más escasas. Manuel Neuer domina con 423 partidos "
            "(45.2% de porterías a cero, 0.84 goles recibidos por 90); ter Stegen tiene el mejor % de paradas (76.7%) por sus "
            "años en el Gladbach."),
        "impacto": (
            "On-off 0.04 y puntos del equipo con el jugador −0.01: saber cuántos puntos sumó su equipo con él en una temporada "
            "no dice nada de la siguiente. La referencia individual llega a 0.59."),
        "dependencia": (
            "Es la liga donde la dependencia del goleador más se asocia con los puntos (0.21) y aun así es débil frente a los "
            "goles del equipo (0.84). Papiss Cissé hizo el 58% de los goles del Freiburg 2010-11. En 2025-26, Harry Kane firmó "
            "el mejor puntaje fantasy de todas las ligas: 212 puntos, el 13% de los del Bayern."),
    },
    "Ligue 1": {
        "plantillas": (
            "La mayor subida de extranjeros del panel: del 49% de los minutos en 2010-11 al 72.6% en 2025-26. Liga joven y con "
            "muchos minutos para juveniles (11.6-20.9%). Rotar se asocia con perder (−0.35), con una excepción: el PSG 2020-21 "
            "repartió el 80% de sus minutos entre 18 jugadores y sumó 2.2 puntos por partido. Los campeones Lille 2010-11 y "
            "Montpellier 2011-12 usaron 11. Ojo: la liga pasó de 20 a 18 equipos en 2023-24, y 2019-20 se cortó por COVID."),
        "porteros": (
            "Salvatore Sirigu (PSG) domina las tres métricas entre los 35 porteros con 100+ partidos: 77.6% de paradas, 44.8% "
            "de porterías a cero y 0.75 goles recibidos por 90. La liga pasó de ser la menos goleada del panel (1.15 goles "
            "recibidos por partido en 2010-11) a sus valores más altos (1.39-1.48). En 2025-26 encabeza Hervé Koffi (Angers, "
            "76.4%)."),
        "impacto": (
            "Las dos medidas de impacto salen NEGATIVAS de una temporada a la siguiente (on-off −0.03, puntos con él −0.06), "
            "frente al 0.60 de la referencia individual. Es la demostración más clara de que con totales de temporada estas "
            "medidas son ruido."),
        "dependencia": (
            "Dependencia del goleador 0.13 con los puntos; goles del equipo 0.78, la más baja junto con la Liga MX (pesa la "
            "distancia entre el PSG y el resto). Ibrahimović (46% del PSG 2012-13) y Cavani (35 goles, 44% en 2016-17) son las "
            "dependencias altas más productivas. En 2025-26 destacan Lepaul (Rennes, 161) y Greenwood (Marsella, 154)."),
    },
    "Eredivisie": {
        "plantillas": (
            "La liga más joven del panel con diferencia: 23.6-25.0 años de edad de quien juega y entre 20% y 33.6% de los "
            "minutos para jugadores de 21 años o menos (en la Premier son 6-12.7%). También la rotación más concentrada: 12-14 "
            "jugadores para el 80% de los minutos. Extranjeros entre 40.8% y 56.1%, sin tendencia. Rotar se asocia con perder "
            "(−0.38)."),
        "porteros": (
            "La línea del % de paradas es la más plana de las siete ligas (70.9% → 69.0%), con 2018-19 sin dato en FBref. Los "
            "goles recibidos por partido están entre los más altos (1.42-1.70) y las porterías a cero entre las más escasas. "
            "Cillessen tiene el mejor % de paradas (76.4% en 200 partidos) y Onana las mejores porterías a cero (39.9%) y goles "
            "recibidos por 90 (0.85)."),
        "impacto": (
            "El on-off llega aquí a su valor más alto del panel (0.08) y sigue siendo insignificante frente al 0.59 de la "
            "referencia individual. Con menos pares que en las grandes ligas (855), la conclusión es la misma."),
        "dependencia": (
            "Aquí está la dependencia más alta de todo el panel: Giorgos Giakoumakis hizo 26 de los 42 goles del VVV-Venlo "
            "2020-21 (62%), con 0.68 puntos por partido. Y aun así la dependencia no se asocia con los puntos (−0.02), "
            "mientras que los goles del equipo sí (0.86). En 2025-26 destacan Mika Godts (Ajax, 164 puntos) y Ayase Ueda "
            "(Feyenoord, 163 con 25 goles)."),
    },
}


def limpio(x):
    """Convierte a tipos de JSON: NaN/inf -> None, numpy -> Python, redondeo a 4 decimales."""
    if isinstance(x, dict):
        return {k: limpio(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [limpio(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        if math.isnan(x) or math.isinf(x):
            return None
        return int(x) if float(x).is_integer() else round(float(x), 4)     # 15.0 -> 15: el JSON pesa menos
    if isinstance(x, (np.bool_,)):
        return bool(x)
    return x


def registros(df, columnas):
    return limpio(df[columnas].to_dict("records"))


def main(clave):
    nombre = CLAVES[clave]
    filas = plantillas.unir_tablas_extra(plantillas.limpiar_panel(plantillas.cargar_panel_crudo()))
    jt = fantasy.puntos_fantasy(plantillas.agregar_por_temporada(filas))
    jt["pct_pts_jornada"] = fantasy.percentil_en_grupo(jt, "pts_por_jornada")
    filas, jt = filas[filas["league"] == nombre], jt[jt["league"] == nombre]
    # Dos vistas del mismo cálculo: las GRÁFICAS por temporada usan solo temporadas completas (una de 5 jornadas
    # haría ver una caída que solo es el calendario), y el EXPLORADOR sí incluye la que se está jugando, que es
    # justamente lo que se quiere mirar del presente.
    equipos = liga.resumen_equipos(filas, nombre)
    equipos_exp = liga.resumen_equipos(filas, nombre, incluir_parciales=True)
    temporadas = sorted(equipos["temporada_inicio"].unique())
    temporadas_exp = sorted(equipos_exp["temporada_inicio"].unique())
    ultima = temporadas[-1]
    etiqueta = {t: f"{t % 100:02d}-{(t + 1) % 100:02d}" for t in temporadas_exp}
    en_curso = [etiqueta[t] for t in temporadas_exp if t not in temporadas]

    # --- Control de calidad ---
    control = (equipos.assign(cobertura=equipos["minutos"] / (equipos["pj"] * 990))
               .groupby("temporada_inicio").agg(equipos=("team_id", "size"), partidos=("pj", "median"),
                                                cobertura_min=("cobertura", "min")).reset_index())

    # --- Plantillas ---
    metricas = ["jugadores_usados", "jugadores_80pct", "edad_ponderada", "pct_min_extranjeros", "pct_min_sub21"]
    tend = liga.tendencia_liga(equipos, metricas)
    series_plantillas = {m: {"mediana": tend[("mediana", m)].tolist(), "p25": tend[("p25", m)].tolist(),
                             "p75": tend[("p75", m)].tolist()} for m in metricas}
    cols_eq = ["season", "equipo", "jugadores_usados", "jugadores_80pct", "edad_ponderada", "pct_min_extranjeros",
               "pct_min_sub21", "ppg"]

    # --- Porteros ---
    lp = liga.porteros_liga(jt, nombre).reindex(temporadas)
    porteros_jt = jt[jt["gk_games"].notna()]
    r_par, n_par, _ = liga.estabilidad(porteros_jt, "gk_save_pct", minutos="gk_minutes")
    r_cero, n_cero, _ = liga.estabilidad(porteros_jt, "gk_clean_sheets_pct", minutos="gk_minutes")
    carreras = liga.carrera_porteros(jt, nombre, min_minutos=9000).head(12)
    ult_por = (jt[(jt["temporada_inicio"] == ultima) & (jt["gk_minutes"] >= 900)]
               .sort_values("gk_save_pct", ascending=False))

    # --- Impacto en cancha ---
    jt = liga.agregar_ppg_extra(jt, equipos)
    pruebas = {"on_off": ("plus_minus_wowy", jt), "ppg_extra": ("ppg_extra", jt),
               "referencia_goles": ("goals_pens_per90", jt[jt["pos_principal"] == "FW"])}
    impacto = {}
    for nombre_prueba, (col, datos) in pruebas.items():
        r, n, pares = liga.estabilidad(datos, col, min_minutos=1500)
        impacto[nombre_prueba] = {
            "r": r, "pares": n,
            "puntos": [[a, b, j, etiqueta[int(t)]] for a, b, j, t in
                       zip(pares[col], pares[f"{col}_siguiente"], pares["player"], pares["temporada_inicio"])]}

    # --- Dependencia y fantasy ---
    rho_dep = spearmanr(equipos["dependencia_goleador"], equipos["ppg"], nan_policy="omit").statistic
    rho_gol = spearmanr(equipos["goles"], equipos["ppg"], nan_policy="omit").statistic
    rho_rot = spearmanr(equipos["jugadores_80pct"], equipos["ppg"], nan_policy="omit").statistic
    mejores = liga.mejor_fantasy_por_equipo(jt, ultima)

    # --- Explorador de plantillas: una fila por jugador-EQUIPO-temporada ---
    # Los puntos fantasy se calculan sobre cada fila (lo que hizo en ESE equipo); el percentil es el de su temporada
    # completa en la liga (tabla jugador-temporada), porque se calculó con los totales de la temporada.
    exp = fantasy.puntos_fantasy(filas)
    percentil = jt.set_index(["id_jugador", "season"])["pct_pts_jornada"]
    pj_equipo = equipos_exp.set_index(["season", "team_id"])["pj"]
    exp = exp.assign(
        t=exp["temporada_inicio"].map(etiqueta),
        pct=percentil.reindex(list(zip(exp["id_jugador"], exp["season"]))).round(0).to_numpy(),
        pmin=(exp["minutes"] / (pj_equipo.reindex(list(zip(exp["season"], exp["team_id"]))).to_numpy() * 90)).round(3),
        gk_par=(100 * exp["gk_saves"] / exp["gk_shots_on_target_against"].where(exp["gk_shots_on_target_against"] > 0))
        .round(1))
    columnas_exp = {"t": "t", "eq": "team", "id": "id_jugador", "j": "player", "pos": "pos_principal", "edad": "age",
                    "nac": "nacionalidad", "pj": "games", "tit": "games_starts", "min": "minutes", "pmin": "pmin",
                    "g": "goals", "a": "assists", "ta": "cards_yellow", "tr": "cards_red", "pts": "pts_total",
                    "pct": "pct", "gk_pj": "gk_games", "gk_par": "gk_par", "gk_cero": "gk_clean_sheets",
                    "gk_gr": "gk_goals_against"}
    exp = exp.sort_values(["temporada_inicio", "team", "minutes"], ascending=[True, True, False])
    explorador = {"columnas": list(columnas_exp),
                  "filas": limpio(exp[list(columnas_exp.values())].astype(object).to_numpy().tolist())}

    datos = {
        "meta": {"liga": nombre, "clave": clave, "temporadas": [etiqueta[t] for t in temporadas],
                 # `temporadas` son las de las gráficas; el explorador usa esta otra, que añade la que está en curso.
                 "temporadas_explorador": [etiqueta[t] for t in temporadas_exp], "en_curso": en_curso,
                 "ultima_temporada": etiqueta[ultima], "jugador_temporadas": len(jt),
                 "jugadores": jt["id_jugador"].nunique(), "equipos": equipos["team_id"].nunique(),
                 "generado": datetime.now().strftime("%Y-%m-%d %H:%M"),
                 "fuente": "FBref (tablas estándar, playingtime y keepers) desde 2010-11"},
        "control": registros(control, ["temporada_inicio", "equipos", "partidos", "cobertura_min"]),
        "plantillas": {
            "series": series_plantillas, "rho_rotacion_puntos": rho_rot,
            "ultima": registros(equipos[equipos["temporada_inicio"] == ultima].sort_values("jugadores_80pct"), cols_eq),
            "mas_rotacion": registros(equipos.nlargest(6, "jugadores_80pct"), cols_eq),
            "menos_rotacion": registros(equipos.nsmallest(6, "jugadores_80pct"), cols_eq)},
        "porteros": {
            "series": {c: lp[c].tolist() for c in ("pct_paradas", "goles_recibidos_por_partido", "pct_porterias_cero")},
            "estabilidad": {"paradas": {"r": r_par, "pares": n_par}, "porterias_cero": {"r": r_cero, "pares": n_cero}},
            "carreras": registros(carreras, ["portero", "equipos", "desde", "hasta", "partidos", "pct_paradas",
                                             "pct_porterias_cero", "goles_recibidos_90"]),
            "ultima": registros(ult_por, ["player", "equipo_principal", "gk_games", "gk_save_pct", "gk_clean_sheets",
                                          "gk_goals_against"]),
            "desacuerdos": registros(liga.desacuerdo_goles_porteros(porteros_jt).assign(
                temporada=lambda d: d["temporada_inicio"].map(etiqueta)), ["temporada", "no_coinciden", "porteros"])},
        "impacto": impacto,
        "dependencia": {
            "rho_dependencia_puntos": rho_dep, "rho_goles_puntos": rho_gol,
            "puntos": registros(equipos.assign(temporada=equipos["temporada_inicio"].map(etiqueta)),
                                ["temporada", "equipo", "goleador", "goles_goleador", "goles", "dependencia_goleador",
                                 "ppg"]),
            "mediana_por_temporada": equipos.groupby("temporada_inicio")["dependencia_goleador"].median().tolist(),
            "fantasy_ultima": registros(mejores, ["equipo_principal", "player", "pos_principal", "goals", "assists",
                                                  "pts_total", "pts_equipo", "parte_del_equipo", "pct_pts_jornada"])},
        "explorador": explorador,
        "lectura": LECTURAS.get(nombre, {}),
    }
    ruta = SALIDA / f"analisis_{clave}.json"
    ruta.write_text(json.dumps(limpio(datos), ensure_ascii=False, separators=(",", ":"), allow_nan=False))
    print(f"{nombre}: {ruta.relative_to(RAIZ)} ({ruta.stat().st_size / 1024:.0f} KB)"
          + ("" if nombre in LECTURAS else " — sin textos de lectura (solo datos)"))


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in CLAVES:
        sys.exit(f"uso: python scripts/export_analisis_liga.py <{'|'.join(CLAVES)}>")
    main(sys.argv[1])
