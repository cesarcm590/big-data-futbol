"""
Une los identificadores de FBref (player_id, team_id) al panel de plantillas.

    python scripts/unir_ids_fbref.py

Entrada
  data/raw/fbref_ids/fbref_ids_panel_2010_2026.json
      Extraído el 2026-09-19 desde el navegador del usuario con la lógica de `scripts/fbref_extraer_tabla.js`: las 112
      tablas liga-temporada del panel, pedidas de nuevo a FBref. Por página:
        n, firma   número de filas y huella (FNV-1a de "jugador|equipo|partidos|minutos" de todas las filas, en orden)
        ok         True si la firma es IDÉNTICA a la del CSV del panel -> FBref no cambió nada en esa tabla
        pids       ids de jugador en el orden de la tabla;  equipos: nombre -> id de equipo
        filas      solo si ok = False: [jugador, equipo, partidos, minutos, player_id, team_id] por fila
  data/raw/fbref_historical/*.csv   el panel tal como se scrapeó en agosto (no se modifica)

Salida
  data/processed/fbref_panel_2010_2025.csv   el mismo panel, fila por fila, con dos columnas nuevas al final:
      player_id, team_id. Si el script se corre otra vez, reemplaza esas dos columnas (es idempotente).

Cómo se alinea cada fila del panel con su fila de FBref
  - Páginas ok (90 de 112): por posición. La firma garantiza que la tabla es la misma, fila por fila.
  - Páginas con diferencias (22): FBref cambió algo desde agosto. Se revisaron las 22 una por una y solo hay tres
    tipos de cambio, ninguno en los números:
      1. renombró un equipo: "PSG" -> "Paris SG" (las 16 temporadas de la Ligue 1);
      2. renombró un jugador: "Ben Brereton" -> "Ben Brereton Díaz" (3 filas);
      3. invirtió el orden de las dos filas de un jugador que jugó en dos equipos esa temporada (18 filas).
    Por eso el emparejamiento es en dos pasos: (a) por contenido exacto (jugador, equipo, partidos, minutos), que
    resuelve los órdenes invertidos; (b) lo que quede, por posición exigiendo mismos partidos y minutos, que resuelve
    los renombres. Si alguna fila no se pudiera emparejar, el script se detiene y la muestra (no inventa ids).
"""
import json
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
RUTA_IDS = RAIZ / "data" / "raw" / "fbref_ids" / "fbref_ids_panel_2010_2026.json"
CARPETA_RAW = RAIZ / "data" / "raw" / "fbref_historical"
RUTA_PANEL = RAIZ / "data" / "processed" / "fbref_panel_2010_2025.csv"

CONTENIDO = ["player", "team", "games", "minutes"]


def firma(filas: pd.DataFrame) -> str:
    """Misma huella FNV-1a de 32 bits que calculó el navegador, para confirmar que la página es idéntica."""
    texto = "\n".join("|".join(r) for r in filas[CONTENIDO].itertuples(index=False, name=None))
    h = 0x811C9DC5
    for byte in texto.encode("utf-8"):
        h = ((h ^ byte) * 0x01000193) & 0xFFFFFFFF
    return f"{h:08x}"


def ids_de_pagina(raw: pd.DataFrame, pagina: dict) -> pd.DataFrame:
    """Devuelve `raw` con player_id y team_id, alineado según el tipo de página (ver docstring del módulo)."""
    if pagina["ok"]:
        if firma(raw) != pagina["firma"]:
            raise ValueError("la firma guardada no coincide con el CSV: el archivo raw cambió después de la extracción")
        pids = pagina["pids"].split()
        return raw.assign(player_id=pids, team_id=raw["team"].map(pagina["equipos"]))

    web = pd.DataFrame(pagina["filas"], columns=CONTENIDO + ["player_id", "team_id"])
    raw = raw.assign(_pos=range(len(raw)), player_id=pd.NA, team_id=pd.NA)
    web = web.assign(_pos=range(len(web)), _usada=False)

    # (a) Contenido exacto. `_rep` numera repeticiones del mismo contenido para que dos filas idénticas (no pasa en las
    # páginas con diferencias, pero es gratis protegerse) se emparejen una a una y no en producto cruzado.
    raw["_rep"] = raw.groupby(CONTENIDO).cumcount()
    web["_rep"] = web.groupby(CONTENIDO).cumcount()
    exacto = raw.reset_index().merge(web, on=CONTENIDO + ["_rep"], suffixes=("", "_web")).set_index("index")
    raw.loc[exacto.index, ["player_id", "team_id"]] = exacto[["player_id_web", "team_id_web"]].to_numpy()
    web.loc[web["_pos"].isin(exacto["_pos_web"]), "_usada"] = True

    # (b) Lo que queda: misma posición, mismos partidos y minutos (el nombre del equipo o del jugador cambió).
    for i in raw.index[raw["player_id"].isna()]:
        w = web.iloc[raw.at[i, "_pos"]]
        if not w["_usada"] and (w["games"], w["minutes"]) == (raw.at[i, "games"], raw.at[i, "minutes"]):
            raw.loc[i, ["player_id", "team_id"]] = [w["player_id"], w["team_id"]]
            web.at[w.name, "_usada"] = True

    sin_pareja = raw[raw["player_id"].isna()]
    if len(sin_pareja):
        raise ValueError(f"{len(sin_pareja)} filas sin pareja:\n{sin_pareja[CONTENIDO].head(10)}")
    return raw.drop(columns=["_pos", "_rep"])


def main():
    paginas = json.loads(RUTA_IDS.read_text())
    partes, resumen = [], {"por posición (idénticas)": 0, "con diferencias": 0}
    for clave, pagina in sorted(paginas.items()):
        raw = pd.read_csv(CARPETA_RAW / f"{clave}.csv", dtype=str, keep_default_na=False)
        if len(raw) != pagina["n"]:
            raise ValueError(f"{clave}: el panel tiene {len(raw)} filas y FBref {pagina['n']}")
        con_ids = ids_de_pagina(raw, pagina)
        partes.append(con_ids[["league", "season", "ranker", "player_id", "team_id"]])
        resumen["por posición (idénticas)" if pagina["ok"] else "con diferencias"] += 1
    ids = pd.concat(partes, ignore_index=True)

    # El panel procesado es exactamente la concatenación de los 112 CSV (verificado: mismas 61,542 filas y contenido),
    # así que (liga, temporada, ranker) identifica cada fila en ambos lados.
    panel = pd.read_csv(RUTA_PANEL, dtype=str, keep_default_na=False)
    panel = panel.drop(columns=[c for c in ("player_id", "team_id") if c in panel.columns])
    unido = panel.merge(ids, on=["league", "season", "ranker"], how="left", validate="one_to_one")
    faltan = unido["player_id"].isna().sum() + unido["team_id"].isna().sum()
    if len(unido) != len(panel) or faltan:
        raise ValueError(f"unión incompleta: {len(unido)} de {len(panel)} filas, {faltan} ids vacíos")
    unido.to_csv(RUTA_PANEL, index=False)

    print(f"Páginas: {resumen}")
    print(f"Panel: {len(unido):,} filas, {unido['player_id'].nunique():,} jugadores y "
          f"{unido['team_id'].nunique():,} equipos distintos según FBref -> {RUTA_PANEL.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
