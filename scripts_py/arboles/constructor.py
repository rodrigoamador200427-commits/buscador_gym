"""Construye los dos árboles a partir de filas (dicts) de ejercicios y artículos.

Las filas pueden venir de MySQL (producción, con los IDs reales) o de los CSV
(pruebas). El constructor no sabe de dónde vienen: solo exige las claves
documentadas abajo.
"""
from .nodo import Arbol
from .taxonomia import (
    MUSCULOS, REGIONES, TEMAS, SIN_CLASIFICAR,
    nombre_equipamiento, separar_etiquetas, temas_del_articulo,
)


def construir_arbol_anatomia(ejercicios):
    """ejercicios: filas con id, nombre_es, grupo_id, equipamiento, modalidad, nivel.

    Cuerpo humano > Región > Músculo > Equipamiento > Ejercicio.
    Devuelve el Arbol; las filas con grupo_id desconocido van a arbol.meta['descartados'].
    """
    arbol = Arbol("anatomia", "Cuerpo humano")
    musculos, descartados = {}, []

    for region, ids in REGIONES.items():
        nodo_region = arbol.agregar(region, arbol.raiz)
        for gid in ids:
            musculos[gid] = arbol.agregar(MUSCULOS[gid], nodo_region, {"grupo_id": gid})

    por_equipo = {}
    for fila in sorted(ejercicios, key=lambda f: int(f["id"])):
        gid = int(fila["grupo_id"])
        if gid not in musculos:
            descartados.append(int(fila["id"]))
            continue
        equipo = nombre_equipamiento(fila.get("equipamiento"))
        clave = (gid, equipo)
        if clave not in por_equipo:
            por_equipo[clave] = arbol.agregar(equipo, musculos[gid], {"equipamiento": equipo})
        hoja = arbol.agregar(fila["nombre_es"], por_equipo[clave], {
            "doc_id": int(fila["id"]), "origen": "ejercicios",
            "modalidad": fila.get("modalidad"), "nivel": fila.get("nivel"),
        })
        arbol.doc_a_nodo[("ejercicios", int(fila["id"]))] = hoja

    for nodo in musculos.values():
        arbol.ordenar_hijos(nodo)       # equipamiento en orden alfabético, estable
    arbol.meta["musculos"] = musculos   # grupo_id -> Nodo
    arbol.meta["descartados"] = descartados
    return arbol


def construir_arbol_temas(articulos):
    """articulos: filas con id, titulo, etiquetas ('a, b, c').

    Conocimiento > Rama > Tema > Artículo. Cada artículo cuelga de UN tema (el de
    mayor coincidencia de etiquetas); sus demás temas quedan como enlaces cruzados.
    """
    arbol = Arbol("temas", "Conocimiento")
    ramas, temas = {}, {}
    for rama, tema, tags in TEMAS:
        if rama not in ramas:
            ramas[rama] = arbol.agregar(rama, arbol.raiz)
        temas[tema] = arbol.agregar(tema, ramas[rama], {"etiquetas": tags})

    sin_clasificar = None
    for fila in sorted(articulos, key=lambda f: int(f["id"])):
        etiquetas = separar_etiquetas(fila["etiquetas"])
        candidatos = temas_del_articulo(etiquetas)
        if candidatos:
            padre = temas[candidatos[0]]
        else:
            if sin_clasificar is None:
                sin_clasificar = arbol.agregar(SIN_CLASIFICAR, arbol.raiz)
            padre = sin_clasificar
        hoja = arbol.agregar(fila["titulo"], padre, {
            "doc_id": int(fila["id"]), "origen": "articulos", "etiquetas": etiquetas,
        })
        arbol.doc_a_nodo[("articulos", int(fila["id"]))] = hoja

    arbol.meta["temas"] = temas         # nombre del tema -> Nodo
    arbol.meta["sin_clasificar"] = sin_clasificar
    return arbol
