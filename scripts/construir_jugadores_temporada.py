"""
Construye EL dataset de jugadores del proyecto: una fila por jugador-liga-temporada, con todo lo que tenemos de FBref.

    python scripts/construir_jugadores_temporada.py

Entradas: data/processed/fbref_panel_2010_2025.csv       tabla estándar de las 112 liga-temporadas (+ ids de FBref)
          data/raw/fbref_playingtime/*.csv              minutos, banca, goles a favor/en contra con el jugador en cancha
          data/raw/fbref_keepers/*.csv                  estadísticas de portero
Salidas:  data/processed/jugadores_temporada_2010_2026.csv
              una fila por jugador-liga-temporada (traspasos dentro de la liga ya sumados). Se filtra por la columna
              `league` para analizar una liga. Al leerlo, forzar los ids a texto:
                  pd.read_csv(ruta, dtype={"id_jugador": str, "equipo_principal_id": str})
              porque muchos ids de FBref parecen números ("12345678", "1e345678") y pandas los corrompería.
          data/processed/jugadores_temporada_2010_2026_diccionario.csv
              qué es cada columna, de qué tabla viene y desde qué temporada existe el dato
          output/auditoria_panel_fbref.csv
              la tabla de chequeos de calidad (qué se encontró y qué se hizo con cada cosa)

Las celdas vacías significan "FBref no tiene ese dato para esa liga-temporada" (no cero). Toda la lógica vive en
`futbol_bd/` (probada en `tests/`); este script solo la encadena, ordena las columnas y guarda.
"""
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from futbol_bd import fantasy, plantillas  # noqa: E402  (después de ajustar sys.path)

SALIDA = RAIZ / "data" / "processed" / "jugadores_temporada_2010_2026.csv"
SALIDA_DICCIONARIO = RAIZ / "data" / "processed" / "jugadores_temporada_2010_2026_diccionario.csv"
SALIDA_AUDITORIA = RAIZ / "output" / "auditoria_panel_fbref.csv"

TODAS = "2010-11"
EN_CANCHA = "2014-15"

