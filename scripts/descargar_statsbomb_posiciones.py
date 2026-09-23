"""
Descarga eventos de StatsBomb Open Data y guarda SOLO el agregado por jugador-partido que necesita el mapa de cancha.

    python scripts/descargar_statsbomb_posiciones.py                 # La Liga y Premier 2015/16 (380 partidos c/u)
    python scripts/descargar_statsbomb_posiciones.py --liga laliga   # solo una

Salidas: data/processed/statsbomb_<clave>_posiciones.csv   una fila por jugador-partido (posición media, dispersión,
                                                           acciones y acciones exitosas)
         data/processed/statsbomb_<clave>_partidos.csv     una fila por partido (equipos, fecha, marcador)
         data/processed/statsbomb_<clave>_jugadores.csv    player_id -> nombre para mostrar

El nombre para mostrar sale de las ALINEACIONES, no de los eventos: en los eventos StatsBomb trae el nombre legal
completo, así que Messi aparece como "Lionel Andrés Messi Cuccittini" y quedarse con la última palabra daría
"Cuccittini". Las alineaciones traen `player_nickname` ("Messi", "Isco", "Cristiano Ronaldo"), que es como se le
conoce; cuando está vacío se usa el nombre completo.

Por qué se guarda el agregado y no los eventos: son ~8 MB de eventos por partido, 3 GB por temporada, y de todo eso el
análisis solo usa la posición media y el conteo de acciones de cada jugador. La agregación vive en
`futbol_bd/cancha.posiciones_por_partido`, la misma que usa el notebook, así que bajar los datos y analizarlos no
pueden aplicar reglas distintas.

Es reanudable: si el CSV ya existe, solo baja los partidos que le faltan. Un partido tarda ~1.3 s.
"""
import argparse
import sys
import time
import warnings
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
warnings.filterwarnings("ignore")

from futbol_bd import cancha  # noqa: E402

# Las CUATRO ligas que StatsBomb Open Data publica completas, todas de 2015/16 (season_id 27). El resto de lo que
# publica en abierto son temporadas parciales centradas en un equipo o un jugador: la Premier 2003/04 son los 38
# partidos del Arsenal invicto y las 17 temporadas de La Liga entre 2004/05 y 2020/21 son los partidos del Barcelona
# de Messi (30-35 cada una). Para un panel de liga solo sirven estas cuatro.
COMPETICIONES = {
    "laliga": {"competition_id": 11, "season_id": 27, "nombre": "La Liga 2015/16"},
    "premier": {"competition_id": 2, "season_id": 27, "nombre": "Premier League 2015/16"},
    "seriea": {"competition_id": 12, "season_id": 27, "nombre": "Serie A 2015/16"},
    "ligue1": {"competition_id": 7, "season_id": 27, "nombre": "Ligue 1 2015/16"},
}
SALIDA = RAIZ / "data" / "processed"


def descargar(clave: str, limite: int | None = None):
    from statsbombpy import sb

    info = COMPETICIONES[clave]
    partidos = sb.matches(competition_id=info["competition_id"], season_id=info["season_id"])
    ruta_pos = SALIDA / f"statsbomb_{clave}_posiciones.csv"
    ruta_par = SALIDA / f"statsbomb_{clave}_partidos.csv"
    partidos[["match_id", "match_date", "home_team", "away_team", "home_score", "away_score"]].to_csv(
        ruta_par, index=False)

    hechos = set()
    if ruta_pos.exists():
        hechos = set(pd.read_csv(ruta_pos, usecols=["match_id"])["match_id"])
        print(f"{info['nombre']}: ya había {len(hechos)} partidos en {ruta_pos.name}")
    faltan = [int(m) for m in partidos["match_id"] if int(m) not in hechos][:limite]
    print(f"{info['nombre']}: {len(faltan)} partidos por bajar de {len(partidos)}")

    t0, acumulado = time.time(), []
    for i, match_id in enumerate(faltan, 1):
        try:
            acumulado.append(cancha.posiciones_por_partido(sb.events(match_id=match_id)))
        except Exception as e:                            # un partido roto no debe tirar toda la descarga
            print(f"  ! {match_id}: {type(e).__name__} {str(e)[:60]}")
            continue
        if i % 40 == 0 or i == len(faltan):
            # Se guarda por tandas: si se corta la descarga, lo bajado no se pierde y la próxima corrida lo respeta.
            nuevo = pd.concat(acumulado, ignore_index=True)
            nuevo.to_csv(ruta_pos, mode="a", header=not ruta_pos.exists(), index=False)
            acumulado = []
            print(f"  {i}/{len(faltan)} partidos · {time.time() - t0:.0f} s")
    if ruta_pos.exists():
        d = pd.read_csv(ruta_pos)
        print(f"{info['nombre']}: {len(d):,} filas jugador-partido, {d['match_id'].nunique()} partidos -> "
              f"{ruta_pos.relative_to(RAIZ)}")


