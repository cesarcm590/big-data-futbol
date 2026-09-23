"""
Exporta las comparaciones con el percentil del fantasy completo (notebook 21) al JSON que lee la sección 8 de
`analisis.html`.

    python scripts/export_percentil_ligas.py       # -> dashboard-predicciones/analisis_percentil.json

Usa `fantasy.percentil_completo`, `liga.escalera_ligas`, `liga.comparativa_posiciones` y `liga.plantel_vs_puntos`:
las mismas funciones del notebook 21.
Contenido:
  meta         ligas, tamaños de muestra y la recta de control con la que se descuenta la regresión a la media
  control      percentil medio del año siguiente por tramo, para el grupo de control y para quien llegó a cada liga
  escalera     una fila por liga: dificultad, error estándar, intervalo de confianza y traspasos que la sostienen
  pares        diferencias entre pares de ligas con su intervalo de confianza (cuáles son distinguibles y cuáles no)
  estabilidad  correlación año a año de los puntos y del percentil, por posición (media de las 7 ligas)
  plantel      una fila por liga: correlación del plantel con los puntos del equipo
  lectura      textos de interpretación (los mismos bloques que muestra la página)
"""
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from futbol_bd import fantasy, liga, plantillas  # noqa: E402
from export_analisis_liga import limpio  # noqa: E402  (misma conversión a tipos de JSON)

LIGAS = ["Liga MX", "Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1", "Eredivisie"]
NOMBRE_POS = {"GK": "Porteros", "DF": "Defensas", "MF": "Mediocampistas", "FW": "Delanteros"}
SALIDA = RAIZ / "dashboard-predicciones" / "analisis_percentil.json"
# Los pares que vale la pena mirar: los extremos contra el resto y los dos vecinos del medio que NO se distinguen.
PARES = [("Premier League", "Liga MX"), ("Premier League", "Ligue 1"), ("Premier League", "La Liga"),
         ("La Liga", "Serie A"), ("Serie A", "Ligue 1")]
TRAMOS = [0, 25, 50, 75, 100]

LECTURA = {
    "percentil": (
        "El percentil del fantasy completo se calcula DENTRO de cada liga-temporada-posición, así que un 90 significa "
        "lo mismo en la Eredivisie 2016-17 que en la Premier 2024-25. Lo primero que hay que entender es qué NO se "
        "puede hacer con él: el percentil medio de toda liga es 50 por construcción, así que comparar percentiles "
        "medios entre ligas no dice nada. Lo que sí informa es qué le pasa a un jugador cuando se muda."),
    "estabilidad": (
        "El percentil se repite MENOS que los puntos en las siete ligas y las cuatro posiciones (delanteros 0.50 → "
        "0.37, mediocampistas 0.55 → 0.47, defensas 0.38 → 0.34, porteros 0.28 → 0.21). No es que sea peor: es más "
        "honesto. Los puntos brutos llevan dentro una parte estable que no es del jugador —el ambiente goleador de su "
        "liga y de su época— y que se repite sola. Parte de lo que parecía «este jugador repite» era «su contexto "
        "repite». Contra el percentil juega que comprime los extremos, y por eso castiga sobre todo a los delanteros."),
    "control": (
        "Quien se muda fue elegido por su última temporada, así que su percentil baja al año siguiente por pura "
        "regresión a la media, cambie de liga o no. Por eso el punto de comparación no es «quedarse igual» sino quien "
        "cambió de CLUB dentro de su misma liga: misma selección, mismo trastorno de mudarse, sin cambiar de liga. "
        "Ese grupo, viniendo del percentil 90, promedia 72 al año siguiente: esos 18 percentiles de caída no hay que "
        "cobrárselos a ninguna liga. Sobre esa recta, quien llega a la Premier queda por debajo y quien llega a la "
        "Ligue 1 por encima."),
    "escalera": (
        "Llegar a la Premier cuesta unos 8 percentiles más que cambiar de club dentro de la propia liga; la Liga MX "
        "está al otro extremo. El orden coincide con lo que cualquiera esperaría —buena señal de que el método no "
        "inventa nada—, pero lo que aporta es el TAMAÑO: entre la Premier y la Ligue 1 hay unos 10 percentiles, no "
        "40. Las llegadas y salidas cuentan otra historia: la Ligue 1 exporta casi el doble de lo que importa y la "
        "Premier importa dos veces y media lo que exporta."),
    "incertidumbre": (
        "La escalera no es una tabla de posiciones. Con 606 traspasos, los datos separan claramente a la Premier del "
        "resto (+9.8 sobre la Ligue 1, +4.7 sobre La Liga) y ponen a la Liga MX al final (+17.0 por debajo de la "
        "Premier, aunque con solo 23 traspasos), pero las cinco ligas de en medio NO se pueden ordenar entre sí. "
        "Además quedan confusiones que ningún control arregla: quien se muda cambia también de edad, de rol y de "
        "nivel de equipo."),
    "plantel": (
        "El percentil medio del plantel explica los puntos del equipo con 0.78 a 0.86 en las siete ligas, sin "
        "excepción. Buena parte de eso es mecánico (los puntos fantasy se construyen con goles y porterías a cero, "
        "que son los sucesos que ganan partidos), así que vale sobre todo como comprobación de que la medida no está "
        "rota. Lo informativo es que sea igual de alto en las siete, y que el promedio del plantel le gane al número "
        "de figuras en el 20% superior: pesa más un plantel entero decente que unos pocos jugadores excepcionales. "
        "El contraste con el on-off sigue en pie: lo que el jugador PRODUJO se corresponde con lo que logró el "
        "equipo; las medidas de «impacto» no."),
}


