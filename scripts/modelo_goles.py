"""
Modelo de goles Poisson + corrección Dixon-Coles para predecir Local / Empate / Visitante.

IDEA (en corto)
---------------
En vez de predecir directamente "quién gana", se modelan los GOLES de cada equipo:
  1. Una regresión de Poisson estima cuántos goles espera anotar el local (lambda).
  2. Otra regresión de Poisson estima los goles esperados del visitante (mu).
  3. Con lambda y mu se arma una matriz de marcadores P(local anota i, visita anota j).
  4. Las probabilidades de resultado salen de sumar esa matriz:
        P(Local)     = suma de los marcadores donde i > j
        P(Empate)    = suma de la diagonal (0-0, 1-1, 2-2, ...)
        P(Visitante) = suma de los marcadores donde i < j
  Ventaja: la probabilidad de empate sale de forma directa y coherente con los goles esperados,
  en vez de ser una "clase" que un clasificador casi nunca elige.

CORRECCIÓN DIXON-COLES
----------------------
El Poisson independiente supone que los goles del local y del visitante no se afectan entre sí.
En la práctica los marcadores bajos (0-0, 1-0, 0-1, 1-1) no cumplen del todo esa independencia.
Dixon y Coles (1997) proponen multiplicar esas 4 celdas por un factor que depende de un parámetro
rho (estimado por máxima verosimilitud con los datos de entrenamiento) y renormalizar.
Con rho < 0 (lo que se observa aquí) suben los 0-0 y 1-1 y bajan los 1-0 y 0-1, es decir, sube un
poco la probabilidad de empate.

VARIABLES
---------
Las mismas 8 variables pre-partido del resto del proyecto (perfil del equipo local como local y del
visitante como visitante, calculado solo con partidos ANTERIORES al partido): goles a favor, goles en
contra, corners a favor y tarjetas a favor de cada uno.

ORDEN DE CLASES (importante, se usa en TODO el proyecto): columna 0 = Empate, 1 = Local, 2 = Visitante.
"""
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.optimize import minimize_scalar
from scipy.stats import poisson

CLASES = ["Empate", "Local", "Visitante"]
MAX_GOLES = 10  # la matriz de marcadores se trunca en 0..10 goles por equipo (la masa restante es ~0)
COLS_GOLES = ["local_goles_favor", "local_goles_contra", "local_corners_favor", "local_tarjetas_favor",
              "visita_goles_favor", "visita_goles_contra", "visita_corners_favor", "visita_tarjetas_favor"]


def matriz_marcadores(lam, mu, rho=0.0):
    """
    Para cada partido devuelve la matriz (MAX_GOLES+1) x (MAX_GOLES+1) con
    P(goles_local = i, goles_visita = j).

    lam, mu : arreglos de largo n con los goles esperados del local y del visitante.
    rho     : parámetro Dixon-Coles (0 = Poisson independiente puro).
    """
    k = np.arange(MAX_GOLES + 1)
    p_local = poisson.pmf(k[None, :], lam[:, None])       # n x K : P(el local anota i goles)
    p_visita = poisson.pmf(k[None, :], mu[:, None])       # n x K : P(el visitante anota j goles)
    m = p_local[:, :, None] * p_visita[:, None, :]        # independencia: producto de las marginales
    if rho != 0.0:
        # Factores tau de Dixon-Coles: solo tocan los 4 marcadores bajos.
        m[:, 0, 0] *= 1 - lam * mu * rho
        m[:, 0, 1] *= 1 + lam * rho
        m[:, 1, 0] *= 1 + mu * rho
        m[:, 1, 1] *= 1 - rho
    m = np.clip(m, 1e-12, None)                           # evita ceros/negativos numéricos
    return m / m.sum(axis=(1, 2), keepdims=True)          # renormaliza (truncamiento + corrección)


def probs_desde_matriz(m):
    """De la matriz de marcadores a un arreglo n x 3 con [P(Empate), P(Local), P(Visitante)]."""
    i, j = np.indices(m.shape[1:])
    p_empate = m[:, i == j].sum(axis=1)                   # diagonal
    p_local = m[:, i > j].sum(axis=1)
    p_visita = m[:, i < j].sum(axis=1)
    return np.column_stack([p_empate, p_local, p_visita])


def estimar_rho(goles_local, goles_visita, lam, mu):
    """Estima rho (Dixon-Coles) por máxima verosimilitud usando SOLO datos de entrenamiento."""
    gl = np.clip(goles_local, 0, MAX_GOLES)
    gv = np.clip(goles_visita, 0, MAX_GOLES)

    def neg_loglik(rho):
        m = matriz_marcadores(lam, mu, rho)
        return -np.log(m[np.arange(len(gl)), gl, gv]).sum()

    # Cotas de rho para que los factores tau sigan siendo positivos con goles esperados típicos (< ~3).
    return float(minimize_scalar(neg_loglik, bounds=(-0.3, 0.3), method="bounded").x)


class ModeloPoissonDC:
    """
    Ajuste y predicción del modelo. Uso:
        modelo = ModeloPoissonDC().ajustar(train)   # train con las columnas de `cols` + 'gl' + 'gv'
        pred = modelo.predecir(otros)               # dict con probs (n x 3), lam, mu

    cols: variables pre-partido a usar (por defecto las 8 de Liga MX). Se puede pasar otra lista, p. ej.
    agregando tiros a puerta, sin duplicar el modelo.
    """

    def __init__(self, cols=None):
        self.cols = list(cols) if cols is not None else list(COLS_GOLES)

    def ajustar(self, train):
        X = sm.add_constant(train[self.cols].astype(float), has_constant="add")
        self.glm_local = sm.GLM(train["gl"].astype(float), X, family=sm.families.Poisson()).fit()
        self.glm_visita = sm.GLM(train["gv"].astype(float), X, family=sm.families.Poisson()).fit()
        self.rho = estimar_rho(
            train["gl"].values.astype(int), train["gv"].values.astype(int),
            self.glm_local.predict(X).values, self.glm_visita.predict(X).values,
        )
        return self

    def predecir(self, datos):
        X = sm.add_constant(datos[self.cols].astype(float), has_constant="add")
        lam = self.glm_local.predict(X).values
        mu = self.glm_visita.predict(X).values
        probs = probs_desde_matriz(matriz_marcadores(lam, mu, self.rho))
        return {"probs": probs, "lam": lam, "mu": mu}


def ajustar_tarjetas(train):
    """Poisson de tarjetas totales por partido (mismo modelo que antes: solo perfil de tarjetas de los equipos)."""
    cols = ["local_tarjetas_favor", "visita_tarjetas_favor"]
    X = sm.add_constant(train[cols].astype(float), has_constant="add")
    glm = sm.GLM(train["total_game_cards_real"].astype(float), X, family=sm.families.Poisson()).fit()

    def predecir(datos):
        Xd = sm.add_constant(datos[cols].astype(float), has_constant="add")
        return glm.predict(Xd).values
    return predecir
