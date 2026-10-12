/**
 * Extractor de Liga MX en FBref, para correr DENTRO de una pestaña del navegador del usuario (Claude in Chrome).
 *
 * Pegar este archivo completo en la consola/javascript_tool de una pestaña que ya muestre
 *   https://fbref.com/en/comps/31/schedule/Liga-MX-Scores-and-Fixtures
 * Define dos funciones en `window`. Lo que devuelven es TEXTO delimitado con "|" (los .psv que lee
 * scripts/ligamx_incorporar_semana.py), porque el javascript_tool corta la salida cerca de 1,000 caracteres y la
 * bloquea si trae URLs con parámetros o ciertas palabras como CLAVE de un objeto: se pide en trozos pequeños.
 *
 *   window.__ligamxCalendario(idsConocidos)   -> { jugadosNuevos: n, porJugar: n }   (llena window.__nuevas y window.__fut)
 *   window.__lineasNuevos(desde, hasta)       -> líneas de schedule_nuevos_<etiqueta>.psv
 *   window.__lineasFuturos(desde, hasta)      -> líneas de futuros_<etiqueta>.psv
 *   await window.__ext(matchId)               -> una línea de reportes_<etiqueta>.psv (descarga la página del partido)
 *
 * Límites aprendidos (2026-10-10), respétalos o el navegador deja de responder:
 *   - Cada llamada de javascript_tool tiene tope de 45 s: máximo 3 reportes por llamada con 6-7 s de pausa entre
 *     páginas (también evita el desafío de Cloudflare).
 *   - Un lote de browser_batch con 7 llamadas excede el tiempo total; usar lotes de 3.
 *   - Un dato ausente en FBref (corners de un equipo, paradas de un portero) llega VACÍO y debe quedarse vacío.
 *
 * Validado el 2026-10-10 contra un partido ya guardado (Puebla–Toluca, 889c1480): los 25 campos idénticos.
 */

