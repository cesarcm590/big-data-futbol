"""
DESPLIEGUE SEGURO del dashboard de predicciones (https://dashboard-predicciones.vercel.app).

POR QUÉ EXISTE
--------------
Antes se publicaba con `vercel deploy --prod`, que cambia el link público de inmediato: si el HTML o algún JSON
salía roto, el link se caía al instante. Este script separa "probar" de "publicar" y deja siempre una versión buena
a la cual volver (la LÍNEA BASE):

  1. VALIDAR   los archivos locales (JSON válidos y sin NaN, probabilidades que suman 1, todas las ligas presentes,
               sin archivos personales dentro de la carpeta que se publica, sin pérdida grande de datos vs. la
               última versión buena).
  2. RESPALDAR una copia de los archivos en backups/dashboard_predicciones/AAAAMMDD_HHMM/ (se conservan las últimas 8).
  3. STAGING   `vercel deploy --prod --skip-domain`: construye el despliegue de producción SIN mover el link público.
  4. PROBAR    el despliegue en staging (`vercel curl`, que salta la protección): cada archivo responde 200 y es
               idéntico (SHA-256) al local.
  5. PROMOVER  `vercel promote <staging>`: ahora sí el link apunta a la versión nueva.
  6. VERIFICAR el link público; si algo falla, ROLLBACK automático a la línea base.
  7. GUARDAR   la nueva línea base en registro/deploy_baseline.json (URL del despliegue bueno + historial).

USO
  python scripts/desplegar_dashboard.py               # flujo completo (validar -> staging -> probar -> promover)
  python scripts/desplegar_dashboard.py --validar     # solo validar los archivos locales
  python scripts/desplegar_dashboard.py --sin-promover  # llega hasta probar el staging y se detiene (link intacto)
  python scripts/desplegar_dashboard.py --rollback    # vuelve a la línea base (última versión buena)
  python scripts/desplegar_dashboard.py --rollback <url-de-despliegue>   # vuelve a un despliegue concreto

NOTA: Vercel conserva TODOS los despliegues anteriores, así que un rollback es solo re-apuntar el link (segundos).
"""
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from datetime import datetime

RAIZ = "/Users/javiercarrillo/Proyectos/Big_data_futbol"
CARPETA = f"{RAIZ}/dashboard-predicciones"                     # lo único que se publica
BACKUPS = f"{RAIZ}/backups/dashboard_predicciones"
BASELINE = f"{RAIZ}/registro/deploy_baseline.json"
SCOPE = "cesarcm590"
LINK_PUBLICO = "https://dashboard-predicciones.vercel.app"
# Nada más entra a la carpeta que se publica: predicciones (index.html + data*.json) y análisis por liga
# (analisis.html + analisis_<liga>.json, Fase 20).
ARCHIVOS_PERMITIDOS = re.compile(r"^(index\.html|data(_[a-z]+)?\.json|analisis\.html|analisis_[a-z0-9_]+\.json|\.gitignore)$")
LLAVES_ANALISIS = ("meta", "control", "plantillas", "porteros", "impacto", "dependencia", "explorador", "lectura")
MAX_RESPALDOS = 8


def salir(msg, codigo=1):
    print(f"\n✗ {msg}")
    sys.exit(codigo)


def vercel(*args, timeout=300):
    """Ejecuta el CLI de Vercel dentro de la carpeta del dashboard y devuelve (código, salida)."""
    # `--scope` debe ir ANTES de un posible `--` (lo que va después se lo pasa tal cual a curl).
    args = list(args)
    corte = args.index("--") if "--" in args else len(args)
    args = args[:corte] + ["--scope", SCOPE] + args[corte:]
    p = subprocess.run(["npx", "--yes", "vercel", *args], cwd=CARPETA,
                       capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout + p.stderr


# --------------------------------------------------------------------------------------------
# 1) Validación local
# --------------------------------------------------------------------------------------------
def _sin_nan(x, ruta="raiz"):
    """Recorre el JSON y falla si hay NaN/inf (no son JSON válido para el navegador)."""
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        raise ValueError(f"valor no finito en {ruta}")
    if isinstance(x, dict):
        for k, v in x.items():
            _sin_nan(v, f"{ruta}.{k}")
    elif isinstance(x, list):
        for i, v in enumerate(x[:5000]):
            _sin_nan(v, f"{ruta}[{i}]")


def validar_local():
    print("1) Validando archivos locales...")
    errores = []
    archivos = sorted(f for f in os.listdir(CARPETA) if f not in (".vercel",))
    for f in archivos:
        if not ARCHIVOS_PERMITIDOS.match(f):
            errores.append(f"archivo no permitido dentro de la carpeta que se publica: {f} (¿dato personal?)")
    html = open(f"{CARPETA}/index.html", encoding="utf-8").read() if "index.html" in archivos else ""
    if "const LIGAS" not in html:
        errores.append("index.html no contiene el diccionario LIGAS")
    ligas_html = re.findall(r"archivo:\s*'\./([\w.]+)'", html)
    if not ligas_html:
        errores.append("no se encontraron archivos de liga en LIGAS")
    ultimo = _ultimo_respaldo()
    for f in ligas_html:
        ruta = f"{CARPETA}/{f}"
        if not os.path.exists(ruta):
            errores.append(f"{f}: lo referencia el HTML pero no existe")
            continue
        try:
            d = json.load(open(ruta, encoding="utf-8"), parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c)))
            _sin_nan(d)
        except Exception as e:
            errores.append(f"{f}: JSON inválido ({e})")
            continue
        for k in ("meta", "historico", "futuras", "seguimiento_en_vivo"):
            if k not in d:
                errores.append(f"{f}: falta la llave '{k}'")
        if not d.get("historico"):
            errores.append(f"{f}: histórico vacío")
        for p in d.get("futuras", []):
            if p.get("sin_perfil"):
                continue
            s = p["prob_local"] + p["prob_empate"] + p["prob_visitante"]
            if abs(s - 1) > 0.02:
                errores.append(f"{f}: probabilidades de {p['home_team']}-{p['away_team']} suman {s:.3f}")
        # Pérdida grande de datos respecto a la última versión buena (p. ej. un export truncado)
        if ultimo and os.path.exists(f"{ultimo}/{f}"):
            previo = len(json.load(open(f"{ultimo}/{f}", encoding="utf-8")).get("historico", []))
            if previo and len(d.get("historico", [])) < 0.9 * previo:
                errores.append(f"{f}: histórico bajó de {previo} a {len(d.get('historico', []))} partidos (>10%)")
    extras = validar_analisis(errores)
    if errores:
        print("\n".join(f"   - {e}" for e in errores))
        salir("La validación falló; NO se publicó nada.")
    print(f"   ✓ {len(ligas_html)} ligas válidas: {', '.join(ligas_html)}")
    if extras:
        print(f"   ✓ análisis por liga: {', '.join(extras)}")
    return ligas_html + extras


