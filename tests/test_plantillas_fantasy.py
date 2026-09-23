"""
Pruebas de la limpieza del panel y del cálculo de puntos fantasy, con un mini-panel escrito a mano.

Cada fila del mini-panel representa uno de los problemas reales que encontró la auditoría de la Fase 19, para que un
cambio futuro en la limpieza no pueda reintroducirlos sin que falle una prueba.
"""
import numpy as np
import pandas as pd
import pytest

from futbol_bd import fantasy, plantillas

COLUMNAS = ["ranker", "player", "nationality", "position", "team", "age", "birth_year", "games", "games_starts",
            "minutes", "minutes_90s", "goals", "assists", "goals_assists", "goals_pens", "pens_made", "pens_att",
            "cards_yellow", "cards_red", "goals_per90", "assists_per90", "goals_assists_per90", "goals_pens_per90",
            "goals_assists_pens_per90", "league", "season", "player_id", "team_id"]


# Un id de equipo distinto por equipo, como en FBref (la unión con playingtime/keepers es por jugador Y equipo).
IDS_EQUIPO = {"Toluca": "0e000001", "América": "0e000002", "Pachuca": "0e000003", "Puebla": "0e000004",
              "León": "0e000005", "Marseille": "0e000006", "PSG": "0e000007", "Almería": "0e000008", "Tecos": "0e000009"}


def _fila(ranker, player, team, by, games, starts, minutes, goals, assists, pid, pens_made=0, pens_att=0, yel=0,
          red=0, nat="mx MEX", pos="FW", league="Liga MX", season="2024-2025"):
    return [ranker, player, nat, pos, team, 25, by, games, starts, minutes, None, goals, assists, None, None,
            pens_made, pens_att, yel, red, None, None, None, None, None, league, season, pid, IDS_EQUIPO[team]]


@pytest.fixture
def ruta_mini_panel(tmp_path):
    filas = [
        # Traspaso dentro de la liga: dos filas del mismo jugador (mismo id) que deben sumarse en una temporada.
        _fila(1, "Raúl Pérez", "Toluca", 1998, 10, 10, "900", 5, 2, "aaaa0001", pens_made=1, pens_att=2, yel=1,
              pos="FW,MF"),
        _fila(2, "Raúl Pérez", "América", 1998, 5, 1, "150", 1, 0, "aaaa0001"),
        # Homónimo: mismo nombre, otra persona (otro id de FBref).
        _fila(3, "Raúl Pérez", "Pachuca", 2004, 3, 0, "60", 0, 0, "aaaa0002", pos="DF"),
        # Fila duplicada bajo DOS ids (caso Torrasi): mismo contenido -> se elimina aunque los ids difieran.
        _fila(4, "Juan Duplicado", "Puebla", 2000, 2, 0, "20", 0, 0, "0d0d0001", pos="MF"),
        _fila(5, "Juan Duplicado", "Puebla", 2000, 2, 0, "20", 0, 0, "0d0d0002", pos="MF"),
        # Asistencias vacías (casos Bundesliga 2010-11) y penal anotado sin intento (caso Lemina). Id solo con dígitos
        # y otro con forma de notación científica: deben quedar como texto, intactos.
        _fila(6, "Pedro Vacío", "León", 1995, 30, 30, "2,700", 3, None, "12345678", pens_made=1, pens_att=0, red=1,
              pos="DF"),
        _fila(7, "Luis Científico", "León", 1996, 1, 0, "10", 0, 0, "1e345678", pos="MF"),
        # Mismo nombre, año y nacionalidad pero dos personas (caso Vitinha): el id de FBref las separa.
        _fila(8, "Vitinha", "Marseille", 2000, 4, 4, "360", 1, 0, "74d4cec6", nat="pt POR", league="Ligue 1"),
        _fila(9, "Vitinha", "PSG", 2000, 4, 4, "360", 0, 1, "3b029691", nat="pt POR", pos="MF", league="Ligue 1"),
        # Perfil duplicado en FBref (caso Édgar Méndez): el id alias se une al canónico de ALIAS_FBREF.
        _fila(10, "Edgar Mendez", "Almería", 1990, 30, 25, "1,912", 4, 1, "f5e19d23", nat="es ESP", pos="MF",
              league="La Liga", season="2014-2015"),
        # Jugador sin página en FBref: el id es su nombre.
        _fila(11, "Cesar Moreno", "Tecos", None, 1, 0, "12", 0, 0, "Cesar-Moreno", pos="MF"),
        # Un portero, para la unión con la tabla keepers.
        _fila(12, "Portero Uno", "León", 1990, 30, 30, "2,700", 0, 0, "abcd0001", pos="GK"),
    ]
    ruta = tmp_path / "mini_panel.csv"
    pd.DataFrame(filas, columns=COLUMNAS).to_csv(ruta, index=False)
    return ruta


