# Selecciones: Euro y Nations League

Análisis derivado del conjunto de datos de [Petro Ivaniuk](https://www.kaggle.com/datasets/piterfm/football-soccer-uefa-euro-1960-2024)
(CC BY-NC-SA 4.0). **Lee `LICENSE` antes de reutilizar nada de esta carpeta**: sus condiciones son distintas a las
del resto del repositorio.

## Por qué está aparte

La licencia del origen obliga a que lo derivado herede sus mismas condiciones (*CompartirIgual*). Aislarlo aquí evita
que esa obligación se extienda al proyecto entero, que no deriva de esos datos.

Los datos originales **no se redistribuyen**. Se bajan con:

```bash
python scripts/descargar_euro_nations.py
```

que los deja en `data/raw/euro_nations_kaggle/` (fuera del control de versiones).

## Qué aporta y qué no

**Sí**: resultados de Euro 1960-2024, **Nations League 2019-2025**, clasificatorias 1960-2024 y amistosos 2021-2025;
alineaciones de las Euros; árbitros, estadios y asistencia.

**No**: la Nations League **2026-27 en curso** (el conjunto se actualizó por última vez en junio de 2025).

**Cuidado con `start_position_x` / `start_position_y`** de las alineaciones: son la posición NOMINAL en el dibujo
táctico, en una rejilla propia que va de -1 a ~930, no metros sobre la cancha. No son comparables con las posiciones
medias calculadas a partir de eventos que usa `futbol_bd/cancha.py`, y su cobertura va del 26% al 99% según la
edición. Mezclarlas sería comparar cosas distintas.
