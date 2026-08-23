"""
crypto_graph_v1_original.py -- pierwsza wersja (autorstwa uzytkownika,
z jednym fixem: math.random() -> random.random(), ktorego w oryginale
nie ma - math.random nie istnieje, kod nie uruchamialby sie ani razu).
Zachowana dla historii/reprodukcji.

ZNANY SLEPY PUNKT (patrz README.md, sekcja "Historia"): eq domyslnie
= wlasna wartosc startowa wezla ("kim byles na poczatku = twoja norma").
Dynamika po inicjalizacji jest w pelni AUTONOMICZNA (helisa + rezonans +
szum) - state() nigdy nie jest aktualizowany zadnymi zewnetrznymi/zywymi
danymi po konstrukcji.

Konsekwencja, zweryfikowana empirycznie (test_v1_blind_spot.py):
klaster wewnetrznie spojny i odizolowany od reszty grafu (np. pierscien
prania pieniedzy, ktory transferuje glownie miedzy soba, wszyscy o
podobnym/wysokim ryzyku od poczatku) jest CALKOWICIE NIEWIDOCZNY dla
omega_hotspot() - ranga #25-30 z 30, PONIZEJ mediany calej sieci. To
dokladnie odwrotnosc tego, co chcialoby sie wykryc w realnym AML.
Naprawione w v2 (crypto_graph_v2_calibrated.py).
"""
import math
import random
from collections import defaultdict


class CryptoNode:
    def __init__(self, node_id, features, eq=None):
        self.id = node_id
        self.features = features
        self.state = features["risk"]
        self.eq = eq if eq is not None else self.state
        self.history = [self.state]


class TIMDRCryptoField:
    def __init__(self, nodes, edges, helix_k=0.05, temp=0.01, noise=0.001):
        self.nodes = nodes
        self.adj = defaultdict(list)
        for src, dst, w in edges:
            self.adj[src].append((dst, w))
            self.adj[dst].append((src, w))
        self.helix_k = helix_k
        self.temp = temp
        self.noise = noise

    def helix(self, node):
        delta = node.eq - node.state
        drift = math.tanh(delta) * self.helix_k
        return node.state + drift

    def resonance(self, node_id):
        neigh = self.adj[node_id]
        if not neigh:
            return 0.0
        total, wsum = 0.0, 0.0
        for nid, w in neigh:
            total += self.nodes[nid].state * w
            wsum += w
        return (total / wsum) - self.nodes[node_id].state

    def defect(self, node):
        return abs(node.state - node.eq) * self.temp

    def step(self):
        new_states = {}
        for nid, node in self.nodes.items():
            base = self.helix(node)
            res = self.resonance(nid)
            noise = (random.random() - 0.5) * 2 * self.noise
            new_states[nid] = base + res * 0.1 + noise
        for nid, val in new_states.items():
            node = self.nodes[nid]
            node.state = val
            node.history.append(val)

    def omega_hotspot(self):
        ranking = [(nid, self.defect(node)) for nid, node in self.nodes.items()]
        ranking.sort(key=lambda x: x[1], reverse=True)
        return ranking

    def omega_time(self, window=5, percentile=0.25):
        defects = {nid: self.defect(node) for nid, node in self.nodes.items()}
        sorted_vals = sorted(defects.values())
        threshold = sorted_vals[int(len(sorted_vals) * percentile)]
        out = {}
        for nid, node in self.nodes.items():
            hist = node.history[-window:]
            if len(hist) < 2:
                out[nid] = float("inf")
                continue
            Ds = [abs(s - node.eq) for s in hist]
            vel = (Ds[-1] - Ds[0]) / (len(Ds) - 1)
            dist = Ds[-1] - threshold
            out[nid] = dist / abs(vel) if vel < 0 else float("inf")
        return out
