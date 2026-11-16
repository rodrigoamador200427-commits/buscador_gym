// tests/interfaz.mjs — pruebas de la interfaz en un navegador real (Edge sin ventana).
//
// Lo lanza tests/test_interfaz.php, que prepara la BD de pruebas y el servidor:
//     node tests/interfaz.mjs http://127.0.0.1:<puerto>
//
// Sin dependencias: habla con Edge por el protocolo de DevTools usando el WebSocket que
// trae Node 22+. La ruta de Edge se puede cambiar con la variable EDGE_PATH.
// Sale con 0 si todo pasa, 1 si algo falla y 3 si no se pudo arrancar el navegador.
import { spawn } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const BASE = process.argv[2];
if (!BASE) { console.error('uso: node tests/interfaz.mjs <url base>'); process.exit(3); }

const EDGE = [process.env.EDGE_PATH,
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
    'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
    'C:/Program Files/Google/Chrome/Application/chrome.exe'].find(p => p && existsSync(p));
if (!EDGE) { console.error('ABORTADO: no se encontró Edge ni Chrome (define EDGE_PATH)'); process.exit(3); }

// ----------------------------------------------------------------------------- navegador
const perfilTmp = mkdtempSync(join(tmpdir(), 'bg-edge-'));
const edge = spawn(EDGE, ['--headless=new', '--remote-debugging-port=0', `--user-data-dir=${perfilTmp}`,
    '--no-first-run', '--no-default-browser-check', '--disable-gpu', '--window-size=1280,900', 'about:blank'],
    { stdio: ['ignore', 'ignore', 'pipe'] });

function cerrar(codigo) {
    try { edge.kill(); } catch {}
    setTimeout(() => { try { rmSync(perfilTmp, { recursive: true, force: true }); } catch {} process.exit(codigo); }, 500);
}

