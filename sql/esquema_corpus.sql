-- =============================================================================
-- esquema_corpus.sql — Origen del contenido de cada artículo
--
-- Sin USE, igual que los otros esquemas:
--     mysql -uroot gym_buscador      < sql/esquema_corpus.sql
--     mysql -uroot gym_buscador_test < sql/esquema_corpus.sql
--
-- Es idempotente: la columna se agrega solo si no existe. Los artículos que ya existen
-- quedan como 'original' por el valor por defecto; scripts_py/importar_lote.py marca los
-- que carga como 'generado'.
-- =============================================================================

SET @ya_existe := (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME   = 'articulos'
      AND COLUMN_NAME  = 'origen_contenido'
);
SET @sql_origen := IF(@ya_existe = 0,
    "ALTER TABLE articulos ADD COLUMN origen_contenido ENUM('original','generado') NOT NULL DEFAULT 'original' AFTER etiquetas",
    'DO 0');
PREPARE agregar_origen FROM @sql_origen;
EXECUTE agregar_origen;
DEALLOCATE PREPARE agregar_origen;
