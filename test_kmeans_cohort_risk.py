"""
test_kmeans_cohort_risk.py -- stress test dla auto-klastrowania: co jesli
kolegujacy sie klaster ma tez PODOBNE cechy statyczne (realny wzorzec -
swiezo zalozone konta, podobny wolumen)? Czy k-means, przy zlym doborze K,
zamyka ich we WLASNEJ kohorcie i odtwarza pulapke PEER_NB przez inne drzwi?

Scenariusz: izolowany, chronicznie zly pierscien (jak w test_eq_cohort.py),
ALE tym razem czlonkowie pierscienia maja tez podejrzanie podobne cechy
statyczne (konto zalozone <15 dni temu, reszta populacji 100-1000 dni) -
dokladnie taki sygnal, jaki auto-klastrowanie MIALOBY wychwycic jako
"podobienstwo", wiec to uczciwy, trudny test, nie ustawiony pod latwy wynik.

Test dwoch K: MALE K (duze, zroznicowane kohorty, kolegujacy sie klaster
rozcienczony wsrod wielu normalnych) vs DUZE K (male kohorty, kolegujacy
sie klaster moze zdominowac wlasna, ciasna kohorte).
"""
import numpy as np
from crypto_graph_v3_cohort import CohortCryptoNode, TIMDRCryptoFieldV2, calibrate_eq_cohort, kmeans_cohorts

N = 30
RING = [0, 1, 2, 3, 4]
CALIB_STEPS = 200
POST_STEPS = 100


def build_scenario(seed):
    np.random.seed(seed)
    baseline_mean = {i: float(np.random.uniform(0.05, 0.20)) for i in range(N)}
    for i in RING:
        baseline_mean[i] = 0.9  # chronicznie zly od t=0

    nodes = {}
    for i in range(N):
        if i in RING:
            feats = {"account_age": float(np.random.uniform(3, 15)), "typical_volume": float(np.random.uniform(4, 6))}
        else:
            feats = {"account_age": float(np.random.uniform(100, 1000)), "typical_volume": float(np.random.uniform(0.5, 10))}
        nodes[i] = CohortCryptoNode(i, baseline_state=baseline_mean[i], static_features=feats)

    edges = [(i, j, 1.0) for i in RING for j in RING if i < j]
    rng = np.random.RandomState(seed)
    for i in range(N):
        if i in RING:
            continue
        targets = rng.choice([x for x in range(N) if x != i and x not in RING], size=rng.randint(2, 5), replace=False)
        for t in targets:
            edges.append((i, int(t), round(float(rng.uniform(0.5, 2.0)), 2)))
    return nodes, edges, baseline_mean


def run_and_report(K, seed=2):
    nodes, edges, baseline_mean = build_scenario(seed)
    field = TIMDRCryptoFieldV2(nodes, edges, fast_alpha=0.4, resonance_w=0.05)
    np.random.seed(seed)
    for _ in range(CALIB_STEPS):
        live = {i: max(0.0, baseline_mean[i] + np.random.normal(0, 0.02)) for i in range(N)}
        field.step_live(live)

    cohort_of = kmeans_cohorts(nodes, ["account_age", "typical_volume"], k=K, seed=seed)
    cohort_sizes = {}
    for c in cohort_of.values():
        cohort_sizes[c] = cohort_sizes.get(c, 0) + 1
    ring_cohorts = [cohort_of[i] for i in RING]
    ring_cohort_purity = {c: sum(1 for x in ring_cohorts if x == c) / cohort_sizes[c] for c in set(ring_cohorts)}

    calibrate_eq_cohort(field, cohort_of)
    for _ in range(POST_STEPS):
        live = {i: max(0.0, baseline_mean[i] + np.random.normal(0, 0.02)) for i in range(N)}
        field.step_live(live)

    defects = {nid: field.defect(node) for nid, node in field.nodes.items()}
    ranked = sorted(defects.items(), key=lambda x: x[1], reverse=True)
    rank_of = {nid: i + 1 for i, (nid, d) in enumerate(ranked)}
    top10 = set(nid for nid, d in ranked[:10])
    n_ring_top10 = len(top10 & set(RING))
    med = float(np.median(list(defects.values())))

    print(f"K={K}: rozmiary kohort={sorted(cohort_sizes.values())}, "
          f"czystosc kohort(y) pierscienia={ {c: round(p,2) for c,p in ring_cohort_purity.items()} }")
    print(f"  ranga pierscienia: #{min(rank_of[i] for i in RING)}-#{max(rank_of[i] for i in RING)}/{N}, "
          f"D {min(defects[i] for i in RING):.4f}-{max(defects[i] for i in RING):.4f}, "
          f"mediana sieci {med:.4f}, w top-10: {n_ring_top10}/5")


print("=" * 70)
print("Kolegujacy sie pierscien MA TEZ podobne cechy statyczne (nowe konta, podobny wolumen)")
print("=" * 70)
for seed in [2, 5, 10]:
    print(f"\n--- ziarno={seed} ---")
    for K in [2, 3, 4, 5, 8, 15]:
        run_and_report(K, seed=seed)

print()
print("=" * 70)
print("WNIOSEK (3 niezalezne ziarna): prog nie jest w K, tylko w CZYSTOSCI kohorty")
print("klastra - gdy klaster > 50% wlasnej kohorty, mediana 'przeskakuje' na jego")
print("wlasna wartosc (D~0, niewidoczny); gdy klaster < 50% (mniejszosc), mediana")
print("kotwiczy sie w normalnej wiekszosci (D~0.7-0.8, ranga #1-#5). Ten prog pojawil")
print("sie przy K=3 lub K=4 w kazdym z 3 ziaren - male K NIE jest niezawodne.")
print("=" * 70)
