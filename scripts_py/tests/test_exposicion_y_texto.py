"""Revisión de la fase 7, parte estática (no necesita BD ni servidor).

1. Exposición por HTTP: lo que no es página, endpoint ni asset no debe poder leerse con Apache.
   El 403/404 real se comprobó a mano con curl (ver docs/Avances.md, fase 7); aquí se fija que
   las reglas existan para que nadie las quite sin darse cuenta.
2. La interfaz no lleva emojis ni texto de relleno.
"""
import glob
import os
import re

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def leer(*partes):
    with open(os.path.join(RAIZ, *partes), encoding="utf-8") as f:
        return f.read()


# --------------------------------------------------------------------------- exposición por HTTP
CARPETAS_INTERNAS = ["config", "lib", "sql", "tests", "herramientas", "corpus", "scripts_py", "unirdataset", "docs"]


@pytest.mark.parametrize("carpeta", CARPETAS_INTERNAS)
def test_carpeta_interna_niega_el_acceso(carpeta):
    assert "Require all denied" in leer(carpeta, ".htaccess")


def test_raiz_sin_listado_de_carpetas_y_sin_git():
    t = leer(".htaccess")
    assert "Options -Indexes" in t
    # el repositorio y las carpetas de código y datos responden 404 desde la raíz (cubre backups/, que no va a Git)
    regla = next(l for l in t.splitlines() if l.startswith("RedirectMatch"))
    for nombre in (r"\.git", "scripts_py", "backups", "unirdataset", "docs"):
        assert nombre in regla, nombre


def test_raiz_niega_documentos_y_datos_sueltos():
    t = leer(".htaccess")
    assert "FilesMatch" in t and "Require all denied" in t
    for ext in ("md", "csv", "docx", "txt", "py", "sql"):
        assert ext in t.split("FilesMatch", 1)[1], ext


# --------------------------------------------------------------------------- texto de la interfaz
EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿⌀-⏿️‍✅❌✨]")
MARCAS = re.compile(r"\b(?:TODO|FIXME)\b\s*[:(]")      # marca pendiente; «TODO texto…» como énfasis no cuenta
RELLENO = re.compile(r"lorem|ipsum|próximamente|proximamente|coming soon|texto de ejemplo|aquí va", re.I)


def archivos_de_interfaz():
    fijos = ["index.html", os.path.join("lib", "admin_panel.html"), os.path.join("assets", "estilos.css"),
             os.path.join("assets", "admin.css"), os.path.join("assets", "admin.js"), os.path.join("assets", "ilustraciones.js")]
    return fijos + [os.path.relpath(p, RAIZ) for p in sorted(glob.glob(os.path.join(RAIZ, "assets", "**", "*.svg"), recursive=True))]


@pytest.mark.parametrize("ruta", archivos_de_interfaz())
def test_interfaz_sin_emojis_ni_relleno(ruta):
    for n, linea in enumerate(leer(ruta).splitlines(), 1):
        m = EMOJI.search(linea)
        assert not m, f"{ruta}:{n}: emoji U+{ord(m.group()):04X}"
        r = MARCAS.search(linea) or RELLENO.search(linea)
        assert not r, f"{ruta}:{n}: relleno {r.group()!r}"
