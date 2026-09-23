"""
Métricas para analizar UNA liga: plantillas y rotación, porteros, impacto en cancha y dependencia.
Las usan los notebooks 18_analisis_liga_<liga>.ipynb y la página del dashboard analisis.html (vía
scripts/export_analisis_liga.py), así que los dos siempre muestran los mismos números.

Todo recibe la liga como parámetro, para empezar por la Liga MX y repetir exactamente el mismo análisis en las otras
seis. Trabaja sobre dos tablas del paquete:
  - `filas`   jugador-EQUIPO-temporada (plantillas.limpiar_panel + plantillas.unir_tablas_extra). Es la que sirve para
              métricas de equipo: un jugador traspasado a mitad de temporada aporta sus minutos a CADA equipo.
  - `jt`      jugador-temporada (plantillas.agregar_por_temporada), para métricas del jugador.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import pearsonr

# Nacionalidad "local" de cada liga, para medir minutos de extranjeros. FBref asigna a cada jugador la selección que
# representa (nacionalidad deportiva), así que un naturalizado que juega para México cuenta como mexicano.
# Premier: las cuatro naciones del Reino Unido cuentan como locales (galeses, escoceses y norirlandeses no son
# "extranjeros" en el sentido que interesa aquí: jugadores formados fuera del país de la liga).
NACIONALES = {
    "Liga MX": {"MEX"}, "Premier League": {"ENG", "WAL", "SCO", "NIR"}, "La Liga": {"ESP"}, "Serie A": {"ITA"},
    "Bundesliga": {"GER"}, "Ligue 1": {"FRA"}, "Eredivisie": {"NED"},
}


def jugadores_para_pct(minutos, pct: float = 0.8) -> int:
    """Cuántos jugadores (de más a menos minutos) hacen falta para cubrir `pct` de los minutos del equipo.

    Mide concentración: con 11 titulares fijos serían ~11-12 jugadores para el 80%; si el equipo rota mucho, más.
    Es más interpretable que un índice de Gini y no depende de cuántos jugadores con 5 minutos haya en la lista.
    """
    m = np.sort(np.asarray(minutos, dtype=float))[::-1]
    if m.sum() <= 0:
        return 0
    return int(np.searchsorted(np.cumsum(m) / m.sum(), pct - 1e-12) + 1)


def _promedio_ponderado(valores: pd.Series, pesos: pd.Series) -> float:
    ok = valores.notna() & pesos.notna() & (pesos > 0)
    return float(np.average(valores[ok], weights=pesos[ok])) if ok.any() else np.nan


def resumen_equipos(filas: pd.DataFrame, liga: str, incluir_parciales: bool = False) -> pd.DataFrame:
    """Una fila por equipo-temporada de `liga` con plantilla, rotación, resultados y dependencia del goleador.

    Por defecto deja fuera la temporada EN CURSO (`temporada_parcial`, ver `plantillas.limpiar_panel`): con cinco
    jornadas jugadas, la rotación y la edad ponderada de un equipo no son comparables con las de una temporada
    completa, y colocarlas en la misma serie haría ver una caída que solo es el calendario. Se puede pedir con
    `incluir_parciales=True` para explorar el presente, que es lo que hace el explorador de plantillas de la web.

    Columnas:
      jugadores_usados     jugadores con minutos
      jugadores_80pct      jugadores necesarios para el 80% de los minutos (ver jugadores_para_pct)
      edad_ponderada       edad media ponderada por minutos (la edad "de la cancha", no de la lista)
      pct_min_extranjeros  % de minutos de jugadores de otra nacionalidad (ver NACIONALES; sin nacionalidad = fuera)
      pct_min_sub21        % de minutos de jugadores de 21 años o menos
      minutos              suma de minutos (control: ≈ partidos × 990, menos expulsiones)
      pj                   partidos del equipo, estimados con los minutos de sus porteros (siempre hay uno en cancha):
                           gk_minutes / 90. Es el dato robusto: no depende de que FBref tenga los G/E/P.
      ganados, empatados, perdidos, puntos, ppg
                           resultados del equipo, reconstruidos con los G/E/P de sus porteros. En 7 equipo-temporadas de
                           todo el panel FBref tiene los partidos del portero pero sus G/E/P en cero (p. ej. Mallorca
                           2011-12: 1 partido "con resultado" de 38), lo que daría puntos por partido falsos: cuando
                           los G/E/P no cuadran con `pj` (diferencia > 1) estas columnas quedan VACÍAS y
                           `resultados_confiables` es False.
      resultados_confiables  ver arriba
      goles                goles de sus jugadores (sin autogoles a favor: FBref no se los asigna a nadie)
      goleador, goles_goleador, dependencia_goleador   máximo goleador y su parte de los goles del equipo
    """
    d = filas[filas["league"] == liga]
    if not incluir_parciales and "temporada_parcial" in d:
        d = d[~d["temporada_parcial"]]
    locales = NACIONALES[liga]
    res = []
    for (temporada, team_id), g in d.groupby(["season", "team_id"], sort=True):
        con_nac = g[g["nacionalidad"] != "UNK"]
        ganados, empatados, perdidos = (g[c].sum() for c in ("gk_wins", "gk_ties", "gk_losses"))
        pj = round(g["gk_minutes"].sum() / 90)
        confiables = pj > 0 and abs(ganados + empatados + perdidos - pj) <= 1
        puntos = 3 * ganados + empatados if confiables else np.nan
        goleador = g.loc[g["goals"].idxmax()]
        res.append({
            "season": temporada, "temporada_inicio": int(temporada[:4]), "team_id": team_id,
            "equipo": g["team"].iloc[0],
            "jugadores_usados": int((g["minutes"] > 0).sum()),
            "jugadores_80pct": jugadores_para_pct(g["minutes"]),
            "edad_ponderada": _promedio_ponderado(g["age"], g["minutes"]),
            "pct_min_extranjeros": 100 * con_nac.loc[~con_nac["nacionalidad"].isin(locales), "minutes"].sum()
                                   / con_nac["minutes"].sum(),
            "pct_min_sub21": 100 * g.loc[g["age"] <= 21, "minutes"].sum() / g["minutes"].sum(),
            "minutos": g["minutes"].sum(),
            "pj": pj, "resultados_confiables": confiables,
            "ganados": ganados if confiables else np.nan, "empatados": empatados if confiables else np.nan,
            "perdidos": perdidos if confiables else np.nan,
            "puntos": puntos, "ppg": puntos / pj if confiables else np.nan,
            "goles": g["goals"].sum(),
            "goleador": goleador["player"], "goles_goleador": goleador["goals"],
        })
    res = pd.DataFrame(res)
    res["dependencia_goleador"] = res["goles_goleador"] / res["goles"].where(res["goles"] > 0)
    return res


def tendencia_liga(equipos: pd.DataFrame, columnas: list[str]) -> pd.DataFrame:
    """Mediana y rango intercuartil (p25-p75) por temporada de cada columna, entre los equipos de la liga.

    Mediana y no media: un solo equipo con una temporada rara (p. ej. 46 jugadores usados) no mueve la tendencia.
    """
    g = equipos.groupby("temporada_inicio")[columnas]
    return pd.concat({"p25": g.quantile(0.25), "mediana": g.median(), "p75": g.quantile(0.75)}, axis=1)


def porteros_liga(jt: pd.DataFrame, liga: str, incluir_parciales: bool = False) -> pd.DataFrame:
    """Totales de porteros por temporada: % de paradas, goles recibidos por partido y % de porterías a cero.

    Se suman paradas y tiros a puerta de TODOS los porteros antes de dividir (una tasa de la liga, no el promedio de
    las tasas de cada portero, que daría el mismo peso al suplente de 2 partidos que al titular de 34).

    Como `resumen_equipos`, deja fuera la temporada en curso salvo que se pida (ver ahí el porqué).
    """
    p = jt[(jt["league"] == liga) & jt["gk_games"].notna()]
    if not incluir_parciales and "temporada_parcial" in p:
        p = p[~p["temporada_parcial"]]
    t = p.groupby("temporada_inicio")[["gk_saves", "gk_shots_on_target_against", "gk_goals_against",
                                        "gk_clean_sheets", "gk_games"]].sum(min_count=1)
    t["pct_paradas"] = 100 * t["gk_saves"] / t["gk_shots_on_target_against"].where(t["gk_shots_on_target_against"] > 0)
    t["goles_recibidos_por_partido"] = t["gk_goals_against"] / t["gk_games"]
    t["pct_porterias_cero"] = 100 * t["gk_clean_sheets"] / t["gk_games"]
    return t


def carrera_porteros(jt: pd.DataFrame, liga: str, min_minutos: int = 9000) -> pd.DataFrame:
    """Porteros con al menos `min_minutos` en la liga (9,000 ≈ 100 partidos), con sus tasas de TODA la carrera.

    Sumar primero y dividir después (paradas totales / tiros totales) pondera cada temporada por lo que jugó.
    Las temporadas sin dato de paradas (Liga MX y Eredivisie 2018-19) no suman ni paradas ni tiros, así que no sesgan
    el %; sí cuentan para porterías a cero y goles recibidos.
    """
    p = jt[(jt["league"] == liga) & jt["gk_games"].notna()]
    c = p.groupby("id_jugador").agg(
        portero=("player", "first"), temporadas=("season", "nunique"), desde=("temporada_inicio", "min"),
        hasta=("temporada_inicio", "max"), equipos=("equipo_principal", lambda s: " / ".join(pd.unique(s))),
        minutos=("gk_minutes", "sum"), partidos=("gk_games", "sum"), paradas=("gk_saves", "sum"),
        tiros_a_puerta=("gk_shots_on_target_against", "sum"), goles_recibidos=("gk_goals_against", "sum"),
        porterias_cero=("gk_clean_sheets", "sum"))
    c = c[c["minutos"] >= min_minutos].copy()
    c["pct_paradas"] = 100 * c["paradas"] / c["tiros_a_puerta"]
    c["pct_porterias_cero"] = 100 * c["porterias_cero"] / c["partidos"]
    c["goles_recibidos_90"] = c["goles_recibidos"] / (c["minutos"] / 90)
    return c.sort_values("pct_paradas", ascending=False)


def estabilidad(df: pd.DataFrame, columna: str, min_minutos: int = 1500,
                minutos: str = "minutes") -> tuple[float, int, pd.DataFrame]:
    """¿La métrica es una característica del jugador o ruido? Correlación entre una temporada y la siguiente.

    `df` debe ser de UNA liga (una fila por jugador-temporada).
    Se emparejan las temporadas t y t+1 del mismo jugador, ambas con `min_minutos`. Si la métrica
    mide algo del jugador, quien sale alto un año tiende a salir alto al siguiente (r claramente > 0). Si r ≈ 0, el
    número de un año dice muy poco del siguiente: es ruido, o depende de cosas ajenas al jugador (compañeros, rivales).
    Devuelve (r de Pearson, número de pares, tabla de pares).
    """
    x = df[(df[minutos] >= min_minutos) & df[columna].notna()][["id_jugador", "player", "temporada_inicio", columna]]
    pares = x.merge(x.assign(temporada_inicio=x["temporada_inicio"] - 1), on=["id_jugador", "temporada_inicio"],
                    suffixes=("", "_siguiente"))
    if len(pares) < 3:
        return np.nan, len(pares), pares
    r = pearsonr(pares[columna], pares[f"{columna}_siguiente"]).statistic
    return float(r), len(pares), pares


def agregar_ppg_extra(jt: pd.DataFrame, equipos: pd.DataFrame) -> pd.DataFrame:
    """Agrega `ppg_extra` = puntos por partido del equipo CON el jugador en cancha − puntos por partido del equipo.

    Solo para jugadores con un único equipo en la temporada (con dos, "su equipo" es ambiguo y FBref promedia): para
    los demás queda vacío. También vacío antes de 2014-15, cuando FBref no tiene puntos por partido con el jugador.
    """
    ppg_equipo = equipos.set_index(["season", "team_id"])["ppg"]
    del_equipo = ppg_equipo.reindex(list(zip(jt["season"], jt["equipo_principal_id"]))).to_numpy()
    return jt.assign(ppg_extra=np.where(jt["n_equipos"] == 1, jt["points_per_game"] - del_equipo, np.nan))


def mejor_fantasy_por_equipo(jt: pd.DataFrame, temporada_inicio: int) -> pd.DataFrame:
    """El jugador con más puntos fantasy de cada equipo en una temporada, y qué parte de los puntos del equipo hizo.

    Los puntos de un jugador traspasado cuentan solo para su equipo principal (el de más minutos): es una aproximación,
    porque la tabla jugador-temporada ya sumó sus dos equipos.
    """
    u = jt[jt["temporada_inicio"] == temporada_inicio]
    total = u.groupby("equipo_principal")["pts_total"].sum()
    mejores = u.sort_values("pts_total", ascending=False).groupby("equipo_principal").head(1)
    return (mejores.assign(pts_equipo=mejores["equipo_principal"].map(total),
                           parte_del_equipo=mejores["pts_total"] / mejores["equipo_principal"].map(total))
            .sort_values("parte_del_equipo", ascending=False))


def desacuerdo_goles_porteros(jt: pd.DataFrame) -> pd.DataFrame:
    """Por temporada: porteros con goles recibidos en `keepers` distintos de su onGA en `playingtime`.

    Las dos cifras deberían ser iguales (un portero está en cancha en todos los goles que recibe su equipo mientras
    juega). Donde no coinciden, FBref se contradice; sirve para saber en qué temporadas confiar menos en ese dato.
    """
    p = jt[jt["gk_games"].notna() & jt["on_goals_against"].notna()]
    d = p.assign(difiere=p["gk_goals_against"] != p["on_goals_against"])
    return d.groupby("temporada_inicio")["difiere"].agg(no_coinciden="sum", porteros="size").reset_index()


# Métricas que se comparan entre ligas. Cada una es una serie por temporada (mediana de los equipos para las de
# plantilla; total de la liga para las de portero) más un resumen de una cifra por liga.
SERIES_COMPARABLES = {
    "jugadores_80pct": "Jugadores para el 80% de los minutos",
    "pct_min_extranjeros": "% de minutos de extranjeros",
    "pct_min_sub21": "% de minutos de jugadores sub-21",
    "edad_ponderada": "Edad media ponderada por minutos",
    "dependencia_goleador": "Dependencia del máximo goleador",
    "pct_paradas": "% de paradas de la liga",
    "goles_recibidos_por_partido": "Goles recibidos por partido",
    "pct_porterias_cero": "% de partidos con portería a cero",
}


def comparativa(filas: pd.DataFrame, jt: pd.DataFrame, ligas: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Calcula, para varias ligas, las mismas series por temporada y el mismo resumen de una cifra por liga.

    Devuelve (series, resumen):
      series   una fila por liga-temporada con las columnas de SERIES_COMPARABLES (medianas de los equipos para las de
               plantilla y dependencia; totales de la liga para las de portero, ver `porteros_liga`).
      resumen  una fila por liga con tamaño del panel, las tres correlaciones de Spearman con los puntos por partido
               (rotación, dependencia, goles) y las estabilidades año a año (on-off, puntos con él, referencia
               individual, % de paradas, % de porterías a cero).

    Las estabilidades y correlaciones se calculan exactamente con las mismas funciones que los notebooks por liga, así
    que la comparativa no puede desviarse de lo que muestra cada liga por separado.
    """
    from scipy.stats import spearmanr

    series, resumen = [], []
    for nombre in ligas:
        f, j = filas[filas["league"] == nombre], jt[jt["league"] == nombre]
        equipos = resumen_equipos(f, nombre)
        de_equipos = ["jugadores_80pct", "pct_min_extranjeros", "pct_min_sub21", "edad_ponderada",
                      "dependencia_goleador"]
        s = equipos.groupby("temporada_inicio")[de_equipos].median()
        s = s.join(porteros_liga(j, nombre)[["pct_paradas", "goles_recibidos_por_partido", "pct_porterias_cero"]])
        series.append(s.assign(league=nombre).reset_index())

        j = agregar_ppg_extra(j, equipos)
        porteros = j[j["gk_games"].notna()]
        rho = lambda col: spearmanr(equipos[col], equipos["ppg"], nan_policy="omit").statistic
        estab = lambda datos, col, **kw: estabilidad(datos, col, **kw)[0]
        resumen.append({
            "league": nombre, "temporadas": j["season"].nunique(), "jugadores": j["id_jugador"].nunique(),
            "equipos": equipos["team_id"].nunique(),
            "rho_rotacion_puntos": rho("jugadores_80pct"), "rho_dependencia_puntos": rho("dependencia_goleador"),
            "rho_goles_puntos": rho("goles"),
            "estab_on_off": estab(j, "plus_minus_wowy"), "estab_ppg_extra": estab(j, "ppg_extra"),
            "estab_referencia": estab(j[j["pos_principal"] == "FW"], "goals_pens_per90"),
            "estab_paradas": estab(porteros, "gk_save_pct", minutos="gk_minutes"),
            "estab_porterias_cero": estab(porteros, "gk_clean_sheets_pct", minutos="gk_minutes"),
        })
    return pd.concat(series, ignore_index=True), pd.DataFrame(resumen)


