"""Pruebas del seguimiento de la Nations League (Fase 29). No tocan la red: usan una respuesta de ejemplo."""
import pandas as pd
import pytest

from futbol_bd import calendario, nations_league

CRUDO = [
    {"id": "1", "status": "FINISHED",
     "kickOffTime": {"dateTime": "2026-09-24T18:45:00+0000"},
     "homeTeam": {"countryCode": "NOR", "translations": {"displayName": {"EN": "Norway"}}},
     "awayTeam": {"countryCode": "DEN", "translations": {"displayName": {"EN": "Denmark"}}},
     "score": {"total": {"home": 3, "away": 2}},
     "group": {"league": {"metaData": {"leagueName": "League A"}}, "metaData": {"name": "Group A1"}},
     "matchday": {"translations": {"name": {"EN": "Matchday 1"}}},
     "referees": [{"role": "ASSISTANT_REFEREE_1", "person": {"countryCode": "SWE"}},
                  {"role": "REFEREE", "person": {"countryCode": "GER",
                                                 "translations": {"name": {"EN": "Tobias Stieler"}}}}],
     "stadium": {"translations": {"officialName": {"EN": "Ullevaal"}}}},
    {"id": "2", "status": "UPCOMING",
     "kickOffTime": {"dateTime": "2026-11-17T19:45:00+0000"},
     "homeTeam": {"countryCode": "WAL", "translations": {"displayName": {"EN": "Wales"}}},
     "awayTeam": {"countryCode": "POR", "translations": {"displayName": {"EN": "Portugal"}}},
     "score": {}, "group": {"league": {"metaData": {"leagueName": "League B"}}},
     "matchday": {}, "referees": [], "stadium": {}},
]


@pytest.fixture
def tabla():
    return nations_league.a_tabla(CRUDO)


def test_extrae_marcador_arbitro_y_liga(tabla):
    j = tabla[tabla["match_id"] == "1"].iloc[0]
    assert (j["goles_local"], j["goles_visitante"]) == (3, 2)
    assert j["arbitro"] == "Tobias Stieler" and j["arbitro_pais"] == "GER"   # el principal, no el asistente
    assert j["liga"] == "League A" and j["fecha"] == "2026-09-24"
    assert j["jugado"]


def test_un_partido_sin_jugar_no_inventa_datos(tabla):
    f = tabla[tabla["match_id"] == "2"].iloc[0]
    assert pd.isna(f["goles_local"]) and pd.isna(f["goles_visitante"])
    assert not f["jugado"]
    assert f["arbitro"] is None or pd.isna(f["arbitro"])     # sin designar todavía


def test_la_neutralidad_se_comprueba_de_verdad():
    """Si un árbitro fuera del país de un equipo, el control TIENE que verlo."""
    malo = [dict(CRUDO[0], id="3",
                 referees=[{"role": "REFEREE", "person": {"countryCode": "NOR",
                                                          "translations": {"name": {"EN": "Alguien"}}}}])]
    d = nations_league.a_tabla(CRUDO + malo)
    fallos = nations_league.comprobar_neutralidad(d)
    assert len(fallos) == 1 and fallos.iloc[0]["match_id"] == "3"
    # Y los partidos correctos no se marcan por error.
    assert nations_league.comprobar_neutralidad(nations_league.a_tabla(CRUDO)).empty


def test_ventana_activa_reconoce_la_fecha_fifa():
    cal = calendario.cargar_calendario()
    dentro = calendario.ventana_activa(cal, pd.Timestamp("2026-09-26"))
    assert dentro is not None and dentro["edicion"] == "2026-09"
    # Entre ventanas no debe activarse: en pleno diciembre no se juegan selecciones.
    assert calendario.ventana_activa(cal, pd.Timestamp("2026-12-15")) is None


def test_la_ventana_sigue_activa_unos_dias_despues_de_cerrar():
    """El margen existe porque los datos de la última jornada tardan en cuadrar."""
    cal = calendario.cargar_calendario()
    assert calendario.ventana_activa(cal, pd.Timestamp("2026-10-08"), margen_dias=3) is not None
    assert calendario.ventana_activa(cal, pd.Timestamp("2026-10-08"), margen_dias=0) is None
