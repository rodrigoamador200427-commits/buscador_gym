"""Motor de relación consulta -> árboles -> salto entre árboles.

Reemplaza a motor_grafos.py. Diferencias de fondo:
  * trabaja con las RAÍCES que ya produce el pipeline de NLP (no con texto crudo);
  * los conceptos salen de la taxonomía y de los datos, no de una tabla tecleada;
  * es DETERMINISTA: la misma consulta da siempre la misma respuesta;
  * si no hay relación lo dice (via = 'ninguno') en vez de inventar una.

Política de decisión (cada respuesta declara cuál nivel la produjo en `via`):
  1. 'interseccion'     la consulta nombra un músculo Y un tema, y hay artículos que los unen.
  2. 'sin_interseccion' nombra ambos pero ningún artículo los relaciona (se dice, no se inventa).
  3. 'concepto'         nombra solo un músculo o solo un tema -> salto por la mejor arista (lift).
     'concepto_local'   lo nombra, pero no tiene aristas de salida -> responde dentro de su árbol.
  4. 'recuperacion'     no nombra conceptos, pero TF-IDF recuperó documentos: se acumulan en
                        posorden sobre ambos árboles y se salta desde el nodo con más peso.
  5. 'ninguno'          nada que relacionar.
"""
from collections import Counter

from .recorridos import acumular_posorden, preorden
from .taxonomia import (ALIAS_MUSCULO, ETIQUETA_A_MUSCULO, SINONIMOS_TEMA, TEMAS, normalizar)


def _frase_a_raices(frase, stem):
    return frozenset(stem(p) for p in normalizar(frase).split() if p)


