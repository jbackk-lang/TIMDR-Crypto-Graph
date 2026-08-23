"""
test_eq_definitions.py -- PRZED wdrozeniem peer-group eq: sprawdzam trzy
definicje eq na trzech scenariuszach, zamiast zakladac ktora dziala.

Trzy definicje (wszystkie liczone z tego samego okresu kalibracji):
  SELF     - srednia WLASNEJ historii wezla (to co jest w v2 teraz)
  PEER_NB  - srednia stanu BEZPOSREDNICH SASIADOW w grafie (najbardziej
             oczywista literalna implementacja "peer-group eq")
  GLOBAL   - mediana CALEJ populacji (wszystkie wezly)

Trzy scenariusze:
  A. Izolowany pierscien, chronicznie zly OD SAMEGO POCZATKU kalibracji
     (nie dryfuje po kalibracji - jest taki od t=0). To jest dokladnie ten
     przypadek, ktory Twoje rozumowanie identyfikuje jako "jedyny pozostaly
     slepy punkt".
  B. Pojedynczy chronicznie zly wezel, ale NORMALNIE polaczony z siecia
     (nie izolowany) - kontrola: czy PEER_NB dziala tam, gdzie powinien.
  C. Populacja HETEROGENICZNA: polowa wezlow to legalnie inny "typ" (np.
     gieldowy hot-wallet, naturalnie wyzszy poziom aktywnosci), stabilny
     przez caly czas, NIC anomalnego sie nie dzieje. Test na falszywe alarmy.
"""
import numpy as np
from crypto_graph_v2_calibrated import LiveCryptoNode, TIMDRCryptoFieldV2

CALIB_STEPS = 200
POST_STEPS = 100


def calibrate_self(field):
    for node in field.nodes.values():
        node.eq = float(np.mean(node.history))


def calibrate_peer_neighbors(field):
    hist_mean = {nid: float(np.mean(node.history)) for nid, node in field.nodes.items()}
    for nid, node in field.nodes.items():
        neigh = field.adj[nid]
        if not neigh:
            node.eq = hist_mean[nid]
            continue
        total, wsum = 0.0, 0.0
        for nnid, w in neigh:
            total += hist_mean[nnid] * w
            wsum += w
        node.eq = total / wsum


def calibrate_global(field):
    all_means = [float(np.mean(node.history)) for node in field.nodes.values()]
    g = float(np.median(all_means))
    for node in field.nodes.values():
        node.eq = g


STRATEGIES = {"SELF": calibrate_self, "PEER_NB": calibrate_peer_neighbors, "GLOBAL": calibrate_global}


def run(N, edges, baseline_mean, seed, calib_steps=CALIB_STEPS, post_steps=POST_STEPS):
    """Chronicznie zle wezly maja swoj TARGET baseline_mean juz OD t=0 -
    zero dryfu, zero zdarzenia do wykrycia - test czy eq w ogole to zlapie."""
    np.random.seed(seed)
    nodes = {i: LiveCryptoNode(i, baseline_state=baseline_mean[i]) for i in range(N)}
    field = TIMDRCryptoFieldV2(nodes, edges, fast_alpha=0.4, resonance_w=0.05)
    for _ in range(calib_steps):
        live = {i: max(0.0, baseline_mean[i] + np.random.normal(0, 0.02)) for i in range(N)}
        field.step_live(live)

    results = {}
    for name, calib_fn in STRATEGIES.items():
        calib_fn(field)
        for _ in range(post_steps):
            live = {i: max(0.0, baseline_mean[i] + np.random.normal(0, 0.02)) for i in range(N)}
            field.step_live(live)
        defects = {nid: field.defect(node) for nid, node in field.nodes.items()}
        results[name] = defects
    return results


