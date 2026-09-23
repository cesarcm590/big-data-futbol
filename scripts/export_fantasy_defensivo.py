"""
Exporta el fantasy defensivo (notebook 20) al JSON que lee la sección 7 de `analisis.html`.

    python scripts/export_fantasy_defensivo.py     # -> dashboard-predicciones/analisis_defensivo.json

Usa `fantasy.puntos_defensivos`, `fantasy.validar_porterias_cero`, `liga.comparativa_posiciones` y
`liga.origen_porteria_cero`: las mismas funciones del notebook 20, así que la web y el notebook no pueden decir cosas
distintas.
Contenido:
  meta         posiciones, ligas, cobertura y fecha de generación
  hueco        puntos medios por posición antes y después de sumar lo defensivo, y el desglose de dónde sale cada punto
  validacion   la estimación de porterías a cero contra la verdad de los porteros, por tramo de partidos jugados
  estabilidad  correlación año a año del puntaje ofensivo y del completo, por posición (media de las 7 ligas) y por liga
  origen       correlación de las porterías a cero según el jugador siga en su equipo o lo haya cambiado
  ligas        una fila por liga y posición (puntos y estabilidades)
  mejores      las 5 mejores temporadas de cada posición con el fantasy completo
  lectura      textos de interpretación (los mismos bloques que muestra la página)
"""
import json
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from futbol_bd import fantasy, liga, plantillas  # noqa: E402
from export_analisis_liga import limpio  # noqa: E402  (misma conversión a tipos de JSON)

LIGAS = ["Liga MX", "Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1", "Eredivisie"]
NOMBRE_POS = {"GK": "Porteros", "DF": "Defensas", "MF": "Mediocampistas", "FW": "Delanteros"}
SALIDA = RAIZ / "dashboard-predicciones" / "analisis_defensivo.json"

# Los ocho conceptos del desglose, en el orden en que se apilan (los tres últimos restan).
DESGLOSE = {"pts_aparicion": "Aparición", "pts_goles": "Goles", "pts_asistencias": "Asistencias",
            "pts_porteria_cero": "Portería a cero", "pts_paradas": "Paradas",
            "pts_penales_atajados": "Penal atajado", "pts_disciplina": "Tarjetas y penal fallado",
            "pts_goles_recibidos": "Goles recibidos"}

LECTURA = {
    "hueco": (
        "Con el puntaje ofensivo un portero titular promediaba 58.6 puntos por temporada y un defensa 58.7, contra "
        "101.5 de un delantero: no es que valieran la mitad, es que la mitad de su trabajo no se contaba. Al sumar lo "
        "defensivo el portero pasa a 100.8 y el defensa a 75.4, mientras el delantero se queda igual (no recibe "
        "puntos defensivos, por regla de FPL). En un portero, 42 de sus 101 puntos son defensivos; en un defensa, 17 "
        "de 75, casi todos de porterías a cero."),
    "validacion": (
        "FBref publica porterías a cero solo de los porteros, así que las de los jugadores de campo se ESTIMAN a "
        "partir de los goles que recibió su equipo con él en cancha, suponiendo que los goles de un partido siguen "
        "una Poisson. La estimación se puede comprobar en los porteros, que sí tienen la cifra real: correlación "
        "0.96 y sesgo de −1.7%. Pero el error de un jugador concreto es de ±1.5 porterías a cero por temporada de "
        "titular, es decir ±6 puntos fantasy: sirve para ordenar y promediar, no para leerlo como un dato exacto."),
    "estabilidad": (
        "La prueba de si el cambio mejora algo: al sumar lo defensivo, la correlación de una temporada a la siguiente "
        "sube en las SIETE ligas para porteros (+0.08 de media) y defensas (+0.07), no se mueve en mediocampistas "
        "(−0.01) y es idéntica en delanteros, que no reciben puntos defensivos. Es el patrón de una mejora real, no "
        "de ruido añadido. Aun así, 0.3-0.45 sigue muy por debajo del 0.5-0.66 de los delanteros."),
    "origen": (
        "Por qué sigue por debajo: la portería a cero es sobre todo del EQUIPO. Cuando un jugador se queda en su "
        "club, sus porterías a cero por partido se repiten (r de 0.37 a 0.50); cuando cambia de equipo, un defensa "
        "pierde 0.21 y un delantero 0.24. La excepción es el portero, que pierde solo 0.08: es el único que se lleva "
        "una parte apreciable consigo. Cuidado: quien cambia de club cambia también de rivales y de rol, y esa "
        "muestra es más pequeña."),
    "ligas": (
        "Los puntos defensivos disponibles no son iguales en todas partes: un portero de La Liga promedia 45.7 y uno "
        "de la Bundesliga 36.5, y entre los defensas la brecha es casi del doble (19.4 en La Liga contra 11.9 en "
        "Bundesliga y Eredivisie). Depende del ambiente goleador de la liga, no del jugador. Por eso comparar "
        "defensas de ligas distintas exige percentiles dentro de su liga-temporada-posición, no puntos brutos."),
}


