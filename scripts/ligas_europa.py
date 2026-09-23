"""
Configuración de las ligas europeas que se alimentan de football-data.co.uk (mismo formato de CSV en todas).

Agregar una liga nueva = agregar una entrada aquí + registrarla en el diccionario LIGAS del dashboard
(dashboard-predicciones/index.html) y en scripts/congelar_predicciones.py. Los scripts genéricos
(europa_construir_dataset.py, europa_comparar_con_mercado.py, export_predicciones_europa.py) reciben la clave de la
liga como argumento:   python scripts/export_predicciones_europa.py laliga

Campos:
  nombre        nombre que se muestra en el dashboard
  en_texto      nombre con artículo para frases ("En la Bundesliga...")
  div           columna `Div` de football-data (E0 = Premier, SP1 = La Liga, D1 = Bundesliga, I1 = Serie A, F1 = Ligue 1)
  carpeta_raw   carpeta de data/raw/ con los CSV por temporada ({prefijo}_AAAA.csv)
  dataset       CSV unificado en data/processed/
  salida_json   archivo que consume el dashboard
  registro      CSV de predicciones congeladas (seguimiento en vivo) en registro/
  inicio_en_vivo / inicio_label   desde qué fecha cuentan los partidos en el seguimiento oficial en vivo
  nombres       renombrado de equipos para mostrarlos completos (football-data usa abreviaturas)
  ventana       tamaño de la ventana de perfil (partidos por lado); None = expandible
  nota_mercado  frase sobre la comparación con el mercado (solo se afirma lo que se probó fuera de muestra)
"""
RAIZ = "/Users/javiercarrillo/Proyectos/Big_data_futbol"
RUTA_FIXTURES = f"{RAIZ}/data/raw/fixtures_football_data.csv"   # calendario futuro de TODAS las ligas (fixtures.csv)

LIGAS_EUROPA = {
    "premier": {
        "nombre": "Premier League", "en_texto": "la Premier League", "div": "E0", "prefijo": "E0", "carpeta_raw": "premier_odds",
        "dataset": "premier_matches_2015_2026.csv", "salida_json": "data_premier.json",
        "registro": "predicciones_congeladas_premier.csv",
        "inicio_en_vivo": "2026-09-19", "inicio_label": "el 19 sept 2026 (J5, sin Brentford–Chelsea)",
        "nombres": {}, "ventana": 38,
        "nota_mercado": "en pruebas fuera de muestra el modelo no lo supera ni le agrega información",
    },
    "laliga": {
        "nombre": "La Liga", "en_texto": "La Liga", "div": "SP1", "prefijo": "SP1", "carpeta_raw": "laliga_odds",
        "dataset": "laliga_matches_2015_2026.csv", "salida_json": "data_laliga.json",
        "registro": "predicciones_congeladas_laliga.csv",
        "inicio_en_vivo": "2026-09-19", "inicio_label": "el 19 sept 2026 (sin Espanyol–Elche, ya jugado al congelar)",
        "nombres": {
            "Ath Madrid": "Atlético Madrid", "Ath Bilbao": "Athletic Club", "Sociedad": "Real Sociedad",
            "Espanol": "Espanyol", "Vallecano": "Rayo Vallecano", "Alaves": "Alavés", "La Coruna": "Deportivo La Coruña",
            "Santander": "Racing Santander", "Malaga": "Málaga", "Celta": "Celta Vigo", "Betis": "Real Betis",
            "Oviedo": "Real Oviedo", "Sp Gijon": "Sporting Gijón", "Cadiz": "Cádiz", "Almeria": "Almería",
            "Leganes": "Leganés", "Valladolid": "Real Valladolid", "Granada": "Granada",
        },
        "ventana": 38,
        "nota_mercado": "en pruebas fuera de muestra el modelo no lo supera ni le agrega información",
    },
    "bundesliga": {
        "nombre": "Bundesliga", "en_texto": "la Bundesliga", "div": "D1", "prefijo": "D1", "carpeta_raw": "bundesliga_odds",
        "dataset": "bundesliga_matches_2015_2026.csv", "salida_json": "data_bundesliga.json",
        "registro": "predicciones_congeladas_bundesliga.csv",
        "inicio_en_vivo": "2026-09-19", "inicio_label": "el 19 sept 2026 (J4, sin Bayern–Union Berlin, ya jugado al congelar)",
        "nombres": {
            "Ein Frankfurt": "Eintracht Frankfurt", "M'gladbach": "Mönchengladbach", "Dortmund": "Borussia Dortmund",
            "Leverkusen": "Bayer Leverkusen", "FC Koln": "FC Köln", "Fortuna Dusseldorf": "Fortuna Düsseldorf",
            "Greuther Furth": "Greuther Fürth", "Nurnberg": "Nürnberg", "St Pauli": "FC St. Pauli",
        },
        # Con 18 equipos (17 partidos por sede y temporada) la ventana casi no importa: en la comparación fuera de muestra
        # la expandible (None) y la de 34 partidos (2 temporadas) dieron log-loss 1.0076 vs 1.0089 (diferencia trivial);
        # se usa la expandible por ser la de menor log-loss.
        "ventana": None,
        "nota_mercado": "en pruebas fuera de muestra el modelo no lo supera ni le agrega información",
    },
    "seriea": {
        "nombre": "Serie A", "en_texto": "la Serie A", "div": "I1", "prefijo": "I1", "carpeta_raw": "seriea_odds",
        "dataset": "seriea_matches_2015_2026.csv", "salida_json": "data_seriea.json",
        "registro": "predicciones_congeladas_seriea.csv",
        "inicio_en_vivo": "2026-09-19", "inicio_label": "el 19 sept 2026 (J5, sin Monza–Sassuolo, ya jugado al congelar)",
        "nombres": {"Verona": "Hellas Verona", "Milan": "AC Milan", "Roma": "AS Roma"},
        # La ventana casi no importa (expandible con tiros a puerta 0.9800 vs mejor variante 0.9793 en log-loss
        # fuera de muestra); se usa la expandible (None) con las 12 variables, igual que la Bundesliga.
        "ventana": None,
        "nota_mercado": "en pruebas fuera de muestra el modelo no lo supera ni le agrega información",
    },
}


def renombrar_equipos(df, nombres, columnas=("HomeTeam", "AwayTeam")):
    """Aplica el renombrado de equipos (si hay) a las columnas de equipo de un DataFrame."""
    if not nombres:
        return df
    df = df.copy()
    for c in columnas:
        df[c] = df[c].replace(nombres)
    return df
