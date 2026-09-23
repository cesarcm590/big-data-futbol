"""
Apolonio SOBRE LA CANCHA: posiciones medias de los jugadores en un partido, con eventos de StatsBomb.

Qué cambia respecto al notebook 17
----------------------------------
Allí el plano era un **espacio de perfil** (goles/90 contra asistencias/90) porque el panel de FBref no trae
posiciones. Aquí el plano es la cancha de verdad, que es el uso original de los diagramas ponderados en fútbol
("dominant region", Taki y Hasegawa 2000). La diferencia práctica importa para el cálculo: en el espacio de perfil
había que llevar los dos ejes a [0, 1] porque uno llegaba a 1 y el otro a 0.6 y la distancia habría pesado más en el
de números grandes; **en la cancha no se normaliza nada**, porque los dos ejes ya están en la misma unidad (metros) y
un metro a lo largo vale lo mismo que un metro a lo ancho.

Lo que se puede y lo que NO se puede leer en este mapa
-----------------------------------------------------
Cada sitio es la **posición media** de un jugador durante el partido, calculada con los eventos en los que tocó el
balón. Eso NO es dónde estuvo: es el centro de sus acciones. Un lateral que sube y baja toda la banda aparece a media
altura, en un lugar donde quizá no estuvo nunca. Por eso cada jugador trae también la dispersión de sus acciones
(`x_desv`, `y_desv`): sin ella el punto engaña.

El peso es `acciones_exitosas`, que es sobre todo **participación con éxito**. Un mediocentro que toca 100 balones
pesará más que un delantero que toca 25, aunque el delantero haya decidido el partido. El área de la celda mide
territorio de influencia, no calidad — lo mismo que ya se advertía en el mapa de perfiles.

Coordenadas de StatsBomb: cancha de 120 × 80, con el equipo SIEMPRE atacando de izquierda a derecha (x = 0 es su
propia portería, x = 120 la contraria) e y = 40 en el centro. Verificado con los porteros, que salen en x ≈ 9, y ≈ 40.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

LARGO, ANCHO = 120.0, 80.0
LIMITES = ((0.0, LARGO), (0.0, ANCHO))

# Tipos de evento que cuentan como una acción del jugador con el balón (se excluye 'Ball Receipt*', que duplica cada
# pase recibido, y 'Pressure', que no es una acción con balón).
TIPOS_ACCION = ("Pass", "Carry", "Dribble", "Shot", "Ball Recovery", "Interception", "Clearance", "Block",
                "Duel", "Goal Keeper", "Miscontrol", "Dispossessed", "Foul Won")


def _exito(eventos: pd.DataFrame) -> pd.Series:
    """¿La acción salió bien? Una regla por tipo, con los valores que usa StatsBomb en cada columna de desenlace.

    En StatsBomb un pase COMPLETADO no trae desenlace (la columna queda vacía) y solo los fallidos se marcan
    ('Incomplete', 'Out', ...), así que ahí la ausencia de dato sí significa éxito — al revés que en el panel de FBref.
    """
    col = lambda c: eventos[c] if c in eventos else pd.Series(np.nan, index=eventos.index)
    tipo = eventos["type"]
    gano = lambda c: col(c).astype("string").str.startswith(("Won", "Success")).fillna(False)
    return (
        ((tipo == "Pass") & col("pass_outcome").isna())
        | ((tipo == "Carry"))
        | ((tipo == "Dribble") & (col("dribble_outcome").astype("string") == "Complete"))
        | ((tipo == "Shot") & col("shot_outcome").astype("string").isin(["Goal", "Saved"]))
        | ((tipo == "Ball Recovery") & col("ball_recovery_recovery_failure").isna())
        | ((tipo == "Interception") & gano("interception_outcome"))
        | (tipo.isin(["Clearance", "Block", "Foul Won"]))
        | ((tipo == "Duel") & gano("duel_outcome"))
    )


def once_inicial(eventos: pd.DataFrame) -> tuple[dict[str, set], dict[str, str]]:
    """{equipo: {player_id del once titular}} y la formación, leídos del evento 'Starting XI' de StatsBomb."""
    once, formacion = {}, {}
    for _, fila in eventos[eventos["type"] == "Starting XI"].iterrows():
        tacticas = fila["tactics"]
        if isinstance(tacticas, dict):
            once[fila["team"]] = {j["player"]["id"] for j in tacticas.get("lineup", [])}
            formacion[fila["team"]] = str(tacticas.get("formation", ""))
    return once, formacion


def posiciones_por_partido(eventos: pd.DataFrame, min_acciones: int = 20) -> pd.DataFrame:
    """Una fila por jugador de un partido: dónde actuó en promedio, cuánto se movió y cuántas acciones le salieron.

    `min_acciones` deja fuera a los suplentes que entraron poco: con 5 acciones la posición media es ruido y su celda
    del diagrama sería un accidente. 20 acciones ≈ un jugador que estuvo media hora larga. Además se marca quién fue
    `titular`, porque para dibujar el reparto de la cancha lo que interesa es el once: si se incluyen los cambios, el
    mapa acaba con 13 o 14 celdas para 11 puestos, y dos de ellas son el mismo puesto en dos ratos distintos.

    Columnas: match_id, team, player, player_id, posicion (la más frecuente), titular, formacion, acciones, exitosas,
    pct_exito, x, y (medias), x_desv, y_desv (dispersión), minuto_primero, minuto_ultimo.
    """
    con_lugar = eventos[eventos["location"].notna() & eventos["type"].isin(TIPOS_ACCION)
                        & eventos["player"].notna()].copy()
    lugar = pd.DataFrame(con_lugar["location"].tolist(), columns=["x", "y"], index=con_lugar.index)
    con_lugar["x"], con_lugar["y"] = lugar["x"], lugar["y"]
    con_lugar["exito"] = _exito(con_lugar)

    d = con_lugar.groupby(["match_id", "team", "player", "player_id"], sort=False).agg(
        posicion=("position", lambda s: s.mode().iloc[0] if len(s.mode()) else "ND"),
        acciones=("x", "size"), exitosas=("exito", "sum"),
        x=("x", "mean"), y=("y", "mean"), x_desv=("x", "std"), y_desv=("y", "std"),
        minuto_primero=("minute", "min"), minuto_ultimo=("minute", "max"),
    ).reset_index()
    d["pct_exito"] = 100 * d["exitosas"] / d["acciones"]
    once, formacion = once_inicial(eventos)
    d["titular"] = [pid in once.get(eq, set()) for eq, pid in zip(d["team"], d["player_id"])]
    d["formacion"] = d["team"].map(formacion)
    return d[d["acciones"] >= min_acciones].reset_index(drop=True)


def sitios_de_equipo(posiciones: pd.DataFrame, match_id: int, equipo: str,
                     solo_titulares: bool = True) -> pd.DataFrame:
    """Los jugadores de un equipo en un partido, listos para pasarlos a `apolonio.etiquetar`.

    El peso es `exitosas` recortado a un mínimo de 1: el modo multiplicativo divide entre el peso, así que un cero lo
    rompería. Recortar en vez de eliminar mantiene al jugador en el mapa con la celda más pequeña posible.
    """
    d = posiciones[(posiciones["match_id"] == match_id) & (posiciones["team"] == equipo)]
    if solo_titulares and "titular" in d and d["titular"].any():
        d = d[d["titular"]]
    return d.assign(peso=d["exitosas"].clip(lower=1)).sort_values("exitosas", ascending=False).reset_index(drop=True)


def area_dominada(posiciones: pd.DataFrame, modo: str = "multiplicativo", resolucion: int = 200) -> pd.Series:
    """Fracción de la cancha que domina cada jugador, dentro de su propio equipo y partido.

    Se calcula equipo por equipo (no los 22 juntos): un diagrama con los dos equipos mezclados respondería "quién
    llega antes", que es otra pregunta y necesitaría velocidades, no posiciones medias. Aquí la pregunta es cómo se
    reparte un equipo su propia cancha.
    """
    from futbol_bd import apolonio

    trozos = []
    for (match_id, equipo), d in posiciones.groupby(["match_id", "team"], sort=False):
        pesos = d["exitosas"].clip(lower=1).to_numpy()
        etiquetas, _, _ = apolonio.etiquetar(d[["x", "y"]].to_numpy(), pesos, modo=modo, resolucion=resolucion,
                                             limites=LIMITES)
        trozos.append(pd.Series(apolonio.areas(etiquetas, len(d)), index=d.index))
    return pd.concat(trozos).reindex(posiciones.index)


def dibujar_cancha(ax, color="#c3c2b7", linewidth=1.2):
    """Las líneas de una cancha de 120 × 80, para dibujar el diagrama encima."""
    ax.plot([0, 0, LARGO, LARGO, 0], [0, ANCHO, ANCHO, 0, 0], color=color, linewidth=linewidth, zorder=4)
    ax.plot([LARGO / 2, LARGO / 2], [0, ANCHO], color=color, linewidth=linewidth, zorder=4)
    circulo = np.linspace(0, 2 * np.pi, 120)
    ax.plot(LARGO / 2 + 10 * np.cos(circulo), ANCHO / 2 + 10 * np.sin(circulo), color=color, linewidth=linewidth,
            zorder=4)
    for x0, signo in ((0, 1), (LARGO, -1)):
        for fondo, alto in ((18, 44), (6, 20)):          # área grande y área chica
            ax.plot([x0, x0 + signo * fondo, x0 + signo * fondo, x0],
                    [(ANCHO - alto) / 2, (ANCHO - alto) / 2, (ANCHO + alto) / 2, (ANCHO + alto) / 2],
                    color=color, linewidth=linewidth, zorder=4)
    ax.set_xlim(-2, LARGO + 2)
    ax.set_ylim(-2, ANCHO + 2)
    ax.set_aspect("equal")
    ax.axis("off")


# Los once puestos de StatsBomb agrupados en cuatro líneas, para resumir sin perder el sentido del mapa.
LINEA = {"Goalkeeper": "Portero", "Right Back": "Defensa", "Left Back": "Defensa", "Center Back": "Defensa",
         "Right Center Back": "Defensa", "Left Center Back": "Defensa", "Right Wing Back": "Defensa",
         "Left Wing Back": "Defensa", "Center Defensive Midfield": "Medio", "Right Defensive Midfield": "Medio",
         "Left Defensive Midfield": "Medio", "Center Midfield": "Medio", "Right Center Midfield": "Medio",
         "Left Center Midfield": "Medio", "Center Attacking Midfield": "Medio",
         "Right Attacking Midfield": "Medio", "Left Attacking Midfield": "Medio", "Right Midfield": "Medio",
         "Left Midfield": "Medio", "Right Wing": "Ataque", "Left Wing": "Ataque", "Center Forward": "Ataque",
         "Right Center Forward": "Ataque", "Left Center Forward": "Ataque", "Secondary Striker": "Ataque"}


def origen_del_area(posiciones: pd.DataFrame, partidos: pd.DataFrame) -> pd.DataFrame:
    """¿El área dominada es del jugador o de su PUESTO? Compara sus partidos seguidos según cuánto haya cambiado.

    Es la misma prueba que el proyecto le hace a la portería a cero en `liga.origen_porteria_cero`: si dominar mucha
    cancha fuera una cualidad del jugador, se la llevaría al cambiarlo de sitio.

    **El puesto de StatsBomb es muy granular** ("Right Center Midfield" contra "Center Midfield" son etiquetas
    distintas para casi lo mismo), así que comparar solo "mismo puesto" contra "otro puesto" metería en el segundo
    grupo movimientos de dos metros. Por eso se separan tres grados:

      mismo puesto          la misma etiqueta exacta
      misma línea           otra etiqueta dentro de portero / defensa / medio / ataque (p. ej. de central a lateral)
      cambió de línea       un cambio de verdad (p. ej. de medio a delantero)

    Se emparejan apariciones CONSECUTIVAS del mismo jugador (ordenadas por fecha) en las que fue titular.
    """
    d = posiciones[posiciones["titular"]].merge(partidos[["match_id", "match_date"]], on="match_id")
    d = d.sort_values(["player_id", "match_date"])
    siguiente = d.groupby("player_id").shift(-1)
    linea, linea_sig = d["posicion"].map(LINEA).fillna("Otro"), siguiente["posicion"].map(LINEA).fillna("Otro")
    pares = pd.DataFrame({
        "linea": linea, "area": d["area"], "area_sig": siguiente["area"],
        "grado": np.where(d["posicion"] == siguiente["posicion"], "mismo puesto",
                 np.where(linea == linea_sig, "misma línea", "cambió de línea")),
    }).dropna(subset=["area_sig"])

    def fila(nombre, sub):
        r = lambda g: (float(g["area"].corr(g["area_sig"])) if len(g) >= 10 else np.nan)
        salida = {"grupo": nombre, "pares": len(sub)}
        for grado in ("mismo puesto", "misma línea", "cambió de línea"):
            g = sub[sub["grado"] == grado]
            salida[f"r_{grado.replace(' ', '_')}"] = r(g)
            salida[f"n_{grado.replace(' ', '_')}"] = len(g)
        return salida

    filas = [fila(nombre, sub) for nombre, sub in pares.groupby("linea", sort=False)] + [fila("TODOS", pares)]
    return pd.DataFrame(filas)


def fiabilidad_del_area(posiciones: pd.DataFrame, partidos: pd.DataFrame, min_partidos: int = 10) -> dict:
    """¿El área de UN partido es ruido pero la MEDIA de un jugador sí dice algo? Fiabilidad por mitades.

    Se parten los partidos de cada jugador en pares e impares (por fecha), se promedia su área en cada mitad y se
    correlacionan las dos mitades. Es la prueba estándar de fiabilidad: si la media de media temporada predice la de
    la otra media, la cifra agregada mide algo aunque la de un partido sola sea ruido.

    Se corrige con Spearman-Brown, que estima la fiabilidad de la medida COMPLETA a partir de la de una mitad
    (r_completa = 2r / (1 + r)); sin esa corrección se subestima, porque cada mitad tiene la mitad de partidos.

    Se hace con cuatro versiones del área, cada una quitándole una explicación alternativa:
      area              tal cual. Una fiabilidad alta aquí puede ser solo el puesto: los porteros siempre dominan poco
                        y los medios mucho, así que cualquier medida que distinga puestos saldrá fiable.
      menos_puesto      área − media de su puesto. Si sigue siendo fiable, dos jugadores del mismo puesto ocupan
                        territorios distintos de forma consistente.
      menos_equipo      área − media de (equipo, línea). Quita además la forma de jugar del equipo, que es el control
                        que faltaría para no repetir el error de las porterías a cero (medir al equipo creyendo que
                        se mide al jugador).
      menos_equipo_puesto  área − media de (equipo, puesto exacto). Es un control EXCESIVO y se reporta como cota
                        inferior: en la mitad de los casos ese puesto de ese equipo lo ocupa casi siempre la misma
                        persona, así que restarle la media de la celda es restarle su propia señal.
    """
    d = posiciones[posiciones["titular"] & posiciones["area"].notna()].merge(
        partidos[["match_id", "match_date"]], on="match_id").sort_values(["player_id", "match_date"])
    d["orden"] = d.groupby("player_id").cumcount()
    d = d[d.groupby("player_id")["area"].transform("size") >= min_partidos].copy()
    linea = d["posicion"].map(LINEA).fillna("Otro")
    d["menos_puesto"] = d["area"] - d.groupby("posicion")["area"].transform("mean")
    d["menos_equipo"] = d["area"] - d.groupby([d["team"], linea])["area"].transform("mean")
    d["menos_equipo_puesto"] = d["area"] - d.groupby(["team", "posicion"])["area"].transform("mean")

    salida = {"jugadores": d["player_id"].nunique(),
              "partidos_por_jugador": float(d.groupby("player_id").size().mean())}
    for etiqueta in ("area", "menos_puesto", "menos_equipo", "menos_equipo_puesto"):
        columna = etiqueta
        mitades = d.pivot_table(index="player_id", columns=d["orden"] % 2, values=columna, aggfunc="mean").dropna()
        r = float(mitades[0].corr(mitades[1]))
        salida[f"r_{etiqueta}"] = r
        salida[f"r_{etiqueta}_corregida"] = 2 * r / (1 + r)   # Spearman-Brown: de media temporada a temporada entera
    return salida


def reparto_por_equipo(posiciones: pd.DataFrame) -> pd.DataFrame:
    """Cómo se reparte cada equipo su cancha en cada partido: qué tan concentrado está el dominio.

      mayor_celda  fracción de la cancha del jugador que más domina (1/11 = 0.09 sería un reparto perfectamente igual)
      gini         desigualdad del reparto entre los 11: 0 = todos igual, 1 = uno se lo queda todo
      jugadores    cuántos titulares entraron en el cálculo (siempre 11 si el partido está completo)
    """
    def gini(v):
        v = np.sort(np.asarray(v, dtype=float))
        n = len(v)
        return float((2 * np.arange(1, n + 1) - n - 1) @ v / (n * v.sum())) if v.sum() > 0 else np.nan

    d = posiciones[posiciones["titular"]]
    return d.groupby(["match_id", "team"], sort=False).agg(
        mayor_celda=("area", "max"), gini=("area", gini), jugadores=("area", "size"),
        formacion=("formacion", "first")).reset_index()