def main():
    filas = plantillas.unir_tablas_extra(plantillas.limpiar_panel(plantillas.cargar_panel_crudo()))
    jt = fantasy.puntos_defensivos(fantasy.puntos_fantasy(plantillas.agregar_por_temporada(filas)))
    titulares = jt[jt["def_completo"] & (jt["minutes"] >= 1500)].copy()
    titulares["pts_disciplina"] = titulares["pts_tarjetas"] + titulares["pts_penales"]

    posiciones = liga.POSICIONES
    medias = titulares.groupby("pos_principal")[list(DESGLOSE)].mean().fillna(0).reindex(posiciones)
    totales = titulares.groupby("pos_principal")[["pts_total", "pts_defensivos", "pts_total_completo"]].mean(
        ).reindex(posiciones)
    validacion = fantasy.validar_porterias_cero(filas)
    por_liga = liga.comparativa_posiciones(jt, LIGAS)
    origen = liga.origen_porteria_cero(jt)

    # La estabilidad "de las 7 ligas" es la MEDIA de las siete, no un cálculo sobre todas juntas: juntarlas mezclaría
    # ligas con niveles de puntaje distintos y además emparejaría temporadas de un jugador que cambió de liga.
    estabilidad = por_liga.groupby("posicion")[["estab_ofensivo", "estab_completo"]].mean().reindex(posiciones)
    estabilidad["sube_en"] = por_liga.assign(sube=por_liga["estab_completo"] > por_liga["estab_ofensivo"]).groupby(
        "posicion")["sube"].sum().reindex(posiciones)

    cols_mejores = ["player", "equipo_principal", "league", "season", "pts_total", "pts_defensivos",
                    "pts_total_completo"]
    mejores = {pos: titulares[titulares["pos_principal"] == pos].nlargest(5, "pts_total_completo")[cols_mejores]
               .to_dict("records") for pos in posiciones}

    datos = {
        "meta": {
            "posiciones": posiciones, "nombres": NOMBRE_POS, "ligas": LIGAS,
            "temporadas_completas": int(jt.loc[jt["def_completo"], "temporada_inicio"].min()),
            "titulares": len(titulares), "porteros_validacion": int(validacion.loc["TODOS", "porteros"]),
            "generado": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "fuente": "FBref (tablas estándar, playingtime y keepers); reglas de puntuación adaptadas de FPL",
        },
        "hueco": {
            "conceptos": list(DESGLOSE.values()),
            "desglose": {pos: [medias.loc[pos, c] for c in DESGLOSE] for pos in posiciones},
            "ofensivo": [totales.loc[p, "pts_total"] for p in posiciones],
            "defensivo": [totales.loc[p, "pts_defensivos"] for p in posiciones],
            "completo": [totales.loc[p, "pts_total_completo"] for p in posiciones],
        },
        "validacion": {
            "tramos": [i for i in validacion.index if i != "TODOS"],
            "real": [validacion.loc[i, "real"] for i in validacion.index if i != "TODOS"],
            "estimada": [validacion.loc[i, "estimada"] for i in validacion.index if i != "TODOS"],
            "error": [validacion.loc[i, "error_absoluto"] for i in validacion.index if i != "TODOS"],
            "correlacion": validacion.loc["TODOS", "correlacion"],
            "sesgo_pct": 100 * validacion.loc["TODOS", "sesgo"] / validacion.loc["TODOS", "real"],
            "error_titular": validacion.loc["26+ (titular)", "error_absoluto"],
        },
        "estabilidad": {"ofensivo": estabilidad["estab_ofensivo"].tolist(),
                        "completo": estabilidad["estab_completo"].tolist(),
                        "sube_en": estabilidad["sube_en"].tolist()},
        "origen": origen.to_dict("records"),
        "ligas": por_liga.to_dict("records"),
        "mejores": mejores,
        "lectura": LECTURA,
    }
    SALIDA.write_text(json.dumps(limpio(datos), ensure_ascii=False, separators=(",", ":"), allow_nan=False))
    print(f"Fantasy defensivo ({len(titulares):,} temporadas de titular) -> {SALIDA.relative_to(RAIZ)} "
          f"({SALIDA.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
