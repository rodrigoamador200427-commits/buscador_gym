// tests/ilustraciones.mjs — revisa TODAS las ilustraciones en un navegador real.
//
// Lo lanza tests/test_ilustraciones.php:
//     node tests/ilustraciones.mjs <url base> <datos.json> [carpeta de capturas]
// datos.json = { musculos: [grupo_id de la taxonomía], grupos_bd: [grupo_id que existen en la
//                BD], temas: [temas del árbol de Temas] }
//
// Abre tests/galeria_ilustraciones.html, hace una captura de cada ilustración (tamaño de
// tarjeta y de detalle, en claro y en oscuro) y CUENTA PÍXELES en ella: así comprueba que el
// músculo resaltado se ve, que el resto queda atenuado y que ningún color está fijo.
// Con una carpeta de capturas (o la variable CAPTURAS) guarda los PNG para revisarlos a ojo.
import { readFileSync } from 'node:fs';
import { abrirNavegador, crearInforme, leerPNG, contarColor, contraste } from './navegador.mjs';

const [BASE, rutaDatos, carpetaArg] = process.argv.slice(2);
if (!BASE || !rutaDatos) { console.error('uso: node tests/ilustraciones.mjs <url base> <datos.json> [capturas]'); process.exit(3); }
const datos = JSON.parse(readFileSync(rutaDatos, 'utf8'));
const carpeta = carpetaArg || process.env.CAPTURAS || null;

// Vista en la que se ve cada grupo muscular (conocimiento de anatomía, no del código)
const VISTA_ESPERADA = { 1: 'frontal', 2: 'posterior', 3: 'frontal', 4: 'frontal', 5: 'posterior', 6: 'frontal',
    7: 'posterior', 8: 'posterior', 9: 'posterior', 10: 'frontal', 11: 'frontal' };
const MITAD_ESPERADA = { 1: 'superior', 2: 'superior', 3: 'superior', 4: 'superior', 5: 'superior', 6: 'inferior',
    7: 'inferior', 8: 'inferior', 9: 'inferior', 10: 'superior', 11: 'superior' };
const REGIONES = {
    frontal: ['hombro', 'pecho', 'biceps', 'antebrazos', 'abdomen', 'cuadriceps'],
    posterior: ['hombro', 'espalda', 'triceps', 'antebrazos', 'gluteo', 'isquiotibiales', 'pantorrilla'],
};
// Área mínima del resaltado, en píxeles, para decir que "se distingue a simple vista"
const MIN_RESALTADO = { tarjeta: 250, detalle: 600 };

const n = await abrirNavegador();
const informe = crearInforme();
const comprobar = informe.comprobar;
const ids = [...new Set([...datos.musculos, ...datos.grupos_bd])].sort((a, b) => a - b);

