"""
Pruebas de la geometría de futbol_bd.apolonio contra resultados que se conocen analíticamente.

Si la rasterización tuviera un error (ejes invertidos, píxeles desplazados, la regla mal escrita), los diagramas se
verían "razonables" pero serían falsos. Estas pruebas lo impiden comparando con casos donde la respuesta exacta se
conoce de antemano.
"""
import numpy as np
import pytest
from scipy.spatial import cKDTree

from futbol_bd import apolonio


def test_pesos_iguales_es_voronoi_normal():
    # Con todos los pesos iguales, los dos modos ponderados deben coincidir píxel a píxel con el vecino más cercano.
    rng = np.random.default_rng(7)
    sitios = rng.random((15, 2))
    etiq_vor, xs, ys = apolonio.etiquetar(sitios, modo="voronoi", resolucion=200)
    X, Y = np.meshgrid(xs, ys)
    _, vecino = cKDTree(sitios).query(np.column_stack([X.ravel(), Y.ravel()]))
    assert np.array_equal(etiq_vor.ravel(), vecino)
    for modo in ("multiplicativo", "aditivo"):
        etiq, _, _ = apolonio.etiquetar(sitios, np.full(15, 3.0), modo=modo, resolucion=200)
        assert np.array_equal(etiq, etiq_vor)


def test_frontera_multiplicativa_es_circulo_de_apolonio():
    # Dos sitios, uno con el doble de peso: la celda del débil debe ser exactamente el círculo de Apolonio.
    # k = 1/2, distancia 0.3 -> centro = (a − b/4)/(3/4) = (0.35, 0.5), radio = 0.5·0.3/(3/4) = 0.2: el círculo va de
    # x = 0.15 a 0.55 y cabe entero en [0, 1]² (si se saliera, el área rasterizada sería la del círculo recortado).
    debil, fuerte = np.array([0.45, 0.5]), np.array([0.75, 0.5])
    centro, radio = apolonio.circulo_apolonio(debil, 1.0, fuerte, 2.0)
    assert np.allclose(centro, [0.35, 0.5]) and np.isclose(radio, 0.2)

    etiq, xs, ys = apolonio.etiquetar([debil, fuerte], [1.0, 2.0], resolucion=800)
    X, Y = np.meshgrid(xs, ys)
    dentro = np.hypot(X - centro[0], Y - centro[1]) < radio
    # Todos los píxeles salvo los que tocan la frontera deben coincidir con el círculo analítico.
    lejos_del_borde = np.abs(np.hypot(X - centro[0], Y - centro[1]) - radio) > 2 / 800
    assert np.array_equal((etiq == 0)[lejos_del_borde], dentro[lejos_del_borde])
    # Y el área rasterizada debe aproximar π r².
    assert apolonio.areas(etiq, 2)[0] == pytest.approx(np.pi * radio**2, rel=0.01)


def test_aditivo_sitio_dominado_se_queda_sin_celda():
    # En modo aditivo, si w_fuerte − w_débil ≥ distancia entre ellos, el débil no gana ningún punto del plano.
    sitios = [[0.4, 0.5], [0.6, 0.5]]  # distancia 0.2
    etiq, _, _ = apolonio.etiquetar(sitios, [0.0, 0.25], modo="aditivo", resolucion=300)
    assert apolonio.areas(etiq, 2)[0] == 0
    # Con una ventaja menor que la distancia, el débil sí conserva celda.
    etiq, _, _ = apolonio.etiquetar(sitios, [0.0, 0.15], modo="aditivo", resolucion=300)
    assert apolonio.areas(etiq, 2)[0] > 0


def test_multiplicativo_invariante_a_escala_de_pesos():
    rng = np.random.default_rng(3)
    sitios, pesos = rng.random((10, 2)), rng.uniform(50, 250, 10)
    a, _, _ = apolonio.etiquetar(sitios, pesos, resolucion=150)
    b, _, _ = apolonio.etiquetar(sitios, pesos * 37.5, resolucion=150)
    assert np.array_equal(a, b)


def test_areas_suman_uno_y_orientacion_de_ejes():
    etiq, xs, ys = apolonio.etiquetar([[0.1, 0.9], [0.9, 0.1]], modo="voronoi", resolucion=100,
                                      limites=((0, 2), (0, 1)))
    assert apolonio.areas(etiq, 2).sum() == pytest.approx(1.0)
    # fila = y, columna = x: la esquina superior izquierda (x chico, y grande) pertenece al sitio 0.
    assert etiq[-1, 0] == 0 and etiq[0, -1] == 1
    assert xs.max() < 2 and ys.max() < 1


def test_errores_de_entrada():
    with pytest.raises(ValueError):
        apolonio.etiquetar([[0, 0]], [0.0], modo="multiplicativo")
    with pytest.raises(ValueError):
        apolonio.etiquetar([[0, 0]], None, modo="aditivo")
    with pytest.raises(ValueError):
        apolonio.circulo_apolonio([0, 0], 2.0, [1, 1], 1.0)