@pytest.fixture
def panel_crudo(ruta_mini_panel):
    return plantillas.cargar_panel_crudo(ruta_mini_panel)


def test_ids_se_leen_como_texto(panel_crudo):
    assert set(panel_crudo["player_id"]) >= {"12345678", "1e345678"}


def test_limpieza(panel_crudo):
    lim = plantillas.limpiar_panel(panel_crudo)
    assert len(lim) == len(panel_crudo) - 1                          # el duplicado se fue, aunque sus ids difieran
    assert lim.loc[lim["player"] == "Pedro Vacío", "minutes"].item() == 2700  # "2,700" -> 2700
    fila = lim[lim["player"] == "Pedro Vacío"].iloc[0]
    assert fila["assists"] == 0 and fila["goals_assists"] == 3       # vacío -> 0, derivada recalculada
    assert fila["pens_att"] == 1                                     # max(intentos, anotados)
    assert lim.loc[lim["player"] == "Raúl Pérez", "id_jugador"].nunique() == 2   # 1998 y 2004 son personas distintas
    assert lim.loc[lim["player"] == "Vitinha", "id_jugador"].nunique() == 2       # el id de FBref los separa
    assert lim.loc[lim["player"] == "Edgar Mendez", "id_jugador"].item() == "aed746df"   # alias -> id canónico
    assert lim.set_index("player")["id_provisional"].to_dict()["Cesar Moreno"]
    assert not lim.set_index("player")["id_provisional"].to_dict()["Luis Científico"]
    assert set(lim["pos_principal"]) <= {"FW", "MF", "DF", "GK"}


def test_clave_por_nombre_junta_homonimos_y_sirve_de_respaldo(panel_crudo):
    # Sin ids de FBref, la clave por nombre es el respaldo... y confirma por qué no basta: junta a los dos Vitinha.
    sin_ids = panel_crudo.drop(columns=["player_id", "team_id"])
    ids = plantillas.construir_id_jugador(sin_ids)
    assert ids[panel_crudo["player"] == "Vitinha"].nunique() == 1
    assert ids.iloc[0] == "raul-perez|1998|MEX"


def test_agregacion_suma_traspaso(panel_crudo):
    jt = plantillas.agregar_por_temporada(plantillas.limpiar_panel(panel_crudo))
    raul = jt[jt["id_jugador"] == "aaaa0001"].iloc[0]
    assert raul["games"] == 15 and raul["minutes"] == 1050 and raul["goals"] == 6
    assert raul["equipo_principal"] == "Toluca" and raul["equipos"] == "Toluca / América"
    assert raul["pos_principal"] == "FW"                             # la del equipo con más minutos
    assert raul["goals_per90"] == pytest.approx(6 / (1050 / 90))
    assert raul["pct_minutos"] == pytest.approx(1050 / (30 * 90))    # 30 = máximo de partidos en esa liga-temporada


def test_auditoria_encuentra_cada_problema(panel_crudo):
    aud = plantillas.auditar_panel(panel_crudo).set_index("chequeo")["casos"]
    assert aud["fila duplicada (mismo contenido)"] == 1
    assert aud["otro conteo vacío (asistencias, penales)"] == 1
    assert aud["más penales anotados que intentados"] == 1
    assert aud["jugador en 2+ equipos de la misma liga-temporada (traspaso)"] == 1
    assert aud["mismo nombre con 2+ años de nacimiento en una liga-temporada"] == 1
    assert aud["jugador sin página en FBref (id = su nombre)"] == 1
    assert aud["nombre + año + nacionalidad iguales, 2 personas"] == 1          # Vitinha (en HOMONIMOS_VERIFICADOS)
    # "Juan Duplicado" tiene 2 ids que nadie ha revisado: la auditoría debe marcarlo como pendiente.
    assert aud["candidatos de identidad sin revisar"] == 1