# columna: (bloque, fuente, desde, descripción). El orden de este diccionario es el orden de las columnas del CSV.
DICCIONARIO = {
    # --- Identidad y contexto ---
    "id_jugador": ("identidad", "FBref", TODAS, "id de jugador de FBref (con 2 perfiles duplicados unidos, ver ALIAS_FBREF)"),
    "player": ("identidad", "estándar", TODAS, "nombre (de la fila con más minutos)"),
    "id_provisional": ("identidad", "calculado", TODAS, "True si el jugador no tiene página en FBref (su id es el nombre)"),
    "league": ("contexto", "estándar", TODAS, "liga"),
    "season": ("contexto", "estándar", TODAS, "temporada ('2024-2025'); Liga MX = Apertura + Clausura, fase regular"),
    "temporada_inicio": ("contexto", "calculado", TODAS, "año de inicio de la temporada (2024)"),
    "partidos_liga": ("contexto", "calculado", TODAS, "jornadas de la liga-temporada (máximo de partidos de alguien)"),
    "temporada_parcial": ("contexto", "calculado", TODAS, "¿temporada en curso? (menos del 60% de las jornadas habituales de su liga; las series por temporada la excluyen)"),
    "equipo_principal": ("contexto", "estándar", TODAS, "equipo en el que jugó más minutos"),
    "equipo_principal_id": ("contexto", "FBref", TODAS, "id de FBref de ese equipo"),
    "equipos": ("contexto", "estándar", TODAS, "todos sus equipos en la liga esa temporada, de más a menos minutos"),
    "n_equipos": ("contexto", "calculado", TODAS, "número de equipos (2+ = traspaso a mitad de temporada)"),
    "position": ("contexto", "estándar", TODAS, "posiciones según FBref ('FW,MF'), ordenadas por uso"),
    "pos_principal": ("contexto", "calculado", TODAS, "primera posición: GK, DF, MF, FW (ND si falta)"),
    "age": ("contexto", "estándar", TODAS, "edad al inicio de la temporada"),
    "birth_year": ("contexto", "estándar", TODAS, "año de nacimiento (vacío en 92 filas)"),
    "nacionalidad": ("contexto", "estándar", TODAS, "código de país de 3 letras"),
    # --- Tabla estándar: participación y producción ---
    "games": ("estándar", "estándar", TODAS, "partidos jugados"),
    "games_starts": ("estándar", "estándar", TODAS, "partidos como titular"),
    "minutes": ("estándar", "estándar", TODAS, "minutos"),
    "minutes_90s": ("estándar", "calculado", TODAS, "minutos / 90"),
    "pct_minutos": ("estándar", "calculado", TODAS, "minutos / (jornadas × 90): proporción de lo posible que jugó"),
    "goals": ("estándar", "estándar", TODAS, "goles"),
    "assists": ("estándar", "estándar", TODAS, "asistencias"),
    "goals_assists": ("estándar", "calculado", TODAS, "goles + asistencias"),
    "goals_pens": ("estándar", "calculado", TODAS, "goles sin contar penales"),
    "pens_made": ("estándar", "estándar", TODAS, "penales anotados"),
    "pens_att": ("estándar", "estándar", TODAS, "penales tirados"),
    "cards_yellow": ("estándar", "estándar", TODAS, "amarillas"),
    "cards_red": ("estándar", "estándar", TODAS, "rojas"),
    "goals_per90": ("estándar", "calculado", TODAS, "goles por 90 (poco fiable con < 900 minutos)"),
    "assists_per90": ("estándar", "calculado", TODAS, "asistencias por 90"),
    "goals_assists_per90": ("estándar", "calculado", TODAS, "goles + asistencias por 90"),
    "goals_pens_per90": ("estándar", "calculado", TODAS, "goles sin penal por 90"),
    "goals_assists_pens_per90": ("estándar", "calculado", TODAS, "goles sin penal + asistencias por 90"),
    # --- playingtime: rol y lo que pasa con el jugador en cancha ---
    "games_complete": ("playingtime", "playingtime", EN_CANCHA, "partidos completos (90 minutos)"),
    "games_subs": ("playingtime", "playingtime", EN_CANCHA, "partidos entrando de cambio"),
    "unused_subs": ("playingtime", "playingtime", EN_CANCHA, "partidos en la banca sin entrar"),
    "points_per_game": ("playingtime", "playingtime", EN_CANCHA, "puntos por partido de su equipo cuando jugó"),
    "on_goals_for": ("playingtime", "playingtime", EN_CANCHA, "goles de su equipo con él en cancha"),
    "on_goals_against": ("playingtime", "playingtime", EN_CANCHA, "goles recibidos por su equipo con él en cancha (onGA)"),
    "plus_minus": ("playingtime", "calculado", EN_CANCHA, "on_goals_for − on_goals_against"),
    "on_goals_against_per90": ("playingtime", "calculado", EN_CANCHA, "onGA por 90 minutos"),
    "plus_minus_wowy": ("playingtime", "playingtime", EN_CANCHA,
                        "on-off: goles netos por 90 con él menos sin él (promedio ponderado por minutos si tuvo 2 equipos)"),
    # --- keepers: solo porteros (vacío para los demás) ---
    "gk_games": ("keepers", "keepers", TODAS, "partidos como portero"),
    "gk_games_starts": ("keepers", "keepers", TODAS, "titularidades como portero"),
    "gk_minutes": ("keepers", "keepers", TODAS, "minutos como portero"),
    "gk_goals_against": ("keepers", "keepers", TODAS,
                         "goles recibidos (en ~6% de los porteros difiere de onGA; hay casos grandes, p. ej. Wiedwald 2015-16)"),
    "gk_shots_on_target_against": ("keepers", "keepers", TODAS, "tiros a puerta recibidos (vacío en Liga MX y Eredivisie 2018-19)"),
    "gk_saves": ("keepers", "keepers", TODAS, "paradas (vacío en Liga MX y Eredivisie 2018-19)"),
    "gk_save_pct": ("keepers", "calculado", TODAS, "paradas / tiros a puerta recibidos × 100"),
    "gk_clean_sheets": ("keepers", "keepers", TODAS, "porterías a cero"),
    "gk_clean_sheets_pct": ("keepers", "calculado", TODAS, "porterías a cero / partidos como portero × 100"),
    "gk_wins": ("keepers", "keepers", TODAS, "partidos ganados como portero"),
    "gk_ties": ("keepers", "keepers", TODAS, "empatados"),
    "gk_losses": ("keepers", "keepers", TODAS, "perdidos"),
    "gk_pens_att": ("keepers", "keepers", "2016-17", "penales en contra (La Liga desde 2015-16)"),
    "gk_pens_allowed": ("keepers", "keepers", "2016-17", "penales recibidos (gol)"),
    "gk_pens_saved": ("keepers", "keepers", "2016-17", "penales atajados"),
    "gk_pens_missed": ("keepers", "keepers", "2016-17", "penales fallados por el rival (fuera o al poste)"),
    # --- Fantasy ofensivo (FPL adaptado; ver futbol_bd/fantasy.py) ---
    "pts_aparicion": ("fantasy", "calculado", TODAS, "titular 2, suplente 1"),
    "pts_goles": ("fantasy", "calculado", TODAS, "gol: POR/DEF 6, MED 5, DEL 4"),
    "pts_asistencias": ("fantasy", "calculado", TODAS, "asistencia 3"),
    "pts_tarjetas": ("fantasy", "calculado", TODAS, "amarilla −1, roja −3"),
    "pts_penales": ("fantasy", "calculado", TODAS, "penal fallado −2"),
    "pts_total": ("fantasy", "calculado", TODAS, "suma de lo ofensivo y la disciplina (sin nada defensivo)"),
    "pts_por_jornada": ("fantasy", "calculado", TODAS, "pts_total / jornadas de la liga-temporada"),
    "pts_por90": ("fantasy", "calculado", TODAS, "pts_total por 90 minutos"),
    "pct_pts_jornada": ("fantasy", "calculado", TODAS, "percentil de pts_por_jornada en liga-temporada-posición (900+ min)"),
    "pct_pts_por90": ("fantasy", "calculado", TODAS, "percentil de pts_por90 en liga-temporada-posición (900+ min)"),
    # Mitad defensiva del fantasy (Fase 21). Reales en porteros; en jugadores de campo la portería a cero es una
    # ESTIMACIÓN a partir de los goles recibidos con él en cancha (validada contra porteros, ver futbol_bd/fantasy.py).
    "porterias_cero": ("fantasy", "calculado", EN_CANCHA, "porterías a cero: reales en porteros, estimadas en el resto"),
    "pts_porteria_cero": ("fantasy", "calculado", EN_CANCHA, "portería a cero: POR/DEF 4, MED 1, DEL 0"),
    "pts_goles_recibidos": ("fantasy", "calculado", EN_CANCHA, "−1 por cada 2 goles recibidos en cancha (POR y DEF)"),
    "pts_paradas": ("fantasy", "calculado", TODAS, "+1 por cada 3 paradas (solo porteros)"),
    "pts_penales_atajados": ("fantasy", "calculado", "2016-17", "+5 por penal atajado (solo porteros)"),
    "pts_defensivos": ("fantasy", "calculado", EN_CANCHA, "suma de los cuatro anteriores"),
    "pts_total_completo": ("fantasy", "calculado", EN_CANCHA, "pts_total + pts_defensivos: el fantasy comparable entre posiciones"),
    "pts_completo_por_jornada": ("fantasy", "calculado", EN_CANCHA, "pts_total_completo / jornadas de la liga-temporada"),
    "def_completo": ("fantasy", "calculado", EN_CANCHA, "¿existían TODOS los datos defensivos de su posición? filtrar por aquí antes de comparar"),
    "pct_pts_completo": ("fantasy", "calculado", EN_CANCHA, "percentil de pts_completo_por_jornada en liga-temporada-posición (900+ min)"),
}


