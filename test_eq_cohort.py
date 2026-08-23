"""
test_eq_cohort.py -- peer-group eq PO KOHORTACH (cechy/typ konta), NIE po
krawedziach grafu. Bezposrednia odpowiedz na to, co pokazal
test_eq_definitions.py:

  SELF     - slepy na "zly od poczatku" (ranga #22/30 dla izolowanego
             pierscienia, #11/30 dla pojedynczego wezla)
  PEER_NB  - PSUJE sprawe dla skolegowanych grup: pierscien wychodzi jeszcze
             gorzej (#29/30) niz przy SELF, bo "sasiedzi" kolegow to inni
             kolejarze - peer-group = wspolnicy, nie kontrola
  GLOBAL   - lapie oba chroniczne przypadki (#5/30, #1/30), ale kosztem
             falszywych alarmow na legalnie innej populacji (7/10 top-10 to
             legalny "typ B", przy bazowym poziomie 5/10)

WAZNE ZALOZENIE PROJEKTOWE: cohort_id MUSI pochodzic z cechy NIEZALEZNEJ od
grafu transakcji I niezaleznej od samej wartosci "risk", ktora probujemy
ocenic (inaczej kohorta kolegujacych sie wezlow po prostu wchlonie ich
wlasna anomalie jako "norme kohorty" - dokladnie ten sam blad co PEER_NB,
tylko przez inne drzwi). W realnym AML to typ konta/KYC segment - tutaj
symulowane jako `node_id % liczba_kohort` (dla pierscienia - rozprasza
kolegow miedzy kohorty z normalnymi wezlami) i jako prawdziwy typ konta (dla
scenariusza heterogenicznego).
"""
import numpy as np
from crypto_graph_v2_calibrated import LiveCryptoNode, TIMDRCryptoFieldV2
from test_eq_definitions import run, calibrate_self, calibrate_peer_neighbors, calibrate_global, N, POST_STEPS, CALIB_STEPS

STRATEGIES_EXTENDED = {}


def make_cohort_calibrator(cohort_of):
    def calibrate_cohort(field):
        hist_mean = {nid: float(np.mean(node.history)) for nid, node in field.nodes.items()}
        cohorts = {}
        for nid, c in cohort_of.items():
            cohorts.setdefault(c, []).append(nid)
        cohort_median = {c: float(np.median([hist_mean[n] for n in members])) for c, members in cohorts.items()}
        for nid, node in field.nodes.items():
            node.eq = cohort_median[cohort_of[nid]]
    return calibrate_cohort


def run_with_strategies(N, edges, baseline_mean, seed, strategies, calib_steps=CALIB_STEPS, post_steps=POST_STEPS):
    np.random.seed(seed)
    nodes = {i: LiveCryptoNode(i, baseline_state=baseline_mean[i]) for i in range(N)}
    field = TIMDRCryptoFieldV2(nodes, edges, fast_alpha=0.4, resonance_w=0.05)
    for _ in range(calib_steps):
        live = {i: max(0.0, baseline_mean[i] + np.random.normal(0, 0.02)) for i in range(N)}
        field.step_live(live)
    results = {}
    for name, calib_fn in strategies.items():
        calib_fn(field)
        for _ in range(post_steps):
            live = {i: max(0.0, baseline_mean[i] + np.random.normal(0, 0.02)) for i in range(N)}
            field.step_live(live)
        results[name] = {nid: field.defect(node) for nid, node in field.nodes.items()}
    return results


def report(results, N, target_ids, label):
    print(f"\n{label}")
    for name, defects in results.items():
        ranked = sorted(defects.items(), key=lambda x: x[1], reverse=True)
        rank_of = {nid: i + 1 for i, (nid, d) in enumerate(ranked)}
        med = float(np.median(list(defects.values())))
        worst = max(rank_of[t] for t in target_ids)
        best = min(rank_of[t] for t in target_ids)
        d_range = (min(defects[t] for t in target_ids), max(defects[t] for t in target_ids))
        top10 = set(nid for nid, d in ranked[:10])
        n_in_top10 = len(top10 & set(target_ids))
        print(f"  {name:10s}: ranga celu #{best}-#{worst}/{N}, D {d_range[0]:.4f}-{d_range[1]:.4f}, "
              f"mediana sieci {med:.4f}, w top-10: {n_in_top10}/{len(target_ids)}")


print("=" * 70)
print("SCENARIUSZ A (powtorka): izolowany pierscien, zly od t=0")
print("Kohorta = node_id % 6 (rozprasza 5 kolegow miedzy 6 grup, kazda z ~4-5 normalnymi)")
print("=" * 70)
N_ = 30
RING = [0, 1, 2, 3, 4]
np.random.seed(2)
baseline_mean_a = {i: float(np.random.uniform(0.05, 0.20)) for i in range(N_)}
for i in RING:
    baseline_mean_a[i] = 0.9
edges_a = [(i, j, 1.0) for i in RING for j in RING if i < j]
rng = np.random.RandomState(2)
for i in range(N_):
    if i in RING:
        continue
    targets = rng.choice([x for x in range(N_) if x != i and x not in RING], size=rng.randint(2, 5), replace=False)
    for t in targets:
        edges_a.append((i, int(t), round(float(rng.uniform(0.5, 2.0)), 2)))

cohort_a = {i: i % 6 for i in range(N_)}  # ARBITRALNE, niezalezne od grafu i od "risk"
strategies_a = {
    "SELF": calibrate_self,
    "PEER_NB": calibrate_peer_neighbors,
    "GLOBAL": calibrate_global,
    "COHORT": make_cohort_calibrator(cohort_a),
}
res_a2 = run_with_strategies(N_, edges_a, baseline_mean_a, seed=2, strategies=strategies_a)
report(res_a2, N_, RING, "Izolowany, chronicznie zly pierscien:")
print("  (kazdy czlonek pierscienia trafia do INNEJ kohorty, z 4-5 normalnymi wezlami -")
print("   ich wlasna kolegujaca sie 'norma' NIE staje sie punktem odniesienia)")


print()
print("=" * 70)
print("SCENARIUSZ C (powtorka): populacja heterogeniczna, typ B legalnie inny")
print("Kohorta = PRAWDZIWY typ konta (typ A / typ B), niezalezny od grafu")
print("=" * 70)
np.random.seed(6)
baseline_mean_c = {}
TYPE_B = list(range(15, 30))
for i in range(N_):
    if i in TYPE_B:
        baseline_mean_c[i] = float(np.random.uniform(0.55, 0.65))
    else:
        baseline_mean_c[i] = float(np.random.uniform(0.05, 0.20))
edges_c = []
rng = np.random.RandomState(6)
for i in range(N_):
    targets = rng.choice([x for x in range(N_) if x != i], size=rng.randint(2, 5), replace=False)
    for t in targets:
        edges_c.append((i, int(t), round(float(rng.uniform(0.5, 2.0)), 2)))

cohort_c = {i: ("B" if i in TYPE_B else "A") for i in range(N_)}
strategies_c = {
    "SELF": calibrate_self,
    "PEER_NB": calibrate_peer_neighbors,
    "GLOBAL": calibrate_global,
    "COHORT": make_cohort_calibrator(cohort_c),
}
res_c2 = run_with_strategies(N_, edges_c, baseline_mean_c, seed=6, strategies=strategies_c)
report(res_c2, N_, TYPE_B, "Typ B (legalnie inny, stabilny):")
print("  (chcemy: NISKA ranga / male D / male top-10 - COHORT powinien byc najblizej SELF)")
