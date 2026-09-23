# Big Data aplicado al fútbol

Proyecto de análisis de fútbol con dos entregables públicos y un principio que gobierna todo lo demás:
**una cifra no se publica hasta saber si mide algo.** Buena parte del trabajo consiste en descartar métricas que
parecían útiles y no lo eran, y eso está documentado igual que lo que sí funcionó.

- **Predicciones y seguimiento en vivo** — 5 ligas, con las probabilidades *congeladas antes* de cada partido.
- **Análisis por liga** — 10 secciones sobre plantillas, rotación, porteros, fantasy y reparto territorial.

Ambos se publican en <https://dashboard-predicciones.vercel.app>.

---

## Qué hay aquí

| Carpeta | Qué contiene |
|---|---|
| `futbol_bd/` | La librería: 7 módulos con la lógica reutilizable y **45 pruebas** en `tests/` |
| `notebooks/` | 29 notebooks, uno por fase de análisis, ejecutados y con sus salidas |
| `scripts/` | 27 scripts: descarga, construcción de datasets, exportadores del dashboard y despliegue |
| `dashboard-predicciones/` | El sitio publicado (HTML + los JSON que lee) |
| `output/` | Figuras generadas por los notebooks |
| `PLAN_DE_TRABAJO.md` | **El diario del proyecto.** 26 fases con qué se hizo, qué salió y qué se descartó |

`PLAN_DE_TRABAJO.md` es el documento importante: el código dice *cómo*, el plan dice *por qué* y, sobre todo, qué
se intentó y no funcionó. Si vas a tocar algo, léelo antes.

## De dónde salen los datos

| Fuente | Qué aporta | ¿Automatizable? |
|---|---|---|
| [football-data.co.uk](https://www.football-data.co.uk/) | Resultados y cuotas de las ligas europeas | Sí, descarga directa |
| [FBref](https://fbref.com/) | Plantillas, porteros y minutos (2010-11 a 2026-27) | **No**: Cloudflare solo responde desde un navegador con sesión |
| [StatsBomb Open Data](https://github.com/statsbomb/open-data) | Eventos con posición, 2015/16 | Sí, vía `statsbombpy` |
| Liga MX | Calendario y resultados | **No**: se captura a mano |

La carpeta `data/` **no está en el repositorio** (son ~87 MB y se regenera). Para reconstruirla:

```bash
python scripts/descargar_statsbomb_posiciones.py --liga todas
```

Los CSV de FBref necesitan el navegador; el procedimiento está en `scripts/fbref_extraer_tabla.js` y
`scripts/incorporar_temporada_fbref.py`.

## Puesta en marcha

```bash
conda create -n futbol-bigdata python=3.11 && conda activate futbol-bigdata
pip install pandas numpy scipy matplotlib scikit-learn statsbombpy jupyter pytest requests
python -m pytest tests/ -q
```

Para ver el dashboard en local:

```bash
python -m http.server 8765 --directory dashboard-predicciones
```

## La actualización semanal

`scripts/actualizar_semanal.py` encadena todo lo que se puede automatizar de las 4 ligas europeas:
descargar → reconstruir el dataset → exportar → congelar predicciones → publicar.

```bash
python scripts/actualizar_semanal.py --solo-descargar   # mirar si hay partidos nuevos
python scripts/actualizar_semanal.py                    # cadena completa
```

Corre solo, dos veces por semana, con un agente de `launchd`
(`scripts/com.javiercarrillo.futbol.actualizar.plist`). **Son dos y no una a propósito**: el lunes califica el fin de
semana, y el viernes congela la jornada siguiente. Si el viernes no corre, esa jornada se pierde para siempre del
seguimiento en vivo, porque solo cuenta lo que se dijo *antes* del partido.

> El agente debe vivir **fuera** de `~/Desktop`, `~/Documents` y `~/Downloads`: macOS protege esas carpetas con TCC y
> un proceso en segundo plano no puede leerlas sin Acceso a Disco Completo.

## Lo que se encontró

**El modelo de predicción no le gana al mercado.** En las 5 ligas, las casas de apuestas predicen mejor. Donde sí
aporta algo es en los partidos parejos: ahí la frecuencia de empate sube de forma clara y medible.

**El territorio dominado sí mide al jugador.** Es el mejor resultado del proyecto. El área que domina un futbolista
en *un* partido es casi ruido (0.35 de un partido al siguiente), pero la media de su temporada es muy fiable:
**0.90-0.93 en las cuatro ligas**, y aguanta al descontarle su puesto (0.85-0.90) y su equipo (0.85-0.90).

**Mide participación, no calidad.** El peso de cada jugador son sus acciones completadas, así que quien más toca el
balón domina más mapa aunque el partido lo decida otro con tres toques. Y la posición media no es dónde estuvo: su
dispersión típica cubre un tercio de la cancha.

## Dos trampas que conviene no repetir

**Un R² de 0% puede ser aritmética, no un hallazgo.** El área dominada se reparte entre los once de un equipo, así
que las áreas suman 1 y la media de cualquier equipo es 1/11 *por construcción*. El efecto del equipo no puede
existir. Cuando una métrica se define como un reparto, los efectos de grupo desaparecen solos.

**Una afirmación sin verificar sobrevive.** Durante tres fases este proyecto dijo que StatsBomb solo publica dos
temporadas completas. Son cuatro. La frase se escribió una vez, se copió al plan, al notebook y al sitio web, y nadie
la comprobó hasta que alguien preguntó. Comprobarlo costaba una consulta.

## Convenciones

- **El código está comentado en detalle y en español**, explicando el *porqué* de cada decisión, no el *qué*.
  Los comentarios que explican una decisión metodológica valen más que el código que documentan: no los borres al
  refactorizar.
- Cualquier lógica que se use en un análisis vive en `futbol_bd/` y tiene prueba. Los notebooks orquestan, no deciden.
- Las cifras que se publican llevan su advertencia al lado, no en una nota al pie.