def test_puntos_fantasy_a_mano(panel_crudo):
    jt = fantasy.puntos_fantasy(plantillas.agregar_por_temporada(plantillas.limpiar_panel(panel_crudo)))
    raul = jt[jt["id_jugador"] == "aaaa0001"].iloc[0]
    # 11 titularidades × 2 + 4 suplencias × 1 = 26; 6 goles de delantero × 4 = 24; 2 asist × 3 = 6;
    # 1 amarilla = −1; 1 penal fallado (2 intentos, 1 anotado) = −2.  Total = 53.
    assert raul["pts_aparicion"] == 26 and raul["pts_goles"] == 24 and raul["pts_asistencias"] == 6
    assert raul["pts_tarjetas"] == -1 and raul["pts_penales"] == -2 and raul["pts_total"] == 53
    assert raul["pts_por_jornada"] == pytest.approx(53 / 30)
    pedro = jt[jt["player"] == "Pedro Vacío"].iloc[0]
    # Defensa: 30 × 2 + 3 goles × 6 − 3 (roja); el penal "anotado sin intento" ya no cuenta como fallado.
    assert pedro["pts_total"] == 60 + 18 - 3


def test_percentil_respeta_minimo_de_minutos():
    df = pd.DataFrame({"league": "L", "season": "S", "pos_principal": "FW",
                       "minutes": [1000, 2000, 3000, 100], "x": [1.0, 2.0, 3.0, 99.0]})
    pct = fantasy.percentil_en_grupo(df, "x", min_minutos=900)
    assert np.isnan(pct.iloc[3])                       # sin minutos suficientes: sin percentil, aunque su valor sea 99
    assert list(pct.iloc[:3].round(1)) == [33.3, 66.7, 100.0]


@pytest.fixture
def carpeta_raw(tmp_path):
    """Mini `data/raw/` con las tablas playingtime y keepers para algunos jugadores del mini-panel."""
    base = ["league", "season", "player", "nationality", "position", "team", "player_id", "team_id"]
    pt_cols = base + plantillas.SUMAS_PLAYINGTIME + list(plantillas.PROMEDIOS_PLAYINGTIME)
    pt = pd.DataFrame([
        # Raúl Pérez en sus dos equipos: se suman los conteos y se pondera el promedio.
        ["Liga MX", "2024-2025", "Raúl Pérez", "mx MEX", "FW", "Toluca", "aaaa0001", "0e000001",
         "5", "0", "2", "12", "10", "2.00", "0.50"],
        ["Liga MX", "2024-2025", "Raúl Pérez", "mx MEX", "FW", "América", "aaaa0001", "0e000002",
         "0", "4", "7", "3", "4", "1.00", "-1.00"],
        # Pedro Vacío: temporada "vieja" sin datos en cancha (celdas vacías) -> deben quedar NaN, no 0.
        ["Liga MX", "2024-2025", "Pedro Vacío", "mx MEX", "DF", "León", "12345678", "0e000005",
         "", "", "", "", "", "", ""],
    ], columns=pt_cols)
    kp_cols = base + plantillas.SUMAS_KEEPERS
    kp = pd.DataFrame([["Liga MX", "2024-2025", "Portero Uno", "mx MEX", "GK", "León", "abcd0001", "0e000005",
                        "30", "30", "2,700", "25", "100", "75", "12", "9", "9", "10", "", "", "", ""]],
                      columns=kp_cols)
    for nombre, df in (("playingtime", pt), ("keepers", kp)):
        (tmp_path / f"fbref_{nombre}").mkdir()
        df.to_csv(tmp_path / f"fbref_{nombre}" / "Liga-MX_2024-2025.csv", index=False)
    return tmp_path


