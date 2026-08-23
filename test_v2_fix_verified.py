"""
test_v2_fix_verified.py -- dowod, ze poprawka dziala: TEN SAM graf co
test_v1_blind_spot.py (izolowany pierscien 5 wezlow), ale test uczciwy: w
okresie kalibracji pierscien zachowuje sie STATYSTYCZNIE TAK SAMO jak reszta
sieci (eq liczy sie z tego okresu, wiec zero wbudowanego cheatu). Dopiero PO
kalibracji pierscien zaczyna dryfowac w gore, skorelowanie, jako jedyny sygnal.
"""
import numpy as np
from crypto_graph_v2_calibrated import LiveCryptoNode, TIMDRCryptoFieldV2
from demo_graph import N, RING, build_edges

np.random.seed(3)

CALIB_STEPS = 200
POST_STEPS = 150
INJECT_AT = 30
RAMP_LEN = 40
TARGET_RISK = 0.85

baseline_mean = {i: float(np.random.uniform(0.05, 0.20)) for i in range(N)}
nodes = {i: LiveCryptoNode(i, baseline_state=baseline_mean[i]) for i in range(N)}
edges = build_edges(seed=3)
field = TIMDRCryptoFieldV2(nodes, edges)

# --- kalibracja: WSZYSCY, w tym pierscien, zachowuja sie tak samo (zwykly szum) ---
for _ in range(CALIB_STEPS):
    live = {i: max(0.0, baseline_mean[i] + np.random.normal(0, 0.02)) for i in range(N)}
    field.step_live(live)

field.calibrate_eq()
print("Po kalibracji (pierscien NIE byl jeszcze niczym rozny):")
for i in RING:
    print(f"  wezel {i}: eq={nodes[i].eq:.4f} (baseline_mean={baseline_mean[i]:.4f})")

# --- post-kalibracja: pierscien dryfuje w gore, skorelowanie; reszta normalnie ---
for t in range(POST_STEPS):
    live = {}
    for i in range(N):
        if i in RING and t >= INJECT_AT:
            progress = min(1.0, (t - INJECT_AT) / RAMP_LEN)
            val = baseline_mean[i] + progress * (TARGET_RISK - baseline_mean[i]) + np.random.normal(0, 0.02)
        else:
            val = baseline_mean[i] + np.random.normal(0, 0.02)
        live[i] = max(0.0, val)
    field.step_live(live)

hotspots = field.omega_hotspot()
ranks = {nid: i + 1 for i, (nid, d) in enumerate(hotspots)}
median_d = np.median([d for _, d in hotspots])

print(f"\nPo {POST_STEPS} krokach post-kalibracyjnych (pierscien dryfowal od kroku {INJECT_AT}):")
for i in RING:
    print(f"  wezel {i}: ranga #{ranks[i]}/{N}, D={dict(hotspots)[i]:.4f}")
print(f"mediana D calej sieci: {median_d:.4f}")

worst_rank = max(ranks[i] for i in RING)
assert worst_rank <= len(RING) + 2, (
    f"oczekiwano, ze cały pierscien wejdzie w okolice top-{len(RING)} - "
    f"najgorsza ranga w pierscieniu to #{worst_rank}, poprawka nie zadziałała jak oczekiwano"
)
print("\nPOTWIERDZONE: caly pierscien w top rankingu, D >> mediana sieci.")
