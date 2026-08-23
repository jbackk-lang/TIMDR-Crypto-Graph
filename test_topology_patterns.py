"""
test_topology_patterns.py -- v2 na 4 wzorcach AML, nie tylko na pierscieniu.

WAZNE ZASTRZEZENIE ZNALEZIONE PRZY BUDOWIE TEGO TESTU (nie zalozone, tylko
odczytane wprost z kodu v1/v2): graf jest NIESKIEROWANY. `TIMDRCryptoField`/
`TIMDRCryptoFieldV2` buduja `adj` symetrycznie (`self.adj[src].append((dst,w));
self.adj[dst].append((src,w))`) niezaleznie od kolejnosci (src,dst) na wejsciu.
Konsekwencja: "gwiazda" (wiele wezlow -> jeden centralny, wzorzec botow/scamow)
i "rozgalezienie" (jeden wezel -> wiele, wzorzec wash-tradingu) sa TOPOLOGICZNIE
NIEODROZNIALNE dla tego modelu - to ten sam ksztalt grafu (hub + liscie), rozni
je tylko KIEDY/GDZIE pojawia sie anomalia (w hubie vs w jednym lisciu), nie
struktura krawedzi. Test to wprost sprawdza zamiast to ukrywac.

Cztery scenariusze, kazdy embedded w sieci 30 wezlow (reszta = tlo, losowo
polaczone miedzy soba, normalne zachowanie):

1. GWIAZDA - hub + 8 lisci, anomalia wstrzykiwana W HUBIE (agregacja/dystrybucja
   z centralnego punktu - boty, scamy zbierajace od wielu ofiar).
2. ROZGALEZIENIE - TA SAMA gwiazda, anomalia wstrzykiwana w JEDNYM LISCIU
   (jeden zly aktor rozsiewajacy do wspolnikow - wash trading). Test: czy
   detekcja zalezy od tego GDZIE w gwiezdzie pojawia sie sygnal, nie tylko
   OD ksztaltu grafu.
3. LANCUCH (layering) - sciezka A-B-C-D-E, anomalia to WEDRUJACY, KROTKOTRWALY
   impuls (kazdy wezel trzyma podwyzszona wartosc tylko przez PULSE_LEN krokow,
   potem wraca do normy i przekazuje "dalej") - najbardziej realistyczny wzorzec
   "peel chain": pieniadze przechodza przez posrednika, nie zostaja.
4. MIESZANIE - klaster 5 wezlow (jak pierscien wczesniej), ale SWEEP po liczbie
   slabych polaczen z reszta sieci (0/1/2/4) - sprawdza, czy wieksze
   "wtopienie" w normalna siec maskuje sygnal (rezonans ciagnie stan klastra
   z powrotem w strone normalnego otoczenia).
"""
import numpy as np
from crypto_graph_v2_calibrated import LiveCryptoNode, TIMDRCryptoFieldV2

N = 30
CALIB_STEPS = 200
POST_STEPS = 150


def random_background_edges(node_ids, seed, min_e=2, max_e=4):
    rng = np.random.RandomState(seed)
    edges = []
    for i in node_ids:
        n_e = rng.randint(min_e, max_e + 1)
        targets = rng.choice([x for x in node_ids if x != i], size=min(n_e, len(node_ids) - 1), replace=False)
        for t in targets:
            edges.append((i, int(t), round(float(rng.uniform(0.5, 2.0)), 2)))
    return edges


