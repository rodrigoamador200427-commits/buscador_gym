"""Etiquetas normalizadas de ejercicios y artículos, y ruta de cada documento en su árbol.

Lógica pura (sin BD) para poder probarla; generar_etiquetas.py la escribe en MySQL.

- Clave (nombre_normalizado): minúsculas, sin acentos ni espacios repetidos, con los
  sinónimos de taxonomia.SINONIMOS_ETIQUETA y los plurales simples unidos al singular.
- Ejercicios: músculo (grupo_id), equipamiento, nivel y modalidad, con los nombres en
  español de taxonomia.py.
- Artículos: su columna `etiquetas`. Tipo musculo/equipamiento si la clave está en los
  diccionarios de taxonomia.py; si no, tema.
- Si una clave aparece con dos tipos, gana el de mayor prioridad (PRIORIDAD_TIPO).
"""
import re
from collections import Counter, defaultdict

from arboles.taxonomia import (
    EQUIPAMIENTO, EQUIPAMIENTO_SIN_ETIQUETA, MODALIDADES, MUSCULOS, NIVELES,
    SINONIMOS_ETIQUETA, TERMINOS_EQUIPAMIENTO, TERMINOS_MUSCULO, normalizar, separar_etiquetas,
    ALIAS_MUSCULO, ETIQUETA_A_MUSCULO, TEMAS, VOCABULARIO_EXTRA,
)

PRIORIDAD_TIPO = ["musculo", "equipamiento", "nivel", "modalidad", "tema"]
MAX_NOMBRE = 80          # etiquetas.nombre_* son VARCHAR(80)
MAX_RUTA = 255           # documento_rutas.ruta es VARCHAR(255)
_PALABRA = re.compile(r"[^\W\d_]+", re.UNICODE)


def clave(texto):
    """Forma normalizada de una etiqueta, antes de unir plurales."""
    k = re.sub(r"\s+", " ", normalizar(texto)).strip()
    return SINONIMOS_ETIQUETA.get(k, k)


def vocabulario_controlado():
    """Etiquetas permitidas en los artículos generados, normalizadas con clave().

    Vocabulario de taxonomia.py (etiquetas que definen cada tema, términos de músculo y de
    equipamiento, niveles, modalidades y sinónimos) más VOCABULARIO_EXTRA. Devuelve
    {clave: tipo} con tipo en tema, musculo, equipamiento, nivel, modalidad o extra.
    """
    voc = {}
    for _, _, etiquetas in TEMAS:
        for t in etiquetas:
            voc.setdefault(clave(t), "tema")
    for t in ETIQUETA_A_MUSCULO:
        voc.setdefault(clave(t), "musculo")
    for t in list(MUSCULOS.values()) + list(TERMINOS_MUSCULO) + list(ALIAS_MUSCULO):
        voc.setdefault(clave(t), "musculo")
    for t in list(EQUIPAMIENTO.values()) + list(TERMINOS_EQUIPAMIENTO):
        voc.setdefault(clave(t), "equipamiento")
    for t in NIVELES.values():
        voc.setdefault(clave(t), "nivel")
    for t in MODALIDADES.values():
        voc.setdefault(clave(t), "modalidad")
    for t in VOCABULARIO_EXTRA:
        voc.setdefault(clave(t), "extra")
    for t in SINONIMOS_ETIQUETA:
        voc.setdefault(clave(t), voc.get(SINONIMOS_ETIQUETA[t], "extra"))
    return voc


def unir_plurales(claves):
    """{clave: canónica}. 'rodillas' -> 'rodilla' solo si 'rodilla' también existe."""
    claves = set(claves)
    canon = {}
    for k in claves:
        if k.endswith("s") and k[:-1] in claves:
            canon[k] = k[:-1]
        elif k.endswith("es") and k[:-2] in claves:
            canon[k] = k[:-2]
        else:
            canon[k] = k
    return canon


def formas_con_acento(textos):
    """{palabra normalizada: forma más frecuente en los textos}. Sirve para recuperar los
    acentos que las etiquetas de los artículos no traen ('sueno' -> 'sueño')."""
    cuenta = defaultdict(Counter)
    for t in textos:
        for p in _PALABRA.findall(str(t or "").lower()):
            cuenta[normalizar(p)][p] += 1
    # Más frecuente; en empate, la que tiene acento (más larga en bytes) y luego alfabética
    return {n: sorted(c.items(), key=lambda x: (-x[1], -len(x[0].encode()), x[0]))[0][0]
            for n, c in cuenta.items()}


