"""Motor de relación consulta -> árboles -> salto entre árboles.

Reemplaza a motor_grafos.py. Diferencias de fondo:
  * trabaja con las RAÍCES que ya produce el pipeline de NLP (no con texto crudo);
  * los conceptos salen de la taxonomía y de los datos, no de una tabla tecleada;
  * es DETERMINISTA: la misma consulta da siempre la misma respuesta;
  * si no hay relación lo dice (via = 'ninguno') en vez de inventar una.

Desde la fase 6B trabaja con N árboles (un `Bosque`: anatomía, temas, equipamiento, nivel...).
Cada consulta "nombra" cero o más árboles, según los conceptos (nodos) que reconoce en ella:

  * cero  -> 'recuperacion' (o 'ninguno'): se acumulan en posorden los documentos que recuperó el
             TF-IDF sobre anatomía y temas (taxonomia.ARBOLES_RECUPERACION) y se salta desde el
             nodo con más peso.
  * uno   -> 'concepto' / 'concepto_local': salto por la mejor arista (lift) al árbol compañero
             (taxonomia.ARBOL_COMPANERO: músculo <-> tema; equipamiento y nivel saltan a anatomía).
  * dos o más: se toma el mejor nodo de cada árbol nombrado y
        1. 'interseccion'         hay documentos que pertenecen a TODOS los nodos;
        2. 'interseccion_parcial' no los hay, pero sí para algún PAR: se elige el par de mayor lift
                                  (luego mayor peso, luego el orden fijo de los árboles) y la traza
                                  dice qué árbol(es) quedó fuera;
        3. 'sin_interseccion'     ningún par se relaciona (se dice, no se inventa).
Para consultas que solo nombran un músculo y un tema el comportamiento es idéntico al de la fase 1.

Cada respuesta declara qué nivel la produjo en `via` y trae `nodos`: la ruta del nodo en CADA árbol
que participa (`origen` y `destino` son los dos primeros, como siempre).
"""
from collections import Counter

from .bosque import Bosque
from .recorridos import acumular_posorden, preorden
from .taxonomia import (ALIAS_MUSCULO, ARBOL_COMPANERO, ARBOLES_RECUPERACION, CONSULTA_EQUIPAMIENTO,
                        CONSULTA_NIVEL, EXPANSION_TEMA, ETIQUETA_A_MUSCULO, SINONIMOS_TEMA, TEMAS,
                        TITULO_ARBOL, normalizar)


def _frase_a_raices(frase, stem):
    return frozenset(stem(p) for p in normalizar(frase).split() if p)


