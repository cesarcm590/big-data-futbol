"""
El calendario internacional de aquí al Mundial 2030: qué se juega, cuándo y qué choca con qué.

POR QUÉ ES UN CSV A MANO Y NO UN SCRAPEO
----------------------------------------
No hay una fuente única y descargable del calendario a cuatro años vista: FIFA publica las ventanas en un PDF, cada
confederación anuncia sus torneos por su cuenta y varias fechas todavía no están cerradas. Así que
`referencia/calendario_internacional.csv` se mantiene a mano, con dos columnas que son la mitad de su valor:

    confirmado   'si'           fecha anunciada oficialmente
                 'provisional'  el torneo está confirmado pero sus fechas exactas no
                 'pendiente'    ni siquiera hay fechas anunciadas; el rango es una estimación nuestra
    fuente       de dónde salió

Un calendario a 2030 SIEMPRE tendrá filas provisionales. Lo que no puede pasar es que no se distingan: sin esas dos
columnas, una fecha inventada y una oficial se ven igual. Las funciones de aquí nunca mezclan unas con otras sin
decirlo.
"""
from pathlib import Path

import pandas as pd

RUTA = Path(__file__).resolve().parents[1] / "referencia" / "calendario_internacional.csv"
MUNDIAL_2030 = pd.Timestamp("2030-06-08")


def cargar_calendario(ruta: Path | str = RUTA) -> pd.DataFrame:
    """Lee el calendario con las fechas ya como fechas y la duración en días."""
    d = pd.read_csv(ruta, parse_dates=["inicio", "fin"])
    d["dias"] = (d["fin"] - d["inicio"]).dt.days + 1
    d["es_provisional"] = d["confirmado"].ne("si")   # provisional y pendiente: ambas hay que señalarlas
    return d.sort_values("inicio").reset_index(drop=True)


def solapamientos(d: pd.DataFrame, solo_torneos: bool = True) -> pd.DataFrame:
    """Pares de competiciones cuyas fechas se pisan.

    Es la pregunta útil de un calendario: no cuántos torneos hay, sino cuáles compiten por los mismos jugadores en
    las mismas semanas. Se comparan todos contra todos porque son pocas filas; con miles habría que ordenar por
    fecha y barrer una sola vez.
    """
    t = d[d["tipo"] == "torneo"] if solo_torneos else d
    filas = []
    for i, a in t.iterrows():
        for j, b in t.iterrows():
            if j <= i or a["competicion"] == b["competicion"]:
                continue
            ini, fin = max(a["inicio"], b["inicio"]), min(a["fin"], b["fin"])
            if ini <= fin:
                filas.append({
                    "competicion_a": f"{a['competicion']} {a['edicion']}",
                    "competicion_b": f"{b['competicion']} {b['edicion']}",
                    "desde": ini, "hasta": fin, "dias_solapados": (fin - ini).days + 1,
                    "alguna_provisional": bool(a["es_provisional"] or b["es_provisional"]),
                })
    return pd.DataFrame(filas).sort_values("dias_solapados", ascending=False).reset_index(drop=True)


def que_ocupa_cada_ventana(d: pd.DataFrame) -> pd.DataFrame:
    """Para cada ventana FIFA, qué torneo cae dentro. Una ventana sin torneo se juega con amistosos o eliminatorias.

    Sirve para responder "¿qué se juega?" sin mirar el calendario a ojo: una ventana ocupada por una fase final
    exige a los jugadores mucho más que una de amistosos, aunque en el calendario ocupen el mismo hueco.
    """
    ventanas, torneos = d[d["tipo"] == "ventana"], d[d["tipo"] == "torneo"]
    filas = []
    for _, v in ventanas.iterrows():
        dentro = torneos[(torneos["inicio"] <= v["fin"]) & (torneos["fin"] >= v["inicio"])]
        filas.append({
            "ventana": v["edicion"], "inicio": v["inicio"], "fin": v["fin"], "dias": v["dias"],
            "partidos": v["fase"],
            "ocupada_por": " + ".join(f"{r.competicion} ({r.fase})" for r in dentro.itertuples()) or "—",
        })
    return pd.DataFrame(filas)


def cuenta_atras(d: pd.DataFrame, hoy: pd.Timestamp | None = None) -> pd.DataFrame:
    """Lo que queda por jugarse antes del Mundial, con los días que faltan."""
    hoy = pd.Timestamp(hoy or pd.Timestamp.today().normalize())
    t = d[(d["tipo"] == "torneo") & (d["fin"] >= hoy) & (d["inicio"] < MUNDIAL_2030)].copy()
    t["dias_para_empezar"] = (t["inicio"] - hoy).dt.days.clip(lower=0)
    t["en_curso"] = (t["inicio"] <= hoy) & (t["fin"] >= hoy)
    return t[["competicion", "edicion", "fase", "confederacion", "inicio", "fin",
              "dias_para_empezar", "en_curso", "es_provisional", "que_se_juega"]].reset_index(drop=True)