POSICIONES = ["GK", "DF", "MF", "FW"]


def comparativa_posiciones(jt: pd.DataFrame, ligas: list[str], min_minutos: int = 1500) -> pd.DataFrame:
    """Compara las ligas DENTRO de cada posición, ya con el fantasy completo (ofensivo + defensivo).

    `jt` tiene que venir de `fantasy.puntos_defensivos`. Solo se usan las filas con `def_completo`: antes de 2014-15 no
    hay goles recibidos con el jugador en cancha y antes de 2016-17 no hay penales atajados, así que incluirlas
    mezclaría "puntuó poco" con "no hay dato".

    Una fila por liga y posición:
      jugadores, temporadas      tamaño de la muestra (titulares con `min_minutos`)
      pts_ofensivos, pts_defensivos, pts_completo   medias por temporada
      pct_defensivo              qué parte del puntaje total es defensiva
      porterias_cero_partido     porterías a cero por partido jugado (reales en porteros, estimadas en el resto)
      estab_ofensivo             correlación año a año del puntaje SOLO ofensivo por jornada
      estab_completo             la misma, ya con la parte defensiva. La comparación entre las dos columnas es la
                                 prueba de si añadir lo defensivo acerca el puntaje a medir al jugador.
      estab_percentil            la misma sobre el PERCENTIL del fantasy completo dentro de su liga-temporada-posición.
                                 Quita de en medio el ambiente de la liga y del año, así que es la cifra a usar para
                                 comparar ligas entre sí; `estab_completo` sigue siendo la de los puntos tal cual.
      pares                      pares de temporadas consecutivas con que se calcularon las estabilidades
    """
    if "pct_completo" not in jt:
        from futbol_bd import fantasy
        jt = jt.assign(pct_completo=fantasy.percentil_completo(jt))
    filas = []
    for nombre in ligas:
        j = jt[(jt["league"] == nombre) & jt["def_completo"]]
        titulares = j[j["minutes"] >= min_minutos]
        for pos in POSICIONES:
            p, t = j[j["pos_principal"] == pos], titulares[titulares["pos_principal"] == pos]
            r_ofensivo, _, _ = estabilidad(p, "pts_por_jornada", min_minutos)
            r_completo, pares, _ = estabilidad(p, "pts_completo_por_jornada", min_minutos)
            r_percentil, _, _ = estabilidad(p, "pct_completo", min_minutos)
            filas.append({
                "league": nombre, "posicion": pos, "jugadores": t["id_jugador"].nunique(),
                "temporadas": len(t), "pts_ofensivos": t["pts_total"].mean(),
                "pts_defensivos": t["pts_defensivos"].mean(), "pts_completo": t["pts_total_completo"].mean(),
                "pct_defensivo": 100 * t["pts_defensivos"].sum() / t["pts_total_completo"].sum(),
                "porterias_cero_partido": (t["porterias_cero"] / t["games"].where(t["games"] > 0)).mean(),
                "estab_ofensivo": r_ofensivo, "estab_completo": r_completo, "estab_percentil": r_percentil,
                "pares": pares,
            })
    return pd.DataFrame(filas)


