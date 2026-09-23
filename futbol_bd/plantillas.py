"""
Panel de plantillas de FBref: carga, auditoría y limpieza.

Qué es el panel
---------------
`data/processed/fbref_panel_2010_2025.csv` junta las 112 tablas "Standard Stats" de jugadores que se extrajeron de FBref
con el navegador (PLAN_DE_TRABAJO.md, "Intento de dataset panel histórico"): 7 ligas (Premier League, La Liga, Serie A,
Bundesliga, Ligue 1, Eredivisie, Liga MX) × 16 temporadas (2010-11 a 2025-26). Cada fila es un jugador EN UN EQUIPO
en una liga-temporada. Solo trae estadística básica: partidos, titularidades, minutos, goles, asistencias, penales y
tarjetas (FBref perdió las columnas avanzadas — xG, pases, acciones defensivas — ver Fase 7).

Desde el 2026-09-19 el panel trae además `player_id` y `team_id`, los identificadores de FBref, agregados por
`scripts/unir_ids_fbref.py` (las 112 tablas se volvieron a pedir a FBref y se verificó fila por fila que fueran las
mismas; ver ese script).

Por qué hace falta este módulo
------------------------------
1. Identidad. El nombre no identifica a nadie (176 nombres del panel son 2+ personas; 98 veces el mismo nombre aparece
   con dos años de nacimiento en la MISMA liga-temporada). El id de jugador es el de FBref, con dos correcciones
   verificadas a mano (`ALIAS_FBREF`): FBref tiene a dos jugadores con perfil duplicado. Antes de tener los ids se usó
   una clave nombre + año de nacimiento + nacionalidad (`clave_por_nombre`); al comparar, esa clave nunca partió a una
   persona en dos, pero juntaba a 4 pares de personas distintas (Vitinha, Fernandinho, Adriano, Borja García). Se
   conserva solo para esa comparación en la auditoría y como respaldo si alguna vez falta el id.
2. Un jugador que cambia de equipo a mitad de temporada DENTRO de la misma liga aparece en 2 filas (una por equipo).
   Para "su temporada" hay que sumarlas → `agregar_por_temporada`.
3. Errores puntuales de la fuente: una fila duplicada, minutos vacíos, asistencias vacías, columnas derivadas (G+A,
   goles sin penal) que no cuadran con sus componentes, un penal anotado sin intento registrado. Son pocos, pero una
   sola fila rota basta para romper un cálculo agregado → `limpiar_panel` los corrige y `auditar_panel` los reporta.
4. La temporada 2019-20 se cortó por COVID en Eredivisie (26 jornadas), Ligue 1 (28) y Liga MX (Clausura 2020
   cancelado). Los totales de esa temporada no son comparables con los de otras → se guarda `partidos_liga` (máximo de
   partidos jugados por alguien en esa liga-temporada) para normalizar.

La limpieza produce un DataFrame nuevo; el script `scripts/construir_jugadores_temporada.py` lo guarda como CSV aparte.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
RUTA_PANEL = RAIZ / "data" / "processed" / "fbref_panel_2010_2025.csv"

# Los ids de FBref se leen SIEMPRE como texto: 1,482 ids de jugador son solo dígitos y 779 tienen forma de notación
# científica ("1e345678"). Si pandas los adivina como números, pierde ceros a la izquierda o los convierte en infinito.
TIPOS_ID = {"player_id": "string", "team_id": "string", "age": "string"}  # `age` cambia de formato: ver `edad_en_anios`

# Conteos "crudos": lo que FBref cuenta directamente. Todo lo demás (G+A, goles sin penal, minutos/90, tasas por 90)
# es DERIVADO de estas columnas y se recalcula aquí en vez de confiar en la columna scrapeada — la auditoría encontró
# 33 filas con G+A vacío y 3 con goles-sin-penal vacío aunque sus componentes sí estaban.
CONTEOS = ["games", "games_starts", "minutes", "goals", "assists", "pens_made", "pens_att", "cards_yellow", "cards_red"]

# Tablas extra de FBref (extraídas el 2026-09-19, un CSV por liga-temporada en data/raw/fbref_<tabla>/). Solo se traen
# los CONTEOS; las tasas y porcentajes de FBref (minutos %, +/- por 90, % de paradas...) se recalculan después de sumar
# los equipos de un jugador, porque promediar porcentajes de dos equipos da un número que no significa nada.
CARPETA_RAW = RAIZ / "data" / "raw"
SUMAS_PLAYINGTIME = ["games_complete", "games_subs", "unused_subs", "on_goals_for", "on_goals_against"]
SUMAS_KEEPERS = ["gk_games", "gk_games_starts", "gk_minutes", "gk_goals_against", "gk_shots_on_target_against",
                 "gk_saves", "gk_wins", "gk_ties", "gk_losses", "gk_clean_sheets", "gk_pens_att", "gk_pens_allowed",
                 "gk_pens_saved", "gk_pens_missed"]
# Dos tasas de playingtime no se pueden reconstruir desde conteos y se promedian ponderando (ver agregar_por_temporada):
#   points_per_game   puntos por partido del equipo con el jugador en cancha  -> ponderado por partidos
#   plus_minus_wowy   "on-off": goles netos por 90 con él menos sin él         -> ponderado por minutos
PROMEDIOS_PLAYINGTIME = {"points_per_game": "games", "plus_minus_wowy": "minutes"}
EXTRAS = SUMAS_PLAYINGTIME + SUMAS_KEEPERS

# Una "temporada de un jugador" = un jugador (id) en una liga y una temporada. Si cambió de liga a mitad de temporada
# quedan DOS filas, una por liga, a propósito: los percentiles y rankings se calculan dentro de cada liga, y mezclar
# minutos de la Premier con minutos de la Eredivisie no tendría una interpretación limpia.
CLAVE_TEMPORADA = ["id_jugador", "league", "season"]

# Perfiles duplicados DENTRO de FBref: la misma persona con dos ids. Se unen al id canónico (el de la carrera más larga).
# Verificados a mano el 2026-09-19 con `candidatos_revision` (mismo nombre, año y nacionalidad; ids distintos):
ALIAS_FBREF = {
    # Édgar Méndez (España, 1990): "Edgar Mendez" sin acentos tiene Almería 2014-15 y Cruz Azul 2017-18; "Édgar Méndez"
    # tiene Granada 2015-16, Alavés, Cruz Azul 2018-20 y Necaxa. Las temporadas se intercalan en una sola carrera.
    "f5e19d23": "aed746df",
    # Emanuele Torrasi (Italia, 1999): FBref lo lista DOS veces en el Milan 2017-18, con la misma fila (1 partido, 6
    # minutos) bajo dos ids. La copia además se elimina como fila duplicada.
    "06378dd2": "16bc48f8",
}
# Claves nombre|año|nacionalidad que sí son 2 personas distintas (FBref tiene razón al separarlas). Se listan para que la
# auditoría distinga "ya revisado" de "pendiente de revisar" si un scrapeo futuro trae casos nuevos.
HOMONIMOS_VERIFICADOS = {
    "vitinha|2000|POR",      # mediocampista del PSG (antes Wolves) vs. delantero de Marsella y Genoa
    "fernandinho|1985|BRA",  # Manchester City 2013-22 vs. Hellas Verona 2014-15 (delantero)
    "adriano|1982|BRA",      # Roma 2010-11 (delantero) vs. Mónaco 2010-11 (defensa)
    "borja-garcia|1990|ESP", # Racing Santander 2011-12 (defensa) vs. Córdoba/Girona/Huesca 2014-23
}


# ----------------------------------------------------------------------------------------------------------------------
# Carga
# ----------------------------------------------------------------------------------------------------------------------
def cargar_panel_crudo(ruta: str | Path = RUTA_PANEL) -> pd.DataFrame:
    """Lee el panel tal como quedó del scrapeo, solo convirtiendo `minutes` a número y forzando los ids a texto.

    FBref escribe los minutos con separador de miles ("2,086"), así que pandas los lee como texto. Se convierten aquí
    porque sin eso ni siquiera se puede auditar; cualquier otro arreglo se deja a `limpiar_panel` para que la auditoría
    vea los datos tal como llegaron.
    """
    df = pd.read_csv(ruta, dtype=TIPOS_ID)
    df["minutes"] = pd.to_numeric(df["minutes"].astype("string").str.replace(",", "", regex=False), errors="coerce")
    return df


# ----------------------------------------------------------------------------------------------------------------------
# Identidad del jugador
# ----------------------------------------------------------------------------------------------------------------------
def _normalizar_nombre(nombre: str) -> str:
    """'Raúl Jiménez' -> 'raul-jimenez'. Quita acentos y todo lo que no sea letra o número."""
    sin_acentos = unicodedata.normalize("NFKD", str(nombre)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", sin_acentos.lower()).strip("-")


def codigo_nacionalidad(nat: pd.Series) -> pd.Series:
    """FBref guarda la nacionalidad como 'de GER' (bandera + código). Nos quedamos con el código de 3 letras."""
    return nat.astype("string").str.split().str[-1].fillna("UNK")


def clave_por_nombre(df: pd.DataFrame) -> pd.Series:
    """'nombre-normalizado|año-de-nacimiento|nacionalidad' — la identidad que se usó antes de tener los ids de FBref.

    Se conserva para (a) la auditoría, que la compara con el id de FBref para encontrar homónimos y perfiles duplicados,
    y (b) como respaldo en `construir_id_jugador` si un panel no trae `player_id`.
    """
    anio = df["birth_year"].astype("Int64").astype("string").fillna("na")
    return df["player"].map(_normalizar_nombre) + "|" + anio + "|" + codigo_nacionalidad(df["nationality"])


def construir_id_jugador(df: pd.DataFrame) -> pd.Series:
    """Id de jugador = id de FBref, con los perfiles duplicados de `ALIAS_FBREF` unidos a su id canónico.

    Si el DataFrame no trae `player_id` (un panel viejo, o datos de otra fuente), se usa `clave_por_nombre` con su
    límite conocido: puede juntar a homónimos que coinciden en nombre, año y nacionalidad.
    """
    if "player_id" not in df.columns or df["player_id"].isna().any():
        return clave_por_nombre(df)
    return df["player_id"].replace(ALIAS_FBREF)


def es_id_provisional(ids: pd.Series) -> pd.Series:
    """True si el id no es uno de FBref de 8 caracteres hexadecimales.

    43 filas del panel (casi todas de la Liga MX 2010-11, sin año de nacimiento) son jugadores SIN página propia en
    FBref; para ellos FBref usa el nombre como id ("Cesar-Moreno"). Funciona como id, pero dos homónimos sin página
    compartirían el mismo; con tan pocas filas el riesgo es bajo, y queda marcado para no perderlo de vista.
    """
    return ~ids.astype("string").str.fullmatch(r"[0-9a-f]{8}").fillna(False)


def candidatos_revision(df: pd.DataFrame) -> pd.DataFrame:
    """Claves nombre|año|nacionalidad que caen en 2+ ids de FBref: o son homónimos, o son un perfil duplicado de FBref.

    No hay regla automática que distinga los dos casos (Borja García: dos personas SIN temporadas en común; Édgar
    Méndez: una persona con dos perfiles, también sin temporadas en común). Por eso cada candidato se revisa a mano y se
    anota en `ALIAS_FBREF` (misma persona) o `HOMONIMOS_VERIFICADOS` (personas distintas). `estado` dice cuál aplica.
    """
    d = df.assign(_clave=clave_por_nombre(df))
    n_ids = d.groupby("_clave")["player_id"].nunique()
    d = d[d["_clave"].isin(n_ids[n_ids > 1].index)]
    res = d.groupby(["_clave", "player_id"]).agg(
        jugador=("player", "first"), equipos=("team", lambda s: " / ".join(pd.unique(s))),
        desde=("season", "min"), hasta=("season", "max"), posicion=("position", "first")).reset_index()
    res["estado"] = np.where(res["player_id"].isin(set(ALIAS_FBREF) | set(ALIAS_FBREF.values())), "alias (misma persona)",
                             np.where(res["_clave"].isin(HOMONIMOS_VERIFICADOS), "homónimos verificados",
                                      "PENDIENTE de revisar"))
    return res.rename(columns={"_clave": "clave_por_nombre"})


def detectar_colisiones(df: pd.DataFrame) -> pd.DataFrame:
    """Ids que probablemente juntan a dos personas: suman más partidos de los que caben en una temporada.

    Regla: dentro de una liga-temporada, un jugador no puede sumar más partidos que las jornadas de esa liga (+1 de
    tolerancia por partidos reprogramados). Entre dos ligas europeas en la misma temporada tampoco (los calendarios
    coinciden: agosto-mayo). Liga MX se excluye de la segunda regla porque su temporada empieza en julio y un traspaso
    a Europa en el verano puede sumar legítimamente partidos de ambas (caso Santiago Giménez 2022-23).
    Con los ids de FBref no debería encontrar nada; se mantiene como control de calidad sobre el id final.
    Espera un DataFrame con `id_jugador` y `partidos_liga` (la salida de `limpiar_panel`).
    """
    g = df.groupby(["id_jugador", "league", "season"]).agg(
        partidos=("games", "sum"), jornadas=("partidos_liga", "first"), equipos=("team", " / ".join))
    en_liga = g[g["partidos"] > g["jornadas"] + 1].reset_index().assign(regla="misma liga")

    eu = df[df["league"] != "Liga MX"]
    g = eu.groupby(["id_jugador", "season"]).agg(
        ligas=("league", "nunique"), partidos=("games", "sum"), jornadas=("partidos_liga", "max"),
        equipos=("team", " / ".join))
    entre = g[(g["ligas"] > 1) & (g["partidos"] > g["jornadas"] + 1)].reset_index().assign(regla="entre ligas")
    return pd.concat([en_liga, entre], ignore_index=True)[["id_jugador", "season", "regla", "partidos", "jornadas", "equipos"]]


# ----------------------------------------------------------------------------------------------------------------------
# Auditoría
# ----------------------------------------------------------------------------------------------------------------------
def _columnas_duplicado(df: pd.DataFrame) -> list[str]:
    # Dos filas son la misma observación si coinciden en todo el CONTENIDO. Se ignoran `ranker` (el número de fila de la
    # tabla) y los ids: el duplicado de Emanuele Torrasi (Milan 2017-18) es la misma fila bajo dos perfiles de FBref.
    return [c for c in df.columns if c not in ("ranker", "player_id", "team_id")]


def auditar_panel(df_crudo: pd.DataFrame) -> pd.DataFrame:
    """Revisa el panel crudo y devuelve una tabla con cada chequeo, cuántos casos encontró (filas o grupos) y qué hace la limpieza.

    `tipo` distingue:
      - 'error'        dato roto o incoherente en la fuente → `limpiar_panel` lo corrige;
      - 'estructura'   el dato es correcto, pero obliga a un paso extra antes de analizar (identidad, agregación);
      - 'contexto'     no se corrige, pero hay que tenerlo en cuenta al interpretar.
    """
    df = df_crudo
    ids = construir_id_jugador(df)
    filas = []

    def agregar(chequeo, tipo, n, ejemplo, accion):
        filas.append({"chequeo": chequeo, "tipo": tipo, "casos": int(n), "ejemplo": ejemplo, "accion": accion})

    def ejemplo_de(mascara, cols=("player", "team", "league", "season")):
        if not mascara.any():
            return ""
        r = df.loc[mascara].iloc[0]
        return ", ".join(str(r[c]) for c in cols)

    # --- Errores de la fuente ---
    dup = df.duplicated(_columnas_duplicado(df), keep="first")
    agregar("fila duplicada (mismo contenido)", "error", dup.sum(), ejemplo_de(dup), "se elimina la copia")

    m = df["minutes"].isna()
    agregar("minutos vacíos", "error", m.sum(), ejemplo_de(m), "0 si `minutes_90s` = 0 (entró sin sumar minutos)")

    m = df[CONTEOS].isna().any(axis=1) & ~df["minutes"].isna()
    agregar("otro conteo vacío (asistencias, penales)", "error", m.sum(), ejemplo_de(m), "se rellena con 0")

    m = (df["goals_assists"] != df["goals"] + df["assists"])
    agregar("G+A no cuadra con goles + asistencias", "error", m.sum(), ejemplo_de(m),
            "todas las columnas derivadas se recalculan desde los conteos")

    m = (df["goals_pens"] != df["goals"] - df["pens_made"])
    agregar("goles sin penal no cuadra con goles − penales", "error", m.sum(), ejemplo_de(m), "se recalcula")

    m = df["pens_made"] > df["pens_att"]
    agregar("más penales anotados que intentados", "error", m.sum(), ejemplo_de(m),
            "intentos = max(intentos, anotados)")

    # --- Identidad ---
    if "player_id" not in df.columns:
        agregar("el panel no trae `player_id` de FBref", "estructura", len(df), "(todas las filas)",
                "se usa clave nombre|año|nacionalidad; correr scripts/unir_ids_fbref.py")
    else:
        m = df["player_id"].isna()
        agregar("fila sin id de FBref", "error", m.sum(), ejemplo_de(m), "se usa la clave por nombre en todo el panel")
        m = es_id_provisional(df["player_id"])
        agregar("jugador sin página en FBref (id = su nombre)", "contexto", m.sum(), ejemplo_de(m),
                "se usa ese id; marcado en `id_provisional`")

        g = df.groupby(["league", "season", "player"])["birth_year"].nunique()
        homonimos = g[g > 1]
        agregar("mismo nombre con 2+ años de nacimiento en una liga-temporada", "estructura", len(homonimos),
                " / ".join(f"{p} ({l} {s})" for l, s, p in homonimos.index[:3]), "el id es el de FBref, no el nombre")

        cand = candidatos_revision(df)
        por_estado = cand.drop_duplicates("clave_por_nombre")["estado"].value_counts()
        agregar("nombre + año + nacionalidad iguales, 2 personas", "estructura",
                por_estado.get("homónimos verificados", 0),
                ", ".join(sorted(cand.loc[cand["estado"] == "homónimos verificados", "jugador"].unique())),
                "el id de FBref los separa")
        agregar("perfil duplicado en FBref (1 persona, 2 ids)", "error", por_estado.get("alias (misma persona)", 0),
                ", ".join(sorted(cand.loc[cand["estado"] == "alias (misma persona)", "jugador"].unique())),
                "se unen con ALIAS_FBREF")
        agregar("candidatos de identidad sin revisar", "estructura", por_estado.get("PENDIENTE de revisar", 0), "",
                "revisar con candidatos_revision() y anotar en ALIAS_FBREF o HOMONIMOS_VERIFICADOS")

    tmp = df.assign(id_jugador=ids, partidos_liga=df.groupby(["league", "season"])["games"].transform("max"))
    agregar("id con más partidos de los que caben en la temporada", "error", len(detectar_colisiones(tmp)), "",
            "control de calidad del id final (debe ser 0)")

    # --- Estructura y contexto ---
    g = df.assign(id_jugador=ids).groupby(["id_jugador", "league", "season"])["team"].nunique()
    agregar("jugador en 2+ equipos de la misma liga-temporada (traspaso)", "estructura", int((g > 1).sum()),
            "", "se suman en una sola fila por temporada")

    g = df.assign(id_jugador=ids).groupby(["id_jugador", "season"])["league"].nunique()
    agregar("jugador en 2+ ligas en la misma temporada (traspaso entre ligas)", "contexto", int((g > 1).sum()),
            "", "una fila por liga (no se mezclan)")

    m = df["birth_year"].isna()
    agregar("año de nacimiento vacío", "contexto", m.sum(), ejemplo_de(m), "la edad queda vacía (no afecta al id)")

    # Temporadas recortadas: el máximo de partidos de alguien queda por debajo de las jornadas de un torneo de ida y
    # vuelta, 2 × (equipos − 1). Se compara contra el número de equipos de ESA temporada y no contra lo "habitual" de la
    # liga: la Ligue 1 pasó de 20 a 18 equipos en 2023-24 (34 jornadas) y eso no es un recorte.
    cobertura = df.groupby(["league", "season"]).agg(maxp=("games", "max"), equipos=("team", "nunique"))
    recortadas = cobertura.loc[cobertura["maxp"] < 2 * (cobertura["equipos"] - 1), "maxp"]
    agregar("liga-temporada recortada (menos jornadas de lo habitual)", "contexto", len(recortadas),
            " / ".join(f"{l} {s}: {int(v)} partidos" for (l, s), v in recortadas.items()),
            "se normaliza con `partidos_liga` y por 90 minutos")
    return pd.DataFrame(filas)


# ----------------------------------------------------------------------------------------------------------------------
# Limpieza
# ----------------------------------------------------------------------------------------------------------------------
def _recalcular_derivadas(df: pd.DataFrame) -> pd.DataFrame:
    """Recalcula G+A, goles sin penal, minutos/90 y todas las tasas por 90 desde los conteos crudos.

    Las tasas por 90 se dejan en NaN si el jugador no sumó minutos (dividir entre 0 no es "0 goles por 90", es "sin
    dato"); los análisis por 90 además filtran por un mínimo de minutos, porque con 50 minutos un solo gol da 1.8/90.
    """
    df["goals_assists"] = df["goals"] + df["assists"]
    df["goals_pens"] = df["goals"] - df["pens_made"]
    df["minutes_90s"] = df["minutes"] / 90
    n90 = df["minutes_90s"].where(df["minutes_90s"] > 0)
    df["goals_per90"] = df["goals"] / n90
    df["assists_per90"] = df["assists"] / n90
    df["goals_assists_per90"] = df["goals_assists"] / n90
    df["goals_pens_per90"] = df["goals_pens"] / n90
    df["goals_assists_pens_per90"] = (df["goals_pens"] + df["assists"]) / n90
    return df


def edad_en_anios(edad: pd.Series) -> pd.Series:
    """Edad a número, aguantando los dos formatos que usa FBref.

    En las temporadas CERRADAS la publica como años enteros ("29"); en la que está EN CURSO, como "años-días"
    ("30-284"), que pandas lee como texto y convierte en NaN cualquier cálculo de edad ponderada o de minutos sub-21.
    Se toma la parte de los años, que es lo que significa la columna en el resto del panel.
    """
    return pd.to_numeric(edad.astype("string").str.split("-").str[0], errors="coerce")


def limpiar_panel(df_crudo: pd.DataFrame) -> pd.DataFrame:
    """Aplica las correcciones de `auditar_panel` y agrega columnas de trabajo. Una fila = jugador-equipo-temporada.

    Columnas nuevas:
      id_jugador        ver `construir_id_jugador` (id de FBref con alias aplicados)
      id_provisional    True si el jugador no tiene página en FBref (ver `es_id_provisional`)
      nacionalidad      código de 3 letras
      pos_principal     primera posición de FBref ('FW,MF' -> 'FW'); FBref ordena las posiciones por uso
      temporada_inicio  2024 para '2024-2025' (útil para ordenar y graficar)
      age               años como número (ver `edad_en_anios`)
    """
    df = df_crudo.drop_duplicates(_columnas_duplicado(df_crudo), keep="first").copy()

    # Minutos vacíos: solo se ponen en 0 si FBref dice 0 "noventas" (entró a la lista del partido sin sumar minutos).
    # Si hubiera minutos vacíos con `minutes_90s` > 0 se reconstruirían desde ahí (no pasa en el panel actual).
    sin_min = df["minutes"].isna()
    df.loc[sin_min, "minutes"] = (df.loc[sin_min, "minutes_90s"].fillna(0) * 90).round()

    df[CONTEOS] = df[CONTEOS].fillna(0)
    # Un penal anotado implica un penal intentado: si la fuente dice 1 anotado y 0 intentos, el error está en los intentos.
    df["pens_att"] = df[["pens_att", "pens_made"]].max(axis=1)

    df = _recalcular_derivadas(df)
    df["id_jugador"] = construir_id_jugador(df)
    df["id_provisional"] = es_id_provisional(df["id_jugador"])
    df["nacionalidad"] = codigo_nacionalidad(df["nationality"])
    df["pos_principal"] = df["position"].astype("string").str.split(",").str[0].fillna("ND")
    df["temporada_inicio"] = df["season"].str[:4].astype(int)
    df["age"] = edad_en_anios(df["age"])

    # Partidos de liga "disponibles" en esa liga-temporada: el máximo que jugó alguien. Es una aproximación (en
    # temporadas recortadas no todos los equipos jugaron lo mismo, p. ej. Ligue 1 2019-20: 27 o 28), pero basta para
    # expresar los minutos como proporción de lo posible y comparar temporadas de 34, 38 o 28 jornadas.
    df["partidos_liga"] = df.groupby(["league", "season"])["games"].transform("max")
    # Una temporada EN CURSO (la que se está jugando) tiene un puñado de jornadas y no se puede poner en la misma
    # serie que las cerradas: su rotación, su edad ponderada y sus tasas por 90 no significan lo mismo. Se marca
    # comparando contra lo que esa liga suele jugar. El umbral es bajo (60%) a propósito: temporadas acortadas pero
    # TERMINADAS, como las de 2019-20 por COVID (27 de 38 jornadas en Ligue 1, 71%), no se marcan — se jugaron y el
    # proyecto siempre las ha incluido.
    normal = df.groupby("league")["partidos_liga"].transform("max")
    df["temporada_parcial"] = df["partidos_liga"] < 0.6 * normal
    return df


def cargar_tabla_fbref(tabla: str, carpeta_raw: str | Path = CARPETA_RAW) -> pd.DataFrame:
    """Junta los 112 CSV de `data/raw/fbref_<tabla>/` ("keepers" o "playingtime") y convierte los números.

    Las celdas vacías quedan como NaN, NO como 0: en FBref una celda vacía significa "sin dato" (p. ej. onGA antes de
    2014-15, penales atajados antes de 2016-17; ver output/cobertura_keepers_playingtime.csv), y convertirla en 0
    haría creer que un defensa de 2012 no recibió goles con él en cancha.
    """
    archivos = sorted(Path(carpeta_raw, f"fbref_{tabla}").glob("*.csv"))
    if not archivos:
        raise FileNotFoundError(f"no hay CSV en {Path(carpeta_raw, f'fbref_{tabla}')}")
    df = pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False) for f in archivos], ignore_index=True)
    texto = ["player", "nationality", "position", "team", "league", "season", "player_id", "team_id"]
    for col in df.columns.difference(texto):
        df[col] = pd.to_numeric(df[col].str.replace(",", "", regex=False).replace("", np.nan), errors="coerce")
    return df


def unir_tablas_extra(df_limpio: pd.DataFrame, carpeta_raw: str | Path = CARPETA_RAW) -> pd.DataFrame:
    """Agrega a cada fila jugador-equipo-temporada sus columnas de `playingtime` y, si es portero, de `keepers`.

    Se une por (liga, temporada, player_id, team_id) — el id ORIGINAL de FBref, antes de aplicar ALIAS_FBREF, porque así
    vienen las tablas extra. Es uno a uno (verificado: ninguna clave se repite en ninguna tabla). Quedan fuera los
    jugadores que solo fueron a la banca (0 partidos): no están en el panel y no suman nada en un fantasy.
    """
    clave = ["league", "season", "player_id", "team_id"]
    pt = cargar_tabla_fbref("playingtime", carpeta_raw)[clave + SUMAS_PLAYINGTIME + list(PROMEDIOS_PLAYINGTIME)]
    kp = cargar_tabla_fbref("keepers", carpeta_raw)[clave + SUMAS_KEEPERS]
    df = df_limpio.merge(pt, on=clave, how="left", validate="one_to_one")
    return df.merge(kp, on=clave, how="left", validate="one_to_one")


def _agregar_extras(d: pd.DataFrame) -> pd.DataFrame:
    """Suma y promedios ponderados de las columnas extra por jugador-liga-temporada (ver agregar_por_temporada)."""
    llave = [d[k] for k in CLAVE_TEMPORADA]
    # min_count=1: si TODAS las filas del jugador están vacías (sin dato), la suma queda NaN en vez de 0.
    res = d.groupby(llave, sort=False)[[c for c in EXTRAS if c in d.columns]].sum(min_count=1)
    for col, peso in PROMEDIOS_PLAYINGTIME.items():
        if col in d.columns:
            con_dato = d[col].notna()
            num = (d[col] * d[peso]).where(con_dato).groupby(llave, sort=False).sum(min_count=1)
            den = d[peso].where(con_dato).groupby(llave, sort=False).sum(min_count=1)
            res[col] = num / den.where(den > 0)
    return res.reset_index()


def agregar_por_temporada(df_limpio: pd.DataFrame) -> pd.DataFrame:
    """Una fila por jugador-liga-temporada, sumando los equipos por los que pasó en esa liga durante la temporada.

    - Conteos: se suman.
    - Datos descriptivos (nombre, posición, edad, equipo principal): se toman de la fila con MÁS minutos — es el
      equipo/rol que mejor representa su temporada.
    - `equipos`: todos los equipos, del de más minutos al de menos ("América / Toluca").
    - `pct_minutos`: minutos / (partidos_liga × 90), recortado a 1. Mide "regularidad": cuánto de lo posible jugó.
    - Columnas extra (si antes se llamó a `unir_tablas_extra`): conteos sumados (vacío si no hay dato en ninguna de sus
      filas); puntos por partido ponderado por partidos y on-off ponderado por minutos (aproximación: FBref no publica
      los conteos detrás de esas dos tasas); y tasas recalculadas: plus_minus, on_goals_against_per90, gk_save_pct,
      gk_clean_sheets_pct.
    """
    d = df_limpio.sort_values("minutes", ascending=False, kind="mergesort")
    extra = {"equipo_principal_id": ("team_id", "first")} if "team_id" in d.columns else {}
    agg = d.groupby(CLAVE_TEMPORADA, sort=False).agg(
        player=("player", "first"),
        id_provisional=("id_provisional", "first"),
        birth_year=("birth_year", "first"),
        nacionalidad=("nacionalidad", "first"),
        position=("position", "first"),
        pos_principal=("pos_principal", "first"),
        age=("age", "first"),
        temporada_inicio=("temporada_inicio", "first"),
        partidos_liga=("partidos_liga", "first"),
        temporada_parcial=("temporada_parcial", "first"),
        equipo_principal=("team", "first"),
        **extra,
        equipos=("team", " / ".join),
        n_equipos=("team", "nunique"),
        **{c: (c, "sum") for c in CONTEOS},
    ).reset_index()
    agg = _recalcular_derivadas(agg)
    agg["pct_minutos"] = (agg["minutes"] / (agg["partidos_liga"] * 90)).clip(upper=1)

    if any(c in d.columns for c in EXTRAS):
        agg = agg.merge(_agregar_extras(d), on=CLAVE_TEMPORADA, how="left", validate="one_to_one")
        agg["plus_minus"] = agg["on_goals_for"] - agg["on_goals_against"]
        agg["on_goals_against_per90"] = agg["on_goals_against"] / agg["minutes_90s"].where(agg["minutes_90s"] > 0)
        agg["gk_save_pct"] = 100 * agg["gk_saves"] / agg["gk_shots_on_target_against"].where(
            agg["gk_shots_on_target_against"] > 0)
        agg["gk_clean_sheets_pct"] = 100 * agg["gk_clean_sheets"] / agg["gk_games"].where(agg["gk_games"] > 0)
    return agg.sort_values(["league", "temporada_inicio", "player"], ignore_index=True)


def cargar_jugadores_temporada(ruta: str | Path = RUTA_PANEL, con_extras: bool = True,
                               carpeta_raw: str | Path = CARPETA_RAW) -> pd.DataFrame:
    """Atajo: panel crudo -> limpio (+ playingtime y keepers si `con_extras`) -> una fila por jugador-liga-temporada."""
    limpio = limpiar_panel(cargar_panel_crudo(ruta))
    if con_extras:
        limpio = unir_tablas_extra(limpio, carpeta_raw)
    return agregar_por_temporada(limpio)
