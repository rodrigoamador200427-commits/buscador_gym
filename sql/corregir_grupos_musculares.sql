-- corregir_grupos_musculares.sql — alinea los NOMBRES de grupos_musculares con los IDs reales.
--
-- ejercicios.grupo_id está bien: sigue la asignación de unirdataset/limpiar_ejercicios.py
-- (1=Chest, 2=Back, ... 11=Forearms), igual que scripts_py/arboles/taxonomia.py (MUSCULOS).
-- Lo que estaba mal eran los nombres de esta tabla (p. ej. id 1 = "Cuádriceps" con 262
-- ejercicios que en el dataset original son Chest).
--
-- Solo cambian los nombres; los IDs no, así que la clave foránea fk_grupo de
-- `ejercicios` no se toca. Es idempotente.
--     mysql -uroot gym_buscador < sql/corregir_grupos_musculares.sql

SET NAMES utf8mb4;

UPDATE grupos_musculares SET
    nombre    = ELT(id, 'Pecho', 'Espalda', 'Hombro', 'Bíceps', 'Tríceps', 'Cuádriceps',
                        'Isquiotibiales', 'Pantorrilla', 'Glúteo', 'Abdomen', 'Antebrazos'),
    nombre_en = ELT(id, 'Chest', 'Back', 'Shoulders', 'Biceps', 'Triceps', 'Quadriceps',
                        'Hamstrings', 'Calves', 'Glutes', 'Abs', 'Forearms')
WHERE id BETWEEN 1 AND 11;