def simulate(N, edges, baseline_mean, live_override, seed, fast_alpha=0.4, resonance_w=0.05):
    """live_override(node_id, t) -> zywa wartosc w kroku post-kalibracyjnym t,
    albo None zeby uzyc domyslnego szumu wokol baseline_mean."""
    np.random.seed(seed)
    nodes = {i: LiveCryptoNode(i, baseline_state=baseline_mean[i]) for i in range(N)}
    field = TIMDRCryptoFieldV2(nodes, edges, fast_alpha=fast_alpha, resonance_w=resonance_w)

    for _ in range(CALIB_STEPS):
        live = {i: max(0.0, baseline_mean[i] + np.random.normal(0, 0.02)) for i in range(N)}
        field.step_live(live)
    field.calibrate_eq()

    snapshots = []
    for t in range(POST_STEPS):
        live = {}
        for i in range(N):
            v = live_override(i, t)
            if v is None:
                v = baseline_mean[i] + np.random.normal(0, 0.02)
            live[i] = max(0.0, v)
        field.step_live(live)
        snapshots.append({i: field.defect(nodes[i]) for i in range(N)})
    return nodes, snapshots


def best_rank(snapshots, node_id, N):
    """UWAGA - metryka naprawiona po tym, jak pierwsza wersja (szukanie
    PIERWSZEGO kroku z najlepsza ranga) dawala mylace wyniki: mrozila D na
    momencie pierwszego dotarcia do rangi #1, ignorujac czy D dalej rosnie.
    Efekt uboczny: dla trwale podwyzszonego wezla (np. hub) raportowala D z
    wczesnego etapu narastania (male), nie ze szczytu (duze) - a dla wezlow
    BEZ zadnej wstrzykietej anomalii, gdzie ranga #1 krazy losowo miedzy
    wezlami przez caly szumowy przebieg, raportowala fantomowa "ranga #1"
    z przypadkowego momentu, sugerujac wyciek sygnalu tam, gdzie go nie bylo.

    Poprawka: szukamy kroku z MAKSYMALNYM D (szczyt anomalii tego wezla),
    i DOPIERO w tym kroku liczymy range. To odpowiada na pytanie "jak bardzo
    ten wezel wygladal na anomalie w swoim najgorszym momencie", nie "kiedy
    przypadkiem pierwszy raz dotknal topu rankingu"."""
    best_t = max(range(len(snapshots)), key=lambda t: snapshots[t][node_id])
    d = snapshots[best_t][node_id]
    rank = 1 + sum(1 for v in snapshots[best_t].values() if v > d)
    return (rank, best_t, d)


def median_at_peak(snapshots, t):
    return float(np.median(list(snapshots[t].values())))


def ramp(t, inject_at, ramp_len, start, target):
    if t < inject_at:
        return start
    progress = min(1.0, (t - inject_at) / ramp_len)
    return start + progress * (target - start)


def pulse(t, active_at, pulse_len, start, target):
    """Trojkatny impuls: rosnie do target, potem wraca do start, srodek w active_at."""
    half = pulse_len / 2
    dist = abs(t - active_at)
    if dist >= half:
        return start
    frac = 1 - dist / half
    return start + frac * (target - start)


print("=" * 70)
print("SCENARIUSZ 1: GWIAZDA - anomalia w HUBIE")
print("=" * 70)
HUB = 0
LEAVES = list(range(1, 9))
BACKGROUND = list(range(9, N))
np.random.seed(10)
baseline_mean = {i: float(np.random.uniform(0.05, 0.20)) for i in range(N)}
edges = [(HUB, leaf, 1.0) for leaf in LEAVES]
edges += random_background_edges(BACKGROUND, seed=10)
for leaf in LEAVES:  # kazdy lisc ma tez 1 slabe polaczenie z tlem (realizm)
    t = np.random.RandomState(leaf).choice(BACKGROUND)
    edges.append((leaf, int(t), 0.3))

INJECT_AT, RAMP_LEN, TARGET = 30, 40, 0.85


def live_star_hub(i, t):
    if i == HUB:
        return ramp(t, INJECT_AT, RAMP_LEN, baseline_mean[HUB], TARGET)
    return None


