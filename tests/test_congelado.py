"""Pruebas de las reglas del congelado: nada que ya empezó, y nada se pierde por no haber resultados nuevos."""
from datetime import datetime, timezone

import pandas as pd
import pytest

from futbol_bd import congelado
from futbol_bd.congelado import ZONA_MEXICO

# 2026-10-10 11:31 UTC = 12:31 en el Reino Unido (horario de verano, UTC+1) = 05:31 en México.
SABADO_1231_UK = datetime(2026, 10, 10, 11, 31, tzinfo=timezone.utc)


def test_un_partido_de_las_1230_uk_ya_empezo_a_las_1231_uk():
    assert congelado.ya_empezo("2026-10-10", "12:30", SABADO_1231_UK)


def test_un_partido_de_las_1500_uk_todavia_no_empieza():
    assert not congelado.ya_empezo("2026-10-10", "15:00", SABADO_1231_UK)


def test_el_horario_de_verano_cuenta():
    """12:30 UK en octubre son las 11:30 UTC, no las 12:30: con la hora mal leída el partido 'no habría empezado'."""
    justo_antes = datetime(2026, 10, 10, 11, 29, tzinfo=timezone.utc)
    justo_despues = datetime(2026, 10, 10, 11, 30, tzinfo=timezone.utc)
    assert not congelado.ya_empezo("2026-10-10", "12:30", justo_antes)
    assert congelado.ya_empezo("2026-10-10", "12:30", justo_despues)


def test_un_partido_de_ayer_ya_empezo_y_uno_de_manana_no():
    assert congelado.ya_empezo("2026-10-09", "20:00", SABADO_1231_UK)
    assert not congelado.ya_empezo("2026-10-11", "14:00", SABADO_1231_UK)


def test_sin_hora_solo_cuenta_por_dia():
    """Liga MX no trae hora: el partido de HOY no se puede descartar, el de AYER sí."""
    assert not congelado.ya_empezo("2026-10-10", None, SABADO_1231_UK)
    assert not congelado.ya_empezo("2026-10-10", float("nan"), SABADO_1231_UK)
    assert congelado.ya_empezo("2026-10-09", "", SABADO_1231_UK)


def test_un_datetime_sin_zona_horaria_se_rechaza():
    with pytest.raises(ValueError):
        congelado.ya_empezo("2026-10-10", "12:30", datetime(2026, 10, 10, 11, 31))


def _futura(fecha, local, visita, hora="15:00", sin_perfil=False):
    return {"date": fecha, "home_team": local, "away_team": visita, "hora_uk": hora, "sin_perfil": sin_perfil}


def test_pendientes_descarta_sin_perfil_ya_congelados_y_ya_empezados():
    futuras = [
        _futura("2026-10-10", "A", "B", "12:30"),                         # ya empezó
        _futura("2026-10-10", "C", "D", "15:00"),                         # sí
        _futura("2026-10-10", "E", "F", "15:00", sin_perfil=True),        # no hay predicción
        _futura("2026-10-11", "G", "H", "14:00"),                         # ya congelado
        _futura("2026-10-11", "I", "J", "14:00"),                         # sí
    ]
    congeladas = {("2026-10-11", "G", "H")}
    res = congelado.pendientes_de_congelar(futuras, congeladas, SABADO_1231_UK)
    assert [(f["home_team"], f["away_team"]) for f in res] == [("C", "D"), ("I", "J")]


def test_el_viernes_sin_resultados_nuevos_sigue_habiendo_algo_que_congelar():
    """El caso del 9 de octubre de 2026: 153 partidos nuevos en el calendario y ningún resultado nuevo."""
    fx = pd.DataFrame({"Date": ["10/10/2026", "10/10/2026", "11/10/2026"], "Time": ["15:00", "12:30", "14:00"],
                       "HomeTeam": ["Ath Madrid", "Espanol", "Betis"], "AwayTeam": ["Betis", "Elche", "Celta"]})
    nombres = {"Ath Madrid": "Atlético Madrid", "Espanol": "Espanyol", "Betis": "Real Betis", "Celta": "Celta Vigo"}
    pendientes = congelado.fixtures_sin_atender(fx, nombres, congeladas=set(), sin_perfil=set(), ahora=SABADO_1231_UK)
    assert len(pendientes) == 2                       # el de las 12:30 ya empezó
    assert set(pendientes["home_team"]) == {"Atlético Madrid", "Real Betis"}


def test_lo_ya_congelado_o_sin_perfil_no_vuelve_a_disparar_la_corrida():
    fx = pd.DataFrame({"Date": ["11/10/2026", "11/10/2026"], "Time": ["14:00", "16:00"],
                       "HomeTeam": ["Ath Madrid", "Frosinone"], "AwayTeam": ["Betis", "Como"]})
    nombres = {"Ath Madrid": "Atlético Madrid", "Betis": "Real Betis"}
    congeladas = {("2026-10-11", "Atlético Madrid", "Real Betis")}
    sin_perfil = {("2026-10-11", "Frosinone", "Como")}
    assert congelado.fixtures_sin_atender(fx, nombres, congeladas, sin_perfil, SABADO_1231_UK).empty


def test_un_calendario_vacio_no_revienta():
    vacio = pd.DataFrame(columns=["Date", "Time", "HomeTeam", "AwayTeam"])
    assert congelado.fixtures_sin_atender(vacio, {}, set(), set(), SABADO_1231_UK).empty


def test_liga_mx_usa_su_propio_horario():
    """17:00 en Ciudad de México = 23:00 UTC. A las 22:59 UTC no ha empezado; a las 23:00 sí. Leída como hora del
    Reino Unido (error posible al reutilizar la regla) ya habría empezado 6 horas antes."""
    antes = datetime(2026, 10, 10, 22, 59, tzinfo=timezone.utc)
    despues = datetime(2026, 10, 10, 23, 0, tzinfo=timezone.utc)
    assert not congelado.ya_empezo("2026-10-10", "17:00", antes, zona=ZONA_MEXICO)
    assert congelado.ya_empezo("2026-10-10", "17:00", despues, zona=ZONA_MEXICO)
    assert congelado.ya_empezo("2026-10-10", "17:00", antes)          # con la zona por defecto (UK) sí: por eso existe el parámetro


def test_el_horizonte_no_congela_la_cola_del_calendario():
    """Liga MX publica el torneo completo; solo se congelan los próximos 5 días (el 2026-10-10 se congelaron 63 de
    golpe, hasta el 22 de noviembre, y hubo que deshacerlo)."""
    sabado = datetime(2026, 10, 10, 11, 31, tzinfo=timezone.utc)       # 05:31 en México, sábado
    assert congelado.dentro_del_horizonte("2026-10-10", sabado)       # hoy
    assert congelado.dentro_del_horizonte("2026-10-15", sabado)       # +5 días, el borde
    assert not congelado.dentro_del_horizonte("2026-10-16", sabado)   # +6
    assert not congelado.dentro_del_horizonte("2026-11-22", sabado)


def test_los_partidos_lejanos_no_disparan_la_corrida():
    fx = pd.DataFrame({"Date": ["11/10/2026", "22/11/2026"], "Time": ["14:00", "19:00"],
                       "HomeTeam": ["A", "C"], "AwayTeam": ["B", "D"]})
    res = congelado.fixtures_sin_atender(fx, {}, set(), set(), SABADO_1231_UK)
    assert list(res["home_team"]) == ["A"]
