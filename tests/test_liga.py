"""
Pruebas de futbol_bd.liga con equipos y jugadores escritos a mano, donde cada resultado se puede calcular de cabeza.
"""
import numpy as np
import pandas as pd
import pytest

from futbol_bd import liga


def test_jugadores_para_pct():
    # 11 titulares con 100 minutos cada uno y 5 suplentes con 10: el 80% de 1,150 = 920 -> hacen falta 10 titulares.
    assert liga.jugadores_para_pct([100] * 11 + [10] * 5) == 10
    assert liga.jugadores_para_pct([50, 30, 20]) == 2       # 50 + 30 = 80 exacto: basta con 2
    assert liga.jugadores_para_pct([0, 0]) == 0


def _jugador(player, team, minutos, goles, edad, nac, g=np.nan, e=np.nan, p=np.nan, temporada="2024-2025"):
    return {"league": "Liga MX", "season": temporada, "team_id": team, "team": team, "player": player,
            "minutes": minutos, "goals": goles, "age": edad, "nacionalidad": nac,
            # Los partidos del equipo se estiman con los minutos de sus porteros: un jugador de campo no aporta.
            "gk_minutes": minutos if not np.isnan(g) else np.nan,
            "gk_wins": g, "gk_ties": e, "gk_losses": p}


def test_resumen_equipos():
    filas = pd.DataFrame([
        _jugador("Portero", "A", 900, 0, 30, "MEX", g=5, e=3, p=2),
        _jugador("Goleador", "A", 900, 6, 20, "ARG"),
        _jugador("Otro", "A", 450, 2, 25, "MEX"),
        _jugador("Sin nacionalidad", "A", 450, 0, np.nan, "UNK"),
    ])
    r = liga.resumen_equipos(filas, "Liga MX").iloc[0]
    assert r["jugadores_usados"] == 4 and r["minutos"] == 2700
    assert r["edad_ponderada"] == pytest.approx((30 * 900 + 20 * 900 + 25 * 450) / 2250)   # sin la edad vacía
    assert r["pct_min_extranjeros"] == pytest.approx(100 * 900 / 2250)                      # UNK fuera del cálculo
    assert r["pct_min_sub21"] == pytest.approx(100 * 900 / 2700)
    assert (r["pj"], r["puntos"]) == (10, 18) and r["ppg"] == pytest.approx(1.8)
    assert r["goleador"] == "Goleador" and r["dependencia_goleador"] == pytest.approx(6 / 8)


def test_resultados_no_confiables_quedan_vacios():
    # FBref a veces trae los partidos del portero pero sus G/E/P en cero (Mallorca 2011-12): los puntos por partido
    # serían falsos, así que deben quedar vacíos.
    filas = pd.DataFrame([
        _jugador("Portero", "A", 3420, 0, 30, "MEX", g=1, e=0, p=0),      # 38 partidos de minutos, 1 con resultado
        _jugador("Otro", "A", 3000, 5, 25, "MEX"),
    ])
    r = liga.resumen_equipos(filas, "Liga MX").iloc[0]
    assert r["pj"] == 38 and not r["resultados_confiables"]
    assert np.isnan(r["ppg"]) and np.isnan(r["puntos"]) and np.isnan(r["ganados"])


def test_estabilidad_detecta_senal_y_ruido():
    rng = np.random.default_rng(1)
    talento = rng.normal(size=200)
    filas = []
    for i, t in enumerate(talento):
        for temporada in (2020, 2021):
            filas.append({"id_jugador": f"j{i}", "player": f"j{i}", "temporada_inicio": temporada, "minutes": 2000,
                          "senal": t, "ruido": rng.normal()})
    df = pd.DataFrame(filas)
    r_senal, n, _ = liga.estabilidad(df, "senal")
    r_ruido, _, _ = liga.estabilidad(df, "ruido")
    assert n == 200 and r_senal == pytest.approx(1.0) and abs(r_ruido) < 0.2


