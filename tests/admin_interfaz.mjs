// tests/admin_interfaz.mjs — pruebas del panel de administrador en un navegador real.
//
// Lo lanza tests/test_admin_interfaz.php, que prepara la BD de pruebas con el escenario fijo
// de tests/datos_admin.php (totales calculados a mano en ese archivo) y el servidor:
//     node tests/admin_interfaz.mjs http://127.0.0.1:<puerto>
// Con CAPTURAS=<carpeta> guarda capturas de pantalla.
import { abrirNavegador, crearInforme } from './navegador.mjs';

const BASE = process.argv[2];
if (!BASE) { console.error('uso: node tests/admin_interfaz.mjs <url base>'); process.exit(3); }

const { cdp, js, esperar, hasta, pantalla, captura, tema, ir, cerrar, TAB } = await abrirNavegador();
const informe = crearInforme();
const comprobar = informe.comprobar;

const EMOJI = /\p{Extended_Pictographic}/u;
const RELLENO = /calculando|modo descubrimiento|lorem|pr[oó]ximamente|bienvenid/i;

/** Inicia sesión desde la propia página (misma origen: la cookie queda en el navegador). */
const entrar = (correo, contrasena) => js(`fetch('login.php', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ correo: '${correo}', contrasena: '${contrasena}' }) }).then(r => r.status)`);
const salir = () => js(`fetch('logout.php', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: '{}' }).then(r => r.status)`);
/** Abre una URL desde cero (pasando por about:blank, así siempre es una carga nueva). */
const abrir = async url => { await ir('about:blank'); await ir(url); };
const seccion = async (id, dias = 7) => {
    await abrir(`${BASE}/admin.php#${id}/${dias}`);
    await hasta(`document.readyState === 'complete' && window.PanelAdmin && PanelAdmin.seccion() === '${id}' && PanelAdmin.dias() === ${dias}`);
    await hasta(`document.querySelector('#actualizado').textContent.startsWith('Actualizado') || document.querySelector('.estado-error')`);
};
const textos = sel => js(`[...document.querySelectorAll('${sel}')].map(e => e.innerText.replace(/\\s+/g, ' ').trim())`);
const tarjetas = () => js(`Object.fromEntries([...document.querySelectorAll('.tarjeta-numero')].map(t => [t.querySelector('h2').textContent, { valor: t.querySelector('.valor').textContent, detalle: (t.querySelector('.detalle-numero')?.textContent || '').trim() }]))`);
const titulosGraficas = () => textos('.grafica h2');
const comprobarTexto = async donde => {
    const t = await js('document.body.innerText');
    comprobar(`${donde}: sin emojis`, !EMOJI.test(t), t.match(EMOJI)?.[0]);
    comprobar(`${donde}: sin textos de relleno`, !RELLENO.test(t), t.match(RELLENO)?.[0]);
    comprobar(`${donde}: ni correo, ni nombre, ni fecha de nacimiento, ni perfil en la página`, !/@prueba\.test|Usuario u\d\d|perfil_id|cuenta_id|fecha_nac|contrasena/i.test(t));
};

