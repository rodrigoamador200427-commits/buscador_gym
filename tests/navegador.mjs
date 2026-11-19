// tests/navegador.mjs — maneja Edge (o Chrome) sin ventana para las pruebas de interfaz.
//
// Sin dependencias: habla con el navegador por el protocolo de DevTools usando el WebSocket
// que trae Node 22+. La ruta del navegador se puede cambiar con la variable EDGE_PATH.
// Lo usan tests/interfaz.mjs y tests/ilustraciones.mjs.
import { spawn } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { inflateSync } from 'node:zlib';

const TOPE_MS = 5 * 60 * 1000;      // si algo se bloquea, la prueba termina en vez de colgarse
const ORDEN_MS = 30000;             // tiempo límite de cada orden al navegador

/**
 * Arranca el navegador y devuelve las funciones para manejarlo. Si no puede arrancar,
 * escribe "ABORTADO: ..." y termina el proceso con código 3.
 */
export async function abrirNavegador() {
    const EDGE = [process.env.EDGE_PATH,
        'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
        'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
        'C:/Program Files/Google/Chrome/Application/chrome.exe'].find(p => p && existsSync(p));
    if (!EDGE) { console.error('ABORTADO: no se encontró Edge ni Chrome (define EDGE_PATH)'); process.exit(3); }

    const perfilTmp = mkdtempSync(join(tmpdir(), 'bg-edge-'));
    const edge = spawn(EDGE, ['--headless=new', '--remote-debugging-port=0', `--user-data-dir=${perfilTmp}`,
        '--no-first-run', '--no-default-browser-check', '--disable-gpu', '--window-size=1280,900', 'about:blank'],
        { stdio: ['ignore', 'ignore', 'pipe'] });

    /** Cierra el navegador, borra su perfil temporal y termina el proceso con `codigo`. */
    function cerrar(codigo) {
        try { edge.kill(); } catch {}
        setTimeout(() => { try { rmSync(perfilTmp, { recursive: true, force: true, maxRetries: 10, retryDelay: 200 }); } catch {} process.exit(codigo); }, 500);
        return new Promise(() => {});          // quien la espera no sigue ejecutando
    }
    const abortar = e => { console.error('ABORTADO: ' + e.message); return cerrar(3); };

    const puerto = await new Promise((ok, mal) => {
        let buf = '';
        const t = setTimeout(() => mal(new Error('el navegador no abrió el puerto de depuración')), 20000);
        edge.stderr.on('data', d => {
            buf += d;
            const m = buf.match(/DevTools listening on ws:\/\/127\.0\.0\.1:(\d+)\//);
            if (m) { clearTimeout(t); ok(Number(m[1])); }
        });
        edge.on('exit', () => mal(new Error('el navegador terminó antes de tiempo')));
    }).catch(abortar);

    const paginas = await (await fetch(`http://127.0.0.1:${puerto}/json/list`)).json();
    const pagina = paginas.find(p => p.type === 'page');
    if (!pagina) await abortar(new Error('el navegador no abrió ninguna página'));
    const ws = new WebSocket(pagina.webSocketDebuggerUrl);
    await new Promise((ok, mal) => {
        ws.addEventListener('open', ok);
        ws.addEventListener('error', () => mal(new Error('no se pudo conectar con el navegador')));
        setTimeout(() => mal(new Error('el navegador no aceptó la conexión')), 20000);
    }).catch(abortar);

    setTimeout(() => { console.log(`  FALLO la prueba no terminó en ${TOPE_MS / 60000} minutos`); cerrar(1); }, TOPE_MS).unref();

    let seq = 0;
    const pendientes = new Map();
    ws.addEventListener('message', ev => {
        const m = JSON.parse(ev.data);
        if (m.id && pendientes.has(m.id)) { pendientes.get(m.id)(m); pendientes.delete(m.id); }
    });
    /** Envía una orden del protocolo de DevTools y devuelve su resultado. */
    function cdp(method, params = {}) {
        return new Promise((ok, mal) => {
            const id = ++seq;
            const t = setTimeout(() => { pendientes.delete(id); mal(new Error(`${method}: el navegador no respondió en ${ORDEN_MS / 1000} s`)); }, ORDEN_MS);
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
    /** Espera hasta que la expresión sea verdadera. Devuelve false si no ocurre a tiempo. */
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
    async function pantalla(ancho, alto, movil = false) {
        await cdp('Emulation.setDeviceMetricsOverride', { width: ancho, height: alto, deviceScaleFactor: 1, mobile: movil });
    }
    /** Abre una URL y espera a que termine de cargar. */
    async function ir(url) {
        await cdp('Page.navigate', { url });
        await hasta(`document.readyState === 'complete'`);
    }
    /**
     * Guarda una captura PNG. Sin `carpeta` usa la variable CAPTURAS; si tampoco existe, no
     * hace nada. `recorte` = {x, y, width, height} en píxeles de la página.
     */
    async function captura(nombre, { carpeta = process.env.CAPTURAS, recorte = null } = {}) {
        if (!carpeta) return;
        mkdirSync(carpeta, { recursive: true });
        writeFileSync(join(carpeta, nombre + '.png'), await foto(recorte));
    }
    /** Captura PNG en memoria (Buffer) de toda la ventana o de un `recorte` de la página. */
    async function foto(recorte = null) {
        const params = { format: 'png' };
        if (recorte) { params.clip = { ...recorte, scale: 1 }; params.captureBeyondViewport = true; }
        return Buffer.from((await cdp('Page.captureScreenshot', params)).data, 'base64');
    }
    /** Simula la preferencia de tema del sistema: 'dark', 'light' o '' para quitarla. */
    async function tema(valor) {
        await cdp('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: valor }] });
    }

    await cdp('Page.enable');
    await cdp('Runtime.enable');
    return {
        cdp, js, esperar, hasta, pantalla, ir, captura, foto, tema, cerrar,
        ENTER: () => tecla('Enter', 13, '\r'),
        TAB: () => tecla('Tab', 9),
        ESCAPE: () => tecla('Escape', 27),
        ABAJO: () => tecla('ArrowDown', 40),
        /** Escribe texto en el elemento con el foco, como lo haría el teclado (sin tocar el ratón). */
        ESCRIBIR: texto => cdp('Input.insertText', { text: texto }),
    };
}

/**
 * Decodifica un PNG de 8 bits RGB o RGBA sin entrelazar (el formato de las capturas) para
 * poder contar píxeles. Devuelve { ancho, alto, canales, datos }.
 */
export function leerPNG(buf) {
    let p = 8, ancho = 0, alto = 0, bits = 0, tipo = 0;
    const idat = [];
    while (p < buf.length) {
        const largo = buf.readUInt32BE(p), nombre = buf.toString('ascii', p + 4, p + 8), d = buf.subarray(p + 8, p + 8 + largo);
        if (nombre === 'IHDR') {
            ancho = d.readUInt32BE(0); alto = d.readUInt32BE(4); bits = d[8]; tipo = d[9];
            if (d[12] !== 0) throw new Error('PNG entrelazado: no se admite');
        } else if (nombre === 'IDAT') idat.push(d);
        else if (nombre === 'IEND') break;
        p += 12 + largo;
    }
    if (bits !== 8 || (tipo !== 6 && tipo !== 2)) throw new Error(`PNG no admitido (bits ${bits}, tipo ${tipo})`);
    const canales = tipo === 6 ? 4 : 3, fila = ancho * canales, crudo = inflateSync(Buffer.concat(idat)), datos = Buffer.alloc(alto * fila);
    for (let y = 0; y < alto; y++) {
        const filtro = crudo[y * (fila + 1)], base = y * (fila + 1) + 1, sal = y * fila;
        for (let x = 0; x < fila; x++) {
            const a = x >= canales ? datos[sal + x - canales] : 0;
            const b = y > 0 ? datos[sal - fila + x] : 0;
            const c = x >= canales && y > 0 ? datos[sal - fila + x - canales] : 0;
            let v = crudo[base + x];
            if (filtro === 1) v += a;
            else if (filtro === 2) v += b;
            else if (filtro === 3) v += (a + b) >> 1;
            else if (filtro === 4) { const pa = Math.abs(b - c), pb = Math.abs(a - c), pc = Math.abs(a + b - 2 * c); v += pa <= pb && pa <= pc ? a : pb <= pc ? b : c; }
            datos[sal + x] = v & 255;
        }
    }
    return { ancho, alto, canales, datos };
}

/** Cuántos píxeles de la imagen tienen ese color [r, g, b], con una tolerancia por canal. */
export function contarColor(png, [r, g, b], tolerancia = 10) {
    let n = 0;
    for (let i = 0; i < png.datos.length; i += png.canales) {
        if (Math.abs(png.datos[i] - r) <= tolerancia && Math.abs(png.datos[i + 1] - g) <= tolerancia && Math.abs(png.datos[i + 2] - b) <= tolerancia) n++;
    }
    return n;
}

/** Contraste WCAG entre dos colores [r, g, b] (de 1 a 21). */
export function contraste(c1, c2) {
    const lum = c => { const [r, g, b] = c.map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
    const [a, b] = [lum(c1), lum(c2)].sort((x, y) => y - x);
    return (a + 0.05) / (b + 0.05);
}

/** Contador de comprobaciones con el mismo formato que las pruebas PHP. */
export function crearInforme() {
    const informe = {
        total: 0,
        fallos: 0,
        comprobar(nombre, ok, detalle = '') {
            informe.total++;
            if (!ok) informe.fallos++;
            console.log((ok ? '  OK    ' : '  FALLO ') + nombre
                + (ok || detalle === '' ? '' : `  -> ${typeof detalle === 'string' ? detalle : JSON.stringify(detalle)}`));
        },
    };
    return informe;
}
