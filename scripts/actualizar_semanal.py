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


def correr(descripcion: str, *args) -> bool:
    """Corre un script del proyecto y devuelve si salió bien, enseñando solo la última línea de su salida."""
    p = subprocess.run([PYTHON, str(RAIZ / "scripts" / args[0]), *args[1:]], capture_output=True, text=True)
    ok = p.returncode == 0
    # Solo se resume la SALIDA ESTÁNDAR: los avisos de pandas van a stderr y taparían la línea de resultado. Si el
    # script falla, ahí sí interesa el stderr, que es donde estará el error.
    lineas = [l for l in (p.stdout if ok else p.stdout + p.stderr).strip().splitlines() if l.strip()]
    print(f"   {'✓' if ok else '✗'} {descripcion}: {lineas[-1][:110] if lineas else 'sin salida'}")
    return ok


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
    print(f"0) Calendario futuro (fixtures.csv): {msg_fx}\n")
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

    if a.solo_descargar:
        print(f"\n(solo descarga) ligas con partidos nuevos: {cambiadas or 'ninguna'}")
        return 1 if fallos else 0

    if not cambiadas and a.forzar:
        # Útil cuando la descarga ya se corrió antes: los CSV locales están al día pero falta propagarlos.
        cambiadas = [c for c in LIGAS_EUROPA if LIGAS_EUROPA[c]["nombre"] not in fallos]
        print("\n(--forzar) sin descargas nuevas, pero se reexportan todas las ligas de todos modos.")
    if not cambiadas:
        print("\nNo hay partidos nuevos en ninguna liga: no se reexporta ni se publica nada.")
        print("(si los CSV ya estaban al día y hace falta propagarlos, usa --forzar)")
        return 1 if fallos else 0

    # Los tres pasos van EN ESTE ORDEN y cada uno depende del anterior:
    #   1. construir: CSV crudos de football-data -> data/processed/<dataset>.csv (el exportador NO lee los crudos).
    #   2. exportar:  ese dataset + el calendario futuro -> dashboard-predicciones/data_<liga>.json.
    #   3. congelar:  lee las "futuras" de ese JSON y las guarda antes de que se jueguen.
    # Saltarse el primero fue justo el error al escribir este script: los resultados nuevos estaban bajados pero el
    # dashboard seguía viendo los viejos, así que el seguimiento en vivo no calificaba ningún partido.
    print(f"\n2) Reconstruyendo, exportando y congelando ({len(cambiadas)} ligas)")
    for clave in cambiadas:
        nombre = LIGAS_EUROPA[clave]["nombre"]
        if not correr(f"{nombre} dataset", "europa_construir_dataset.py", clave):
            continue
        if correr(f"{nombre} exportada", "export_predicciones_europa.py", clave):
            correr(f"{nombre} congelada", "congelar_predicciones.py", clave)

    if a.sin_desplegar:
        print("\n3) (--sin-desplegar) no se publicó nada.")
    else:
        print("\n3) Publicando")
        if not correr("dashboard publicado", "desplegar_dashboard.py"):
            print("   ! el despliegue falló; el link público sigue en la versión anterior")
            return 1

    print("\nQueda FUERA de esta actualización (no es automatizable):")
    print("   - Liga MX: sus partidos futuros se capturan a mano")
    print("   - FBref (plantillas): Cloudflare solo responde desde tu navegador")
    if fallos:
        print(f"\n! Ligas que no se pudieron bajar: {', '.join(fallos)}")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