def test_union_playingtime_y_keepers(ruta_mini_panel, carpeta_raw):
    jt = plantillas.cargar_jugadores_temporada(ruta_mini_panel, carpeta_raw=carpeta_raw).set_index("player")
    raul = jt.loc["Raúl Pérez"].query("birth_year == 1998").iloc[0]
    assert raul["on_goals_for"] == 15 and raul["on_goals_against"] == 14 and raul["plus_minus"] == 1
    assert raul["unused_subs"] == 9 and raul["games_subs"] == 4
    assert raul["points_per_game"] == pytest.approx((2.0 * 10 + 1.0 * 5) / 15)       # ponderado por partidos
    assert raul["plus_minus_wowy"] == pytest.approx((0.5 * 900 + -1.0 * 150) / 1050)  # ponderado por minutos
    assert raul["on_goals_against_per90"] == pytest.approx(14 / (1050 / 90))
    pedro = jt.loc["Pedro Vacío"]
    assert np.isnan(pedro["on_goals_against"]) and np.isnan(pedro["points_per_game"])  # sin dato != 0
    portero = jt.loc["Portero Uno"]
    assert portero["gk_clean_sheets"] == 10 and portero["gk_minutes"] == 2700
    assert portero["gk_save_pct"] == pytest.approx(75.0) and portero["gk_clean_sheets_pct"] == pytest.approx(100 / 3)
    assert np.isnan(portero["gk_pens_saved"])                                          # penales sin dato
    assert np.isnan(raul["gk_games"])                                                  # no es portero


# --- Fantasy defensivo (Fase 21) -------------------------------------------------------------------------------