def descargar_nombres(clave: str):
    """player_id -> nombre para mostrar, tomado de `player_nickname` de las alineaciones (ver el encabezado)."""
    from statsbombpy import sb

    info = COMPETICIONES[clave]
    partidos = sb.matches(competition_id=info["competition_id"], season_id=info["season_id"])
    nombres = {}
    t0 = time.time()
    for i, match_id in enumerate(partidos["match_id"], 1):
        try:
            for equipo in sb.lineups(match_id=int(match_id)).values():
                for r in equipo.itertuples():
                    apodo = getattr(r, "player_nickname", None)
                    nombres[int(r.player_id)] = apodo if isinstance(apodo, str) and apodo else r.player_name
        except Exception as e:
            print(f"  ! alineación {match_id}: {type(e).__name__} {str(e)[:50]}")
        if i % 100 == 0:
            print(f"  alineaciones {i}/{len(partidos)} · {len(nombres)} jugadores · {time.time() - t0:.0f} s")
    ruta = SALIDA / f"statsbomb_{clave}_jugadores.csv"
    pd.DataFrame({"player_id": list(nombres), "nombre": list(nombres.values())}).to_csv(ruta, index=False)
    print(f"{info['nombre']}: {len(nombres)} jugadores -> {ruta.relative_to(RAIZ)}")


def _a_minutos(txt) -> float | None:
    """'64:56' -> 64.93. StatsBomb cuenta desde el saque inicial, no desde el inicio de cada parte."""
    if not isinstance(txt, str) or ":" not in txt:
        return None
    m, sg = txt.split(":")[:2]
    return int(m) + int(sg) / 60


