"""demo_graph.py -- wspolny generator sieci testowej dla test_v1_blind_spot.py
i test_v2_fix_verified.py, zeby oba testy uzywaly DOKLADNIE tej samej
struktury grafu (30 wezlow, izolowany pierscien 5 wezlow polaczonych
tylko miedzy soba + reszta siatki normalnie polaczona z reszta)."""
import random
import numpy as np

N = 30
RING = [0, 1, 2, 3, 4]


def build_edges(seed):
    random.seed(seed)
    edges = []
    node_ids = list(range(N))
    for i in RING:
        for j in RING:
            if i < j:
                edges.append((i, j, 1.0))
    for i in node_ids:
        if i in RING:
            continue
        n_edges = random.randint(2, 4)
        targets = random.sample(
            [x for x in node_ids if x != i and x not in RING],
            min(n_edges, N - len(RING) - 1),
        )
        for t in targets:
            edges.append((i, t, round(random.uniform(0.5, 2.0), 2)))
    return edges