nodes, snaps = simulate(N, edges, baseline_mean, live_star_hub, seed=10)
r_hub = best_rank(snaps, HUB, N)
leaf_ranks = [best_rank(snaps, l, N) for l in LEAVES]
print(f"HUB (wezel {HUB}): najlepsza ranga #{r_hub[0]}/{N} (krok {r_hub[1]}, D={r_hub[2]:.4f}, "
      f"mediana sieci w tym kroku={median_at_peak(snaps, r_hub[1]):.4f})")
print(f"Liscie: srednia najlepsza ranga = {np.mean([r[0] for r in leaf_ranks]):.1f}/{N} "
      f"(zakres {min(r[0] for r in leaf_ranks)}-{max(r[0] for r in leaf_ranks)}) "
      f"-- czy wyciekl sygnal z huba przez rezonans?")


print()
print("=" * 70)
print("SCENARIUSZ 2: ROZGALEZIENIE - TA SAMA gwiazda, anomalia w JEDNYM LISCIU")
print("=" * 70)
TARGET_LEAF = LEAVES[0]


def live_star_leaf(i, t):
    if i == TARGET_LEAF:
        return ramp(t, INJECT_AT, RAMP_LEN, baseline_mean[TARGET_LEAF], TARGET)
    return None


nodes2, snaps2 = simulate(N, edges, baseline_mean, live_star_leaf, seed=10)
r_leaf = best_rank(snaps2, TARGET_LEAF, N)
r_hub2 = best_rank(snaps2, HUB, N)
other_leaves = [l for l in LEAVES if l != TARGET_LEAF]
r_other = [best_rank(snaps2, l, N) for l in other_leaves]
print(f"Odchylajacy sie lisc (wezel {TARGET_LEAF}): najlepsza ranga #{r_leaf[0]}/{N} "
      f"(krok {r_leaf[1]}, D={r_leaf[2]:.4f})")
print(f"HUB (widzi tylko 1/8 sasiadow anomalijnych): najlepsza ranga #{r_hub2[0]}/{N} "
      f"(D={r_hub2[2]:.4f}) -- czy rezonans z 1 zlego liscia wsrod 8 wystarcza, zeby wychwycic huba?")
print(f"Pozostale 7 lisci (nie polaczone z odchylajacym sie bezposrednio): "
      f"srednia ranga = {np.mean([r[0] for r in r_other]):.1f}/{N}")


print()
print("=" * 70)
print("SCENARIUSZ 3: LANCUCH (layering) - impuls wedrujacy A-B-C-D-E")
print("=" * 70)
CHAIN = list(range(5))
BACKGROUND3 = list(range(5, N))
np.random.seed(20)
baseline_mean3 = {i: float(np.random.uniform(0.05, 0.20)) for i in range(N)}
edges3 = [(CHAIN[i], CHAIN[i + 1], 1.0) for i in range(len(CHAIN) - 1)]
edges3 += random_background_edges(BACKGROUND3, seed=20)
for c in CHAIN:  # kazdy wezel lancucha tez lekko wtopiony w tlo
    t = np.random.RandomState(c + 100).choice(BACKGROUND3)
    edges3.append((c, int(t), 0.3))

PULSE_LEN_LONG = 30
SHIFT = 20
ACTIVE_AT = {CHAIN[i]: 30 + i * SHIFT for i in range(len(CHAIN))}


def live_chain_long(i, t):
    if i in ACTIVE_AT:
        return pulse(t, ACTIVE_AT[i], PULSE_LEN_LONG, baseline_mean3[i], 0.85)
    return None


nodes3, snaps3 = simulate(N, edges3, baseline_mean3, live_chain_long, seed=20)
print(f"Impuls dlugi ({PULSE_LEN_LONG} krokow, ~{PULSE_LEN_LONG*100/POST_STEPS:.0f}% okna):")
for c in CHAIN:
    r = best_rank(snaps3, c, N)
    print(f"  wezel {c} (aktywny ok. kroku {ACTIVE_AT[c]}): najlepsza ranga #{r[0]}/{N}, "
          f"D={r[2]:.4f} (krok {r[1]}, oczekiwano ok. {ACTIVE_AT[c]})")

