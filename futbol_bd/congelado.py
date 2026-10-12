"""
Reglas del congelado de predicciones (seguimiento en vivo), aisladas para poder probarlas.

El seguimiento en vivo solo vale si lo congelado se dijo ANTES del partido. Dos reglas lo protegen y las dos
fallaron o estuvieron a punto de fallar, por eso viven aquí con sus pruebas y no enterradas en un script:

1. `ya_empezo`: un partido cuyo silbatazo ya pasó NO se congela. Antes solo se miraba la fecha, así que una
   corrida del sábado por la mañana (hora de México) congelaba partidos de las 12:30 del Reino Unido que ya habían
   empezado. football-data da la hora en horario del Reino Unido.
2. `pendientes_de_congelar`: qué partidos futuros todavía no están en el registro. La actualización semanal se
   disparaba solo cuando había RESULTADOS nuevos, y el viernes casi nunca los hay (los del fin de semana ya se
   bajaron el lunes), así que la corrida del viernes —la única que importa para congelar— no hacía nada.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd

ZONA_FOOTBALL_DATA = ZoneInfo("Europe/London")
ZONA_MEXICO = ZoneInfo("America/Mexico_City")       # sin horario de verano desde 2022: UTC-6 todo el año

# Solo se congela lo que se juega en los próximos días. Liga MX publica el calendario del torneo completo; congelar
# toda esa cola (se hizo una vez, 63 partidos hasta el 22 de noviembre) fija predicciones con 6 semanas de
# anticipación, mezcla horizontes distintos en el seguimiento y no son lo que el modelo diría con la información de esa
# semana. 5 días cubre desde el viernes hasta la jornada de entre semana siguiente (martes-miércoles).
HORIZONTE_DIAS = 5


def dentro_del_horizonte(fecha: str, ahora: datetime | None = None, dias: int = HORIZONTE_DIAS) -> bool:
    """¿El partido es de hoy o de los próximos `dias` días? (el día se cuenta en horario de México, el del usuario)."""
    ahora = ahora or datetime.now(timezone.utc)
    hoy = ahora.astimezone(ZONA_MEXICO).date()
    return pd.Timestamp(fecha).date() <= hoy + pd.Timedelta(days=dias)


def ya_empezo(fecha: str, hora_uk, ahora: datetime | None = None, zona: ZoneInfo = ZONA_FOOTBALL_DATA) -> bool:
    """¿El partido ya empezó? `fecha` AAAA-MM-DD y `hora_uk` 'HH:MM' en la zona `zona` (por defecto el Reino Unido,
    que es como las da football-data; Liga MX las trae en horario de México y pasa `ZONA_MEXICO`).

    Sin hora conocida se es conservador por DÍA: solo cuenta como empezado si su fecha ya pasó, porque sin la hora
    no se puede saber si el partido de hoy empezó y rechazarlo por eso dejaría la jornada sin congelar.
    """
    ahora = ahora or datetime.now(timezone.utc)
    if ahora.tzinfo is None:
        raise ValueError("`ahora` debe traer zona horaria; un datetime ingenuo daría la hora equivocada")
    if hora_uk is None or (isinstance(hora_uk, float) and pd.isna(hora_uk)) or str(hora_uk).strip() == "":
        return pd.Timestamp(fecha).date() < ahora.astimezone(zona).date()
    saque = datetime.fromisoformat(f"{fecha}T{str(hora_uk).strip()}").replace(tzinfo=zona)
    return saque <= ahora


def pendientes_de_congelar(futuras: list[dict], congeladas: set[tuple], ahora: datetime | None = None) -> list[dict]:
    """Partidos de `futuras` (las del JSON del dashboard) que se pueden y se deben congelar ya.

    Quedan fuera: los `sin_perfil` (no hay predicción que guardar), los que ya están en el registro (la llave es
    (fecha, local, visitante) y el registro nunca se sobrescribe) y los que ya empezaron.
    """
    return [f for f in futuras
            if not f.get("sin_perfil")
            and (f["date"], f["home_team"], f["away_team"]) not in congeladas
            and not ya_empezo(f["date"], f.get("hora_uk"), ahora)
            and dentro_del_horizonte(f["date"], ahora)]


def fixtures_sin_atender(fixtures: pd.DataFrame, nombres: dict, congeladas: set[tuple], sin_perfil: set[tuple],
                         ahora: datetime | None = None, dias: int = HORIZONTE_DIAS) -> pd.DataFrame:
    """Partidos del calendario (fixtures.csv, ya filtrado a UNA liga) que nadie ha congelado ni descartado.

    Es lo que decide si la corrida semanal tiene algo que hacer aunque no haya resultados nuevos. `nombres` es el
    renombrado de equipos de la liga (football-data usa abreviaturas), `sin_perfil` las llaves que el exportador ya
    vio y no puede predecir (ascendidos sin historial): sin descontarlas, esa liga dispararía la corrida para siempre.
    """
    if fixtures.empty:
        return fixtures
    f = fixtures.copy()
    f["date"] = pd.to_datetime(f["Date"], dayfirst=True, format="mixed").dt.strftime("%Y-%m-%d")
    f["home_team"] = f["HomeTeam"].replace(nombres)
    f["away_team"] = f["AwayTeam"].replace(nombres)
    llaves = list(zip(f["date"], f["home_team"], f["away_team"]))
    atendido = [k in congeladas or k in sin_perfil for k in llaves]
    empezado = [ya_empezo(d, t, ahora) for d, t in zip(f["date"], f["Time"])]
    lejano = [not dentro_del_horizonte(d, ahora, dias) for d in f["date"]]
    return f[[not a and not e and not l for a, e, l in zip(atendido, empezado, lejano)]]
