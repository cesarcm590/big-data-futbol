"""
Actualización semanal del dashboard: baja los resultados nuevos, reexporta, congela y publica.

    python scripts/actualizar_semanal.py                  # cadena completa (incluye publicar)
    python scripts/actualizar_semanal.py --sin-desplegar  # todo menos publicar (para probar)
    python scripts/actualizar_semanal.py --solo-descargar # solo mirar si hay partidos nuevos

POR QUÉ EXISTE
--------------
Hasta ahora la actualización semanal era una secuencia a mano: bajar el CSV de cada liga de football-data.co.uk,
correr el exportador, correr el congelador y desplegar. Son 13 comandos en orden y si se olvida uno el dashboard
queda a medias (p. ej. exportar sin congelar hace que el seguimiento en vivo pierda esa jornada para siempre, porque
el registro de congeladas solo guarda lo que se dijo ANTES del partido). Este script encadena eso y, sobre todo,
deja dicho al final qué NO tocó.

QUÉ NO HACE, Y POR QUÉ NO PUEDE
-------------------------------
  - **Liga MX.** Sus partidos futuros no salen de ninguna fuente automática: la jornada se define a mano (la J10 del
    Apertura 2026 se capturó el 2026-09-18). Mientras siga así, Liga MX se actualiza aparte.
  - **FBref** (plantillas, porteros, minutos). Está detrás de Cloudflare y solo responde desde el navegador del
    usuario con su sesión iniciada; un proceso automático recibe 403. Ver `scripts/incorporar_temporada_fbref.py`.
Las dos cosas se avisan en el resumen final para que un log semanal no las esconda.

SEGURIDAD AL SOBRESCRIBIR
-------------------------
football-data.co.uk a veces devuelve una página de error con código 200. Un CSV así, escrito encima del bueno,
borraría la temporada entera sin avisar. Por eso un archivo descargado solo reemplaza al local si: parsea como CSV,
trae las columnas mínimas y **no tiene menos partidos que el que ya estaba**. Si algo falla, se deja el local
intacto y esa liga se salta (las demás siguen).
"""
import argparse
import io
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd
import requests

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))

sys.path.insert(0, str(RAIZ))
from futbol_bd.congelado import fixtures_sin_atender  # noqa: E402
from ligas_europa import LIGAS_EUROPA, RUTA_FIXTURES  # noqa: E402  (la config que usan los exportadores)

PYTHON = sys.executable
TEMPORADA = "2627"                      # código de football-data para 2026-27
URL = "https://www.football-data.co.uk/mmz4281/{temporada}/{div}.csv"
URL_FIXTURES = "https://www.football-data.co.uk/fixtures.csv"   # próximos partidos de todas las ligas
COLUMNAS_MINIMAS = {"Div", "Date", "HomeTeam", "AwayTeam"}
PAUSA = 2                               # segundos entre descargas: son 4 archivos, no hay prisa


