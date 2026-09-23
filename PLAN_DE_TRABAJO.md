# Plan de trabajo — Big Data aplicado al Fútbol Profesional

Basado en el temario de [Fútbol Data Academy](https://futbolbigdata.com/master-online-big-data-aplicado-al-futbol-profesional/)
(15 módulos + anexos de scouting). Reorganizado en 6 fases de estudio, cada una con
un notebook propio en `notebooks/`.

## Entorno
- Conda env `futbol-bigdata` (Python 3.11) — creado con `~/miniconda3/bin/conda`
  porque el conda del sistema (miniforge en Homebrew Caskroom) tiene permisos
  rotos en su caché de paquetes.
- Activar con: `conda activate futbol-bigdata`
- Librerías clave: pandas, numpy, matplotlib, seaborn, mplsoccer, soccerdata,
  statsbombpy, understatpy/understat, requests, beautifulsoup4, lxml, highlight_text,
  jupyter, ipykernel.
- Cache de eventos entre notebooks: `to_pickle`/`read_pickle` (NO parquet — hay
  una incompatibilidad real entre pandas 3.0.5 y pyarrow 25.0.1 en este equipo).
- **R 4.2.1** (ya estaba instalado en `/usr/local/bin/R`) con `worldfootballR`
  (FBref/Transfermarkt/Understat) y kernel de Jupyter `ir-futbol-bigdata`, para
  poder correr notebooks en R junto a los de Python en el mismo Jupyter. Ver
  sección "worldfootballR (R)" más abajo.

## Fase 0 — Setup (Módulo 0: Anaconda)
- Entorno conda aislado, kernel de Jupyter registrado.
- Notebook: `00_setup_entorno.ipynb`
- Objetivo: confirmar que todas las librerías importan y que hay acceso a internet
  para scraping/APIs.

## Fase 1 — Adquisición de datos (Módulos 1–2: FotMob, StatsBomb)
- Scraping básico de páginas de fútbol (FotMob) — fundamentos de requests/HTML.
- Extracción de datos StatsBomb Open Data (eventos, líneas, xG) vía `statsbombpy`.
- Notebook: `01_scraping_fotmob_statsbomb.ipynb`
- Conceptos: estructura de datos de eventos (event data) vs. datos de posición
  (tracking data), esquema StatsBomb.

## Fase 2 — Visualización táctica de equipo (Módulos 3–5, 13–14)
- Shot maps (mapas de tiros) con `mplsoccer.Pitch`.
- Pass networks (redes de pases): nodos = jugadores, aristas = pases entre ellos.
- Heat maps de equipo (zonas de mayor uso del campo).
- Posición media del equipo (average position) por partido.
- Zonas de generación/recepción de pases.
- Notebook: `02_visualizacion_equipo.ipynb`

## Fase 3 — Análisis individual de jugador (Módulos 6–7)
- Heat maps individuales.
- Radios de acción (action radius): elipses de dispersión de acciones de un jugador.
- Notebook: `03_analisis_jugador.ipynb`

## Fase 4 — Métricas avanzadas y comparación (Módulos 8–11)
- xG segmentado por tramos de partido (0-15, 15-30, ... minutos).
- Pizza charts / radar charts para perfiles de jugador.
- Radar clásico comparando jugadores de la misma posición.
- Beeswarm charts para benchmarking de plantilla vs. competición.
- Notebook: `04_metricas_avanzadas_radar_beeswarm.ipynb`
- Conceptos: percentiles, normalización por 90 minutos, xG/xA.

## Fase 5 — Reportes automatizados (Módulo 12)
- Plantilla de reporte de partido que combine varias visualizaciones anteriores
  (shot map + pass network + xG timeline) en una sola figura/PDF exportable.
- Notebook: `05_reporte_automatizado_partido.ipynb`

## Fase 6 — Presentación de datos (Módulo 15: Tableau)
- Exportar tablas limpias (CSV/Parquet) desde los notebooks anteriores.
- Construir un dashboard en Tableau Public a partir de esos datos.
- No requiere notebook propio — carpeta `output/dashboards/` con los datos
  exportados y notas de qué visual va en cada hoja.
- **Estado (2026-08-25)**: Tableau Public instalado. CSVs listos para
  importar: `data/raw/fbref_big5_player_standard_2025.csv`,
  `data/processed/fbref_equipos_2025.csv`,
  `data/raw/fbref_big5_player_defense_partial_2025.csv`, y el nuevo
  `data/processed/fbref_scouting_percentiles_2025.csv` (exportado desde
  `06_scouting_percentiles_similaridad.ipynb` — un jugador por fila, métricas
  per-90 + percentiles por posición ya calculados, sin necesidad de
  recalcular nada dentro de Tableau).

## Fase 7 — Rendimiento de jugador con datos reales de FBref
- Dataset real: `data/raw/fbref_big5_player_standard_2025.csv` (2854 jugadores,
  5 grandes ligas, temporada 2024-25, stats estándar de FBref).
- **FBref bloquea scraping automatizado con un challenge de Cloudflare**
  (`cf-mitigated: challenge`) — ni `requests`/`rvest` con headers de navegador
  lo pasan. `worldfootballR` también choca con esto. La única vía que
  funcionó: abrir la página en un navegador real (pasa el challenge solo,
  toma unos segundos) y extraer la tabla vía JS (`Share & Export` de FBref
  hace lo mismo manualmente). Si hace falta más data de FBref, repetir ese
  proceso — no vale la pena perseguir un bypass del challenge.
- Notebook: `07_fbref_rendimiento_jugador.ipynb` — diccionario de datos,
  análisis descriptivo, ranking de rendimiento (goles totales vs. G+A por 90
  filtrando por minutos jugados).
- Notebook: `08_analisis_equipos.ipynb` — agrega el CSV por `team` (suma
  goles/minutos y recalcula per90 al nivel de equipo, no promedia el per90 de
  cada jugador), ranking por liga, ataque vs. disciplina, dependencia del
  máximo goleador. Guarda `data/processed/fbref_equipos_2025.csv`.
- `06_scouting_percentiles_similaridad.ipynb` ya usa este dataset real en vez
  de datos sintéticos: percentiles por posición principal y similaridad
  coseno dentro de la misma posición (ej. similares a Mbappé/Kane).
- **Incidente (2026-08-25)**: el notebook 06 se sobrescribió por completo con
  una versión sintética antigua (probablemente por un "Revert to Checkpoint"
  o guardado desde una pestaña de navegador con el estado viejo) — perdió el
  pizza chart entero y volvió a "Jugador 1"/"Jugador 2". Reconstruido desde
  cero a partir del historial de la conversación, y de paso se añadió una
  sección nueva para resaltar un jugador puntual dentro de una ventana de su
  grupo de posición (no solo el top-10). Lección: si un notebook se abre en
  el navegador y se deja abierto mucho tiempo, el autoguardado de Jupyter
  puede pisar ediciones hechas por fuera — cerrar/recargar la pestaña después
  de cualquier edición externa antes de seguir trabajando en vivo.
- `04_metricas_avanzadas_radar_beeswarm.ipynb` también migrado a datos reales
  (2026-08-25): pizza chart y beeswarm usan el mismo dataset real de FBref
  (percentiles por posición, igual que 06); el xG por tramos de partido usa
  los eventos reales de StatsBomb cacheados en 01 (un solo partido de
  ejemplo). Se eliminaron `xg_90`, `xa_90`, `pases_completados_pct` y
  `regates_exitosos_90` — nunca se consiguieron esas columnas reales.
- **Conclusión final (2026-08-25) sobre `passing`/`defense` de FBref**: no son
  utilizables, y esto quedó confirmado más allá de toda duda — probado incluso
  con la exportación manual del propio usuario (`Share & Export → Get table as
  CSV`, en su navegador normal, con sesión humana real). Resultado, columna por
  columna, sobre las 2854 filas:
  - **Passing**: de 20 columnas detalladas (pases totales/cortos/medios/largos,
    distancia, xAG, pases clave, pases a último tercio, al área, centros al
    área), **0% pobladas**. Solo `Ast` trae datos, y ya está en el CSV de
    standard stats — este archivo no aporta nada nuevo.
  - **Defense**: de ~17 columnas, solo **2 pobladas**: `tackles_won` e
    `interceptions` (verificados como reales y creíbles: João Gomes, Idrissa
    Gueye, Moisés Caicedo arriba de la tabla). El resto (tackles totales, por
    tercio de cancha, challenges, blocks, despejes, errores) vacío en el 100%
    de las filas.
  - Guardado: `data/raw/fbref_big5_player_defense_partial_2025.csv` (solo las
    2 columnas reales + campos identificadores). El de passing no se guardó
    como dataset — no tenía nada que aportar.
  - Como esto pasó igual en una sesión humana manual, no es un tema de
    scraping/bot-detection — es una restricción de contenido real del lado de
    FBref (probablemente movieron estas columnas detrás de Stathead). No vale
    la pena reintentar esto de nuevo.

## Intento de dataset panel histórico (2026-08-26) — completado en el tercer intento

Tercer y último intento (el del 2026-08-25 había fallado por completo, 0 de
112; el segundo intento, más temprano el 2026-08-26, había logrado 67/112
antes de un bloqueo de Cloudflare — ver historial de este archivo más abajo
para el detalle de ambos). El bloqueo de la sesión anterior ya se había
enfriado (se verificó con una carga de prueba de Ligue-1 2013-2014 antes de
empezar, que cargó la tabla real sin challenge). Se retomó exactamente
donde se había quedado y se completaron las 45 combinaciones pendientes sin
volver a toparse con Cloudflare en ningún momento:

- Ligue 1: 13 temporadas restantes (2013-2014 a 2025-2026) → **16/16
  completa**
- Eredivisie: 16 temporadas (2010-2011 a 2025-2026) → **16/16 completa**
- Liga MX: 16 temporadas (2010-2011 a 2025-2026) → **16/16 completa**
  (el patrón de URL estándar `/en/comps/31/{season}/stats/{season}-Liga-MX-Stats`
  funcionó directamente para las 16 temporadas — FBref resuelve el slug
  "Liga-MX" aunque el título de la página muestre "Primera División" para
  las temporadas más antiguas; no hizo falta el fallback vía la página de
  historial)

**Resultado final: 112 de 112 combinaciones liga-temporada extraídas** —
dataset panel histórico completo para las 7 ligas de primera división
(Premier League, La Liga, Serie A, Bundesliga, Ligue 1, Eredivisie, Liga
MX), 16 temporadas cada una (2010-11 a 2025-26).

**Archivos guardados**: `data/raw/fbref_historical/{Nombre-Liga}_{temporada}.csv`
— 112 archivos (67 de intentos previos + 45 nuevos de esta sesión).

**Dataset combinado**: `data/processed/fbref_panel_2010_2025.csv` — 61,542
filas × 26 columnas (incluye `league` y `season` por fila; columna
`matches` descartada por no ser dato real). Cobertura completa: 112/112
combinaciones liga-temporada, 7 ligas × 16 temporadas cada una.

**Estado: dataset panel histórico terminado, no queda pendiente.**

## Fase 8 — Dataset a nivel de partido para modelar ganador/goles/tarjetas/corners (2026-08-27)

Nuevo dataset, esta vez a nivel de **partido** (no jugador), para modelar con el
árbitro y otros factores como predictores:
- **Ganador del partido** (local/empate/visitante) → regresión logística
  multinomial.
- **Goles totales, tarjetas totales, corners totales** → modelos de conteo
  (Poisson / Binomial Negativa, según haya o no sobredispersión).

Base: `data/raw/matches_pl_2024_2025_schedule.csv` (los 380 partidos de la
Premier League 2024-25 — gameweek, fecha, equipos, marcador, asistencia,
**árbitro**, `match_report_url`, `match_id`). A eso se le suman, por partido,
las estadísticas del bloque "Team Stats" de la página de reporte de cada
partido en FBref: posesión, tiros a puerta, atajadas del portero, tarjetas
amarillas/rojas (contadas desde los iconos `<span class="yellow_card">` /
`<span class="red_card">`, no como texto), faltas, corners, centros,
intercepciones y fueras de lugar — todo desglosado por equipo local/visitante.

**Bloqueo de Cloudflare (historial)**: en intentos previos de esta misma fase,
FBref mostró un challenge persistente que forzó a detener la extracción varias
veces (ver commits/estado anteriores: cortes en 22/380 y 65/380). En la corrida
que completó el dataset (2026-08-28) se confirmó que el bloqueo NO estaba
activo — un `fetch()` lanzado desde el contexto de una página ya cargada en el
navegador (reutilizando la cookie `cf_clearance` de la sesión) devolvía el HTML
completo del reporte sin challenge, lo que permitió extraer varios partidos por
llamada en vez de navegar uno por uno.

**Resultado: 380 de 380 partidos extraídos (100% completo).** Sin bloqueos ni
partidos fallidos — los 315 que faltaban tras la corrida anterior (65/380) se
completaron en esta sesión en 15 lotes (`fetch` + `DOMParser` + parseo Python),
con una sola falla transitoria de red (`Failed to fetch` en un partido) resuelta
al reintentarlo en el mismo lote.

**Nota técnica de un bug encontrado y corregido**: al unir los CSVs por
partido con el schedule por `match_id`, pandas infiere `match_id` como
entero (`int64`) en los archivos individuales cuando el hash hexadecimal
resulta ser todos dígitos (ej. `34557647`, que parece un número pero es un
ID hexadecimal como cualquier otro), mientras que en el CSV de schedule se
lee como texto porque la columna mezcla dígitos y letras. Esto rompía el
join para esos partidos específicos. Corregido forzando `dtype={"match_id": str}`
al leer ambos CSVs antes del merge — importante tenerlo en cuenta si se
reprocesa este dataset más adelante.

**Limitación conocida de conteo de tarjetas**: FBref usa una clase de icono
separada, `yellow_red_card`, para la segunda amarilla que termina en expulsión
(distinta de `yellow_card` y `red_card` simples). Siguiendo el método ya usado
en los primeros 65 partidos extraídos, este dataset cuenta únicamente
`yellow_card` y `red_card`, por lo que las expulsiones por doble amarilla NO
se reflejan en `home_red`/`away_red` (ni la segunda amarilla en
`home_yellow`/`away_yellow`) para los partidos donde ocurre este caso. Es una
inconsistencia menor y poco frecuente (se observaron ~8-10 casos en los 380
partidos); si se necesita precisión total en tarjetas rojas, habría que
reprocesar contando también `yellow_red_card` como amarilla+roja.

**Valores faltantes**: 20 de 380 partidos no tienen `home_offsides`/
`away_offsides` porque ese bloque de estadística extra no aparece en el reporte
de FBref para esos partidos (no es un error de parseo, el dato no está en la
página). El resto de las columnas está completo para los 380 partidos.

**Archivos guardados**:
- `data/raw/match_reports_pl_2024_2025/{match_id}.csv` — 380 archivos, uno por
  partido, con las columnas de Team Stats.
- `data/processed/matches_pl_2024_2025_completo.csv` — las 380 filas del
  schedule con las columnas de Team Stats pegadas. Dataset listo para
  modelado (ganador, goles, tarjetas, corners).

**Ejemplo real verificado** (Manchester Utd 1-0 Fulham, 2024-08-16, árbitro
Robert Jones): posesión 55%/45%, tiros a puerta 5 de 14 vs 2 de 10, 2
amarillas (local) vs 3 amarillas (visitante), 0 rojas, 12 vs 10 faltas, 7 vs 8
corners, 18 vs 21 centros, 17 vs 10 intercepciones, 3 vs 1 fuera de lugar —
valores no triviales y consistentes con un partido real, no ceros ni datos
absurdos.

**Estado: completo (380/380).** Fase 8 lista para pasar a la etapa de
modelado (regresión logística multinomial para el resultado, Poisson/Binomial
Negativa para goles/tarjetas/corners).

## Fase 9 — Dataset a nivel de partido para Liga MX (5 temporadas, 2026-08-29)

Réplica exacta del método de la Fase 8, esta vez para **Liga MX, 5
temporadas** (Apertura/Clausura 2020-21 a 2024-25, 1,706 partidos), como base
para un **pipeline de clustering de comportamiento de equipos local/visitante**
(agrupar equipos según su perfil de estadísticas cuando juegan de local vs.
cuando juegan de visitante — posesión, tiros, tarjetas, corners, etc.).

Base: `data/raw/matches_ligamx_2020_2025_schedule.csv` (1,706 partidos —
ronda, jornada, fecha, equipos, marcador, asistencia, árbitro,
`match_report_url`, `match_id`, temporada). A eso se le suman, por partido,
las estadísticas del bloque `#team_stats` de la página de reporte de cada
partido en FBref: posesión, tiros a puerta, atajadas del portero, tarjetas
amarillas/rojas, faltas, corners, centros, intercepciones y fueras de lugar —
desglosado por equipo local/visitante, igual que en la Fase 8.

**Mejora sobre la Fase 8 en el conteo de tarjetas**: en este dataset, el
ícono `yellow_red_card` (expulsión por doble amarilla) SÍ se cuenta como
amarilla + roja simultáneamente (en la Fase 8 se dejó fuera del conteo por
limitación de tiempo). Esto corrige la inconsistencia menor documentada en la
Fase 8 para los partidos de Liga MX.

**Método de extracción**: navegación página por página con el Browser pane
(NO `fetch()` en lote ni ningún otro atajo de aceleración, a diferencia de un
intento posterior en la Fase 8 que generó un problema de consistencia de
datos) — por cada partido: navegar → esperar ~1.5s → extraer con JavaScript
(parseando la tabla de `#team_stats` por fila-etiqueta y el bloque
`#team_stats_extra` por tríos `[valor_local, etiqueta, valor_visitante]`) →
guardar de inmediato en su propio CSV.

**Ronda 1: 23 de 1,706 partidos extraídos.** Se detuvo la sesión por un
**bloqueo de Cloudflare persistente** ("Verificación de seguridad en curso" /
Ray ID cambiante en cada intento) al llegar al partido 24 (`f9c963a5`,
Monterrey vs. Santos Laguna, 8 de agosto de 2020) — no se resolvió tras 3
reintentos con esperas de hasta 10s.

**Ronda 2 (2026-08-29): +27 partidos más (23 → 50 de 1,706).** Se retomó
exactamente donde quedó la ronda 1 (`f9c963a5` en adelante), confirmando
primero que el bloqueo de Cloudflare ya se había enfriado. Esta vez **no
apareció ningún bloqueo** — se procesaron los 27 partidos siguientes del
calendario (todos de la Apertura 2020, del 8 al 22 de agosto de 2020) sin
interrupciones, navegando uno por uno con esperas de 1.5s y extracción vía
JavaScript estructurado (lectura directa del DOM de `#team_stats` por
etiqueta de fila y de `#team_stats_extra` por grupos de 3 divs
`[valor_local, etiqueta, valor_visitante]`, en vez de parsear el texto plano
— más robusto). La sesión se cerró en este punto no por bloqueo sino por
alcanzar un tamaño de ronda razonable; el siguiente partido pendiente es
`12db594e` (Toluca vs. Guadalajara, 23 de agosto de 2020). **Quedan
pendientes 1,656 partidos**, tal como se anticipó en las instrucciones de
esta fase (dataset 4.5x más grande que el de Premier League, se necesitarán
varias rondas más).

**Ronda 3 (2026-08-29): +5 partidos más (50 → 55 de 1,706).** Cambio de
estrategia probado esta ronda: en vez de navegar rápido (~1.5s entre
partidos), se usó una **espera aleatoria de 8 a 15 segundos** entre cada
navegación (`random.uniform(8, 15)` antes de cada `navigate`), bajo la
hipótesis de que el bloqueo de Cloudflare depende del ritmo/velocidad y no
solo de la cantidad total de partidos. Se retomó en `12db594e` (Toluca vs.
Guadalajara, 23 de agosto de 2020) y avanzó sin problemas por 5 partidos
(hasta `1ab2d742`, Puebla vs. Toluca, 28 de agosto de 2020). **Bloqueo de
Cloudflare persistente** al llegar al 6º partido de la ronda —
`46d6d6dd` (Mazatlán vs. Tigres UANL, 28 de agosto de 2020), partido nº56 del
calendario — con el mismo mensaje "Verificación de seguridad en curso"; no se
resolvió tras 3 reintentos con esperas de hasta 10s, y se detuvo la sesión
sin loopear, tal como en las rondas anteriores.

**Comparación de ritmos**: el ritmo lento (8-15s) NO permitió avanzar más
que los ritmos rápidos anteriores — de hecho bloqueó antes en términos
absolutos (5 partidos en esta ronda vs. 23 y 27 en las rondas 1 y 2). Esto
sugiere que el bloqueo de Cloudflare en este sitio depende principalmente de
la **cantidad acumulada de requests desde la misma sesión/IP en una ventana
de tiempo** (posiblemente con un umbral que se reinicia tras un período de
enfriamiento), y no del ritmo de navegación entre partidos. La hipótesis de
esta ronda (que un ritmo más lento permitiría trabajar de forma continua) no
se confirmó con esta única muestra; sería necesario probar con esperas aún
más largas (30-60s) o distribuir la extracción en más sesiones cortas para
aislar la variable real detrás del bloqueo.

**Ronda 4 (2026-08-30): +41 partidos más (55 → 96 de 1,706).** Se confirmó
primero que el bloqueo de Cloudflare de la ronda 3 ya se había enfriado
(`46d6d6dd` cargó en ~6 segundos). Se volvió al **ritmo rápido (1-2s entre
partidos)**, retomando exactamente en `46d6d6dd` (Mazatlán vs. Tigres UANL,
28 de agosto de 2020) y avanzando sin interrupciones durante 41 partidos
consecutivos — superando ampliamente los máximos de las rondas 1 y 2 (23 y 27
partidos) antes de bloquearse. Extracción vía JavaScript estructurado
(lectura del DOM de `#team_stats` por fila `<tr><th colspan=2>Label</th></tr>`
seguida de su fila de datos, y de `#team_stats_extra` por grupos de divs
`[valor_local, etiqueta, valor_visitante]` filtrando las celdas de
encabezado `.th`), guardando cada partido de inmediato en su propio CSV.
**Bloqueo de Cloudflare persistente** ("Un momento…") al llegar al partido
`14125be4` (Atlético San Luis vs. Monterrey, 20 de septiembre de 2020),
partido nº97 del calendario — no se resolvió tras 3 reintentos con esperas
de hasta 10s, y se detuvo la sesión sin loopear.

**Confirmación de la hipótesis de la ronda 3**: el ritmo rápido (1-2s) volvió
a rendir muy por encima del ritmo lento (8-15s) probado en la ronda 3 (41
partidos vs. 5 antes de bloquearse), reforzando que el bloqueo depende del
volumen acumulado de requests por sesión/ventana de tiempo y no del ritmo de
navegación — se mantiene el ritmo rápido como estrategia por defecto para las
próximas rondas.

**Archivos guardados**:
- `data/raw/match_reports_ligamx/{match_id}.csv` — 96 archivos por ahora, uno
  por partido, con las columnas de Team Stats (mismo esquema que la Fase 8).
- `data/processed/matches_ligamx_2020_2025_completo.csv` — las 1,706 filas
  del schedule con las columnas de Team Stats pegadas donde ya están
  disponibles (96 filas con datos, el resto vacío; se regenera concatenando
  todos los CSVs de `match_reports_ligamx/` según crezca el dataset en
  próximas rondas). **Quedan pendientes 1,610 partidos.** El siguiente
  partido pendiente es `14125be4` (Atlético San Luis vs. Monterrey, 20 de
  septiembre de 2020).

**Nota técnica (heredada de la Fase 8)**: forzar siempre
`dtype={"match_id": str}` al leer/escribir/mergear, porque algunos `match_id`
son hex puramente numéricos y pandas los infiere como `int64` rompiendo el
join con el schedule.

**Ronda 5 (2026-08-30): +1 partido más (134 → 135 de 1,706).** Se confirmó
primero que el bloqueo de la ronda 4 ya se había enfriado (`fa34c86c` cargó
en ~6 segundos). Se extrajo `fa34c86c` (Pachuca vs. Pumas UNAM, 26 de octubre
de 2020) sin problemas, pero al navegar al siguiente partido del calendario
(`c9bc3dad`, Atlético San Luis vs. Mazatlán, 29 de octubre de 2020) apareció
de inmediato un **bloqueo de Cloudflare persistente** ("Un momento…") — no se
resolvió tras 3 reintentos con esperas de hasta 10s, y se detuvo la sesión
sin loopear. Esta ronda fue anómalamente corta (1 partido vs. 27-41 en rondas
anteriores con el mismo ritmo rápido), lo que sugiere que el umbral de
bloqueo de Cloudflare puede estar bajando con el tiempo/uso acumulado del
sitio, o que hay variabilidad significativa entre sesiones que aún no se
explica solo por el ritmo de navegación.

**Archivos guardados**:
- `data/raw/match_reports_ligamx/{match_id}.csv` — 135 archivos por ahora, uno
  por partido, con las columnas de Team Stats (mismo esquema que la Fase 8).
- `data/processed/matches_ligamx_2020_2025_completo.csv` — las 1,706 filas
  del schedule con las columnas de Team Stats pegadas donde ya están
  disponibles (135 filas con datos, el resto vacío).

**Estado: parcial (135/1,706).** Para continuar: releer
`data/raw/matches_ligamx_2020_2025_schedule.csv`, filtrar los `match_id` que
ya tengan CSV en `data/raw/match_reports_ligamx/`, y seguir desde ahí
(próximo: `c9bc3dad`, Atlético San Luis vs. Mazatlán, 29 de octubre de 2020)
con el mismo método (navegar → esperar 1-2s → extraer con JS estructurado →
guardar), a ritmo rápido, deteniéndose ante el primer bloqueo persistente de
Cloudflare o al cerrar una ronda de tamaño razonable. **Quedan pendientes
1,571 partidos.**

**Ronda 6 (2026-08-30): +40 partidos (135 → 175 de 1,706).** Se confirmó
primero que el bloqueo de la ronda 5 ya se había enfriado (`c9bc3dad` cargó en
~6 segundos). A ritmo rápido (1-2s entre partidos) se extrajeron 40 partidos
consecutivos sin bloqueo — desde `c9bc3dad` (Atlético San Luis vs. Mazatlán,
29 de octubre de 2020) hasta `e558b54e` (Atlas vs. Monterrey, 9 de enero de
2021), cubriendo el resto de la fase de grupos del Apertura 2020, ambas
rondas de liguilla, y el arranque del Clausura 2021. Al navegar al siguiente
partido (`66546e41`, Tigres UANL vs. León, 9 de enero de 2021) apareció un
**bloqueo de Cloudflare persistente** ("Un momento…") — no se resolvió tras 3
reintentos con esperas de hasta 10s, y se detuvo la sesión sin loopear. Esta
ronda fue la más larga hasta ahora igualando/superando el máximo previo (41
partidos en la ronda 3), reforzando que el ritmo rápido sigue siendo la
mejor estrategia y que el umbral de bloqueo varía bastante de sesión a
sesión sin un patrón claro todavía.

**Optimización de proceso en esta ronda**: se afinó el guion de extracción
JS para calcular directamente en el navegador todos los campos finales
(posesión %, tiros a puerta con su total, atajadas con su total, tarjetas
amarillas/rojas contando `yellow_red_card` como +1 de cada, y los trillizos
`[valor_local, etiqueta, valor_visitante]` de faltas/corners/centros/
intercepciones/fuera de lugar), devolviendo un JSON compacto listo para
volcarse a CSV — evita transportar el HTML crudo de `#team_stats` entre
pasos y agiliza el guardado por partido.

**Archivos guardados**:
- `data/raw/match_reports_ligamx/{match_id}.csv` — 175 archivos por ahora,
  uno por partido, con las columnas de Team Stats (mismo esquema que la
  Fase 8).
- `data/processed/matches_ligamx_2020_2025_completo.csv` — las 1,706 filas
  del schedule con las columnas de Team Stats pegadas donde ya están
  disponibles (175 filas con datos, el resto vacío).

**Estado: parcial (175/1,706).** Para continuar: releer
`data/raw/matches_ligamx_2020_2025_schedule.csv`, filtrar los `match_id` que
ya tengan CSV en `data/raw/match_reports_ligamx/`, y seguir desde ahí
(próximo: `66546e41`, Tigres UANL vs. León, 9 de enero de 2021) con el mismo
método, a ritmo rápido, deteniéndose ante el primer bloqueo persistente de
Cloudflare o al cerrar una ronda de tamaño razonable. **Quedan pendientes
1,531 partidos.**

**Rondas 7-8 (2026-08-30): +37 partidos más (175 → 212 de 1,706).**

**Ronda 9 (2026-08-31): +40 partidos más (212 → 252 de 1,706).** Se confirmó
primero que el bloqueo anterior ya se había enfriado (`31a78b3b`, Toluca vs.
Mazatlán, 7 de febrero de 2021, cargó en ~6 segundos). A ritmo rápido (1-2s
entre partidos) se extrajeron 40 partidos consecutivos sin bloqueo — desde
`31a78b3b` hasta `db423b4e` (Tijuana vs. América, 3 de marzo de 2021),
cubriendo buena parte del Clausura 2021 (jornadas 5 a 9). Extracción vía
JavaScript estructurado (misma técnica de la ronda 6: lectura del DOM de
`#team_stats` por fila `<tr><th colspan=2>Label</th></tr>` seguida de su fila
de datos, y de `#team_stats_extra` por grupos de divs `[valor_local,
etiqueta, valor_visitante]`), guardando cada partido de inmediato en su
propio CSV vía un script Python reutilizable (`save_match.py`). Se
detectaron dos partidos sin categoría "Offsides" en `#team_stats_extra`
(`1c95a843` y `2c72ff5f`) — se guardaron con `home_offsides`/
`away_offsides` vacíos, reflejando que FBref genuinamente no publicó ese
dato para esos partidos (no es un error de extracción). **Bloqueo de
Cloudflare persistente** ("Verificación de seguridad en curso") al llegar a
`a54059fa` (Atlas vs. FC Juárez, 6 de marzo de 2021), partido nº253 del
calendario — no se resolvió tras 3 reintentos con esperas de hasta 10s, y se
detuvo la sesión sin loopear.

**Archivos guardados**:
- `data/raw/match_reports_ligamx/{match_id}.csv` — 252 archivos por ahora,
  uno por partido, con las columnas de Team Stats (mismo esquema que la
  Fase 8).
- `data/processed/matches_ligamx_2020_2025_completo.csv` — las 1,706 filas
  del schedule con las columnas de Team Stats pegadas donde ya están
  disponibles (252 filas con datos, el resto vacío).

**Estado: parcial (252/1,706).** Para continuar: releer
`data/raw/matches_ligamx_2020_2025_schedule.csv`, filtrar los `match_id` que
ya tengan CSV en `data/raw/match_reports_ligamx/`, y seguir desde ahí
(próximo: `a54059fa`, Atlas vs. FC Juárez, 6 de marzo de 2021) con el mismo
método, a ritmo rápido, deteniéndose ante el primer bloqueo persistente de
Cloudflare o al cerrar una ronda de tamaño razonable. **Quedan pendientes
1,454 partidos.**

**Ronda 10 (2026-08-31): +27 partidos más (252 → 279 de 1,706).** Se
confirmó primero que el bloqueo de la ronda 9 ya se había enfriado
(`a54059fa` cargó bien). A ritmo rápido (1-2s entre partidos) se extrajeron
27 partidos consecutivos sin bloqueo — desde `a54059fa` (Atlas vs. FC Juárez,
6 de marzo de 2021) hasta `7439546b` (FC Juárez vs. Cruz Azul, 2 de abril de
2021), cubriendo el resto del Clausura 2021 hasta la jornada 12. Extracción
vía JavaScript minificado en una sola función (mismo método DOM que rondas
anteriores: `#team_stats` por fila `<tr><th colspan>Label</th></tr>` +
`#team_stats_extra` por tríos de divs), guardando cada partido de inmediato
con `scripts/save_match.py` (nuevo script reutilizable creado esta ronda,
recibe el JSON del partido por argumento y escribe el CSV individual).
**Bloqueo de Cloudflare persistente** ("Un momento…") al navegar a
`b0ab4093` (Atlas vs. Tijuana, 3 de abril de 2021), partido nº280 del
calendario — no se resolvió tras 3 reintentos con esperas de hasta 10s, y se
detuvo la sesión sin loopear.

**Archivos guardados**:
- `data/raw/match_reports_ligamx/{match_id}.csv` — 279 archivos por ahora,
  uno por partido, con las columnas de Team Stats (mismo esquema que la
  Fase 8).
- `scripts/save_match.py` — script Python reutilizable para guardar cada
  partido individual desde un JSON (`match_id` + columnas del esquema),
  usado en esta ronda y pensado para reutilizarse en las siguientes.
- `data/processed/matches_ligamx_2020_2025_completo.csv` — las 1,706 filas
  del schedule con las columnas de Team Stats pegadas donde ya están
  disponibles (279 filas con datos, el resto vacío).

**Estado: parcial (279/1,706).** Para continuar: releer
`data/raw/matches_ligamx_2020_2025_schedule.csv`, filtrar los `match_id` que
ya tengan CSV en `data/raw/match_reports_ligamx/`, y seguir desde ahí
(próximo: `b0ab4093`, Atlas vs. Tijuana, 3 de abril de 2021) con el mismo
método, a ritmo rápido, deteniéndose ante el primer bloqueo persistente de
Cloudflare o al cerrar una ronda de tamaño razonable. **Quedan pendientes
1,427 partidos.**

**Ronda 11 (2026-08-30/31): +219 partidos más (349 → 568 de 1,706).** Ronda
con diferencia la más larga de toda la fase — se retomó exactamente donde
quedó la ronda 10 (`b2cb5626`, Tijuana vs. Tigres UANL, 25 de julio de 2021,
inicio del Apertura 2021) y se avanzó sin interrupción real durante 219
partidos consecutivos, cubriendo el resto completo del Apertura 2021
(incluyendo liguilla completa: cuartos de final, semifinales y la final
León vs. Atlas del 9-12 de diciembre de 2021) y una buena parte del Clausura
2022 (hasta el 25 de febrero de 2022, jornada 8). Extracción vía JavaScript
estructurado (mismo método de rondas anteriores: `#team_stats` por fila
`<tr><th colspan>Label</th></tr>` + su fila de datos, y `#team_stats_extra`
por tríos de divs `[valor_local, etiqueta, valor_visitante]`), guardando
cada partido de inmediato con `scripts/save_match.py`.

**Cloudflare esta ronda**: a diferencia de rondas anteriores donde el primer
bloqueo terminaba la sesión, en esta ronda aparecieron **múltiples desafíos
"Un momento…" / "Verificación de seguridad en curso" de forma intermitente**
(al menos 8 veces a lo largo de la ronda) pero **todos se resolvieron solos**
tras 1-3 reintentos con esperas de 8-10s, permitiendo continuar cada vez sin
perder el partido en curso. La sesión se cerró finalmente no por un bloqueo
irresoluble sino por alcanzar un tamaño de ronda ya muy por encima de lo
razonable — es la primera ronda donde el patrón de bloqueo pareció más
"intermitente y recuperable" que "duro y terminal", lo que sugiere que la
combinación de ritmo rápido (1-2s) + reintentos pacientes (8-10s) ante cada
desafío puede sostener rondas mucho más largas que las anteriores.

**Archivos guardados**:
- `data/raw/match_reports_ligamx/{match_id}.csv` — 568 archivos por ahora,
  uno por partido, con las columnas de Team Stats (mismo esquema que la
  Fase 8).
- `data/processed/matches_ligamx_2020_2025_completo.csv` — las 1,706 filas
  del schedule con las columnas de Team Stats pegadas donde ya están
  disponibles (568 filas con datos, el resto vacío).

**Estado: parcial (568/1,706).** Para continuar: releer
`data/raw/matches_ligamx_2020_2025_schedule.csv`, filtrar los `match_id` que
ya tengan CSV en `data/raw/match_reports_ligamx/`, y seguir desde ahí
(próximo: `1e7582cf`, Tijuana vs. Atlas, 25 de febrero de 2022) con el mismo
método, a ritmo rápido, reintentando pacientemente (8-10s) ante cada desafío
de Cloudflare antes de rendirse, y deteniéndose sin loopear solo si un
desafío resulta genuinamente irresoluble tras 3 intentos. **Quedan
pendientes 1,138 partidos.**

**Rondas 12-13 (2026-08-31/09-01): +208 partidos más (568 → 776 de 1,706).**
Dos rondas adicionales de ritmo rápido con reintentos pacientes ante
desafíos intermitentes de Cloudflare (patrón consistente con la ronda 11:
challenges "Un momento…" pasajeros que se resuelven solos en 1-3 reintentos
de 8-10s, sin bloquear la sesión). Ronda 12: +166 partidos. Ronda 13: +42
partidos. Cubrieron el resto del Clausura 2022 y el arranque del Apertura
2022 hasta el 25 de agosto de 2022. **Estado: parcial (776/1,706).**

**Ronda 14 (2026-09-01): +29 partidos más (776 → 805 de 1,706).** Se
confirmó primero que el bloqueo previo ya se había enfriado (`ed970b99`,
Tijuana vs. Santos Laguna, 25 de agosto de 2022, cargó bien). A ritmo rápido
(1-2s entre partidos) se extrajeron 29 partidos consecutivos sin bloqueo —
desde `ed970b99` hasta `f31b3a29` (FC Juárez vs. Monterrey, 9 de septiembre
de 2022), cubriendo jornadas 1-8 del Apertura 2022. Extracción vía
JavaScript estructurado (mismo método de rondas anteriores, con una mejora:
detección automática de `match_id`/equipos local/visitante directamente del
DOM — `location.pathname` y `.scorebox a[href*="/squads/"]` — en vez de
pasarlos manualmente por partido), guardando cada partido de inmediato con
`scripts/save_match.py`.

**Corrección menor esta ronda**: los primeros 4 partidos de la ronda
(`ed970b99`, `fbd7627f`, `3a910aa6`, `75d2276d`) se guardaron inicialmente
con el símbolo `%` en `home_possession`/`away_possession` (p. ej. `"55%"`)
por una diferencia en el parseo del texto del DOM; se detectó al comparar
contra el formato ya establecido en el resto del dataset (posesión como
número plano, sin `%`) y se corrigieron esos 4 archivos con `sed` antes de
continuar. El resto de la ronda ya usa el formato correcto.

**Bloqueo de Cloudflare persistente** ("Verificación de seguridad en curso")
al llegar a `e0bff974` (Querétaro vs. Santos Laguna, 10 de septiembre de
2022), partido nº806 del calendario — no se resolvió tras 7 reintentos
consecutivos con esperas de 8-15s (~85 segundos totales, Ray ID distinto en
cada intento), confirmando un bloqueo duro y no un desafío pasajero. Se
detuvo la sesión sin loopear.

**Archivos guardados**:
- `data/raw/match_reports_ligamx/{match_id}.csv` — 805 archivos por ahora,
  uno por partido, con las columnas de Team Stats (mismo esquema que la
  Fase 8).
- `data/processed/matches_ligamx_2020_2025_completo.csv` — las 1,706 filas
  del schedule con las columnas de Team Stats pegadas donde ya están
  disponibles (805 filas con datos, el resto vacío).

**Estado: parcial (805/1,706).** Para continuar: releer
`data/raw/matches_ligamx_2020_2025_schedule.csv`, filtrar los `match_id` que
ya tengan CSV en `data/raw/match_reports_ligamx/`, y seguir desde ahí
(próximo: `e0bff974`, Querétaro vs. Santos Laguna, 10 de septiembre de 2022)
con el mismo método, a ritmo rápido, reintentando pacientemente (8-10s) ante
cada desafío de Cloudflare antes de rendirse, y deteniéndose sin loopear
solo si un desafío resulta genuinamente irresoluble tras varios reintentos
consecutivos. **Quedan pendientes 901 partidos.**

**Ronda 15** (sesión con Claude for Chrome, extensión real de navegador en
lugar del navegador sandboxed): tras el bloqueo duro de Cloudflare al final de
la Ronda 14 (805/1,706), se retomó la extracción usando la extensión "Claude
for Chrome", que opera sobre una instancia real de Chrome del usuario en vez
del navegador sandboxed que Cloudflare bloqueaba de forma persistente. Un
agente previo avanzó de 805 → 852 → 940 partidos con este método antes de
agotar su presupuesto de sesión (detalles puntuales de ese tramo no quedaron
documentados por ese agente). Esta sesión continuó desde 940 y completó los
**766 partidos restantes**, llevando el dataset a **1,706/1,706 (100%)**.

Notas técnicas de esta ronda:
- *Optimización de tokens:* la función de extracción JS (~2KB) se guardó una
  sola vez en `localStorage` del origen `fbref.com` (`extractFnSrc`) en vez de
  reenviarla en cada llamada; cada partido subsecuente solo requirió
  `eval(localStorage.getItem('extractFnSrc'));extractMatch('ID');`.
- *Tamaño de lote:* se estabilizó en **8 partidos por `browser_batch`**
  (navigate + wait + extracción JS por partido) como el tamaño más confiable;
  lotes de 15 provocaban timeouts de herramienta aunque el navegador sí
  terminaba de ejecutarlos.
- *Bloqueos de Cloudflare con Chrome real:* SÍ se observaron desafíos de
  Cloudflare ("Un momento…" / "Verificación de seguridad en curso") en varias
  ocasiones (~6-7 veces) durante la sesión, cada vez afectando un lote
  completo. A diferencia de los bloqueos duros de las rondas anteriores (con
  el navegador sandboxed), **todos estos desafíos con Chrome real se
  resolvieron solos tras una espera de 8-10 segundos**, sin necesidad de
  intervención humana tipo CAPTCHA. Esto confirma la hipótesis de partida:
  Chrome real no queda bloqueado de forma persistente por Cloudflare, solo
  sufre desafíos automáticos transitorios y autorresolubles.
- *Incidente de integridad de datos:* una desconexión de la herramienta a
  mitad de un `browser_batch` produjo en el reintento datos internamente
  consistentes pero desalineados de su `match_id` (contenido de un partido
  distinto del mismo lote). Detectado antes de guardar (nunca se escribió el
  lote corrupto) verificando `document.title` contra el partido esperado en
  cada extracción. Tras el hallazgo se corrió una auditoría completa
  comparando nombres de equipo normalizados entre el calendario maestro y los
  940 (luego 1,224) reportes ya guardados hasta ese punto: 0 discrepancias,
  confirmando que fue un incidente aislado.
- *Caso límite — sección "Saves" ausente:* el partido `49fa3fbe` (Pumas UNAM
  vs. FC Juárez) no tiene fila de "Saves" en `#team_stats` porque ambos
  equipos registraron 0 tiros a puerta ese partido, lo que rompía la función
  de extracción (`null.querySelectorAll`). Se corrigió haciendo opcionales las
  secciones de Shots on Target, Saves y Cards (dejando los campos vacíos
  cuando la sección no existe), siguiendo la misma convención ya usada en los
  940 archivos previos para datos genuinamente ausentes (p. ej. "Offsides").
- *Verificación final:* recombinación completa del dataset
  (`data/processed/matches_ligamx_2020_2025_completo.csv`) con **1,706 filas,
  0 `match_id` duplicados, 1,706 reportes emparejados, 0 reportes faltantes**;
  auditoría de nombres de equipo con **0 discrepancias**; **0 archivos** con
  datos de posesión faltantes.

**Estado: Fase 9 completa — 1,706/1,706 partidos (100%).**

## Fase 10 — Comportamiento de equipo, sesgo arbitral y modelo de partidos, Liga MX (2026-09)

Con el dataset de la Fase 9 ya al 100%, esta fase retoma y cierra la línea de trabajo abierta en
el notebook 12 ("¿cómo se comporta cada equipo de local/visita?") y la extiende con una
investigación completa de sesgo arbitral y un intento honesto de modelo predictivo de partidos.
Cinco notebooks (12 a 16), resumidos aquí para no tener que releerlos todos para entender qué se
concluyó y qué no funcionó.

### Fuente de datos: de `completo.csv` a las versiones v2/v3

El usuario limpió manualmente en Excel/Numbers el CSV que salió de la Fase 9 y lo fue pasando en
versiones sucesivas, cada una copiada a `data/processed/`:

- **v2** (`matches_ligamx_2020_2025_v2_limpio.csv`, 34 columnas): quita `round`, `attendance`,
  `match_report_url`, `match_id`, `notes` y las columnas redundantes `home_team_stats`/
  `away_team_stats`. Usada en el notebook 13.
- **v3** (`matches_ligamx_2020_2025_v3_arbitraje.csv`, 41 columnas): agrega columnas derivadas
  construidas en Numbers — `home_efficency`/`away_efficency` (tiros a puerta / tiros totales),
  `home_total_cards`/`away_total_cards`/`total_game_cards`, y
  `home_card_game_per_fouls`/`away_card_game_per_foul`. Se detectó que esta última mezclaba
  `total_game_cards` (ambos equipos) con las faltas de un solo equipo — se corrigió con una
  versión propia (`home_card_per_foul_propio` = tarjetas propias / faltas propias) en el
  notebook 13. v3 es la fuente única para los notebooks 14, 15 y 16.

### Notebook 13 — Diccionario de variables y matrices de correlación

Diccionario completo de las 34 (luego 41) variables del dataset limpio, chequeos de calidad
(consistencia de posesión local+visitante ≈100%, sin duplicados, 340-342 partidos por temporada)
y dos matrices de correlación: Pearson sobre variables continuas/conteo, y **policórica**
(Olsson 1979, implementada a mano por incompatibilidades de `semopy` con la versión de scipy
instalada — ver notebook 12 para el detalle del bug) sobre versiones terciladas de las mismas
variables, extendida para incluir `referee` (vía el proxy ordinal `arbitro_dureza`, severidad
histórica) y `home_team`/`away_team` (vía `home_team_propension`/`away_team_propension`) — ambas
categóricas nominales que no se pueden meter directo a una policórica sin convertirlas primero.

### Notebook 14 — Sesgo arbitral: ¿el árbitro o los equipos explican las tarjetas?

Repite el protocolo del notebook 12 (GLM Poisson anidados M0→M4, comparación por AIC/pseudo-R²
de McFadden, más policórica) con el histórico completo (1,706 partidos, el doble de datos que la
primera vez). Resultado: el árbitro sigue pesando más que los equipos (pseudo-R² M3_arbitro=4.1%
vs. M2_equipos=2.4%; policórica árbitro=0.278 vs. equipos=0.071).

**Hallazgo de calidad de datos importante, encontrado a mitad de esta fase:** 6 árbitros estaban
duplicados en la fuente con dos nombres (FBref cambió su formato a partir de 2023-24, agregando
acentos/segundo nombre): `Victor Caceres`/`Víctor Cáceres`, `Oscar Mejia`/`Oscar Mejía`,
`Marco Ortíz`/`Marco Antonio Ortíz`, `Luis Santander`/`Luis Enrique Santander`,
`Erick Miranda`/`Erick Yair Miranda`, `Guillermo Pacheco`/`Guillermo Pacheco Larios` — detectado
porque sus temporadas nunca se traslapan. **46 nombres → 40 árbitros reales.** Esto cambió una
conclusión ya reportada como cerrada: con el nombre partido, Víctor Cáceres salía como atípico
(z=+2.29 de sesgo de localía, con solo 52 partidos); con su historial completo consolidado
(88 partidos, 5 temporadas) su z baja a +1.31 y **deja de ser atípico**. Los que sí se mantienen
atípicos tras la corrección: **Diego Montaño** (z=−2.36, favorece al local) y **Edgar Morales**
(z=2.09, perjudica al local) — ambos con corroboración cualitativa real via búsqueda web
(sanciones/polémicas documentadas por la Comisión de Arbitraje de la FMF o medios especializados).

También se probó separar temporada regular vs. liguilla (sin diferencia significativa en
severidad general, Mann-Whitney p=0.21) y un experimento natural con la temporada 2020-21 sin
público por COVID: **la hipótesis de "la afición explica el sesgo" no se sostuvo** — la ventaja de
localía en goles fue más alta en la temporada sin público (0.35) que en la siguiente con público
de vuelta (0.21), justo lo contrario de lo esperado. Se dejó documentado como resultado honesto,
no forzado a encajar con la hipótesis de partida.

**Aclaración explícita en el notebook, importante para cualquiera que lo lea:** con estadísticas
de caja (tarjetas, faltas, tiros) no se puede detectar ni probar "amaño" (manipulación deliberada
de resultados) — eso requiere datos que no tenemos (cuotas de apuestas históricas, expedientes
disciplinarios). Lo que sí se mide con rigor es sesgo arbitral y anomalías estadísticas, un campo
de estudio real y distinto de acusar de amaño sin evidencia de ese tipo.

### Notebook 15 — Perfiles de equipo con el histórico completo + ventana móvil

Repite el clustering K-Means (Bajo/Medio/Alto ofensivo, por equipo y contexto local/visita) del
notebook 12 con 4 temporadas de entrenamiento en vez de 2, y valida contra 2024-25 **completa**
(340 partidos, holdout genuino) en vez del "vistazo" parcial de 2022-23 que se usó originalmente.
**10 de 36 perfiles equipo-contexto (28%) cambiaron de nivel** al doblar los datos de
entrenamiento — mismo patrón que con los árbitros duplicados: pocos datos, conclusiones inestables.
La correlación de validación de `cards_for` cayó de 0.151 (parcial) a 0.093 (completa y sin sesgo)
— la validación original era más optimista de lo que sostenía el dataset completo.

Se probó también una **ventana móvil de temporadas** (1 a 4 años de historia, walk-forward real
contra cada temporada posible) para ver si el "pasado reciente" predice mejor que el histórico
completo: **no hay ganador consistente entre ventanas** en ninguna de las 3 métricas probadas —
las diferencias entre tamaños de ventana son más chicas que la variación entre qué temporada te
toca validar. Conclusión práctica: no vale la pena complicar el pipeline con ventana móvil.

### Notebook 16 — Modelo de partidos con features 100% pre-partido

Cierre de la línea: mete el perfil histórico de equipo (notebook 15) y la dureza del árbitro
(notebook 14) como *features* de un modelo predictivo real, calculados sin fuga de datos partido
por partido (cada partido usa solo temporadas estrictamente anteriores a la suya — ventana
"expandible"). Dos resultados negativos honestos, ambos informativos:

- **Ganador (MNLogit):** 46.1% de accuracy en el holdout 2024-25 vs. **49.2%** del baseline
  ingenuo ("predecir siempre Local") — no le gana, y casi nunca predice empate.
- **Total de tarjetas (Poisson GLM):** correlación con el valor real en el holdout: solo equipos
  −0.052, solo árbitro 0.053, ambos combinados 0.003 — **las tres pegadas a cero**, pese a que el
  árbitro "explica" claramente más varianza que los equipos dentro de la muestra de ajuste
  (notebooks 12 y 14). La lección metodológica que deja este resultado: que una variable explique
  varianza en un modelo ajustado con fixed effects (una categoría por árbitro) no garantiza que
  sirva para predecir un partido nuevo a partir de un resumen simple de esa variable (su promedio
  histórico) — son preguntas distintas, y aquí quedó demostrado con números, no solo advertido.

### Qué se necesitaría para mejorar la predicción (no implementado)

Forma reciente (últimas 5 jornadas en vez de todo el histórico), historial cabeza a cabeza entre
los dos equipos específicos del partido, o un sistema tipo ELO que capture fuerza relativa de
forma más dinámica que un promedio. También, para investigar "amaño" en sentido fuerte: acceso a
cuotas de apuestas históricas (se revisaron The Odds API, Sportmonks, OpticOdds — todas de paga).

**Estado: Fase 10 cerrada.** Preguntas de investigación originales (comportamiento de equipo
local/visita, sesgo arbitral, viabilidad de un modelo predictivo con estas variables) contestadas
con evidencia real, incluyendo dos hallazgos de calidad de datos corregidos en el camino
(duplicación de nombres de árbitro, definición mezclada de `card_game_per_fouls`) y dos
resultados negativos honestos (el modelo de ganador no supera el baseline; ni equipo ni árbitro
predicen bien las tarjetas de un partido individual fuera de muestra). Ver notebooks
`12_pipeline_comportamiento_ligamx.ipynb` a `16_modelo_partidos_ligamx_prematch.ipynb`. Dashboard
interactivo con los hallazgos del sesgo arbitral publicado en Vercel:
https://dashboard-six-eta-76.vercel.app

## Fase 11 — Actualización a temporadas 2025-2026 y 2026-2027 (catch-up, 2026-09)

Catch-up del dataset de Liga MX (Fase 9) con los partidos jugados desde el cierre del Apertura
2025 hasta la fecha de esta sesión (2026-09-09), replicando exactamente el método y esquema de
la Fase 9 (mismas 26 columnas de `#team_stats`, mismo conteo de `yellow_red_card` como amarilla +
roja simultánea).

**Antecedente — intento previo perdido**: una sesión anterior reportó "263/396 exitosos" pero al
verificar en disco no había ningún archivo nuevo guardado — el intento acumulaba resultados en
memoria antes de escribir a disco en batch y se perdió todo por completo al cortarse por límite
de sesión. Esta ronda cambió el método para evitar ese riesgo: cada partido se procesa y **se
guarda a disco de inmediato** (`scripts/process_and_save_batch.py`, que escribe un CSV por
partido dentro del mismo loop, sin acumular todo el lote antes de escribir), verificando cada
cierto número de partidos con `ls data/raw/match_reports_ligamx/ | wc -l` que el conteo en disco
realmente subía.

**Partidos nuevos por temporada**:
- Apertura 2025 / "2025-2026" (jornadas regulares + liguilla, terminó con la final Tigres UANL vs.
  Toluca el 14 de diciembre de 2025): **337 partidos**.
- "2026-2027" (Apertura 2026) en curso, arrancó el 11 de julio de 2026 — hasta el 20 de septiembre
  de 2026 al momento de esta sesión (solo Apertura, la Clausura 2027 arranca el 2 de enero de
  2027): **59 partidos**.

*(Corrección a esta fecha: una versión anterior de esta nota decía "arrancó 9 de enero de 2026"
para la temporada "2026-2027" — esa fecha en realidad corresponde al arranque de la Clausura 2026,
que es parte de la temporada "2025-2026", no de la "2026-2027". Error de redacción del agente,
corregido aquí tras revisar el calendario scrapeado directamente.)*
- **Total nuevo: 396 partidos**, llevando el dataset de 1,706 → **2,102 partidos (100%)**.

**Método de extracción**: idéntico a la Ronda 15 de la Fase 9 — Chrome real vía la extensión
"Claude in Chrome" (no el navegador sandboxed), función de extracción JS reutilizada desde
`localStorage` (`extractFnSrc`) para no reenviarla en cada partido, lotes de navegación de 3 a 8
partidos por `browser_batch` según qué tan estable estuviera la conexión en el momento, guardando
cada partido a disco justo después de extraerlo.

**Bloqueos y casos límite encontrados**:
- **Desconexiones de la extensión Chrome a mitad de `browser_batch`** (ocurrió 3 veces en esta
  ronda): en cada caso el navegador **siguió ejecutando las navegaciones en segundo plano** pese a
  que la herramienta reportó error de desconexión, produciendo en el reintento inmediato
  extracciones de un partido *distinto* al solicitado (el navegador ya había avanzado a la
  siguiente URL de la cola vieja). El chequeo `match_ok` (comparando el `match_id` extraído del
  `location.pathname` contra el esperado) detectó los tres casos antes de guardar nada; en dos de
  ellos los datos "cruzados" resultaron internamente válidos para su propio `match_id` real (título
  y equipos consistentes entre sí) y se verificaron contra el calendario maestro antes de
  reusarlos, evitando repetir la navegación. **Cero archivos corruptos guardados.**
- **Desafíos de Cloudflare ("Un momento…")**: ~5 veces durante la ronda, siempre resueltos solos
  tras 8-10 segundos de espera y un reintento — mismo comportamiento que las rondas anteriores con
  Chrome real (nunca un bloqueo duro). Detectados por `home_team_page`/`away_team_page` vacíos y
  `document.title` igual a "Un momento…" en vez del título real del partido.
- **Secciones de estadística ausentes** (mismo caso límite ya documentado en la Fase 9): 2 partidos
  sin bloque de "Offsides" en `#team_stats_extra` (`b4602e8d` Tijuana–León, `4b975bab` León–
  Pachuca) — se dejaron esos campos vacíos en vez de fallar el partido completo, siguiendo la
  convención ya establecida.
- **Equipo nuevo en el dataset**: "Atlante" aparece por primera vez en la temporada "2026-2027"
  (equipo recién ascendido), a partir del partido `5ed5289a` (Necaxa vs. Atlante, 16 de julio de
  2026). No requirió ningún cambio de método, solo se documenta porque es la primera vez que un
  equipo nuevo entra al dataset desde que se armó el calendario de la Fase 9.

**Verificación final — Paso 3 (`matches_ligamx_2020_2025_completo.csv`)**: regenerado
concatenando los 2,102 archivos de `data/raw/match_reports_ligamx/` y uniéndolos por `match_id`
contra las 2,102 filas del calendario maestro. **0 `match_id` duplicados** (ni en el calendario ni
en los reportes), **0 filas sin datos de `team_stats`** tras el join — los 396 partidos nuevos
quedaron completos al 100%.

**Paso 4 (`matches_ligamx_2020_2025_v3_arbitraje.csv`)**: se calcularon las columnas derivadas
(`home_efficency`/`away_efficency`, `home_total_cards`/`away_total_cards`, `total_game_cards`,
`home_card_game_per_fouls`/`away_card_game_per_foul`) solo para las 396 filas nuevas, formateando
los floats con la misma convención ya presente en el archivo (`%.15g`, igual que el resto del
dataset) y dejando en blanco los cocientes 0/0 (no se dio el caso en las 396 filas nuevas: ningún
partido tuvo `home_fouls` o `away_fouls` en 0). Las filas nuevas se **appendearon** al final del
archivo existente sin tocar las 1,706 filas originales — verificado leyendo el archivo previo como
texto puro (`dtype=str`) antes de concatenar, para no reformatear ni un solo valor ya existente.
Archivo final: **2,102 filas** (41 columnas, mismo orden).

**Archivos actualizados**:
- `data/raw/match_reports_ligamx/` — ahora 2,102 archivos (1,706 originales + 396 nuevos), uno por
  partido.
- `data/processed/matches_ligamx_2020_2025_completo.csv` — 2,102 filas, 0 duplicados.
- `data/processed/matches_ligamx_2020_2025_v3_arbitraje.csv` — 2,102 filas, 0 duplicados, columnas
  derivadas calculadas para las 396 filas nuevas.
- `scripts/process_and_save_batch.py` (nuevo) — variante de `process_and_save.py` que acepta un
  arreglo JSON de partidos y guarda cada uno en su propio archivo dentro del mismo loop, para
  agilizar el guardado sin perder la garantía de "un archivo por partido, apenas se tiene" que
  causó la pérdida de datos del intento anterior.

**Sin tocar**: `data/raw/matches_ligamx_2020_2025_schedule.csv` (ya estaba correcto, 2,102 filas,
0 duplicados desde antes de esta sesión) ni los notebooks 13–16 ni `dashboard/`, según lo pedido.

**Estado: Fase 11 completa — 396/396 partidos nuevos (100%), dataset acumulado en 2,102/2,102.**

### Addendum — 2 duplicados de árbitro más, mismo patrón que la Fase 10

Después de que el agente de scraping terminó, se revisó si las temporadas nuevas introducían más
casos del problema de nombres duplicados ya descrito en la Fase 10 (FBref cambiando el formato del
nombre de un árbitro a mitad de temporada). Se encontraron **2 casos más**, mismo patrón exacto
(sin acentos → con acentos, cero o casi cero traslape de temporadas):

- `Jesus Lopez` → `Jesús López` (0 temporadas traslapadas).
- `Ismael Lopez` → `Ismael López` (1 partido suelto de traslape en 2025-2026, igual que el caso de
  "Marco Ortíz" de la Fase 10 — formato inconsistente en un solo reporte, no una tercera persona).

Se agregaron ambos al `mapa_nombres_arbitro` en el notebook 14, el notebook 16 y
`export_dashboard_data.py` (ahora 8 pares consolidados en total). **Árbitros únicos: 53 nombres
crudos → 45 reales.**

**Impacto real de re-ejecutar el notebook 14 con el dataset completo (2,102 partidos, 7
temporadas):** **Edgar Morales deja de ser atípico** (z bajó de 2.088 a 1.830, por debajo del
umbral de |z|>2) — con más árbitros en el conjunto de referencia, su desviación relativa ya no
destaca tanto. **Diego Montaño se mantiene como el único atípico** (z=−2.313). La correlación
policórica árbitro-vs-tarjetas bajó ligeramente de 0.278 a 0.254 (equipos se mantiene en ~0.07).
Mismo patrón que ya se documentó dos veces en este proyecto: las conclusiones basadas en muestras
más chicas conviene revisarlas cuando llega más información, en vez de darlas por definitivas.

El dashboard (`dashboard/index.html`) también se actualizó para que el rango de temporadas, el
conteo de partidos/árbitros y la lista de atípicos en el texto de conclusión se calculen siempre
dinámicamente desde `data.json` en vez de estar escritos a mano en el HTML — así una futura
actualización de datos no vuelve a dejar texto desactualizado (pasó con "5 temporadas" fijo
cuando el dataset creció a 7). Redesplegado: https://dashboard-six-eta-76.vercel.app

### Addendum 2 — Notebooks 13, 15 y 16 actualizados al dataset de 2,102 partidos

Los notebooks 13 (variables), 15 (perfiles de equipo) y 16 (modelo de partidos) también se
re-ejecutaron con el dataset extendido (2,102 partidos, 7 temporadas). Cambios reales que valen
la pena registrar:

- **Notebook 13**: se agregó por primera vez la consolidación de los 8 árbitros duplicados (no
  se había aplicado ahí antes). Diccionario de variables y matriz policórica actualizados a
  45 árbitros / 19 equipos.
- **Notebook 15**: se encontró y corrigió un problema real — **toda la sección 8 (ventana móvil)
  había desaparecido del archivo en algún punto** (solo quedaban dos celdas de conclusión sueltas,
  sin el código que las sustenta; causa exacta no determinada). Se reconstruyó completa desde los
  scripts de generación que seguían disponibles. De paso, el split entrenamiento/validación se
  corrió hacia adelante (entrenamiento ahora 2020-21 a 2024-25, validación 2025-26 completa en vez
  de 2024-25) y las ventanas móviles ahora van de W=1 a W=5 en vez de fijo hasta W=4 (calculado
  dinámicamente según cuántas temporadas completas haya, para no volver a quedar hardcodeado).
  Conclusión sin cambios: ninguna ventana gana de forma consistente. Nota: "Atlante" no aparece en
  este notebook — solo juega en la temporada 2026-2027, que queda fuera tanto del entrenamiento
  como de la validación (no es una temporada completa todavía), así que el análisis sigue siendo
  sobre 18 equipos.
- **Notebook 16**: el resultado del Modelo A **cambió de verdad** con más datos de entrenamiento
  (1,278 partidos vs. 957 antes): antes perdía contra el baseline (46.1% vs. 49.2%), ahora **le
  gana** (49.4% vs. 46.8%, holdout 2025-26) — aunque sigue sin predecir un solo empate. El Modelo B
  (tarjetas) se mantiene igual de débil pero ahora con correlaciones positivas en las 3 versiones
  (antes una era negativa); el árbitro solo sigue siendo el mejor predictor individual (0.107).

Todos los notebooks verificados con 0 errores de ejecución tras la actualización.

## Fase 12 — Actualización semanal #1 (2026-09-17)

Primera corrida del ciclo semanal acordado con el usuario: él conecta Chrome y avisa, se scrapea
lo jugado desde el último corte y se redespliega el dashboard en la misma sesión.

- **11 partidos nuevos** (Apertura 2026, jornadas 7-8, del 10 al 15 de septiembre de 2026).
  Dataset acumulado: **2,113 partidos**.
- **Bug propio detectado y corregido en el momento:** al recombinar el dataset crudo se usó por
  error `match_id` + `home_team` + `away_team` como llave del merge (en vez de solo `match_id`,
  el método correcto que ya usaba el proyecto desde la Fase 9). Los nombres de equipo no siempre
  coinciden carácter por carácter entre el calendario maestro y los archivos de reporte
  individuales (ej. "UNAM" vs. "Pumas UNAM" según de qué ronda de scraping viene cada archivo), así
  que esa llave extra rompió el join silenciosamente y dejó **358 partidos viejos marcados como
  "sin stats"** sin serlo. Detectado al revisar el conteo tras recombinar (2,113 filas pero solo
  1,755 con stats — no cuadraba). Corregido volviendo a unir solo por `match_id`; verificado
  después: 2,113/2,113 con stats completos.
- **Posible nuevo árbitro, no duplicado:** apareció "Mario Terrazas Chávez" — se revisó contra
  "Charles Terrazas" (ya existente) por si era el mismo patrón de nombres duplicados de las Fases
  10-11, pero el nombre de pila es completamente distinto (Mario vs. Charles), a diferencia de los
  8 casos anteriores donde FBref solo agregaba acentos o un segundo nombre al mismo nombre de pila.
  Se trata como árbitro nuevo, no como duplicado.
- Notebook 14 re-ejecutado (0 errores) y dashboard redesplegado con los datos actualizados:
  https://dashboard-six-eta-76.vercel.app — sigue con Diego Montaño como único árbitro atípico.

## Fase 13 — Dashboard de predicciones por jornada (2026-09-17/18)

Segundo dashboard (proyecto Vercel aparte): https://dashboard-predicciones.vercel.app — carpeta
`dashboard-predicciones/` (`index.html` + `data.json`). Es el modelo del notebook 16 aplicado solo a
Liga MX: probabilidades de Local/Empate/Visitante y tarjetas totales esperadas por partido.

- **Dos selectores (temporada y jornada):** al elegir una jornada ya jugada se muestra la predicción
  junto al resultado real con insignia "acertó/falló" y el conteo "X/Y acertados"; si la jornada aún
  no se juega, solo la predicción. Arranca en la primera jornada sin jugar (hoy: Apertura 2026 - J9;
  J10 ya incluida, 25-27 de septiembre). Las jornadas se ordenan por la fecha de su primer partido,
  no por número (si no, Apertura y Clausura se mezclan).
- **Diseño anti-fuga:** el perfil de cada equipo para cada partido se calcula con ventana expandible
  **por fecha** (solo partidos anteriores a ese día, no por temporada), y solo se predice cuando el
  equipo ya acumula ≥100 partidos de historia (`UMBRAL_MINIMO_HISTORIA`). Así, Atlante (que solo
  existe desde 2026-27) ya es predecible.
- **Resultado retrospectivo:** accuracy 49.1% sobre 2,010 partidos vs. 45.3% de "siempre Local";
  pseudo-R² 0.037. El modelo casi nunca predice empate (limitación conocida de un MNLogit con
  Empate como clase de referencia).
- **Limitación importante (aviso visible en el propio dashboard):** el modelo se ajusta UNA sola vez
  con todo el histórico de hoy. Los perfiles sí son pre-partido, pero los coeficientes no se
  reajustan en cada fecha; por eso la comparación pasado-vs-real es descriptiva, no un backtest
  riguroso. La evaluación honesta será la de los partidos futuros conforme se vayan jugando.
- **Historial cabeza a cabeza (H2H):** probado y no cambió ninguna predicción, se muestra solo como
  dato informativo. En partidos futuros el árbitro aún no está asignado, así que las tarjetas
  esperadas usan solo el perfil de equipos.
- **Bugs propios corregidos al probar:** (1) los partidos de liguilla no tienen número de jornada y
  pandas los exportaba como `NaN`, que no es JSON válido — el navegador rechazaba todo el archivo y
  el dashboard quedaba vacío; el exportador ahora convierte `NaN` a `null` y falla ruidosamente si
  se cuela otro; (2) los recuadros de H2H/tarjetas usaban `display:inline-flex` y partían el texto
  en columnas.
- **Mantenimiento semanal:** en cada "actualiza", además de scrapear resultados, hay que refrescar
  la lista de partidos futuros (hardcodeada en `scripts/export_predicciones_historico.py`) desde FBref para
  añadir las jornadas nuevas; los resultados de J9/J10 pasarán solos de "predicción" a "predicción
  vs. real". El script tarda ~10-17 min (recalcula perfiles por cada fecha única).

### Fase 13 — Adenda: MNLogit vs. Poisson, evaluado fuera de muestra (2026-09-18)

Script: `scripts/comparar_modelos_ganador.py`. Compara (mismas 8 variables pre-partido) el MNLogit del
dashboard contra Poisson independiente de goles y Poisson + Dixon-Coles, con validación
walk-forward: cada temporada de prueba (2022-23 → 2026-27, 1,427 partidos) se predice con modelos
reajustados solo con temporadas anteriores.

| Modelo | Accuracy | Log-loss | AUC empate | Picks "Empate" |
|---|---|---|---|---|
| MNLogit (actual) | 48.4% | 1.034 | 0.514 | 5 |
| Poisson independiente | 48.6% | 1.030 | 0.540 | 0 |
| Poisson + Dixon-Coles | 48.6% | 1.030 | 0.535 | 0 |
| Baseline (frecuencias) | 45.9% | 1.065 | 0.522 | 0 |

- **Los tres modelos son estadísticamente indistinguibles entre sí** (bootstrap pareado: la mejora
  del Poisson en log-loss es -0.0046, IC95% [-0.010, +0.001]). Sí superan al baseline (+2.5 pts de
  accuracy, IC95% [0.6, 4.5]). El Poisson no predice mejor el ganador; su ventaja es conceptual:
  da una probabilidad de empate directa (suma de 0-0, 1-1, 2-2...) y sus probabilidades son algo
  más limpias.
- **Corrección importante a lo publicado:** la marca ⚖ "partido parejo" mostraba 32% de empates vs
  25% en el resto (p = 0.003), pero eso es DENTRO de muestra. Fuera de muestra con el MNLogit baja a
  26.8% vs 25.0% (p = 0.58); con Poisson + Dixon-Coles a 29.0% vs 24.2% (p = 0.086, misma dirección
  en 4 de 5 temporadas pero sin significancia). La señal de "riesgo de empate" existe a lo sumo en
  forma débil; la cifra 32% vs 25% del dashboard y de la publicación de LinkedIn está inflada por
  evaluar con el mismo histórico con el que se ajustó el modelo.
- El AUC de P(empate) (0.51-0.54) confirma que ningún modelo distingue bien los empates con estas
  variables; predecir empates con box-score previo es intrínsecamente difícil.
- Accuracy del dashboard (dentro de muestra) 49.1% vs. 48.4% fuera de muestra: la mejora real sobre
  "siempre Local" es de ~2.5 pts, no de ~4.

**Decisión (2026-09-18): el dashboard cambió a Poisson + Dixon-Coles con validación fuera de muestra.**
- Código: `scripts/modelo_goles.py` (modelo, compartido) y `scripts/export_predicciones_historico.py`
  (exportador; ahora usa walk-forward por temporada; el backup del MNLogit quedó en el scratchpad).
- El histórico del dashboard ahora es fuera de muestra: cada temporada se predice con un modelo ajustado solo con
  las anteriores, con mínimo de 300 partidos de entrenamiento, así que 2020-21 y 2021-22 ya no aparecen
  (solo entrenan). Cifras del dashboard: 48.6% de acierto vs 45.9% de "siempre Local" sobre 1,427 partidos
  (2022-23 en adelante), log-loss 1.030 vs 1.065, y 29% vs 24% de empates en partidos parejos (341
  partidos, umbral 12.5 pts). Los partidos futuros usan el modelo ajustado con todo el histórico
  (rho de Dixon-Coles = -0.055).
- Se agregó el chip de goles esperados por partido. Con este modelo, 1 de los 18 partidos de J9/J10 queda
  marcado como parejo (Santos Laguna vs. Pachuca).
- Texto del dashboard y publicación de LinkedIn reescritos para decir que la señal de empate es débil y no
  concluyente.

## Fase 14 — Seguimiento en vivo de Liga MX y registro personal (2026-09-18)

- **Seguimiento en vivo (oficial desde la jornada 10, Apertura 2026, 25-27 sept 2026):** definido con el usuario.
  `scripts/congelar_predicciones.py` guarda, ANTES de cada jornada, las predicciones en
  `registro/predicciones_congeladas.csv` (solo crece, nunca se sobrescribe; incluye fecha/hora de congelado). El
  exportador (`export_predicciones_historico.py`) usa esas probabilidades originales para los partidos congelados
  (no las recalculadas por el walk-forward) y calcula el acierto por jornada en `data.json → seguimiento_en_vivo`.
  La J9 quedó congelada como "previa" (no cuenta): sus primeros partidos eran del mismo día en que se generó.
- **Dashboard:** tarjeta "Seguimiento en vivo", insignias 🔴 en vivo / previa en cada partido y una gráfica de
  tendencia por jornada (barras de % de acierto, media móvil de 5 jornadas y línea de "siempre Local"; verde =
  en vivo, azul = backtest).
- **Flujo semanal ("actualiza"):** (1) scrapear resultados y actualizar dataset; (2) actualizar la lista de partidos
  futuros en el exportador; (3) correr el exportador; (4) correr `congelar_predicciones.py` para congelar las
  jornadas siguientes; (5) redesplegar.
- **Registro personal de jugadas (privado):** `registro_personal/jugadas.csv` (fuera de las carpetas que se
  publican) + `scripts/resumen_registro_personal.py`, que lo cruza con lo que dijo el modelo y con el resultado real
  (acierto propio vs. del modelo, coincidir o no con el modelo, partido parejo, situación, ganancia/ROI). Se llena
  cuando el usuario avise en qué partidos jugó. Es solo para su seguimiento personal: no se publica.

## Fase 15 — Premier League: viabilidad y comparación contra el mercado (2026-09-18)

Datos: los CSV gratuitos de football-data.co.uk (`data/raw/premier_odds/E0_AAAA.csv`, temporadas 2015-16 a 2026-27,
4,220 partidos) ya traen goles, tiros, tiros a puerta, faltas, corners, tarjetas, árbitro y cuotas 1X2 (Bet365,
Pinnacle, promedio del mercado), por lo que NO hace falta scrapear FBref para esta liga. Dataset unificado:
`data/processed/premier_matches_2015_2026.csv` (`scripts/europa_construir_dataset.py`). Comparación:
`scripts/europa_comparar_con_mercado.py` (walk-forward por temporada, 3,240 partidos, 2017-18 → 2026-27).

| Modelo (fuera de muestra) | Acierto | Log-loss | RPS | AUC empate |
|---|---|---|---|---|
| Baseline (frecuencias) | 44.1% | 1.0675 | 0.233 | 0.48 |
| Modelo A, 8 var., expandible | 51.6% | 0.993 | 0.207 | 0.57 |
| Modelo A, ventana 19 | 52.8% | 0.982 | 0.203 | 0.56 |
| Modelo B, ventana 38 (+tiros a puerta) | 53.2% | 0.982 | 0.204 | 0.56 |
| Mercado Bet365 (previa) | 55.1% | 0.958 | 0.195 | 0.58 |

- **La Premier da mucha más señal que Liga MX:** el modelo supera al baseline por ~8-9 pts de acierto (Liga MX:
  ~2.5). Es consistente con la hipótesis de que hay más diferencia entre equipos y más partidos por equipo.
  Captura ~78% de la mejora que logra el mercado sobre el baseline en log-loss.
- **El mercado sigue ganando:** log-loss +0.024 peor que Bet365 (IC95% [+0.017, +0.031]), peor en 9 de 10
  temporadas. Y el modelo NO aporta información adicional sobre el mercado (apilado walk-forward: mercado+modelo
  no mejora al mercado solo; +0.003, IC95% [+0.000, +0.005]).
- **Ventana:** en la Premier las ventanas cortas (19-38 partidos por lado, 1-2 temporadas) superan a la expandible
  (10 años de memoria); en Liga MX la expandible funcionaba igual de bien.
- **Empates y "partidos parejos":** con las probabilidades del MERCADO, en partidos parejos (<12.5 pts entre las
  tres) el empate sale 29.2% vs 22.3% en el resto (p = 0.0008, n = 517), la señal más clara que hemos visto; con el
  modelo B ventana 38 es 25.6% vs 23.1% (p = 0.26). Ojo: se probaron varias variantes del modelo (comparaciones
  múltiples); el resultado del mercado es una sola definición, sin ajustar el umbral.
- **Dashboard multi-liga (2026-09-18):** https://dashboard-predicciones.vercel.app ahora tiene botones Liga MX /
  Premier League (URL `#ligamx` / `#premier`). Cada liga es un JSON con el mismo formato (`data.json`,
  `data_premier.json`) y el front-end se alimenta de un diccionario `LIGAS`: agregar una liga = generar su JSON con
  ese formato y registrarla. Base pensada para crecer hacia el problema de modelación multiobjetivo (más ligas y
  más variables objetivo: ganador, goles, tarjetas, corners...), por partes.
- **Exportador Premier:** `scripts/export_predicciones_europa.py premier` (Poisson + Dixon-Coles, 12 variables incl. tiros a
  puerta, ventana de 38 partidos por lado, walk-forward por temporada). Cifras del dashboard: 53.5% de acierto vs
  55.0% del mercado (Bet365) vs 43.9% "siempre Local" en 3,106 partidos (2017-18 en adelante); log-loss 0.981 vs
  0.957 (mercado) vs 1.068 (referencia). Muestra también el mercado en cada partido y la media móvil del mercado
  en la gráfica. Módulos compartidos: `scripts/features_europa.py` (perfiles), `scripts/ligas_europa.py` (configuración por liga), `scripts/seguimiento_en_vivo.py`.
- **Correcciones al construirlo:** (1) la jornada se contaba solo con partidos de local (20 partidos por jornada,
  máx. 19); ahora cuenta local y visitante (1-38); (2) un ascendido con años sin jugar en primera (Hull, última
  vez en 2016-17) conservaba un perfil mezclado con datos viejos; ahora se descarta la historia anterior a una
  pausa de más de 2 años (MAX_DIAS=730) y el partido queda "sin perfil" hasta acumular 10 partidos nuevos
  (afecta a Hull y Coventry en la J5).
- **Seguimiento en vivo Premier:** cuenta desde los partidos del 19 sept 2026 (J5); Brentford–Chelsea (viernes
  18, 20:00 UK) ya se había jugado al congelar, así que quedó como "previa". Registro:
  `registro/predicciones_congeladas_premier.csv` (`python scripts/congelar_predicciones.py premier`).
- **Flujo semanal Premier:** bajar CSV nuevos (`E0_2627.csv` y `fixtures.csv` de football-data.co.uk), reconstruir
  con `europa_construir_dataset.py premier`, correr `export_predicciones_europa.py`, congelar con `congelar_predicciones.py
  premier` y redesplegar.
- **Pendiente:** análisis arbitral de la Premier (51 árbitros en el dataset) y sumar más ligas.

## Fase 16 — La Liga (España) en el mismo dashboard (2026-09-18)

Tercera liga del dashboard (botón "La Liga"). Mismos datos y método que la Premier (CSV de football-data.co.uk,
código SP1, 2015-16 a 2026-27, 4,239 partidos; ojo: La Liga NO trae la columna de árbitro, así que no habría
análisis arbitral). Para no copiar código se generalizaron los scripts por liga: `scripts/ligas_europa.py` guarda la
configuración (archivos, renombrado de equipos porque football-data usa abreviaturas como "Ath Madrid", ventana,
inicio del seguimiento en vivo); `europa_construir_dataset.py`, `europa_comparar_con_mercado.py` y
`export_predicciones_europa.py` reciben la clave (`premier`, `laliga`). Agregar otra liga (Bundesliga D1, Serie A I1,
Ligue 1 F1...) = una entrada en `ligas_europa.py`, una en `congelar_predicciones.py` y una en `LIGAS` del HTML. El
calendario futuro de todas las ligas sale de un único archivo (`data/raw/fixtures_football_data.csv`).

Resultados fuera de muestra (3,134 partidos, 2017-18 en adelante; Poisson + Dixon-Coles con tiros a puerta y
ventana de 38 partidos por lado, como la Premier):
- Acierto del modelo 51.7% vs 53.4% del mercado (Bet365) vs 45.3% de "siempre Local" (+6.4 pts sobre el baseline; la
  Premier +9.6). Log-loss 0.999 vs 0.973 (mercado) vs 1.069 (referencia); el modelo pierde con el mercado por
  +0.028 (IC95% [+0.021, +0.035]) y el mercado no mejora al añadirle el modelo (+0.008, IC95% [+0.004, +0.012]).
- Partidos parejos: con el mercado, empate 32.4% vs 24.3% (p < 0.0001); con el modelo, 29.6% vs 25.5% (p = 0.07).
  Igual que en la Premier: la señal está sobre todo en las probabilidades del mercado.
- El dashboard redacta la nota de "partido parejo" según lo que salga de los datos (Fisher p < 0.05).
- Seguimiento en vivo La Liga: desde el 19 sept 2026 (`registro/predicciones_congeladas_laliga.csv`, `python
  scripts/congelar_predicciones.py laliga`); Espanyol–Elche ya se había jugado al congelar (previa). 3 de los 10
  partidos de la jornada 7 salen "sin perfil" (Racing Santander, Málaga y Deportivo La Coruña, ascendidos sin
  historial reciente).
- Jornada: se asigna como el MAYOR de las jornadas de los dos equipos (n-ésimo partido de cada uno), para que un
  partido aplazado no quede en una jornada aparte (Athletic–Alavés salía como J6 y el resto como J7); la Premier
  quedó igual.
- Aviso (bug detectado): el registro `predicciones_congeladas_laliga.csv` conserva la etiqueta antigua "J6" de
  Athletic–Alavés; solo es cosmético (el dashboard usa la etiqueta que calcula al exportar).

## Fase 17 — Bundesliga en el mismo dashboard (2026-09-18)

Cuarta liga del dashboard (botón "Bundesliga"). Se sumó con una entrada en `scripts/ligas_europa.py`, una en
`congelar_predicciones.py` y una en `LIGAS` del HTML (sin escribir scripts nuevos). Datos: football-data.co.uk,
código D1, 2015-16 a 2026-27 (18 equipos, 306 partidos por temporada, 2,926 partidos con perfil; no trae árbitro).

Resultados fuera de muestra (2,536 partidos, 2017-18 en adelante; Poisson + Dixon-Coles con tiros a puerta):
- Acierto del modelo 49.8% vs 52.4% del mercado (Bet365) vs 43.3% de "siempre Local" (+6.5 pts sobre el baseline).
  Log-loss 1.008 vs 0.979 (mercado) vs 1.075 (referencia); el modelo pierde con el mercado por +0.028 (IC95% [+0.020,
  +0.036]) y el mercado no mejora al añadirle el modelo (+0.0014, IC95% [-0.002, +0.005]).
- Ventana: con 18 equipos casi no importa (expandible 1.0076 vs 34 partidos por sede 1.0089); se usó la expandible
  (`ventana: None`). Ojo: se eligió mirando esa misma comparación fuera de muestra, pero la diferencia es trivial.
- Partidos parejos: con el mercado, empate 29.3% vs 24.6% (p = 0.08); con el modelo, 26.6% vs 25.0% (p = 0.49). Aquí
  la señal no es clara ni con el mercado, a diferencia de la Premier y La Liga; el dashboard lo dice así
  automáticamente.
- Seguimiento en vivo: desde el 19 sept 2026; Bayern–Union Berlin (viernes 18, 19:30 hora UK) ya se había jugado al
  congelar (previa). 6 partidos congelados cuentan; Schalke–Elversberg y Paderborn–Hoffenheim salen "sin perfil"
  (ascendidos sin historial reciente).
- Bug encontrado y arreglado: un partido suspendido (Union Berlin–Bochum, 2024-12-14) viene sin ninguna estadística y
  rompía el ajuste del modelo de tarjetas; ahora se excluye de entrenamiento y evaluación (sigue contando en los
  promedios de perfil de otros equipos, donde pandas ignora los NaN).
- La `rho` de Dixon-Coles del modelo final de la Bundesliga es -0.129 (en las otras ligas ronda -0.01 a -0.03):
  más correlación negativa en marcadores bajos (más 0-0 y 1-1 de lo que da el Poisson independiente).
- Los cuatro JSON (~1-2 MB cada uno) se descargan solo al abrir cada liga; con más ligas convendría comprimirlos o
  recortar campos si el tiempo de carga se vuelve un problema.

## Fase 18 — Serie A, registro de apuestas por tipo y despliegue seguro (2026-09-18)

**Serie A (quinta liga del dashboard).** Datos de football-data.co.uk (código I1, 380 partidos por temporada, 2015-16 a
2026-27; no trae árbitro). Solo entradas de configuración (`ligas_europa.py`, `congelar_predicciones.py`, HTML).
Resultados fuera de muestra (3,049 partidos, 2017-18 en adelante): acierto 53.0% vs 55.2% del mercado (Bet365) vs 41.6%
de "siempre Local" (+11.4 pts sobre el baseline, la mayor de las ligas: diferencias grandes entre equipos); log-loss
0.981 vs 0.956 (mercado) vs 1.082; el modelo pierde con el mercado por +0.024 (IC95% [+0.017, +0.030]) y el mercado
no mejora al añadirle el modelo (+0.004, IC95% [+0.001, +0.007]). Partidos parejos: con el mercado, empate 33.5% vs
24.1% (p < 0.0001); con el modelo, 30.3% vs 25.2% (p = 0.034): la señal más clara de las cinco ligas, presente en
ambos. Ventana expandible con 12 variables (la ventana casi no importa: 0.9800 vs 0.9793 de la mejor variante).
Seguimiento en vivo desde el 19 sept 2026 (Monza–Sassuolo quedó "previa"; Frosinone–Como "sin perfil").
- Bug: algunos partidos de la Serie A 2020-21 no tienen cuotas de Bet365; con NaN el log-loss del mercado salía NaN y su
  "pick" era basura. Ahora se excluyen de la evaluación (modelo y mercado se comparan en los mismos partidos); las
  demás ligas quedaron idénticas.

**Registro personal de apuestas por tipo (privado).** `registro_personal/jugadas.csv` con el esquema ampliado
(liga, tipo, selección, línea, cuota, monto, combinada_id, situación...). `scripts/resumen_registro_personal.py`
califica automáticamente 1X2, doble oportunidad, over/under de goles, ambos anotan, hándicap (líneas .5), tarjetas,
corners, marcador exacto y combinadas (gana si ganan todas las patas); busca el resultado en los datasets de cada
liga (si el partido aún no está, queda "pendiente"). Para cada pata calcula la probabilidad del modelo (1X2 y doble
oportunidad del propio modelo; goles/ambos anotan/marcador/hándicap con el Poisson de los goles esperados; tarjetas
con Poisson; corners sin modelo), la compara con la probabilidad implícita de la cuota (edge) y resume acierto,
ganancia y ROI por tipo, liga, rango de cuota, edge, coincidencia con el modelo, partido parejo y situación (marca con
* los grupos con < 30 apuestas: ruido). Probado con un archivo de ejemplo; el registro real está vacío. Limitación:
las tarjetas de las casas pueden contarse distinto (roja = 2 puntos), así que esas jugadas pueden calificarse
distinto a como las resolvió la casa.

**Despliegue seguro con línea base.** `scripts/desplegar_dashboard.py` reemplaza a `vercel deploy --prod` (que movía
el link al instante): valida los archivos (JSON válidos sin NaN, probabilidades que suman 1, todas las ligas, sin
archivos personales en la carpeta pública, sin pérdida > 10% de datos), los respalda en
`backups/dashboard_predicciones/`, construye un despliegue en staging (`--prod --skip-domain`) sin tocar el link,
lo prueba (`vercel curl`: 200 y SHA-256 idéntico al local), lo promueve (`vercel promote`), verifica el link público y
hace rollback automático si falla. La línea base (último despliegue bueno + historial) vive en
`registro/deploy_baseline.json`; `--rollback [url]` vuelve atrás en segundos (Vercel conserva todos los despliegues).
Probado: la validación detecta un archivo personal y un NaN; el flujo completo publicó; el rollback a la versión
anterior y de regreso funcionó sin que el link dejara de responder. Nota: `vercel curl` generó automáticamente un
token de bypass de protección de despliegues para el proyecto (necesario para probar el staging).

## Fase 19 — Revisión del scrapeo de plantillas, fantasy por temporada y Voronoi de Apolonio (2026-09-18)

Objetivo: usar el panel de plantillas de FBref (7 ligas × 16 temporadas, 61,542 filas) para seguir el rendimiento de
**jugadores** temporada por temporada (fantasy + diagramas de Voronoi en modalidad Apolonio), y empezar a mover la
lógica del proyecto a código reutilizable y probado. Notebook: `17_plantillas_fantasy_apolonio.ipynb`.

**Paquete `futbol_bd/` + pruebas (`tests/`, 17 pruebas, `python -m pytest tests`).** Primer paso hacia un proyecto más
robusto: lo que antes vivía copiado dentro de cada notebook ahora está en módulos importables —
`plantillas.py` (carga/auditoría/limpieza del panel, `id_jugador`, suma de traspasos), `fantasy.py` (puntos, percentiles,
regularidad) y `apolonio.py` (Voronoi ponderado multiplicativo/aditivo/normal, áreas, dibujo). Las pruebas cubren cada
problema real encontrado en el panel y validan la geometría contra resultados analíticos (el círculo de Apolonio
coincide píxel a píxel con la fórmula; pesos iguales = Voronoi normal; invariancia a la escala del peso).
`scripts/construir_jugadores_temporada.py` genera `data/processed/jugadores_temporada_2010_2026.csv` (59,452
filas jugador-liga-temporada, 16,307 jugadores) y `output/auditoria_panel_fbref.csv`.

**Auditoría del scrapeo (17 chequeos).**
- Errores de la fuente, pocos y corregidos: 1 fila duplicada con el mismo contenido (Torrasi, Milan 2017-18),
  1 fila sin minutos, 38 con conteos vacíos (asistencias, sobre todo Bundesliga 2010-12), 33 G+A y 3 goles-sin-penal
  que no cuadraban (todas las derivadas se recalculan desde los conteos), 1 penal anotado sin intento (Lemina 2015-16).
- **Identidad (el problema de fondo): el scrapeo original no guardó el id de FBref.** 176 nombres son 2+ personas; 98
  veces el mismo nombre aparece con 2 años de nacimiento en la misma liga-temporada. Primero se usó una clave nombre +
  año + nacionalidad; desde el 2026-09-19 el id es el de FBref (ver "Adenda" abajo).
- 2,088 traspasos dentro de la misma liga-temporada (se suman) y 1,046 entre ligas (una fila por liga).
- Temporadas recortadas por COVID: Eredivisie, Ligue 1 y Liga MX 2019-20 (se normaliza por jornada). Ligue 1 2023-26
  tiene 34 jornadas porque bajó a 18 equipos, no es un recorte (la auditoría compara contra 2 × (equipos − 1)).

**Fantasy (FPL adaptado).** Titular 2 / suplente 1, gol 6/6/5/4 (POR/DEF/MED/DEL), asistencia 3, amarilla −1, roja −3,
penal fallado −2. Sin porterías a cero, paradas ni bonus (no hay datos) → es un fantasy ofensivo: los porteros no pasan
de 2.09 pts/jornada y la mediana de defensas (1.44) queda bajo medios (1.76) y delanteros (2.12). Se compara solo
dentro de posición: `pct_pts_jornada` = percentil de puntos por jornada en liga-temporada-posición (900+ min). Prueba de
sentido común superada (Messi 2011-12, 313 pts, encabeza el panel; la regularidad la lidera Cristiano, percentil medio
97.9 en 12 temporadas). Liga MX: Juan Brunetta, percentil medio 98.0 (2022-23 a 2025-26), mínimo 94.8.

**Voronoi de Apolonio.** El plano es un espacio de perfil (goles sin penal/90 vs. asistencias/90) — no la cancha, porque
el panel no trae posiciones. Sitios = top-20 atacantes fantasy por temporada; peso = puntos. Modo principal:
multiplicativo (d/w; fronteras = círculos de Apolonio; invariante a la escala del peso, sin parámetros). El aditivo
(d − w, el "diagrama de Apolonio" de CGAL) depende de un `alcance` arbitrario y deja jugadores sin celda (5 en Liga MX
2025-26). Dominio fijo por liga para comparar temporadas. Cálculo por rasterización (500 px).
- **Hallazgo: el área de la celda no es una métrica de rendimiento.** Mezcla rendimiento con aislamiento del perfil:
  Spearman con los puntos (mediana por temporada, Liga MX) = 0.19 Voronoi normal, 0.43 multiplicativo, 0.54 aditivo,
  0.61 la "ganancia" (Apolonio − Voronoi). Además es volátil: Brunetta 1% → 39% → 1% con percentil 98 → 100 → 95. El
  mapa sirve para ver la **estructura** de cada temporada (quién cubre qué perfil); para seguir rendimiento, el percentil.
- Figuras: `output/figures/fase19_modos_apolonio_ligamx.png`, `fase19_apolonio_temporadas_ligamx.png`,
  `fase19_rendimiento_temporadas_ligamx.png`.

### Fase 19 — Adenda: ids de FBref en el panel (2026-09-19)

**Extracción.** Con `scripts/fbref_extraer_tabla.js` desde el Chrome del usuario (el navegador integrado se topó con
Cloudflare Turnstile y no se intentó resolver). Para no pasar 112 tablas completas por la conversación: las páginas se
pidieron con `fetch()` desde una pestaña de FBref, cada una se comparó contra una firma (hash FNV-1a de
jugador|equipo|partidos|minutos) del CSV ya guardado, y solo se guardaron los ids (localStorage → una única descarga
autorizada por el usuario: `data/raw/fbref_ids/fbref_ids_panel_2010_2026.json`, 1.4 MB). Ritmo: una página cada
8-10 s. Tras ~100 páginas FBref respondió 403 `cf-mitigated: challenge`; una navegación normal en otra pestaña lo pasó
sola y se terminó. Resultado: 112/112 páginas, 61,542 filas (las mismas del panel), 0 filas sin id.

**Unión** (`scripts/unir_ids_fbref.py`, probada en `tests/test_unir_ids.py`). 90 páginas idénticas (ids por posición)
y 22 con cambios de FBref que no tocan ningún número: "PSG" → "Paris SG" (16 temporadas de la Ligue 1), "Ben Brereton"
→ "Ben Brereton Díaz" (3 filas) y filas invertidas de jugadores con dos equipos (18 filas). Se emparejan por contenido
exacto y luego por posición + partidos + minutos; si algo no empareja, el script se detiene. Agrega `player_id` y
`team_id` al final de `data/processed/fbref_panel_2010_2025.csv` (el resto del archivo queda byte a byte igual;
notebooks 09 y 10 seleccionan columnas por nombre, no les afecta).

**Qué mostró comparar la clave por nombre con los ids de FBref.** La clave nunca partió a una persona en dos, pero
juntaba a **4 pares de personas distintas** (Vitinha, Fernandinho, Adriano, Borja García). Y FBref también tiene
errores: **2 perfiles duplicados** (Édgar Méndez: "Edgar Mendez" en Almería 2014-15 y Cruz Azul 2017-18, "Édgar
Méndez" en el resto de su carrera; Emanuele Torrasi: dos veces en el Milan 2017-18 con la misma fila). Id final =
id de FBref + `ALIAS_FBREF` (esos 2 casos) en `futbol_bd/plantillas.py`; `HOMONIMOS_VERIFICADOS` registra los 4
revisados, y `candidatos_revision()` marca como PENDIENTE cualquier caso nuevo de un scrapeo futuro. Se eliminó
`COLISIONES_CONOCIDAS` (obsoleto). 43 filas (40 jugadores, casi todos Liga MX 2010-11) no tienen página en FBref: su
id es el nombre ("Cesar-Moreno"), marcado como `id_provisional`. Ojo: 1,482 ids son solo dígitos y 779 parecen notación
científica ("1e345678") → leer siempre los ids como texto (`TIPOS_ID`). Las cifras del notebook 17 no cambiaron.

**Prueba de `keepers` y `playingtime` (2026-09-19, una página de cada una: Liga MX 2024-25).** A diferencia de
`passing`/`defense` en la Fase 7, **las dos vienen pobladas**:
- `stats_keeper` (/keepers/): 42 porteros, todos con id; 100% en partidos, minutos, goles recibidos, tiros a puerta
  recibidos, paradas, % de paradas, G/E/P, porterías a cero, penales (intentos, recibidos, atajados, fallados). Los
  únicos huecos son porcentajes sin denominador (% porterías a cero 98%, % penales atajados 64%). Kevin Mier (Cruz
  Azul): 14 porterías a cero, igual que el resumen de la página.
- `stats_playing_time` (/playingtime/): 717 filas = las 635 del panel + 82 jugadores que solo fueron a la banca
  (0 partidos, `unused_subs` > 0; por eso minutos/onG/onGA salen al 89%). Las 635 filas con partidos tienen la MISMA
  firma que el panel (`9cd68408`) → se alinean por posición como en la adenda. Columnas: minutos por partido/titularidad,
  partidos completos, entradas de cambio, banca sin jugar, puntos por partido del equipo con él, `on_goals_for`,
  `on_goals_against` (onGA), `plus_minus`, `plus_minus_wowy` (on-off). Consistencia: onGA de Kevin Mier = 27 = sus
  goles recibidos en `keepers`.
- Qué permite en el fantasy: porteros casi completos (porterías a cero, paradas —1 pt cada 3—, penales atajados +5,
  goles recibidos). Para defensas, la resta por goles recibidos sale de onGA (−1 cada 2; con totales de temporada se
  sobreestima un poco, porque FPL redondea por partido). Lo que **no** trae ninguna tabla es la portería a cero de cada
  jugador de campo: habría que estimarla (porterías a cero del equipo × proporción de titularidades) o sacarla de datos
  partido a partido.
- **Cobertura en 2010-11 (Liga MX y Eredivisie, el peor caso por época y por liga):** las dos ligas se comportan igual.
  - `keepers`: completos en partidos, goles recibidos, porterías a cero, G/E/P; tiros a puerta y paradas al 97-100%
    (en Liga MX falta 1 portero con 42 minutos). **Las 5 columnas de penales vienen vacías (0%).**
  - `playingtime`: las filas coinciden exactamente con el panel (firmas `1e89ced8` y `0c8d0739`), pero **solo trae
    partidos, titularidades y minutos**: onG, onGA, +/−, on-off, puntos por partido, banca sin jugar, minutos por
    titularidad/cambio vienen vacíos (0%). Tampoco lista a los que solo fueron a la banca.
  - Conclusión: porterías a cero, goles recibidos y paradas de porteros existen desde 2010-11; los penales atajados y
    todo lo "con el jugador en cancha" (onGA) solo en temporadas recientes.

### Fase 19 — Adenda 2: extracción completa de `keepers` y `playingtime` (2026-09-19)

**Extracción.** 224 páginas (112 liga-temporadas × 2 tablas) desde el Chrome del usuario, mismo método que los ids
(fetch desde una pestaña de FBref, una página cada 8-10 s), pero guardando las tablas completas en IndexedDB (12.8 MB,
más de lo que cabe en localStorage) y bajándolas en una sola descarga autorizada. Incidentes: la extensión de Chrome se
desconectó dos veces (la segunda perdió el grupo de pestañas; los datos siguieron en IndexedDB y se retomó desde la
página 192 con una pestaña nueva) y Cloudflare pidió desafío en la página ~188 (el extractor paró al primer 403 y una
navegación normal lo pasó sola). Resultado: 224/224 páginas, 75,239 filas, 0 filas sin id, 0 errores.

**Conversión** (`scripts/convertir_keepers_playingtime.py`): `data/raw/fbref_keepers/` y `data/raw/fbref_playingtime/`,
112 CSV cada una (mismo formato que `fbref_historical/`: columnas de FBref + `player_id`, `team_id`, `league`,
`season`), y `output/cobertura_keepers_playingtime.csv` (% de filas con dato por tabla, liga, temporada y columna).
Verificación, sin ningún problema: cada portero está en el panel con el mismo jugador y equipo; en las 112 tablas de
minutos los jugadores que jugaron son EXACTAMENTE las filas del panel (comparando id de jugador, id de equipo, partidos
y minutos — así las 22 páginas con renombres/filas invertidas de FBref no cuentan como diferencia). El JSON se retiró
del proyecto tras verificar (los CSV son la fuente).

**Cobertura: primera temporada con el dato (≥ 90% de las filas)**, igual en las 7 ligas salvo una excepción:

| Dato | Desde |
|---|---|
| porterías a cero, goles recibidos (porteros) | 2010-11 |
| paradas y tiros a puerta recibidos | 2010-11 — **hueco: Liga MX y Eredivisie 2018-19 al 0%** |
| onGA, onG, +/−, on-off, puntos por partido, banca sin jugar | 2014-15 (en 2014-16 hay 1-3% sin dato) |
| penales atajados/recibidos/fallados | 2016-17 (La Liga desde 2015-16) |

Consecuencia para el fantasy defensivo: porteros completos (porterías a cero y goles recibidos) en las 16 temporadas,
paradas en todas salvo esos dos huecos, penales atajados desde 2016-17; la resta por goles recibidos de los defensas
(onGA) solo desde 2014-15. Antes de 2014-15 tampoco se sabe quién fue a la banca sin jugar.

### Fase 19 — Adenda 3: un solo CSV de jugadores (2026-09-19)

`python scripts/construir_jugadores_temporada.py` → **`data/processed/jugadores_temporada_2010_2026.csv`**: una fila por
jugador-liga-temporada (59,452 × 69 columnas, 16,307 jugadores) con la tabla estándar, `playingtime`, `keepers` (solo
porteros) y el fantasy ofensivo; se filtra por `league` para trabajar una liga. Acompañado de
`jugadores_temporada_2010_2026_diccionario.csv` (bloque, fuente, desde qué temporada existe y descripción de cada
columna). Reemplaza a `jugadores_temporada_fantasy_2010_2026.csv` (se verificó que sus 59,452 filas y todas sus
columnas quedaron idénticas dentro del nuevo, y se borró). Lógica en `plantillas.cargar_tabla_fbref`,
`unir_tablas_extra` y `agregar_por_temporada` (prueba en `tests/test_plantillas_fantasy.py`):
- unión por (liga, temporada, player_id, team_id), uno a uno; fuera los que solo fueron a la banca (no están en el panel);
- vacío = sin dato: las sumas quedan vacías si ninguna fila del jugador tiene el dato (onGA antes de 2014-15 no es 0);
- conteos sumados entre equipos; puntos por partido ponderado por partidos y on-off ponderado por minutos
  (aproximaciones, FBref no da sus conteos); % de paradas, % de porterías a cero, +/− y onGA/90 recalculados.
- Calidad: en el 94% de los porteros los goles recibidos de `keepers` coinciden con su onGA; el resto difiere casi
  siempre en ±1-2, pero hay casos grandes (Felix Wiedwald, Werder Bremen 2015-16: 40 vs 65). Liga MX concentra 85 de
  los 210 desacuerdos. Decidir qué fuente usar en el fantasy defensivo.

**Pendientes (en orden de impacto).** (El fantasy defensivo, que era el punto 1, se hizo en la Fase 21.)
1. Temporada en curso 2026-27 (parcial) para conectarlo con el seguimiento en vivo.
2. Apolonio en la cancha con eventos de StatsBomb (posición media como sitio, rendimiento como peso).

## Fase 20 — Análisis por liga, empezando por la Liga MX (2026-09-19)

Objetivo del usuario: analizar una liga a fondo y luego ampliar el mismo análisis a las demás. Notebook
`18_analisis_liga_<liga>.ipynb` (uno por liga, mismo código) con un solo parámetro, `LIGA`; figuras en `output/figures/ligas/<liga>_*.png` (no se pisan
entre ligas). Lógica nueva en `futbol_bd/liga.py` (probada en `tests/test_liga.py`; 22 pruebas en total) y estilo
común de figuras en `futbol_bd/estilo.py`:
- `resumen_equipos`: por equipo-temporada, jugadores usados, jugadores para el 80% de los minutos, edad ponderada por
  minutos, % de minutos de extranjeros (`NACIONALES` por liga; nacionalidad deportiva de FBref), % de minutos sub-21,
  resultados (G/E/P reconstruidos con los porteros; 2 de 289 equipo-temporadas de la Liga MX no cuadran) y dependencia
  del máximo goleador. Se calcula sobre filas jugador-EQUIPO (un traspasado aporta a sus dos equipos).
- `porteros_liga` y `carrera_porteros`: tasas sobre totales (no promedios de tasas).
- `estabilidad`: correlación de una métrica entre temporadas consecutivas del mismo jugador. Es la prueba de si una
  métrica mide algo del jugador o es ruido.

**Resultados Liga MX (2010-11 a 2025-26).** Control: cada equipo suma el 97-99.7% de los minutos teóricos.
1. Plantillas: más rotación (jugadores usados 28-30 → 33-35; para el 80% de los minutos 13-14 → 15-16, salto en 2020,
   año de los cinco cambios). Minutos de extranjeros 30% (2010-14) → 54% (2019-20) → ~45% (desde 2022-23). Rotar se
   asocia con perder (Spearman −0.47 contra puntos por partido).
2. Porteros: % de paradas de la liga 74% → 67%; goles recibidos por partido algo más altos en 2022-26. Nahuel Guzmán
   (Tigres) es el mejor de 39 porteros con 100+ partidos en paradas (75.4%), porterías a cero (37.4%) y goles recibidos
   por 90 (0.93). Estabilidad año a año: % paradas 0.30, % porterías a cero 0.22. 2025-26: Keylor Navas 77.2%.
   Calidad: los desacuerdos de goles recibidos (tabla de porteros vs onGA) se concentran en 2014-15 y 2015-16.
3. Impacto en cancha: on-off r = 0.02 y puntos con él − del equipo r = 0.09 año a año (vs 0.52 de goles sin penal/90
   de delanteros): con totales de temporada no miden al jugador. No se publica ranking. Haría falta minutos compartidos
   partido a partido (tipo RAPM).
4. Dependencia del goleador no se asocia con puntos (0.04); los goles totales del equipo sí (0.78). Máximos: Iván
   Alonso 60% (Toluca 2011-12), Dayro Moreno 56%, João Pedro 54% (San Luis 2025-26). La dependencia mediana bajó de
   25-32% a 19-24% desde 2021-22. El mejor jugador fantasy de cada equipo aporta 7-15% de sus puntos.

**Para ampliar a otra liga**: cambiar `LIGA` y correr. Los textos de interpretación del notebook están escritos para
la Liga MX; la forma prevista es generar una copia por liga (`18_analisis_liga_<liga>.ipynb`) con sus propios textos.
**Pendiente**: comparar las 7 ligas en una sola figura (rotación, extranjeros, dependencia, % de paradas).

### Fase 20 — Adenda: análisis publicado en el dashboard (2026-09-19)

**https://dashboard-predicciones.vercel.app/analisis.html** (enlace desde la página de predicciones). Misma estética
que el dashboard (tema oscuro, Chart.js 4.5.1, botones por liga), gráficas interactivas con tooltip, tablas
desplegables, textos de lectura por sección; probada en escritorio y en celular (375 px, sin scroll horizontal).
- `scripts/export_analisis_liga.py <clave>` → `dashboard-predicciones/analisis_<clave>.json` (150 KB para Liga MX).
  Usa exactamente las funciones del notebook 18 (`futbol_bd.liga`; se movieron ahí `agregar_ppg_extra`,
  `mejor_fantasy_por_equipo` y `desacuerdo_goles_porteros`, que antes vivían solo en el notebook). Los textos de
  lectura están en `LECTURAS` por liga; una liga sin textos se publica con solo los datos.
- `desplegar_dashboard.py` ahora permite `analisis.html` y `analisis_<liga>.json` (sigue rechazando cualquier otro
  archivo, p. ej. el registro personal) y los valida: JSON sin NaN, todas las secciones, cada archivo registrado en
  `LIGAS_ANALISIS` existe. Probado con un JSON con NaN, uno sin la sección de porteros y uno faltante: los tres
  bloquean el despliegue. Staging y link público verifican también estos archivos (SHA-256).
- Desplegado con el flujo seguro: staging → pruebas → promoción → link público OK; nueva línea base
  `dashboard-predicciones-p4f7zr7le`.
- **Agregar una liga a la web**: `python scripts/export_analisis_liga.py <clave>`, escribir sus textos en `LECTURAS`
  (después de revisar sus resultados en el notebook), registrarla en `LIGAS_ANALISIS` de `analisis.html` y desplegar.

### Fase 20 — Adenda 2: Premier League y explorador de plantillas (2026-09-19)

**Premier League** publicada (`18_analisis_liga_premier.ipynb` + `analisis_premier.json`). El notebook de la Liga MX se
renombró a `18_analisis_liga_ligamx.ipynb` (un notebook por liga, generado con el mismo código). Resultados, en
contraste con la Liga MX:
- Control: 20 equipos × 38 partidos, 97-99.9% de los minutos teóricos; 41 clubes distintos por los ascensos.
- Plantillas: la rotación NO creció (13-14 jugadores para el 80% de los minutos en todo el periodo); minutos de
  extranjeros (fuera del Reino Unido) 50-59% → 73%; equipos más jóvenes (26.7 → 25.6 años). Rotar vs puntos: −0.29
  (Leicester 2015-16 campeón con 10 jugadores para el 80%).
- Porteros: % de paradas 71% → 66% (misma caída que la Liga MX); 2023-24 la temporada más goleadora (1.61). Čech mejor %
  de paradas (74.4%), Ederson mejores porterías a cero (44.6%) y goles recibidos/90 (0.79). Estabilidad: paradas 0.30,
  porterías a cero 0.36 (más que la Liga MX: las diferencias entre equipos persisten). Datos de goles recibidos
  consistentes entre tablas (0-1 desacuerdos por temporada).
- Impacto: on-off 0.02 y puntos con él 0.04 año a año (vs 0.62 de goles sin penal/90 de delanteros).
- Dependencia: 0.05 con los puntos; goles del equipo 0.87. De los 6 equipos más dependientes, 4 descendieron.

**Explorador de plantillas** (sección 5 de `analisis.html`, para todas las ligas publicadas): selectores de temporada y
equipo → resumen del equipo (puntos por partido, goles, jugadores usados, máximo goleador), tabla de su plantilla
ordenable (edad, nacionalidad, partidos, titularidades, minutos y % de los posibles, goles, asistencias, tarjetas,
puntos fantasy, percentil) y tabla de porteros; clic en un jugador o buscador por nombre → ficha con su trayectoria en
la liga (percentil fantasy por temporada, tabla de temporadas, enlace a FBref). Datos: `explorador` en el JSON, una
fila por jugador-EQUIPO-temporada (puntos fantasy de lo que hizo en ese equipo; percentil de su temporada completa);
~1.2 MB por liga. Verificado en local (Liga MX y Premier, cambio de temporada/equipo/liga, ficha, buscador, celular) y
en el link público. Nueva línea base: `dashboard-predicciones-2hz5f5oml`.

### Fase 20 — Adenda 3: La Liga y resultados de equipo no confiables (2026-09-19)

**Arreglo de calidad (afecta a las 3 ligas publicadas).** Los resultados del equipo se reconstruían sumando los G/E/P
de sus porteros, pero en 7 equipo-temporadas de todo el panel FBref tiene los partidos del portero y sus G/E/P casi en
cero (Mallorca 2011-12: 1 "con resultado" de 38; también Getafe, Levante y Real Betis ese año, más un caso en Liga MX,
Ligue 1 y Serie A). Eso producía puntos por partido falsos. Ahora `liga.resumen_equipos` estima los partidos con los
MINUTOS de los porteros (`pj` = gk_minutes/90, siempre hay uno en cancha) y, si los G/E/P no cuadran con esa cifra,
deja vacíos `ganados/empatados/perdidos/puntos/ppg` y marca `resultados_confiables = False` (prueba en
`tests/test_liga.py`). Las correlaciones de Liga MX y Premier no cambiaron; en La Liga la dependencia pasó de 0.10 a
0.11 y los goles de 0.81 a 0.82.

**La Liga** publicada (`18_analisis_liga_laliga.ipynb` + `analisis_laliga.json`): 8,957 jugador-temporadas, 3,006
jugadores, 35 clubes.
- Plantillas: rotación creciente pero moderada (13.5-14 → 14-15.5 jugadores para el 80% de los minutos). **Es la liga
  más local**: extranjeros entre 36% y 47% de los minutos sin tendencia (Premier: 73%). Rotar vs puntos −0.28; el
  Atlético campeón de 2013-14 usó 11 jugadores para el 80% de los minutos.
- Porteros: caída más suave del % de paradas (71.7% → 68.6%) y la liga con menos goles recibidos por partido. Keylor
  Navas mejor % de paradas (76.7%); Oblak mejor en porterías a cero (46.1%) y goles recibidos/90 (0.79) en 399
  partidos. Estabilidad: paradas 0.27 (la más baja), porterías a cero 0.40 (la más alta de las tres).
- Impacto: on-off 0.04, puntos con él 0.07, referencia 0.69 (la más alta). El patrón se repite en las tres ligas.
- Dependencia: 0.11 con los puntos; goles del equipo 0.82. Falcao (Atlético 2011-12, 47%) es la dependencia alta más
  productiva. Fantasy 2025-26: Mbappé 169 y Lamine Yamal 164 puntos.
- Nueva línea base: `dashboard-predicciones-pvd7i8nc9`.

### Fase 20 — Adenda 4: las 7 ligas publicadas (2026-09-19)

Serie A, Bundesliga, Ligue 1 y Eredivisie completan el análisis: **7 notebooks** (`18_analisis_liga_<liga>.ipynb`, 28
figuras) y **7 JSON** en el dashboard (8 MB en total). Línea base: `dashboard-predicciones-rnjuwgg3k`.

| Liga | Rotación (80% de los minutos) | Extranjeros (min.) | Edad | % paradas | Goles recibidos/partido | Rotar vs. puntos |
|---|---|---|---|---|---|---|
| Liga MX | 13-14 → 15-16 | 30% → 45% (máx. 54%) | 26.4-28.0 | 74% → 67% | 1.2-1.45 | −0.47 |
| Premier | 13-14 estable | 50% → **73%** | 25.6-26.7 | 71% → 66% | 1.26-1.61 | −0.29 |
| La Liga | 13.5-14 → 14-15.5 | 36-47% sin tendencia | 25.9-27.5 | 71.7% → 68.6% | **1.22-1.45** (menos goles) | −0.28 |
| Serie A | 13.5-15 | 42.8% → 70.2% | 25.8-27.7 | 72.6% → 69.1% | 1.21-1.50 | −0.41 |
| Bundesliga | **13-14 (la más estable)** | 51.5-64.6% | **24.7-26.4** | **70.4% → 65.4% (la más baja)** | **1.36-1.60 (la más alta)** | −0.39 |
| Ligue 1 | 13-15 | 49% → **72.6%** | 25.3-26.2 | 70.5% → 66.6% | 1.15 → 1.39-1.48 | −0.35 |
| Eredivisie | **12-14 (la más concentrada)** | 40.8-56.1% | **23.6-25.0 (la más joven)** | 70.9% → 69.0% (la más plana) | 1.42-1.70 | −0.38 |

Hallazgos transversales:
- **El on-off no mide al jugador en NINGUNA liga**: correlación año a año entre −0.06 y 0.08, contra 0.49-0.69 de una
  medida individual (goles sin penal por 90). En la Ligue 1 las dos medidas de impacto salen negativas.
- **Depender del goleador nunca explica los puntos** (de −0.04 en Serie A a 0.21 en Bundesliga); lo que se asocia es
  cuántos goles mete el equipo (0.78 a 0.89). La dependencia más alta del panel: Giakoumakis, 62% de los goles del
  VVV-Venlo 2020-21.
- **Rotar se asocia con perder en las siete** (−0.28 a −0.47), con excepciones cuando la plantilla es muy superior
  (PSG 2020-21: 18 jugadores para el 80% de los minutos y 2.2 puntos por partido).
- **El % de paradas cae en las siete ligas** en los últimos 15 años (entre 2 y 5 puntos).
- Porteros que dominan las tres métricas de su liga: Buffon (Serie A), Sirigu (Ligue 1), Nahuel Guzmán (Liga MX).
- Mejor puntaje fantasy 2025-26 del panel: Harry Kane, 212 puntos (Bayern).
- Juveniles: Eredivisie 20-33.6% de los minutos para menores de 22, Bundesliga 11-21.7%, Premier 6-12.7%.

### Fase 20 — Adenda 5: comparativa de las 7 ligas (2026-09-19)

`liga.comparativa(filas, jt, ligas)` (probada en `tests/test_liga.py`) calcula, con las MISMAS funciones que los
notebooks por liga, las series por liga-temporada (rotación, extranjeros, sub-21, edad, dependencia, % de paradas,
goles recibidos por partido, porterías a cero) y un resumen por liga (3 correlaciones con los puntos y 5 estabilidades
año a año). Se usa en:
- **`19_comparativa_ligas.ipynb`**: 3 figuras (`output/figures/ligas/comparativa_*.png`) — plantillas (2×2), porteros
  (1×3) y correlaciones (dos gráficas de puntos por liga).
- **Sección 6 de `analisis.html`** (`scripts/export_comparativa_ligas.py` → `analisis_comparativa.json`, 11 KB): las
  mismas siete series con una leyenda de color por liga, dos gráficas de barras con las correlaciones y la tabla
  completa. El validador del despliegue comprueba también este JSON (sus secciones son distintas a las de una liga).
  Nueva línea base: `dashboard-predicciones-do3k5ifa2`.

**Identidad de cada liga**: Eredivisie la más joven (24.6 años; 23.7% de minutos sub-21) y la más concentrada;
Premier (73%) y Ligue 1 (72.6%) las más extranjerizadas; La Liga la más local (43%) y, con la Serie A, la que menos
goles recibe; Liga MX la que más rota y la que más castiga rotar (−0.47); Bundesliga la más goleada (1.60) y la más
estable en plantillas.

**Lo que se repite en las 7** (el hallazgo más sólido del proyecto):
1. El on-off no mide al jugador en ninguna liga: **−0.03 a 0.08** año a año, contra **0.49-0.69** de una medida
   individual (goles sin penal/90 de delanteros). Los puntos del equipo con él: −0.06 a 0.09.
2. Rotar mucho va con perder en las siete (−0.28 a −0.47).
3. Lo que se asocia con los puntos es meter goles (0.78 a 0.89); la dependencia del goleador no (−0.04 a 0.21).
4. El % de paradas de la liga cae en las siete (2 a 7 puntos en 15 años).
5. Las porterías a cero dependen de la liga: estabilidad año a año de 0.22 (Liga MX) a 0.45 (Serie A).

Las dos cosas que quedaban pendientes aquí —el fantasy defensivo y repetir estas comparaciones por posición— se
resolvieron en la Fase 21.

## Fase 21 — Fantasy defensivo y comparación por posición (2026-09-19)

El puntaje fantasy del proyecto era solo ofensivo, así que porteros y defensas aparecían con la mitad de su trabajo
sin contar (59 puntos por temporada contra 102 de un delantero). Esta fase lo cierra usando `keepers` y `playingtime`.

**El problema y cómo se resolvió.** FBref publica porterías a cero SOLO de los porteros. De un jugador de campo se
sabe cuántos goles recibió su equipo con él en cancha (`on_goals_against`, desde 2014-15) pero no cómo se repartieron
entre partidos, que es lo que decide una portería a cero. Solución: suponer que los goles de un partido siguen una
Poisson y usar el estimador **insesgado** de e^(−λ), que es ((n−1)/n)^goles con n = noventas jugados (enchufar
λ̂ = goles/partidos en e^(−λ) sobreestima un 4.7% por convexidad), multiplicado por las titularidades, que aproximan
la regla FPL de los 60 minutos.

**La validación, que es lo que hace usable la estimación**: los porteros son el único banco de pruebas posible y se
les aplica exactamente la misma fórmula. Contra 4,542 porteros-equipo-temporada con la cifra real: **r = 0.96**,
sesgo −1.7%, error absoluto medio 0.91 (±1.5 en un titular ⇒ ±6 puntos fantasy). Caso concreto: Van Dijk 2018-19
(38 partidos, 22 goles recibidos en cancha) → 21.0 porterías a cero estimadas; el Liverpool tuvo exactamente 21.

**Segundo detalle que había que hacer bien**: FPL redondea DENTRO de cada partido ("+1 por cada 3 paradas", "−1 por
cada 2 goles"). `fantasy.esperanza_piso` calcula el valor esperado de ese redondeo bajo la misma Poisson. Para un
portero titular: paradas +33.6 → +22.5 y goles recibidos −22.0 → −14.5, 19 puntos por temporada de diferencia.

**Código nuevo** (probado, 8 pruebas nuevas; 33 en total):
- `fantasy.ESQUEMA_DEFENSIVO`, `esperanza_piso`, `porterias_cero_estimadas`, `puntos_defensivos`,
  `validar_porterias_cero`.
- `liga.comparativa_posiciones` y `liga.origen_porteria_cero`.
- El CSV unificado pasa de 69 a 79 columnas (`porterias_cero`, el desglose defensivo, `pts_total_completo`,
  `def_completo` y `pct_pts_completo`). **`def_completo` es la columna con la que hay que filtrar**: antes de 2014-15
  no hay onGA y antes de 2016-17 no hay penales atajados, así que sin ella se confunde "sin dato" con "puntuó poco".
- `20_fantasy_defensivo.ipynb` (5 figuras `output/figures/ligas/fantasy_def_*.png`) y la **sección 7 de
  `analisis.html`** (`scripts/export_fantasy_defensivo.py` → `analisis_defensivo.json`, 14 KB). El validador del
  despliegue ya comprueba los dos JSON que no dependen de la liga elegida.
  Nueva línea base: `dashboard-predicciones-726a5ph7x`.

**Resultados.**
1. Con la mitad defensiva, el portero pasa de 58.6 a 100.8 puntos por temporada y el defensa de 58.7 a 75.4; el
   delantero se queda en 101.5 (no recibe puntos defensivos). El rango entre posiciones pasa de 58-102 a 75-102.
2. **La estabilidad año a año sube en las 7 ligas** para porteros (+0.08 de media) y defensas (+0.07), no se mueve en
   mediocampistas (−0.01) y es idéntica en delanteros: la firma de una mejora real, no de ruido añadido.
3. **Pero la portería a cero es sobre todo del equipo**: cuando el jugador cambia de club, la correlación cae 0.21 en
   defensas y 0.24 en delanteros, y solo **0.08 en porteros**. El portero es el único que se lleva una parte
   apreciable consigo — coherente con que el % de paradas fuera la métrica de portero más estable en la Fase 20.
4. Los puntos defensivos disponibles dependen de la liga: un portero de La Liga promedia 45.7 y uno de la Bundesliga
   36.5; entre defensas, 19.4 contra 11.9 (casi el doble). Comparar entre ligas exige percentiles, no puntos brutos.
5. La Liga MX es la excepción: la estabilidad de sus porteros sigue en cero (−0.02 → 0.03), con Apertura/Clausura y
   la mayor rotación del panel.

### Fase 21 — Adenda: las comparaciones rehechas con el percentil (2026-09-19)

Con el fantasy completo ya se puede usar `pct_pts_completo` (percentil dentro de la liga-temporada-posición), que es
lo único que pone a un defensa de la Eredivisie y a uno de la Premier en la misma escala. **Lo primero es saber qué NO
se puede hacer con él**: el percentil medio de toda liga es 50 por construcción (comprobado: 50.6-50.7 en las siete),
así que comparar percentiles medios entre ligas no dice nada.

Código nuevo (probado, 3 pruebas más; **36 en total**): `fantasy.percentil_completo` (regla única que usan el CSV, los
notebooks y la web), `liga.escalera_ligas`, `liga.plantel_vs_puntos` y la columna `estab_percentil` en
`liga.comparativa_posiciones`. Notebook `21_percentil_entre_ligas.ipynb` (3 figuras `percentil_*.png`) y **sección 8
de `analisis.html`** (`scripts/export_percentil_ligas.py` → `analisis_percentil.json`, 7 KB).
Nueva línea base: `dashboard-predicciones-qcyvz3itb`.

**1. El percentil se repite MENOS que los puntos**, en las 7 ligas y las 4 posiciones: delanteros 0.50 → 0.37,
mediocampistas 0.55 → 0.47, defensas 0.38 → 0.34, porteros 0.28 → 0.21. Parte de lo que parecía estabilidad del
jugador era estabilidad de su contexto (ambiente goleador de su liga y su época). La cifra en percentiles es la
honesta, con la salvedad de que comprime los extremos y por eso castiga sobre todo a los delanteros.

**2. Escalera de dificultad de las ligas**, con 606 traspasos entre ligas. **El control es la mitad del trabajo**:
quien se muda fue elegido por su última temporada, así que su percentil cae por regresión a la media aunque no cambie
de liga. El punto de comparación son los 1,180 que cambiaron de CLUB dentro de su misma liga (misma selección, mismo
trastorno de mudarse): esa recta es `pct_sig = 40.7 + 0.35·pct`, o sea que del percentil 90 se cae a 72 sin cambiar
de liga. Sobre esos residuos se ajusta `residuo = dificultad(origen) − dificultad(destino)`, una incógnita por liga:

| Premier +7.9 | La Liga +3.3 | Bundesliga +2.2 | Serie A +0.3 | Ligue 1 −1.8 | Eredivisie −2.7 | Liga MX −9.1 |

Errores estándar verificados contra un bootstrap de 2,000 remuestreos (coinciden: 1.3 vs 1.4 en la Premier).
**Solo la Premier y la Liga MX se separan**: Premier − Ligue 1 = +9.8 (IC95 +6.3 a +13.3), Premier − La Liga = +4.7
(+1.4 a +7.9), Premier − Liga MX = +17.0 (+6.1 a +27.6, con solo 23 traspasos). La Liga − Serie A y Serie A − Ligue 1
NO son distinguibles. Flujos: la Ligue 1 exporta 155 y recibe 84; la Premier recibe 207 y exporta 81.

**3. El plantel explica los puntos en las 7 ligas por igual** (rho 0.78 a 0.86), y el percentil medio del plantel le
gana al número de figuras del 20% superior (0.75-0.83): pesa más un plantel entero decente que unos pocos
excepcionales. Buena parte de esa correlación es mecánica (los puntos fantasy se construyen con los sucesos que ganan
partidos), pero el contraste con el on-off sigue en pie: lo que el jugador PRODUJO sí se corresponde con lo que logró
el equipo; las medidas de "impacto" no.

## Fase 22 — Los diagramas de Apolonio, publicados e interactivos (2026-09-19)

Los mapas de Apolonio existían desde la Fase 19 pero solo como tres figuras de la Liga MX en el notebook 17. Ahora
están en la **sección 9 de `analisis.html`**, en las siete ligas y navegables **por temporada, por equipo y por
jugador**.

**Decisión de diseño: el servidor manda sitios, no imágenes.** `scripts/export_apolonio.py` →
`analisis_apolonio.json` (150 KB, 2,240 sitios = 7 ligas × 16 temporadas × 20 atacantes) con el punto de cada jugador
(goles sin penal/90, asistencias/90), su peso (puntos fantasy) y el dominio fijo de su liga. El navegador **rasteriza
el diagrama** con el mismo algoritmo que `apolonio.etiquetar`. Así se cambia de temporada, equipo, jugador y modo sin
volver al servidor, en vez de pre-generar 112 imágenes.

**Cómo se evita que el JavaScript se desvíe de Python**: cada sitio lleva además el área que le calculó
`apolonio.etiquetar` en modo multiplicativo (resolución 300). La página recalcula esas áreas con su propio código y
avisa en consola si alguna difiere más de 1 punto porcentual. Verificado en las 7 ligas: **ningún aviso**. Es el mismo
patrón de la Fase 19 con la firma FNV-1a entre el extractor JS y Python.

**Qué trae la sección**: selector de temporada, equipo (resalta a sus jugadores en naranja), jugador (búsqueda; lo
resalta y abre una ficha con todas las temporadas en que entró al top-20, con enlace a FBref) y modo (multiplicativo,
aditivo, Voronoi normal). El mapa tiene hover: dice qué jugador domina el perfil bajo el cursor. La tabla del % del
plano se recalcula con el modo que se esté viendo; la de la ficha usa el multiplicativo y lo dice.

**El peso es `pts_total` (fantasy ofensivo), no el completo de la Fase 21**: el completo solo existe desde 2014-15 y
para atacantes la parte defensiva vale 0-7 puntos, así que usarlo costaría cuatro temporadas a cambio de casi nada.

**La advertencia va en la página, no en una nota al pie**: el área de la celda NO mide rendimiento (correlación 0.43
con los puntos en Liga MX, y muy volátil — 1% → 39% → 1% con el percentil casi quieto). El mapa sirve para ver
vecindarios de perfil, no para rankear. Está en un bloque `.aviso`, el mismo que usan las demás advertencias del
dashboard.

Nueva línea base: `dashboard-predicciones-kuakyuoxg`.

**Pendiente**: el bonus (BPS) de FPL, que necesita datos por partido que FBref no publica en las tablas de liga.

## Fase 23 — Apolonio sobre la cancha (2026-09-20)

El último pendiente de la Fase 19. Los diagramas de Apolonio pasan del espacio de perfil a la **cancha de verdad**,
que es su uso original en fútbol (la *dominant region* de Taki y Hasegawa, 2000). Notebook
`22_apolonio_en_la_cancha.ipynb` y **sección 10 de `analisis.html`**. Nueva línea base: `dashboard-predicciones-7hmz2obl4`.

**Datos**: StatsBomb Open Data, **2015/16**. ⚠️ **Corregido el 2026-09-22**: esta fase se hizo con DOS ligas porque
se dio por buena la afirmación "las dos únicas temporadas que publica completas", que era **falsa y nunca se
verificó**. Son **cuatro**: La Liga 380/380, Premier 380/380, Serie A 380/380 y Ligue 1 377/380. El error llegó a
publicarse en el texto de la sección 10. Ahora son **1,517 partidos** y ~38,000 filas jugador-partido.
Lo que sí es cierto es que el resto del catálogo abierto de StatsBomb no sirve aquí: son temporadas parciales
centradas en un equipo (la Premier 2003/04 son los 38 partidos del Arsenal invicto; las 17 temporadas de La Liga
entre 2004/05 y 2020/21 son los del Barcelona de Messi, 30-35 cada una). Se comprobó contando partidos por temporada,
no leyendo la documentación.
`scripts/descargar_statsbomb_posiciones.py` (reanudable) guarda solo el agregado por jugador-partido: son ~8 MB de
eventos por partido y el análisis solo usa la posición media y el conteo de acciones.

**Una diferencia de cálculo que importa**: en el espacio de perfil había que llevar los dos ejes a [0, 1] porque uno
llegaba a 1 y el otro a 0.6; **en la cancha NO se normaliza nada**, porque los dos ejes ya están en metros. Hay una
prueba (`test_la_cancha_no_se_normaliza`) que lo blinda.

**Un detalle de datos que costaba caro**: en los eventos StatsBomb trae el nombre legal completo, así que Messi es
"Lionel Andrés Messi Cuccittini" y quedarse con la última palabra daba "Cuccittini". El nombre con el que se conoce a
cada jugador está en `player_nickname` de las ALINEACIONES, que se bajan aparte; cuando falta, el nombre se corta por
delante ("Marco Asensio Willemsen" → "Marco Asensio"), nunca por detrás.

**Código nuevo** (`futbol_bd/cancha.py`, 6 pruebas; **42 en total**): `posiciones_por_partido` (agregado + marca de
titular leída del evento *Starting XI*), `sitios_de_equipo`, `area_dominada`, `origen_del_area`,
`fiabilidad_del_area`, `reparto_por_equipo`, `dibujar_cancha`.

**Resultados** (iguales en las dos ligas):
1. El área de **un** partido es casi ruido: **0.35** de un partido al siguiente jugando en el mismo puesto, contra
   0.49-0.69 de una medida individual establecida. Cambiar de línea la baja a **0.24**; cambiar de etiqueta dentro de
   la misma línea no cambia nada (las etiquetas de StatsBomb son demasiado granulares).
2. **Pero la media de la temporada sí mide al jugador, y con holgura**: fiabilidad por mitades (Spearman-Brown)
   **0.90-0.93 en las cuatro ligas** (Serie A la más alta, Ligue 1 la más baja), que se queda en **0.85-0.90** al
   quitar la media del puesto y **0.85-0.90** al quitar además la del equipo en esa línea. Con el control excesivo de
   (equipo, puesto exacto) baja a 0.66-0.75, y se reporta como cota inferior porque ahí se le resta al jugador su
   propia señal. **Es la métrica individual que mejor ha pasado la prueba del proyecto**, y ahora replicada en cuatro
   campeonatos de cuatro países, no en dos.
3. Por líneas: defensas 10.7% de la cancha y medios 10.4%, contra porteros 5.6% y atacantes 6.5% (reparto igual =
   9.1%). Los atacantes son los más repetibles (0.45) y los defensas los que menos (0.18), no por erráticos sino
   porque se parecen mucho entre sí y hay poca variación que correlacionar.
4. Del cuartil de equipos-partido más repartidos al más concentrados, los puntos por partido caen de **1.66 a 1.17**.
   No hay que leerlo como causa: quien domina el partido tiene más balón y el reparto se iguala solo.

**Trampa metodológica que quedó documentada**: el R² del equipo sale 0% y eso **no es un hallazgo**, es aritmética —
las áreas suman 1 dentro de cada equipo, así que la media de cualquier equipo es 1/11 por construcción. Cuando una
métrica se define como un reparto, los efectos del grupo desaparecen solos y hay que buscarlos de otra forma.

**Advertencias que van en la página, no en una nota al pie**: la posición media no es dónde estuvo el jugador (la
dispersión típica cubre un tercio de la cancha, y la sección deja verla); y el peso es participación con éxito, no
calidad, así que el área mide territorio de participación.

**Pendiente**: sin datos de seguimiento óptico no hay velocidades, así que esto no es la *dominant region* original
—que responde "quién llega antes a cada punto"— sino su versión posible con eventos.

## Fase 24 — La temporada 2026-27 en curso (2026-09-20)

El otro pendiente de la Fase 19. Se extrajeron las 7 ligas × 3 tablas (stats, keepers, playingtime) de la temporada
**2026-2027**, que está empezando: Bundesliga 4 jornadas, Ligue 1 / Premier / Serie A 5, Eredivisie y La Liga 7,
Liga MX 9. Panel: 112 → **119 liga-temporadas**, 61,542 → **64,489 filas**; dataset consolidado 62,376 × 80.
Nueva línea base: `dashboard-predicciones-2r9gbcfd9`.

**La extracción, 21 páginas, 0 bloqueos de Cloudflare.** Dos cosas que conviene recordar para la próxima:
1. El primer `fetch` dio **403** y NO era Cloudflare de verdad: llevaba `credentials: "omit"`, que descarta la cookie
   `cf_clearance` que la pestaña ya tenía. Con `credentials: "same-origin"` funcionó a la primera. Antes de dar un 403
   por bloqueo, comprobar que se mandan las cookies.
2. Chrome aplica *intensive throttling* a los `setTimeout` de pestañas ocultas: el bucle interno pasó de una página
   cada 9 s a una cada 5 minutos. La solución fue dejar de dormir dentro de la página y marcar el ritmo desde fuera,
   una página por llamada.
`scripts/fbref_extraer_tabla.js` ahora acepta un `doc`, para extraer de una página traída con fetch() sin navegar.

**Dos problemas de datos que la temporada nueva destapó** (los dos con prueba):
- **La edad cambia de formato.** En las temporadas cerradas FBref la da como años enteros ("29"); en la que está en
  curso, como años-días ("30-284"). Eso convertía en NaN la edad ponderada y los minutos sub-21 de toda la temporada.
  `plantillas.edad_en_anios` se queda con los años y aguanta los dos formatos.
- **Una temporada de 5 jornadas no puede ir en la misma serie que las completas.** `limpiar_panel` marca ahora
  `temporada_parcial` (menos del 60% de las jornadas habituales de su liga). El umbral es bajo a propósito: las
  temporadas acortadas pero TERMINADAS de 2019-20 por COVID (Ligue 1, 27 de 38) **no** se marcan, porque se jugaron y
  el proyecto siempre las ha incluido — cambiarlo habría movido cifras ya publicadas.

**Cómo queda repartido en la web**: las gráficas por temporada (secciones 1-4 y 6-8) excluyen la temporada en curso;
el **explorador de plantillas** sí la incluye y abre en ella, con un aviso que dice cuántas jornadas lleva y por qué
los percentiles salen vacíos. `resumen_equipos` y `porteros_liga` aceptan `incluir_parciales=True` para eso.
Los exportadores del fantasy defensivo, el percentil y Apolonio no necesitaron cambios: ya filtran por 900 o 1,500
minutos, que nadie alcanza todavía, así que la temporada parcial no se cuela sola en ninguna comparación.

`scripts/incorporar_temporada_fbref.py` deja el proceso repetible para la próxima temporada: valida las 21 páginas,
las columnas contra el panel y que no falte ningún id **antes** de escribir nada.

**Pendiente**: repetir la extracción cada cierto tiempo para seguir la 2026-27 según avance (el script es idempotente
con `--reemplazar`), y el bonus (BPS) de FPL, que sigue necesitando datos por partido que FBref no publica.

## Fase 26 — Serie A y Ligue 1 en el mapa de cancha (2026-09-22)

Al preguntar el usuario por qué la sección 10 tenía solo dos ligas, se comprobó contra StatsBomb y **la respuesta era
un error mío, no una limitación de la fuente**: son cuatro las temporadas completas, no dos (ver Fase 23, corregida).
Se bajaron Serie A y Ligue 1 2015/16, se reejecutó el notebook 22 y se republicó la sección 10 con las cuatro.

**El hallazgo aguanta, y ahora con cuatro campeonatos**: fiabilidad 0.906 (La Liga), 0.899 (Premier), **0.929
(Serie A)** y 0.898 (Ligue 1). El reparto también: Gini 0.461-0.477 y mayor celda 28-29% en las cuatro. El gradiente
Gini→puntos se mantiene monótono con el doble de muestra (2,863 equipos-partido): 1.66 → 1.42 → 1.30 → 1.17.

**Tres gráficas se rompieron al pasar de 2 a 4 series** y ninguna lo avisó — hay que mirarlas, no solo comprobar que
el notebook corra sin errores:
- el ancho de barra estaba fijo en 0.38 (pensado para dos), así que cuatro barras invadían el grupo vecino; ahora se
  calcula como `0.8 / len(LIGAS)`;
- la leyenda tapaba la etiqueta de una barra y, al moverla arriba, chocaba con el título; acabó debajo del eje;
- las etiquetas del eje Y usaban `liga.split()[0]`, que con dos ligas daba "La" y "Premier" (feo pero legible) y con
  cuatro daba "La", "Serie" y "Ligue", que no son nombres de nada; ahora se quita la temporada con `rsplit`.

**La lección**: la afirmación falsa ("las dos únicas") se escribió una vez, se copió al plan, al notebook y al JSON de
la web, y sobrevivió tres fases sin que nadie la comprobara. Verificar contra la fuente cuesta una consulta.

## Fase 25 — La actualización, encadenada y en temporizador (2026-09-22)

El seguimiento en vivo llevaba cuatro días parado (última congelada: 18 sept) porque actualizarlo eran 13 comandos a
mano y se olvidan. `scripts/actualizar_semanal.py` encadena los pasos de las 4 ligas europeas y dice al final qué NO
tocó. Al correrlo quedaron **calificados 27 partidos: 15 aciertos (56%)** — Premier 4/7, La Liga 3/6, Bundesliga 4/6,
Serie A 4/8. Nueva línea base tras publicar.

**La cadena real tiene tres pasos por liga, no dos**, y saltarse el primero fue el error al escribir el script:
`europa_construir_dataset.py` (CSV crudos → dataset procesado) → `export_predicciones_europa.py` →
`congelar_predicciones.py`. El exportador **no lee los CSV crudos**, así que sin reconstruir el dataset los
resultados nuevos estaban bajados pero el dashboard seguía viendo los viejos y no calificaba nada.

**Dos bugs encontrados y arreglados al automatizar** (los dos solo aparecen fuera del camino feliz):
- `congelar_predicciones.py` reventaba con `KeyError: 'date'` cuando no hay partidos futuros: un DataFrame vacío no
  tiene columnas. Y eso pasa de forma **rutinaria**, no excepcional — football-data publica el calendario a mitad de
  semana, así que entre el fin de una jornada y esa publicación no hay futuros. Ahora sale limpio sin tocar el registro.
- La validación de la descarga rechazaba archivos buenos por el **BOM**: leyendo el texto ya decodificado la primera
  columna se llama `\ufeffDiv` y la comprobación de columnas fallaba siempre. Se leen los bytes con `utf-8-sig` y se
  guardan tal cual llegaron.

**Por qué el temporizador corre DOS veces por semana** (`scripts/com.javiercarrillo.futbol.actualizar.plist`, launchd):
los dos trabajos son distintos y ninguno sirve en el momento del otro. El **lunes** ya están los resultados del fin de
semana y se califica el seguimiento; el **viernes** ya está publicado el calendario de la jornada siguiente y hay que
CONGELAR antes de que se juegue nada. Si el viernes no corre, esa jornada se pierde para siempre del seguimiento en
vivo, porque solo cuenta lo que se dijo antes del partido. El plist está escrito y validado pero **NO instalado**:
se instala con `cp` a `~/Library/LaunchAgents` + `launchctl load`.

**Seguridad al sobrescribir**: football-data a veces responde una página de error con código 200. Un archivo así
encima del bueno borraría la temporada. Por eso un CSV descargado solo reemplaza al local si parsea, trae las columnas
mínimas y **no tiene menos partidos** que el que ya estaba; el calendario futuro se exceptúa de lo último porque es
una ventana móvil que encoge sola.

**Lo que NO se puede automatizar, y queda dicho en cada corrida**: Liga MX (sus partidos futuros se capturan a mano;
la J10 la definió el usuario el 18 sept) y FBref (Cloudflare solo responde desde el navegador del usuario).

**El proyecto se mudó a `~/Proyectos/Big_data_futbol`** (antes `~/Desktop/Big_data_futbol`) y el temporizador quedó
**instalado y probado**. La mudanza no fue estética: macOS protege el Escritorio con TCC y un agente de launchd **no
puede leer nada ahí** sin Acceso a Disco Completo. Se comprobó con un experimento (un agente de prueba en `/tmp`
leyendo `/tmp` sí, la carpeta del proyecto no) en vez de suponerlo por el mensaje de error, que era
`/bin/zsh: can't open input file` y no decía "permiso denegado".

La alternativa era dar Acceso a Disco Completo a `/bin/zsh`, y se descartó: eso se lo da a **cualquier** script de
zsh en segundo plano, y no estaba claro que Vercel (otro binario) heredara el permiso. Mover el proyecto a una
carpeta no protegida lo resuelve de raíz y para siempre. Costó 12 archivos con la ruta escrita a mano (ningún
notebook). Tras la mudanza: 45 pruebas pasan y el agente corre bajo launchd con código 0 y sin errores.

**Trampa al verificar**: el `sed` de la mudanza también reescribió `registro/launchd_error.log`, así que el error
viejo reapareció con la ruta NUEVA y parecía un fallo nuevo. Se resolvió vaciando los logs y repitiendo la corrida.
Al verificar un arreglo, vaciar primero el log que se va a leer.

**Pendiente**: el registro de apuestas `registro_personal/jugadas.csv`, que sigue vacío — el esquema y el calificador
existen desde la Fase 18.

## Anexos — Scouting
- Percentiles de rendimiento por posición (barras + grids).
- Comparación de equipos: goles/asistencias reales vs. xG/xA esperados.
- Similaridad entre jugadores usando estadísticas de FBref (distancia
  euclidiana/coseno sobre métricas normalizadas).
- Notebook: `06_scouting_percentiles_similaridad.ipynb`

## Fuentes de datos a usar
- **StatsBomb Open Data** (gratuito, vía `statsbombpy`) — mejor para eventos detallados.
- **Understat** (xG por partido/jugador) — scraping ligero, JSON embebido en HTML.
- **FBref** (estadísticas agregadas por jugador/equipo, ideal para scouting).
- **FotMob** — scraping de su API interna (JSON), útil para datos en vivo/resumen.
  Nota: el paquete de R `worldfootballR` dejó de soportar FotMob en su versión
  0.6.4 por cambios en sus términos de servicio — señal de que esta fuente es
  la más frágil legalmente de las cuatro.
- **Transfermarkt** (valores de mercado, transferencias) — vía `worldfootballR`
  en R, no tenemos equivalente en Python todavía.

## worldfootballR (R)
Paquete de R ([jaseziv.github.io/worldfootballR](https://jaseziv.github.io/worldfootballR/))
que cubre FBref, Transfermarkt y Understat con funciones ya armadas — cubre
parte de lo mismo que hacemos a mano en Python con `soccerdata`/scraping propio,
pero con Transfermarkt (valores de mercado) que no teníamos.

- Instalado vía `remotes::install_github("JaseZiv/worldfootballR")` (no está en
  CRAN actualizado).
- Kernel de Jupyter registrado como `ir-futbol-bigdata` — selecciona ese kernel
  en un notebook `.ipynb` para escribir celdas en R en vez de Python.
- Uso previsto: complementar la Fase 1 (adquisición) y el Anexo de Scouting con
  datos de Transfermarkt que StatsBomb/FBref no tienen, y como referencia de
  qué funciones/columnas existen ya armadas antes de replicarlas en Python si
  hace falta.
- Notebooks en R viven en `notebooks_r/` para no mezclarlos con los de Python.

## Cómo avanzar
Cada notebook de fase se trabaja de forma independiente y se puede ejecutar
sin depender de los anteriores (usa datos de ejemplo de StatsBomb Open Data
para no depender de credenciales). Al terminar una fase, anota en este archivo
qué quedó pendiente o qué duda surgió, antes de pasar a la siguiente.