def test_tasas_de_porteros_se_calculan_sobre_totales():
    jt = pd.DataFrame({
        "league": "Liga MX", "temporada_inicio": 2024, "id_jugador": ["t", "s"], "player": ["Titular", "Suplente"],
        "season": "2024-2025", "equipo_principal": "A", "gk_minutes": [9000, 900],
        "gk_games": [100, 10], "gk_saves": [70, 1], "gk_shots_on_target_against": [100, 10],
        "gk_goals_against": [30, 9], "gk_clean_sheets": [30, 0]})
    t = liga.porteros_liga(jt, "Liga MX").loc[2024]
    assert t["pct_paradas"] == pytest.approx(100 * 71 / 110)       # no (70% + 10%) / 2
    assert t["goles_recibidos_por_partido"] == pytest.approx(39 / 110)
    c = liga.carrera_porteros(jt, "Liga MX", min_minutos=9000)
    assert list(c["portero"]) == ["Titular"] and c["goles_recibidos_90"].iloc[0] == pytest.approx(30 / 100)


def test_ppg_extra_solo_con_un_equipo():
    equipos = pd.DataFrame({"season": ["S", "S"], "team_id": ["A", "B"], "ppg": [1.5, 1.0]})
    jt = pd.DataFrame({"season": "S", "equipo_principal_id": ["A", "B", "A"], "n_equipos": [1, 1, 2],
                       "points_per_game": [2.0, 0.8, 1.9]})
    r = liga.agregar_ppg_extra(jt, equipos)["ppg_extra"]
    assert r.iloc[0] == pytest.approx(0.5) and r.iloc[1] == pytest.approx(-0.2) and np.isnan(r.iloc[2])


def test_comparativa_devuelve_series_y_resumen():
    # Dos "ligas" mínimas: la comparativa debe dar una fila por liga-temporada y una por liga, con las mismas columnas.
    filas = pd.DataFrame([
        _jugador("Portero A", "A", 900, 0, 30, "MEX", g=6, e=2, p=2),
        _jugador("Goleador A", "A", 900, 8, 25, "ARG"),
        _jugador("Portero B", "B", 900, 0, 28, "MEX", g=3, e=3, p=4),
        _jugador("Goleador B", "B", 900, 4, 24, "MEX"),
    ])
    otra = filas.assign(league="Premier League")
    series, resumen = liga.comparativa(pd.concat([filas, otra]), pd.DataFrame(columns=[
        "league", "season", "temporada_inicio", "id_jugador", "player", "gk_games", "equipo_principal",
        "gk_minutes", "gk_saves", "gk_shots_on_target_against", "gk_goals_against", "gk_clean_sheets",
        "pos_principal", "minutes", "plus_minus_wowy", "points_per_game", "n_equipos", "equipo_principal_id",
        "goals_pens_per90", "gk_save_pct", "gk_clean_sheets_pct"]), ["Liga MX", "Premier League"])
    assert list(series["league"].unique()) == ["Liga MX", "Premier League"]
    assert set(liga.SERIES_COMPARABLES) <= set(series.columns)
    assert len(resumen) == 2 and {"rho_rotacion_puntos", "estab_on_off", "estab_referencia"} <= set(resumen.columns)


def _temporada_defensiva(id_jugador, pos, temporada, equipo, pc, ofensivos, minutos=2700):
    """Una fila jugador-temporada ya "puntuada", con lo mínimo que miran las funciones por posición."""
    return {"league": "Liga MX", "season": f"{temporada}-{temporada + 1}", "temporada_inicio": temporada,
            "id_jugador": id_jugador, "player": id_jugador, "pos_principal": pos, "equipo_principal_id": equipo,
            "minutes": minutos, "games": 30, "partidos_liga": 34, "def_completo": True, "porterias_cero": pc,
            "pts_total": ofensivos, "pts_defensivos": 4 * pc,
            "pts_total_completo": ofensivos + 4 * pc,
            "pts_por_jornada": ofensivos / 34, "pts_completo_por_jornada": (ofensivos + 4 * pc) / 34}


