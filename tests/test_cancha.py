"""
Pruebas del mapa de Apolonio sobre la cancha, con un partido escrito a mano donde cada resultado se puede comprobar.
"""
import numpy as np
import pandas as pd
import pytest

from futbol_bd import apolonio, cancha


def _evento(tipo, player, player_id, team, x, y, minuto=10, posicion="Center Midfield", **extra):
    base = {"type": tipo, "player": player, "player_id": player_id, "team": team, "location": [x, y],
            "minute": minuto, "position": posicion, "match_id": 1, "tactics": np.nan}
    return {**base, **extra}


@pytest.fixture
def eventos():
    """Dos jugadores con acciones en sitios conocidos, más el evento de alineación y ruido que debe ignorarse."""
    filas = [
        # Once titular: solo 'A' es titular; 'B' entró de cambio.
        {"type": "Starting XI", "team": "Equipo", "player": None, "player_id": None, "location": None,
         "minute": 0, "position": None, "match_id": 1,
         "tactics": {"formation": 442, "lineup": [{"player": {"id": 1, "name": "A"}}]}},
    ]
    # A: 25 acciones alrededor de (40, 20) -> 20 pases completados y 5 fallados.
    for i in range(25):
        filas.append(_evento("Pass", "A", 1, "Equipo", 40, 20, pass_outcome=None if i < 20 else "Incomplete"))
    # B: 30 acciones alrededor de (80, 60), todas conducciones (siempre cuentan como éxito).
    for _ in range(30):
        filas.append(_evento("Carry", "B", 2, "Equipo", 80, 60))
    # C: solo 5 acciones -> por debajo del mínimo, no debe aparecer.
    for _ in range(5):
        filas.append(_evento("Pass", "C", 3, "Equipo", 10, 10, pass_outcome=None))
    # Ruido que NO es acción con balón: recepciones y presiones no deben contarse.
    for _ in range(50):
        filas.append(_evento("Ball Receipt*", "A", 1, "Equipo", 5, 5))
        filas.append(_evento("Pressure", "A", 1, "Equipo", 5, 5))
    return pd.DataFrame(filas)


def test_posiciones_por_partido(eventos):
    d = cancha.posiciones_por_partido(eventos).set_index("player")
    assert set(d.index) == {"A", "B"}                       # C se queda fuera por pocas acciones
    assert d.loc["A", "acciones"] == 25 and d.loc["A", "exitosas"] == 20   # recepciones y presiones no cuentan
    assert d.loc["A", "pct_exito"] == pytest.approx(80.0)
    assert (d.loc["A", "x"], d.loc["A", "y"]) == (40, 20)   # la media de acciones idénticas es el propio punto
    assert d.loc["B", "exitosas"] == 30                     # una conducción siempre es acción exitosa
    assert d.loc["A", "titular"] and not d.loc["B", "titular"]
    assert d.loc["A", "formacion"] == "442"


def test_sitios_de_equipo_usa_el_once(eventos):
    d = cancha.posiciones_por_partido(eventos)
    assert list(cancha.sitios_de_equipo(d, 1, "Equipo")["player"]) == ["A"]            # solo el titular
    assert set(cancha.sitios_de_equipo(d, 1, "Equipo", solo_titulares=False)["player"]) == {"A", "B"}


def test_area_dominada_suma_uno_y_premia_al_de_mas_peso(eventos):
    d = cancha.posiciones_por_partido(eventos)
    areas = cancha.area_dominada(d)
    assert areas.sum() == pytest.approx(1.0)
    # B pesa más (30 contra 20) y está en el centro de su mitad: le toca más cancha que a A.
    assert areas[d.index[d["player"] == "B"][0]] > areas[d.index[d["player"] == "A"][0]]


