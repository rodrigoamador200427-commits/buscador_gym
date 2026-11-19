-- =============================================================================
-- esquema_rutas_arboles.sql — Una ruta POR ÁRBOL y documento (fase 6B)
--
-- Sin USE, igual que los otros esquemas:
--     mysql -uroot gym_buscador      < sql/esquema_rutas_arboles.sql
--     mysql -uroot gym_buscador_test < sql/esquema_rutas_arboles.sql
-- Requiere sql/esquema_etiquetas.sql (crea documento_rutas).
--
-- Antes: documento_rutas tenía una sola ruta por documento (PRIMARY KEY origen, doc_id).
-- Un ejercicio ahora vive a la vez en Anatomía, Equipamiento y Nivel, así que la clave pasa
-- a (origen, doc_id, arbol) y el ENUM acepta los árboles nuevos. 'patron' se incluye desde
-- ahora para no tener que migrar otra vez si se activa el árbol de Patrón de movimiento.
--
-- Es idempotente: solo altera la tabla si la clave primaria aún no incluye `arbol`. La tabla
-- es DERIVADA (generar_etiquetas.py la vuelve a llenar completa), así que no se pierde nada.
-- =============================================================================

SET @ya_migrada := (
    SELECT COUNT(*) FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME   = 'documento_rutas'
      AND INDEX_NAME   = 'PRIMARY'
      AND COLUMN_NAME  = 'arbol'
);
SET @sql_rutas := IF(@ya_migrada = 0,
    "ALTER TABLE documento_rutas
        MODIFY arbol ENUM('anatomia','temas','equipamiento','nivel','patron') NOT NULL,
        DROP PRIMARY KEY,
        ADD PRIMARY KEY (origen, doc_id, arbol)",
    'DO 0');
PREPARE migrar_rutas FROM @sql_rutas;
EXECUTE migrar_rutas;
DEALLOCATE PREPARE migrar_rutas;