try {
    await pantalla(1280, 900);
    await ir(`${BASE}/index.html`);

    // ========================================================================= acceso
    console.log('\n[Acceso a la página del panel]');
    await js(`fetch('admin.php').then(r => r.status)`).then(c => comprobar('sin sesión, admin.php responde 401', c === 401, c));
    comprobar('un usuario normal inicia sesión', await entrar('u01@prueba.test', 'UsuarioPrueba12345') === 200);
    await abrir(`${BASE}/admin.php`);
    const cuerpoUsuario = await js('document.body.innerText');
    comprobar('un usuario normal que abre admin.php ve un rechazo y no el panel', /No tienes acceso/.test(cuerpoUsuario) && !(await js(`!!document.getElementById('panel')`)), cuerpoUsuario.slice(0, 120));
    await ir(`${BASE}/index.html`);
    await salir();
    comprobar('el administrador inicia sesión', await entrar('admin@prueba.test', 'AdminPrueba12345') === 200);

    // ========================================================================= resumen
    console.log('\n[Resumen: números y variación calculados a mano]');
    await abrir(`${BASE}/admin.php#resumen/7`);
    await hasta(`window.PanelAdmin && PanelAdmin.seccion() === 'resumen' && document.querySelectorAll('.tarjeta-numero').length === 6`);
    comprobar('el título de la página y de la sección', await js('document.title') === 'Resumen · Administración · Buscador Gym' && (await textos('h1'))[0] === 'Resumen');
    let t = await tarjetas();
    comprobar('seis tarjetas: cuentas, perfiles, perfiles activos, búsquedas, aperturas y «me gusta»',
        JSON.stringify(Object.keys(t)) === '["Cuentas","Perfiles","Perfiles activos","Búsquedas","Aperturas","«Me gusta»"]', Object.keys(t));
    comprobar('valores a 7 días: 31 cuentas, 31 perfiles, 7 activos, 8 búsquedas, 9 aperturas, 5 «me gusta»',
        t.Cuentas.valor === '31' && t.Perfiles.valor === '31' && t['Perfiles activos'].valor === '7' && t['Búsquedas'].valor === '8' && t.Aperturas.valor === '9' && t['«Me gusta»'].valor === '5', t);
    comprobar('variación frente al período anterior: +350 % aperturas, +150 % «me gusta», +100 % búsquedas, +133,3 % activos',
        /\+350 % frente a los 7 días anteriores/.test(t.Aperturas.detalle) && /\+150 % frente/.test(t['«Me gusta»'].detalle)
        && /\+100 % frente/.test(t['Búsquedas'].detalle) && /\+133[.,]3 % frente/.test(t['Perfiles activos'].detalle), t);
    comprobar('las cuentas nuevas (6) no tienen período anterior y lo dice', /Nuevas en el período: 6/.test(t.Cuentas.detalle) && /Sin datos de los 7 días anteriores/.test(t.Cuentas.detalle), t.Cuentas);
    const fila = await js(`(() => { const c = [...document.querySelectorAll('.tarjeta-numero')].map(e => Math.round(e.getBoundingClientRect().top));
        return { tops: c, enUnaFila: new Set(c).size === 1, enlace: getComputedStyle(document.querySelector('.admin-barra a.btn')).textDecorationLine }; })()`);
    comprobar('a 1280 px las seis tarjetas del resumen caben en una sola fila', fila.enUnaFila, fila.tops);
    comprobar('«Volver a la aplicación» se ve como botón, sin subrayado de enlace', fila.enlace === 'none', fila.enlace);
    await comprobarTexto('resumen');
    await captura('admin-1-resumen');

    await js(`document.querySelector('[data-dias="30"]').click()`);
    await hasta(`PanelAdmin.dias() === 30 && document.querySelector('.tarjeta-numero:nth-child(5) .valor')?.textContent === '20'`);
    t = await tarjetas();
    comprobar('al elegir 30 días: 20 aperturas (12 más las 8 de los dos artículos agregados), 8 «me gusta», 12 activos, 12 búsquedas',
        t.Aperturas.valor === '20' && t['«Me gusta»'].valor === '8' && t['Perfiles activos'].valor === '12' && t['Búsquedas'].valor === '12', t);
    comprobar('el período seleccionado queda marcado y en la URL', await js(`document.querySelector('[data-dias="30"]').getAttribute('aria-pressed') === 'true' && document.querySelector('[data-dias="7"]').getAttribute('aria-pressed') === 'false' && location.hash === '#resumen/30'`));
    await js(`document.querySelector('[data-dias="90"]').click()`);
    await hasta(`PanelAdmin.dias() === 90 && document.querySelector('.tarjeta-numero:nth-child(5) .valor')?.textContent === '22'`);
    comprobar('a 90 días: 22 aperturas (14 más las 8 agregadas)', (await tarjetas()).Aperturas.valor === '22');
    await js(`document.querySelector('[data-dias="7"]').click()`);
    await hasta(`PanelAdmin.dias() === 7 && document.querySelector('.tarjeta-numero:nth-child(5) .valor')?.textContent === '9'`);

    // ========================================================================= gráficas de línea
    console.log('\n[Actividad por día: línea con fechas legibles y tooltip]');
    const g = await js(`(() => { const s = document.querySelector('#g-lienzo-0 svg'); return {
        lineas: s.querySelectorAll('polyline').length, puntos: s.querySelectorAll('circle').length, zonas: s.querySelectorAll('.g-zona').length,
        fechas: [...s.querySelectorAll('text.g-suave')].map(e => e.textContent).filter(x => /[a-z]/i.test(x)),
        leyenda: [...document.querySelectorAll('#graficas .grafica:first-child .leyenda li')].map(l => l.textContent.trim()),
        titulo: document.querySelector('#graficas .grafica:first-child h2').textContent,
        pasteles: document.querySelectorAll('#graficas svg path').length, canvas: document.querySelectorAll('canvas').length }; })()`);
    comprobar('dos líneas (aperturas y «me gusta») con un punto por día durante 8 días', g.lineas === 2 && g.puntos === 16 && g.zonas === 8, g);
    comprobar('el eje de fechas se lee: etiquetas como «12 nov» y termina en hoy', g.fechas.length >= 3 && g.fechas.every(f => /^\d{1,2} [a-z]{3,4}$/i.test(f)), g.fechas);
    comprobar('la leyenda dice qué es cada línea', JSON.stringify(g.leyenda) === '["Aperturas","«Me gusta»"]', g.leyenda);
    comprobar('el título dice la conclusión: el día más alto (ayer) con 5 aperturas y 4 «me gusta»',
        /^La actividad llegó a su punto más alto el \d{1,2} de [a-záéíóú]+: 5 aperturas y 4 «me gusta»$/.test(g.titulo), g.titulo);
    comprobar('no hay gráficas de pastel ni de otro tipo con arcos, y no se usa <canvas>', g.pasteles === 0 && g.canvas === 0, g);
    const zona = await js(`(() => { const z = [...document.querySelectorAll('#g-lienzo-0 .g-zona')].find(e => e.getAttribute('aria-label').includes('Aperturas: 5')); const r = z.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; })()`);
    await cdp('Input.dispatchMouseEvent', { type: 'mouseMoved', x: zona.x, y: zona.y });
    await hasta(`!document.getElementById('tooltip').hidden`);
    const tip = await js(`document.getElementById('tooltip').textContent`);
    comprobar('al pasar el puntero, el tooltip muestra el día y los valores', /\d{1,2} de [a-záéíóú]+\nAperturas: 5\n«Me gusta»: 4/.test(tip), tip);
    await captura('admin-2-tooltip');
    await cdp('Input.dispatchMouseEvent', { type: 'mouseMoved', x: 5, y: 5 });
    comprobar('al quitar el puntero, el tooltip se oculta', await esperar(`document.getElementById('tooltip').hidden`, 3000));
    await js(`document.querySelector('#g-lienzo-0 .g-zona').focus()`);
    comprobar('con el teclado (foco en un día) también aparece el tooltip', await esperar(`!document.getElementById('tooltip').hidden`, 3000));
    const titulos2 = await titulosGraficas();
    comprobar('segunda gráfica: búsquedas por día, con conclusión', /^Hubo 8 búsquedas; el día con más fue el \d{1,2} de [a-záéíóú]+, con 8$/.test(titulos2[1]), titulos2[1]);

    // ========================================================================= más consumidos
    console.log('\n[Más consumidos: barras ordenadas, un color, valor al lado]');
    await seccion('mas', 7);
    const mas = await js(`(() => ['#g-lienzo-0', '#g-lienzo-1'].map(id => { const s = document.querySelector(id + ' svg');
        const barras = [...s.querySelectorAll('rect.g-barra')];
        return { anchos: barras.map(b => Math.round(parseFloat(b.getAttribute('width')))), valores: [...s.querySelectorAll('text.g-valor')].map(e => e.textContent),
            etiquetas: [...s.querySelectorAll('g[data-tip] text.g-texto')].map(e => e.textContent),
            colores: [...new Set(barras.map(b => getComputedStyle(b).fill))],
            valorAlLado: barras.every((b, i) => { const v = s.querySelectorAll('text.g-valor')[i]; return parseFloat(v.getAttribute('x')) > parseFloat(b.getAttribute('x')) + parseFloat(b.getAttribute('width')); }) }; }))()`);
    comprobar('ejercicios: 101 (6), 201 (4) y 102 (1), de mayor a menor, con el valor a la derecha de cada barra',
        JSON.stringify(mas[0].valores) === '["6","4","1"]' && mas[0].anchos.every((a, i) => i === 0 || a <= mas[0].anchos[i - 1]) && mas[0].valorAlLado, mas[0]);
    comprobar('las etiquetas son los títulos', mas[0].etiquetas[0] === 'Press de banca plano', mas[0].etiquetas);
    comprobar('artículos: 302 (2) antes que 301 (1)', JSON.stringify(mas[1].valores) === '["2","1"]', mas[1]);
    comprobar('un solo color en todas las barras', mas[0].colores.length === 1 && mas[1].colores.length === 1 && mas[0].colores[0] === mas[1].colores[0], [mas[0].colores, mas[1].colores]);
    const tm = await titulosGraficas();
    comprobar('títulos con la conclusión', tm[0] === '«Press de banca plano» lidera los ejercicios con 6 interacciones (4 aperturas y 2 «me gusta»)'
        && tm[1] === '«Cómo progresar en la sentadilla» lidera los artículos con 2 interacciones (1 apertura y 1 «me gusta»)', tm);
    comprobar('las barras son más largas cuanto mayor es el valor (proporcionales)', Math.abs(mas[0].anchos[1] / mas[0].anchos[0] - 4 / 6) < 0.03, mas[0].anchos);
    comprobar('las tarjetas de arriba nombran al líder', (await tarjetas())['Ejercicio más consumido'].valor === 'Press de banca plano');
    await captura('admin-3-mas-consumidos');

    // CSV
    console.log('\n[Exportar a CSV: solo datos agregados]');
    const csv = await js(`PanelAdmin.csv('ejercicios')`);
    comprobar('el CSV tiene el encabezado y una fila por documento', csv.startsWith('Título,Aperturas,«Me gusta»,Total\r\n') && csv.includes('Press de banca plano,4,2,6\r\n') && csv.trim().split('\r\n').length === 4, csv);
    comprobar('el CSV no trae correo, nombre, fecha ni perfil', !/@|perfil|fecha|nombre|correo|contrasena/i.test(csv.split('\r\n')[0]) && !/@prueba|Usuario u\d/.test(csv));
    await js(`window.__descargas = []; HTMLAnchorElement.prototype.click = function () { window.__descargas.push(this.download); };
        const crear = URL.createObjectURL.bind(URL); window.__blobs = []; URL.createObjectURL = b => { window.__blobs.push(b); return crear(b); };
        document.querySelector('[data-csv="ejercicios"]').click()`);
    await hasta(`window.__descargas.length === 1`);
    const desc = await js(`({ nombre: window.__descargas[0], tipo: window.__blobs[0].type })`);
    // Blob.text() quita el BOM al decodificar: se miran los bytes del archivo
    const bytes = await js(`window.__blobs[0].arrayBuffer().then(b => [...new Uint8Array(b).slice(0, 3)])`);
    const texto = await js(`window.__blobs[0].text()`);
    comprobar('el botón descarga un archivo con nombre claro, UTF-8, con marca BOM para Excel y el mismo contenido que se ve',
        desc.nombre === 'panel-mas-ejercicios-7dias.csv' && /utf-8/.test(desc.tipo) && JSON.stringify(bytes) === '[239,187,191]'
        && texto === await js(`PanelAdmin.csv('ejercicios')`), [desc, bytes]);
    await hasta(`document.querySelectorAll('[data-csv]').length === 2`);
    comprobar('cada tabla tiene su botón de exportar', await js(`[...document.querySelectorAll('.tabla-bloque')].every(b => b.querySelector('[data-csv]'))`));

    // ========================================================================= menos consumidos
    console.log('\n[Menos consumidos: qué conviene revisar]');
    await seccion('menos', 7);
    const tmen = await titulosGraficas();
    comprobar('título: «Cruce de poleas» se mostró 25 veces y nadie lo abrió', tmen[0] === '«Cruce de poleas» se mostró 25 veces y nadie lo abrió', tmen);
    const avisosMenos = await textos('.aviso-panel');
    comprobar('un aviso dice qué títulos y etiquetas revisar y cuáles nunca se mostraron',
        avisosMenos.some(a => /Qué conviene revisar.*«Cruce de poleas»/.test(a) && /Etiquetas que se repiten entre ellos: .*Pecho/.test(a))
        && avisosMenos.some(a => /nunca se han mostrado.*«Artículo sin estrenar»/i.test(a)), avisosMenos);
    const menosT = await tarjetas();
    comprobar('tarjetas: 3 poco abiertos y 1 nunca mostrado', menosT['Se muestran mucho y casi no se abren'].valor === '3' && menosT['Nunca se han mostrado'].valor === '1', menosT);
    comprobar('la tabla de nunca mostrados lista el artículo 303', (await textos('[aria-labelledby="t-nunca-mostrados"] .tabla-envoltura tbody tr')).some(f => f.startsWith('Artículo sin estrenar')), await textos('.tabla-envoltura tbody tr'));

    // ========================================================================= edad
    console.log('\n[Edad: barras agrupadas con leyenda; rangos con menos de 5 cuentas ocultos]');
    await seccion('edad', 7);
    const edad = await js(`(() => ({ leyendas: [...document.querySelectorAll('.leyenda')].map(l => [...l.querySelectorAll('li')].map(x => x.textContent.trim())),
        categorias: [...document.querySelectorAll('#g-lienzo-0 svg g[data-tip] text.g-texto')].map(e => e.textContent),
        pies: [...document.querySelectorAll('#g-lienzo-0 svg g[data-tip] text.g-suave')].map(e => e.textContent),
        clases: [...new Set([...document.querySelectorAll('#g-lienzo-0 svg rect')].map(r => r.getAttribute('class')))],
        colores: [...new Set([...document.querySelectorAll('#g-lienzo-0 svg rect')].map(r => getComputedStyle(r).fill))],
        muestras: [...document.querySelectorAll('#graficas .grafica:first-child .leyenda rect')].map(r => getComputedStyle(r).fill),
        filas: [...document.querySelectorAll('[aria-labelledby="t-por-edad"] .tabla-envoltura tbody tr')].map(f => [...f.children].map(c => c.textContent.trim())) }))()`);
    comprobar('solo aparecen 18 a 24, 25 a 34 y 35 a 44 (los de menos de 5 cuentas no)', JSON.stringify(edad.categorias) === '["18 a 24","25 a 34","35 a 44"]', edad.categorias);
    comprobar('cada grupo dice cuántas cuentas tiene', JSON.stringify(edad.pies) === '["6 cuentas","12 cuentas","7 cuentas"]', edad.pies);
    comprobar('dos series con dos colores distintos y una leyenda que explica cada uno',
        edad.colores.length === 2 && JSON.stringify(edad.leyendas[0]) === '["Aperturas","«Me gusta»"]' && JSON.stringify(edad.muestras) === JSON.stringify(edad.colores), edad);
    const te = await titulosGraficas();
    comprobar('los títulos largos se reparten de forma equilibrada (sin dejar el «%» solo en una línea)',
        await js(`getComputedStyle(document.querySelector('.grafica h2')).textWrap === 'balance'`));
    comprobar('títulos con la conclusión: 18 a 24 concentra el 50 % de las aperturas; 2 de 6 cuentas activas',
        te[0] === 'El rango 18 a 24 concentra el 50 % de las aperturas' && /^En el rango 18 a 24, 2 de 6 cuentas estuvieron activas \(33[.,]3 %\)$/.test(te[1]), te);
    comprobar('la tabla tiene 3 filas, con los 5 músculos y temas más consumidos del rango',
        edad.filas.length === 3 && edad.filas[0][0] === '18 a 24' && edad.filas[0][5].startsWith('Pecho (4)') && edad.filas[0][6].startsWith('Fuerza (1)'), edad.filas);
    comprobar('la página no menciona los rangos ocultos', !/menos de 18|45 o más/.test(await js('document.querySelector("main").innerText')));
    await captura('admin-4-edad');

    // ========================================================================= búsquedas y cobertura
    console.log('\n[Búsquedas y cobertura]');
    await seccion('busquedas', 7);
    const tb = await titulosGraficas();
    comprobar('búsquedas: títulos con la conclusión', tb[0] === '«banc» es la raíz más buscada: aparece en 3 búsquedas de 8' && tb[1] === '3 búsquedas no encontraron contenido relacionado; la más repetida es «xyz»', tb);
    const bt = await tarjetas();
    comprobar('búsquedas: 8 en total, 2 sin resultados (25 %), 3 sin relación', bt['Búsquedas'].valor === '8' && bt['Sin resultados'].valor === '2' && /25 % del total/.test(bt['Sin resultados'].detalle) && bt['Sin relación en los árboles'].valor === '3', bt);
    comprobar('la tabla traduce la vía técnica a una frase', (await textos('[aria-labelledby="t-contenido-faltante"] .tabla-envoltura tbody tr')).join('|').includes('Sin relación entre ambos conceptos')
        && !(await js('document.querySelector("main").innerText')).includes('sin_interseccion'));
    await seccion('cobertura', 7);
    const tc = await titulosGraficas();
    comprobar('cobertura: dice dónde falta contenido', tc[0] === '«Cuádriceps» tiene solo 5 documentos: es donde más falta contenido' && tc[1] === '«Recuperación» tiene solo 1 documento: es donde más falta contenido', tc);
    comprobar('cobertura: una nota explica cómo se marca', (await textos('.aviso-panel')).some(a => /mediana/.test(a)));
    const filasCob = await textos('[aria-labelledby="t-temas"] .tabla-envoltura tbody tr');
    comprobar('la tabla de temas marca «Recuperación» con poca interacción', filasCob.some(f => f.startsWith('Recuperación 1 0') && /Poca interacción/.test(f)), filasCob);
    await captura('admin-5-cobertura');

    // ========================================================================= HTML en el contenido
    console.log('\n[Contenido con HTML: no se interpreta]');
    await seccion('mas', 30);
    const xss = await js(`({ marca: window.__xss, img: document.querySelectorAll('img').length, onerror: document.querySelectorAll('[onerror]').length,
        titulo: [...document.querySelectorAll('[aria-labelledby="t-articulos"] .tabla-envoltura td:first-child')].map(e => e.textContent).find(x => x.includes('<img')),
        lienzo: document.querySelector('#g-lienzo-1').innerHTML.includes('<img'), csv: PanelAdmin.csv('articulos').includes('<img') })`);
    comprobar('el título con HTML se ve como texto en la tabla y no crea ningún nodo ni ejecuta nada',
        xss.marca === undefined && xss.img === 0 && xss.onerror === 0 && !!xss.titulo && !xss.lienzo, xss);
    comprobar('el CSV lleva el texto sin interpretarlo', xss.csv === true);
    comprobar('un título que empieza con = se exporta con apóstrofo (sin ejecutar fórmulas)', (await js(`PanelAdmin.csv('articulos')`)).includes("'=HYPERLINK"));

    // ========================================================================= diseño: columnas, selector fijo, teléfono
    console.log('\n[Diseño: dos columnas, selector siempre visible, una columna en teléfono]');
    await seccion('mas', 30);
    await pantalla(1280, 600);
    const cols = await js(`(() => { const g = [...document.querySelectorAll('#graficas .grafica')].map(e => e.getBoundingClientRect());
        const nav = document.querySelector('.admin-nav').getBoundingClientRect(), tar = document.querySelector('#tarjetas').getBoundingClientRect(), graf = document.querySelector('#graficas').getBoundingClientRect(), sel = document.querySelector('.admin-selector').getBoundingClientRect();
        return { dosColumnas: g.length === 2 && Math.abs(g[0].top - g[1].top) < 2 && g[1].left > g[0].right - 2 && Math.abs(g[0].width - g[1].width) < 2,
            navALaIzquierda: nav.right <= tar.left + 1, tarjetasArriba: tar.bottom <= graf.top + 1, selectorArriba: sel.bottom <= tar.top + 1 }; })()`);
    comprobar('navegación lateral a la izquierda; selector y tarjetas arriba; gráficas en dos columnas del mismo ancho', cols.dosColumnas && cols.navALaIzquierda && cols.tarjetasArriba && cols.selectorArriba, cols);
    await js(`window.scrollTo(0, 500)`);
    await new Promise(r => setTimeout(r, 300));
    const fijo = await js(`({ y: scrollY, top: document.querySelector('.admin-selector').getBoundingClientRect().top, alto: innerHeight, nav: document.querySelector('.admin-nav').getBoundingClientRect().top })`);
    comprobar('al desplazar la página, el selector de período sigue visible arriba', fijo.y > 100 && fijo.top >= 0 && fijo.top < 120, fijo);
    comprobar('la navegación lateral también sigue visible', fijo.nav >= 0 && fijo.nav < 200, fijo);
    await js(`window.scrollTo(0, 0)`);

    await pantalla(375, 700, true);
    await abrir(`${BASE}/admin.php#mas/30`);
    await hasta(`document.readyState === 'complete' && document.querySelector('#graficas .grafica')`);
    await new Promise(r => setTimeout(r, 400));
    const tel = await js(`(() => { const g = [...document.querySelectorAll('#graficas .grafica')].map(e => e.getBoundingClientRect());
        const fuera = [...document.querySelectorAll('body *')].filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && (r.right > document.documentElement.clientWidth + 1 || r.left < -1)
            && !e.closest('.tabla-envoltura, .admin-nav, .tooltip') && getComputedStyle(e).position !== 'fixed'; }).slice(0, 5).map(e => e.tagName + '.' + e.className);
        const nav = document.querySelector('.admin-nav');
        return { ancho: document.documentElement.scrollWidth, ventana: document.documentElement.clientWidth, fuera,
            unaColumna: g.length === 2 && Math.abs(g[0].left - g[1].left) < 2 && g[1].top >= g[0].bottom - 1 && g[0].width > 300,
            navHorizontal: getComputedStyle(nav).display === 'flex',
            svgDentro: [...document.querySelectorAll('#graficas svg')].every(s => s.getBoundingClientRect().right <= document.documentElement.clientWidth + 1) }; })()`);
    comprobar('a 375 px no hay desplazamiento horizontal de la página', tel.ancho <= tel.ventana && tel.ventana <= 375 && tel.fuera.length === 0, tel);
    comprobar('a 375 px las gráficas pasan a una columna y caben en la pantalla', tel.unaColumna && tel.svgDentro, tel);
    comprobar('a 375 px la navegación se vuelve una fila deslizable', tel.navHorizontal);
    const letra = await js(`[...document.querySelectorAll('.valor-texto')].map(e => parseFloat(getComputedStyle(e).fontSize))`);
    comprobar('a 375 px los títulos largos de las tarjetas no salen en letra enorme (18 px como máximo)', letra.length > 0 && letra.every(v => v <= 18.5), letra);
    comprobar('los números sí se mantienen grandes', await js(`parseFloat(getComputedStyle(document.querySelector('.tarjeta-numero:nth-child(3) .valor')).fontSize) >= 24`));
    await captura('admin-6-movil');
    await js(`document.querySelector('[data-seccion="edad"]').click()`);
    await hasta(`PanelAdmin.seccion() === 'edad' && document.querySelector('#g-lienzo-0 svg')`);
    await new Promise(r => setTimeout(r, 300));
    comprobar('a 375 px la gráfica agrupada de edad cabe', await js(`document.querySelector('#g-lienzo-0 svg').getBoundingClientRect().right <= document.documentElement.clientWidth + 1 && document.documentElement.scrollWidth <= 375`));
    await pantalla(1280, 900);

    // ========================================================================= modo oscuro
    console.log('\n[Modo oscuro: gráficas y texto legibles]');
    await seccion('edad', 7);
    const medir = () => js(`(() => { const lum = c => { const [r, g, b] = c.match(/[\\d.]+/g).slice(0, 3).map(Number).map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
        const con = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return Math.round((x + 0.05) / (y + 0.05) * 100) / 100; };
        const fondo = getComputedStyle(document.querySelector('.grafica')).backgroundColor;
        const t = e => getComputedStyle(e).fill;
        return { fondo, texto: con(t(document.querySelector('.g-texto')), fondo), valor: con(t(document.querySelector('.g-valor')), fondo), suave: con(t(document.querySelector('.g-suave')), fondo),
            serieA: con(t(document.querySelector('rect.g-a')), fondo), serieB: con(t(document.querySelector('rect.g-b')), fondo),
            color: getComputedStyle(document.querySelector('rect.g-a')).fill,
            h1: con(getComputedStyle(document.querySelector('h1')).color, getComputedStyle(document.body).backgroundColor) }; })()`);
    await tema('light');
    await new Promise(r => setTimeout(r, 200));
    const claro = await medir();
    await tema('dark');
    await new Promise(r => setTimeout(r, 300));
    const oscuro = await medir();
    for (const [nombre, m] of [['claro', claro], ['oscuro', oscuro]]) {
        comprobar(`${nombre}: contraste de las etiquetas 4,5:1 o más y de las dos series con el fondo 3:1 o más`,
            m.texto >= 4.5 && m.valor >= 4.5 && m.suave >= 4.5 && m.serieA >= 3 && m.serieB >= 3 && m.h1 >= 7, m);
    }
    comprobar('en oscuro el fondo y el color de la serie cambian', claro.fondo !== oscuro.fondo && claro.color !== oscuro.color, [claro.color, oscuro.color]);
    await captura('admin-7-oscuro');
    await tema('light');

    // ========================================================================= sesión terminada y teclado
    console.log('\n[Sesión terminada y teclado]');
    await seccion('resumen', 7);
    await js(`document.querySelector('[data-seccion="mas"]').focus()`);
    comprobar('la navegación y el selector se alcanzan con Tab', await js(`document.activeElement.dataset.seccion === 'mas'`));
    for (let i = 0; i < 6; i++) await TAB();
    comprobar('Tab recorre el resto de secciones y llega al selector de período', await js(`document.activeElement.dataset.dias !== undefined`), await js('document.activeElement.outerHTML.slice(0, 70)'));
    await salir();
    await js(`document.querySelector('[data-dias="30"]').click()`);
    comprobar('si la sesión terminó, el panel lo dice y ofrece iniciar sesión', await esperar(`document.querySelector('.estado-error a[href="index.html"]')`, 10000)
        && /sesión terminó/.test(await js(`document.querySelector('.estado-error').innerText`)));
    comprobar('con la sesión terminada ya no queda ningún dato en pantalla', await js(`document.querySelectorAll('.tarjeta-numero').length === 0 && document.querySelectorAll('.tabla-bloque').length === 0`));
} catch (e) {
    comprobar('la prueba terminó sin errores', false, e.message);
}
if (informe.fallos) {
    const estado = await js(`({ seccion: window.PanelAdmin?.seccion(), titulo: document.getElementById('tituloSeccion')?.textContent, graficas: document.getElementById('graficas')?.innerText.slice(0, 200) })`).catch(() => null);
    console.log('  estado de la página al terminar: ' + JSON.stringify(estado));
    await captura('admin-fallo').catch(() => {});
}

console.log(`\n${informe.total} comprobaciones del panel en el navegador, ${informe.fallos} fallos`);
cerrar(informe.fallos === 0 ? 0 : 1);