def validar_analisis(errores):
    """Página de análisis por liga (opcional): si existe, cada JSON que registra debe existir, ser JSON válido sin NaN
    y traer todas sus secciones. Devuelve los archivos a probar en staging y en el link público."""
    ruta_html = f"{CARPETA}/analisis.html"
    if not os.path.exists(ruta_html):
        return []
    html = open(ruta_html, encoding="utf-8").read()
    if "const LIGAS_ANALISIS" not in html:
        errores.append("analisis.html no contiene el diccionario LIGAS_ANALISIS")
        return []
    archivos = re.findall(r"archivo:\s*'\./(analisis_[\w]+\.json)'", html)
    if not archivos:
        errores.append("analisis.html no registra ningún analisis_<liga>.json")
    # Las secciones que no dependen de la liga elegida son JSON aparte, cada uno con sus propias secciones.
    sueltos = {"COMPARATIVA": ("meta", "series", "etiquetas", "resumen", "lectura"),
               "DEFENSIVO": ("meta", "hueco", "validacion", "estabilidad", "origen", "ligas", "mejores", "lectura"),
               "PERCENTIL": ("meta", "control", "escalera", "pares", "estabilidad", "plantel", "lectura"),
               "APOLONIO": ("meta", "ligas", "lectura")}
    llaves = {f: LLAVES_ANALISIS for f in archivos}
    for constante, esperadas in sueltos.items():
        for f in re.findall(rf"{constante} = '\./(analisis_\w+\.json)'", html):
            llaves[f] = esperadas
    # Los mapas de cancha son un JSON por liga dentro de un objeto, así que se buscan por su nombre de archivo.
    for f in re.findall(r"'\./(analisis_cancha_\w+\.json)'", html):
        llaves[f] = ("meta", "partidos", "sitios", "lectura")
    for f, esperadas in llaves.items():
        ruta = f"{CARPETA}/{f}"
        if not os.path.exists(ruta):
            errores.append(f"{f}: lo referencia analisis.html pero no existe")
            continue
        try:
            d = json.load(open(ruta, encoding="utf-8"), parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c)))
            _sin_nan(d)
        except Exception as e:
            errores.append(f"{f}: JSON inválido ({e})")
            continue
        faltan = [k for k in esperadas if k not in d]
        if faltan:
            errores.append(f"{f}: faltan las secciones {faltan}")
    return ["analisis.html", *llaves]


# --------------------------------------------------------------------------------------------
# 2) Respaldo local
# --------------------------------------------------------------------------------------------
def _ultimo_respaldo():
    if not os.path.isdir(BACKUPS):
        return None
    carpetas = sorted(os.listdir(BACKUPS))
    return f"{BACKUPS}/{carpetas[-1]}" if carpetas else None


def respaldar():
    print("2) Respaldando archivos...")
    destino = f"{BACKUPS}/{datetime.now():%Y%m%d_%H%M}"
    os.makedirs(destino, exist_ok=True)
    for f in os.listdir(CARPETA):
        if ARCHIVOS_PERMITIDOS.match(f):
            shutil.copy2(f"{CARPETA}/{f}", destino)
    for viejo in sorted(os.listdir(BACKUPS))[:-MAX_RESPALDOS]:
        shutil.rmtree(f"{BACKUPS}/{viejo}")
    print(f"   ✓ {destino}")
    return destino