def origen_porteria_cero(jt: pd.DataFrame, min_minutos: int = 1500) -> pd.DataFrame:
    """¿La portería a cero es del jugador o de su equipo? Compara quien se queda con quien cambia de equipo.

    La idea: si dejar la portería a cero fuera una cualidad del jugador, se la llevaría al mudarse y la correlación
    entre temporadas consecutivas sería parecida en los dos casos. Si es sobre todo del equipo, al cambiar de club la
    correlación se desploma. Es la misma pregunta que el proyecto le hace al on-off, aplicada a la mitad defensiva.

    Una fila por posición con la correlación año a año de las porterías a cero por partido, separando a quien siguió
    en el mismo equipo de quien cambió, y cuánto se pierde entre una y otra.
    """
    d = jt[jt["def_completo"]].copy()
    d["pc_partido"] = d["porterias_cero"] / d["games"].where(d["games"] > 0)
    filas = []
    for pos in POSICIONES:
        p = d[d["pos_principal"] == pos]
        _, _, pares = estabilidad(p, "pc_partido", min_minutos)
        equipos = p[["id_jugador", "temporada_inicio", "equipo_principal_id"]]
        pares = pares.merge(equipos, on=["id_jugador", "temporada_inicio"]).merge(
            equipos.assign(temporada_inicio=equipos["temporada_inicio"] - 1),
            on=["id_jugador", "temporada_inicio"], suffixes=("", "_siguiente"))
        sigue = pares["equipo_principal_id"] == pares["equipo_principal_id_siguiente"]
        r = lambda sub: sub["pc_partido"].corr(sub["pc_partido_siguiente"]) if len(sub) >= 3 else np.nan
        filas.append({"posicion": pos, "r_mismo_equipo": r(pares[sigue]), "n_mismo_equipo": int(sigue.sum()),
                      "r_cambio_equipo": r(pares[~sigue]), "n_cambio_equipo": int((~sigue).sum())})
    res = pd.DataFrame(filas)
    res["caida"] = res["r_mismo_equipo"] - res["r_cambio_equipo"]
    return res