def test_esperanza_piso_coincide_con_la_suma_directa():
    """E[⌊X/m⌋] bajo Poisson: se compara con la suma término a término, y los casos borde (0 y sin dato)."""
    from math import exp, factorial as fac
    for lam in (0.5, 1.3, 3.0, 8.0):
        for m in (2, 3):
            directo = sum((k // m) * exp(-lam) * lam ** k / fac(k) for k in range(60))
            assert fantasy.esperanza_piso(np.array([lam]), m)[0] == pytest.approx(directo, abs=1e-9)
    assert fantasy.esperanza_piso(np.array([0.0]), 2)[0] == 0        # sin goles recibidos, sin penalización
    assert np.isnan(fantasy.esperanza_piso(np.array([np.nan]), 2)[0])  # sin dato NO es cero


def test_esperanza_piso_es_menor_que_dividir_el_total():
    """El redondeo por partido siempre da menos que repartir el total: es la corrección que justifica la función."""
    lam = np.array([1.0, 2.5, 3.0])
    assert (fantasy.esperanza_piso(lam, 3) < lam / 3).all()


def test_porterias_cero_estimadas_casos_exactos():
    """Con un solo partido completo el estimador tiene que acertar exacto, y un suplente no puede sumar nada."""
    titularidades = pd.Series([1, 1, 20, 0])
    noventas = pd.Series([1.0, 1.0, 20.0, 5.0])
    recibidos = pd.Series([0.0, 3.0, 20.0, 0.0])
    est = fantasy.porterias_cero_estimadas(titularidades, noventas, recibidos)
    assert est.iloc[0] == pytest.approx(1.0)      # jugó un partido y no recibió gol -> 1 portería a cero
    assert est.iloc[1] == pytest.approx(0.0)      # jugó un partido y recibió 3 -> 0
    assert est.iloc[2] == pytest.approx(20 * (19 / 20) ** 20)   # 20 partidos, 1 gol por partido
    assert est.iloc[3] == pytest.approx(0.0)      # nunca fue titular: no cumple la regla de los 60 minutos
    assert np.isnan(fantasy.porterias_cero_estimadas(pd.Series([10]), pd.Series([10.0]), pd.Series([np.nan])).iloc[0])


def test_puntos_defensivos_portero_del_mini_panel(ruta_mini_panel, carpeta_raw):
    """Portero Uno: 30 partidos, 2,700 minutos, 25 goles recibidos, 75 paradas, 10 porterías a cero, penales sin dato."""
    jt = plantillas.cargar_jugadores_temporada(ruta_mini_panel, carpeta_raw=carpeta_raw)
    jt = fantasy.puntos_defensivos(fantasy.puntos_fantasy(jt)).set_index("player")
    p = jt.loc["Portero Uno"]
    assert p["porterias_cero"] == 10                                   # la REAL, no la estimada
    assert p["pts_porteria_cero"] == pytest.approx(40)                 # 4 pts por portería a cero
    assert p["pts_paradas"] == pytest.approx(30 * fantasy.esperanza_piso(np.array([75 / 30]), 3)[0])
    assert p["pts_goles_recibidos"] == pytest.approx(-30 * fantasy.esperanza_piso(np.array([25 / 30]), 2)[0])
    assert np.isnan(p["pts_penales_atajados"])                         # FBref no publica penales atajados aquí
    assert not p["def_completo"]                                       # por eso su temporada no es comparable
    assert p["pts_total_completo"] == pytest.approx(p["pts_total"] + p["pts_defensivos"])


def test_puntos_defensivos_no_alteran_al_delantero(ruta_mini_panel, carpeta_raw):
    """Un delantero no cobra ni paga nada defensivo (regla de FPL), y sin datos en cancha queda marcado incompleto."""
    jt = plantillas.cargar_jugadores_temporada(ruta_mini_panel, carpeta_raw=carpeta_raw)
    jt = fantasy.puntos_defensivos(fantasy.puntos_fantasy(jt))
    raul = jt[(jt["player"] == "Raúl Pérez") & (jt["birth_year"] == 1998)].iloc[0]
    assert raul["pos_principal"] == "FW"
    assert raul["pts_defensivos"] == 0 and raul["pts_total_completo"] == raul["pts_total"]
    assert raul["def_completo"]                                        # sí tiene goles recibidos en cancha
    pedro = jt[jt["player"] == "Pedro Vacío"].iloc[0]
    assert not pedro["def_completo"] and np.isnan(pedro["porterias_cero"])


def test_validar_porterias_cero_devuelve_el_banco_de_pruebas(ruta_mini_panel, carpeta_raw):
    """La validación compara la estimación contra la verdad de los porteros; con un solo portero, una fila y el total."""
    filas = plantillas.unir_tablas_extra(
        plantillas.limpiar_panel(plantillas.cargar_panel_crudo(ruta_mini_panel)), carpeta_raw)
    val = fantasy.validar_porterias_cero(filas)
    assert val.loc["TODOS", "porteros"] == 1 and val.loc["TODOS", "real"] == 10
    assert val.loc["TODOS", "estimada"] == pytest.approx(30 * (29 / 30) ** 25)


# --- Temporada en curso (Fase 24) -------------------------------------------------------------------------------

def test_edad_en_anios_aguanta_los_dos_formatos():
    """FBref da años enteros en las temporadas cerradas y "años-días" en la que está en curso."""
    e = plantillas.edad_en_anios(pd.Series(["29", "29.0", "30-284", "23-024", None, ""]))
    assert list(e[:4]) == [29, 29, 30, 23]      # de "30-284" se queda con los años
    assert e[4:].isna().all()


def test_temporada_parcial_marca_la_que_esta_en_curso():
    """Una temporada de 5 jornadas se marca; una acortada pero TERMINADA (COVID) no."""
    def fila(season, games, minutes):
        return {"league": "Liga MX", "season": season, "player": f"j{games}{minutes}", "team": "A",
                "nationality": "mx MEX", "position": "FW", "age": "25", "birth_year": 1999, "games": games,
                "games_starts": games, "minutes": minutes, "minutes_90s": minutes / 90, "goals": 0, "assists": 0,
                "goals_assists": 0, "goals_pens": 0, "pens_made": 0, "pens_att": 0, "cards_yellow": 0,
                "cards_red": 0, "player_id": f"aaaa{games:04d}", "team_id": "0e000001", "ranker": 1}
    d = plantillas.limpiar_panel(pd.DataFrame([
        fila("2023-2024", 34, 3060),     # temporada normal de la liga
        fila("2019-2020", 27, 2430),     # acortada por COVID pero jugada: 79% -> NO se marca
        fila("2026-2027", 5, 450),       # en curso: 15% -> se marca
    ]))
    marcadas = set(d.loc[d["temporada_parcial"], "season"])
    assert marcadas == {"2026-2027"}
