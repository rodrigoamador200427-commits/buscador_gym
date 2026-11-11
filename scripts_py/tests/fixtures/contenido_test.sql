-- Contenido SINTÉTICO para gym_buscador_test (no se copia nada de la base real).
-- Mismas columnas que usan buscar.php / recomendaciones.php / recommender.py.
--
-- Dos "universos" de vocabulario que casi no se tocan:
--   PECHO  (ejercicios 101-105, artículo 301): pech, banc, press, pectoral
--   PIERNA (ejercicios 201-205, artículo 302): sentadill, piern, cuadricep, zancad
-- Solo comparten "calent" con peso pequeño (0.1): el coseno entre universos es
-- menor que 0.01, por debajo del umbral de 0.05 del recomendador.

CREATE TABLE diccionario (
    id INT PRIMARY KEY,
    termino VARCHAR(100) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE postings (
    termino_id INT NOT NULL,
    doc_id INT NOT NULL,
    origen VARCHAR(20) NOT NULL,
    peso_tfidf FLOAT NOT NULL,
    PRIMARY KEY (termino_id, origen, doc_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE ejercicios (
    id INT PRIMARY KEY,
    nombre_es VARCHAR(150) NOT NULL,
    descripcion_es TEXT,
    grupo_id INT,
    modalidad VARCHAR(50),
    equipamiento VARCHAR(100),
    nivel VARCHAR(50)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE articulos (
    id INT PRIMARY KEY,
    titulo VARCHAR(255) NOT NULL,
    contenido TEXT,
    etiquetas VARCHAR(255)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO diccionario (id, termino) VALUES
 (1,'pech'),(2,'banc'),(3,'press'),(4,'pectoral'),
 (5,'sentadill'),(6,'piern'),(7,'cuadricep'),(8,'zancad'),
 (9,'calent');

INSERT INTO ejercicios (id, nombre_es, descripcion_es, grupo_id, equipamiento, modalidad, nivel) VALUES
 (101,'Press de banca plano','Press de pecho en banco plano',5,'Barbell','Strength','Beginner'),
 (102,'Press de banca inclinado','Press de pecho en banco inclinado',5,'Barbell','Strength','Beginner'),
 (103,'Aperturas con mancuernas','Aperturas para el pectoral',5,'Dumbbell','Strength','Beginner'),
 (104,'Press de pecho en máquina','Press de pecho guiado',5,'Machine','Strength','Beginner'),
 (105,'Cruce de poleas','Pectoral con poleas',5,'Cable','Strength','Beginner'),
 (201,'Sentadilla trasera','Sentadilla con barra para pierna',1,'Barbell','Strength','Beginner'),
 (202,'Sentadilla frontal','Sentadilla frontal para cuádriceps',1,'Barbell','Strength','Beginner'),
 (203,'Zancada caminando','Zancada para pierna',1,'Dumbbell','Strength','Beginner'),
 (204,'Prensa de piernas','Cuádriceps en prensa',1,'Machine','Strength','Beginner'),
 (205,'Zancada búlgara','Zancada con pie atrás',1,'Dumbbell','Strength','Beginner');

INSERT INTO articulos (id, titulo, contenido, etiquetas) VALUES
 (301,'Biomecánica del press de banca','El pectoral y el press de banca.','pecho,fuerza'),
 (302,'Cómo progresar en la sentadilla','Sentadilla, cuádriceps y pierna.','pierna,fuerza');

INSERT INTO postings (termino_id, doc_id, origen, peso_tfidf) VALUES
 -- PECHO
 (1,101,'ejercicios',0.8),(2,101,'ejercicios',0.6),(3,101,'ejercicios',0.5),(9,101,'ejercicios',0.1),
 (1,102,'ejercicios',0.7),(2,102,'ejercicios',0.6),(3,102,'ejercicios',0.6),(9,102,'ejercicios',0.1),
 (1,103,'ejercicios',0.6),(4,103,'ejercicios',0.8),(9,103,'ejercicios',0.1),
 (1,104,'ejercicios',0.8),(3,104,'ejercicios',0.7),(9,104,'ejercicios',0.1),
 (4,105,'ejercicios',0.9),(1,105,'ejercicios',0.3),(9,105,'ejercicios',0.1),
 (2,301,'articulos',0.5),(3,301,'articulos',0.5),(4,301,'articulos',0.6),(9,301,'articulos',0.1),
 -- PIERNA
 (5,201,'ejercicios',0.8),(6,201,'ejercicios',0.6),(7,201,'ejercicios',0.5),(9,201,'ejercicios',0.1),
 (5,202,'ejercicios',0.7),(7,202,'ejercicios',0.7),(9,202,'ejercicios',0.1),
 (8,203,'ejercicios',0.8),(6,203,'ejercicios',0.6),(9,203,'ejercicios',0.1),
 (7,204,'ejercicios',0.8),(6,204,'ejercicios',0.6),(9,204,'ejercicios',0.1),
 (8,205,'ejercicios',0.9),(6,205,'ejercicios',0.3),(9,205,'ejercicios',0.1),
 (5,302,'articulos',0.5),(7,302,'articulos',0.5),(6,302,'articulos',0.6),(9,302,'articulos',0.1);