def escalera_ligas(jt: pd.DataFrame, ligas: list[str], min_minutos: int = 1500) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Ordena las 7 ligas por dificultad usando a los jugadores que se mudan de una a otra.

    La idea: el percentil del fantasy completo se calcula DENTRO de cada liga-temporada-posición, así que el percentil
    medio de toda liga es 50 y compararlos entre sí no dice nada. Lo que sí informa es qué le pasa a un jugador cuando
    cambia de liga: si al llegar a la Premier su percentil cae, es que ahí los rivales por el puesto son mejores.

    **El control, que es lo que hace creíble el número**: quien se muda fue elegido por su última temporada, así que su
    percentil baja al siguiente año por pura regresión a la media, se cambie de liga o no. Por eso el punto de
    comparación no es "quedarse igual" sino **quien cambió de club DENTRO de su liga**: mismo tipo de jugador, misma
    selección, mismo trastorno de mudarse, sin cambiar de liga. Sobre ese grupo se ajusta la recta
    percentil_siguiente = a + b·percentil, y el residuo de cada mudanza internacional se mide contra ella.

    Con los residuos se ajusta de una sola vez `residuo = dificultad(origen) − dificultad(destino)`, una incógnita por
    liga (solo se identifican las diferencias, así que la solución se centra en media cero). Un jugador que sube de una
    liga de dificultad −3 a una de +8 pierde 11 percentiles.

    Lo que el número NO controla: la edad del jugador, el cambio de rol o de nivel de equipo, y el hecho de que quien
    se muda a una liga concreta no es una muestra al azar. Léase como una ordenación aproximada, con su error estándar.

    Devuelve (movimientos, escalera):
      movimientos  una fila por cambio de liga, con el percentil antes y después, el esperado y el residuo
      escalera     una fila por liga con `dificultad`, su error estándar y cuántas llegadas y salidas la sostienen
    """
    if "pct_completo" not in jt:
        from futbol_bd import fantasy
        jt = jt.assign(pct_completo=fantasy.percentil_completo(jt))
    columnas = ["id_jugador", "player", "temporada_inicio", "season", "league", "equipo_principal",
                "equipo_principal_id", "pos_principal", "pct_completo"]
    x = jt[(jt["minutes"] >= min_minutos) & jt["pct_completo"].notna() & jt["league"].isin(ligas)][columnas]
    pares = x.merge(x.assign(temporada_inicio=x["temporada_inicio"] - 1), on=["id_jugador", "temporada_inicio"],
                    suffixes=("", "_sig"))

    control = pares[(pares["league"] == pares["league_sig"])
                    & (pares["equipo_principal_id"] != pares["equipo_principal_id_sig"])]
    pendiente, corte = np.polyfit(control["pct_completo"], control["pct_completo_sig"], 1)
    mov = pares[pares["league"] != pares["league_sig"]].copy()
    mov["esperado"] = corte + pendiente * mov["pct_completo"]
    mov["residuo"] = mov["pct_completo_sig"] - mov["esperado"]

    # Una columna por liga: +1 si es el origen, −1 si es el destino. La matriz es deficiente de rango (sumar una
    # constante a todas las dificultades no cambia nada), y `lstsq` devuelve la solución de norma mínima, que es
    # justamente la centrada en cero.
    X = np.column_stack([(mov["league"] == nombre).astype(float) - (mov["league_sig"] == nombre).astype(float)
                         for nombre in ligas])
    coef = np.linalg.lstsq(X, mov["residuo"].values, rcond=None)[0]
    residuos = mov["residuo"].values - X @ coef
    grados = len(mov) - (len(ligas) - 1)                     # una dificultad no se estima: está fijada por el centrado
    ee = np.sqrt(np.diag(np.linalg.pinv(X.T @ X) * (residuos @ residuos / grados)))
    escalera = pd.DataFrame({
        "league": ligas, "dificultad": coef, "ee": ee,
        "llegadas": [int((mov["league_sig"] == n).sum()) for n in ligas],
        "salidas": [int((mov["league"] == n).sum()) for n in ligas],
    }).sort_values("dificultad", ascending=False, ignore_index=True)
    return mov, escalera


def plantel_vs_puntos(filas: pd.DataFrame, jt: pd.DataFrame, ligas: list[str]) -> pd.DataFrame:
    """¿El fantasy completo del plantel explica los puntos del equipo? Una fila por liga, comparables entre sí.

    Con puntos brutos esta pregunta no se podía comparar entre ligas (una liga más goleadora reparte más puntos); con
    el percentil sí, porque un 80 significa lo mismo en todas.

    Dos medidas del plantel, las dos por equipo-temporada:
      pct_plantel   percentil medio de sus jugadores, ponderado por minutos (qué tan bueno es el plantel que juega)
      top20         cuántos jugadores tuvo en el 20% superior de su liga-temporada-posición (cuántas figuras tuvo)

    Cada jugador se asigna a su `equipo_principal` (el de más minutos esa temporada en esa liga): quien fue traspasado
    a mitad de año cuenta una sola vez, en el equipo donde más jugó.
    """
    from scipy.stats import spearmanr

    if "pct_completo" not in jt:
        from futbol_bd import fantasy
        jt = jt.assign(pct_completo=fantasy.percentil_completo(jt))
    salida = []
    for nombre in ligas:
        equipos = resumen_equipos(filas[filas["league"] == nombre], nombre)
        j = jt[(jt["league"] == nombre) & jt["pct_completo"].notna()]
        plantel = j.groupby(["temporada_inicio", "equipo_principal_id"]).apply(
            lambda d: pd.Series({"pct_plantel": np.average(d["pct_completo"], weights=d["minutes"]),
                                 "top20": int((d["pct_completo"] >= 80).sum())}),
            include_groups=False).reset_index()
        m = equipos.merge(plantel, left_on=["temporada_inicio", "team_id"],
                          right_on=["temporada_inicio", "equipo_principal_id"])
        m = m[m["ppg"].notna()]
        rho = lambda col: float(spearmanr(m[col], m["ppg"], nan_policy="omit").statistic)
        salida.append({"league": nombre, "equipos_temporada": len(m), "rho_plantel_puntos": rho("pct_plantel"),
                       "rho_top20_puntos": rho("top20")})
    return pd.DataFrame(salida)