PULSE_LEN_SHORT = 6


def live_chain_short(i, t):
    if i in ACTIVE_AT:
        return pulse(t, ACTIVE_AT[i], PULSE_LEN_SHORT, baseline_mean3[i], 0.85)
    return None


nodes3b, snaps3b = simulate(N, edges3, baseline_mean3, live_chain_short, seed=20)
print(f"\nImpuls krotki ({PULSE_LEN_SHORT} krokow, ~{PULSE_LEN_SHORT*100/POST_STEPS:.0f}% okna -- "
      f"czy filtr EMA fast_alpha=0.4 zdazy zareagowac?):")
for c in CHAIN:
    r = best_rank(snaps3b, c, N)
    print(f"  wezel {c} (aktywny ok. kroku {ACTIVE_AT[c]}): najlepsza ranga #{r[0]}/{N}, "
          f"D={r[2]:.4f} (krok {r[1]})")

PULSE_LEN_TINY = 2


def live_chain_tiny(i, t):
    if i in ACTIVE_AT:
        return pulse(t, ACTIVE_AT[i], PULSE_LEN_TINY, baseline_mean3[i], 0.85)
    return None


nodes3c, snaps3c = simulate(N, edges3, baseline_mean3, live_chain_tiny, seed=20)
print(f"\nImpuls EKSTREMALNY ({PULSE_LEN_TINY} kroki, ~{PULSE_LEN_TINY*100/POST_STEPS:.0f}% okna -- "
f"granica testu, jednorazowy 'dotyk' konta):")
for c in CHAIN:
    r = best_rank(snaps3c, c, N)
    print(f"  wezel {c} (aktywny ok. kroku {ACTIVE_AT[c]}): najlepsza ranga #{r[0]}/{N}, "
          f"D={r[2]:.4f} (krok {r[1]})")


print()
print("=" * 70)
print("SCENARIUSZ 4: MIESZANIE - sweep po liczbie polaczen z reszta sieci")
print("=" * 70)
CLUSTER = list(range(5))
BACKGROUND4 = list(range(5, N))

for n_ext in [0, 1, 2, 4, 8, 20]:
    np.random.seed(30)
    baseline_mean4 = {i: float(np.random.uniform(0.05, 0.20)) for i in range(N)}
    edges4 = []
    for i in CLUSTER:
        for j in CLUSTER:
            if i < j:
                edges4.append((i, j, 1.0))
    edges4 += random_background_edges(BACKGROUND4, seed=30)
    rng = np.random.RandomState(30)
    n_ext_eff = min(n_ext, len(BACKGROUND4))
    for i in CLUSTER:
        targets = rng.choice(BACKGROUND4, size=n_ext_eff, replace=False) if n_ext_eff > 0 else []
        for t in targets:
            edges4.append((i, int(t), 1.0))  # taka sama waga jak wewnatrz klastra (20 = niemal pelne wtopienie w 25-wezlowe tlo)

    def live_cluster(i, t, cluster=CLUSTER, baseline_mean4=baseline_mean4):
        if i in cluster:
            return ramp(t, INJECT_AT, RAMP_LEN, baseline_mean4[i], TARGET)
        return None

    nodes4, snaps4 = simulate(N, edges4, baseline_mean4, live_cluster, seed=30)
    ranks = [best_rank(snaps4, c, N) for c in CLUSTER]
    worst = max(r[0] for r in ranks)
    d_vals = [r[2] for r in ranks]
    med = median_at_peak(snaps4, max(r[1] for r in ranks))
    print(f"n_zewnetrznych_polaczen={n_ext_eff}: najgorsza ranga w klastrze #{worst}/{N}, "
          f"D klastra {min(d_vals):.3f}-{max(d_vals):.3f}, mediana sieci~{med:.4f}")
