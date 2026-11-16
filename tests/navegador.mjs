// tests/navegador.mjs — maneja Edge (o Chrome) sin ventana para las pruebas de interfaz.
//
// Sin dependencias: habla con el navegador por el protocolo de DevTools usando el WebSocket
// que trae Node 22+. La ruta del navegador se puede cambiar con la variable EDGE_PATH.
// Lo usan tests/interfaz.mjs y tests/ilustraciones.mjs.
import { spawn } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

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
        const params = { format: 'png' };
        if (recorte) { params.clip = { ...recorte, scale: 1 }; params.captureBeyondViewport = true; }
        const r = await cdp('Page.captureScreenshot', params);
        writeFileSync(join(carpeta, nombre + '.png'), Buffer.from(r.data, 'base64'));
    }

    await cdp('Page.enable');
    await cdp('Runtime.enable');
    return {
        cdp, js, esperar, hasta, pantalla, ir, captura, cerrar,
        ENTER: () => tecla('Enter', 13, '\r'),
        TAB: () => tecla('Tab', 9),
        ESCAPE: () => tecla('Escape', 27),
    };
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
