"""
Puntos tipo fantasy por temporada, calculados desde el panel de plantillas de FBref.

Esquema de referencia: Fantasy Premier League (FPL)
----------------------------------------------------
Se toma FPL porque es el fantasy más jugado y su reglamento es público y estable. Sus reglas de puntuación (por
partido) y cómo se traducen a lo que tenemos (TOTALES de temporada):

  Regla FPL                              ¿La tenemos?  Cómo se aplica aquí
  -------------------------------------  ------------  ----------------------------------------------------------------
  Jugar ≥60 min: 2 pts / <60 min: 1 pt   aproximada    titularidad = 2 pts, entrar de cambio = 1 pt (ver nota 1)
  Gol: POR/DEF 6, MED 5, DEL 4           sí            según `pos_principal` (primera posición de FBref)
  Asistencia: 3                          sí            FBref cuenta asistencias con su propio criterio (nota 2)
  Amarilla: −1 / Roja: −3                sí
  Penal fallado: −2                      sí            penales intentados − anotados
  Portería a cero, goles recibidos,      sí, aparte    tablas `keepers` y `playingtime`: ver ESQUEMA_DEFENSIVO abajo
  paradas, penal atajado
  Bonus (BPS)                            NO            necesita datos por partido que FBref no publica (nota 3)

Nota 1 — aparición: FPL da 2 pts a quien juega 60+ minutos EN ESE PARTIDO. Con totales de temporada no se puede saber
partido a partido; "fue titular" es la mejor aproximación (la mayoría de titulares pasan de 60', casi ningún suplente).
El error es simétrico y pequeño frente al peso de goles y asistencias.
Nota 2 — asistencias: FPL usa un criterio más generoso (cuenta rebotes, penales provocados, etc.). FBref usa el pase
previo al gol. Nuestros números de asistencias serán algo más bajos que los de FPL.
Nota 3 — bonus: el BPS de FPL se reparte a los 3 mejores DE CADA PARTIDO con una fórmula sobre eventos por partido.
Con totales de temporada no hay forma de reconstruirlo, así que este puntaje no lo incluye (son ~10-30 pts al año para
un titular importante, casi siempre a favor de los mismos jugadores que ya puntúan alto).

`ESQUEMA_FPL_PARCIAL` es el puntaje **ofensivo + disciplina** (goles, asistencias, tarjetas, aparición). Es el que usan
los notebooks 17 a 19. `ESQUEMA_DEFENSIVO` añade la parte defensiva con `puntos_defensivos` y solo entonces el puntaje
sirve para comparar defensas y porteros; ver la explicación larga arriba de esa función.

Los dos esquemas son diccionarios: para probar otro fantasy (LaLiga Fantasy, Sorare, uno propio para Liga MX) basta con
pasar otro diccionario con las mismas claves.
"""
from __future__ import annotations

from math import factorial

import numpy as np
import pandas as pd

ESQUEMA_FPL_PARCIAL = {
    "nombre": "FPL adaptado (sin porterías a cero, paradas ni bonus)",
    "titular": 2,
    "suplente": 1,
    # Puntos por gol según la posición principal. 'ND' (sin posición en FBref, 0.1% de las filas) se trata como
    # mediocampista: es el valor intermedio y no favorece ni castiga a nadie por un dato faltante.
    "gol": {"GK": 6, "DF": 6, "MF": 5, "FW": 4, "ND": 5},
    "asistencia": 3,
    "amarilla": -1,
    "roja": -3,
    "penal_fallado": -2,
}

POSICIONES_ATAQUE = ("FW", "MF")

ESQUEMA_DEFENSIVO = {
    "nombre": "FPL defensivo (porterías a cero, paradas, penales atajados y goles recibidos)",
    # Portería a cero: en FPL vale 4 para portero y defensa, 1 para mediocampista y nada para delantero.
    "porteria_cero": {"GK": 4, "DF": 4, "MF": 1, "FW": 0, "ND": 1},
    # Goles recibidos: −1 por cada 2, solo a portero y defensa (el mediocampista no los paga en FPL).
    "goles_recibidos": {"GK": -1, "DF": -1, "MF": 0, "FW": 0, "ND": 0},
    "goles_por_punto": 2,
    "parada": 1,
    "paradas_por_punto": 3,      # +1 por cada 3 paradas; solo porteros
    "penal_atajado": 5,
}


