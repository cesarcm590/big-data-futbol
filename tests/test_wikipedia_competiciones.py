"""Pruebas del parseo de CAF desde Wikipedia (Fase 35). No tocan la red: usan wikitexto de ejemplo.

Cada prueba corresponde a un fallo REAL que se cometió al construirlo, no a un caso hipotético.
"""
import pandas as pd

from futbol_bd import wikipedia_competiciones as caf

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


# --- Football box, el otro formato (Fase 37) --------------------------------------------------------------------

BOX = """{{Infobox football tournament
|matches = 2
|goals   = 7
}}
{{Football box
|date       = {{Start date|2026|2|3|df=y}}
|team1      = [[San Diego FC]] {{fbaicon|USA}}
|score      = 4–1
|team2      = {{fbaicon|MEX}} [[Pumas UNAM]]
|stadium    = [[Snapdragon Stadium]]
}}
{{Football box
|date       = {{Start date|2026|2|10|df=y}}
|team1      = {{fbaicon|MEX}} [[Club América|América]]
|score      = 2–0
|team2      = [[Toronto FC]] {{fbaicon|CAN}}
|stadium    = [[Estadio Azteca]]
}}
"""


def test_football_box_lee_fecha_equipos_y_paises():
    d = caf.parsear_football_box(BOX, "Torneo")
    assert len(d) == 2 and d["jugado"].all()
    p = d.iloc[0]
    assert p["fecha"] == "2026-02-03"
    assert p["local"] == "San Diego FC" and p["visitante"] == "Pumas UNAM"
    assert p["local_pais"] == "USA" and p["visitante_pais"] == "MEX"
    assert (p["goles_local"], p["goles_visitante"]) == (4, 1)


def test_football_box_saca_el_nombre_mostrado_no_el_destino_del_enlace():
    """'[[Club América|América]]' debe dar 'América', no 'Club América'."""
    d = caf.parsear_football_box(BOX, "Torneo")
    assert d.iloc[1]["local"] == "América"


def test_el_control_distingue_sin_control_de_no_cuadra():
    """Son cosas distintas: una es que no cuadre, la otra que no haya NADA contra lo que contrastar."""
    d = caf.parsear_football_box(BOX, "Torneo")
    # El ejemplo declara 2 partidos y 7 goles, y hay exactamente eso: es el caso feliz.
    assert caf.control_contra_infobox(BOX, d)["control"] == "cuadra"
    sin_infobox = BOX.split("{{Football box", 1)[1]
    d2 = caf.parsear_football_box("{{Football box" + sin_infobox, "Torneo")
    assert caf.control_contra_infobox("{{Football box" + sin_infobox, d2)["control"] == "sin control"


def test_protege_tambien_las_plantillas_no_solo_los_enlaces():
    """El resultado global puede llevar {{pso|3–5}} cuando se decidió por penales.

    Ese `|` dentro de la plantilla partía el campo y corría el nombre del rival al sitio del marcador: la tabla
    mostraba «3–5}} 2-1 The Strongest» como si fuera un equipo. Apareció con la Libertadores, no con CAF.
    """
    linea = "|[[The Strongest]]|BOL|2–2 {{pso|3–5}}|[[Deportivo Táchira F.C.|Deportivo Táchira]]|VEN|[[A|2–1]]|[[A|0–1]]"
    campos = caf._partir_campos(linea)
    assert campos[0] == "[[The Strongest]]"
    assert campos[2] == "2–2 {{pso|3–5}}"          # el global entero, sin partir
    assert campos[3] == "[[Deportivo Táchira F.C.|Deportivo Táchira]]"
    assert len(campos) == 7


# --- Transclusiones: el fallo que dejaba la Concacaf en 50 de 51 (Fase 39) ---------------------------------------

CON_TRANSCLUSION = """{{Infobox international football competition
|matches = 2
|goals   = 5
}}
{{Football box
|date  = {{Start date|2026|5|20|df=y}}
|team1 = [[Tigres UANL]]
|score = 3–0
|team2 = [[Cruz Azul]]
}}

==Final==
{{main|La final}}
===Match===
{{:La final}}
"""

FINAL_APARTE = """{{Football box
|date  = {{Start date|2026|5|30|df=y}}
|team1 = [[Toluca FC|Toluca]]
|score = 1–1
|team2 = [[Tigres UANL]]
|aet   = yes
}}
"""


def _descarga_falsa(titulo):
    """Sustituye a la red en las pruebas: solo conoce «La final»."""
    if titulo == "La final":
        return FINAL_APARTE, 1374756423, "2026-09-13"
    raise LookupError(titulo)


def test_un_partido_transcluido_de_otro_articulo_se_pierde_si_no_se_expande():
    """Este es el fallo tal cual: el parseo no da error, da un partido menos, y el control lo canta.

    Era la final de la Concacaf (Toluca 1–1 Tigres): 50 partidos de 51 y 147 goles de 149, justo esos 2.
    """
    d = caf.parsear_football_box(CON_TRANSCLUSION, "Torneo")
    assert len(d) == 1                                                  # falta la final
    assert caf.control_contra_infobox(CON_TRANSCLUSION, d)["control"] == "no cuadra"


def test_al_expandir_la_transclusion_el_control_cuadra():
    txt, incrustados = caf.resolver_transclusiones(CON_TRANSCLUSION, descargar=_descarga_falsa)
    d = caf.parsear_football_box(txt, "Torneo")
    assert len(d) == 2 and d["jugado"].all()
    c = caf.control_contra_infobox(txt, d)
    assert c["partidos_parseados"] == 2 and c["goles_parseados"] == 5
    assert c["control"] == "cuadra"
    # Se guarda la revisión de lo incrustado: la del artículo principal ya no basta para reproducir el parseo.
    assert incrustados["La final"]["revision"] == 1374756423


def test_no_confunde_un_vease_ni_una_plantilla_con_una_transclusion():
    """`{{main|X}}` no aporta contenido y `{{Plantilla|...}}` no es un artículo: tocar esos sería destrozar el texto."""
    txt, incrustados = caf.resolver_transclusiones(
        "{{main|La final}}\n{{Football box\n|score = 1–0\n}}\n", descargar=_descarga_falsa)
    assert incrustados == {} and "{{main|La final}}" in txt


def test_una_transclusion_a_un_articulo_que_no_existe_se_anota_y_no_rompe():
    """Un enlace rojo en Wikipedia. Debe quedar constancia, no una excepción a mitad de la actualización."""
    txt, incrustados = caf.resolver_transclusiones("{{:No existe}}\n", descargar=_descarga_falsa)
    assert txt.strip() == "" and "no existe" in incrustados["No existe"]["estado"]