def bajar_csv(url: str, destino: Path, puede_encoger: bool) -> tuple[int, str]:
    """Baja un CSV de football-data y lo escribe en `destino` solo si pasa las validaciones.

    `puede_encoger` distingue los dos tipos de archivo:
      False  resultados de la temporada: solo crecen. Uno con menos partidos que el local es un archivo roto.
      True   calendario futuro (fixtures.csv): es una ventana móvil de los próximos días, así que encoge sola
             cuando pasa una jornada. Ahí solo se comprueba que no llegue vacío.
    Devuelve (filas nuevas respecto al local, mensaje para el log).
    """
    try:
        # allow_redirects: el dominio redirige www -> sin www; sin seguirlo llega un 302 vacío.
        r = requests.get(url, timeout=60, allow_redirects=True)
        r.raise_for_status()
        # Los CSV de football-data empiezan con BOM: leyendo el texto ya decodificado, la primera columna se llamaría
        # "\ufeffDiv" y la validación de columnas fallaría siempre. Se leen los BYTES con utf-8-sig, que se lo come.
        nuevo = pd.read_csv(io.BytesIO(r.content), encoding="utf-8-sig")
    except Exception as e:
        return 0, f"✗ no se pudo bajar ({type(e).__name__}: {str(e)[:60]}) — se deja el archivo local"

    faltan = COLUMNAS_MINIMAS - set(nuevo.columns)
    if faltan:
        return 0, f"✗ el archivo bajado no parece de football-data (faltan {sorted(faltan)}) — se deja el local"
    if nuevo.empty:
        return 0, "✗ el archivo bajado viene vacío — se deja el local"

    # En un clon recién hecho `data/` no existe (no se versiona), así que hay que crear la carpeta antes de escribir
    # o la primera ejecución muere con FileNotFoundError. Se descubrió clonando el repositorio y corriendo la cadena.
    destino.parent.mkdir(parents=True, exist_ok=True)
    antes = len(pd.read_csv(destino, encoding="utf-8-sig")) if destino.exists() else 0
    if not puede_encoger and len(nuevo) < antes:
        return 0, f"✗ el archivo bajado tiene MENOS partidos ({len(nuevo)} < {antes}) — se deja el local"

    destino.write_bytes(r.content)
    nuevos = len(nuevo) - antes
    return nuevos, (f"{nuevos} partidos nuevos ({antes} → {len(nuevo)})" if nuevos > 0 else f"sin novedad ({len(nuevo)})")


def descargar(clave: str, cfg: dict) -> tuple[int, str]:
    """Resultados de una liga -> data/raw/<carpeta_raw>/<prefijo>_<temporada>.csv."""
    destino = RAIZ / "data" / "raw" / cfg["carpeta_raw"] / f"{cfg['prefijo']}_{TEMPORADA}.csv"
    return bajar_csv(URL.format(temporada=TEMPORADA, div=cfg["div"]), destino, puede_encoger=False)


def ligas_con_partidos_sin_congelar() -> dict[str, int]:
    """Ligas cuyo calendario trae partidos que nadie ha congelado ni descartado, y cuántos son.

    Es lo que hace útil la corrida del VIERNES. Antes solo se disparaba con resultados nuevos, pero los del fin de
    semana ya se bajan el lunes: el viernes casi nunca hay, así que la corrida que existe para congelar la jornada
    antes de que se juegue terminaba en "no hay partidos nuevos" sin congelar nada (pasó el 2026-10-09, con 153
    partidos nuevos en el calendario). Un partido "atendido" es uno ya congelado o que el exportador ya vio y no pudo
    predecir (ascendido sin historial); los que ya empezaron tampoco cuentan.
    """
    if not Path(RUTA_FIXTURES).exists():
        return {}
    fx = pd.read_csv(RUTA_FIXTURES, encoding="utf-8-sig", on_bad_lines="skip")
    pendientes = {}
    for clave, cfg in LIGAS_EUROPA.items():
        registro = RAIZ / "registro" / cfg["registro"]
        congeladas = set()
        if registro.exists():
            r = pd.read_csv(registro)
            congeladas = set(zip(r["date"], r["home_team"], r["away_team"]))
        sin_perfil = set()
        salida = RAIZ / "dashboard-predicciones" / cfg["salida_json"]
        if salida.exists():
            import json
            futuras = json.load(open(salida, encoding="utf-8")).get("futuras", [])
            sin_perfil = {(f["date"], f["home_team"], f["away_team"]) for f in futuras if f.get("sin_perfil")}
        n = len(fixtures_sin_atender(fx[fx["Div"] == cfg["div"]], cfg.get("nombres", {}), congeladas, sin_perfil))
        if n:
            pendientes[clave] = n
    return pendientes


