-- =============================================================================
-- esquema_estadisticas.sql — Registro de eventos para estadísticas, sin datos personales
--
-- Requiere esquema_cuentas.sql (tabla perfiles). Sin USE, igual que ese archivo:
--     mysql -uroot gym_buscador      < sql/esquema_estadisticas.sql
--     mysql -uroot gym_buscador_test < sql/esquema_estadisticas.sql
--
-- Es idempotente: volver a ejecutarlo no borra filas.
-- Las filas de más de 180 días se borran con herramientas/purgar_estadisticas.php.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Eventos: qué contenido se consume.
--    - impresion: el documento apareció en los resultados de una búsqueda.
--      Se guarda SIEMPRE con perfil_id NULL: si llevara perfil, su creado_en
--      coincidiría con el de la fila de `consultas` y permitiría saber qué perfil
--      hizo cada búsqueda.
--    - apertura / like: llevan el perfil activo (siempre de la sesión).
--    Al borrar el perfil, el evento se conserva para el conteo con perfil_id NULL.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS eventos (
    id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    perfil_id  INT UNSIGNED    NULL,
    tipo       ENUM('impresion','apertura','like') NOT NULL,
    origen     ENUM('ejercicios','articulos')      NOT NULL,
    doc_id     INT             NOT NULL,
    creado_en  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_eventos_doc (origen, doc_id, tipo),
    INDEX idx_eventos_fecha (creado_en),
    CONSTRAINT fk_eventos_perfil
        FOREIGN KEY (perfil_id) REFERENCES perfiles(id)
        ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 2. Consultas: qué búsquedas fallan (n_resultados = 0).
--    SIN perfil_id y SIN el texto original: solo las raíces ya procesadas,
--    sin repetir y en orden alfabético (no conservan el orden de la frase).
--    via: vía del descubrimiento por árboles (NULL si no hubo).
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS consultas (
    id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    raices        VARCHAR(255) NOT NULL,
    via           VARCHAR(30)  NULL,
    n_resultados  INT UNSIGNED NOT NULL,
    creado_en     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_consultas_fecha (creado_en)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
