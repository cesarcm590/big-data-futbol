# Permite `from futbol_bd import ...` al correr `pytest` desde la raíz del proyecto sin instalar el paquete.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
