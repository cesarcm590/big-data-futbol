"""Pruebas del parseo de CAF desde Wikipedia (Fase 35). No tocan la red: usan wikitexto de ejemplo.

Cada prueba corresponde a un fallo REAL que se cometió al construirlo, no a un caso hipotético.
"""
import pandas as pd

from futbol_bd import caf_wikipedia as caf

WIKI = """{{Infobox international football competition
|matches      = 4
|goals        = 9
|updated      = 13 September 2026
}}
{{#invoke:Sports series|main
|[[Wiliete S.C.|Wiliete]]|ANG|5–0|[[Foresters Mont Fleuri FC|Foresters]]|SEY|[[Art#FR01.1|4–0]]|[[Art#FR01.2|1–0]]
|[[UD Songo]]|MOZ|2–3|[[Atlético Petróleos de Luanda|Petro de Luanda]]|ANG|[[Art#FR03.1|0-1]]|[[Art#FR03.2|2-2]]
|[[15 de Agosto]]|EQG|FR6|[[Fomboni FC|Fomboni]]|COM|[[Art#FR06.1|4–0]]|[[Art#FR06.2|3 October]]
|FR6 winner||SR4|[[Simba S.C.|Simba]]|TAN|[[Art#SR04.1|{{small|16–18 Oct}}]]|[[Art#SR04.2|{{small|23–25 Oct}}]]
}}
"""


def test_parte_los_campos_sin_romperse_con_los_enlaces():
    """Un enlace [[destino|texto]] lleva su propio `|`: un split('|') a secas desalinea la fila entera.

    Ese fue el fallo original y dejaba 2 partidos de 57.
    """
    campos = caf._partir_campos("|[[A|a]]|ANG|5–0|[[B|b]]|SEY|[[L|4–0]]|[[L|1–0]]")
    assert campos == ["[[A|a]]", "ANG", "5–0", "[[B|b]]", "SEY", "[[L|4–0]]", "[[L|1–0]]"]


def test_acepta_los_dos_guiones_que_usa_wikipedia():
    """Unos editores escriben 0–1 (guion largo) y otros 0-1 (normal). Aceptar solo uno perdía 8 partidos."""
    assert caf._marcador("[[Art#X|4–0]]") == (4, 0)      # largo
    assert caf._marcador("[[Art#X|0-1]]") == (0, 1)      # normal
    assert caf._marcador("1–1 ([[Penalty shootout|p]])") == (1, 1)   # con nota entre paréntesis


def test_no_confunde_una_fecha_con_un_marcador():
    """Un partido sin jugar muestra la fecha. Leerlo como 0-0 inventaría un resultado."""
    assert caf._marcador("[[Art#X|3 October]]") == (None, None)
    assert caf._marcador("[[Art#X|{{small|16–18 Oct}}]]") == (None, None)
    assert caf._marcador("FR6") == (None, None)


def test_la_vuelta_invierte_los_equipos():
    d = caf.parsear_eliminatorias(WIKI, "Previas")
    ida = d[(d["local"] == "Wiliete") & (d["partido"] == "Ida")].iloc[0]
    vuelta = d[(d["visitante"] == "Wiliete") & (d["partido"] == "Vuelta")].iloc[0]
    assert (ida["goles_local"], ida["goles_visitante"]) == (4, 0)
    assert vuelta["local"] == "Foresters" and (vuelta["goles_local"], vuelta["goles_visitante"]) == (1, 0)


def test_solo_cuenta_como_jugado_lo_que_tiene_marcador():
    d = caf.parsear_eliminatorias(WIKI, "Previas")
    assert int(d["jugado"].sum()) == 5     # 2+2 de las dos primeras eliminatorias y la ida de la tercera
    sin_jugar = d[~d["jugado"]]
    assert sin_jugar["goles_local"].isna().all()


def test_el_control_compara_contra_lo_que_dice_el_propio_articulo():
    """Es la red de seguridad: si Wikipedia cambia de formato, el parseo falla en silencio y esto lo canta."""
    d = caf.parsear_eliminatorias(WIKI, "Previas")
    c = caf.control_contra_infobox(WIKI, d)
    assert c["partidos_segun_wikipedia"] == 4 and c["goles_segun_wikipedia"] == 9
    assert c["infobox_actualizado"] == "13 September 2026"
    assert c["partidos_parseados"] == 5      # el ejemplo no cuadra a propósito
    assert c["cuadra"] is False
