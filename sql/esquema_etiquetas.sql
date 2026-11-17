-- =============================================================================
-- esquema_etiquetas.sql — Etiquetas normalizadas y ruta en el árbol de cada documento
--
-- Sin USE, igual que los otros esquemas:
--     mysql -uroot gym_buscador      < sql/esquema_etiquetas.sql
--     mysql -uroot gym_buscador_test < sql/esquema_etiquetas.sql
-- Después se llenan (o se regeneran) con:
--     python scripts_py/generar_etiquetas.py
--
-- Es idempotente. Las tres tablas son DERIVADAS del contenido (ejercicios, articulos y
-- los árboles de scripts_py/arboles): el generador las vuelve a llenar completas dentro
-- de una transacción, así que se pueden regenerar cuando cambie el contenido.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Etiquetas. nombre_normalizado: sin acentos, minúsculas y en singular, con los
--    sinónimos ya unidos. Es único por sí solo: "fuerza" (modalidad de un ejercicio)
--    y "fuerza" (etiqueta de un artículo) son la MISMA etiqueta. Si un nombre aparece
--    con dos tipos, gana: musculo > equipamiento > nivel > modalidad > tema.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS etiquetas (
    id                  INT UNSIGNED NOT NULL AUTO_INCREMENT,
    nombre_normalizado  VARCHAR(80)  NOT NULL,
    nombre_visible      VARCHAR(80)  NOT NULL,
    tipo  ENUM('musculo','equipamiento','nivel','modalidad','tema') NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_etiquetas_nombre (nombre_normalizado),
    INDEX idx_etiquetas_tipo (tipo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 2. Documento <-> etiqueta. Sin clave foránea a doc_id: apunta a ejercicios o a
--    articulos según origen. Los huérfanos desaparecen al regenerar.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS documento_etiquetas (
    origen       ENUM('ejercicios','articulos') NOT NULL,
    doc_id       INT          NOT NULL,
    etiqueta_id  INT UNSIGNED NOT NULL,
    PRIMARY KEY (origen, doc_id, etiqueta_id),               -- etiquetas de un documento
    INDEX idx_docetq_etiqueta (etiqueta_id, origen, doc_id), -- documentos de una etiqueta
    CONSTRAINT fk_docetq_etiqueta FOREIGN KEY (etiqueta_id)
        REFERENCES etiquetas(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 3. Ruta de cada documento en su árbol, de la raíz al padre de la hoja (la hoja es el
--    propio documento). Ejercicios: anatomia; artículos: temas.
--    Ej.: "Cuerpo humano > Tren superior > Pecho > Barra".
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS documento_rutas (
    origen  ENUM('ejercicios','articulos') NOT NULL,
    doc_id  INT          NOT NULL,
    arbol   ENUM('anatomia','temas') NOT NULL,
    ruta    VARCHAR(255) NOT NULL,
    PRIMARY KEY (origen, doc_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