// Orden de las columnas de reportes_<etiqueta>.psv después del match_id:
//   posL|posV|sotL|tirosL|sotV|tirosV|paradasL|aPuertaContraL|paradasV|aPuertaContraV|amarL|rojasL|amarV|rojasV|
//   faltasL|faltasV|cornersL|cornersV|centrosL|centrosV|intercepL|intercepV|fuerasL|fuerasV
window.__ligamxCalendario = (idsConocidos) => {
  const conocidos = new Set(idsConocidos);
  const t = document.querySelector('table.stats_table');
  const todas = [...t.querySelectorAll('tbody tr')]
    .filter(r => !r.classList.contains('thead') && !r.classList.contains('spacer'))
    .map(r => {
      const g = s => { const c = r.querySelector(`[data-stat="${s}"]`); return c ? c.textContent.trim() : ''; };
      const a = r.querySelector('[data-stat="match_report"] a');
      const href = a ? a.getAttribute('href') : '';
      const m = href.match(/matches\/([0-9a-f]{8})\//);
      return { gw: g('gameweek'), dow: g('dayofweek'), date: g('date'), time: g('start_time'), home: g('home_team'),
               score: g('score'), away: g('away_team'), att: g('attendance'), venue: g('venue'), ref: g('referee'),
               mid: m ? m[1] : '', notes: g('notes') };
    });
  window.__nuevas = todas.filter(x => x.mid && !conocidos.has(x.mid) && x.score);   // jugados que aún no tenemos
  window.__fut = todas.filter(x => !x.score && x.date);                               // por jugar
  return { jugadosNuevos: window.__nuevas.length, porJugar: window.__fut.length };
};

window.__lineasNuevos = (desde, hasta) => window.__nuevas.slice(desde, hasta)
  .map(x => [x.gw, x.dow, x.date, x.time, x.home, x.score, x.away, x.att, x.venue, x.ref, x.mid, x.notes].join('|'))
  .join('\n');

window.__lineasFuturos = (desde, hasta) => window.__fut.slice(desde, hasta)
  .map(x => [x.gw, x.date, x.time, x.home, x.away].join('|')).join('\n');

window.__ext = async (mid) => {
  const a = document.querySelector(`a[href*="/matches/${mid}/"]`);
  if (!a) return `${mid}|ERROR|sin enlace`;
  const r = await fetch(a.getAttribute('href'), { credentials: 'same-origin' });
  if (!r.ok) return `${mid}|ERROR|http ${r.status}`;      // 403 = Cloudflare: parar, no insistir
  const doc = new DOMParser().parseFromString(await r.text(), 'text/html');
  const canon = (doc.querySelector('link[rel="canonical"]') || {}).href || '';
  if (!canon.includes(mid)) return `${mid}|ERROR|canonical no coincide`;
  const ts = doc.querySelector('#team_stats');
  const filas = ts ? [...ts.querySelectorAll('tr')].filter(tr => tr.querySelectorAll('td').length === 2) : [];
  const num = (s) => { const m = (s || '').match(/(\d+)\s*%/); return m ? m[1] : ''; };
  const pos = filas[0] ? [...filas[0].querySelectorAll('td')].map(td => num(td.textContent)) : ['', ''];
  // Tiros: pie de la tabla resumen de cada equipo (la primera es la local).
  const tf = [...doc.querySelectorAll("table[id^='stats_'][id$='_summary']")].slice(0, 2).map(t => {
    const g = s => { const c = t.querySelector(`tfoot td[data-stat="${s}"]`); return c ? c.textContent.trim() : ''; };
    return [g('shots_on_target'), g('shots')];
  });
  // Paradas y tiros a puerta en contra: suma de las filas de portero de cada equipo.
  const kp = [...doc.querySelectorAll("table[id^='keeper_stats_']")].slice(0, 2).map(t => {
    let sv = 0, sot = 0, hay = false;
    t.querySelectorAll('tbody tr').forEach(r => {
      const g = s => { const c = r.querySelector(`[data-stat="${s}"]`); return c ? parseInt(c.textContent, 10) : NaN; };
      if (!isNaN(g('gk_saves'))) { sv += g('gk_saves'); hay = true; }
      if (!isNaN(g('gk_shots_on_target_against'))) sot += g('gk_shots_on_target_against');
    });
    return hay ? [sv, sot] : ['', ''];
  });
  // Tarjetas: última fila de dos celdas de #team_stats; una doble amarilla cuenta +1 amarilla y +1 roja.
  const tarj = filas.length ? [...filas[filas.length - 1].querySelectorAll('td')].map(td => {
    const c = k => td.querySelectorAll(`span.${k}`).length;
    return [c('yellow_card') + c('yellow_red_card'), c('red_card') + c('yellow_red_card')];
  }) : [['', ''], ['', '']];
  // Extras POR ESTRUCTURA: cada fila es [valor local][etiqueta][valor visitante]. Leer el texto aplanado corría un
  // valor ausente a la fila siguiente (corners 10/vacío salía como 10/45).
  const ex = {};
  const te = doc.querySelector('#team_stats_extra');
  if (te) te.querySelectorAll('div').forEach(d => {
    const lab = d.textContent.trim();
    if (d.children.length === 0 && ['Fouls', 'Corners', 'Crosses', 'Interceptions', 'Offsides'].includes(lab)) {
      const p = d.previousElementSibling, n = d.nextElementSibling;
      ex[lab] = [p ? p.textContent.trim() : '', n ? n.textContent.trim() : ''];
    }
  });
  const e = k => ex[k] || ['', ''];
  return [mid, pos[0], pos[1], tf[0] && tf[0][0], tf[0] && tf[0][1], tf[1] && tf[1][0], tf[1] && tf[1][1],
    kp[0] && kp[0][0], kp[0] && kp[0][1], kp[1] && kp[1][0], kp[1] && kp[1][1],
    tarj[0][0], tarj[0][1], tarj[1][0], tarj[1][1],
    e('Fouls')[0], e('Fouls')[1], e('Corners')[0], e('Corners')[1], e('Crosses')[0], e('Crosses')[1],
    e('Interceptions')[0], e('Interceptions')[1], e('Offsides')[0], e('Offsides')[1]].join('|');
};
