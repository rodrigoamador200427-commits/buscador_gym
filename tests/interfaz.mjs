// tests/interfaz.mjs — pruebas de la interfaz en un navegador real (Edge sin ventana).
//
// Lo lanza tests/test_interfaz.php, que prepara la BD de pruebas y el servidor:
//     node tests/interfaz.mjs http://127.0.0.1:<puerto>
//
// El navegador se maneja con tests/navegador.mjs (sin dependencias; EDGE_PATH cambia la ruta).
// Con CAPTURAS=<carpeta> guarda capturas de pantalla en los momentos clave.
// Sale con 0 si todo pasa, 1 si algo falla y 3 si no se pudo arrancar el navegador.
import { abrirNavegador, crearInforme } from './navegador.mjs';

const BASE = process.argv[2];
if (!BASE) { console.error('uso: node tests/interfaz.mjs <url base>'); process.exit(3); }

const { cdp, js, esperar, hasta, pantalla, captura, tema, cerrar, ENTER, TAB, ESCAPE, ABAJO, ESCRIBIR } = await abrirNavegador();
const informe = crearInforme();
const comprobar = informe.comprobar;

// Funciones que se ejecutan DENTRO de la página
await cdp('Page.addScriptToEvaluateOnNewDocument', { source: `
    window.__t = {
        visible: sel => { const e = document.querySelector(sel); return !!e && !e.closest('[hidden]') && e.getClientRects().length > 0; },
        texto: () => document.body.innerText,
        llenar: (sel, valores) => { const f = document.querySelector(sel);
            for (const [k, v] of Object.entries(valores)) f.elements[k].value = v; f.requestSubmit(); },
        buscar: q => { const i = document.getElementById('searchInput'); i.value = q; i.form.requestSubmit(); },
        tarjetas: () => [...document.querySelectorAll('#resultsGrid .tarjeta')],
        rgb: c => c.match(/[\\d.]+/g).map(Number),
        lum: c => { const [r, g, b] = c.slice(0, 3).map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }); return 0.2126 * r + 0.7152 * g + 0.0722 * b; },
        // Contraste WCAG del texto de un elemento con su fondo real (el primer antepasado con fondo opaco)
        contraste: sel => { const e = document.querySelector(sel); if (!e) return 0;
            let f = e, fondo = null;
            while (f && !fondo) { const c = __t.rgb(getComputedStyle(f).backgroundColor); if (c.length < 4 || c[3] > 0) fondo = c; f = f.parentElement; }
            const [x, y] = [__t.lum(__t.rgb(getComputedStyle(e).color)), __t.lum(fondo || [255, 255, 255])].sort((p, q) => q - p);
            return Math.round((x + 0.05) / (y + 0.05) * 100) / 100; },
        variable: v => { const d = document.createElement('div'); d.style.color = 'var(' + v + ')'; document.body.appendChild(d);
            const c = getComputedStyle(d).color; d.remove(); return c; },
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

    // ========================================================================= ilustraciones en las tarjetas
    console.log('\n[Ilustraciones en las tarjetas]');
    const il = await js(`(() => { const c = __t.tarjetas(); const de = k => c.find(e => e.dataset.doc === k).querySelector('.tarjeta-imagen svg');
        const cajas = c.map(e => e.querySelector('.tarjeta-imagen').getBoundingClientRect());
        return {
            todas: c.every(e => { const s = e.querySelector('.tarjeta-imagen > svg.ilustracion'); return s && s.getAttribute('role') === 'img' && s.querySelector('title').textContent.trim().length > 5; }),
            primera: c.every(e => e.firstElementChild.classList.contains('tarjeta-imagen')),
            proporciones: [...new Set(cajas.map(b => (b.width / b.height).toFixed(2)))],
            tamanos: [...new Set(cajas.map(b => Math.round(b.width) + 'x' + Math.round(b.height)))],
            e101: { dato: de('ejercicios:101').dataset.ilustracion, titulo: de('ejercicios:101').querySelector('title').textContent, clase: de('ejercicios:101').getAttribute('class') },
            e201: { dato: de('ejercicios:201').dataset.ilustracion, clase: de('ejercicios:201').getAttribute('class') },
            a301: { dato: de('articulos:301').dataset.ilustracion, titulo: de('articulos:301').querySelector('title').textContent },
            externos: performance.getEntriesByType('resource').map(r => r.name).filter(u => !u.startsWith(location.origin)),
        }; })()`);
    comprobar('cada tarjeta empieza con su ilustración, con role="img" y un título', il.todas && il.primera, il);
    comprobar('el recuadro de la imagen tiene proporción fija 16:9 y mide lo mismo en todas las tarjetas',
        JSON.stringify(il.proporciones) === '["1.78"]' && il.tamanos.length === 1, { proporciones: il.proporciones, tamanos: il.tamanos });
    comprobar('ejercicio de pecho: «Músculo trabajado: pecho», medio cuerpo superior',
        il.e101.dato === 'musculo:1' && il.e101.titulo === 'Músculo trabajado: pecho' && il.e101.clase.includes('ilustracion-superior'), il.e101);
    comprobar('ejercicio de cuádriceps: medio cuerpo inferior', il.e201.dato === 'musculo:6' && il.e201.clase.includes('ilustracion-inferior'), il.e201);
    comprobar('artículo: pictograma de su tema («Tema del artículo: fuerza»)', il.a301.dato === 'tema:fuerza' && il.a301.titulo === 'Tema del artículo: fuerza', il.a301);
    comprobar('la página no carga nada de otro sitio', il.externos.length === 0, il.externos);

    // Una foto de otra proporción en el mismo recuadro: nada más debe moverse
    const foto = await js(`(async () => { const t = document.querySelector('[data-doc="ejercicios:101"]'), caja = t.querySelector('.tarjeta-imagen');
        const medir = () => ({ tarjeta: Math.round(t.getBoundingClientRect().height),
            caja: [Math.round(caja.getBoundingClientRect().width), Math.round(caja.getBoundingClientRect().height)],
            titulo: Math.round(t.querySelector('.tarjeta-titulo').getBoundingClientRect().top - t.getBoundingClientRect().top),
            vecina: Math.round(document.querySelector('[data-doc="ejercicios:102"]').getBoundingClientRect().height) });
        const antes = medir(), original = caja.innerHTML;
        // la "foto" se fabrica aquí mismo (vertical, 600 x 1500): no depende de ningún archivo
        const lienzo = document.createElement('canvas'); lienzo.width = 600; lienzo.height = 1500; lienzo.getContext('2d').fillRect(0, 0, 600, 1500);
        const img = new Image(); img.alt = 'Foto de prueba'; img.src = lienzo.toDataURL('image/png'); await img.decode();
        caja.replaceChildren(img);
        const despues = medir(), imagen = [Math.round(img.getBoundingClientRect().width), Math.round(img.getBoundingClientRect().height)];
        caja.innerHTML = original;
        return { antes, despues, imagen, natural: [img.naturalWidth, img.naturalHeight] }; })()`);
    comprobar('sustituir la ilustración por una foto vertical de 600 x 1500 no mueve el diseño',
        JSON.stringify(foto.antes) === JSON.stringify(foto.despues) && foto.imagen[0] === foto.antes.caja[0] && foto.imagen[1] === foto.antes.caja[1], foto);

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
        ruta: [...c.querySelector('.ruta').querySelectorAll('li')].map(l => l.textContent),
        rutas: [...c.querySelectorAll('.detalle-info h3')].filter(h => h.textContent.startsWith('Ubicación en')).map(h => h.textContent),
        etiquetas: [...c.querySelectorAll('[data-etiqueta]')].map(b => b.textContent.trim()),
        relacionados: [...c.querySelectorAll('[data-relacionado]')].map(b => b.dataset.relacionado),
        gusta: document.getElementById('detalleGusta').textContent,
    }; })()`);
    comprobar('es una ventana modal (<dialog> con showModal)', d.modal);
    comprobar('muestra el texto completo', d.titulo === 'Press de banca plano' && d.texto === 'Press de pecho en banco plano', d);
    comprobar('muestra la ruta en el árbol', JSON.stringify(d.ruta) === '["Cuerpo humano","Tren superior","Pecho","Barra"]', d.ruta);
    comprobar('muestra una ubicación por árbol y marca la de patrón como aproximada',
        JSON.stringify(d.rutas) === '["Ubicación en Anatomía","Ubicación en Equipamiento","Ubicación en Nivel","Ubicación en Patrón de movimiento (aproximado)"]', d.rutas);
    comprobar('muestra todas las etiquetas', JSON.stringify(d.etiquetas) === '["Pecho","Barra","Principiante","Fuerza"]', d.etiquetas);
    comprobar('muestra hasta 4 relacionados, sin el propio documento',
        d.relacionados.length > 0 && d.relacionados.length <= 4 && !d.relacionados.includes('ejercicios:101'), d.relacionados);
    comprobar('tiene botón de «me gusta»', d.gusta === 'Me gusta', d.gusta);
    const di = await js(`(() => { const s = document.querySelector('#detalleCuerpo .detalle-imagen svg.ilustracion'), b = s.getBoundingClientRect();
        const t = document.querySelector('[data-doc="ejercicios:101"] .tarjeta-imagen svg').getBoundingClientRect();
        return { dato: s.dataset.ilustracion, titulo: s.querySelector('title').textContent, caja: s.getAttribute('viewBox'), alto: Math.round(b.height),
                 escala: b.height / 400, escalaTarjeta: t.height / 242 }; })()`);
    comprobar('muestra la ilustración grande, con el cuerpo completo y su título',
        di.dato === 'musculo:1' && di.titulo === 'Músculo trabajado: pecho' && di.caja === '0 0 200 400' && di.alto >= 350, di);
    comprobar('en el detalle el músculo se ve más grande que en la tarjeta', di.escala > di.escalaTarjeta * 1.25, di);
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
    const scriptsAntes = await js(`document.querySelectorAll('script').length`);
    await js(`__t.buscar('xsstest')`);
    comprobar('aparece el documento con HTML en título, texto y etiquetas', await esperar(`document.querySelector('[data-doc="articulos:390"]')`));
    const sinInyeccion = `({ marca: window.__xss, img: document.querySelectorAll('img').length, script: document.querySelectorAll('script').length,
        nodo: !!document.querySelector('#xss-tag, #xss-titulo, b.xss'), })`;
    let x = await js(sinInyeccion);
    const xt = await js(`document.querySelector('[data-doc="articulos:390"] [data-abrir]').textContent`);
    comprobar('tarjeta: el HTML se muestra como texto', xt.includes('<img') && x.marca === undefined && x.img === 0 && !x.nodo && x.script === scriptsAntes, { xt, x });
    await js(`document.querySelector('[data-doc="articulos:390"] [data-abrir]').click()`);
    await hasta(`document.getElementById('detalleGusta')`);
    x = await js(sinInyeccion);
    const xd = await js(`({ titulo: document.getElementById('detalleTitulo').textContent, texto: document.querySelector('.detalle-texto').textContent,
        etiquetas: [...document.querySelectorAll('#detalleCuerpo [data-etiqueta]')].map(b => b.textContent.trim()) })`);
    comprobar('detalle: título, texto y etiquetas con HTML se muestran como texto',
        xd.titulo.includes('<img') && xd.texto.includes('<script>') && xd.etiquetas.some(e => e.includes('<i')) && x.marca === undefined && x.img === 0 && !x.nodo && x.script === scriptsAntes,
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

    // Dos árboles cualesquiera (fase 6B): Anatomía x Equipamiento
    await js(`(() => { const a = document.getElementById('arbolB'); a.value = 'equipamiento'; a.dispatchEvent(new Event('change', { bubbles: true })); })()`);
    comprobar('al cambiar el árbol B, el menú B lista equipamientos y la etiqueta cambia',
        await esperar(`document.getElementById('etiquetaB').textContent === 'Equipamiento' && [...document.querySelectorAll('#menuB option')].some(o => o.textContent.startsWith('Barra'))`));
    comprobar('el árbol B no ofrece el mismo árbol que A', await esperar(`![...document.querySelectorAll('#arbolB option')].some(o => o.value === document.getElementById('arbolA').value)`));
    await js(`(() => { const b = document.getElementById('menuB'); b.value = [...b.options].find(o => o.textContent.startsWith('Barra (')).value; document.getElementById('formAB').requestSubmit(); })()`);
    comprobar('pecho x barra: tarjetas de ejercicios y las rutas de los dos árboles',
        await esperar(`document.querySelectorAll('#resultadoAB .tarjeta').length > 0 && [...document.querySelectorAll('#resultadoAB .ruta-arbol h3')].map(h => h.textContent).join() === 'Anatomía,Equipamiento'`));
    const rutasAB = await js(`[...document.querySelectorAll('#resultadoAB .ruta-arbol')].map(r => r.querySelector('h3').textContent + ': ' + [...r.querySelectorAll('li')].map(l => l.textContent).join(' > '))`);
    comprobar('las rutas llevan el nombre del árbol', JSON.stringify(rutasAB) === '["Anatomía: Cuerpo humano > Tren superior > Pecho","Equipamiento: Equipamiento > Pesas libres > Barra"]', rutasAB);
    // Patrón de movimiento: clasificación aproximada, avisada en la interfaz
    comprobar('sin patrón elegido no hay aviso de clasificación aproximada', await js(`document.getElementById('avisoAproximado').hidden`));
    await js(`(() => { const a = document.getElementById('arbolB'); a.value = 'patron'; a.dispatchEvent(new Event('change', { bubbles: true })); })()`);
    comprobar('al elegir Patrón de movimiento se avisa que es aproximado y cuántos ejercicios no se clasificaron',
        await esperar(`!document.getElementById('avisoAproximado').hidden && /aproximada/.test(document.getElementById('avisoAproximado').textContent) && /Sin clasificar/.test(document.getElementById('avisoAproximado').textContent)`));
    comprobar('«Sin clasificar» es una opción del menú de patrones', await js(`[...document.querySelectorAll('#menuB option')].some(o => o.textContent.startsWith('Sin clasificar'))`));
    await js(`(() => { const b = document.getElementById('menuB'); b.value = [...b.options].find(o => o.textContent.startsWith('Empuje horizontal (')).value; document.getElementById('formAB').requestSubmit(); })()`);
    comprobar('el resultado repite el aviso y marca el árbol como aproximado',
        await esperar(`document.querySelectorAll('#resultadoAB .tarjeta').length > 0 && document.querySelector('#resultadoAB .aviso-aproximado') && [...document.querySelectorAll('#resultadoAB .ruta-arbol h3')].some(h => h.textContent === 'Patrón de movimiento (aproximado)')`));
    await js(`(() => { const a = document.getElementById('arbolB'); a.value = 'temas'; a.dispatchEvent(new Event('change', { bubbles: true })); })()`);   // dejar el valor de siempre

    // La tarjeta «Relacionado con tu búsqueda» muestra la ruta del nodo en CADA árbol que participa (fase 6B)
    await js(`document.querySelector('[data-vista="vistaBusqueda"]').click()`);
    await js(`__t.buscar('pecho barra principiante')`);
    comprobar('pecho barra principiante: la tarjeta muestra una ruta por árbol (tres)',
        await esperar(`[...document.querySelectorAll('#discoveryZone .ruta-arbol h3')].map(h => h.textContent).join() === 'Anatomía,Equipamiento,Nivel'`));
    const rutasTarjeta = await js(`[...document.querySelectorAll('#discoveryZone .ruta-arbol')].map(r => [...r.querySelectorAll('li')].map(l => l.textContent).join(' > '))`);
    comprobar('con la ruta completa de cada nodo', JSON.stringify(rutasTarjeta) === '["Cuerpo humano > Tren superior > Pecho","Equipamiento > Pesas libres > Barra","Nivel de experiencia > Principiante"]', rutasTarjeta);

    // ========================================================================= solo teclado y escritorio (fase 7)
    console.log('\n[Solo teclado y pantalla de escritorio]');
    await pantalla(1280, 800);
    await js(`document.querySelector('[data-vista="vistaBusqueda"]').click()`);
    await js(`(() => { const i = document.getElementById('searchInput'); i.value = ''; i.focus(); })()`);
    await ESCRIBIR('pecho');
    await ENTER();
    comprobar('escribir en la búsqueda y pulsar Enter busca, sin ratón',
        await esperar(`document.getElementById('sectionTitle').textContent.includes('pecho') && __t.tarjetas().length > 0 && !document.querySelector('#resultsGrid .estado')`));
    const esc = await js(`(() => ({ ancho: document.documentElement.scrollWidth, ventana: document.documentElement.clientWidth, fuera: __t.desbordes(),
        columnas: new Set(__t.tarjetas().map(t => Math.round(t.getBoundingClientRect().left))).size }))()`);
    comprobar('a 1280 px no hay desplazamiento horizontal y las tarjetas se reparten en varias columnas', esc.ancho <= esc.ventana && esc.fuera.length === 0 && esc.columnas >= 3, esc);
    await comprobarTexto('escritorio');
    await captura('7-escritorio');
    comprobar('el enlace «Saltar a los resultados» está fuera de la pantalla mientras no tiene el foco',
        await js(`document.getElementById('saltarResultados').getBoundingClientRect().bottom <= 0`));
    await js(`document.getElementById('saltarResultados').focus()`);
    comprobar('y se ve cuando recibe el foco', await js(`(() => { const r = document.getElementById('saltarResultados').getBoundingClientRect(); return r.top >= 0 && r.bottom > 0 && r.width > 0; })()`));
    await ENTER();
    comprobar('Enter sobre él lleva el foco al título de los resultados', await js(`document.activeElement.id === 'sectionTitle'`));
    let pasos = 0;
    for (; pasos < 60; pasos++) {
        await TAB();
        if (await js(`document.activeElement.matches('#resultsGrid [data-abrir]')`)) break;
    }
    comprobar(`desde ahí, con Tab se llega al título de la primera tarjeta en ${pasos + 1} pulsaciones (sin el enlace eran 18; como mucho 10)`, pasos < 10, pasos);
    const tituloEnfocado = await js(`document.activeElement.closest('.tarjeta').dataset.doc`);
    comprobar('el elemento enfocado se ve (tiene contorno de foco)',
        await js(`(() => { const s = getComputedStyle(document.activeElement); return s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) >= 2; })()`));
    await ENTER();
    comprobar('Enter abre el detalle de la tarjeta enfocada', await esperar(`document.getElementById('detalle').open && document.getElementById('detalleGusta')`));
    await ESCAPE();
    comprobar('Escape lo cierra y el foco vuelve a esa tarjeta',
        await esperar(`!document.getElementById('detalle').open && document.activeElement.closest('.tarjeta')?.dataset.doc === ${JSON.stringify(tituloEnfocado)}`));

    // Explorador de árboles, solo con Tab, flechas y Enter
    await js(`document.querySelector('[data-vista="vistaArboles"]').focus()`);
    await ENTER();
    comprobar('Enter sobre la pestaña abre «Explorar por árboles»', await esperar(`__t.visible('#formAB')`));
    await esperar(`document.querySelectorAll('#arbolB option').length > 1`);
    const orden = [];
    for (let i = 0; i < 12; i++) {
        await TAB();
        orden.push(await js(`document.activeElement.id || document.activeElement.tagName`));
        if (orden.at(-1) === 'arbolB') break;
    }
    comprobar('Tab recorre Árbol A, concepto A y Árbol B, en ese orden', JSON.stringify(orden.filter(x => ['arbolA', 'menuA', 'arbolB'].includes(x))) === '["arbolA","menuA","arbolB"]', orden);
    await js(`(() => { const b = document.getElementById('arbolB'); b.value = 'temas'; b.dispatchEvent(new Event('change', { bubbles: true })); })()`);
    await ABAJO();
    comprobar('la flecha abajo cambia el Árbol B y el menú de conceptos se actualiza',
        await esperar(`document.getElementById('arbolB').value === 'equipamiento' && document.getElementById('etiquetaB').textContent === 'Equipamiento'`));
    await TAB();
    await TAB();
    comprobar('otras dos pulsaciones de Tab llegan a «Ver documentos»', await js(`document.activeElement.textContent.trim()`) === 'Ver documentos');
    await ENTER();
    comprobar('Enter en «Ver documentos» muestra la ruta de cada árbol elegido',
        await esperar(`[...document.querySelectorAll('#resultadoAB .ruta-arbol h3')].map(h => h.textContent).join() === 'Anatomía,Equipamiento'`));
    await comprobarTexto('árboles con teclado');
    // dejar todo como estaba para las secciones siguientes
    await js(`(() => { const b = document.getElementById('arbolB'); b.value = 'temas'; b.dispatchEvent(new Event('change', { bubbles: true })); })()`);
    await js(`document.querySelector('[data-vista="vistaBusqueda"]').click()`);
    await js(`__t.buscar('pecho barra principiante')`);
    await esperar(`document.querySelectorAll('#discoveryZone .ruta-arbol').length === 3`);
    await cdp('Emulation.clearDeviceMetricsOverride');

    // ========================================================================= modo oscuro
    // Cada texto se mide contra su fondo real, en claro y en oscuro (WCAG: 4.5 normal, 7 reforzado)
    const TEXTOS = [['body', 7], ['.marca', 4.5], ['#searchInput', 7], ['#nombrePerfil', 7], ['.pestana[aria-selected="true"]', 4.5],
        ['.pestana[aria-selected="false"]', 4.5], ['#sectionTitle', 7], ['.conteo', 4.5], ['#tituloFiltros', 7], ['.filtro-grupo h3', 4.5],
        ['.opcion', 7], ['.tarjeta-titulo .abrir', 7], ['.tarjeta-resumen', 4.5], ['.tarjeta-meta dt', 4.5], ['.tarjeta-meta dd', 7],
        ['.tipo-ejercicios', 4.5], ['.tipo-articulos', 4.5], ['.tarjeta .etiqueta', 4.5], ['#opcionesEtiquetas .etiqueta[aria-pressed="true"]', 4.5],
        ['.barra-fila .termino', 7], ['#formAB .btn-primario', 4.5], ['#detalleTitulo', 7], ['.detalle-texto', 7], ['#detalleGusta', 4.5],
        ['.relacionado .titulo', 7], ['.relacionado .comparte', 4.5], ['.ruta li', 4.5]];
    const medirTema = () => js(`({ contrastes: ${JSON.stringify(TEXTOS)}.map(([sel, min]) => ({ sel, min, c: __t.contraste(sel) })),
        fondo: __t.lum(__t.rgb(getComputedStyle(document.body).backgroundColor)), tarjeta: __t.lum(__t.rgb(getComputedStyle(document.querySelector('.tarjeta')).backgroundColor)),
        ilustracion: ['fondo', 'base', 'resaltado', 'tinta'].map(k => __t.variable('--color-ilustracion-' + k)) })`);
    await js(`document.querySelector('[data-vista="vistaBusqueda"]').click(); __t.buscar('calentamiento')`);
    await hasta(`__t.tarjetas().length === 12`);
    await js(`[...document.querySelectorAll('#opcionesEtiquetas [data-etiqueta]')].find(b => b.textContent.trim().startsWith('Fuerza')).click()`);   // una etiqueta marcada
    await js(`document.querySelector('[data-doc="ejercicios:103"] [data-abrir]').click()`);
    await hasta(`document.querySelector('#detalleCuerpo .relacionado')`);
    const temas = {};
    for (const [nombre, valor] of [['claro', 'light'], ['oscuro', 'dark']]) {
        console.log(`\n[Tema ${nombre}: contraste de los textos]`);
        await tema(valor);
        await new Promise(r => setTimeout(r, 300));
        const t2 = temas[nombre] = await medirTema();
        const bajos = t2.contrastes.filter(x => x.c < x.min);
        comprobar(`${nombre}: los ${t2.contrastes.length} textos revisados cumplen su contraste mínimo (el menor es ${Math.min(...t2.contrastes.map(x => x.c))}:1)`,
            bajos.length === 0, bajos);
        await captura(`11-${nombre}-detalle`);
    }
    comprobar('claro: fondo claro; oscuro: fondo oscuro y tarjetas algo más claras que el fondo',
        temas.claro.fondo > 0.8 && temas.oscuro.fondo < 0.03 && temas.oscuro.tarjeta > temas.oscuro.fondo && temas.oscuro.tarjeta < 0.1, { claro: temas.claro.fondo, oscuro: temas.oscuro.fondo, tarjeta: temas.oscuro.tarjeta });
    comprobar('los colores de las ilustraciones cambian con el tema', temas.claro.ilustracion.every((c, i) => c !== temas.oscuro.ilustracion[i]), temas);
    await js(`document.getElementById('detalleCerrar').click()`);
    await captura('12-oscuro-resultados');
    await tema('light');
    await js(`document.getElementById('quitarFiltros').click()`);

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
if (informe.fallos) {
    // Diagnóstico: qué mostraba la página cuando falló
    const estado = await js(`({ titulo: document.getElementById('sectionTitle')?.textContent, conteo: document.getElementById('statsBar')?.textContent,
        cuadricula: document.getElementById('resultsGrid')?.innerText.slice(0, 200), detalleAbierto: document.getElementById('detalle')?.open })`).catch(() => null);
    console.log('  estado de la página al terminar: ' + JSON.stringify(estado));
    await captura('fallo').catch(() => {});
}

console.log(`\n${informe.total} comprobaciones de interfaz, ${informe.fallos} fallos`);
cerrar(informe.fallos === 0 ? 0 : 1);
