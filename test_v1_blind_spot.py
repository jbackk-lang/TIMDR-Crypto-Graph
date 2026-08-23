"""
test_v1_blind_spot.py -- dowod na slepy punkt v1: izolowany, wewnetrznie
spojny klaster (np. pierscien prania pieniedzy transferujacy glownie miedzy
soba) jest CALKOWICIE NIEWIDOCZNY dla omega_hotspot(), bo eq = wlasna
wartosc startowa wezla -> defekt startuje od 0 i nigdy realnie nie rosnie
dla klastra, ktory zgadza sie sam ze soba.
"""
import numpy as np
from crypto_graph_v1_original import CryptoNode, TIMDRCryptoField
from demo_graph import N, RING, build_edges

np.random.seed(2)

nodes = {}
for i in range(N):
    risk = float(np.random.uniform(0.05, 0.20))
    nodes[i] = CryptoNode(i, {"risk": risk})

for i in RING:
    nodes[i] = CryptoNode(i, {"risk": 0.9})  # identyczne, PRZED zbudowaniem grafu

edges = build_edges(seed=2)
field = TIMDRCryptoField(nodes, edges, helix_k=0.05, temp=0.01, noise=0.001)

for _ in range(300):
    field.step()

hotspots = field.omega_hotspot()
ranks = {nid: i + 1 for i, (nid, d) in enumerate(hotspots)}

print("v1: izolowany pierscien 5 wezlow, ryzyko 0.9, polaczenia TYLKO miedzy soba")
for i in RING:
    print(f"  wezel {i}: ranga #{ranks[i]}/{N}, D={dict(hotspots)[i]:.6f}")
median_d = np.median([d for _, d in hotspots])
print(f"mediana D calej sieci: {median_d:.6f}")

worst_rank = max(ranks[i] for i in RING)
assert worst_rank >= N - len(RING), (
    f"oczekiwano, ze pierscien bedzie w DOLNEJ czesci rankingu (slepy punkt) - "
    f"najlepsza ranga w pierscieniu to #{min(ranks[i] for i in RING)}, coś się zmieniło"
)
print("\nPOTWIERDZONE: pierscien niewidoczny (dolna czesc rankingu, ponizej/przy medianie).")