def test_la_cancha_no_se_normaliza():
    """Dos sitios con el mismo peso separados solo a lo ancho: la frontera debe caer a media distancia REAL.

    Si el módulo escalara los ejes a [0, 1] como en el espacio de perfil, un desplazamiento a lo ancho (80 m) pesaría
    más que el mismo desplazamiento a lo largo (120 m) y la frontera se movería. Esta prueba lo impide.
    """
    etiquetas, xs, ys = apolonio.etiquetar([(60.0, 20.0), (60.0, 60.0)], [1.0, 1.0], modo="multiplicativo",
                                           resolucion=200, limites=cancha.LIMITES)
    areas = apolonio.areas(etiquetas, 2)
    assert areas[0] == pytest.approx(0.5, abs=0.01) and areas[1] == pytest.approx(0.5, abs=0.01)
    # La frontera está en y = 40: por debajo gana el sitio 0 y por encima el 1.
    fila_baja = np.abs(ys - 20).argmin()
    fila_alta = np.abs(ys - 60).argmin()
    assert etiquetas[fila_baja].max() == 0 and etiquetas[fila_alta].min() == 1


def _temporada_sintetica(rng, n_jugadores=60, n_partidos=20, ruido=0.02):
    """Jugadores con un área 'verdadera' fija más ruido por partido, en puestos conocidos.

    Sirve para comprobar que la fiabilidad por mitades detecta la señal que de verdad hay: si cada jugador tiene su
    propia área característica, la correlación entre sus dos mitades de temporada tiene que salir alta.
    """
    puestos = ["Goalkeeper", "Right Back", "Center Midfield", "Center Forward"]
    filas, partidos = [], []
    verdadera = {i: 0.05 + 0.10 * rng.random() for i in range(n_jugadores)}
    for p in range(n_partidos):
        partidos.append({"match_id": p, "match_date": f"2015-08-{p + 1:02d}"})
        for i in range(n_jugadores):
            filas.append({"match_id": p, "team": f"eq{i % 4}", "player": f"j{i}", "player_id": i,
                          "posicion": puestos[i % 4], "titular": True,
                          "area": max(0.001, verdadera[i] + rng.normal(scale=ruido))})
    return pd.DataFrame(filas), pd.DataFrame(partidos)


def test_fiabilidad_del_area_detecta_senal_y_ruido():
    rng = np.random.default_rng(4)
    pos, par = _temporada_sintetica(rng, ruido=0.01)
    f = cancha.fiabilidad_del_area(pos, par)
    assert f["jugadores"] == 60 and f["partidos_por_jugador"] == pytest.approx(20)
    assert f["r_area_corregida"] > 0.9                  # cada jugador tiene su área propia: muy fiable
    assert f["r_menos_puesto_corregida"] > 0.9          # y no es el puesto: los 4 puestos se reparten al azar

    # Si el área depende SOLO del puesto y lo demás es ruido, al quitar la media del puesto no debe quedar nada.
    filas = pos.copy()
    por_puesto = {"Goalkeeper": 0.05, "Right Back": 0.09, "Center Midfield": 0.13, "Center Forward": 0.07}
    filas["area"] = filas["posicion"].map(por_puesto) + rng.normal(scale=0.01, size=len(filas))
    g = cancha.fiabilidad_del_area(filas, par)
    assert g["r_area_corregida"] > 0.9                  # sigue "fiable"... pero solo porque distingue puestos
    assert abs(g["r_menos_puesto_corregida"]) < 0.4     # al quitar el puesto no queda señal del jugador


def test_origen_del_area_separa_los_tres_grados():
    rng = np.random.default_rng(8)
    pos, par = _temporada_sintetica(rng, n_jugadores=40, n_partidos=12)
    # Un jugador que cambia de línea a mitad de temporada: sus pares deben quedar en 'cambió de línea'.
    pos.loc[(pos["player_id"] == 0) & (pos["match_id"] >= 6), "posicion"] = "Center Forward"
    r = cancha.origen_del_area(pos, par).set_index("grupo")
    assert set(r.index) >= {"TODOS"}
    assert r.loc["TODOS", "pares"] == 40 * 11           # 12 partidos -> 11 pares consecutivos por jugador
    assert r.loc["TODOS", "n_cambió_de_línea"] == 1     # solo el cambio que se introdujo a propósito
