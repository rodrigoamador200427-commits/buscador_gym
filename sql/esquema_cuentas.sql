-- =============================================================================
-- esquema_cuentas.sql — Cuentas, perfiles e historial aislado por perfil
-- Tema: protección de información (Recuperación de la Información)
--
-- Se ejecuta sobre la base elegida, sin USE, para poder aplicarlo igual a
-- gym_buscador y a gym_buscador_test:
--     mysql -uroot gym_buscador      < sql/esquema_cuentas.sql
--     mysql -uroot gym_buscador_test < sql/esquema_cuentas.sql
--
-- Es idempotente: volver a ejecutarlo no borra cuentas, perfiles ni likes nuevos.
-- Probado en MariaDB 10.4.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 0. Migración: descartar la tabla `interacciones` antigua (usuario_id fijo = 1)
--    Solo se borra si todavía tiene la columna `usuario_id`. Decisión del
--    proyecto: los likes de prueba anteriores se descartan, no se migran.
-- -----------------------------------------------------------------------------
SET @es_vieja := (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME   = 'interacciones'
      AND COLUMN_NAME  = 'usuario_id'
);
SET @sql_migracion := IF(@es_vieja > 0, 'DROP TABLE interacciones', 'DO 0');
PREPARE migracion FROM @sql_migracion;
EXECUTE migracion;
DEALLOCATE PREPARE migracion;

-- -----------------------------------------------------------------------------
-- 1. Cuentas
--    - correo: normalizado (trim + minúsculas) por PHP, en claro y único.
--    - contrasena_hash: salida de password_hash(); nunca la contraseña.
--    - nombre_cifrado / fecha_nac_cifrada: AES-256-GCM, formato binario
--      version(1) || nonce(12) || tag(16) || texto_cifrado.
--      La clave vive en config/config.local.php (fuera de Git).
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cuentas (
    id                 INT UNSIGNED  NOT NULL AUTO_INCREMENT,
    correo             VARCHAR(254)  NOT NULL,
    contrasena_hash    VARCHAR(255)  NOT NULL,
    nombre_cifrado     VARBINARY(512) NOT NULL,
    fecha_nac_cifrada  VARBINARY(64)  NOT NULL,
    creado_en          TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_cuentas_correo (correo),
    CONSTRAINT chk_cuentas_correo CHECK (correo = LOWER(TRIM(correo)) AND correo LIKE '%_@_%')
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 2. Perfiles (máximo 4 por cuenta). Borrar la cuenta borra sus perfiles.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS perfiles (
    id         INT UNSIGNED NOT NULL AUTO_INCREMENT,
    cuenta_id  INT UNSIGNED NOT NULL,
    nombre     VARCHAR(40)  NOT NULL,
    creado_en  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_perfiles_cuenta_nombre (cuenta_id, nombre),
    CONSTRAINT fk_perfiles_cuenta
        FOREIGN KEY (cuenta_id) REFERENCES cuentas(id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT chk_perfiles_nombre CHECK (CHAR_LENGTH(TRIM(nombre)) BETWEEN 1 AND 40)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Límite de 4 perfiles: defensa en profundidad. PHP además bloquea la fila de la
-- cuenta (SELECT ... FOR UPDATE) antes de insertar, para evitar carreras.
DROP TRIGGER IF EXISTS trg_perfiles_max4;
DELIMITER $$
CREATE TRIGGER trg_perfiles_max4
BEFORE INSERT ON perfiles
FOR EACH ROW
BEGIN
    IF (SELECT COUNT(*) FROM perfiles WHERE cuenta_id = NEW.cuenta_id) >= 4 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Limite de 4 perfiles por cuenta';
    END IF;
END$$
DELIMITER ;

-- -----------------------------------------------------------------------------
-- 3. Interacciones, ahora por perfil. Borrar un perfil borra su historial.
--    El centroide NO se guarda: el recomendador lo recalcula en cada petición
--    con WHERE perfil_id = ?, así nunca mezcla perfiles ni queda desactualizado.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS interacciones (
    id           INT UNSIGNED NOT NULL AUTO_INCREMENT,
    perfil_id    INT UNSIGNED NOT NULL,
    doc_id       INT          NOT NULL,
    origen       ENUM('ejercicios','articulos') NOT NULL,
    interaccion  ENUM('like') NOT NULL DEFAULT 'like',
    peso         FLOAT        NOT NULL DEFAULT 1.0,
    fecha        TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    -- un like por documento y perfil; el índice empieza por perfil_id, así que
    -- también sirve para "todo el historial de este perfil"
    UNIQUE KEY uq_interacciones_perfil_doc (perfil_id, origen, doc_id, interaccion),
    CONSTRAINT fk_interacciones_perfil
        FOREIGN KEY (perfil_id) REFERENCES perfiles(id)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 4. Intentos de inicio de sesión (límite de intentos)
--    No guarda el correo en claro: guarda SHA-256 del correo normalizado, porque
--    también se registran intentos con correos que no tienen cuenta. Sin clave
--    foránea a propósito: así no se revela si el correo existe. Al eliminar una
--    cuenta, PHP borra también sus filas por correo_hash. PHP purga las filas de
--    más de 24 h.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS intentos_login (
    id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    correo_hash  BINARY(32)      NOT NULL,
    ip           VARBINARY(16)   NOT NULL,      -- INET6_ATON(ip)
    exito        TINYINT(1)      NOT NULL DEFAULT 0,
    creado_en    TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_intentos_correo (correo_hash, creado_en),
    INDEX idx_intentos_ip (ip, creado_en)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
