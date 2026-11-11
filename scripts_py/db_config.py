"""Conexión a MySQL con las credenciales de config/config.*.ini.php (fuera de Git).

Es el mismo archivo que lee PHP (lib/config.php). Solo la variable de entorno
BUSCADOR_ENTORNO=pruebas elige la configuración de pruebas, y se valida que el
entorno y el nombre de la BD sean coherentes, igual que en PHP.
"""
import configparser
import os
import sys

import mysql.connector
from mysql.connector import Error

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _sin_comillas(valor):
    valor = valor.strip()
    if len(valor) >= 2 and valor[0] == valor[-1] == '"':
        return valor[1:-1]
    return valor


def cargar_config():
    tipo = "test" if os.environ.get("BUSCADOR_ENTORNO") == "pruebas" else "local"
    ruta = os.path.join(RAIZ, "config", f"config.{tipo}.ini.php")
    if not os.path.isfile(ruta):
        raise RuntimeError(f"Falta config/config.{tipo}.ini.php (copia config.example.ini.php)")

    # La línea 1 (";<?php ... ?>") es un comentario INI; interpolation=None para no
    # interpretar % en contraseñas.
    cp = configparser.ConfigParser(interpolation=None)
    cp.read(ruta, encoding="utf-8")
    entorno = _sin_comillas(cp.get("app", "entorno"))
    db = {k: _sin_comillas(v) for k, v in cp.items("db")}

    es_bd_prueba = db["nombre"].endswith("_test")
    if tipo == "test" and (entorno != "pruebas" or not es_bd_prueba):
        raise RuntimeError("La configuración de pruebas debe usar entorno=pruebas y una BD *_test")
    if tipo == "local" and (entorno == "pruebas" or es_bd_prueba):
        raise RuntimeError("La configuración real no puede apuntar a una BD de pruebas")
    return db


def get_connection():
    try:
        db = cargar_config()
        return mysql.connector.connect(
            host=db["host"],
            database=db["nombre"],
            user=db["usuario"],
            password=db.get("contrasena", ""),
        )
    except (Error, RuntimeError, KeyError, configparser.Error) as e:
        # A stderr y sin detalles: stdout es el JSON que lee PHP, y el mensaje de
        # MySQL puede incluir usuario o host.
        print(f"db_config: no se pudo conectar ({type(e).__name__})", file=sys.stderr)
        return None
