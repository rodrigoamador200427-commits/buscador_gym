// assets/admin.js — panel de administrador (lo carga lib/admin_panel.html vía admin.php).
//
// Pide los datos a admin_estadisticas.php?seccion=...&dias=... (solo GET, siempre agregados:
// nunca correo, nombre, fecha de nacimiento ni perfil) y los dibuja. Las gráficas son SVG
// propio, sin librerías ni enlaces externos, y se pintan con las variables de estilos.css.
//
// Regla de seguridad: todo texto que viene del servidor pasa por esc() antes de entrar en
// innerHTML. Los datos de este panel son agregados, pero los títulos de documentos y las
// raíces de búsqueda son contenido y no se confía en ellos.
(function () {
    'use strict';

    const $ = id => document.getElementById(id);
    const esc = t => String(t ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    const n = v => Number(v).toLocaleString('es');
    const plural = (v, uno, varios) => `${n(v)} ${Number(v) === 1 ? uno : varios}`;
    const pct = (parte, total) => (total > 0 ? Math.round(parte / total * 1000) / 10 : 0);

    const SECCIONES = [
        { id: 'resumen', nombre: 'Resumen' },
        { id: 'mas', nombre: 'Más consumidos' },
        { id: 'menos', nombre: 'Menos consumidos' },
        { id: 'edad', nombre: 'Edad' },
        { id: 'busquedas', nombre: 'Búsquedas' },
        { id: 'cobertura', nombre: 'Cobertura' },
    ];
    const PERIODOS = [7, 30, 90];
    const TIPO = { ejercicios: 'Ejercicio', articulos: 'Artículo' };
    const VIA = {
        interseccion: 'Cruce de dos árboles', concepto: 'Salto entre árboles', recuperacion: 'Salto desde los resultados',
        concepto_local: 'Recomendación dentro del tema', sin_interseccion: 'Sin relación entre ambos conceptos',
        ninguno: 'Sin relación', 'sin descubrimiento': 'Sin descubrimiento',
    };

    let seccion = 'resumen';
    let dias = 30;
    let peticion = 0;
    let tablasActuales = {};
    let redibujar = [];            // funciones que repintan las gráficas al cambiar el ancho

    // ------------------------------------------------------------------ formatos
    function fechaCorta(dia) {
        const [a, m, d] = dia.split('-').map(Number);
        return new Date(a, m - 1, d).toLocaleDateString('es', { day: 'numeric', month: 'short' }).replace('.', '');
    }
    function fechaLarga(dia) {
        const [a, m, d] = dia.split('-').map(Number);
        return new Date(a, m - 1, d).toLocaleDateString('es', { day: 'numeric', month: 'long' });
    }
    function variacionTexto(v) {
        const periodo = `los ${dias} días anteriores`;
        if (v === null || v === undefined) return `Sin datos de ${periodo} para comparar`;
        if (v === 0) return `Igual que ${periodo}`;
        return `${v > 0 ? '+' : '−'}${Math.abs(v).toLocaleString('es', { maximumFractionDigits: 1 })} % frente a ${periodo}`;
    }
    const lista = (items, max = 3) => items.slice(0, max).map(x => `«${x}»`).join(', ');

    // ------------------------------------------------------------------ servidor
    async function pedir(sec, d) {
        const res = await fetch(`admin_estadisticas.php?seccion=${encodeURIComponent(sec)}&dias=${d}`, { credentials: 'same-origin' });
        let datos = null;
        try { datos = await res.json(); } catch { /* respuesta no JSON */ }
        if (res.status === 401 || res.status === 403) throw Object.assign(new Error('acceso'), { codigo: res.status });
        if (!res.ok || !datos || datos.status !== 'success') throw new Error('respuesta');
        return datos;
    }

    // ------------------------------------------------------------------ escalas
    /** Máximo "redondo" del eje y paso entre marcas, con 5 marcas o menos. */
    function escala(max) {
        for (const base of [1, 2, 5]) {
            for (let e = 0; e < 9; e++) {
                const paso = base * 10 ** e;
                if (max / paso <= 5) return { paso, tope: Math.max(paso, Math.ceil(max / paso) * paso) };
            }
        }
        return { paso: 1, tope: Math.max(1, max) };
    }
    const recortar = (texto, max) => (texto.length > max ? texto.slice(0, Math.max(1, max - 1)) + '…' : texto);
    const vacio = texto => `<p class="tabla-vacia">${esc(texto)}</p>`;

    // ------------------------------------------------------------------ gráficas (SVG propio)
    /** Líneas por día. series = [{clave, nombre, clase: 'g-a'|'g-b'|'g-c'}]. */
    function lineas(el, puntos, series) {
        if (!puntos.length || !series.some(s => puntos.some(p => p[s.clave] > 0))) {
            el.innerHTML = vacio('Sin actividad en este período.');
            return;
        }
        const W = Math.max(280, el.clientWidth), H = 250, m = { t: 14, r: 14, b: 34, l: 40 };
        const ancho = W - m.l - m.r, alto = H - m.t - m.b;
        const { paso, tope } = escala(Math.max(...series.flatMap(s => puntos.map(p => p[s.clave]))));
        const x = i => m.l + (puntos.length === 1 ? ancho / 2 : i * ancho / (puntos.length - 1));
        const y = v => m.t + alto * (1 - v / tope);
        const salto = Math.ceil(puntos.length / Math.max(2, Math.floor(ancho / 62)));
        let g = '';
        for (let v = 0; v <= tope; v += paso) {
            g += `<line class="${v === 0 ? 'g-eje' : 'g-rejilla'}" x1="${m.l}" x2="${W - m.r}" y1="${y(v)}" y2="${y(v)}"/>`
               + `<text class="g-suave" x="${m.l - 8}" y="${y(v) + 4}" text-anchor="end">${n(v)}</text>`;
        }
        puntos.forEach((p, i) => {                          // fechas: siempre se rotula el último día (hoy)
            if ((puntos.length - 1 - i) % salto === 0) {
                g += `<text class="g-suave" x="${x(i)}" y="${H - 10}" text-anchor="middle">${esc(fechaCorta(p.dia))}</text>`;
            }
        });
        for (const s of series) {
            g += `<polyline class="g-linea ${s.clase}" points="${puntos.map((p, i) => `${x(i).toFixed(1)},${y(p[s.clave]).toFixed(1)}`).join(' ')}"/>`;
            if (puntos.length <= 31) {
                g += puntos.map((p, i) => `<circle class="g-punto ${s.clase}" cx="${x(i).toFixed(1)}" cy="${y(p[s.clave]).toFixed(1)}" r="3"/>`).join('');
            }
        }
        const anchoZona = Math.max(8, ancho / Math.max(1, puntos.length - 1));
        puntos.forEach((p, i) => {
            const texto = [fechaLarga(p.dia), ...series.map(s => `${s.nombre}: ${n(p[s.clave])}`)].join('\n');
            g += `<rect class="g-zona" x="${(x(i) - anchoZona / 2).toFixed(1)}" y="${m.t}" width="${anchoZona.toFixed(1)}" height="${alto}" tabindex="0" role="img" data-tip="${esc(texto)}" aria-label="${esc(texto.replace(/\n/g, '. '))}"/>`;
        });
        el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="group" aria-label="Gráfica de líneas por día">${g}</svg>`;
    }

    /** Barras horizontales, ya ordenadas de mayor a menor, con el valor al lado. items = [{etiqueta, valor, texto, tip}] */
    function barrasH(el, items) {
        if (!items.length) { el.innerHTML = vacio('Sin datos en este período.'); return; }
        const W = Math.max(280, el.clientWidth), fila = 26, hueco = 8;
        const etiquetaW = Math.min(190, Math.floor(W * 0.4));
        const valorW = Math.max(28, Math.max(...items.map(i => i.texto.length)) * 7.4 + 6);
        const barraMax = Math.max(20, W - etiquetaW - valorW - 14);
        const max = Math.max(1, ...items.map(i => i.valor));
        const H = items.length * (fila + hueco);
        const caracteres = Math.floor(etiquetaW / 6.9);
        const g = items.map((it, k) => {
            const yy = k * (fila + hueco), w = it.valor > 0 ? Math.max(3, it.valor / max * barraMax) : 0;
            const tip = it.tip || `${it.etiqueta}\n${it.texto}`;
            return `<g data-tip="${esc(tip)}" tabindex="0" role="img" aria-label="${esc(tip.replace(/\n/g, '. '))}">`
                + `<text class="g-texto" x="0" y="${yy + fila / 2 + 4.5}">${esc(recortar(it.etiqueta, caracteres))}</text>`
                + `<rect class="g-barra" x="${etiquetaW}" y="${yy + 3}" width="${w.toFixed(1)}" height="${fila - 6}" rx="3"/>`
                + `<text class="g-valor" x="${(etiquetaW + w + 6).toFixed(1)}" y="${yy + fila / 2 + 4.5}">${esc(it.texto)}</text></g>`;
        }).join('');
        el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="group" aria-label="Gráfica de barras horizontales">${g}</svg>`;
    }

    /** Barras verticales agrupadas por categoría. series = [{clave, nombre, clase: 'g-a'|'g-b'}] */
    function barrasAgrupadas(el, categorias, series) {
        if (!categorias.length) { el.innerHTML = vacio('Sin datos en este período.'); return; }
        const W = Math.max(280, el.clientWidth), H = 270, m = { t: 22, r: 10, b: 44, l: 40 };
        const ancho = W - m.l - m.r, alto = H - m.t - m.b;
        const { paso, tope } = escala(Math.max(1, ...categorias.flatMap(c => series.map(s => c[s.clave]))));
        const y = v => m.t + alto * (1 - v / tope);
        const grupoW = ancho / categorias.length, barraW = Math.min(44, grupoW * 0.78 / series.length);
        let g = '';
        for (let v = 0; v <= tope; v += paso) {
            g += `<line class="${v === 0 ? 'g-eje' : 'g-rejilla'}" x1="${m.l}" x2="${W - m.r}" y1="${y(v)}" y2="${y(v)}"/>`
               + `<text class="g-suave" x="${m.l - 8}" y="${y(v) + 4}" text-anchor="end">${n(v)}</text>`;
        }
        categorias.forEach((c, i) => {
            const x0 = m.l + i * grupoW + (grupoW - barraW * series.length) / 2;
            const tip = [c.etiqueta, ...series.map(s => `${s.nombre}: ${n(c[s.clave])}`)].join('\n');
            g += `<g data-tip="${esc(tip)}" tabindex="0" role="img" aria-label="${esc(tip.replace(/\n/g, '. '))}">`;
            series.forEach((s, k) => {
                const alt = alto * c[s.clave] / tope;
                g += `<rect class="${s.clase}" x="${(x0 + k * barraW).toFixed(1)}" y="${(m.t + alto - alt).toFixed(1)}" width="${(barraW - 2).toFixed(1)}" height="${alt.toFixed(1)}" rx="2"/>`
                   + `<text class="g-valor" x="${(x0 + k * barraW + (barraW - 2) / 2).toFixed(1)}" y="${(m.t + alto - alt - 5).toFixed(1)}" text-anchor="middle">${n(c[s.clave])}</text>`;
            });
            g += `<text class="g-texto" x="${(m.l + i * grupoW + grupoW / 2).toFixed(1)}" y="${H - 22}" text-anchor="middle">${esc(c.etiqueta)}</text>`
               + `<text class="g-suave" x="${(m.l + i * grupoW + grupoW / 2).toFixed(1)}" y="${H - 7}" text-anchor="middle">${esc(c.pie || '')}</text></g>`;
        });
        el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="group" aria-label="Gráfica de barras agrupadas">${g}</svg>`;
    }

    function leyendaHTML(series, tipo) {
        const muestra = s => tipo === 'linea'
            ? `<svg viewBox="0 0 28 12" aria-hidden="true"><line class="g-linea ${s.clase}" x1="2" x2="26" y1="6" y2="6"/></svg>`
            : `<svg viewBox="0 0 28 12" aria-hidden="true"><rect class="${s.clase}" x="6" y="0" width="16" height="12" rx="2"/></svg>`;
        return `<ul class="leyenda" aria-label="Leyenda">${series.map(s => `<li>${muestra(s)}${esc(s.nombre)}</li>`).join('')}</ul>`;
    }

    // ------------------------------------------------------------------ bloques de la página
    function tarjetaNumero({ titulo, valor, detalle, texto }) {
        return `<section class="tarjeta-numero"><h2>${esc(titulo)}</h2>`
            + `<div class="valor${texto ? ' valor-texto' : ''}">${esc(texto ? valor : n(valor))}</div>`
            + (detalle ? `<p class="detalle-numero">${detalle}</p>` : '') + '</section>';
    }
    const conVariacion = (v) => `<strong>${esc(variacionTexto(v))}</strong>`;

    function pintarGraficas(graficas) {
        redibujar = [];
        $('graficas').innerHTML = graficas.map((g, i) => `
            <section class="grafica${g.ancha ? ' grafica-ancha' : ''}" aria-labelledby="g-titulo-${i}">
                <h2 id="g-titulo-${i}">${esc(g.titulo)}</h2>
                ${g.nota ? `<p class="nota">${esc(g.nota)}</p>` : ''}
                ${g.leyenda ? leyendaHTML(g.leyenda.series, g.leyenda.tipo) : ''}
                <div class="grafica-lienzo" id="g-lienzo-${i}"></div>
            </section>`).join('');
        graficas.forEach((g, i) => {
            const el = $(`g-lienzo-${i}`);
            const dibujar = () => g.dibujar(el);
            dibujar();
            redibujar.push(dibujar);
        });
    }

    function tablaHTML(t) {
        tablasActuales[t.id] = t;
        const celda = (c, v) => {
            const texto = Array.isArray(v) ? v.join(', ') : v;
            return `<td${c.num ? ' class="num"' : ''}>${esc(c.num && typeof texto === 'number' ? n(texto) : texto)}</td>`;
        };
        return `<section class="tabla-bloque" aria-labelledby="t-${esc(t.id)}">
            <div class="tabla-cab"><h2 id="t-${esc(t.id)}">${esc(t.titulo)}</h2>
                <button type="button" class="btn" data-csv="${esc(t.id)}"${t.filas.length ? '' : ' disabled'}>Exportar CSV</button></div>
            ${t.nota ? `<p class="nota conteo">${esc(t.nota)}</p>` : ''}
            ${t.filas.length ? `<div class="tabla-envoltura" tabindex="0"><table><caption>${esc(t.titulo)}</caption>
                <thead><tr>${t.columnas.map(c => `<th scope="col"${c.num ? ' class="num"' : ''}>${esc(c.titulo)}</th>`).join('')}</tr></thead>
                <tbody>${t.filas.map(f => `<tr>${t.columnas.map(c => celda(c, f[c.clave])).join('')}</tr>`).join('')}</tbody></table></div>`
                : `<div class="tabla-envoltura">${vacio(t.vacio || 'Sin datos en este período.')}</div>`}
        </section>`;
    }

    // ------------------------------------------------------------------ CSV (solo datos agregados)
    function csvCelda(v) {
        let s = Array.isArray(v) ? v.join('; ') : String(v ?? '');
        if (/^[=+\-@\t\r]/.test(s)) s = "'" + s;          // evita que una hoja de cálculo ejecute un título como fórmula
        return /[",\n;]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    }
    function csvDe(id) {
        const t = tablasActuales[id];
        if (!t) return '';
        return [t.columnas.map(c => csvCelda(c.titulo)).join(','),
            ...t.filas.map(f => t.columnas.map(c => csvCelda(f[c.clave])).join(','))].join('\r\n') + '\r\n';
    }
    function descargarCSV(id) {
        const blob = new Blob(['﻿' + csvDe(id)], { type: 'text/csv;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `panel-${seccion}-${id}-${dias}dias.csv`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
    }

    // ------------------------------------------------------------------ vistas por sección
    const SERIES_ACTIVIDAD = [{ clave: 'aperturas', nombre: 'Aperturas', clase: 'g-a' }, { clave: 'me_gusta', nombre: '«Me gusta»', clase: 'g-b' }];

    function vistaResumen(d) {
        const tarjetas = [
            { titulo: 'Cuentas', valor: d.cuentas.valor, detalle: `Nuevas en el período: <strong>${n(d.cuentas.nuevas.valor)}</strong>. ${esc(variacionTexto(d.cuentas.nuevas.variacion))}` },
            { titulo: 'Perfiles', valor: d.perfiles.valor, detalle: 'Entre todas las cuentas' },
            { titulo: 'Perfiles activos', valor: d.perfiles_activos.valor, detalle: conVariacion(d.perfiles_activos.variacion) },
            { titulo: 'Búsquedas', valor: d.busquedas.valor, detalle: conVariacion(d.busquedas.variacion) },
            { titulo: 'Aperturas', valor: d.aperturas.valor, detalle: conVariacion(d.aperturas.variacion) },
            { titulo: '«Me gusta»', valor: d.me_gusta.valor, detalle: conVariacion(d.me_gusta.variacion) },
        ];
        const pico = d.por_dia.reduce((a, p) => (p.aperturas + p.me_gusta > a.aperturas + a.me_gusta ? p : a), d.por_dia[0] || { aperturas: 0, me_gusta: 0 });
        const totalActividad = d.aperturas.valor + d.me_gusta.valor;
        const picoBusq = d.por_dia.reduce((a, p) => (p.busquedas > a.busquedas ? p : a), d.por_dia[0] || { busquedas: 0 });
        return {
            tarjetas,
            graficas: [
                {
                    titulo: totalActividad === 0 ? `Sin aperturas ni «me gusta» en los últimos ${dias} días`
                        : `La actividad llegó a su punto más alto el ${fechaLarga(pico.dia)}: ${plural(pico.aperturas, 'apertura', 'aperturas')} y ${plural(pico.me_gusta, '«me gusta»', '«me gusta»')}`,
                    leyenda: { series: SERIES_ACTIVIDAD, tipo: 'linea' },
                    dibujar: el => lineas(el, d.por_dia, SERIES_ACTIVIDAD),
                },
                {
                    titulo: d.busquedas.valor === 0 ? `No hubo búsquedas en los últimos ${dias} días`
                        : `Hubo ${plural(d.busquedas.valor, 'búsqueda', 'búsquedas')}; el día con más fue el ${fechaLarga(picoBusq.dia)}, con ${n(picoBusq.busquedas)}`,
                    dibujar: el => lineas(el, d.por_dia, [{ clave: 'busquedas', nombre: 'Búsquedas', clase: 'g-a' }]),
                },
            ],
            tablas: [],
        };
    }

    function vistaMas(d) {
        const tabla = (id, titulo, filas) => ({
            id, titulo, filas, vacio: 'Sin aperturas ni «me gusta» en este período.',
            columnas: [{ clave: 'titulo', titulo: 'Título' }, { clave: 'aperturas', titulo: 'Aperturas', num: true }, { clave: 'me_gusta', titulo: '«Me gusta»', num: true }, { clave: 'total', titulo: 'Total', num: true }],
        });
        const grafica = (filas, plural1, singular) => ({
            titulo: filas.length ? `«${filas[0].titulo}» lidera ${plural1} con ${plural(filas[0].total, 'interacción', 'interacciones')} (${plural(filas[0].aperturas, 'apertura', 'aperturas')} y ${plural(filas[0].me_gusta, '«me gusta»', '«me gusta»')})`
                : `Sin aperturas ni «me gusta» de ${singular} en los últimos ${dias} días`,
            nota: filas.length ? 'Aperturas más «me gusta», los 10 primeros.' : '',
            dibujar: el => barrasH(el, filas.map(f => ({ etiqueta: f.titulo, valor: f.total, texto: n(f.total),
                tip: `${f.titulo}\n${plural(f.aperturas, 'apertura', 'aperturas')}, ${plural(f.me_gusta, '«me gusta»', '«me gusta»')}` }))),
        });
        const [ej, ar] = [d.ejercicios, d.articulos];
        const suma = l => l.reduce((a, f) => a + f.total, 0);
        return {
            tarjetas: [
                { titulo: 'Ejercicio más consumido', texto: true, valor: ej[0]?.titulo ?? 'Sin interacciones', detalle: ej[0] ? `<strong>${esc(plural(ej[0].total, 'interacción', 'interacciones'))}</strong>` : '' },
                { titulo: 'Artículo más consumido', texto: true, valor: ar[0]?.titulo ?? 'Sin interacciones', detalle: ar[0] ? `<strong>${esc(plural(ar[0].total, 'interacción', 'interacciones'))}</strong>` : '' },
                { titulo: 'Interacciones en el top de ejercicios', valor: suma(ej) },
                { titulo: 'Interacciones en el top de artículos', valor: suma(ar) },
            ],
            graficas: [grafica(ej, 'los ejercicios', 'ejercicios'), grafica(ar, 'los artículos', 'artículos')],
            tablas: [tabla('ejercicios', 'Top 10 de ejercicios', ej), tabla('articulos', 'Top 10 de artículos', ar)],
        };
    }

    function vistaMenos(d) {
        const poco = d.poco_abiertos, nunca = d.nunca_mostrados;
        const totalNunca = d.nunca_mostrados_total.ejercicios + d.nunca_mostrados_total.articulos;
        const avisos = [];
        if (poco.length) {
            avisos.push({ titulo: 'Qué conviene revisar', texto: `Estos documentos aparecen mucho en los resultados y casi nadie los abre; revisa su título y sus etiquetas: ${lista(poco.map(p => p.titulo))}.`
                + (d.etiquetas_a_revisar.length ? ` Etiquetas que se repiten entre ellos: ${d.etiquetas_a_revisar.map(e => `${e.etiqueta} (${plural(e.documentos, 'documento', 'documentos')})`).join(', ')}.` : '') });
        }
        if (totalNunca > 0) {
            avisos.push({ titulo: 'Documentos que nunca se han mostrado', texto: `${plural(totalNunca, 'documento', 'documentos')} no ha aparecido nunca en una búsqueda o recomendación. Revisa que tengan etiquetas y palabras que la gente busque: ${lista(nunca.map(x => x.titulo))}.` });
        }
        const p0 = poco[0];
        return {
            tarjetas: [
                { titulo: 'Se muestran mucho y casi no se abren', valor: poco.length, detalle: `Con al menos ${n(d.minimo_impresiones ?? 20)} impresiones en el período` },
                { titulo: 'Nunca se han mostrado', valor: totalNunca, detalle: `${esc(plural(d.nunca_mostrados_total.ejercicios, 'ejercicio', 'ejercicios'))} y ${esc(plural(d.nunca_mostrados_total.articulos, 'artículo', 'artículos'))}` },
                { titulo: 'Etiqueta a revisar primero', texto: true, valor: d.etiquetas_a_revisar[0]?.etiqueta ?? 'Ninguna destaca', detalle: d.etiquetas_a_revisar[0] ? `En ${esc(plural(d.etiquetas_a_revisar[0].documentos, 'documento', 'documentos'))} poco abiertos` : '' },
            ],
            avisos,
            graficas: [
                {
                    titulo: p0 ? `«${p0.titulo}» se mostró ${plural(p0.impresiones, 'vez', 'veces')} y ${p0.aperturas === 0 ? 'nadie lo abrió' : `solo se abrió ${plural(p0.aperturas, 'vez', 'veces')}`}`
                        : 'Ningún documento se muestra mucho y se abre poco en este período',
                    nota: poco.length ? 'Impresiones y porcentaje de aperturas, de menor a mayor tasa de apertura.' : '',
                    dibujar: el => barrasH(el, poco.map(p => ({ etiqueta: p.titulo, valor: p.impresiones, texto: `${n(p.impresiones)} · ${n(p.tasa_apertura)} %`,
                        tip: `${p.titulo}\n${plural(p.impresiones, 'impresión', 'impresiones')}, ${plural(p.aperturas, 'apertura', 'aperturas')} (${n(p.tasa_apertura)} %)` }))),
                },
                {
                    titulo: d.etiquetas_a_revisar[0] ? `«${d.etiquetas_a_revisar[0].etiqueta}» aparece en ${plural(d.etiquetas_a_revisar[0].documentos, 'documento', 'documentos')} de los poco abiertos`
                        : 'No hay etiquetas que se repitan entre los documentos poco abiertos',
                    dibujar: el => barrasH(el, d.etiquetas_a_revisar.map(e => ({ etiqueta: e.etiqueta, valor: e.documentos, texto: n(e.documentos) }))),
                },
            ],
            tablas: [
                {
                    id: 'poco-abiertos', titulo: 'Se muestran mucho y casi no se abren', vacio: 'Ningún documento llega al mínimo de impresiones con pocas aperturas.',
                    filas: poco.map(p => ({ ...p, tipo: TIPO[p.origen], tasa: p.tasa_apertura })),
                    columnas: [{ clave: 'titulo', titulo: 'Título' }, { clave: 'tipo', titulo: 'Tipo' }, { clave: 'impresiones', titulo: 'Impresiones', num: true },
                        { clave: 'aperturas', titulo: 'Aperturas', num: true }, { clave: 'tasa', titulo: 'Tasa de apertura (%)', num: true }, { clave: 'etiquetas', titulo: 'Etiquetas' }],
                },
                {
                    id: 'nunca-mostrados', titulo: 'Nunca mostrados', vacio: 'Todos los documentos se han mostrado alguna vez.',
                    nota: totalNunca > nunca.length ? `Se muestran los primeros ${n(nunca.length)} de ${n(totalNunca)}.` : '',
                    filas: nunca.map(x => ({ ...x, tipo: TIPO[x.origen] })),
                    columnas: [{ clave: 'titulo', titulo: 'Título' }, { clave: 'tipo', titulo: 'Tipo' }, { clave: 'etiquetas', titulo: 'Etiquetas' }],
                },
            ],
        };
    }

    function vistaEdad(d) {
        const r = d.rangos;
        const aperturasTotal = r.reduce((a, x) => a + x.aperturas, 0);
        const lider = r.reduce((a, x) => (x.aperturas > (a?.aperturas ?? -1) ? x : a), null);
        const activo = r.reduce((a, x) => (x.cuentas ? (pct(x.cuentas_activas, x.cuentas) > (a ? pct(a.cuentas_activas, a.cuentas) : -1) ? x : a) : a), null);
        const SERIES_A = [{ clave: 'aperturas', nombre: 'Aperturas', clase: 'g-a' }, { clave: 'me_gusta', nombre: '«Me gusta»', clase: 'g-b' }];
        const SERIES_B = [{ clave: 'cuentas', nombre: 'Cuentas del rango', clase: 'g-a' }, { clave: 'cuentas_activas', nombre: 'Cuentas activas en el período', clase: 'g-b' }];
        const cat = x => ({ ...x, etiqueta: x.rango, pie: plural(x.cuentas, 'cuenta', 'cuentas') });
        const enTexto = l => l.map(x => `${x.concepto} (${n(x.eventos)})`);
        return {
            tarjetas: [
                { titulo: 'Rangos con datos', valor: r.length, detalle: `Solo se muestran rangos con al menos ${n(d.minimo_cuentas)} cuentas` },
                { titulo: 'Cuentas en esos rangos', valor: r.reduce((a, x) => a + x.cuentas, 0) },
                { titulo: 'Cuentas en rangos ocultos', valor: d.cuentas_sin_rango_visible, detalle: 'Tienen menos cuentas que el mínimo, o no se pudo calcular la edad' },
            ],
            avisos: r.length ? [] : [{ titulo: 'Todavía no hay datos por edad', texto: `Ningún rango tiene aún ${n(d.minimo_cuentas)} cuentas. La edad no se muestra hasta entonces para proteger la privacidad.` }],
            graficas: [
                {
                    titulo: aperturasTotal === 0 ? `Sin aperturas por rango de edad en los últimos ${dias} días`
                        : `El rango ${lider.rango} concentra el ${n(pct(lider.aperturas, aperturasTotal))} % de las aperturas`,
                    leyenda: { series: SERIES_A, tipo: 'barra' },
                    dibujar: el => barrasAgrupadas(el, r.map(cat), SERIES_A),
                },
                {
                    titulo: activo ? `En el rango ${activo.rango}, ${n(activo.cuentas_activas)} de ${n(activo.cuentas)} cuentas estuvieron activas (${n(pct(activo.cuentas_activas, activo.cuentas))} %)`
                        : 'Sin cuentas en los rangos visibles',
                    leyenda: { series: SERIES_B, tipo: 'barra' },
                    dibujar: el => barrasAgrupadas(el, r.map(cat), SERIES_B),
                },
            ],
            tablas: [{
                id: 'por-edad', titulo: 'Consumo por rango de edad', vacio: 'Ningún rango tiene todavía el mínimo de cuentas.',
                filas: r.map(x => ({ ...x, musculos_top: enTexto(x.musculos), temas_top: enTexto(x.temas) })),
                columnas: [{ clave: 'rango', titulo: 'Rango' }, { clave: 'cuentas', titulo: 'Cuentas', num: true }, { clave: 'cuentas_activas', titulo: 'Cuentas activas', num: true },
                    { clave: 'aperturas', titulo: 'Aperturas', num: true }, { clave: 'me_gusta', titulo: '«Me gusta»', num: true },
                    { clave: 'musculos_top', titulo: 'Músculos más consumidos' }, { clave: 'temas_top', titulo: 'Temas más consumidos' }],
            }],
        };
    }

    function vistaBusquedas(d) {
        const faltan = d.contenido_faltante.reduce((a, f) => a + f.busquedas, 0);
        const r0 = d.raices[0], f0 = d.contenido_faltante[0];
        return {
            tarjetas: [
                { titulo: 'Búsquedas', valor: d.total },
                { titulo: 'Sin resultados', valor: d.sin_resultados, detalle: `<strong>${esc(n(pct(d.sin_resultados, d.total)))} %</strong> del total` },
                { titulo: 'Sin relación en los árboles', valor: faltan, detalle: 'Contenido que la gente busca y no existe' },
            ],
            graficas: [
                {
                    titulo: r0 ? `«${r0.raiz}» es la raíz más buscada: aparece en ${plural(r0.busquedas, 'búsqueda', 'búsquedas')} de ${n(d.total)}` : `No hubo búsquedas en los últimos ${dias} días`,
                    nota: r0 ? 'Raíces de las palabras, no el texto que escribió cada persona.' : '',
                    dibujar: el => barrasH(el, d.raices.map(x => ({ etiqueta: x.raiz, valor: x.busquedas, texto: n(x.busquedas) }))),
                },
                {
                    titulo: f0 ? `${plural(faltan, 'búsqueda no encontró', 'búsquedas no encontraron')} contenido relacionado; la más repetida es «${f0.raices}»` : 'Todas las búsquedas encontraron algo relacionado',
                    dibujar: el => barrasH(el, d.contenido_faltante.map(x => ({ etiqueta: x.raices, valor: x.busquedas, texto: n(x.busquedas),
                        tip: `${x.raices}\n${VIA[x.via] ?? x.via}\n${plural(x.busquedas, 'búsqueda', 'búsquedas')}` }))),
                },
            ],
            tablas: [
                { id: 'raices', titulo: 'Raíces más buscadas', vacio: 'No hubo búsquedas en este período.', filas: d.raices,
                    columnas: [{ clave: 'raiz', titulo: 'Raíz' }, { clave: 'busquedas', titulo: 'Búsquedas', num: true }] },
                { id: 'contenido-faltante', titulo: 'Búsquedas sin relación (contenido que falta)', vacio: 'Todas las búsquedas encontraron algo relacionado.',
                    filas: d.contenido_faltante.map(x => ({ ...x, via_texto: VIA[x.via] ?? x.via })),
                    columnas: [{ clave: 'raices', titulo: 'Raíces buscadas' }, { clave: 'via_texto', titulo: 'Qué pasó' }, { clave: 'busquedas', titulo: 'Búsquedas', num: true }, { clave: 'sin_resultados', titulo: 'Sin resultados', num: true }] },
                { id: 'por-via', titulo: 'Búsquedas por tipo de resultado', vacio: 'No hubo búsquedas en este período.',
                    filas: d.por_via.map(x => ({ via_texto: VIA[x.via] ?? x.via, busquedas: x.busquedas })),
                    columnas: [{ clave: 'via_texto', titulo: 'Tipo de resultado' }, { clave: 'busquedas', titulo: 'Búsquedas', num: true }] },
            ],
        };
    }

    function vistaCobertura(d) {
        const senal = x => [x.pocos_documentos ? 'Pocos documentos' : null, x.poca_interaccion ? 'Poca interacción' : null].filter(Boolean).join(' · ') || 'Sin alerta';
        const escaso = l => l.reduce((a, x) => (!a || x.documentos < a.documentos ? x : a), null);
        const grafica = (l, singular) => {
            const e = escaso(l);
            const ordenado = [...l].sort((a, b) => b.documentos - a.documentos || a.concepto.localeCompare(b.concepto, 'es'));
            return {
                titulo: e ? `«${e.concepto}» tiene solo ${plural(e.documentos, 'documento', 'documentos')}: es donde más falta contenido` : `Sin ${singular} para comparar`,
                nota: 'Documentos por grupo, con las interacciones del período.',
                dibujar: el => barrasH(el, ordenado.map(x => ({ etiqueta: x.concepto, valor: x.documentos, texto: `${n(x.documentos)} · ${n(x.interacciones)} inter.`,
                    tip: `${x.concepto}\n${plural(x.documentos, 'documento', 'documentos')}\n${plural(x.interacciones, 'interacción', 'interacciones')} en el período\n${senal(x)}` }))),
            };
        };
        const tabla = (id, titulo, l, nombreCol) => ({
            id, titulo, vacio: 'Sin datos.', filas: l.map(x => ({ ...x, senal: senal(x) })),
            columnas: [{ clave: 'concepto', titulo: nombreCol }, { clave: 'documentos', titulo: 'Documentos', num: true }, { clave: 'interacciones', titulo: 'Interacciones', num: true }, { clave: 'senal', titulo: 'Señal' }],
        });
        const cuenta = (l, k) => l.filter(x => x[k]).length;
        return {
            tarjetas: [
                { titulo: 'Músculos con pocos documentos', valor: cuenta(d.musculos, 'pocos_documentos') },
                { titulo: 'Músculos con poca interacción', valor: cuenta(d.musculos, 'poca_interaccion') },
                { titulo: 'Temas con pocos documentos', valor: cuenta(d.temas, 'pocos_documentos') },
                { titulo: 'Temas con poca interacción', valor: cuenta(d.temas, 'poca_interaccion') },
            ],
            avisos: [{ titulo: 'Cómo se marca', texto: 'Un músculo o tema tiene «pocos documentos» cuando está por debajo de la mitad de la mediana, y «poca interacción» cuando no tiene ninguna o también está por debajo de la mitad de la mediana. Ahí conviene crear contenido.' }],
            graficas: [grafica(d.musculos, 'músculos'), grafica(d.temas, 'temas')],
            tablas: [tabla('musculos', 'Cobertura por músculo', d.musculos, 'Músculo'), tabla('temas', 'Cobertura por tema', d.temas, 'Tema')],
        };
    }

    const VISTAS = { resumen: vistaResumen, mas: vistaMas, menos: vistaMenos, edad: vistaEdad, busquedas: vistaBusquedas, cobertura: vistaCobertura };

    // ------------------------------------------------------------------ carga y navegación
    function limpiar(mensajeGraficas = '') {
        $('tarjetas').innerHTML = '';
        $('avisos').innerHTML = '';
        $('tablas').innerHTML = '';
        $('graficas').innerHTML = mensajeGraficas;
        redibujar = [];
        tablasActuales = {};
    }

    async function cargar() {
        const mia = ++peticion;
        limpiar('<div class="estado"><p>Cargando…</p></div>');
        let datos;
        try {
            datos = await pedir(seccion, dias);
        } catch (e) {
            if (mia !== peticion) return;
            if (e.codigo) {
                limpiar(`<div class="estado estado-error"><p>Tu sesión terminó por inactividad o ya no tienes acceso.</p><a class="btn" href="index.html">Iniciar sesión</a></div>`);
            } else {
                limpiar('<div class="estado estado-error"><p>No se pudo cargar esta sección. Revisa tu conexión e intenta de nuevo.</p><button type="button" class="btn" id="reintentar">Reintentar</button></div>');
                $('reintentar').addEventListener('click', cargar);
            }
            return;
        }
        if (mia !== peticion) return;                        // llegó tarde: ya se pidió otra sección o período
        const v = VISTAS[seccion](datos);
        $('tarjetas').innerHTML = v.tarjetas.map(tarjetaNumero).join('');
        $('avisos').innerHTML = (v.avisos || []).map(a => `<section class="aviso-panel"><h2>${esc(a.titulo)}</h2><p>${esc(a.texto)}</p></section>`).join('');
        pintarGraficas(v.graficas);
        $('tablas').innerHTML = v.tablas.map(tablaHTML).join('');
        $('actualizado').textContent = `Actualizado a las ${datos.generado_en.slice(11, 16)}`;
    }

    function pintarNavegacion() {
        $('navegacion').innerHTML = SECCIONES.map(s => `<button type="button" data-seccion="${s.id}"${s.id === seccion ? ' aria-current="page"' : ''}>${esc(s.nombre)}</button>`).join('');
        $('periodos').innerHTML = PERIODOS.map(p => `<button type="button" data-dias="${p}" aria-pressed="${p === dias}">${p} días</button>`).join('');
        const nombre = SECCIONES.find(s => s.id === seccion).nombre;
        $('tituloSeccion').textContent = nombre;
        document.title = `${nombre} · Administración · Buscador Gym`;
    }

    function ir(nuevaSeccion, nuevosDias, { enfocar = false } = {}) {
        seccion = nuevaSeccion;
        dias = nuevosDias;
        history.replaceState(null, '', `#${seccion}/${dias}`);
        pintarNavegacion();
        if (enfocar) $('tituloSeccion').focus();
        return cargar();
    }

    document.addEventListener('click', e => {
        const nav = e.target.closest('[data-seccion]');
        if (nav) return void ir(nav.dataset.seccion, dias, { enfocar: true });
        const per = e.target.closest('[data-dias]');
        if (per) return void ir(seccion, Number(per.dataset.dias));
        const csv = e.target.closest('[data-csv]');
        if (csv) descargarCSV(csv.dataset.csv);
    });

    // Tooltip: sigue al puntero y también aparece al enfocar con el teclado
    const tooltip = $('tooltip');
    function mostrarTip(el, x, y) {
        tooltip.textContent = el.dataset.tip;
        tooltip.style.whiteSpace = 'pre-line';
        tooltip.hidden = false;
        const ancho = tooltip.offsetWidth, alto = tooltip.offsetHeight;
        tooltip.style.left = `${Math.max(4, Math.min(innerWidth - ancho - 4, x + 14))}px`;
        tooltip.style.top = `${Math.max(4, Math.min(innerHeight - alto - 4, y + 14))}px`;
    }
    document.addEventListener('mousemove', e => {
        const el = e.target.closest ? e.target.closest('[data-tip]') : null;
        if (el) mostrarTip(el, e.clientX, e.clientY); else tooltip.hidden = true;
    });
    document.addEventListener('focusin', e => {
        const el = e.target.closest ? e.target.closest('[data-tip]') : null;
        if (el) { const r = el.getBoundingClientRect(); mostrarTip(el, r.left + r.width / 2, r.top); }
    });
    document.addEventListener('focusout', () => { tooltip.hidden = true; });
    document.addEventListener('keydown', e => { if (e.key === 'Escape') tooltip.hidden = true; });

    let temporizador;
    new ResizeObserver(() => {
        clearTimeout(temporizador);
        temporizador = setTimeout(() => redibujar.forEach(f => f()), 120);
    }).observe(document.body);

    // Para las pruebas: el CSV exactamente como se descargaría
    window.PanelAdmin = { csv: csvDe, seccion: () => seccion, dias: () => dias };

    const m = /^#(\w+)\/(\d+)$/.exec(location.hash);
    ir(m && SECCIONES.some(s => s.id === m[1]) ? m[1] : 'resumen', m && PERIODOS.includes(Number(m[2])) ? Number(m[2]) : 30);
})();