def descargar_participacion(clave: str):
    """Minutos y CÓMO participó cada jugador en cada partido, leídos de las alineaciones.

    Por qué hace falta: hasta ahora un titular contaba igual jugara 90 minutos o 20. La posición media de alguien
    sustituido al 25' sale de un puñado de eventos y es mucho más ruidosa, pero pesaba lo mismo en todos los análisis.

    Cada jugador trae en `positions` una lista de TRAMOS (cambia de tramo al moverse de posición sin salir, lo que
    StatsBomb llama Tactical Shift). Dos cuidados:
      - Los minutos se SUMAN por tramo, no se restan último menos primero: un jugador puede salir y volver a entrar
        (atención médica: end_reason 'Player Off' seguido de start_reason 'Player On') y en medio no estuvo en cancha.
      - Un tramo con `to` vacío terminó con el partido. Como las alineaciones no dicen cuándo fue el pitido final, se
        usa el máximo instante visto en ese partido, con 90 como mínimo. El error es de segundos y solo afecta al
        descuento.

    Salida: data/processed/statsbomb_<clave>_participacion.csv, una fila por jugador-partido que pisó la cancha.
      estado   titular_completo | titular_sustituido | titular_salio (roja o lesión sin reemplazo) | suplente
      entro, salio, minutos     en minutos desde el saque inicial
      tramos                    cuántos tramos tuvo (>1 = le cambiaron la posición en el partido)
    """
    from statsbombpy import sb

    info = COMPETICIONES[clave]
    partidos = sb.matches(competition_id=info["competition_id"], season_id=info["season_id"])
    filas = []
    t0 = time.time()
    for i, match_id in enumerate(partidos["match_id"], 1):
        try:
            alineaciones = sb.lineups(match_id=int(match_id))
        except Exception as e:
            print(f"  ! alineación {match_id}: {type(e).__name__} {str(e)[:50]}")
            continue
        crudo = []
        for equipo, d in alineaciones.items():
            for r in d.itertuples():
                tramos = [t for t in (r.positions or []) if t.get("from") is not None]
                if not tramos:
                    continue                       # no salió del banquillo
                crudo.append((equipo, r, tramos))
        # El final del partido se estima una vez por partido, con todos los tramos ya vistos.
        fin = max([_a_minutos(t["to"]) for _, _, ts in crudo for t in ts if t.get("to")] + [90.0])
        for equipo, r, tramos in crudo:
            minutos = sum((_a_minutos(t["to"]) if t.get("to") else fin) - _a_minutos(t["from"]) for t in tramos)
            # Titular es quien estaba en cancha en el MINUTO 0. Se probaron dos reglas sobre los 760 equipos-partido
            # de La Liga y esta acierta en los 760; la de `start_reason == 'Starting XI'` falla en uno, porque en ese
            # partido la fuente no marca la razón a varios que sí empezaron. Además hay que mirar TODOS los tramos y
            # no solo el primero: StatsBomb a veces mete un tramo de duración cero con 'Tactical Shift' justo antes
            # de la entrada real de un suplente (Juan Añor, Málaga, 84:10), y mirando solo el primero se colaban
            # como titulares (52 equipos-partido con 12 o 13).
            razones_ini = [str(t.get("start_reason")) for t in tramos]
            fin_razon = str(tramos[-1].get("end_reason"))
            empezo = any(_a_minutos(t["from"]) == 0 for t in tramos) or "Starting XI" in razones_ini
            if not empezo:
                estado = "suplente"
            elif "Substitution - Off" in fin_razon:
                estado = "titular_sustituido"
            elif fin_razon == "Final Whistle":
                estado = "titular_completo"
            else:
                estado = "titular_salio"      # roja, lesión sin reemplazo o final de partido atípico
            filas.append({
                "match_id": int(match_id), "team": equipo, "player_id": int(r.player_id),
                "entro": round(_a_minutos(tramos[0]["from"]), 1),
                "salio": round(_a_minutos(tramos[-1]["to"]) if tramos[-1].get("to") else fin, 1),
                "minutos": round(minutos, 1), "estado": estado, "tramos": len(tramos),
                "motivo_salida": fin_razon,
            })
        if i % 100 == 0:
            print(f"  participación {i}/{len(partidos)} · {len(filas)} filas · {time.time() - t0:.0f} s")
    ruta = SALIDA / f"statsbomb_{clave}_participacion.csv"
    pd.DataFrame(filas).to_csv(ruta, index=False)
    print(f"{info['nombre']}: {len(filas):,} filas de participación -> {ruta.relative_to(RAIZ)}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--liga", choices=list(COMPETICIONES) + ["todas"], default="todas")
    p.add_argument("--limite", type=int, default=None, help="bajar solo N partidos (para probar)")
    p.add_argument("--solo-nombres", action="store_true", help="bajar solo las alineaciones (nombres para mostrar)")
    p.add_argument("--solo-participacion", action="store_true", help="bajar solo minutos y cambios por jugador")
    a = p.parse_args()
    for clave in (COMPETICIONES if a.liga == "todas" else [a.liga]):
        if a.solo_participacion:
            descargar_participacion(clave)
            continue
        if not a.solo_nombres:
            descargar(clave, a.limite)
        descargar_nombres(clave)


if __name__ == "__main__":
    main()