# --------------------------------------------------------------------------------------------
# 3-6) Staging, pruebas, promoción, verificación
# --------------------------------------------------------------------------------------------
def sha(ruta_o_bytes):
    b = ruta_o_bytes if isinstance(ruta_o_bytes, bytes) else open(ruta_o_bytes, "rb").read()
    return hashlib.sha256(b).hexdigest()


def probar_staging(url, archivos):
    """Descarga cada archivo del despliegue en staging (con bypass de protección) y compara con el local."""
    print("4) Probando el despliegue en staging (el link público sigue intacto)...")
    for f in ["index.html", *archivos]:
        with tempfile.NamedTemporaryFile(delete=False) as t:
            tmp = t.name
        cod, salida = vercel("curl", f"/{f}", "--deployment", url, "--", "-s", "-o", tmp, "-w", "HTTP=%{http_code}")
        http = re.search(r"HTTP=(\d+)", salida)
        if cod != 0 or not http or http.group(1) != "200":
            salir(f"staging: {f} respondió {http.group(1) if http else 'sin respuesta'}. Link público NO modificado.")
        if sha(tmp) != sha(f"{CARPETA}/{f}"):
            salir(f"staging: {f} no es idéntico al archivo local (subida corrupta). Link público NO modificado.")
        os.unlink(tmp)
    print("   ✓ todos los archivos responden 200 y son idénticos al local")


def probar_publico(archivos):
    """Verifica el link público tras promover (con parámetro para saltar cachés)."""
    for f in ["index.html", *archivos]:
        try:
            req = urllib.request.Request(f"{LINK_PUBLICO}/{f}?v={int(datetime.now().timestamp())}",
                                         headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                if r.status != 200 or sha(r.read()) != sha(f"{CARPETA}/{f}"):
                    return False
        except Exception as e:
            print(f"   público: {f} falló ({e})")
            return False
    return True


def promover(url):
    cod, salida = vercel("promote", url, "--yes", timeout=400)
    return cod == 0, salida


# --------------------------------------------------------------------------------------------
# Línea base (última versión buena)
# --------------------------------------------------------------------------------------------
def leer_baseline():
    return json.load(open(BASELINE, encoding="utf-8")) if os.path.exists(BASELINE) else {"actual": None, "historial": []}


def guardar_baseline(url, snapshot):
    b = leer_baseline()
    if b["actual"]:
        b["historial"] = ([b["actual"]] + b["historial"])[:15]
    b["actual"] = {"url": url, "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"), "snapshot": snapshot, "link": LINK_PUBLICO}
    os.makedirs(os.path.dirname(BASELINE), exist_ok=True)
    json.dump(b, open(BASELINE, "w", encoding="utf-8"), indent=2, ensure_ascii=False)


def rollback(url=None):
    b = leer_baseline()
    destino = url or (b["actual"] or {}).get("url")
    if not destino:
        salir("No hay línea base registrada; pasa una URL de despliegue: --rollback <url>")
    print(f"Rollback: re-apuntando {LINK_PUBLICO} a {destino} ...")
    ok, salida = promover(destino)
    if not ok:
        print(salida[-600:])
        salir("El rollback falló; revisa `npx vercel ls dashboard-predicciones --scope cesarcm590` y promueve a mano.")
    print("✓ Rollback listo.")


# --------------------------------------------------------------------------------------------
# Programa principal
# --------------------------------------------------------------------------------------------
if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["--rollback"]:
        rollback(args[1] if len(args) > 1 else None)
        sys.exit(0)

    ligas = validar_local()
    if args[:1] == ["--validar"]:
        print("\n✓ Validación OK (no se publicó nada).")
        sys.exit(0)
    snapshot = respaldar()

    print("3) Construyendo despliegue en staging (--prod --skip-domain)...")
    cod, salida = vercel("deploy", "--prod", "--skip-domain", "--yes", timeout=600)
    m = re.search(r"https://dashboard-predicciones-[a-z0-9]+-" + SCOPE + r"\.vercel\.app", salida)
    if cod != 0 or not m:
        print(salida[-800:])
        salir("El despliegue en staging falló. El link público NO se modificó.")
    staging = m.group(0)
    print(f"   ✓ staging: {staging}")

    probar_staging(staging, ligas)
    if "--sin-promover" in args:
        print(f"\n✓ Staging probado y listo. Link público intacto. Para publicarlo: npx vercel promote {staging} --scope {SCOPE}")
        sys.exit(0)

    print("5) Promoviendo staging a producción...")
    ok, salida = promover(staging)
    if not ok:
        print(salida[-600:])
        salir("La promoción falló; el link público sigue en la versión anterior (sin cambios).")

    print("6) Verificando el link público...")
    if not probar_publico(ligas):
        print("   ✗ El link público no coincide con lo publicado: ROLLBACK automático a la línea base.")
        rollback()
        sys.exit(1)
    print("   ✓ link público OK")

    guardar_baseline(staging, snapshot)
    print(f"7) ✓ Nueva línea base guardada ({BASELINE}): {staging}")
    print(f"\n✓ Publicado: {LINK_PUBLICO}")
