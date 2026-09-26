"""Pruebas del calendario internacional (Fase 28)."""
import pandas as pd
import pytest

from futbol_bd import calendario


@pytest.fixture(scope="module")
def cal():
    return calendario.cargar_calendario()


def test_el_calendario_carga_y_las_fechas_son_coherentes(cal):
    assert len(cal) > 20
    assert (cal["fin"] >= cal["inicio"]).all(), "hay filas que terminan antes de empezar"
    assert cal["inicio"].min() >= pd.Timestamp("2026-01-01")
    assert cal["fin"].max() <= pd.Timestamp("2030-12-31")


def test_toda_fila_declara_si_su_fecha_es_oficial(cal):
    """La columna que distingue un dato verificado de una estimación no puede tener huecos ni valores raros."""
    assert cal["confirmado"].isin({"si", "provisional", "pendiente"}).all()
    assert cal["confirmado"].notna().all()
    # Y lo no confirmado tiene que quedar marcado para que ninguna función lo mezcle sin avisar.
    assert (cal.loc[cal["confirmado"] != "si", "es_provisional"]).all()
    assert not cal.loc[cal["confirmado"] == "si", "es_provisional"].any()


def test_el_mundial_2030_esta_y_es_el_final_del_camino(cal):
    m = cal[cal["competicion"].eq("Copa Mundial de la FIFA") & cal["fase"].eq("Torneo")]
    assert len(m) == 1
    assert m.iloc[0]["inicio"] == calendario.MUNDIAL_2030
    assert m.iloc[0]["confirmado"] == "si"


def test_solapamientos_marca_cuando_alguna_fecha_no_es_oficial():
    """Un choque calculado con fechas provisionales no vale lo mismo que uno con fechas oficiales."""
    d = pd.DataFrame([
        {"tipo": "torneo", "competicion": "A", "edicion": "2028", "fase": "Torneo",
         "inicio": pd.Timestamp("2028-06-01"), "fin": pd.Timestamp("2028-06-30"), "es_provisional": False},
        {"tipo": "torneo", "competicion": "B", "edicion": "2028", "fase": "Torneo",
         "inicio": pd.Timestamp("2028-06-15"), "fin": pd.Timestamp("2028-07-10"), "es_provisional": True},
        {"tipo": "torneo", "competicion": "C", "edicion": "2029", "fase": "Torneo",
         "inicio": pd.Timestamp("2029-01-01"), "fin": pd.Timestamp("2029-01-10"), "es_provisional": False},
    ])
    s = calendario.solapamientos(d)
    assert len(s) == 1, "solo A y B se pisan"
    assert s.iloc[0]["dias_solapados"] == 16          # del 15 al 30 de junio, ambos incluidos
    # Se comprueba por verdad, no con `is True`: al construir el DataFrame pandas lo guarda como np.True_.
    assert s.iloc[0]["alguna_provisional"]


def test_cuenta_atras_respeta_la_fecha_que_se_le_pasa(cal):
    """Se le pasa 'hoy' a propósito: si dependiera del reloj, la prueba cambiaría de resultado cada día."""
    c = calendario.cuenta_atras(cal, hoy=pd.Timestamp("2026-09-26"))
    assert (c["fin"] >= pd.Timestamp("2026-09-26")).all(), "no puede listar lo ya terminado"
    assert c["en_curso"].any(), "en septiembre de 2026 la Nations League está en curso"
    assert (c.loc[c["en_curso"], "dias_para_empezar"] == 0).all()
    # Nada de lo que devuelve empieza después del Mundial: es una cuenta atrás HACIA él.
    assert (c["inicio"] < calendario.MUNDIAL_2030).all()


def test_las_ventanas_fifa_no_se_pisan_entre_si(cal):
    """Control de la fuente: FIFA no programa dos ventanas a la vez. Si esto falla, el CSV tiene una errata."""
    v = cal[cal["tipo"] == "ventana"].sort_values("inicio")
    assert (v["inicio"].iloc[1:].to_numpy() > v["fin"].iloc[:-1].to_numpy()).all()