def estado_liga_mx() -> str:
    """Una línea sobre qué tan al día está Liga MX. Esa liga no se automatiza (FBref solo responde desde el Chrome del
    usuario), y por eso se atrasó 3 semanas sin que nada lo dijera: el log salía con código 0 y la nota genérica de
    "queda fuera". Aquí se mide el atraso en días."""
    ruta = RAIZ / "data" / "processed" / "matches_ligamx_2020_2025_v3_arbitraje.csv"
    if not ruta.exists():
        return "Liga MX: no hay dataset local"
    ultimo = pd.to_datetime(pd.read_csv(ruta, usecols=["date"])["date"]).max()
    dias = (pd.Timestamp.now().normalize() - ultimo).days
    aviso = "  ← CAPTURA DE FBREF PENDIENTE (pídele a Claude: «actualiza Liga MX», con el Chrome conectado)" if dias > 4 else ""
    return f"Liga MX: último partido en el dataset {ultimo.date()} (hace {dias} días){aviso}"


def correr(descripcion: str, *args) -> bool:
    """Corre un script del proyecto y devuelve si salió bien, resumiendo su salida.

    RESUMIR NO ES QUEDARSE CON LA ÚLTIMA LÍNEA. `seguir_clubes.py` sigue cinco competiciones y la última línea que
    imprime es de la última de ellas; cuando una de las otras daba la alarma, la cadena marcaba ✗ y enseñaba un
    mensaje de una competición distinta, que encima parecía normal. Estuvo así hasta el 28 de octubre de 2026
    tapando tres alarmas de verdad. Así que si el script marcó alguna línea con `!` o `✗`, se enseñan ESAS; si no,
    la última, que es el resumen.
    """
    p = subprocess.run([PYTHON, str(RAIZ / "scripts" / args[0]), *args[1:]], capture_output=True, text=True)
    ok = p.returncode == 0
    # Solo se resume la SALIDA ESTÁNDAR: los avisos de pandas van a stderr y taparían la línea de resultado. Si el
    # script falla, ahí sí interesa el stderr, que es donde estará el error.
    lineas = [l for l in (p.stdout if ok else p.stdout + p.stderr).strip().splitlines() if l.strip()]
    # También las líneas de detalle, que empiezan por `·`: son el porqué de la alarma de arriba, y sin ellas la
    # línea `!` da el número pero no dice qué falla ("127 partidos de fase liga" no explica cuál falta).
    avisos = [l.strip() for l in lineas if l.strip().startswith(("!", "✗", "·"))]
    if avisos:
        print(f"   ✗ {descripcion}: {len(avisos)} aviso(s)")
        for linea in avisos[:8]:
            print(f"       {linea[:120]}")
    else:
        print(f"   {'✓' if ok else '✗'} {descripcion}: {lineas[-1][:110] if lineas else 'sin salida'}")
    return ok


