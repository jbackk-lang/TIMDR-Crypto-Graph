"""
crypto_graph_v2_calibrated.py -- naprawiona wersja, zweryfikowana empirycznie
(test_v2_fix_verified.py) na tym samym scenariuszu, ktory w v1 byl calkowicie
niewidoczny.

Dwie zmiany wzgledem v1 (crypto_graph_v1_original.py), obie konieczne razem:

1. eq[node] = SREDNIA STANU Z OKRESU KALIBRACJI ("kim bylem, zanim zaczelo
   sie cokolwiek podejrzanego"), nie wlasna wartosc startowa. Dokladnie ten
   sam wzorzec co kalibracja progu STA/LTA na czysto szumowym oknie (patrz
   siostrzany projekt TIMDR-Quantum-Lattice / test sejsmiczny w tej samej
   rodzinie) - inna domena, ten sam pattern: naucz sie "normy" z okresu, o
   ktorym wiesz, ze nic podejrzanego jeszcze sie nie dzialo, ZANIM zaczniesz
   flagowac odchylenia.

2. state(t) jest napedzany ZYWYMI DANYMI z zewnatrz (step_live(live_values)),
   nie autonomiczna dynamika. Helisa przestaje ciagnac stan do eq (eq juz nie
   jest "celem" dynamiki) - staje sie filtrem EMA wygladzajacym szum
   przychodzacej obserwacji. Rezonans zostaje jako lekka modulacja od
   sasiadow w grafie (peer pressure), ale glownym zrodlem stanu jest
   napiywajacy sygnal, nie sama siatka.

WYNIK (test_v2_fix_verified.py, ten sam scenariusz co test_v1_blind_spot.py):
izolowany, wewnetrznie spojny pierscien 5 wezlow, ktory w v1 mial range
#25-30 z 30 (ponizej mediany), w v2 zajmuje TOP-5 z 30, D > 100x mediana
sieci, gdy zaczyna dryfowac w gore PO okresie kalibracji.

WCIAZ NIE JEST TO GOTOWE NARZEDZIE AML - patrz README.md, sekcja
"Czego to NIE jest".
"""
from collections import defaultdict
import numpy as np


class LiveCryptoNode:
    def __init__(self, node_id, baseline_state=0.0):
        self.id = node_id
        self.state = baseline_state
        self.eq = None  # ustawiane przez calibrate_eq() po okresie kalibracji
        self.history = [self.state]


class TIMDRCryptoFieldV2:
    def __init__(self, nodes, edges, fast_alpha=0.4, resonance_w=0.05):
        """
        nodes: dict {node_id: LiveCryptoNode}
        edges: list[(src_id, dst_id, weight)]
        fast_alpha: sila filtru EMA (state goni live_value) - wyzsze = mniej
            wygladzania, szybsza reakcja na zywe dane, ale wiecej szumu.
        resonance_w: waga modulacji od sasiadow w grafie (peer pressure) --
            NIE wchodzi do defektu/omega, tylko modulowanie samego state()
            (lekcja z TIMDR-Quantum-Lattice: rezonans jako skladnik Omega
            szkodzil we WSZYSTKICH dotad przetestowanych wariantach).
        """
        self.nodes = nodes
        self.adj = defaultdict(list)
        for src, dst, w in edges:
            self.adj[src].append((dst, w))
            self.adj[dst].append((src, w))
        self.fast_alpha = fast_alpha
        self.resonance_w = resonance_w

    def resonance(self, node_id):
        neigh = self.adj[node_id]
        if not neigh:
            return 0.0
        total, wsum = 0.0, 0.0
        for nid, w in neigh:
            total += self.nodes[nid].state * w
            wsum += w
        return (total / wsum) - self.nodes[node_id].state

    def step_live(self, live_values):
        """live_values: dict {node_id: nowa zywa obserwacja w tym kroku}
        (np. dzisiejszy wynik risk-scoringu z realnego pipeline'u on-chain)."""
        new_states = {}
        for nid, node in self.nodes.items():
            live = live_values[nid]
            res = self.resonance(nid)
            new_states[nid] = (
                (1 - self.fast_alpha) * node.state
                + self.fast_alpha * live
                + res * self.resonance_w
            )
        for nid, val in new_states.items():
            node = self.nodes[nid]
            node.state = val
            node.history.append(val)

    def calibrate_eq(self):
        """Wywolaj PO okresie kalibracji (dane, o ktorych wiesz, ze nie
        zawieraja jeszcze niczego podejrzanego). eq = srednia przefiltrowanego
        stanu z tego okresu, per wezel."""
        for node in self.nodes.values():
            node.eq = float(np.mean(node.history))

    def defect(self, node):
        if node.eq is None:
            raise RuntimeError(f"wezel {node.id}: wywolaj calibrate_eq() przed defect()")
        return abs(node.state - node.eq)

    def omega_hotspot(self):
        ranking = [(nid, self.defect(node)) for nid, node in self.nodes.items()]
        ranking.sort(key=lambda x: x[1], reverse=True)
        return ranking