const puerto = await new Promise((ok, mal) => {
    let buf = '';
    const t = setTimeout(() => mal(new Error('Edge no abrió el puerto de depuración')), 20000);
    edge.stderr.on('data', d => {
        buf += d;
        const m = buf.match(/DevTools listening on ws:\/\/127\.0\.0\.1:(\d+)\//);
        if (m) { clearTimeout(t); ok(Number(m[1])); }
    });
    edge.on('exit', () => mal(new Error('Edge terminó antes de tiempo')));
}).catch(e => { console.error('ABORTADO: ' + e.message); cerrar(3); });

const paginas = await (await fetch(`http://127.0.0.1:${puerto}/json/list`)).json();
const pagina = paginas.find(p => p.type === 'page');
if (!pagina) { console.error('ABORTADO: Edge no abrió ninguna página'); cerrar(3); }
const ws = new WebSocket(pagina.webSocketDebuggerUrl);
await new Promise((ok, mal) => {
    ws.addEventListener('open', ok);
    ws.addEventListener('error', () => mal(new Error('no se pudo conectar con Edge')));
    setTimeout(() => mal(new Error('Edge no aceptó la conexión')), 20000);
}).catch(e => { console.error('ABORTADO: ' + e.message); cerrar(3); });

// Tope global: si algo se bloquea, la prueba termina con un fallo en vez de colgarse.
const TOPE_MS = 5 * 60 * 1000;
setTimeout(() => { console.log(`  FALLO la prueba no terminó en ${TOPE_MS / 60000} minutos`); cerrar(1); }, TOPE_MS).unref();
let seq = 0;
const pendientes = new Map();
ws.addEventListener('message', ev => {
    const m = JSON.parse(ev.data);
    if (m.id && pendientes.has(m.id)) { pendientes.get(m.id)(m); pendientes.delete(m.id); }
});
function cdp(method, params = {}) {
    return new Promise((ok, mal) => {
        const id = ++seq;
        const t = setTimeout(() => { pendientes.delete(id); mal(new Error(`${method}: Edge no respondió en 30 s`)); }, 30000);
        pendientes.set(id, m => { clearTimeout(t); m.error ? mal(new Error(`${method}: ${m.error.message}`)) : ok(m.result); });
        ws.send(JSON.stringify({ id, method, params }));
    });
}

/** Evalúa una expresión en la página y devuelve su valor (espera promesas). */
async function js(expresion) {
    const r = await cdp('Runtime.evaluate', { expression: expresion, awaitPromise: true, returnByValue: true });
    if (r.exceptionDetails) throw new Error('JS: ' + (r.exceptionDetails.exception?.description || r.exceptionDetails.text));
    return r.result.value;
}
async function esperar(expresion, ms = 30000) {
    const fin = Date.now() + ms;
    while (Date.now() < fin) {
        if (await js(`!!(${expresion})`)) return true;
        await new Promise(r => setTimeout(r, 100));
    }
    return false;
}
/** Como esperar(), pero si no ocurre a tiempo lanza un error que dice qué faltó. */
async function hasta(expresion, ms = 30000) {
    if (!await esperar(expresion, ms)) throw new Error('no ocurrió a tiempo: ' + expresion.slice(0, 120));
}
async function tecla(key, vk, text) {
    await cdp('Input.dispatchKeyEvent', { type: text ? 'keyDown' : 'rawKeyDown', key, code: key, windowsVirtualKeyCode: vk, nativeVirtualKeyCode: vk, text, unmodifiedText: text });
    await cdp('Input.dispatchKeyEvent', { type: 'keyUp', key, code: key, windowsVirtualKeyCode: vk, nativeVirtualKeyCode: vk });
}
const ENTER = () => tecla('Enter', 13, '\r');
const TAB = () => tecla('Tab', 9);
const ESCAPE = () => tecla('Escape', 27);
async function pantalla(ancho, alto, movil) {
    await cdp('Emulation.setDeviceMetricsOverride', { width: ancho, height: alto, deviceScaleFactor: 1, mobile: movil });
}

// Con CAPTURAS=<carpeta> guarda capturas de pantalla en los momentos clave (para revisar a ojo).
const CAPTURAS = process.env.CAPTURAS;
if (CAPTURAS) mkdirSync(CAPTURAS, { recursive: true });
async function captura(nombre) {
    if (!CAPTURAS) return;
    const r = await cdp('Page.captureScreenshot', { format: 'png' });
    writeFileSync(join(CAPTURAS, nombre + '.png'), Buffer.from(r.data, 'base64'));
}

// ----------------------------------------------------------------------------- informe
let total = 0, fallos = 0;
function comprobar(nombre, ok, detalle = '') {
    total++;
    if (!ok) fallos++;
    console.log((ok ? '  OK    ' : '  FALLO ') + nombre + (ok || detalle === '' ? '' : `  -> ${typeof detalle === 'string' ? detalle : JSON.stringify(detalle)}`));
}

// Funciones que se ejecutan DENTRO de la página
await cdp('Page.enable');
await cdp('Runtime.enable');
await cdp('Page.addScriptToEvaluateOnNewDocument', { source: `
    window.__t = {
        visible: sel => { const e = document.querySelector(sel); return !!e && !e.closest('[hidden]') && e.getClientRects().length > 0; },
        texto: () => document.body.innerText,
        llenar: (sel, valores) => { const f = document.querySelector(sel);
            for (const [k, v] of Object.entries(valores)) f.elements[k].value = v; f.requestSubmit(); },
        buscar: q => { const i = document.getElementById('searchInput'); i.value = q; i.form.requestSubmit(); },
        tarjetas: () => [...document.querySelectorAll('#resultsGrid .tarjeta')],
        // Elementos visibles que se salen del ancho de la ventana
        desbordes: () => { const w = document.documentElement.clientWidth;
            return [...document.querySelectorAll('body *')].filter(e => { const r = e.getBoundingClientRect();
                return r.width > 0 && r.height > 0 && (r.right > w + 1 || r.left < -1) && getComputedStyle(e).position !== 'fixed'; }).slice(0, 5).map(e => e.tagName + '.' + e.className); },
    };` });

const EMOJI = /\p{Extended_Pictographic}/u;
const RELLENO = /cold\s*start|calculando|modo descubrimiento|raz[oó]n algor[ií]tmica|salto sem[aá]ntico|tf-idf|coseno|vectorial|algoritmo/i;
async function comprobarTexto(donde) {
    const t = await js('__t.texto()');
    comprobar(`${donde}: sin emojis`, !EMOJI.test(t), t.match(EMOJI)?.[0]);
    comprobar(`${donde}: sin vocabulario técnico ni relleno`, !RELLENO.test(t), t.match(RELLENO)?.[0]);
}

try {
    // ========================================================================= acceso y perfil
    console.log('\n[Acceso y perfil]');
    await pantalla(1280, 900, false);
    await cdp('Page.navigate', { url: BASE + '/index.html' });
    comprobar('sin sesión se muestra el acceso', await esperar(`__t.visible('#formLogin')`));
    comprobar('sin sesión no hay búsqueda ni menú de perfil', await js(`!__t.visible('#searchInput') && !__t.visible('#menuPerfil')`));
    await comprobarTexto('acceso');
    await captura('1-acceso');
    await js(`document.getElementById('tabRegistro').click();
        __t.llenar('#formRegistro', { nombre_completo: 'Prueba Interfaz', fecha_nacimiento: '2000-01-01', correo: 'ui@prueba.test', contrasena: 'InterfazUI12345' })`);
    comprobar('tras crear la cuenta se pide elegir un perfil', await esperar(`__t.visible('#formPerfil')`));
    await comprobarTexto('perfiles');
    await js(`__t.llenar('#formPerfil', { nombre: 'Pecho' })`);
    await hasta(`document.querySelector('[data-elegir]')`);
    await js(`document.querySelector('[data-elegir]').click()`);
    comprobar('al elegir el perfil aparece la aplicación', await esperar(`__t.visible('#searchInput') && __t.visible('#menuPerfil')`));
    comprobar('el menú muestra el perfil activo', await js(`document.getElementById('nombrePerfil').textContent`) === 'Pecho');
    comprobar('la barra superior es fija', await js(`getComputedStyle(document.querySelector('.barra')).position`) === 'sticky');
    comprobar('la hoja de estilos es un archivo aparte y no hay estilos en línea en <head>',
        await js(`!!document.querySelector('link[rel=stylesheet][href="assets/estilos.css"]') && !document.querySelector('head style')`));

    // ========================================================================= perfil sin "me gusta"
    console.log('\n[Perfil sin «me gusta»]');
    await hasta(`document.querySelector('#resultsGrid .estado [data-buscar]')`);
    const vacio = await js(`({ grafica: document.getElementById('grafica').innerText, barras: document.querySelectorAll('.barra-fila').length,
        estado: document.querySelector('#resultsGrid .estado')?.innerText })`);
    comprobar('sin «me gusta» no hay gráfica, solo una frase que dice qué hacer',
        vacio.barras === 0 && /me gusta/i.test(vacio.grafica) && vacio.grafica.length < 120, vacio);
    comprobar('el estado vacío dice qué hacer', /me gusta/i.test(vacio.estado || ''), vacio.estado);
    comprobar('título de la gráfica', await js(`document.getElementById('tituloGrafica').textContent`) === 'Lo que más pesa en tus recomendaciones');
    await comprobarTexto('sin «me gusta»');
    await captura('2-sin-me-gusta');

    // ========================================================================= tarjetas
    console.log('\n[Tarjetas]');
    await js(`__t.buscar('calentamiento')`);
    comprobar('la búsqueda muestra tarjetas', await esperar(`__t.tarjetas().length > 0`));
    const t = await js(`(() => { const c = __t.tarjetas(); return {
        n: c.length,
        alturas: [...new Set(c.map(e => Math.round(e.getBoundingClientRect().height)))],
        estructura: c.every(e => e.querySelector('.tipo') && e.querySelector('.tarjeta-titulo [data-abrir]') && e.querySelector('.tarjeta-resumen')
            && e.querySelectorAll('.tarjeta-meta dt').length === 3 && e.querySelector('ul.etiquetas') && e.querySelector('[data-gusta]')),
        resumenLineas: Math.max(...c.map(e => { const p = e.querySelector('.tarjeta-resumen'); return p.getBoundingClientRect().height / parseFloat(getComputedStyle(p).lineHeight); })),
        meta: [...c.find(e => e.dataset.doc === 'ejercicios:101').querySelectorAll('.tarjeta-meta dd')].map(d => d.textContent.trim()),
        conteo: document.getElementById('statsBar').textContent,
    }; })()`);
    comprobar('12 resultados (ejercicios y artículos)', t.n === 12 && t.conteo === '12 resultados', t);
    comprobar('todas las tarjetas tienen la misma altura', t.alturas.length === 1, t.alturas);
    comprobar('todas tienen la misma estructura (tipo, título, resumen, 3 metadatos, etiquetas, me gusta)', t.estructura);
    comprobar('el resumen ocupa 3 líneas como máximo', t.resumenLineas <= 3.05, t.resumenLineas);
    comprobar('metadatos del ejercicio 101: Pecho, Barra, Principiante', JSON.stringify(t.meta) === '["Pecho","Barra","Principiante"]', t.meta);
    await comprobarTexto('resultados');
    await captura('3-resultados');

    // ========================================================================= filtros
    console.log('\n[Filtro por etiqueta]');
    await js(`[...document.querySelectorAll('[data-doc="articulos:302"] .etiquetas [data-etiqueta]')].find(b => b.textContent.trim() === 'Pierna').click()`);
    let f = await js(`({ n: __t.tarjetas().length, docs: __t.tarjetas().map(e => e.dataset.doc), conteo: document.getElementById('statsBar').textContent,
        activa: document.querySelector('#opcionesEtiquetas [aria-pressed="true"]')?.textContent.trim(), quitar: __t.visible('#quitarFiltros') })`);
    comprobar('clic en una etiqueta de la tarjeta reduce los resultados', f.n > 0 && f.n < 12, f);
    comprobar('solo quedan documentos con esa etiqueta («Pierna»: el artículo 302)', JSON.stringify(f.docs) === '["articulos:302"]', f.docs);
    comprobar('el conteo dice cuántos quedan de cuántos', f.conteo === '1 de 12 resultados', f.conteo);
    comprobar('la etiqueta queda marcada en el panel y aparece «Quitar filtros»', /^Pierna/.test(f.activa || '') && f.quitar, f);
    await js(`document.getElementById('quitarFiltros').click()`);
    comprobar('«Quitar filtros» devuelve todos los resultados', await js(`__t.tarjetas().length`) === 12);

    await js(`[...document.querySelectorAll('#opcionesEtiquetas [data-etiqueta]')].find(b => b.textContent.trim().startsWith('Cuádriceps')).click()`);
    f = await js(`({ n: __t.tarjetas().length, ok: __t.tarjetas().every(e => e.querySelector('.tarjeta-meta dd').textContent.includes('Cuádriceps')) })`);
    comprobar('etiqueta del panel («Cuádriceps»): quedan solo los 5 ejercicios de ese músculo', f.n === 5 && f.ok, f);
    await js(`[...document.querySelectorAll('[data-filtro="nivel"]')].find(c => c.parentElement.textContent.includes('Intermedio')).click()`);
    comprobar('sumar el filtro de nivel «Intermedio» deja 1', await js(`__t.tarjetas().map(e => e.dataset.doc).join()`) === 'ejercicios:204');
    await js(`[...document.querySelectorAll('[data-filtro="equipamiento"]')].find(c => c.parentElement.textContent.includes('Polea')).click()`);
    f = await js(`({ n: __t.tarjetas().length, estado: document.querySelector('#resultsGrid .estado')?.innerText })`);
    comprobar('si ningún resultado cumple los filtros, se dice y se ofrece quitarlos', f.n === 0 && /Quitar filtros/.test(f.estado || ''), f);
    await js(`document.querySelector('[data-quitar-filtros]').click()`);
    await js(`document.querySelector('[data-tipo="ejercicios"]').click()`);
    comprobar('filtro de tipo: solo artículos', await js(`__t.tarjetas().map(e => e.dataset.doc).sort().join()`) === 'articulos:301,articulos:302');
    await js(`document.getElementById('quitarFiltros').click()`);

    // ========================================================================= detalle con teclado
    console.log('\n[Detalle: abrir y cerrar con teclado]');
    await js(`document.querySelector('[data-doc="ejercicios:101"] [data-abrir]').focus()`);
    await ENTER();
    comprobar('Enter sobre el título abre el detalle', await esperar(`document.getElementById('detalle').open`));
    await hasta(`document.getElementById('detalleGusta')`);
    const d = await js(`(() => { const c = document.getElementById('detalleCuerpo'); return {
        modal: document.getElementById('detalle').matches(':modal'),
        titulo: document.getElementById('detalleTitulo').textContent,
        texto: c.querySelector('.detalle-texto').textContent,
        ruta: [...c.querySelectorAll('.ruta li')].map(l => l.textContent),
        etiquetas: [...c.querySelectorAll('[data-etiqueta]')].map(b => b.textContent.trim()),
        relacionados: [...c.querySelectorAll('[data-relacionado]')].map(b => b.dataset.relacionado),
        gusta: document.getElementById('detalleGusta').textContent,
    }; })()`);
    comprobar('es una ventana modal (<dialog> con showModal)', d.modal);
    comprobar('muestra el texto completo', d.titulo === 'Press de banca plano' && d.texto === 'Press de pecho en banco plano', d);
    comprobar('muestra la ruta en el árbol', JSON.stringify(d.ruta) === '["Cuerpo humano","Tren superior","Pecho","Barra"]', d.ruta);
    comprobar('muestra todas las etiquetas', JSON.stringify(d.etiquetas) === '["Pecho","Barra","Principiante","Fuerza"]', d.etiquetas);
    comprobar('muestra hasta 4 relacionados, sin el propio documento',
        d.relacionados.length > 0 && d.relacionados.length <= 4 && !d.relacionados.includes('ejercicios:101'), d.relacionados);
    comprobar('tiene botón de «me gusta»', d.gusta === 'Me gusta', d.gusta);
    await captura('4-detalle');

    let dentro = await js(`document.getElementById('detalle').contains(document.activeElement)`);
    const focos = new Set();
    for (let i = 0; i < 14; i++) {
        await TAB();
        const r = await js(`({ dentro: document.getElementById('detalle').contains(document.activeElement),
            que: document.activeElement.id || document.activeElement.className || document.activeElement.tagName })`);
        dentro = dentro && r.dentro;
        focos.add(r.que);
    }
    comprobar('el foco no sale del detalle al tabular (14 veces)', dentro, [...focos]);
    comprobar('con Tab se llega a «Cerrar», «Me gusta», las etiquetas y los relacionados',
        ['detalleCerrar', 'detalleGusta', 'etiqueta', 'relacionado'].every(x => focos.has(x)), [...focos]);
    await ESCAPE();
    comprobar('Escape cierra el detalle', await esperar(`!document.getElementById('detalle').open`));
    comprobar('el foco vuelve a la tarjeta', await js(`document.activeElement === document.querySelector('[data-doc="ejercicios:101"] [data-abrir]')`),
        await js(`document.activeElement.outerHTML.slice(0, 80)`));

    await ENTER();
    await hasta(`document.getElementById('detalle').open && document.getElementById('detalleGusta')`);
    await js(`document.getElementById('detalleCerrar').focus()`);
    await ENTER();
    comprobar('el botón «Cerrar» cierra el detalle con Enter', await esperar(`!document.getElementById('detalle').open`));

    // Clic en la tarjeta (no solo en el título), saltar a un relacionado y filtrar desde el detalle
    await js(`document.querySelector('[data-doc="ejercicios:101"] .tarjeta-resumen').click()`);
    await hasta(`document.querySelector('[data-relacionado]')`);
    await js(`document.querySelector('[data-relacionado="ejercicios:102"]').click()`);
    comprobar('un relacionado abre su propio detalle', await esperar(`document.getElementById('detalleTitulo').textContent === 'Press de banca inclinado' && document.getElementById('detalleGusta')`));
    await js(`[...document.querySelectorAll('#detalleCuerpo [data-etiqueta]')].find(b => b.textContent.trim() === 'Barra').click()`);
    f = await js(`({ abierto: document.getElementById('detalle').open, docs: __t.tarjetas().map(e => e.dataset.doc).sort().join() })`);
    comprobar('clic en una etiqueta del detalle lo cierra y filtra los resultados',
        !f.abierto && f.docs === 'ejercicios:101,ejercicios:102,ejercicios:201,ejercicios:202', f);
    await js(`document.getElementById('quitarFiltros').click()`);

    // ========================================================================= me gusta y gráfica
    console.log('\n[«Me gusta» y gráfica]');
    await js(`document.querySelector('[data-doc="ejercicios:101"] [data-abrir]').click()`);
    await hasta(`document.getElementById('detalleGusta')`);
    await js(`document.getElementById('detalleGusta').click()`);
    comprobar('«me gusta» desde el detalle: el botón y el corazón de la tarjeta quedan marcados',
        await esperar(`document.getElementById('detalleGusta')?.getAttribute('aria-pressed') === 'true'
            && document.getElementById('detalleGusta').textContent.startsWith('Quitar')
            && document.querySelector('[data-doc="ejercicios:101"] [data-gusta]').getAttribute('aria-pressed') === 'true'`));
    await js(`document.getElementById('detalleCerrar').click()`);
    await js(`document.querySelector('[data-doc="ejercicios:102"] [data-gusta]').click()`);
    comprobar('con «me gusta» aparece la gráfica', await esperar(`document.querySelectorAll('.barra-fila').length > 0`, 30000));
    await new Promise(r => setTimeout(r, 1500));     // segunda actualización (el segundo «me gusta»)
    const g = await js(`(() => { const filas = [...document.querySelectorAll('.barra-fila')]; return {
        n: filas.length,
        valores: filas.map(x => Number(x.querySelector('.valor').textContent)),
        anchos: filas.map(x => x.querySelector('.relleno').getBoundingClientRect().width),
        colores: [...new Set(filas.map(x => getComputedStyle(x.querySelector('.relleno')).backgroundColor))],
        palabras: filas.map(x => x.querySelector('.termino').textContent),
        lienzo: !!document.querySelector('canvas'),
    }; })()`);
    comprobar('hasta 8 barras horizontales, sin <canvas>', g.n > 0 && g.n <= 8 && !g.lienzo, g);
    comprobar('ordenadas de mayor a menor, con el valor al lado',
        g.valores.every((v, i) => v > 0 && (i === 0 || v <= g.valores[i - 1])) && g.anchos.every((a, i) => i === 0 || a <= g.anchos[i - 1] + 0.5), g);
    comprobar('un solo color', g.colores.length === 1, g.colores);
    await captura('5-grafica');
    comprobar('muestra palabras completas («pecho»), no raíces («pech»)', g.palabras.includes('pecho') && !g.palabras.includes('pech'), g.palabras);

    // ========================================================================= HTML en el contenido
    console.log('\n[Contenido con HTML: no se interpreta]');
    await js(`__t.buscar('xsstest')`);
    comprobar('aparece el documento con HTML en título, texto y etiquetas', await esperar(`document.querySelector('[data-doc="articulos:390"]')`));
    const sinInyeccion = `({ marca: window.__xss, img: document.querySelectorAll('img').length, script: document.querySelectorAll('body script').length,
        nodo: !!document.querySelector('#xss-tag, #xss-titulo, b.xss'), })`;
    let x = await js(sinInyeccion);
    const xt = await js(`document.querySelector('[data-doc="articulos:390"] [data-abrir]').textContent`);
    comprobar('tarjeta: el HTML se muestra como texto', xt.includes('<img') && x.marca === undefined && x.img === 0 && !x.nodo && x.script === 1, { xt, x });
    await js(`document.querySelector('[data-doc="articulos:390"] [data-abrir]').click()`);
    await hasta(`document.getElementById('detalleGusta')`);
    x = await js(sinInyeccion);
    const xd = await js(`({ titulo: document.getElementById('detalleTitulo').textContent, texto: document.querySelector('.detalle-texto').textContent,
        etiquetas: [...document.querySelectorAll('#detalleCuerpo [data-etiqueta]')].map(b => b.textContent.trim()) })`);
    comprobar('detalle: título, texto y etiquetas con HTML se muestran como texto',
        xd.titulo.includes('<img') && xd.texto.includes('<script>') && xd.etiquetas.some(e => e.includes('<i')) && x.marca === undefined && x.img === 0 && !x.nodo && x.script === 1,
        { xd, x });
    await js(`document.getElementById('detalleCerrar').click()`);

    // ========================================================================= árboles
    console.log('\n[Explorar por árboles]');
    await js(`document.querySelector('[data-vista="vistaArboles"]').click()`);
    comprobar('la pestaña muestra los menús de músculo y tema', await esperar(`__t.visible('#menuA') && document.querySelectorAll('#menuA option').length > 0`));
    await js(`(() => { const a = document.getElementById('menuA'); a.value = [...a.options].find(o => o.textContent.startsWith('Pecho')).value; a.dispatchEvent(new Event('change', { bubbles: true }));
        const b = document.getElementById('menuB'); const con = [...b.options].find(o => !o.textContent.includes('(0 ')); if (con) b.value = con.value;
        document.getElementById('formAB').requestSubmit(); })()`);
    comprobar('muestra tarjetas o dice que no hay artículos', await esperar(`document.querySelector('#resultadoAB .tarjeta, #resultadoAB .estado p')`));
    await comprobarTexto('árboles');
    await captura('6-arboles');

    // ========================================================================= 375 px
    console.log('\n[Teléfono: 375 px de ancho]');
    await pantalla(375, 700, true);
    await cdp('Page.reload');
    await hasta(`window.__t && __t.visible('#searchInput') && document.querySelector('#resultsGrid .tarjeta')`);
    const m = async donde => {
        const r = await js(`({ ancho: document.documentElement.scrollWidth, ventana: document.documentElement.clientWidth, fuera: __t.desbordes() })`);
        comprobar(`${donde}: sin desplazamiento horizontal`, r.ancho <= r.ventana && r.ventana <= 375 && r.fuera.length === 0, r);
    };
    await m('recomendaciones');
    await captura('7-movil-recomendaciones');
    comprobar('el panel de filtros empieza plegado y se puede abrir',
        await js(`!document.getElementById('lateral').open && __t.visible('#lateral > summary')`)
        && await js(`(document.querySelector('#lateral > summary').click(), document.getElementById('lateral').open && __t.visible('#grafica'))`));
    await m('con los filtros abiertos');
    await captura('8-movil-filtros');
    await js(`document.querySelector('#lateral > summary').click(); __t.buscar('calentamiento')`);
    await hasta(`__t.tarjetas().length === 12`);
    await m('resultados de búsqueda');
    await captura('9-movil-resultados');
    comprobar('las tarjetas van en una columna y caben en la pantalla',
        await js(`__t.tarjetas().every(e => { const r = e.getBoundingClientRect(); return r.left >= 0 && r.right <= 375 && r.width > 300; })`));
    comprobar('la búsqueda y el menú del perfil siguen visibles', await js(`__t.visible('#searchInput') && __t.visible('#menuPerfil')`));
    await js(`document.querySelector('[data-doc="ejercicios:103"] [data-abrir]').click()`);
    await hasta(`document.getElementById('detalleGusta')`);
    const dm = await js(`(() => { const r = document.getElementById('detalle').getBoundingClientRect(); return { left: r.left, right: r.right,
        cerrar: __t.visible('#detalleCerrar'), fuera: [...document.querySelectorAll('#detalle *')].filter(e => e.getBoundingClientRect().right > 376).length }; })()`);
    comprobar('el detalle cabe en 375 px y «Cerrar» está a la vista', dm.left >= 0 && dm.right <= 375.5 && dm.cerrar && dm.fuera === 0, dm);
    await captura('10-movil-detalle');
    await ESCAPE();
    comprobar('Escape también cierra el detalle en teléfono', await esperar(`!document.getElementById('detalle').open`));
    await js(`document.querySelector('[data-vista="vistaArboles"]').click()`);
    await m('explorar por árboles');

    // ========================================================================= cerrar sesión
    console.log('\n[Menú del perfil]');
    await js(`document.querySelector('#menuPerfil summary').click()`);
    comprobar('el menú ofrece cambiar de perfil y cerrar sesión',
        await js(`__t.visible('#btnCambiarPerfil') && __t.visible('#menuPerfil [data-accion="logout"]') && document.getElementById('correoCuenta').textContent === 'ui@prueba.test'`));
    await js(`document.querySelector('#menuPerfil [data-accion="logout"]').click()`);
    comprobar('cerrar sesión vuelve al acceso', await esperar(`__t.visible('#formLogin') && !__t.visible('#searchInput')`));
    await m('acceso');
} catch (e) {
    comprobar('la prueba terminó sin errores', false, e.message);
}

console.log(`\n${total} comprobaciones de interfaz, ${fallos} fallos`);
cerrar(fallos === 0 ? 0 : 1);