def esperanza_piso(lam: np.ndarray | pd.Series, divisor: int, k_max: int = 40) -> np.ndarray:
    """E[⌊X/divisor⌋] cuando X ~ Poisson(lam): el promedio de puntos por partido de una regla "1 punto por cada N".

    Para qué sirve: FPL redondea DENTRO de cada partido. Un portero con 3 paradas en un partido y 2 en el siguiente
    suma 1+0 = 1 punto, no 5/3 = 1.67. Con totales de temporada no sabemos el reparto por partido, pero sí el promedio,
    y bajo Poisson el valor esperado del redondeo se calcula exacto sumando la distribución. No es un detalle menor:
    para un portero titular, paradas/3 da +34 pts y el redondeo correcto +23 (y goles recibidos −22 vs −15).

    El supuesto de Poisson por partido es el mismo que sostiene `porterias_cero_estimadas`, y ahí sí se puede verificar
    contra la verdad (ver `validar_porterias_cero`): predice bien los partidos sin goles, así que se acepta también
    para el redondeo, donde FBref no publica nada con qué comprobarlo.
    """
    lam = np.asarray(lam, dtype=float)
    k = np.arange(k_max)
    positivo = lam > 0                      # los NaN quedan fuera (NaN > 0 es False) y se reponen al final
    seguro = np.where(positivo, lam, 1.0)
    # pmf de Poisson calculada en logaritmos: con lam grande, lam**k desborda antes de que k! lo compense.
    log_pmf = -seguro[:, None] + k * np.log(seguro[:, None]) - np.array([np.log(float(factorial(i))) for i in k])
    esperanza = (np.exp(log_pmf) * (k // divisor)).sum(axis=1)
    return np.where(positivo, esperanza, np.where(np.isnan(lam), np.nan, 0.0))


def porterias_cero_estimadas(partidos_60: pd.Series, noventas: pd.Series, goles_recibidos: pd.Series) -> pd.Series:
    """Estima cuántos partidos terminó un jugador sin que su equipo recibiera gol CON ÉL EN LA CANCHA.

    El problema: FBref publica porterías a cero solo de los porteros. Para un jugador de campo sabemos cuántos goles
    recibió su equipo mientras él estaba en la cancha (`on_goals_against`, desde 2014-15) pero no cómo se repartieron
    entre partidos, que es justo lo que decide una portería a cero.

    La estimación: si los goles de un partido siguen una Poisson de media λ, la probabilidad de un partido sin goles es
    e^(−λ). Enchufar λ̂ = goles/partidos en e^(−λ) sobreestima (la función es convexa; da +4.7% en los porteros), así
    que se usa el estimador insesgado de e^(−λ) para una Poisson: ((n−1)/n)^goles, con n = noventas jugados. Ese
    estimador es exacto en el caso extremo: con n=1 vale 1 si no recibió goles y 0 si recibió alguno.

    Se multiplica por `partidos_60` —los partidos en que jugó 60+ minutos, aproximados por las titularidades— porque
    FPL solo paga la portería a cero a quien llegó a 60'. Un suplente que entró 10 minutos 20 veces no suma nada,
    aunque su `on_goals_against` sea bajo precisamente por jugar poco.

    Qué tan buena es: verificada contra los 4,542 porteros-equipo-temporada del panel, donde la verdad se conoce
    (`validar_porterias_cero`): correlación 0.96, sesgo −1.7% en el total y un error típico de ±1.5 porterías a cero
    por temporada de titular. Es decir, sirve para promedios de liga, de posición y para ordenar jugadores; para un
    jugador concreto arrastra ~±6 puntos fantasy de incertidumbre, y así se reporta.
    """
    n = noventas.where(noventas > 0)
    prob_cero = np.power(((n - 1) / n).clip(lower=0), goles_recibidos)
    return (partidos_60 * prob_cero).where(goles_recibidos.notna())


def puntos_fantasy(jt: pd.DataFrame, esquema: dict = ESQUEMA_FPL_PARCIAL) -> pd.DataFrame:
    """Agrega el desglose de puntos a una tabla jugador-liga-temporada (salida de `plantillas.agregar_por_temporada`).

    Columnas nuevas:
      pts_aparicion, pts_goles, pts_asistencias, pts_tarjetas, pts_penales   desglose (suman `pts_total`)
      pts_total        puntos de la temporada
      pts_por_jornada  pts_total / jornadas de la liga-temporada — compara temporadas de 34, 38 o 28 (COVID) jornadas
                       y "castiga" perderse partidos (lesión, banca), igual que en un fantasy real
      pts_por90        pts_total / (minutos/90) — rendimiento cuando juega, sin importar cuánto; SOLO es fiable con un
                       mínimo de minutos (con 30' repartidos en 3 cambios da 9 pts/90 solo por aparecer)
    """
    df = jt.copy()
    suplencias = df["games"] - df["games_starts"]
    valor_gol = df["pos_principal"].map(esquema["gol"]).fillna(esquema["gol"]["ND"])
    penales_fallados = (df["pens_att"] - df["pens_made"]).clip(lower=0)

    df["pts_aparicion"] = esquema["titular"] * df["games_starts"] + esquema["suplente"] * suplencias
    df["pts_goles"] = valor_gol * df["goals"]
    df["pts_asistencias"] = esquema["asistencia"] * df["assists"]
    df["pts_tarjetas"] = esquema["amarilla"] * df["cards_yellow"] + esquema["roja"] * df["cards_red"]
    df["pts_penales"] = esquema["penal_fallado"] * penales_fallados
    df["pts_total"] = df[["pts_aparicion", "pts_goles", "pts_asistencias", "pts_tarjetas", "pts_penales"]].sum(axis=1)
    df["pts_por_jornada"] = df["pts_total"] / df["partidos_liga"]
    df["pts_por90"] = df["pts_total"] / df["minutes_90s"].where(df["minutes_90s"] > 0)
    return df


def puntos_defensivos(jt: pd.DataFrame, esquema: dict = ESQUEMA_DEFENSIVO) -> pd.DataFrame:
    """Agrega la mitad defensiva del fantasy a una tabla que ya pasó por `puntos_fantasy`.

    De dónde sale cada cosa (y de dónde NO):

      Concepto            Portero                              Jugador de campo
      ------------------  -----------------------------------  ------------------------------------------------------
      Portería a cero     REAL (`gk_clean_sheets`, 2010-11+)    ESTIMADA desde `on_goals_against` (2014-15+, ver
                                                                `porterias_cero_estimadas`)
      Goles recibidos     REAL (`gk_goals_against`)             REAL, los recibidos con él en cancha (2014-15+)
      Paradas             REAL (`gk_saves`), +1 por cada 3      no aplica
      Penal atajado       REAL (`gk_pens_saved`, 2016-17+)      no aplica

    Las reglas que FPL aplica por partido (1 punto por cada 3 paradas, −1 por cada 2 goles recibidos) se calculan con
    `esperanza_piso`, no dividiendo el total de la temporada: la diferencia es de 10 puntos o más por temporada.

    Columnas nuevas:
      porterias_cero       porterías a cero (reales en porteros, estimadas en jugadores de campo)
      pts_porteria_cero, pts_goles_recibidos, pts_paradas, pts_penales_atajados   desglose
      pts_defensivos       suma de los cuatro
      pts_total_completo   ofensivo (`pts_total`) + defensivo
      pts_completo_por_jornada   `pts_total_completo` / jornadas de la liga-temporada
      def_completo         True solo si existían TODOS los datos que su posición necesita. Es la columna con la que hay
                           que filtrar antes de comparar: un defensa de 2012-13 no tiene `on_goals_against` y un
                           portero de 2014-15 no tiene penales atajados, así que sus puntos defensivos salen
                           incompletos, no bajos. Con las siete ligas, `def_completo` arranca en 2016-17.
    """
    df = jt.copy()
    es_portero = (df["gk_minutes"].fillna(0) > 0) if "gk_minutes" in df else pd.Series(False, index=df.index)
    valor_cero = df["pos_principal"].map(esquema["porteria_cero"]).fillna(esquema["porteria_cero"]["ND"])
    valor_gol_recibido = df["pos_principal"].map(esquema["goles_recibidos"]).fillna(esquema["goles_recibidos"]["ND"])

    # Porterías a cero: la verdad en los porteros, la estimación en el resto.
    estimadas = porterias_cero_estimadas(df["games_starts"], df["minutes_90s"], df["on_goals_against"])
    df["porterias_cero"] = np.where(es_portero, df["gk_clean_sheets"], estimadas)

    # Goles recibidos y paradas: partidos y media por partido de cada quien, redondeando como FPL dentro del partido.
    partidos = np.where(es_portero, df["gk_games"], df["games"])
    recibidos = np.where(es_portero, df["gk_goals_against"], df["on_goals_against"])
    penalizacion = esperanza_piso(np.divide(recibidos, partidos, out=np.zeros(len(df)), where=partidos > 0),
                                  esquema["goles_por_punto"]) * partidos
    paradas = esperanza_piso(np.divide(df["gk_saves"].fillna(0), partidos, out=np.zeros(len(df)), where=partidos > 0),
                             esquema["paradas_por_punto"]) * partidos

    df["pts_porteria_cero"] = valor_cero * df["porterias_cero"]
    df["pts_goles_recibidos"] = valor_gol_recibido * np.where(np.isnan(recibidos), np.nan, penalizacion)
    df["pts_paradas"] = np.where(es_portero & df["gk_saves"].notna(), esquema["parada"] * paradas, np.nan)
    df["pts_penales_atajados"] = np.where(es_portero, esquema["penal_atajado"] * df["gk_pens_saved"], np.nan)

    desglose = ["pts_porteria_cero", "pts_goles_recibidos", "pts_paradas", "pts_penales_atajados"]
    df["pts_defensivos"] = df[desglose].sum(axis=1)          # los NaN cuentan como 0: por eso existe `def_completo`
    df["pts_total_completo"] = df["pts_total"] + df["pts_defensivos"]
    df["pts_completo_por_jornada"] = df["pts_total_completo"] / df["partidos_liga"]
    df["def_completo"] = np.where(es_portero,
                                  df[["gk_clean_sheets", "gk_goals_against", "gk_saves", "gk_pens_saved"]].notna(
                                      ).all(axis=1),
                                  df["on_goals_against"].notna())
    return df


def validar_porterias_cero(df: pd.DataFrame) -> pd.DataFrame:
    """Compara la estimación de porterías a cero contra la verdad, usando a los porteros como banco de pruebas.

    Es la única comprobación posible: los porteros son los únicos de quienes FBref publica porterías a cero reales, y
    la fórmula que se les aplica aquí es EXACTAMENTE la que se usa con los jugadores de campo (titularidades, noventas
    jugados y goles recibidos con él en cancha). Si acierta en ellos, el supuesto de Poisson por partido se sostiene.

    Devuelve una fila por tramo de partidos jugados con: cuántos porteros-temporada hay, la media real, la estimada,
    el sesgo (estimada − real) y el error absoluto medio.
    """
    gk = df[(df["gk_games"].fillna(0) > 0) & df["gk_clean_sheets"].notna() & df["gk_goals_against"].notna()].copy()
    gk["estimada"] = porterias_cero_estimadas(gk["gk_games_starts"], gk["gk_minutes"] / 90, gk["gk_goals_against"])
    gk["error"] = gk["estimada"] - gk["gk_clean_sheets"]
    gk["tramo"] = pd.cut(gk["gk_games"], [0, 5, 15, 25, 60], labels=["1-5", "6-15", "16-25", "26+ (titular)"])
    res = gk.groupby("tramo", observed=True).agg(
        porteros=("error", "size"), real=("gk_clean_sheets", "mean"), estimada=("estimada", "mean"),
        sesgo=("error", "mean"), error_absoluto=("error", lambda s: s.abs().mean()),
        correlacion=("estimada", lambda s: s.corr(gk.loc[s.index, "gk_clean_sheets"])))
    total = pd.DataFrame({"porteros": [len(gk)], "real": [gk["gk_clean_sheets"].mean()],
                          "estimada": [gk["estimada"].mean()], "sesgo": [gk["error"].mean()],
                          "error_absoluto": [gk["error"].abs().mean()],
                          "correlacion": [gk["estimada"].corr(gk["gk_clean_sheets"])]}, index=["TODOS"])
    return pd.concat([res, total])


def percentil_en_grupo(df: pd.DataFrame, columna: str, min_minutos: int = 900,
                       grupo: tuple[str, ...] = ("league", "season", "pos_principal")) -> pd.Series:
    """Percentil (0-100) de `columna` dentro de su liga-temporada-posición, solo entre jugadores con `min_minutos`.

    Por qué percentil y no el valor crudo: el ambiente goleador cambia entre ligas y temporadas (la Premier 2023-24 tuvo
    1,197 goles, la 2014-15 943). Ser percentil 95 significa lo mismo en cualquier contexto, así que permite seguir a un
    jugador a través de temporadas y ligas.
    Por qué 900 minutos por defecto: ~10 partidos completos; por debajo, las tasas por 90 son sobre todo ruido.
    Los jugadores que no llegan al mínimo quedan en NaN (no se les asigna percentil, ni bajo ni alto).
    """
    elegible = df["minutes"] >= min_minutos
    pct = df.loc[elegible].groupby(list(grupo))[columna].rank(pct=True) * 100
    return pct.reindex(df.index)


def percentil_completo(jt: pd.DataFrame, min_minutos: int = 900) -> pd.Series:
    """Percentil del fantasy COMPLETO dentro de la liga-temporada-posición. Es la única forma de comparar entre ligas.

    Dos reglas, y las dos importan:
      - solo entran las filas con `def_completo`: antes de 2014-15 no hay goles recibidos en cancha y antes de 2016-17
        no hay penales atajados, así que incluirlas confundiría "sin dato" con "puntuó poco";
      - el percentil se calcula dentro de liga-temporada-posición, así que un 90 significa lo mismo en la Eredivisie
        2016-17 que en la Premier 2024-25, y un portero se compara con porteros.

    Ojo con lo que NO se puede hacer con esto: el percentil medio de cualquier liga es 50 por construcción, así que
    comparar percentiles medios entre ligas no dice nada. Para comparar ligas hay que mirar a los jugadores que se
    mudan de una a otra (`liga.escalera_ligas`).
    """
    completas = jt[jt["def_completo"]] if "def_completo" in jt else jt
    return percentil_en_grupo(completas, "pts_completo_por_jornada", min_minutos).reindex(jt.index)


def tabla_consistencia(df: pd.DataFrame, columna_pct: str = "pct_pts_jornada", min_temporadas: int = 4) -> pd.DataFrame:
    """Resume la carrera de cada jugador: cuántas temporadas elegibles, percentil medio, mejor y peor, y dispersión.

    "Regularidad fantasy" = percentil medio alto con dispersión baja: el jugador que rinde cada año, no el de un solo
    año excepcional. Se usa el percentil (no los puntos) para que temporadas de ligas y épocas distintas sean comparables.
    """
    d = df.dropna(subset=[columna_pct])
    res = d.groupby("id_jugador").agg(
        jugador=("player", "first"),
        posicion=("pos_principal", lambda s: s.mode().iloc[0]),
        temporadas=(columna_pct, "size"),
        ligas=("league", lambda s: " / ".join(pd.unique(s))),
        pct_medio=(columna_pct, "mean"),
        pct_min=(columna_pct, "min"),
        pct_max=(columna_pct, "max"),
        pct_desv=(columna_pct, "std"),
        desde=("temporada_inicio", "min"),
        hasta=("temporada_inicio", "max"),
    )
    return res[res["temporadas"] >= min_temporadas].sort_values("pct_medio", ascending=False)