class MotorArboles:
    def __init__(self, anatomia, temas, aristas, stem):
        """stem: función palabra -> raíz (la misma del indexador, p. ej. SnowballStemmer.stem)."""
        self.A, self.T, self.E, self.stem = anatomia, temas, aristas, stem
        self._musculos = anatomia.meta["musculos"]        # grupo_id -> Nodo
        self._temas = temas.meta["temas"]                 # nombre -> Nodo
        self._orden_tema = {t: i for i, (_, t, _) in enumerate(TEMAS)}

        # índice de conceptos: lista de (clave, frozenset de raíces)
        self._idx_musculo = [(gid, _frase_a_raices(tag, stem)) for tag, gid in ETIQUETA_A_MUSCULO.items()]
        for alias, gids in ALIAS_MUSCULO.items():
            self._idx_musculo += [(gid, _frase_a_raices(alias, stem)) for gid in gids]
        self._idx_tema = []
        for _, tema, tags in TEMAS:
            self._idx_tema += [(tema, _frase_a_raices(t, stem)) for t in tags]
        for tema, frases in SINONIMOS_TEMA.items():
            self._idx_tema += [(tema, _frase_a_raices(f, stem)) for f in frases]

    # ------------------------------------------------------------------ API
    def descubrir(self, raices, recuperados=()):
        """raices: raíces de la consulta. recuperados: [(origen, doc_id, score)] del índice TF-IDF."""
        consulta = set(raices)
        scores = {(o, d): s for o, d, s in recuperados}
        musculos = self._coincidencias(self._idx_musculo, consulta)
        temas = self._coincidencias(self._idx_tema, consulta)
        traza = {"conceptos_musculo": [self._musculos[g].nombre for g in musculos],
                 "conceptos_tema": list(temas), "documentos_recuperados": len(scores)}

        if musculos and temas:
            m, t = self._mejor_musculo(musculos), self._mejor_tema(temas)
            docs = self._articulos(self.E.docs(m.id, self._temas[t].id))
            if docs:
                return self._respuesta("interseccion", m, self._temas[t], docs, scores, traza,
                                       f"Tu consulta combina «{m.nombre}» y «{t}»: "
                                       f"{len(docs)} artículos conectan ambos árboles.")
            alt = self._salto_desde_musculo(m, scores, traza, "concepto")
            return self._sin_relacion(
                "sin_interseccion", traza,
                f"Ningún artículo relaciona «{m.nombre}» con «{t}»; el sistema no inventa una relación.",
                alternativa=alt)
        if temas:
            return self._salto_desde_tema(self._temas[self._mejor_tema(temas)], scores, traza, "concepto")
        if musculos:
            return self._salto_desde_musculo(self._mejor_musculo(musculos), scores, traza, "concepto")
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

    def _mejor_musculo(self, conteo):
        # más coincidencias; luego el músculo con más evidencia en artículos; luego id
        return self._musculos[min(conteo, key=lambda g: (-conteo[g],
                                                         -self.E.n_docs_musculo(self._musculos[g].id), g))]

    def _mejor_tema(self, conteo):
        return min(conteo, key=lambda t: (-conteo[t], self._orden_tema[t]))

    # ---------------------------------------------------------------- saltos
    def _salto_desde_tema(self, tema, scores, traza, via):
        vec = self.E.vecinos_de_tema(tema.id) or self.E.vecinos_de_tema(tema.id, min_soporte=1)
        if not vec:
            return self._local(tema, scores, traza, "ningún artículo lo relaciona con un músculo")
        id_m, peso, lift = vec[0]
        m = self.A.nodo(id_m)
        docs = self._articulos(self.E.docs(id_m, tema.id))
        razon = (f"Tu consulta apunta al tema «{tema.nombre}». De {self.E.n_docs_tema(tema.id)} artículos "
                 f"sobre ese tema, {peso} también tratan «{m.nombre}» (lift {lift:.1f}): "
                 f"el grafo salta de Temas a Anatomía.")
        return self._respuesta(via, tema, m, docs, scores, traza, razon, lift=lift)

    def _salto_desde_musculo(self, musculo, scores, traza, via):
        vec = self.E.vecinos_de_musculo(musculo.id) or self.E.vecinos_de_musculo(musculo.id, min_soporte=1)
        if not vec:
            return self._local(musculo, scores, traza, "ningún artículo lo relaciona con un tema")
        id_t, peso, lift = vec[0]
        t = self.T.nodo(id_t)
        docs = self._articulos(self.E.docs(musculo.id, id_t))
        razon = (f"Tu consulta apunta a «{musculo.nombre}». De {self.E.n_docs_musculo(musculo.id)} artículos "
                 f"sobre ese músculo, {peso} tratan «{t.nombre}» (lift {lift:.1f}): "
                 f"el grafo salta de Anatomía a Temas.")
        return self._respuesta(via, musculo, t, docs, scores, traza, razon, lift=lift)

    def _desde_recuperacion(self, scores, traza):
        def valor(nodo):
            p = nodo.payload
            return scores.get((p.get("origen"), p.get("doc_id")), 0.0) if "doc_id" in p else 0.0

        acum_a = acumular_posorden(self.A.raiz, valor)
        acum_t = acumular_posorden(self.T.raiz, valor)
        mejor_m = max(self._musculos.values(), key=lambda n: (acum_a[n.id], -n.id))
        mejor_t = max(self._temas.values(), key=lambda n: (acum_t[n.id], -n.id))
        total_a = sum(acum_a[n.id] for n in self._musculos.values())
        total_t = sum(acum_t[n.id] for n in self._temas.values())
        share_a = acum_a[mejor_m.id] / total_a if total_a else 0.0
        share_t = acum_t[mejor_t.id] / total_t if total_t else 0.0
        traza["acumulado_posorden"] = {mejor_m.nombre: round(acum_a[mejor_m.id], 4),
                                       mejor_t.nombre: round(acum_t[mejor_t.id], 4)}
        if share_a == 0 and share_t == 0:
            return self._sin_relacion("ninguno", traza, "Los documentos recuperados no pertenecen a ningún nodo.")
        if share_a >= share_t:
            return self._salto_desde_musculo(mejor_m, scores, traza, "recuperacion")
        return self._salto_desde_tema(mejor_t, scores, traza, "recuperacion")

    # ------------------------------------------------------------ respuestas
    @staticmethod
    def _ruta(nodo):
        return {"arbol": nodo.arbol, "nodo_id": nodo.id, "nombre": nodo.nombre,
                "ruta": [n.nombre for n in nodo.ruta()], "ruta_texto": nodo.ruta_texto()}

    @staticmethod
    def _articulos(ids):
        return [("articulos", d) for d in ids]

    def _local(self, nodo, scores, traza, motivo):
        """El nodo se reconoció pero no tiene arista de salida: se responde DENTRO de su árbol
        con los documentos de su subárbol (mejor puntuados; sin puntajes, por id)."""
        hojas = [(n.payload["origen"], n.payload["doc_id"]) for n in preorden(nodo)
                 if n.es_hoja and "doc_id" in n.payload]
        traza["orden_documentos"] = "puntaje TF-IDF" if scores else "id (no hubo puntajes)"
        razon = (f"Tu consulta apunta a «{nodo.nombre}», pero {motivo}; se muestran los documentos "
                 f"de ese mismo nodo ({len(hojas)} en total).")
        return self._respuesta("concepto_local", nodo, nodo, hojas, scores, traza, razon)

    def _respuesta(self, via, origen, destino, docs, scores, traza, razon, lift=None):
        """docs: lista de (origen, doc_id). Orden: puntaje TF-IDF desc, luego id (determinista)."""
        ranking = sorted(docs, key=lambda k: (-scores.get(k, 0.0), k[1]))
        return {"via": via, "origen": self._ruta(origen), "destino": self._ruta(destino),
                "documentos": [{"origen": o, "doc_id": d} for o, d in ranking[:3]],
                "lift": None if lift is None else round(lift, 3),
                "razon": razon, "traza": traza}

    @staticmethod
    def _sin_relacion(via, traza, razon, alternativa=None):
        out = {"via": via, "origen": None, "destino": None, "documentos": [], "lift": None,
               "razon": razon, "traza": traza}
        if alternativa:
            out["alternativa"] = alternativa
        return out
