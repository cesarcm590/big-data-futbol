"""
Pruebas del emparejamiento de `scripts/unir_ids_fbref.py` con los tres tipos de cambio reales que hizo FBref entre el
scrapeo de agosto y la extracción de ids (2026-09-19): renombre de equipo, renombre de jugador y filas invertidas.
"""
import importlib.util
from pathlib import Path

import pandas as pd
import pytest

_ruta = Path(__file__).resolve().parents[1] / "scripts" / "unir_ids_fbref.py"
_spec = importlib.util.spec_from_file_location("unir_ids_fbref", _ruta)
unir = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(unir)

RAW = pd.DataFrame({
    "player": ["Ana", "Ben Brereton", "Carlos", "Carlos", "Dani"],
    "team": ["PSG", "Sevilla", "Leganés", "Athletic Club", "PSG"],
    "games": ["10", "20", "19", "34", "5"],
    "minutes": ["900", "1,500", "1,392", "2,627", "450"],
})


def test_pagina_identica_por_posicion():
    pagina = {"ok": True, "firma": unir.firma(RAW), "pids": "a1 b2 c3 c3 d4",
              "equipos": {"PSG": "t1", "Sevilla": "t2", "Leganés": "t3", "Athletic Club": "t4"}}
    res = unir.ids_de_pagina(RAW, pagina)
    assert res["player_id"].tolist() == ["a1", "b2", "c3", "c3", "d4"]
    assert res["team_id"].tolist() == ["t1", "t2", "t3", "t4", "t1"]


def test_firma_distinta_se_detecta():
    pagina = {"ok": True, "firma": "00000000", "pids": "a1 b2 c3 c3 d4", "equipos": {}}
    with pytest.raises(ValueError):
        unir.ids_de_pagina(RAW, pagina)


def test_pagina_con_renombres_y_filas_invertidas():
    # FBref hoy: "PSG" -> "Paris SG", "Ben Brereton" -> "Ben Brereton Díaz", y las dos filas de Carlos en otro orden.
    web = [["Ana", "Paris SG", "10", "900", "a1", "t1"],
           ["Ben Brereton Díaz", "Sevilla", "20", "1,500", "b2", "t2"],
           ["Carlos", "Athletic Club", "34", "2,627", "c3", "t4"],
           ["Carlos", "Leganés", "19", "1,392", "c3", "t3"],
           ["Dani", "Paris SG", "5", "450", "d4", "t1"]]
    res = unir.ids_de_pagina(RAW, {"ok": False, "filas": web})
    assert res["player_id"].tolist() == ["a1", "b2", "c3", "c3", "d4"]
    assert res["team_id"].tolist() == ["t1", "t2", "t3", "t4", "t1"]     # Leganés -> t3 aunque cambió de posición


def test_fila_sin_pareja_detiene_el_proceso():
    web = [["Ana", "Paris SG", "10", "900", "a1", "t1"],
           ["Otro", "Sevilla", "99", "1", "x9", "t2"],          # números distintos: no se puede emparejar
           ["Carlos", "Leganés", "19", "1,392", "c3", "t3"],
           ["Carlos", "Athletic Club", "34", "2,627", "c3", "t4"],
           ["Dani", "Paris SG", "5", "450", "d4", "t1"]]
    with pytest.raises(ValueError, match="sin pareja"):
        unir.ids_de_pagina(RAW, {"ok": False, "filas": web})
