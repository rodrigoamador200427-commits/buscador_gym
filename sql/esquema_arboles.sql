-- Esquema para persistir los árboles (FASE 2). NO ejecutado todavía contra MySQL.
-- Se llena con un cargador a partir de los objetos Arbol de scripts_py/arboles.

CREATE TABLE IF NOT EXISTS nodos (
    id        INT AUTO_INCREMENT PRIMARY KEY,
    arbol     VARCHAR(20)  NOT NULL,            -- 'anatomia' | 'temas'
    nombre    VARCHAR(200) NOT NULL,
    padre_id  INT NULL,
    nivel     TINYINT NOT NULL,
    es_hoja   TINYINT(1) NOT NULL DEFAULT 0,
    FOREIGN KEY (padre_id) REFERENCES nodos(id) ON DELETE CASCADE,
    INDEX idx_arbol_padre (arbol, padre_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Hoja <-> documento real (mismos IDs que `postings`: ejercicios.id / articulos.id)
CREATE TABLE IF NOT EXISTS doc_nodo (
    nodo_id INT NOT NULL,
    doc_id  INT NOT NULL,
    origen  VARCHAR(20) NOT NULL,               -- 'ejercicios' | 'articulos'
    PRIMARY KEY (origen, doc_id),
    FOREIGN KEY (nodo_id) REFERENCES nodos(id) ON DELETE CASCADE,
    INDEX idx_nodo (nodo_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Arista cruzada músculo (anatomía) <-> tema (temas); peso = nº de artículos puente
CREATE TABLE IF NOT EXISTS aristas_cruzadas (
    nodo_musculo_id INT NOT NULL,
    nodo_tema_id    INT NOT NULL,
    peso            INT NOT NULL,
    PRIMARY KEY (nodo_musculo_id, nodo_tema_id),
    FOREIGN KEY (nodo_musculo_id) REFERENCES nodos(id) ON DELETE CASCADE,
    FOREIGN KEY (nodo_tema_id)    REFERENCES nodos(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
