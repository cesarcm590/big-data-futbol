"""
futbol_bd — código reutilizable del proyecto Big_data_futbol.

Hasta la Fase 18 toda la lógica vivía dentro de notebooks o de scripts sueltos en `scripts/`. A partir de la Fase 19
lo que se usa en más de un lugar se mueve aquí, a módulos importables y con pruebas (`tests/`), para que:
  - un notebook no pueda "pisar" la lógica de otro (ver el incidente del notebook 06 en PLAN_DE_TRABAJO.md, Fase 7);
  - la misma regla (p. ej. cómo se identifica a un jugador o cómo se puntúa en fantasy) sea idéntica en todo el proyecto;
  - cada decisión metodológica quede escrita en un solo lugar, junto al código que la aplica.

Módulos:
  plantillas  carga, auditoría y limpieza del panel de plantillas de FBref (2010-11 a 2025-26, 7 ligas)
  fantasy     puntos tipo fantasy (esquema FPL adaptado a las columnas que realmente tenemos)
  apolonio    diagramas de Voronoi ponderados (modalidad Apolonio: multiplicativa y aditiva) y su área de dominio

Uso desde un notebook en `notebooks/`:
    import sys; sys.path.insert(0, "..")
    from futbol_bd import plantillas, fantasy, apolonio
"""
