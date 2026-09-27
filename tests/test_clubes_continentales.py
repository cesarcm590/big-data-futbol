"""Pruebas de las dos competiciones que vienen de una API: UEFA y AFC (Fase 42). No tocan la red.

Cada una corresponde a un fallo real o a un control que se puso después de encontrarlo, no a un caso hipotético.
"""
import pandas as pd

from futbol_bd import clubes_continentales as cc


def partido_afc(local, visitante, goles=None, estado="scheduled", fase="LEAGUE STAGE", mid=None):
    """Un partido con la forma que devuelve la API de AFC, incluido su relleno de ceros."""
    return {
        "matchId": mid or f"{local}-{visitante}", "dateVenue": "2026-10-12", "timeVenueUTC": "16:00:00",
        "stage": {"name": fase}, "group": None,
        "homeTeam": {"name": local, "countryCode": "UZB"}, "awayTeam": {"name": visitante, "countryCode": "KSA"},
        # La API manda 0-0 en TODO lo que no se ha jugado. Ese es el relleno que hay que no confundir con un empate.
        "result": {"homeGoals": goles[0] if goles else 0, "awayGoals": goles[1] if goles else 0},
        "status": estado, "stadium": {"name": "X"},
        "referees": [{"role": "Assistant referee 1", "refereeName": "El asistente"},
                     {"role": "Referee", "refereeName": "El árbitro", "countryCode": "QAT"}],
    }


def test_un_partido_por_jugar_no_guarda_un_cero_a_cero():
    """La API manda 0-0 en los programados y así se guardaban 112 empates a cero que no existen.

    La web no los enseñaba —filtra por `jugado`— pero el dato estaba en el CSV esperando a que alguien leyera la
    columna sin filtrar. Un relleno que se puede confundir con un resultado es peor que un hueco: el hueco se ve.
    """
    d = cc.a_tabla_afc([partido_afc("Pakhtakor", "Al Qadsiah"),
                        partido_afc("Al Wasl", "Al Ahli", goles=(2, 1), estado="played")])
    sin_jugar = d[~d["jugado"]].iloc[0]
    assert pd.isna(sin_jugar["goles_local"]) and pd.isna(sin_jugar["goles_visitante"])
    jugado = d[d["jugado"]].iloc[0]
    assert (jugado["goles_local"], jugado["goles_visitante"]) == (2, 1)


def test_el_arbitro_es_el_principal_y_no_el_primer_asistente():
    """Los roles son 'Referee', 'Assistant referee 1' y 2: un `in` se quedaría con el asistente."""
    d = cc.a_tabla_afc([partido_afc("A", "B", goles=(1, 0), estado="played")])
    assert d.iloc[0]["arbitro"] == "El árbitro"


def liga_completa(equipos=4, por_equipo=2):
    """Una fase liga de juguete que cumple el formato: todos contra todos una vez, mitad en casa y mitad fuera."""
    nombres = [chr(ord("A") + i) for i in range(equipos)]
    filas, mid = [], 0
    for i in range(equipos):
        for j in range(i + 1, equipos):
            # Alterna el campo para que cada equipo acabe con los mismos partidos en casa que fuera.
            local, visitante = (nombres[i], nombres[j]) if (i + j) % 2 else (nombres[j], nombres[i])
            mid += 1
            filas.append({"match_id": mid, "fase": "LIGA", "local": local, "visitante": visitante,
                          "goles_local": 1.0, "goles_visitante": 0.0, "jugado": True})
    return pd.DataFrame(filas)


def test_el_formato_cuadra_cuando_todo_esta():
    c = cc.control_de_formato(liga_completa(), fase_liga="LIGA", equipos=4, por_equipo=3)
    assert c["formato_ok"] and c["fallos"] == []
    assert c["partidos_fase_liga"] == 6 and c["equipos"] == 4


def test_si_falta_un_partido_el_formato_lo_canta():
    """Es lo que tiene que atrapar: una descarga a medias no da error, da una tabla más corta."""
    c = cc.control_de_formato(liga_completa().iloc[:-1], fase_liga="LIGA", equipos=4, por_equipo=3)
    assert not c["formato_ok"]
    assert any("5 partidos y el formato pide 6" in f for f in c["fallos"])
    assert any("no juegan 3 partidos" in f for f in c["fallos"])


def test_un_cruce_repetido_tambien_lo_canta():
    """Bajar dos veces la misma jornada, o mezclar dos ediciones, deja rivales repetidos en una liga suiza."""
    d = liga_completa()
    repetido = d.iloc[[0]].assign(match_id=99)
    c = cc.control_de_formato(pd.concat([d, repetido], ignore_index=True),
                              fase_liga="LIGA", equipos=4, por_equipo=3)
    assert any("cruces se repiten" in f for f in c["fallos"])


def test_el_relleno_de_ceros_sale_en_el_control():
    """El control de formato es lo que destapó los 112 empates a cero de la AFC."""
    d = liga_completa().assign(jugado=False)
    c = cc.control_de_formato(d, fase_liga="LIGA", equipos=4, por_equipo=3)
    assert any("sin jugar CON marcador" in f for f in c["fallos"])


def test_el_reparto_de_casa_y_fuera_admite_el_margen_justo_de_un_formato_impar():
    """Con 3 partidos alguien juega 2-1 por fuerza; con 8 el reparto tiene que ser 4-4 exacto.

    Exigir la igualdad a secas daría una alarma falsa en el primer caso, y aceptar cualquier reparto dejaría pasar
    un 6-2 en el segundo, que sí sería un fallo de la descarga.
    """
    assert cc.control_de_formato(liga_completa(), fase_liga="LIGA", equipos=4, por_equipo=3)["formato_ok"]
    torcido = liga_completa()
    torcido.loc[torcido["visitante"] == "A", ["local", "visitante"]] = ["A", "Z"]   # A siempre en casa
    c = cc.control_de_formato(torcido, fase_liga="LIGA", equipos=4, por_equipo=3)
    assert any("casa y fuera" in f for f in c["fallos"])


def test_un_equipo_contra_si_mismo_no_pasa_desapercibido():
    d = liga_completa()
    d.loc[0, "visitante"] = d.loc[0, "local"]
    c = cc.control_de_formato(d, fase_liga="LIGA", equipos=4, por_equipo=3)
    assert any("contra sí mismo" in f for f in c["fallos"])
