// assets/ilustraciones.js — ilustración de cada documento.
//
//   ilustracion('ejercicios', grupo_id)   cuerpo con ese grupo muscular resaltado
//   ilustracion('articulos', tema)        pictograma del tema del árbol de Temas
//   ilustracion(origen, clave, { encuadre: 'medio' })
//                                         igual, pero el cuerpo se acerca a la mitad (superior
//                                         o inferior) donde está el músculo: para las tarjetas
//
// Devuelve el marcado de un <svg> con título accesible ("Músculo trabajado: pecho").
// Si el grupo o el tema no tienen ilustración, devuelve una imagen de respaldo.
//
// Los dibujos son propios y están en este mismo sitio (assets/anatomia/ y assets/temas/):
// ninguna imagen depende de un enlace externo. Aquí solo se elige cuál mostrar:
//   - el cuerpo se toma de frontal.svg o posterior.svg con <use>, y la región se resalta
//     con una variable CSS (--ilu-<region>) que ese archivo lee;
//   - los colores salen de las variables de assets/estilos.css (--color-ilustracion-*),
//     nunca van fijos, así que cambian solos con el tema de la interfaz.
(function (global) {
    'use strict';

    const RUTA_ANATOMIA = 'assets/anatomia/';
    const RUTA_TEMAS = 'assets/temas/pictogramas.svg';

    // grupo_id (taxonomia.MUSCULOS y tabla grupos_musculares) -> vista y región del SVG.
    // `region` es el id del grupo dentro de frontal.svg / posterior.svg; `mitad` es la parte
    // del cuerpo que se muestra con el encuadre 'medio'.
    const MUSCULOS = {
        1:  { nombre: 'pecho',          vista: 'frontal',   region: 'pecho',          mitad: 'superior' },
        2:  { nombre: 'espalda',        vista: 'posterior', region: 'espalda',        mitad: 'superior' },
        3:  { nombre: 'hombro',         vista: 'frontal',   region: 'hombro',         mitad: 'superior' },
        4:  { nombre: 'bíceps',         vista: 'frontal',   region: 'biceps',         mitad: 'superior' },
        5:  { nombre: 'tríceps',        vista: 'posterior', region: 'triceps',        mitad: 'superior' },
        6:  { nombre: 'cuádriceps',     vista: 'frontal',   region: 'cuadriceps',     mitad: 'inferior' },
        7:  { nombre: 'isquiotibiales', vista: 'posterior', region: 'isquiotibiales', mitad: 'inferior' },
        8:  { nombre: 'pantorrilla',    vista: 'posterior', region: 'pantorrilla',    mitad: 'inferior' },
        9:  { nombre: 'glúteo',         vista: 'posterior', region: 'gluteo',         mitad: 'inferior' },
        10: { nombre: 'abdomen',        vista: 'frontal',   region: 'abdomen',        mitad: 'superior' },
        11: { nombre: 'antebrazos',     vista: 'frontal',   region: 'antebrazos',     mitad: 'superior' },
    };

    // Recortes del lienzo 200 x 400. Las dos mitades miden lo mismo (140 x 242), así que el
    // cuerpo se ve a la misma escala en todas las tarjetas. El lado por donde se corta la
    // figura coincide con el borde del recuadro; el otro lado lleva un pequeño margen.
    const ENCUADRES = {
        completo: '0 0 200 400',
        superior: '30 -8 140 242',      // de la cabeza a las manos; se corta abajo (y = 234)
        inferior: '30 158 140 242',     // de la cintura a los pies; se corta arriba (y = 158)
    };

    // Tema del árbol de Temas (sin acentos, en minúsculas) -> id del pictograma (tema-<id>).
    const TEMAS = {
        'fuerza': 'fuerza',
        'hipertrofia': 'hipertrofia',
        'resistencia': 'resistencia',
        'tecnica y biomecanica': 'tecnica',
        'planificacion': 'planificacion',
        'recuperacion': 'recuperacion',
        'prevencion y movilidad': 'prevencion',
        'alimentacion': 'alimentacion',
        'suplementacion': 'suplementacion',
    };

    let siguienteId = 0;

    function esc(t) {
        return String(t == null ? '' : t).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    }

    function normalizar(t) {
        return String(t == null ? '' : t).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/\s+/g, ' ').trim();
    }

    function svg(clase, cajaVista, dato, titulo, estilo, referencia) {
        const id = 'ilu-' + (++siguienteId);
        return `<svg class="ilustracion ${clase}" viewBox="${cajaVista}" role="img" aria-labelledby="${id}" data-ilustracion="${esc(dato)}"${
            estilo ? ` style="${estilo}"` : ''}><title id="${id}">${esc(titulo)}</title><use href="${referencia}"></use></svg>`;
    }

    function cuerpo(vista, region, encuadre, dato, titulo) {
        return svg(`ilustracion-cuerpo ilustracion-${encuadre}`, ENCUADRES[encuadre], dato, titulo,
            region ? `--ilu-${region}:var(--ilu-resaltado)` : '', `${RUTA_ANATOMIA}${vista}.svg#cuerpo`);
    }

    function pictograma(id, dato, titulo) {
        return svg('ilustracion-pictograma', '0 0 48 48', dato, titulo, '', `${RUTA_TEMAS}#tema-${id}`);
    }

    /**
     * Marcado SVG de la ilustración de un documento.
     * @param {string} origen 'ejercicios' o 'articulos'
     * @param {number|string|null} clave grupo_id del ejercicio o nombre del tema del artículo
     * @param {{encuadre?: 'completo'|'medio'}} [opciones] 'medio' acerca el cuerpo a la mitad
     *        donde está el músculo (para tamaños pequeños, como las tarjetas)
     */
    function ilustracion(origen, clave, opciones) {
        const medio = !!opciones && opciones.encuadre === 'medio';
        if (origen === 'ejercicios') {
            const m = MUSCULOS[Number(clave)];
            return m
                ? cuerpo(m.vista, m.region, medio ? m.mitad : 'completo', `musculo:${Number(clave)}`, `Músculo trabajado: ${m.nombre}`)
                : cuerpo('frontal', null, medio ? 'superior' : 'completo', 'respaldo:ejercicios', 'Ejercicio sin grupo muscular asignado');
        }
        const tema = TEMAS[normalizar(clave)];
        return tema
            ? pictograma(tema, `tema:${tema}`, `Tema del artículo: ${String(clave).trim().toLowerCase()}`)
            : pictograma('respaldo', 'respaldo:articulos', 'Artículo sin tema asignado');
    }

    const publico = { ilustracion, MUSCULOS, TEMAS, ENCUADRES };
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = publico;            // para poder revisarlo desde Node
    }
    global.Ilustraciones = publico;
    global.ilustracion = ilustracion;
})(typeof window !== 'undefined' ? window : globalThis);