def congeladas_sin_resultado(margen_dias: int = 2):
    """Ligas con predicciones congeladas de partidos YA JUGADOS que todavía no tienen resultado en el dataset.

    POR QUÉ. El 26 de octubre de 2026 la cadena corrió a las 09:07, football-data aún no había publicado la jornada
    del fin de semana, y el log dijo «sin novedad» en las seis ligas. Era verdad y era inútil: el archivo bajado
    tenía las mismas filas que el local, así que no había nada que comparar. Los resultados aparecieron horas
    después y nadie se enteró hasta que el usuario preguntó, cinco días más tarde, por qué no se actualizaba.

    La cadena no puede saber si la fuente está al día —no tiene con qué contrastarla—. Lo que SÍ sabe es qué
    partidos prometió seguir: si congeló un pronóstico para un partido que ya se jugó y sigue sin resultado, algo
    va por detrás. Eso es un contraste contra una expectativa propia, que es lo único que convierte un silencio en
    un aviso.

    El margen de dos días evita gritar por un partido de anoche que la fuente publicará mañana.
    """
    hoy = pd.Timestamp.today().normalize()
    avisos = []
    for clave, cfg in LIGAS_EUROPA.items():
        reg = RAIZ / "registro" / cfg["registro"]
        crudo = RAIZ / "data" / "raw" / cfg["carpeta_raw"] / f"{cfg['prefijo']}_{TEMPORADA}.csv"
        if not reg.exists() or not crudo.exists():
            continue
        try:
            congeladas = pd.to_datetime(pd.read_csv(reg)["date"], errors="coerce")
            ultimo = pd.to_datetime(pd.read_csv(crudo, encoding="utf-8-sig")["Date"],
                                    dayfirst=True, errors="coerce").max()
        except Exception:
            continue                      # un registro vacío o un CSV a medias no debe tumbar la cadena
        pendientes = congeladas[(congeladas <= hoy - pd.Timedelta(days=margen_dias)) & (congeladas > ultimo)]
        if len(pendientes):
            avisos.append(f"{cfg['nombre']:16s} {len(pendientes)} partidos entre {pendientes.min():%Y-%m-%d} y "
                          f"{pendientes.max():%Y-%m-%d}; el dataset llega al {ultimo:%Y-%m-%d}")
    return avisos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sin-desplegar", action="store_true", help="hace todo menos publicar")
    ap.add_argument("--solo-descargar", action="store_true", help="solo mira si hay partidos nuevos")
    ap.add_argument("--forzar", action="store_true",
                    help="reexporta y congela aunque la descarga no traiga nada (p. ej. si ya se bajó antes)")
    a = ap.parse_args()

    print(f"Actualización semanal · {time.strftime('%Y-%m-%d %H:%M')}\n")
    # El calendario futuro va PRIMERO: de ahí salen los partidos que el exportador predice y el congelador guarda.
    # Football-data lo publica a mitad de semana, así que a veces todavía trae la jornada que acaba de pasar; en ese
    # caso no habrá nada nuevo que congelar y el script lo dirá.
    _, msg_fx = bajar_csv(URL_FIXTURES, Path(RUTA_FIXTURES), puede_encoger=True)
    print(f"0) Calendario futuro (fixtures.csv): {msg_fx}")
    # El fixtures.csv de football-data solo llega a 2-3 días: sin esto, de lunes a jueves el panel no enseña
    # ninguna jornada próxima. El calendario de temporada (openfootball) la cubre siempre.
    correr("Calendario de temporada", "calendario_temporada.py")
    print(f"   {estado_liga_mx()}\n")
    print("1) Bajando resultados de football-data.co.uk")
    cambiadas, fallos = [], []
    for clave, cfg in LIGAS_EUROPA.items():
        nuevos, msg = descargar(clave, cfg)
        print(f"   {cfg['nombre']:16s} {msg}")
        if msg.startswith("✗"):
            fallos.append(cfg["nombre"])
        elif nuevos:
            cambiadas.append(clave)
        time.sleep(PAUSA)

    atrasadas = congeladas_sin_resultado()
    if atrasadas:
        print("\n! Congeladas ya jugadas y SIN resultado (la fuente va por detrás):")
        for linea in atrasadas:
            print(f"   {linea}")

    if a.solo_descargar:
        print(f"\n(solo descarga) ligas con partidos nuevos: {cambiadas or 'ninguna'}")
        return 1 if fallos else 0

    # Selecciones ANTES de cualquier salida temprana: el seguimiento de la Nations League no depende de que haya
    # partidos de clubes nuevos. Al contrario — durante una fecha FIFA las ligas están paradas por definición, así
    # que ponerlo después del "no hay nada nuevo" lo apagaba justo en las semanas en las que sirve. El propio script
    # mira el calendario y no hace nada fuera de ventana.
    print("\n2) Selecciones (solo en fecha FIFA)")
    correr("Nations League", "seguir_nations_league.py")

    # Los clubes continentales NO se atan a la ventana FIFA: juegan entre semana casi todo el año, justo cuando las
    # selecciones paran. Por eso este corre siempre.
    print("\n2b) Clubes continentales")
    # La etiqueta decía "AFC Champions League Elite", pero este script sigue CINCO competiciones: UEFA, AFC, CAF,
    # Libertadores y Concacaf. Es un resto de cuando solo hacía la AFC, y hacía creer que la alarma era de esa.
    correr("Clubes continentales (UEFA, AFC, CAF, Libertadores, Concacaf)", "seguir_clubes.py")

    # Dos motivos independientes para procesar una liga: resultados nuevos (hay que calificar) o partidos del
    # calendario sin congelar (hay que predecir). El segundo es el que importa el viernes.
    sin_congelar = ligas_con_partidos_sin_congelar()
    if sin_congelar:
        detalle = ", ".join(f"{LIGAS_EUROPA[c]['nombre']} {n}" for c, n in sin_congelar.items())
        print(f"\nPartidos del calendario sin congelar: {detalle}")
    cambiadas = cambiadas + [c for c in sin_congelar if c not in cambiadas]

    if not cambiadas and a.forzar:
        # Útil cuando la descarga ya se corrió antes: los CSV locales están al día pero falta propagarlos.
        cambiadas = [c for c in LIGAS_EUROPA if LIGAS_EUROPA[c]["nombre"] not in fallos]
        print("\n(--forzar) sin descargas nuevas, pero se reexportan todas las ligas de todos modos.")
    if not cambiadas:
        print("\nNo hay resultados nuevos ni partidos por congelar: no se reexporta ni se publica nada.")
        print("(si los CSV ya estaban al día y hace falta propagarlos, usa --forzar)")
        return 1 if fallos else 0

    # Los tres pasos van EN ESTE ORDEN y cada uno depende del anterior:
    #   1. construir: CSV crudos de football-data -> data/processed/<dataset>.csv (el exportador NO lee los crudos).
    #   2. exportar:  ese dataset + el calendario futuro -> dashboard-predicciones/data_<liga>.json.
    #   3. congelar:  lee las "futuras" de ese JSON y las guarda antes de que se jueguen.
    # Saltarse el primero fue justo el error al escribir este script: los resultados nuevos estaban bajados pero el
    # dashboard seguía viendo los viejos, así que el seguimiento en vivo no calificaba ningún partido.
    print(f"\n3) Reconstruyendo, exportando y congelando ({len(cambiadas)} ligas)")
    for clave in cambiadas:
        nombre = LIGAS_EUROPA[clave]["nombre"]
        if not correr(f"{nombre} dataset", "europa_construir_dataset.py", clave):
            continue
        if correr(f"{nombre} exportada", "export_predicciones_europa.py", clave):
            correr(f"{nombre} congelada", "congelar_predicciones.py", clave)

    if a.sin_desplegar:
        print("\n4) (--sin-desplegar) no se publicó nada.")
    else:
        print("\n4) Publicando")
        publicado = correr("dashboard publicado", "desplegar_dashboard.py")
        if not publicado:
            # El script de despliegue no toca el link si algo falla, así que reintentar es seguro. Pasó el
            # 2026-10-10: el staging falló una vez y al minuto siguiente pasó entero (error de red del CLI).
            print("   ... se reintenta en 60 s (los fallos de red del CLI de Vercel suelen ser transitorios)")
            time.sleep(60)
            publicado = correr("dashboard publicado (reintento)", "desplegar_dashboard.py")
        if not publicado:
            print("   ! el despliegue falló dos veces; el link público sigue en la versión anterior")
            return 1

    print("\nQueda FUERA de esta actualización (no es automatizable):")
    print("   - Liga MX: sus partidos futuros se capturan a mano")
    print("   - FBref (plantillas): Cloudflare solo responde desde tu navegador")
    if fallos:
        print(f"\n! Ligas que no se pudieron bajar: {', '.join(fallos)}")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
