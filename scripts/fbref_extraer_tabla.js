/**
 * Extractor de tablas de jugadores de FBref CON los identificadores de FBref (Fase 19).
 *
 * Por qué existe
 * --------------
 * El panel de plantillas (data/raw/fbref_historical/, 112 archivos) se extrajo leyendo el TEXTO de cada celda, así que
 * solo guardó el nombre del jugador. La revisión de la Fase 19 mostró que el nombre no identifica a nadie: hay 176
 * nombres compartidos por 2+ personas y al menos un par (dos "Vitinha", portugueses, 2000) que ni con año de nacimiento
 * y nacionalidad se separa. FBref sí tiene un id único por jugador y por equipo: está en los enlaces de cada fila
 *   /en/players/1f44ac21/Erling-Haaland          -> player_id = 1f44ac21
 *   /en/squads/b8fd03ef/2024-2025/Manchester-City -> team_id   = b8fd03ef
 * Esta función devuelve la misma tabla de siempre (mismas columnas, con los nombres internos `data-stat` de FBref, que
 * son los que ya usa el panel) más `player_id` y `team_id` al final.
 *
 * Uso
 * ---
 * FBref bloquea `requests` con Cloudflare (Fase 7), así que se corre DENTRO del navegador, con la página de la
 * liga-temporada ya cargada (p. ej. https://fbref.com/en/comps/31/2024-2025/stats/2024-2025-Liga-MX-Stats):
 *     extraerTablaFBref("stats_standard")      // -> texto CSV
 * o sobre una página traída con fetch() desde otra pestaña de FBref, sin navegar:
 *     const doc = new DOMParser().parseFromString(await (await fetch(url)).text(), "text/html");
 *     extraerTablaFBref("stats_standard", doc)
 * Otras tablas de jugadores de la misma familia de páginas:
 *     "stats_keeper"   (.../keepers/...)       porterías a cero, paradas, goles recibidos
 *     "stats_playing_time" (.../playingtime/...) goles a favor/en contra con el jugador en cancha (onG, onGA)
 * El CSV resultante se guarda en data/raw/ agregándole `league` y `season`, igual que el panel actual.
 *
 * Detalles que maneja
 * -------------------
 * - FBref manda varias tablas grandes COMENTADAS dentro del HTML (<!-- <table ...> -->) y las activa con JavaScript;
 *   si la tabla no está en el DOM todavía, se busca dentro de esos comentarios.
 * - Cada ~25 filas FBref repite la fila de encabezados dentro del <tbody> (clase "thead"): se descartan.
 * - La columna "matches" es solo un enlace ("Matches"), no un dato: se descarta (el panel actual tampoco la usa).
 *
 * Probado contra FBref real (2026-09-19) — lo que conviene saber para el próximo scrapeo
 * --------------------------------------------------------------------------------------
 * - Se usó para agregar los ids a las 112 tablas del panel (ver scripts/unir_ids_fbref.py): mismas columnas que el
 *   panel, id de jugador y de equipo en el 100% de las 61,542 filas.
 * - Hay jugadores SIN página en FBref (43 filas, casi todos Liga MX 2010-11): su `player_id` es el nombre
 *   ("Cesar-Moreno"), no un código de 8 caracteres. FBref además tiene algunos perfiles duplicados (misma persona, 2
 *   ids): se corrigen con ALIAS_FBREF en futbol_bd/plantillas.py.
 * - Los ids parecen números con frecuencia ("12345678", "1e345678"): leer siempre esas columnas como texto.
 * - Ritmo: con una página cada 8-10 s no hubo problemas durante ~100 páginas; después FBref respondió 403 con
 *   `cf-mitigated: challenge` (desafío de Cloudflare). Una navegación normal a cualquier página de FBref en el
 *   navegador del usuario lo pasó sola, sin interacción, y se pudo continuar. Si el desafío pide interacción (casilla
 *   de verificación), la resuelve el usuario, no el asistente.
 * - Para no pasar tablas completas por la conversación, en esa extracción se pidieron las páginas con fetch() desde
 *   una pestaña de FBref, se verificó cada una contra una firma (hash FNV-1a del contenido) del CSV ya guardado, y solo
 *   se guardaron los ids (localStorage -> una sola descarga JSON al final).
 */
function extraerTablaFBref(idTabla = "stats_standard", doc = document) {
  // `doc` permite pasar una página traída con fetch() y parseada con DOMParser, en vez de la que está abierta: así se
  // pueden recorrer varias liga-temporadas sin navegar, que es como se hizo la extracción de la Fase 19.
  let tabla = doc.querySelector(`table#${idTabla}`);
  if (!tabla) {
    const contenedor = doc.querySelector(`#all_${idTabla}`) || doc.body || doc.documentElement;
    const iterador = (doc.ownerDocument || doc).createNodeIterator(contenedor, NodeFilter.SHOW_COMMENT);
    for (let nodo = iterador.nextNode(); nodo && !tabla; nodo = iterador.nextNode()) {
      if (nodo.nodeValue.includes(`id="${idTabla}"`)) {
        tabla = new DOMParser().parseFromString(nodo.nodeValue, "text/html").querySelector(`table#${idTabla}`);
      }
    }
  }
  if (!tabla) throw new Error(`No encontré la tabla "${idTabla}" en esta página`);

  // El id está en el enlace: /en/players/<id>/<slug> o /en/squads/<id>/... -> el 4º segmento al partir por "/".
  const idDeEnlace = (celda, tipo) => {
    const a = celda && celda.querySelector(`a[href*="/${tipo}/"]`);
    return a ? a.getAttribute("href").split("/")[3] : "";
  };

  const filas = [...tabla.querySelectorAll("tbody tr")].filter(
    (tr) => !tr.classList.contains("thead") && !tr.classList.contains("over_header") &&
            tr.querySelector('[data-stat="player"] a'));
  if (!filas.length) throw new Error(`La tabla "${idTabla}" no tiene filas de jugadores`);

  const registros = filas.map((tr) => {
    const r = {};
    for (const celda of tr.querySelectorAll("[data-stat]")) r[celda.dataset.stat] = celda.textContent.trim();
    const celdaJugador = tr.querySelector('[data-stat="player"]');
    // `data-append-csv` es el id que FBref usa en su propio "Get table as CSV"; el enlace es el respaldo.
    r.player_id = celdaJugador.dataset.appendCsv || idDeEnlace(celdaJugador, "players");
    r.team_id = idDeEnlace(tr.querySelector('[data-stat="team"]'), "squads");
    return r;
  });

  // Columnas en el orden en que aparecen en la tabla (primera fila), sin "matches", y los ids al final.
  const columnas = [...filas[0].querySelectorAll("[data-stat]")].map((c) => c.dataset.stat)
    .filter((c) => c !== "matches").concat(["player_id", "team_id"]);
  const escapar = (v) => (/[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v);
  return [columnas.join(","), ...registros.map((r) => columnas.map((c) => escapar(r[c] ?? "")).join(","))].join("\n");
}
