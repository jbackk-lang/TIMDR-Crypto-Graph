"""
crypto_graph_v3_cohort.py -- v2 (crypto_graph_v2_calibrated.py) + kohortowe
`eq`, zweryfikowane w test_eq_definitions.py/test_eq_cohort.py jako jedyna z
czterech testowanych definicji, ktora nie psuje ani wykrywalnosci
chronicznego, izolowanego klastra, ani nie podnosi falszywych alarmow na
legalnie odmiennej populacji.

Interfejs w DWA POZIOMY, zgodnie z decyzja "najpierw prosty interfejs, potem
klastering jako rozszerzenie":

1. `calibrate_eq_cohort(field, cohort_of)` -- przyjmuje GOTOWA etykiete
   kohorty per wezel (np. z KYC/typu konta), niezalezna od grafu i od
   samego `risk`. To jest droga produkcyjna, gdy etykieta jest dostepna.

2. `kmeans_cohorts(nodes, feature_keys, k, seed)` -- gdy nie ma gotowej
   etykiety, wyprowadza kohorty automatycznie z prostego k-means na
   CECHACH STATYCZNYCH (np. wiek konta, typowy wolumen) zapisanych w
   `node.static_features` -- NIE z `risk`/`state`/historii live-data.
   Uzycie: `cohort_of = kmeans_cohorts(nodes, ["account_age","typical_volume"], k=5)`,
   potem `calibrate_eq_cohort(field, cohort_of)`.

KRYTYCZNE ZALOZENIE, ZWERYFIKOWANE i SPRECYZOWANE w test_kmeans_cohort_risk.py:
jesli kolegujacy sie klaster ma tez podobne cechy statyczne (realny wzorzec -
swiezo zalozone konta o podobnym wolumenie), auto-klastrowanie MOZE odtworzyc
pulapke PEER_NB przez inne drzwi. Pierwotna hipoteza ("male K jest
bezpieczniejsze") okazala sie NIEPRECYZYJNA - male K samo w sobie NIE daje
bezpiecznego marginesu:

  - w 3 niezaleznych powtorzeniach (rozne ziarna losowosci) pulapka
    ujawnia sie juz przy K=3 albo K=4 - nie dopiero przy duzym K.
  - PRAWDZIWYM wyznacznikiem nie jest K, tylko CZYSTOSC kohorty, do ktorej
    trafia klaster: gdy klaster stanowi >50% wlasnej kohorty, mediana
    kohorty "przeskakuje" na wartosc klastra i eq ~ wlasna historia klastra
    (D~0, ranga #14-#30/30 - niewidoczny). Gdy klaster jest MNIEJSZOSCIA
    (<50%) we wlasnej kohorcie, mediana kotwiczy sie w normalnej wiekszosci
    i klaster wychodzi wyraznie (D~0.7-0.8, ranga #1-#5/30).
  - ten prog (50% czystosci) potrafi wystapic przy MALYM K (np. K=2 bylo
    bezpieczne we wszystkich 3 ziarnach, ale K=3 lub K=4 - juz nie), wiec
    "male K" NIE jest niezawodnym zabezpieczeniem - to twardy prog, nie
    lagodny gradient.

Praktyczny wniosek: auto-klastrowanie na samych cechach statycznych bez
dodatkowej kontroli czystosci kohort jest RYZYKOWNE dla realnych wdrozen.
Jesli uzywane, wymaga monitorowania czystosci kohort (patrz
`kmeans_cohorts` + rozne K) i/lub wybierania gotowej etykiety (KYC) nad
automatycznym klastrowaniem, gdziekolwiek to mozliwe - to jest sciezka
produkcyjna domyslna (`calibrate_eq_cohort` z zewnetrznym `cohort_of`).
"""
import numpy as np
from crypto_graph_v2_calibrated import LiveCryptoNode, TIMDRCryptoFieldV2


class CohortCryptoNode(LiveCryptoNode):
    def __init__(self, node_id, baseline_state=0.0, static_features=None):
        super().__init__(node_id, baseline_state=baseline_state)
        self.static_features = static_features or {}


def calibrate_eq_cohort(field, cohort_of):
    """cohort_of: dict {node_id: cohort_label} - dowolny hashowalny label,
    z zewnatrz (KYC) albo z kmeans_cohorts(). Nadpisuje calibrate_eq()
    z TIMDRCryptoFieldV2 (nie modyfikuje go - to osobna funkcja)."""
    hist_mean = {nid: float(np.mean(node.history)) for nid, node in field.nodes.items()}
    cohorts = {}
    for nid, c in cohort_of.items():
        cohorts.setdefault(c, []).append(nid)
    cohort_median = {c: float(np.median([hist_mean[n] for n in members])) for c, members in cohorts.items()}
    for nid, node in field.nodes.items():
        node.eq = cohort_median[cohort_of[nid]]


def kmeans_cohorts(nodes, feature_keys, k, seed=0, n_iter=50):
    """Prosty k-means (bez sklearn) na node.static_features[feature_keys].
    Cechy z-normalizowane przed klastrowaniem (rozne skale). Zwraca
    dict {node_id: cluster_index}."""
    ids = list(nodes.keys())
    X = np.array([[nodes[i].static_features[fk] for fk in feature_keys] for i in ids], dtype=float)
    mu, sigma = X.mean(axis=0), X.std(axis=0)
    sigma[sigma < 1e-9] = 1.0
    Xn = (X - mu) / sigma

    rng = np.random.RandomState(seed)
    centers = Xn[rng.choice(len(ids), size=k, replace=False)]
    assign = np.zeros(len(ids), dtype=int)
    for _ in range(n_iter):
        dists = ((Xn[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
        new_assign = dists.argmin(axis=1)
        if np.array_equal(new_assign, assign):
            break
        assign = new_assign
        for c in range(k):
            members = Xn[assign == c]
            if len(members) > 0:
                centers[c] = members.mean(axis=0)
    return {ids[i]: int(assign[i]) for i in range(len(ids))}