def test_comparativa_posiciones_resume_por_liga_y_posicion():
    rng = np.random.default_rng(7)
    filas = []
    for i in range(60):
        # El puntaje ofensivo es puro ruido y las porterías a cero se repiten: el puntaje completo tiene que salir
        # MÁS estable que el ofensivo, que es justo lo que la función existe para medir.
        pc = 4 + 12 * rng.random()
        for temporada in (2020, 2021):
            filas.append(_temporada_defensiva(f"d{i}", "DF", temporada, f"eq{i % 8}", pc, 10 * rng.random()))
    cp = liga.comparativa_posiciones(pd.DataFrame(filas), ["Liga MX"])
    assert list(cp["posicion"]) == liga.POSICIONES                      # una fila por posición, siempre las cuatro
    df = cp[cp["posicion"] == "DF"].iloc[0]
    assert df["jugadores"] == 60 and df["temporadas"] == 120 and df["pares"] == 60
    assert df["estab_completo"] > 0.8 > df["estab_ofensivo"]
    assert df["pct_defensivo"] == pytest.approx(100 * 4 * np.mean([f["porterias_cero"] for f in filas])
                                                / np.mean([f["pts_total_completo"] for f in filas]))
    assert np.isnan(cp[cp["posicion"] == "GK"].iloc[0]["estab_completo"])   # sin porteros en la muestra


def test_origen_porteria_cero_separa_jugador_de_equipo():
    rng = np.random.default_rng(3)
    filas = []
    for i in range(80):
        # Las porterías a cero dependen SOLO del equipo: quien se queda repite, quien cambia no.
        for temporada, equipo in ((2020, f"eq{i % 4}"), (2021, f"eq{i % 4}" if i < 40 else f"eq{(i + 1) % 4}")):
            nivel = {"eq0": 3.0, "eq1": 7.0, "eq2": 11.0, "eq3": 15.0}[equipo]
            filas.append(_temporada_defensiva(f"d{i}", "DF", temporada, equipo, nivel + rng.normal(scale=0.3), 50))
    r = liga.origen_porteria_cero(pd.DataFrame(filas)).set_index("posicion").loc["DF"]
    assert r["n_mismo_equipo"] == 40 and r["n_cambio_equipo"] == 40
    assert r["r_mismo_equipo"] > 0.9 and abs(r["r_cambio_equipo"]) < 0.6
    assert r["caida"] == pytest.approx(r["r_mismo_equipo"] - r["r_cambio_equipo"])


