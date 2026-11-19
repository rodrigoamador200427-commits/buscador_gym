"""Construye los dos árboles a partir de filas (dicts) de ejercicios y artículos.

Las filas pueden venir de MySQL (producción, con los IDs reales) o de los CSV
(pruebas). El constructor no sabe de dónde vienen: solo exige las claves
documentadas abajo.
"""
from .nodo import Arbol
from .patrones import GRUPOS_PATRON, NOMBRE_RAIZ as RAIZ_PATRON, patron_de_nombre
from .taxonomia import (
    CATEGORIA_DE_EQUIPAMIENTO_DESCONOCIDO, CATEGORIAS_EQUIPAMIENTO, MUSCULOS, NIVELES,
    NIVELES_ORDEN, REGIONES, SIN_CLASIFICAR, SIN_EQUIPAMIENTO, TEMAS,
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
    arbol.meta["conceptos"] = musculos  # lo que una consulta o un menú puede nombrar
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
    arbol.meta["conceptos"] = temas
    arbol.meta["sin_clasificar"] = sin_clasificar
    return arbol


def construir_arbol_equipamiento(ejercicios):
    """Equipamiento > Categoría > Equipamiento > Ejercicio (hoja). Altura 3.

    ejercicios: filas con id, nombre_es, equipamiento (y opcionalmente grupo_id, nivel, modalidad).
    La estructura sale de taxonomia.CATEGORIAS_EQUIPAMIENTO y existe aunque no haya ejercicios
    (Banco, Paralelas y Correas solo los nombran los artículos). Un valor de la columna que la
    taxonomía no conoce crea su propio nodo al final de la categoría «Otros»; un valor vacío va a
    «Sin especificar». Los artículos no son hojas: se enlazan por etiquetas (ver bosque.py).
    """
    arbol = Arbol("equipamiento", "Equipamiento")
    categorias, equipos = {}, {}
    for categoria, nombres in CATEGORIAS_EQUIPAMIENTO:
        categorias[categoria] = arbol.agregar(categoria, arbol.raiz)
        for nombre in nombres:
            equipos[nombre] = arbol.agregar(nombre, categorias[categoria], {"equipamiento": nombre})

    for fila in sorted(ejercicios, key=lambda f: int(f["id"])):
        nombre = nombre_equipamiento(fila.get("equipamiento"))
        if nombre not in equipos:
            equipos[nombre] = arbol.agregar(nombre, categorias[CATEGORIA_DE_EQUIPAMIENTO_DESCONOCIDO],
                                            {"equipamiento": nombre})
        hoja = arbol.agregar(fila["nombre_es"], equipos[nombre], {
            "doc_id": int(fila["id"]), "origen": "ejercicios",
            "modalidad": fila.get("modalidad"), "nivel": fila.get("nivel"),
        })
        arbol.doc_a_nodo[("ejercicios", int(fila["id"]))] = hoja

    arbol.meta["categorias"] = categorias
    arbol.meta["equipamientos"] = equipos   # nombre -> Nodo
    arbol.meta["conceptos"] = equipos
    return arbol


def construir_arbol_nivel(ejercicios):
    """Nivel de experiencia > Nivel > Ejercicio (hoja). Altura 2.

    Los tres niveles existen siempre (Principiante, Intermedio, Avanzado, en ese orden); los
    ejercicios sin nivel reconocible cuelgan de «Sin especificar», que solo se crea si hace falta.
    Está muy desbalanceado en los datos reales (casi todo es Intermedio): el reporte lo dice.
    """
    arbol = Arbol("nivel", "Nivel de experiencia")
    niveles = {n: arbol.agregar(n, arbol.raiz, {"nivel": n}) for n in NIVELES_ORDEN}
    sin_nivel = None
    for fila in sorted(ejercicios, key=lambda f: int(f["id"])):
        valor = fila.get("nivel")
        nombre = NIVELES.get(valor.strip()) if isinstance(valor, str) else None
        if nombre is None:
            if sin_nivel is None:
                sin_nivel = arbol.agregar(SIN_EQUIPAMIENTO, arbol.raiz, {"nivel": SIN_EQUIPAMIENTO})
            padre = sin_nivel
        else:
            padre = niveles[nombre]
        hoja = arbol.agregar(fila["nombre_es"], padre, {
            "doc_id": int(fila["id"]), "origen": "ejercicios",
            "modalidad": fila.get("modalidad"), "nivel": fila.get("nivel"),
        })
        arbol.doc_a_nodo[("ejercicios", int(fila["id"]))] = hoja

    arbol.meta["niveles"] = niveles         # nombre -> Nodo (solo los tres niveles reales)
    # «Sin especificar» también es un nodo con aristas, así que cuenta como concepto (los menús lo
    # muestran), aunque las consultas no lo pueden nombrar.
    arbol.meta["conceptos"] = {**niveles, SIN_EQUIPAMIENTO: sin_nivel} if sin_nivel else niveles
    arbol.meta["sin_nivel"] = sin_nivel
    return arbol


def construir_arbol_patron(ejercicios):
    """Patrón de movimiento > Grupo > Patrón > Ejercicio (hoja). Altura 3. CLASIFICACIÓN APROXIMADA.

    El patrón sale de reglas de palabras clave sobre `nombre_es` (ver arboles/patrones.py). Todos los
    grupos y patrones existen siempre; lo que ninguna regla reconoce cuelga de «Sin clasificar» (hijo
    de la raíz) y NO se adivina. meta['aproximado'] = True; meta['sin_clasificar_ids'] lista esos ejercicios.
    """
    arbol = Arbol("patron", RAIZ_PATRON)
    grupos, patrones = {}, {}
    for grupo, nombres in GRUPOS_PATRON:
        grupos[grupo] = arbol.agregar(grupo, arbol.raiz)
        for nombre in nombres:
            patrones[nombre] = arbol.agregar(nombre, grupos[grupo], {"patron": nombre})
    sin_clasificar = arbol.agregar(SIN_CLASIFICAR, arbol.raiz, {"patron": SIN_CLASIFICAR})

    sin_ids = []
    for fila in sorted(ejercicios, key=lambda f: int(f["id"])):
        patron = patron_de_nombre(fila["nombre_es"])
        padre = patrones[patron] if patron else sin_clasificar
        if not patron:
            sin_ids.append(int(fila["id"]))
        hoja = arbol.agregar(fila["nombre_es"], padre, {
            "doc_id": int(fila["id"]), "origen": "ejercicios",
            "modalidad": fila.get("modalidad"), "nivel": fila.get("nivel"),
        })
        arbol.doc_a_nodo[("ejercicios", int(fila["id"]))] = hoja

    arbol.meta["grupos"] = grupos
    arbol.meta["patrones"] = patrones                 # nombre -> Nodo (los patrones reales)
    arbol.meta["sin_clasificar"] = sin_clasificar
    arbol.meta["sin_clasificar_ids"] = sin_ids
    # «Sin clasificar» también es un nodo con aristas y los menús lo muestran; las consultas no lo nombran
    arbol.meta["conceptos"] = {**patrones, SIN_CLASIFICAR: sin_clasificar}
    arbol.meta["aproximado"] = True
    return arbol
