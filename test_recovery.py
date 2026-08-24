"""
test_recovery.py -- pytanie uzytkownika: gdy pierscien (5 wezlow) po anomalii
WRACA do zachowania takiego jak reszta sieci (0.1-0.2), czy defect() tez
wraca w dol, czy zostaje trwale podniesiony (bo eq jest zamrozone po
kalibracji, a state to tylko EMA)?

Skrypt uzytkownika zakladal API ktorego nie ma (demo_graph(), field.eq,
field.defect(int)) - poprawiono pod realne API repo:
- demo_graph.py: N, RING, build_edges(seed) -- nie demo_graph()
- TIMDRCryptoFieldV2(nodes: dict[int, LiveCryptoNode], edges: list)
- eq jest per-node (node.eq), ustawiane przez field.calibrate_eq()
- defect() przyjmuje obiekt node, nie int
"""
import numpy as np
from crypto_graph_v2_calibrated import LiveCryptoNode, TIMDRCryptoFieldV2
from demo_graph import N, RING, build_edges

np.random.seed(7)

CALIB_STEPS = 200
ANOMALY_STEPS = 50
RECOVERY_STEPS = 200

nodes = {i: LiveCryptoNode(i, baseline_state=0.0) for i in range(N)}
edges = build_edges(seed=7)
field = TIMDRCryptoFieldV2(nodes, edges)

# --- 1. KALIBRACJA ---
for _ in range(CALIB_STEPS):
    live = {i: np.random.uniform(0.1, 0.2) for i in range(N)}
    field.step_live(live)

field.calibrate_eq()
eq_snapshot = {i: nodes[i].eq for i in range(N)}

# --- 2. ANOMALIA (pierscien skok do 0.85, caly czas trwania anomalii) ---
for _ in range(ANOMALY_STEPS):
    live = {i: np.random.uniform(0.1, 0.2) for i in range(N)}
    for r in RING:
        live[r] = 0.85
    field.step_live(live)

peak_defect = {i: field.defect(nodes[i]) for i in range(N)}

# --- 3. POWROT DO NORMY (0.1-0.2 dla WSZYSTKICH, w tym pierscienia) ---
for _ in range(RECOVERY_STEPS):
    live = {i: np.random.uniform(0.1, 0.2) for i in range(N)}
    field.step_live(live)

final_defect = {i: field.defect(nodes[i]) for i in range(N)}

# --- WYNIKI ---
print("=== EQ po kalibracji (pierscien) ===")
for r in RING:
    print(f"  ring[{r}] eq = {eq_snapshot[r]:.4f}")

print("\n=== Defekt w szczycie anomalii (pierscien) ===")
for r in RING:
    print(f"  ring[{r}] D_peak = {peak_defect[r]:.4f}")
median_peak = np.median(list(peak_defect.values()))
print(f"  mediana D calej sieci w szczycie: {median_peak:.4f}")

print("\n=== Defekt po pelnym powrocie do normy (pierscien) ===")
for r in RING:
    print(f"  ring[{r}] D_final = {final_defect[r]:.4f}")
median_final = np.median(list(final_defect.values()))
print(f"  mediana D calej sieci po powrocie: {median_final:.4f}")

print("\n=== Ranga po powrocie do normy ===")
ranking = field.omega_hotspot()
for pos, (node_id, D) in enumerate(ranking[:10], start=1):
    tag = " <-- RING" if node_id in RING else ""
    print(f"  #{pos}: node {node_id}, D={D:.4f}{tag}")

print("\n=== Ranga pierscienia konkretnie ===")
ranks = {nid: i + 1 for i, (nid, d) in enumerate(ranking)}
for r in RING:
    print(f"  ring[{r}]: ranga #{ranks[r]}/{N}, D={dict(ranking)[r]:.4f}")

print("\n=== WNIOSEK ===")
avg_peak_ring = np.mean([peak_defect[r] for r in RING])
avg_final_ring = np.mean([final_defect[r] for r in RING])
decay_ratio = avg_final_ring / avg_peak_ring if avg_peak_ring > 0 else float("nan")
print(f"srednie D pierscienia: szczyt={avg_peak_ring:.4f} -> po powrocie={avg_final_ring:.4f} "
      f"(spadek do {decay_ratio*100:.1f}% szczytu)")
print(f"po powrocie D pierscienia vs mediana sieci: {avg_final_ring/median_final:.2f}x mediany")

# --- ASERCJE (sprawdzone na 5 niezaleznych ziarnach [1,2,3,4,5] przed
# wpisaniem progow - wyniki: decay 0.8-2.2% szczytu, final_vs_median
# 0.79-1.29x, najgorsza ranga pierscienia po powrocie #24-#30/30) ---
assert decay_ratio < 0.10, (
    f"defect() nie zapomina anomalii wystarczajaco szybko: po {RECOVERY_STEPS} "
    f"krokach normalnego zachowania D pierscienia to wciaz {decay_ratio*100:.1f}% szczytu"
)
assert avg_final_ring < median_final * 2.0, (
    f"pierscien wciaz wyraznie odstaje od sieci po powrocie do normy "
    f"({avg_final_ring:.4f} vs mediana {median_final:.4f}) - mozliwy trwaly false-positive"
)
print("\nPOTWIERDZONE: po pelnym powrocie do normalnego zachowania, defect() "
      "'zapomina' anomalie - D pierscienia spada do jednocyfrowych % szczytu i "
      "wraca w okolice mediany sieci (brak trwalego false-positive).")