def curva(d, columna_x="pct_completo", columna_y="pct_completo_sig"):
    """Percentil medio del año siguiente por tramo del percentil de partida (los puntos de una línea de la gráfica)."""
    tramo = pd.cut(d[columna_x], TRAMOS)
    m = d.groupby(tramo, observed=False).agg(x=(columna_x, "mean"), y=(columna_y, "mean"), n=(columna_y, "size"))
    return [{"x": f.x, "y": f.y, "n": int(f.n)} for f in m.itertuples()]


def main():
    filas = plantillas.unir_tablas_extra(plantillas.limpiar_panel(plantillas.cargar_panel_crudo()))
    jt = fantasy.puntos_defensivos(fantasy.puntos_fantasy(plantillas.agregar_por_temporada(filas)))
    jt["pct_completo"] = fantasy.percentil_completo(jt)

    movimientos, escalera = liga.escalera_ligas(jt, LIGAS)

    # El grupo de control, recalculado igual que dentro de `escalera_ligas`, para poder dibujarlo.
    x = jt[(jt["minutes"] >= 1500) & jt["pct_completo"].notna()][
        ["id_jugador", "temporada_inicio", "league", "equipo_principal_id", "pct_completo"]]
    pares = x.merge(x.assign(temporada_inicio=x["temporada_inicio"] - 1), on=["id_jugador", "temporada_inicio"],
                    suffixes=("", "_sig"))
    control = pares[(pares["league"] == pares["league_sig"])
                    & (pares["equipo_principal_id"] != pares["equipo_principal_id_sig"])]
    pendiente, corte = np.polyfit(control["pct_completo"], control["pct_completo_sig"], 1)

    # Intervalos de confianza por remuestreo de los traspasos (el mismo bootstrap del notebook).
    rng = np.random.default_rng(11)
    X = np.column_stack([(movimientos["league"] == n).astype(float) - (movimientos["league_sig"] == n).astype(float)
                         for n in LIGAS])
    y = movimientos["residuo"].values
    muestras = np.array([np.linalg.lstsq(X[i], y[i], rcond=None)[0]
                         for i in (rng.integers(0, len(y), len(y)) for _ in range(2000))])
    ic = {n: np.percentile(muestras[:, j], [2.5, 97.5]) for j, n in enumerate(LIGAS)}
    escalera["ic_bajo"] = escalera["league"].map(lambda n: ic[n][0])
    escalera["ic_alto"] = escalera["league"].map(lambda n: ic[n][1])

    comparaciones = []
    for a, b in PARES:
        d = muestras[:, LIGAS.index(a)] - muestras[:, LIGAS.index(b)]
        bajo, alto = np.percentile(d, [2.5, 97.5])
        comparaciones.append({"a": a, "b": b, "diferencia": float(d.mean()), "ic_bajo": float(bajo),
                              "ic_alto": float(alto), "distinguible": bool(bajo > 0 or alto < 0)})

    comp_pos = liga.comparativa_posiciones(jt, LIGAS)
    estabilidad = comp_pos.groupby("posicion")[["estab_completo", "estab_percentil"]].mean().reindex(liga.POSICIONES)

    datos = {
        "meta": {
            "ligas": LIGAS, "posiciones": liga.POSICIONES, "nombres": NOMBRE_POS,
            "movimientos": len(movimientos), "control": len(control),
            "recta": {"corte": float(corte), "pendiente": float(pendiente),
                      "desde90": float(corte + pendiente * 90)},
            "generado": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "fuente": "FBref; percentil del fantasy completo dentro de liga-temporada-posición (900+ minutos)",
        },
        "control": {"grupo": curva(control),
                    "destinos": {n: curva(movimientos[movimientos["league_sig"] == n]) for n in LIGAS}},
        "escalera": escalera.to_dict("records"),
        "pares": comparaciones,
        "estabilidad": {"puntos": estabilidad["estab_completo"].tolist(),
                        "percentil": estabilidad["estab_percentil"].tolist()},
        "plantel": liga.plantel_vs_puntos(filas, jt, LIGAS).to_dict("records"),
        "lectura": LECTURA,
    }
    SALIDA.write_text(json.dumps(limpio(datos), ensure_ascii=False, separators=(",", ":"), allow_nan=False))
    print(f"Percentil entre ligas ({len(movimientos)} traspasos, {len(control):,} de control) -> "
          f"{SALIDA.relative_to(RAIZ)} ({SALIDA.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