try {
    await n.pantalla(1280, 1000);
    await n.tema('light');
    await n.ir(`${BASE}/tests/galeria_ilustraciones.html?musculos=${ids.join(',')}&temas=${encodeURIComponent(datos.temas.join('|'))}`);

    // ========================================================================= cobertura
    console.log('\n[Cobertura: todo grupo muscular y todo tema tiene ilustración]');
    const m = await n.js(`[...document.querySelectorAll('.muestra')].map(f => { const s = f.querySelector('[data-tamano="detalle"] svg'), t = f.querySelector('[data-tamano="tarjeta"] svg');
        return { clave: f.dataset.muestra, dato: s.dataset.ilustracion, titulo: s.querySelector('title').textContent,
                 uso: s.querySelector('use').getAttribute('href'), caja: s.getAttribute('viewBox'), cajaTarjeta: t.getAttribute('viewBox'),
                 clases: t.getAttribute('class'), estilo: s.getAttribute('style') || '' }; })`);
    const porClave = Object.fromEntries(m.map(x => [x.clave, x]));
    const sinIlustracion = ids.filter(id => porClave[`musculo-${id}`]?.dato !== `musculo:${id}`);
    comprobar(`los ${datos.musculos.length} grupos de la taxonomía (${datos.musculos.join(', ')}) tienen ilustración propia`,
        datos.musculos.length === 11 && datos.musculos.every(id => !sinIlustracion.includes(id)), sinIlustracion);
    comprobar(`los grupo_id que existen en la BD (${datos.grupos_bd.join(', ')}) tienen ilustración propia`,
        datos.grupos_bd.length > 0 && datos.grupos_bd.every(id => !sinIlustracion.includes(id)), sinIlustracion);
    const malVista = ids.filter(id => !porClave[`musculo-${id}`].uso.includes(`/${VISTA_ESPERADA[id]}.svg#`));
    comprobar('cada grupo usa la vista correcta (frontal o posterior)', malVista.length === 0, malVista.map(id => `${id}: ${porClave[`musculo-${id}`].uso}`));
    const malMitad = ids.filter(id => !porClave[`musculo-${id}`].clases.includes(`ilustracion-${MITAD_ESPERADA[id]}`));
    comprobar('en la tarjeta se muestra la mitad del cuerpo donde está el músculo', malMitad.length === 0, malMitad);
    comprobar('en el detalle se muestra el cuerpo completo', ids.every(id => porClave[`musculo-${id}`].caja === '0 0 200 400'));
    const temasVistos = datos.temas.map((t, i) => porClave[`tema-${i + 1}`].dato);
    comprobar(`los ${datos.temas.length} temas tienen pictograma propio y distinto`,
        temasVistos.every(d => d.startsWith('tema:')) && new Set(temasVistos).size === datos.temas.length, temasVistos);
    comprobar('un grupo_id sin ilustración recibe la imagen de respaldo', porClave['respaldo-ejercicios'].dato === 'respaldo:ejercicios'
        && !porClave['respaldo-ejercicios'].estilo.includes('--ilu-'), porClave['respaldo-ejercicios']);
    comprobar('un tema sin ilustración recibe la imagen de respaldo', porClave['respaldo-articulos'].dato === 'respaldo:articulos');
    comprobar('ilustracion() con datos vacíos o extraños devuelve el respaldo, no un error',
        await js(`[ilustracion('ejercicios', null), ilustracion('ejercicios', 'abc'), ilustracion('articulos', null), ilustracion('articulos', ''), ilustracion('otro', 5)]
            .every(s => s.includes('data-ilustracion="respaldo:'))`));

    // ========================================================================= título accesible
    console.log('\n[Título accesible]');
    const acc = await n.js(`(() => { const svgs = [...document.querySelectorAll('svg.ilustracion')];
        const idsT = svgs.map(s => s.getAttribute('aria-labelledby'));
        return { n: svgs.length, ok: svgs.every(s => s.getAttribute('role') === 'img' && s.querySelector('title')?.id === s.getAttribute('aria-labelledby') && s.querySelector('title').textContent.trim().length > 5),
                 unicos: new Set(idsT).size === idsT.length }; })()`);
    comprobar(`las ${acc.n} ilustraciones tienen role="img" y un <title> enlazado con aria-labelledby`, acc.n === m.length * 2 && acc.ok);
    comprobar('los id de los títulos no se repiten', acc.unicos);
    comprobar('título de un músculo: "Músculo trabajado: pecho"', porClave['musculo-1'].titulo === 'Músculo trabajado: pecho', porClave['musculo-1'].titulo);
    comprobar('todos los músculos se titulan "Músculo trabajado: ..."', ids.every(id => /^Músculo trabajado: \S/.test(porClave[`musculo-${id}`].titulo)));
    comprobar('título de un tema: "Tema del artículo: fuerza"', porClave['tema-1'].titulo === `Tema del artículo: ${datos.temas[0].toLowerCase()}`, porClave['tema-1'].titulo);
    comprobar('un tema con HTML en el nombre se escapa en el título',
        await js(`(() => { const d = document.createElement('div'); d.innerHTML = ilustracion('articulos', '<img src=x onerror="window.__xss=1">'); return !d.querySelector('img') && window.__xss === undefined; })()`));

    // ========================================================================= archivos SVG
    console.log('\n[Archivos SVG: regiones con id y sin colores fijos]');
    const svg = await n.js(`Promise.all(['assets/anatomia/frontal.svg', 'assets/anatomia/posterior.svg', 'assets/temas/pictogramas.svg'].map(async u => {
        const r = await fetch(u), texto = await r.text(), doc = new DOMParser().parseFromString(texto, 'image/svg+xml');
        const pinturas = [...doc.querySelectorAll('*')].flatMap(e => [e.getAttribute('fill'), e.getAttribute('stroke'),
            ...(e.getAttribute('style') || '').split(';').filter(x => /^\\s*(fill|stroke)\\s*:/.test(x)).map(x => x.split(':').slice(1).join(':'))]).filter(Boolean).map(x => x.trim());
        return { u, tipo: r.headers.get('content-type'), error: !!doc.querySelector('parsererror'), grupos: [...doc.querySelectorAll('g[id]')].map(g => g.id),
                 fijos: [...new Set(pinturas.filter(x => x !== 'none' && x !== 'currentColor' && !/^var\\(--ilu-[a-z]+,\\s*(var\\(--ilu-base,\\s*)?currentColor\\)?\\)$/.test(x)))],
                 titulo: doc.querySelector('svg > title')?.textContent, texto: /<text[\\s>]/.test(texto) }; }))`);
    const [frontal, posterior, pictos] = svg;
    comprobar('los tres archivos son SVG bien formados y con <title>', svg.every(s => !s.error && s.tipo.includes('svg') && s.titulo), svg.map(s => [s.u, s.tipo, s.error]));
    comprobar('vista frontal: grupo "cuerpo" y una región con id por músculo', ['cuerpo', 'silueta', ...REGIONES.frontal].every(g => frontal.grupos.includes(g)), frontal.grupos);
    comprobar('vista posterior: grupo "cuerpo" y una región con id por músculo', ['cuerpo', 'silueta', ...REGIONES.posterior].every(g => posterior.grupos.includes(g)), posterior.grupos);
    const regionMala = await n.js(`Object.entries(Ilustraciones.MUSCULOS).filter(([id, mu]) => !(${JSON.stringify(REGIONES)}[mu.vista] || []).includes(mu.region)).map(([id]) => id)`);
    comprobar('la región de cada músculo en ilustraciones.js existe en el archivo de su vista', regionMala.length === 0, regionMala);
    comprobar('ningún archivo tiene colores fijos: solo variables CSS, currentColor o none', svg.every(s => s.fijos.length === 0), svg.map(s => s.fijos));
    comprobar('los pictogramas no llevan texto', !pictos.texto && !frontal.texto && !posterior.texto);

    // ========================================================================= sin enlaces externos
    console.log('\n[Ninguna imagen depende de un enlace externo]');
    const red = await n.js(`({ recursos: performance.getEntriesByType('resource').map(e => ({ url: e.name, estado: e.responseStatus })),
        usos: [...document.querySelectorAll('use')].map(u => u.getAttribute('href')), imagenes: document.querySelectorAll('img, image').length })`);
    const propios = red.recursos.filter(r => !r.url.endsWith('favicon.ico'));
    comprobar('todo lo que carga la galería sale de este mismo sitio y responde 200',
        propios.length >= 5 && propios.every(r => r.url.startsWith(BASE + '/') && r.estado === 200), propios.filter(r => !r.url.startsWith(BASE + '/') || r.estado !== 200));
    comprobar('las referencias <use> son rutas relativas a assets/', red.usos.every(u => /^assets\/(anatomia|temas)\/[a-z]+\.svg#[a-z-]+$/.test(u)), [...new Set(red.usos)]);
    comprobar('se cargan los tres archivos de dibujo', ['frontal.svg', 'posterior.svg', 'pictogramas.svg'].every(f => propios.some(r => r.url.includes(f))));

    // ========================================================================= capturas y píxeles
    const coloresDe = () => n.js(`(() => { const d = document.createElement('div'); document.body.appendChild(d);
        const leer = v => { d.style.color = 'var(' + v + ')'; return getComputedStyle(d).color.match(/[\\d.]+/g).slice(0, 3).map(Number); };
        const r = { fondo: leer('--color-ilustracion-fondo'), base: leer('--color-ilustracion-base'), resaltado: leer('--color-ilustracion-resaltado'), tinta: leer('--color-ilustracion-tinta') };
        d.remove(); return r; })()`);
    const cajas = () => n.js(`[...document.querySelectorAll('.muestra')].flatMap(f => [...f.querySelectorAll('[data-tamano]')].map(c => { const b = c.getBoundingClientRect();
        return { clave: f.dataset.muestra, tamano: c.dataset.tamano, x: b.left + scrollX, y: b.top + scrollY, width: b.width, height: b.height }; }))`);
    const galeria = () => n.js(`(() => { const b = document.getElementById('rejilla').getBoundingClientRect(); return { x: 0, y: 0, width: Math.ceil(b.right + 16), height: Math.ceil(b.bottom + scrollY + 16) }; })()`);

    const paletas = {};
    for (const [paleta, valor] of [['claro', 'light'], ['oscuro', 'dark']]) {
        console.log(`\n[Capturas en ${paleta}: el músculo resaltado se distingue]`);
        await n.tema(valor);
        await new Promise(r => setTimeout(r, 300));
        const c = paletas[paleta] = await coloresDe();
        comprobar(`${paleta}: contraste del resaltado con el resto del cuerpo de 3:1 o más`, contraste(c.resaltado, c.base) >= 3, contraste(c.resaltado, c.base).toFixed(2));
        comprobar(`${paleta}: contraste del resaltado con el fondo de 3:1 o más`, contraste(c.resaltado, c.fondo) >= 3, contraste(c.resaltado, c.fondo).toFixed(2));
        comprobar(`${paleta}: el cuerpo atenuado se distingue del fondo`, contraste(c.base, c.fondo) >= 1.5, contraste(c.base, c.fondo).toFixed(2));
        comprobar(`${paleta}: contraste del trazo de los pictogramas con el fondo de 3:1 o más`, contraste(c.tinta, c.fondo) >= 3, contraste(c.tinta, c.fondo).toFixed(2));

        const lista = await cajas();
        // Los SVG se cargan con <use>: se espera a que la primera ilustración ya esté pintada
        for (let i = 0; i < 50; i++) {
            if (contarColor(leerPNG(await n.foto(lista[0])), c.resaltado) > 50) break;
            await new Promise(r => setTimeout(r, 200));
        }
        await n.captura(`galeria-${paleta}`, { carpeta, recorte: await galeria() });

        const medidas = {};
        for (const caja of lista) {
            const png = leerPNG(await n.foto(caja));
            if (carpeta) await n.captura(`${paleta}-${caja.clave}-${caja.tamano}`, { carpeta, recorte: caja });
            (medidas[caja.clave] ||= {})[caja.tamano] = {
                resaltado: contarColor(png, c.resaltado), base: contarColor(png, c.base), tinta: contarColor(png, c.tinta),
                fondo: contarColor(png, c.fondo), total: png.ancho * png.alto,
            };
        }
        for (const id of ids) {
            const t = medidas[`musculo-${id}`].tarjeta, d = medidas[`musculo-${id}`].detalle;
            comprobar(`${paleta} · grupo ${id} (${porClave[`musculo-${id}`].titulo.split(': ')[1]}): resaltado ${t.resaltado} px en tarjeta y ${d.resaltado} px en detalle, resto atenuado`,
                t.resaltado >= MIN_RESALTADO.tarjeta && d.resaltado >= MIN_RESALTADO.detalle && t.base > t.resaltado * 0.5 && d.base > d.resaltado * 0.5, { t, d });
        }
        const proporciones = ids.map(id => medidas[`musculo-${id}`].detalle).map(d => d.resaltado / (d.resaltado + d.base));
        comprobar(`${paleta}: el resaltado nunca ocupa más de la mitad de la figura (no se pinta todo el cuerpo)`, Math.max(...proporciones) < 0.5, proporciones.map(p => p.toFixed(2)));
        const re = medidas['respaldo-ejercicios'];
        comprobar(`${paleta} · respaldo de ejercicios: cuerpo sin ninguna región resaltada`, re.tarjeta.resaltado === 0 && re.detalle.resaltado === 0 && re.detalle.base > 3000, re);
        datos.temas.forEach((nombre, i) => {
            const t = medidas[`tema-${i + 1}`].tarjeta, d = medidas[`tema-${i + 1}`].detalle;
            comprobar(`${paleta} · tema ${nombre}: pictograma visible (${t.tinta + t.resaltado} px en tarjeta, ${d.tinta + d.resaltado} px en detalle)`,
                t.tinta + t.resaltado >= 300 && d.tinta + d.resaltado >= 800, { t, d });
        });
        const ra = medidas['respaldo-articulos'];
        comprobar(`${paleta} · respaldo de artículos: pictograma visible`, ra.tarjeta.tinta >= 200 && ra.detalle.tinta >= 500, ra);
        comprobar(`${paleta}: el fondo del recuadro es el de la variable CSS en todas las capturas`,
            Object.values(medidas).every(x => x.tarjeta.fondo > x.tarjeta.total * 0.5 && x.detalle.fondo > x.detalle.total * 0.4));
        if (paleta === 'oscuro') {
            comprobar('oscuro: los cuatro colores de las ilustraciones cambiaron respecto al claro',
                ['fondo', 'base', 'resaltado', 'tinta'].every(k => String(paletas.claro[k]) !== String(paletas.oscuro[k])), paletas);
        }
    }

    // ========================================================================= ningún color fijo
    // Tercera pasada con una paleta de prueba de colores inconfundibles. Cada píxel de cada
    // captura debe ser uno de los cuatro o una mezcla de dos o tres de ellos (el suavizado
    // de los bordes). Un color fijo en cualquier dibujo dejaría píxeles sin explicar.
    // (Comparar claro con oscuro no sirve: los dos temas comparten grises parecidos.)
    console.log('\n[Ningún color fijo: todo se pinta con las variables CSS]');
    await n.tema('light');
    const PRUEBA = { fondo: [255, 255, 0], base: [0, 200, 0], resaltado: [255, 0, 128], tinta: [0, 128, 255] };
    await n.js(`(() => { const hex = c => '#' + c.map(v => v.toString(16).padStart(2, '0')).join('');
        for (const [k, c] of Object.entries(${JSON.stringify(PRUEBA)})) document.documentElement.style.setProperty('--color-ilustracion-' + k, hex(c));
        // Esquinas rectas: en las redondeadas asoma el color de la tarjeta, que no es del dibujo
        document.documentElement.style.setProperty('--radio-m', '0px'); })()`);
    await new Promise(r => setTimeout(r, 300));
    comprobar('la paleta de prueba se aplicó solo cambiando las variables --color-ilustracion-*', JSON.stringify(await coloresDe()) === JSON.stringify(PRUEBA), await coloresDe());
    await n.captura('galeria-paleta-de-prueba', { carpeta, recorte: await galeria() });

    const colores = Object.values(PRUEBA);
    const pares = colores.flatMap((a, i) => colores.slice(i + 1).map(b => [a, b]));
    const trios = colores.flatMap((a, i) => colores.slice(i + 1).flatMap((b, k) => colores.slice(i + k + 2).map(c => [a, b, c])));
    const TOL = 16;
    const resta = (u, v) => [u[0] - v[0], u[1] - v[1], u[2] - v[2]];
    const punto = (u, v) => u[0] * v[0] + u[1] * v[1] + u[2] * v[2];
    /** ¿El color p es de la paleta, o una mezcla de dos o tres colores de la paleta? */
    function explicado(p) {
        if (colores.some(c => Math.abs(p[0] - c[0]) <= TOL && Math.abs(p[1] - c[1]) <= TOL && Math.abs(p[2] - c[2]) <= TOL)) return true;
        for (const [a, b] of pares) {                       // sobre el segmento a-b
            const d = resta(b, a), q = resta(p, a), t = Math.max(0, Math.min(1, punto(q, d) / punto(d, d)));
            if (Math.hypot(q[0] - t * d[0], q[1] - t * d[1], q[2] - t * d[2]) <= TOL) return true;
        }
        for (const [a, b, c] of trios) {                    // dentro del triángulo a-b-c
            const e1 = resta(b, a), e2 = resta(c, a), q = resta(p, a);
            const d11 = punto(e1, e1), d12 = punto(e1, e2), d22 = punto(e2, e2), q1 = punto(q, e1), q2 = punto(q, e2), det = d11 * d22 - d12 * d12;
            const u = (d22 * q1 - d12 * q2) / det, v = (d11 * q2 - d12 * q1) / det;
            if (u < -0.02 || v < -0.02 || u + v > 1.02) continue;
            if (Math.hypot(q[0] - u * e1[0] - v * e2[0], q[1] - u * e1[1] - v * e2[1], q[2] - u * e1[2] - v * e2[2]) <= TOL) return true;
        }
        return false;
    }
    // El detector debe reconocer como ajenos los colores que más probablemente quedarían fijos
    const SOSPECHOSOS = { negro: [0, 0, 0], blanco: [255, 255, 255], 'gris medio': [128, 128, 128], 'gris claro': [200, 200, 200],
        ...Object.fromEntries(Object.entries(paletas.claro).map(([k, c]) => [`${k} del tema claro`, c])),
        ...Object.fromEntries(Object.entries(paletas.oscuro).map(([k, c]) => [`${k} del tema oscuro`, c])) };
    const noDetectados = Object.entries(SOSPECHOSOS).filter(([, c]) => explicado(c)).map(([k]) => k);
    comprobar(`el detector distingue de la paleta de prueba ${Object.keys(SOSPECHOSOS).length} colores que podrían quedar fijos (negro, blanco, grises y los de los dos temas)`,
        noDetectados.length === 0, noDetectados);

    const conFijos = [];
    let peor = 0;
    for (const caja of await cajas()) {
        const png = leerPNG(await n.foto(caja));
        let malos = 0;
        for (let k = 0; k < png.datos.length; k += png.canales) {
            if (!explicado([png.datos[k], png.datos[k + 1], png.datos[k + 2]])) malos++;
        }
        const fraccion = malos / (png.ancho * png.alto);
        peor = Math.max(peor, fraccion);
        // Margen del 0.05 % para ruido de redondeo; un detalle de color fijo ocupa mucho más
        if (fraccion > 0.0005) conFijos.push(`${caja.clave} ${caja.tamano}: ${malos} px`);
        if (carpeta && caja.clave === 'musculo-1') await n.captura(`prueba-${caja.clave}-${caja.tamano}`, { carpeta, recorte: caja });
    }
    comprobar(`las ${m.length * 2} capturas solo contienen los colores de las variables (peor caso: ${(peor * 100).toFixed(3)} % de píxeles sin explicar)`,
        conFijos.length === 0, conFijos);
    const muestraPrueba = leerPNG(await n.foto((await cajas()).find(c => c.clave === 'musculo-1' && c.tamano === 'detalle')));
    comprobar('con la paleta de prueba el pecho se pinta con el color de resaltado y el resto con el de base',
        contarColor(muestraPrueba, PRUEBA.resaltado) >= MIN_RESALTADO.detalle && contarColor(muestraPrueba, PRUEBA.base) > 3000,
        { resaltado: contarColor(muestraPrueba, PRUEBA.resaltado), base: contarColor(muestraPrueba, PRUEBA.base) });

    if (carpeta) console.log(`\n  capturas guardadas en ${carpeta}`);
} catch (e) {
    comprobar('la prueba terminó sin errores', false, e.message);
}

console.log(`\n${informe.total} comprobaciones de ilustraciones, ${informe.fallos} fallos`);
await n.cerrar(informe.fallos === 0 ? 0 : 1);

function js(expresion) { return n.js(expresion); }
