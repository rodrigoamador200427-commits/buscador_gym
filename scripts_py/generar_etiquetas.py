"""Llena (o regenera) etiquetas, documento_etiquetas y documento_rutas.

    python scripts_py/generar_etiquetas.py                              (BD real)
    BUSCADOR_ENTORNO=pruebas python scripts_py/generar_etiquetas.py     (gym_buscador_test)

Requiere sql/esquema_etiquetas.sql y sql/esquema_rutas_arboles.sql (una ruta por árbol). Todo va en UNA transacción: si algo falla, las
tablas quedan como estaban. Los id de las etiquetas que siguen existiendo se conservan
(INSERT ... ON DUPLICATE KEY UPDATE); las que ya no aparecen se borran.
Solo consultas con parámetros (%s); los nombres de tabla son fijos.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from arboles import (construir_arbol_anatomia, construir_arbol_equipamiento, construir_arbol_nivel,  # noqa: E402
                     construir_arbol_patron, construir_arbol_temas)
from etiquetado import construir_etiquetas, construir_rutas_arboles  # noqa: E402


BLOQUE = 2000     # filas por INSERT: MariaDB corta la conexión si un paquete supera max_allowed_packet (1 MB por defecto)


def insertar_en_bloques(cur, sql, filas):
    """executemany en bloques. Siguen siendo parte de la misma transacción: si uno falla, todo se deshace."""
    for i in range(0, len(filas), BLOQUE):
        cur.executemany(sql, filas[i:i + BLOQUE])


def leer_contenido(conn):
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT id, nombre_es, descripcion_es, grupo_id, equipamiento, nivel, modalidad FROM ejercicios")
    ejercicios = cur.fetchall()
    cur.execute("SELECT id, titulo, contenido, etiquetas FROM articulos")
    articulos = cur.fetchall()
    cur.close()
    return ejercicios, articulos


def generar(conn):
    """Regenera las tres tablas en la BD de `conn`. Devuelve un resumen con conteos."""
    ejercicios, articulos = leer_contenido(conn)
    textos = [a["titulo"] for a in articulos] + [a["contenido"] for a in articulos] \
        + [e["nombre_es"] for e in ejercicios] + [e["descripcion_es"] for e in ejercicios]
    etiquetas, asignaciones = construir_etiquetas(ejercicios, articulos, textos)
    rutas = construir_rutas_arboles([construir_arbol_anatomia(ejercicios), construir_arbol_temas(articulos),
                                     construir_arbol_equipamiento(ejercicios), construir_arbol_nivel(ejercicios),
                                     construir_arbol_patron(ejercicios)])

    conn.autocommit = False            # todo lo de abajo es una sola transacción
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM documento_etiquetas")
        cur.execute("DELETE FROM documento_rutas")
        if etiquetas:
            cur.executemany(
                "INSERT INTO etiquetas (nombre_normalizado, nombre_visible, tipo) VALUES (%s, %s, %s) "
                "ON DUPLICATE KEY UPDATE nombre_visible = VALUES(nombre_visible), tipo = VALUES(tipo)",
                [(k, e["visible"], e["tipo"]) for k, e in sorted(etiquetas.items())],
            )
        cur.execute("SELECT id, nombre_normalizado FROM etiquetas")
        ids = {}
        sobrantes = []
        for i, k in cur.fetchall():
            if k in etiquetas:
                ids[k] = i
            else:
                sobrantes.append((i,))
        if sobrantes:
            cur.executemany("DELETE FROM etiquetas WHERE id = %s", sobrantes)
        if asignaciones:
            insertar_en_bloques(
                cur, "INSERT INTO documento_etiquetas (origen, doc_id, etiqueta_id) VALUES (%s, %s, %s)",
                sorted((o, d, ids[k]) for o, d, k in asignaciones),
            )
        if rutas:
            insertar_en_bloques(
                cur, "INSERT INTO documento_rutas (origen, doc_id, arbol, ruta) VALUES (%s, %s, %s, %s)",
                sorted((o, d, a, r) for (o, d, a), r in rutas.items()),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()

    por_tipo = {}
    for e in etiquetas.values():
        por_tipo[e["tipo"]] = por_tipo.get(e["tipo"], 0) + 1
    return {"etiquetas": len(etiquetas), "por_tipo": por_tipo,
            "asignaciones": len(asignaciones), "rutas": len(rutas)}


def main():
    from db_config import get_connection
    conn = get_connection()
    if conn is None:
        print("ERROR: sin conexión a la BD", file=sys.stderr)
        return 1
    try:
        print(json.dumps(generar(conn), ensure_ascii=False))
    except Exception as e:
        # Sin el mensaje: puede traer valores. Solo la clase.
        print(f"ERROR: no se pudieron generar las etiquetas ({type(e).__name__})", file=sys.stderr)
        return 1
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