def _percentiles_sinteticos(rng, dificultad, n_por_grupo=150):
    """Jugadores con una habilidad fija y dos temporadas, en ligas de dificultad conocida.

    El percentil observado es habilidad − dificultad(liga) + ruido, así que al mudarse de una liga a otra el jugador
    debe perder exactamente la diferencia de dificultades: es lo que `escalera_ligas` tiene que recuperar.
    """
    ligas = list(dificultad)
    filas = []
    def añadir(jid, temporada, nombre_liga, club, habilidad):
        filas.append({"id_jugador": jid, "player": jid, "temporada_inicio": temporada,
                      "season": f"{temporada}-{temporada + 1}", "league": nombre_liga, "equipo_principal": club,
                      "equipo_principal_id": club, "pos_principal": "MF", "minutes": 2500, "def_completo": True,
                      "pct_completo": 50 + habilidad - dificultad[nombre_liga] + rng.normal(scale=8)})
    for i in range(n_por_grupo):                       # control: cambia de club, NO de liga
        hab, l = rng.normal(scale=20), ligas[i % len(ligas)]
        añadir(f"c{i}", 2020, l, f"{l}-A", hab)
        añadir(f"c{i}", 2021, l, f"{l}-B", hab)
    for i in range(n_por_grupo):                       # mudanzas internacionales, en todas las direcciones
        hab = rng.normal(scale=20)
        origen, destino = ligas[i % len(ligas)], ligas[(i // len(ligas)) % len(ligas)]
        if origen == destino:
            destino = ligas[(ligas.index(origen) + 1) % len(ligas)]
        añadir(f"m{i}", 2020, origen, f"{origen}-A", hab)
        añadir(f"m{i}", 2021, destino, f"{destino}-A", hab)
    return pd.DataFrame(filas), ligas


def test_escalera_ligas_recupera_dificultades_conocidas():
    rng = np.random.default_rng(5)
    dificultad = {"Dura": 10.0, "Media": 0.0, "Floja": -10.0}
    jt, ligas = _percentiles_sinteticos(rng, dificultad)
    mov, escalera = liga.escalera_ligas(jt, ligas, min_minutos=1500)

    assert len(mov) == 150 and set(mov["league"]) <= set(ligas)
    assert escalera["dificultad"].sum() == pytest.approx(0, abs=1e-6)     # la solución está centrada
    assert list(escalera["league"]) == ["Dura", "Media", "Floja"]         # ordenada de más a menos difícil
    estimada = escalera.set_index("league")["dificultad"]
    for nombre, real in dificultad.items():
        assert estimada[nombre] == pytest.approx(real, abs=3)             # el sesgo tiene que ser pequeño
    assert (escalera["ee"] < 3).all()
    assert escalera["llegadas"].sum() == escalera["salidas"].sum() == len(mov)


def test_escalera_ligas_no_confunde_regresion_a_la_media_con_dificultad():
    """Si todas las ligas son igual de difíciles, la escalera tiene que salir plana aunque los percentiles caigan."""
    rng = np.random.default_rng(6)
    jt, ligas = _percentiles_sinteticos(rng, {"A": 0.0, "B": 0.0, "C": 0.0})
    mov, escalera = liga.escalera_ligas(jt, ligas, min_minutos=1500)
    assert mov["residuo"].abs().mean() > 0                                # hay ruido individual...
    assert escalera["dificultad"].abs().max() < 3                         # ...pero ninguna liga destaca


def test_plantel_vs_puntos():
    filas, jt = [], []
    for i, (equipo, pct, g, e, p) in enumerate([("A", 90, 25, 5, 8), ("B", 60, 18, 8, 12), ("C", 30, 10, 9, 19)]):
        filas.append(_jugador("Portero", equipo, 3420, 0, 30, "MEX", g=g, e=e, p=p))
        filas.append(_jugador(f"Campo{i}", equipo, 3000, 5, 25, "MEX"))
        jt.append({"league": "Liga MX", "temporada_inicio": 2024, "equipo_principal_id": equipo, "minutes": 3000,
                   "pct_completo": pct, "def_completo": True})
    r = liga.plantel_vs_puntos(pd.DataFrame(filas), pd.DataFrame(jt), ["Liga MX"]).iloc[0]
    assert r["equipos_temporada"] == 3
    assert r["rho_plantel_puntos"] == pytest.approx(1.0)      # mejor plantel, más puntos, sin excepciones


def test_resumen_equipos_deja_fuera_la_temporada_en_curso():
    """Las series por temporada no pueden mezclar una temporada de 5 jornadas con las completas."""
    filas = pd.DataFrame([
        {**_jugador("Portero", "A", 3060, 0, 30, "MEX", g=20, e=7, p=7, temporada="2023-2024"),
         "temporada_inicio": 2023, "temporada_parcial": False},
        {**_jugador("Campo", "A", 3000, 10, 25, "MEX", temporada="2023-2024"),
         "temporada_inicio": 2023, "temporada_parcial": False},
        {**_jugador("Portero", "A", 450, 0, 30, "MEX", g=3, e=1, p=1, temporada="2026-2027"),
         "temporada_inicio": 2026, "temporada_parcial": True},
        {**_jugador("Campo", "A", 440, 2, 25, "MEX", temporada="2026-2027"),
         "temporada_inicio": 2026, "temporada_parcial": True},
    ])
    assert list(liga.resumen_equipos(filas, "Liga MX")["temporada_inicio"]) == [2023]
    con_todo = liga.resumen_equipos(filas, "Liga MX", incluir_parciales=True)
    assert sorted(con_todo["temporada_inicio"]) == [2023, 2026]