def main():
    crudo = plantillas.cargar_panel_crudo()
    auditoria = plantillas.auditar_panel(crudo)
    auditoria.to_csv(SALIDA_AUDITORIA, index=False)

    limpio = plantillas.limpiar_panel(crudo)
    pendientes = plantillas.detectar_colisiones(limpio)
    jt = fantasy.puntos_fantasy(plantillas.agregar_por_temporada(plantillas.unir_tablas_extra(limpio)))
    jt["pct_pts_jornada"] = fantasy.percentil_en_grupo(jt, "pts_por_jornada")
    jt["pct_pts_por90"] = fantasy.percentil_en_grupo(jt, "pts_por90")
    jt = fantasy.puntos_defensivos(jt)
    jt["pct_pts_completo"] = fantasy.percentil_completo(jt)

    faltan = set(jt.columns) ^ set(DICCIONARIO)
    if faltan:
        raise ValueError(f"el diccionario y el dataset no tienen las mismas columnas: {sorted(faltan)}")
    # 4 decimales bastan para tasas por 90 y percentiles, y reducen el archivo a la mitad frente a la precisión completa.
    jt[list(DICCIONARIO)].round(4).to_csv(SALIDA, index=False)
    pd.DataFrame([{"columna": c, "bloque": b, "fuente": f, "desde": d, "descripcion": t}
                  for c, (b, f, d, t) in DICCIONARIO.items()]).to_csv(SALIDA_DICCIONARIO, index=False)

    print(f"Panel crudo: {len(crudo):,} filas (jugador-equipo-temporada)")
    print(f"Auditoría:   {len(auditoria)} chequeos -> {SALIDA_AUDITORIA.relative_to(RAIZ)}")
    for _, r in auditoria[auditoria["tipo"] == "error"].iterrows():
        print(f"  - {r['chequeo']}: {r['casos']} ({r['accion']})")
    print(f"Colisiones de identidad sin resolver: {len(pendientes)}")
    print(f"Salida:      {len(jt):,} filas × {len(DICCIONARIO)} columnas, {jt['id_jugador'].nunique():,} jugadores "
          f"-> {SALIDA.relative_to(RAIZ)}")
    print(f"Diccionario: {SALIDA_DICCIONARIO.relative_to(RAIZ)}")
    if len(pendientes):
        print("\nRevisar a mano (posibles homónimos fusionados):")
        print(pendientes.to_string(index=False))


if __name__ == "__main__":
    main()
