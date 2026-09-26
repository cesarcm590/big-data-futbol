"""
Baja el conjunto de Euro y Nations League de Kaggle a data/raw/ (que no se versiona).

    python scripts/descargar_euro_nations.py

FUENTE Y LICENCIA
-----------------
"Football - Soccer - UEFA EURO, 1960 - 2024", de Petro Ivaniuk (piterfm), bajo CC BY-NC-SA 4.0:
https://www.kaggle.com/datasets/piterfm/football-soccer-uefa-euro-1960-2024

Los datos NO se redistribuyen: por eso se descargan a `data/raw/`, que está fuera del control de versiones. Lo que
sí se publica —lo que calculamos a partir de ellos— vive en `selecciones/`, con su propia licencia CC BY-NC-SA,
aislado para que la cláusula de CompartirIgual no alcance al resto del repositorio.

No hacen falta credenciales de Kaggle: el endpoint público de descarga responde sin autenticar.

QUÉ TRAE Y QUÉ NO
-----------------
Sí: Euro 1960-2024, Nations League 2019-2025, clasificatorias 1960-2024, amistosos 2021-2025, alineaciones de las
Euros, y el cuerpo arbitral completo con la nacionalidad de cada miembro.
No: la Nations League 2026-27 en curso. El conjunto se actualizó por última vez en junio de 2025.
"""
import io
import sys
import zipfile
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parents[1]
DESTINO = RAIZ / "data" / "raw" / "euro_nations_kaggle"
URL = "https://www.kaggle.com/api/v1/datasets/download/piterfm/football-soccer-uefa-euro-1960-2024"


def main():
    print(f"Bajando de Kaggle -> {DESTINO.relative_to(RAIZ)}")
    try:
        r = requests.get(URL, timeout=180)
        r.raise_for_status()
        z = zipfile.ZipFile(io.BytesIO(r.content))
    except Exception as e:
        print(f"✗ no se pudo bajar ({type(e).__name__}: {str(e)[:70]})")
        return 1
    # Se valida antes de escribir: si Kaggle devolviera una página de error con código 200, el zip no abriría o no
    # traería los CSV esperados, y sobrescribir con eso dejaría la carpeta inservible sin avisar.
    csvs = [n for n in z.namelist() if n.endswith(".csv")]
    if len(csvs) < 20:
        print(f"✗ el archivo bajado solo trae {len(csvs)} CSV; se esperaban más de 20. No se escribe nada.")
        return 1
    DESTINO.mkdir(parents=True, exist_ok=True)
    z.extractall(DESTINO)
    print(f"✓ {len(csvs)} CSV extraídos ({sum(f.file_size for f in z.infolist()) / 1e6:.0f} MB sin comprimir)")
    print("  Licencia CC BY-NC-SA 4.0 · Petro Ivaniuk · ver selecciones/LICENSE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