def _visible_desde_texto(k, formas):
    v = " ".join(formas.get(p, p) for p in k.split(" "))
    return v[:1].upper() + v[1:]


def construir_etiquetas(ejercicios, articulos, textos=()):
    """Devuelve (etiquetas, asignaciones).

    etiquetas: {clave: {"visible": str, "tipo": str}}
    asignaciones: set de (origen, doc_id, clave)
    """
    candidatos = []   # (origen, doc_id, clave, tipo, visible o None)

    for e in ejercicios:
        did = int(e["id"])
        gid = e.get("grupo_id")
        if gid is not None and int(gid) in MUSCULOS:
            nombre = MUSCULOS[int(gid)]
            candidatos.append(("ejercicios", did, clave(nombre), "musculo", nombre))
        equipo = (e.get("equipamiento") or "").strip()
        if equipo not in EQUIPAMIENTO_SIN_ETIQUETA and equipo in EQUIPAMIENTO:
            nombre = EQUIPAMIENTO[equipo]
            candidatos.append(("ejercicios", did, clave(nombre), "equipamiento", nombre))
        nivel = (e.get("nivel") or "").strip()
        if nivel in NIVELES:
            candidatos.append(("ejercicios", did, clave(NIVELES[nivel]), "nivel", NIVELES[nivel]))
        modalidad = (e.get("modalidad") or "").strip()
        if modalidad in MODALIDADES:
            nombre = MODALIDADES[modalidad]
            candidatos.append(("ejercicios", did, clave(nombre), "modalidad", nombre))

    claves_musculo = {clave(n) for n in MUSCULOS.values()} | {clave(t) for t in TERMINOS_MUSCULO}
    claves_equipo = {clave(n) for n in EQUIPAMIENTO.values()} | {clave(t) for t in TERMINOS_EQUIPAMIENTO}
    for a in articulos:
        did = int(a["id"])
        for t in separar_etiquetas(a.get("etiquetas")):
            k = clave(t)
            if not k or len(k) > MAX_NOMBRE:
                continue
            tipo = "musculo" if k in claves_musculo else "equipamiento" if k in claves_equipo else "tema"
            candidatos.append(("articulos", did, k, tipo, None))

    canon = unir_plurales(c[2] for c in candidatos)
    formas = formas_con_acento(textos)

    etiquetas, asignaciones = {}, set()
    for origen, did, k, tipo, visible in candidatos:
        k = canon[k]
        asignaciones.add((origen, did, k))
        actual = etiquetas.get(k)
        nuevo = {"tipo": tipo, "visible": visible}
        if actual is None:
            etiquetas[k] = nuevo
            continue
        # Tipo: el de mayor prioridad. Nombre visible: el de taxonomia.py si lo hay.
        if PRIORIDAD_TIPO.index(tipo) < PRIORIDAD_TIPO.index(actual["tipo"]):
            actual["tipo"] = tipo
        if actual["visible"] is None and visible is not None:
            actual["visible"] = visible

    for k, et in etiquetas.items():
        if et["visible"] is None:
            et["visible"] = _visible_desde_texto(k, formas)
        et["visible"] = et["visible"][:MAX_NOMBRE]
    return etiquetas, asignaciones


def construir_rutas(arbol_anatomia, arbol_temas):
    """{(origen, doc_id): (arbol, ruta)}; la ruta va de la raíz al padre de la hoja."""
    rutas = {}
    for arbol in (arbol_anatomia, arbol_temas):
        for (origen, did), hoja in arbol.doc_a_nodo.items():
            texto = " > ".join(n.nombre for n in hoja.ruta()[:-1])
            rutas[(origen, int(did))] = (arbol.nombre, texto[:MAX_RUTA])
    return rutas


def construir_rutas_arboles(arboles):
    """{(origen, doc_id, arbol): ruta} para cualquier lista de árboles (fase 6B).

    Un documento tiene UNA ruta por árbol en el que es hoja: un ejercicio, en anatomía,
    equipamiento y nivel; un artículo, en temas. La ruta va de la raíz al padre de la hoja."""
    rutas = {}
    for arbol in arboles:
        for (origen, did), hoja in arbol.doc_a_nodo.items():
            rutas[(origen, int(did), arbol.nombre)] = " > ".join(n.nombre for n in hoja.ruta()[:-1])[:MAX_RUTA]
    return rutas