class MotorArboles:
    def __init__(self, anatomia, temas, aristas, stem):
        """Forma de la fase 1: dos árboles y sus `Aristas` (músculo x tema). stem: función palabra ->
        raíz (la misma del indexador, p. ej. SnowballStemmer.stem). Para N árboles: desde_bosque()."""
        self._iniciar(Bosque.desde_aristas_clasicas(anatomia, temas, aristas), stem)
        self.A, self.T, self.E = anatomia, temas, aristas

    @classmethod
    def desde_bosque(cls, bosque, stem):
        motor = cls.__new__(cls)
        motor._iniciar(bosque, stem)
        motor.A, motor.T, motor.E = bosque.arboles.get("anatomia"), bosque.arboles.get("temas"), None
        return motor

    def _iniciar(self, bosque, stem):
        self.B, self.stem = bosque, stem
        self._orden_tema = {t: i for i, (_, t, _) in enumerate(TEMAS)}

        # índice de conceptos por árbol: lista de (clave, frozenset de raíces)
        self._idx = {}
        if "anatomia" in bosque.arboles:
            idx = [(gid, _frase_a_raices(tag, stem)) for tag, gid in ETIQUETA_A_MUSCULO.items()]
            for alias, gids in ALIAS_MUSCULO.items():
                idx += [(gid, _frase_a_raices(alias, stem)) for gid in gids]
            self._idx["anatomia"] = idx
        self._idx_sinonimo = []     # (tema, raíces de la frase): vocabulario del usuario
        self._idx_tema_etiquetas = []
        if "temas" in bosque.arboles:
            for _, tema, tags in TEMAS:
                self._idx_tema_etiquetas += [(tema, _frase_a_raices(t, stem)) for t in tags]
            for tema, frases in SINONIMOS_TEMA.items():
                self._idx_sinonimo += [(tema, _frase_a_raices(f, stem)) for f in frases]
            self._idx["temas"] = self._idx_tema_etiquetas + self._idx_sinonimo
        for arbol, vocabulario in (("equipamiento", CONSULTA_EQUIPAMIENTO), ("nivel", CONSULTA_NIVEL)):
            if arbol in bosque.arboles:
                existentes = bosque.conceptos(arbol)
                self._idx[arbol] = [(n, _frase_a_raices(f, stem))
                                    for n, frases in vocabulario.items() if n in existentes for f in frases]

    # ------------------------------------------------------------------ API
    def preparar_consulta(self, raices):
        """Raíces que se usarán para RECUPERAR en el índice TF-IDF (la detección de conceptos sigue
        usando las raíces completas). Dos reglas, ambas basadas en la taxonomía:
          * frase de intención (>= 2 palabras, p. ej. «bajar peso»): sus raíces se sustituyen por el
            vocabulario del tema, porque por separado son ambiguas ('baj' choca con «baja», 'pes' con
            «peso muerto»). Las raíces que también nombran un músculo, una etiqueta, un equipamiento
            o un nivel se conservan.
          * palabra suelta de usuario (p. ej. «masa»): se conserva y se añade el vocabulario del tema.
        -> {"raices": [...], "descartadas": [...], "expandidas": [...]}"""
        consulta = set(raices)
        protegidas = set()
        conceptos = self._idx.get("anatomia", []) + self._idx_tema_etiquetas \
            + self._idx.get("equipamiento", []) + self._idx.get("nivel", [])
        for _, r in conceptos:
            if r and r <= consulta:
                protegidas |= r
        descartar, temas = set(), []
        for tema, r in self._idx_sinonimo:
            if r and r <= consulta:
                if tema not in temas:
                    temas.append(tema)
                if len(r) >= 2:
                    descartar |= (r - protegidas)
        base = [x for x in raices if x not in descartar]
        extra = []
        for tema in temas:
            for palabra in EXPANSION_TEMA.get(tema, []):
                raiz = self.stem(palabra)
                if raiz not in base and raiz not in extra:
                    extra.append(raiz)
        final = base + extra
        return {"raices": final or list(raices),
                "descartadas": sorted(d for d in descartar if d not in final),
                "expandidas": extra}

    def descubrir(self, raices, recuperados=()):
        """raices: raíces de la consulta. recuperados: [(origen, doc_id, score)] del índice TF-IDF."""
        consulta = set(raices)
        scores = {(o, d): s for o, d, s in recuperados}
        nombrados = {a: self._coincidencias(self._idx[a], consulta) for a in self.B.nombres if a in self._idx}
        nombrados = {a: c for a, c in nombrados.items() if c}
        mejores = {a: self._mejor(a, c) for a, c in nombrados.items()}
        arboles = [a for a in self.B.nombres if a in mejores]            # en orden de prioridad

        traza = {"conceptos_musculo": [self.B.conceptos("anatomia")[g].nombre
                                       for g in nombrados.get("anatomia", ())],
                 "conceptos_tema": list(nombrados.get("temas", ())),
                 "conceptos": {a: [self._nombre(a, c) for c in nombrados[a]] for a in arboles},
                 "arboles_nombrados": arboles,
                 "documentos_recuperados": len(scores)}

        if len(arboles) >= 2:
            return self._combinar(arboles, mejores, scores, traza)
        if arboles:
            return self._salto(arboles[0], mejores[arboles[0]], scores, traza, "concepto")
        if scores:
            return self._desde_recuperacion(scores, traza)
        return self._sin_relacion("ninguno", traza,
                                  "Ningún término de la consulta corresponde a un nodo y no se recuperó "
                                  "ningún documento: sin relación.")

    # ------------------------------------------------------- reconocimiento
    @staticmethod
    def _coincidencias(indice, consulta):
        n = Counter()
        for clave, raices in indice:
            if raices and raices <= consulta:
                n[clave] += 1
        return n

    def _nombre(self, arbol, clave):
        return self.B.conceptos(arbol)[clave].nombre

    def _mejor(self, arbol, conteo):
        """Mejor nodo de un árbol: más coincidencias; luego, con más artículos que lo respaldan (salvo
        en temas); luego el orden propio (grupo_id en anatomía, orden de TEMAS, orden del árbol)."""
        conceptos = self.B.conceptos(arbol)
        if arbol == "temas":
            clave = lambda c: (-conteo[c], self._orden_tema[c])
        elif arbol == "anatomia":
            clave = lambda c: (-conteo[c], -self.B.n_articulos(conceptos[c]), c)
        else:
            clave = lambda c: (-conteo[c], -self.B.n_articulos(conceptos[c]), conceptos[c].id)
        return conceptos[min(conteo, key=clave)]

    # ------------------------------------------------------------ combinar
    def _combinar(self, arboles, mejores, scores, traza):
        nodos = [mejores[a] for a in arboles]
        comunes = sorted(set.intersection(*(self.B.docs_de_nodo(n) for n in nodos)))
        if comunes:
            if arboles == ["anatomia", "temas"] and all(d[0] == "articulos" for d in comunes):
                razon = (f"Tu consulta combina «{nodos[0].nombre}» y «{nodos[1].nombre}»: "
                         f"{len(comunes)} artículos conectan ambos árboles.")
            else:
                razon = (f"Tu consulta combina {self._lista_nodos(nodos)}: "
                         f"{self._cuenta_docs(comunes)} {'pertenece' if len(comunes) == 1 else 'pertenecen'} a "
                         f"{'ambos' if len(nodos) == 2 else 'todos'} a la vez.")
            return self._respuesta("interseccion", nodos[0], nodos[1], comunes, scores, traza, razon, nodos=nodos)

        if len(arboles) >= 3:
            elegido = self._mejor_par(arboles, mejores)
            if elegido:
                (a, b), par, ia, ib = elegido
                na, nb = mejores[a], mejores[b]
                omitidos = [x for x in arboles if x not in (a, b)]
                traza["arboles_usados"], traza["arboles_omitidos"] = [a, b], omitidos
                docs = par.docs(ia, ib)
                razon = (f"Ningún documento reúne a la vez {self._lista_nodos(nodos)}. "
                         f"La mejor relación es entre «{na.nombre}» ({TITULO_ARBOL[a]}) y «{nb.nombre}» "
                         f"({TITULO_ARBOL[b]}): {self._cuenta_docs(docs)} (lift {par.lift(ia, ib):.1f}); "
                         f"quedó fuera {', '.join(TITULO_ARBOL[x] for x in omitidos)}.")
                return self._respuesta("interseccion_parcial", na, nb, docs, scores, traza, razon,
                                       lift=par.lift(ia, ib), nodos=[na, nb])

        primero = nodos[0]
        alt = self._salto(arboles[0], primero, scores, traza, "concepto")
        solo_articulos = arboles[:2] == ["anatomia", "temas"] and len(arboles) == 2
        razon = (f"Ningún artículo relaciona «{nodos[0].nombre}» con «{nodos[1].nombre}»; "
                 f"el sistema no inventa una relación." if solo_articulos else
                 f"Ningún documento relaciona {self._lista_nodos(nodos)}; el sistema no inventa una relación.")
        return self._sin_relacion("sin_interseccion", traza, razon, alternativa=alt, nodos=nodos)

    def _mejor_par(self, arboles, mejores):
        """Par de árboles nombrados con documentos en común: mayor lift, luego peso, luego el orden
        fijo de los árboles. Primero con al menos 2 documentos; si no hay, con 1."""
        for minimo in (2, 1):
            candidatos = []
            for i, a in enumerate(arboles):
                for b in arboles[i + 1:]:
                    par = self.B.par(a, b)
                    ia, ib = mejores[a].id, mejores[b].id
                    peso = par.peso(ia, ib)
                    if peso >= minimo:
                        candidatos.append((-par.lift(ia, ib), -peso, self.B.nombres.index(a),
                                           self.B.nombres.index(b), (a, b), par, ia, ib))
            if candidatos:
                _, _, _, _, ab, par, ia, ib = min(candidatos, key=lambda c: c[:4])
                return ab, par, ia, ib
        return None

    @staticmethod
    def _lista_nodos(nodos):
        partes = [f"«{n.nombre}» ({TITULO_ARBOL[n.arbol]})" for n in nodos]
        return partes[0] if len(partes) == 1 else ", ".join(partes[:-1]) + " y " + partes[-1]

    @staticmethod
    def _cuenta_docs(docs):
        ej = sum(1 for d in docs if d[0] == "ejercicios")
        ar = len(docs) - ej
        partes = ([f"{ej} ejercicio{'s' if ej != 1 else ''}"] if ej else []) \
            + ([f"{ar} artículo{'s' if ar != 1 else ''}"] if ar else [])
        return " y ".join(partes) or "0 documentos"

    # ---------------------------------------------------------------- saltos
    def _companero(self, arbol):
        c = ARBOL_COMPANERO.get(arbol)
        if c in self.B.arboles:
            return c
        otros = [a for a in self.B.nombres if a != arbol]
        return otros[0] if otros else None

    def _salto(self, arbol, nodo, scores, traza, via):
        """Salta desde un nodo reconocido por su mejor arista (lift) hacia el árbol compañero."""
        destino_arbol = self._companero(arbol)
        if destino_arbol is None:
            return self._local(nodo, scores, traza, "no hay otro árbol con el que relacionarlo")
        par = self.B.par(arbol, destino_arbol)
        lado = "a" if arbol == par.arbol_a else "b"
        vec = par.vecinos(lado, nodo.id) or par.vecinos(lado, nodo.id, min_soporte=1)
        if not vec:
            motivo = {"anatomia": "ningún artículo lo relaciona con un tema",
                      "temas": "ningún artículo lo relaciona con un músculo"}.get(
                arbol, "ningún documento lo relaciona con otro árbol")
            return self._local(nodo, scores, traza, motivo)
        id_otro, peso, lift = vec[0]
        otro = self.B.arbol(destino_arbol).nodo(id_otro)
        docs = par.docs(nodo.id, id_otro) if lado == "a" else par.docs(id_otro, nodo.id)
        total = par.n_docs(lado, nodo.id)
        if (arbol, destino_arbol) == ("anatomia", "temas"):
            razon = (f"Tu consulta apunta a «{nodo.nombre}». De {total} artículos "
                     f"sobre ese músculo, {peso} tratan «{otro.nombre}» (lift {lift:.1f}): "
                     f"el grafo salta de Anatomía a Temas.")
        elif (arbol, destino_arbol) == ("temas", "anatomia"):
            razon = (f"Tu consulta apunta al tema «{nodo.nombre}». De {total} artículos "
                     f"sobre ese tema, {peso} también tratan «{otro.nombre}» (lift {lift:.1f}): "
                     f"el grafo salta de Temas a Anatomía.")
        else:
            razon = (f"Tu consulta apunta a «{nodo.nombre}» ({TITULO_ARBOL[arbol]}). De {total} documentos "
                     f"de ese nodo, {peso} también pertenecen a «{otro.nombre}» ({TITULO_ARBOL[destino_arbol]}) "
                     f"(lift {lift:.1f}): el grafo salta de {TITULO_ARBOL[arbol]} a {TITULO_ARBOL[destino_arbol]}.")
        return self._respuesta(via, nodo, otro, docs, scores, traza, razon, lift=lift)

    def _desde_recuperacion(self, scores, traza):
        def valor(nodo):
            p = nodo.payload
            return scores.get((p.get("origen"), p.get("doc_id")), 0.0) if "doc_id" in p else 0.0

        mejores = []        # (árbol, nodo, parte del total) en orden de prioridad
        acumulado = {}
        for arbol in ARBOLES_RECUPERACION:
            if arbol not in self.B.arboles:
                continue
            raiz = self.B.arbol(arbol).raiz
            acum = acumular_posorden(raiz, valor)
            nodos = list(self.B.conceptos(arbol).values())
            mejor = max(nodos, key=lambda n: (acum[n.id], -n.id))
            total = sum(acum[n.id] for n in nodos)
            mejores.append((arbol, mejor, acum[mejor.id] / total if total else 0.0))
            acumulado[mejor.nombre] = round(acum[mejor.id], 4)
        traza["acumulado_posorden"] = acumulado
        if not mejores or all(share == 0 for _, _, share in mejores):
            return self._sin_relacion("ninguno", traza, "Los documentos recuperados no pertenecen a ningún nodo.")
        arbol, nodo = max(((a, n, s) for a, n, s in mejores), key=lambda x: x[2])[:2]   # empate: el primero
        return self._salto(arbol, nodo, scores, traza, "recuperacion")

    # ------------------------------------------------------------ respuestas
    @staticmethod
    def _ruta(nodo):
        return {"arbol": nodo.arbol, "titulo_arbol": TITULO_ARBOL.get(nodo.arbol, nodo.arbol),
                "nodo_id": nodo.id, "nombre": nodo.nombre,
                "ruta": [n.nombre for n in nodo.ruta()], "ruta_texto": nodo.ruta_texto()}

    def _local(self, nodo, scores, traza, motivo):
        """El nodo se reconoció pero no tiene arista de salida: se responde DENTRO de su árbol
        con los documentos de su subárbol (mejor puntuados; sin puntajes, por id)."""
        hojas = [(n.payload["origen"], n.payload["doc_id"]) for n in preorden(nodo)
                 if n.es_hoja and "doc_id" in n.payload]
        traza["orden_documentos"] = "puntaje TF-IDF" if scores else "id (no hubo puntajes)"
        razon = (f"Tu consulta apunta a «{nodo.nombre}», pero {motivo}; se muestran los documentos "
                 f"de ese mismo nodo ({len(hojas)} en total).")
        return self._respuesta("concepto_local", nodo, nodo, hojas, scores, traza, razon)

    def _respuesta(self, via, origen, destino, docs, scores, traza, razon, lift=None, nodos=None):
        """docs: lista de (origen, doc_id). Orden: puntaje TF-IDF desc, artículos antes que ejercicios
        en empate y luego id (determinista)."""
        ranking = sorted(docs, key=lambda k: (-scores.get(k, 0.0), 0 if k[0] == "articulos" else 1, k[1]))
        if nodos is None:
            nodos = [origen] if origen is destino else [origen, destino]
        return {"via": via, "origen": self._ruta(origen), "destino": self._ruta(destino),
                "nodos": [self._ruta(n) for n in nodos],
                "documentos": [{"origen": o, "doc_id": d} for o, d in ranking[:3]],
                "lift": None if lift is None else round(lift, 3),
                "razon": razon, "traza": traza}

    def _sin_relacion(self, via, traza, razon, alternativa=None, nodos=()):
        out = {"via": via, "origen": None, "destino": None, "nodos": [self._ruta(n) for n in nodos],
               "documentos": [], "lift": None, "razon": razon, "traza": traza}
        if alternativa:
            out["alternativa"] = alternativa
        return out