def report_ranks(results, N, target_ids, label):
    print(f"\n{label}")
    for name, defects in results.items():
        ranked = sorted(defects.items(), key=lambda x: x[1], reverse=True)
        rank_of = {nid: i + 1 for i, (nid, d) in enumerate(ranked)}
        med = float(np.median(list(defects.values())))
        worst = max(rank_of[t] for t in target_ids)
        d_range = (min(defects[t] for t in target_ids), max(defects[t] for t in target_ids))
        print(f"  {name:8s}: najgorsza ranga celu #{worst}/{N}, D celu {d_range[0]:.4f}-{d_range[1]:.4f}, "
              f"mediana sieci {med:.4f}")


print("=" * 70)
print("SCENARIUSZ A: izolowany pierscien, zly OD t=0 (nie dryfuje - byl taki caly czas)")
print("=" * 70)
N = 30
RING = [0, 1, 2, 3, 4]
np.random.seed(2)
baseline_mean_a = {i: float(np.random.uniform(0.05, 0.20)) for i in range(N)}
for i in RING:
    baseline_mean_a[i] = 0.9  # chroniczny, od samego poczatku
edges_a = [(i, j, 1.0) for i in RING for j in RING if i < j]
rng = np.random.RandomState(2)
for i in range(N):
    if i in RING:
        continue
    targets = rng.choice([x for x in range(N) if x != i and x not in RING], size=rng.randint(2, 5), replace=False)
    for t in targets:
        edges_a.append((i, int(t), round(float(rng.uniform(0.5, 2.0)), 2)))
res_a = run(N, edges_a, baseline_mean_a, seed=2)
report_ranks(res_a, N, RING, "Izolowany pierscien, chronicznie zly:")


print()
print("=" * 70)
print("SCENARIUSZ B: pojedynczy chronicznie zly wezel, NORMALNIE polaczony (nie izolowany)")
print("=" * 70)
np.random.seed(4)
baseline_mean_b = {i: float(np.random.uniform(0.05, 0.20)) for i in range(N)}
BAD_NODE = 0
baseline_mean_b[BAD_NODE] = 0.9
edges_b = []
rng = np.random.RandomState(4)
for i in range(N):
    targets = rng.choice([x for x in range(N) if x != i], size=rng.randint(2, 5), replace=False)
    for t in targets:
        edges_b.append((i, int(t), round(float(rng.uniform(0.5, 2.0)), 2)))
res_b = run(N, edges_b, baseline_mean_b, seed=4)
report_ranks(res_b, N, [BAD_NODE], "Pojedynczy chronicznie zly wezel, normalnie wtopiony w siec:")


print()
print("=" * 70)
print("SCENARIUSZ C: populacja HETEROGENICZNA - polowa wezlow to inny, LEGALNY typ")
print("(np. gieldowy hot-wallet: naturalnie wyzszy poziom aktywnosci, stabilny, nic anomalnego)")
print("=" * 70)
np.random.seed(6)
baseline_mean_c = {}
TYPE_B = list(range(15, 30))  # 15 wezlow "typu B" - stabilnie wyzszy poziom
for i in range(N):
    if i in TYPE_B:
        baseline_mean_c[i] = float(np.random.uniform(0.55, 0.65))
    else:
        baseline_mean_c[i] = float(np.random.uniform(0.05, 0.20))
edges_c = []
rng = np.random.RandomState(6)
for i in range(N):
    targets = rng.choice([x for x in range(N) if x != i], size=rng.randint(2, 5), replace=False)
    for t in targets:
        edges_c.append((i, int(t), round(float(rng.uniform(0.5, 2.0)), 2)))
res_c = run(N, edges_c, baseline_mean_c, seed=6)
report_ranks(res_c, N, TYPE_B, "Typ B (15 legalnie innych wezlow, STABILNYCH, nic sie nie zmienia):")
print("  (chcemy: te wezly NIE powinny byc top hotspotami - nic anomalnego nie robia,")
print("   sa tylko strukturalnie inne od reszty populacji)")
