-- =============================================================================
-- esquema_admin.sql — Rol de administrador en las cuentas
--
-- Sin USE, igual que los otros esquemas:
--     mysql -uroot gym_buscador      < sql/esquema_admin.sql
--     mysql -uroot gym_buscador_test < sql/esquema_admin.sql
--
-- Es idempotente: la columna se agrega solo si no existe y las filas no se tocan
-- (las cuentas que ya existen quedan como 'usuario').
--
-- El rol 'admin' lo escribe ÚNICAMENTE herramientas/crear_admin.php (línea de comandos).
-- registro.php y el resto de los endpoints web nunca mencionan esta columna.
-- =============================================================================

SET @ya_existe := (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME   = 'cuentas'
      AND COLUMN_NAME  = 'rol'
);
SET @sql_rol := IF(@ya_existe = 0,
    "ALTER TABLE cuentas ADD COLUMN rol ENUM('usuario','admin') NOT NULL DEFAULT 'usuario' AFTER contrasena_hash",
    'DO 0');
PREPARE agregar_rol FROM @sql_rol;
EXECUTE agregar_rol;
DEALLOCATE PREPARE agregar_rol;
