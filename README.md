# TIMDR-Crypto-Graph

## Co to jest

Wersja rdzenia TIMDR (helisa + rezonans + defekt, ten sam mechanizm co w
[TIMDR-Quantum-Lattice](../TIMDR-Quantum-Lattice)) przeniesiona z siatki 2D
o stałej strukturze sąsiedztwa na **dowolny ważony graf**: węzły = encje
(np. portfele/adresy), krawędzie = relacje (np. transfery), waga = siła
powiązania. Rezonans przestaje być "sprzężenie z 4 sąsiadami w siatce", a
staje się "sprzężenie z sąsiadami w grafie transakcji".

## Do czego to służy

Pytanie: czy z bieżącego stanu grafu (i jego historii) da się wykryć węzły,
które zachowują się nietypowo — potencjalnie przydatne w kontekście AML
(anti-money-laundering) na grafach transakcji kryptowalutowych, choć **nic
tutaj nie zostało zweryfikowane na realnych, oznaczonych danych AML** —
patrz "Czego to NIE jest" niżej.

## Historia: znaleziony ślepy punkt i zweryfikowana poprawka

**v1** (`crypto_graph_v1_original.py`) miał `eq` (lokalna "norma" węzła)
domyślnie ustawione na własną wartość startową węzła, a `state` ewoluował
wyłącznie autonomicznie (helisa + rezonans + szum) — bez żadnego kanału na
nowe, żywe dane po inicjalizacji.

Konsekwencja, sprawdzona empirycznie (`test_v1_blind_spot.py`): izolowany,
wewnętrznie spójny klaster (5 węzłów, identyczne ryzyko 0.9, połączonych
**tylko między sobą** — dokładnie kształt pierścienia prania pieniędzy,
który transferuje głównie sam ze sobą) jest **całkowicie niewidoczny** dla
`omega_hotspot()`:

| węzeł | ranga (z 30) | D |
|---|---|---|
| 0 | #29 | 0.000005 |
| 1 | #28 | 0.000005 |
| 2 | #27 | 0.000006 |
| 3 | #25 | 0.000012 |
| 4 | #30 | 0.000002 |

mediana D całej sieci: 0.000156 — czyli cały pierścień siedzi **poniżej
mediany**. Im bardziej wewnętrznie spójna i odizolowana grupa, tym mniej
podejrzana dla v1 — dokładnie odwrotność tego, co chciałoby się wykrywać.

**v2** (`crypto_graph_v2_calibrated.py`) naprawia to dwiema zmianami,
zastosowanymi razem (osobno żadna nie wystarcza):

1. `eq[węzeł]` = średnia stanu z **okresu kalibracji** ("kim byłem, zanim
   zaczęło się coś podejrzanego"), nie własna wartość startowa. Ten sam
   wzorzec co kalibracja progu STA/LTA na czysto szumowym oknie w teście
   sejsmicznym w ramach `TIMDR-Quantum-Lattice` — inna domena, ten sam
   pattern.
2. `state(t)` napędzany żywymi danymi z zewnątrz (`step_live()`), nie
   autonomiczną dynamiką. Helisa przestaje ciągnąć stan do `eq` (bo `eq`
   już nie jest "celem" dynamiki) — staje się filtrem EMA wygładzającym
   szum przychodzącej obserwacji.

Test uczciwy (`test_v2_fix_verified.py`, **nie** "na zamówienie"): ten sam
pierścień przez 200 kroków kalibracji zachowuje się statystycznie
identycznie jak reszta sieci — zero wbudowanej różnicy, `eq` liczy się
właśnie z tego okresu. Dopiero po kalibracji pierścień zaczyna dryfować w
górę (0.1→0.85), skorelowanie, nadal połączony tylko między sobą:

| węzeł | ranga (z 30) | D |
|---|---|---|
| 2 | #1 | 0.7386 |
| 0 | #2 | 0.7170 |
| 3 | #3 | 0.7089 |
| 1 | #4 | 0.7028 |
| 4 | #5 | 0.6635 |

mediana D całej sieci: 0.0065 — cały pierścień w top-5 z 30, >100× nad
medianą. Poprawka działa, zweryfikowane na dokładnie tym samym grafie co
błąd, który naprawia.

## Uruchomienie

```
pip install numpy
python3 test_v1_blind_spot.py    # dowod slepego punktu (v1)
python3 test_v2_fix_verified.py  # dowod poprawki (v2), ten sam graf
python3 test_topology_patterns.py  # v2 na 4 wzorcach AML (patrz nizej)
python3 test_eq_definitions.py     # SELF vs PEER_NB vs GLOBAL - "zly od t=0"
python3 test_eq_cohort.py          # + COHORT - peer-group po cechach, nie po grafie
python3 test_kmeans_cohort_risk.py # auto-klastrowanie (k-means) - kiedy zawodzi
```

Wszystkie deterministyczne (ustalone ziarna) — te same liczby za każdym razem.

## v2 na 4 wzorcach AML (`test_topology_patterns.py`)

**Zastrzeżenie znalezione przy budowie tego testu, nie założone z góry:**
graf jest **nieskierowany** (`adj` budowane symetrycznie, niezależnie od
kolejności `(src,dst)` na wejściu). Konsekwencja: "gwiazda" (wielu → jeden,
wzorzec botów/scamów) i "rozgałęzienie" (jeden → wielu, wash trading) są
**topologicznie nieodróżnialne** dla tego modelu — ten sam kształt grafu
(hub + liście), różni je tylko GDZIE pojawia się anomalia, nie struktura
krawędzi. Test sprawdza to wprost, dzieląc je na dwa scenariusze różniące
się miejscem wstrzyknięcia (hub vs pojedynczy liść), nie kształtem grafu.

Metodologia poprawiona w trakcie: pierwsza wersja metryki ("pierwszy krok,
w którym węzeł dotarł do najlepszej rangi") dawała mylące wyniki — mroziła
D na wczesnym etapie narastania dla trwale podwyższonych węzłów, i łapała
fantomową "rangę #1" dla węzłów bez żadnej anomalii (w czysto szumowym
przebiegu ranga #1 krąży losowo między wezłami). Poprawiona na: szukaj
kroku z MAKSYMALNYM D (szczyt anomalii tego węzła), policz rangę tam.

### Gwiazda i rozgałęzienie (hub + 8 liści, embedded w sieci 30 węzłów)

| scenariusz | cel | ranga | D (szczyt) |
|---|---|---|---|
| anomalia w hubie | hub | **#1/30** | 0.61 |
| anomalia w hubie | wszystkie 8 liści | #2/30 (każdy) | leakage przez rezonans |
| anomalia w 1 liściu | ten liść | **#1/30** | 0.71 |
| anomalia w 1 liściu | hub (1/8 sąsiadów anomalijnych) | #2/30 | 0.036 (małe, ale wystarcza) |
| anomalia w 1 liściu | pozostałych 7 liści (bez bezpośredniego połączenia) | #2/30 (każdy) | leakage 2-hopowy: liść→hub→reszta liści |

Rezonans propaguje się przez CAŁĄ gwiazdę, nie tylko do bezpośrednich
sąsiadów — nawet liście niepołączone bezpośrednio z anomalią wychodzą na
rangę #2, bo hub pośredniczy. To ma dwie strony: dobrą (flaguje całe
sąsiedztwo podejrzanego huba, przydatne do śledztwa) i złą (guilt-by-association
— wszyscy połączeni z ryzykownym hubem zaczynają wyglądać podejrzanie,
nawet jeśli sami nic nie zrobili).

### Łańcuch / layering (A-B-C-D-E, impuls wędrujący)

| długość impulsu | % okna | D (szczyt, zakres 5 węzłów) | ranga |
|---|---|---|---|
| 30 kroków | 20% | 0.55–0.66 | #1/30 (wszystkie) |
| 6 kroków | 4% | 0.39–0.47 | #1/30 (wszystkie) |
| 2 kroki (jednorazowy "dotyk") | 1% | 0.27–0.32 | #1/30 (wszystkie) |

Hipoteza przed testem: filtr EMA (`fast_alpha=0.4`) wygładzi krótkotrwały
impuls typu "peel chain" (pieniądze dotykają konta na chwilę i idą dalej)
na tyle, że zniknie. **Niepotwierdzona** — nawet 2-krokowy, jednorazowy
impuls dał rangę #1 na tle sieci o medianie D~0.01. Zastrzeżenie: test użył
DUŻEJ amplitudy (skok do 0.85 z bazowego ~0.1-0.2) — subtelniejsze,
mniejsze odchylenia nie zostały sprawdzone i mogłyby zachowywać się inaczej.

### Mieszanie (klaster 5 węzłów, sweep liczby połączeń z tłem)

| liczba zewn. połączeń | najgorsza ranga w klastrze | D klastra (szczyt) |
|---|---|---|
| 0 (pełna izolacja) | #5/30 | 0.66–0.77 |
| 1 | #5/30 | 0.65–0.75 |
| 2 | #5/30 | 0.63–0.74 |
| 4 | #5/30 | 0.62–0.73 |
| 8 | #5/30 | 0.61–0.71 |
| 20 (niemal pełne wtopienie w 25-węzłowe tło) | #5/30 | 0.60–0.70 |

D klastra spada łagodnie z rosnącą liczbą połączeń (widać efekt "ciągnięcia
w stronę normy przez rezonans"), ale nawet przy 20 zewnętrznych połączeniach
na węzeł (praktycznie pełne wtopienie w tło) klaster wciąż zajmuje top-5 z
30, >60x nad medianą sieci. **Wniosek ogólniejszy**: to, że klaster jest
wciąż wykrywalny niezależnie od tego, jak bardzo jest wtopiony w sieć, nie
jest zasługą struktury grafu — to dlatego, że `defect()` porównuje stan
WYŁĄCZNIE z WŁASNĄ skalibrowaną historią, a rezonans wpływa na `state()`
tylko lekko (`resonance_w=0.05`, świadomie małe, patrz lekcja z
TIMDR-Quantum-Lattice). Prawdziwa podatność v2 nie leży w topologii grafu —
leży w tym, czy własne, żywe dane węzła faktycznie się zmieniają względem
jego kalibrowanej normy. Żadna struktura sąsiedztwa tego nie zamaskuje ani
nie zastąpi.

## Ostatni ślepy punkt: "zły od samego początku" i cztery definicje `eq`

Testy topologii (wyżej) pokazały jedną czystą własność v2: topologia grafu
ani rezonans NIE są źródłem błędów — wszystko zależy od tego, czy własne,
żywe dane węzła odbiegają od jego skalibrowanej normy. Z tego wynika
ostatni, logicznie nieunikniony ślepy punkt: węzeł, który jest "zły" (albo
strukturalnie inny) **już w okresie kalibracji** — bo wtedy `eq` = średnia
jego własnej historii = poziom, na którym już siedział. Cztery definicje
`eq`, przetestowane na dwóch chronicznych scenariuszach + jednym teście
false-positive (`test_eq_definitions.py`, `test_eq_cohort.py`):

| `eq` = | izolowany pierścień, zły od t=0 | pojedynczy zły węzeł, wtopiony normalnie | populacja heterogeniczna (typ B legalnie inny, top-10 na 15/30 wezlow) |
|---|---|---|---|
| **SELF** (własna historia, obecny v2) | #22/30 — niewidoczny | #11/30 — słabo widoczny | 4/10 w top-10 — brak falszywych alarmow |
| **PEER_NB** (średnia BEZPOŚREDNICH SĄSIADÓW w grafie) | **#29/30 — gorzej niż SELF** | #1/30, D=0.68 — działa | 5/10 w top-10 |
| **GLOBAL** (mediana całej populacji) | #5/30, D=0.76-0.79 — działa | #1/30, D=0.68 — działa | **7/10 w top-10 — realne false-positive** |
| **COHORT** (mediana kohorty z cechy NIEZALEŻNEJ od grafu i od "risk") | #1-5/30, D=0.76-0.82 — działa | (nie testowane osobno, mechanizm identyczny do GLOBAL) | 5/10 w top-10 — z powrotem blisko SELF |

**PEER_NB (sąsiedzi w grafie) to pułapka, nie rozwiązanie**: dla
skolegowanego, izolowanego klastra sąsiedzi TO współoskarżeni — ich średnia
odtwarza (a tu nawet pogarsza) dokładnie ten sam błąd co `SELF` w v1.
Peer-group eq działa tylko wtedy, gdy "peer" pochodzi z cechy **niezależnej
od grafu transakcji i niezależnej od samej ocenianej wartości** (w
`test_eq_cohort.py`: `node_id % 6` dla scenariusza pierścienia — rozprasza
5 kolegów do różnych kohort z normalnymi węzłami; prawdziwy typ konta dla
scenariusza heterogenicznego) — dokładnie to, co w realnym AML nazywa się
segmentem/kohortą klienta (KYC), nie "kto z kim transakcjonuje".

**COHORT wygrywa oba testy jednocześnie**: łapie chroniczny izolowany
klaster tak samo dobrze jak GLOBAL (D~0.76-0.82, top-10: 5/5), ale na
populacji heterogenicznej wraca blisko poziomu SELF pod względem
false-positive (5/10 zamiast 7/10 dla GLOBAL, przy bazowym poziomie ~5/10
dla populacji 15/30). To jedyna z czterech definicji, która nie psuje
żadnej z dwóch własności na raz.

**Nierozwiązane, jawnie zostawione na później**: skąd bierze się
`cohort_id` w praktyce. Tu jest symulowany (arbitralna etykieta / prawdziwy
typ konta) — realne wdrożenie wymagałoby cech niezależnych od `risk`
(typ konta/KYC, wiek konta, typowy wolumen przy onboardingu), nie
wyprowadzonych z samego sygnału, który ma być oceniany ani z tego, kto z
kim transakcjonuje.

## Auto-klastrowanie kohort (k-means) i kiedy to zawodzi

`test_eq_cohort.py` zakłada, że `cohort_id` jest **dany z zewnątrz** (KYC,
typ konta) — niezależny od grafu transakcji i od samej ocenianej wartości
`risk`. Ale skąd wziąć `cohort_id`, jeśli takiej etykiety nie ma? Zgodnie z
decyzją "najpierw prosty interfejs, potem klastering jako rozszerzenie",
`crypto_graph_v3_cohort.py` dodaje drugą ścieżkę: `kmeans_cohorts()` —
prosty k-means (bez sklearn) na **cechach statycznych** węzła
(`static_features`, np. wiek konta, typowy wolumen) — świadomie NIE na
`risk`/historii live-data, żeby nie zamknąć koła: klastrować po tym samym
sygnale, który potem ma być oceniany.

Pytanie testowe (`test_kmeans_cohort_risk.py`): co, jeśli kolegujący się
klaster ma też **podobne cechy statyczne** — realny wzorzec koluzji (świeżo
założone konta, 3-15 dni, vs reszta populacji 100-1000 dni; podobny
typowy wolumen)? Czy auto-klastrowanie zamknie ich we WŁASNEJ, czystej
kohorcie i odtworzy pułapkę PEER_NB przez inne drzwi?

**Odpowiedź: tak, i próg jest ostrzejszy niż pierwotnie zakładano.**
Hipoteza robocza w kodzie brzmiała "małe K (duże, zróżnicowane kohorty)
jest bezpieczniejsze". Po przetestowaniu na 3 niezależnych ziarnach
losowości (K = 2, 3, 4, 5, 8, 15 dla każdego) okazało się to niewystarczające:

| ziarno | bezpieczne K (klaster wykryty, D~0.7-0.8, top-10 5/5) | pułapka zaczyna się od K = | czystość kohorty klastra przy pułapce |
|---|---|---|---|
| 2 | K=2 | **3** | 0.62 |
| 5 | K=2, K=3 (częściowo, D=0.33) | **4** | 0.71 |
| 10 | K=2, K=3 | **4** | 0.62 |

Prawdziwym wyznacznikiem okazała się nie wartość K, tylko **czystość
kohorty**, do której trafia klaster (jaki % jej członków to węzły
klastra): gdy klaster stanowi **>50% własnej kohorty**, mediana kohorty
"przeskakuje" na jego własną wartość — `eq ≈ własna historia klastra`,
dokładnie mechanizm PEER_NB, D~0 (ranga #14-#30/30, niewidoczny). Gdy
klaster jest **mniejszością (<50%)** we własnej kohorcie, mediana
kotwiczy się w normalnej większości i klaster wychodzi wyraźnie (D~0.7-0.8,
ranga #1-#5/30). Przy dokładnie 50/50 (ziarno 5, K=3) wynik jest
pośredni (D=0.33, ranga #5-#10) — spójne z tym, że `np.median` przy
parzystej liczbie uśrednia dwie środkowe wartości.

Ten próg pojawił się już przy K=3 lub K=4 w każdym z 3 ziaren — nie
dopiero przy dużym K, jak sugerowałaby pierwotna hipoteza. Powód:
k-means jest algorytmem nienadzorowanym i **naturalnie znajduje dobrze
odseparowany klaster jako osobne skupienie niezależnie od K**, gdy
separacja cech jest duża (tu: rząd wielkości różnicy w wieku konta) — nie
trzeba dużego K, żeby k-means "chciał" wydzielić taką grupę.

**Wniosek praktyczny**: auto-klastrowanie na samych cechach statycznych,
bez dodatkowej kontroli czystości kohort, jest ryzykowne dla realnych
wdrożeń — "małe K" nie daje niezawodnego marginesu bezpieczeństwa, to
twardy próg (przeskok), nie łagodny gradient. Tam gdzie to możliwe,
gotowa etykieta (KYC/segment klienta) pozostaje bezpieczniejszą ścieżką
produkcyjną niż automatyczne wyprowadzanie kohort z cech.

## Pliki

- `crypto_graph_v1_original.py` — pierwsza wersja (`CryptoNode`,
  `TIMDRCryptoField`) — zachowana dla historii/reprodukcji błędu. Jedyna
  zmiana względem oryginalnego paste'a: `math.random()` → `random.random()`
  (`math.random` nie istnieje, to `AttributeError`, kod w oryginalnej
  formie nie uruchomiłby się ani razu).
- `crypto_graph_v2_calibrated.py` — naprawiona wersja (`LiveCryptoNode`,
  `TIMDRCryptoFieldV2`) — `eq` z kalibracji, `state` z żywych danych,
  helisa jako filtr.
- `demo_graph.py` — wspólny generator grafu testowego (30 węzłów, izolowany
  pierścień 5 węzłów) używany przez oba testy, żeby porównanie v1 vs v2
  było na dokładnie tym samym grafie.
- `test_topology_patterns.py` — v2 na 4 wzorcach AML (gwiazda, rozgałęzienie,
  łańcuch/layering, mieszanie) — patrz sekcja wyżej.
- `test_eq_definitions.py` — SELF vs PEER_NB (sąsiedzi w grafie) vs GLOBAL na
  dwóch chronicznych scenariuszach i jednym teście false-positive.
- `test_eq_cohort.py` — czwarta definicja, COHORT (kohorta z cechy
  niezależnej od grafu), na tych samych scenariuszach — patrz sekcja wyżej.
- `crypto_graph_v3_cohort.py` — v2 + `calibrate_eq_cohort()` (kohorta z
  gotowej etykiety) + `kmeans_cohorts()` (kohorta auto-wyprowadzona z cech
  statycznych, numpy-only, bez sklearn).
- `test_kmeans_cohort_risk.py` — stress-test auto-klastrowania: czy k-means
  odtwarza pułapkę PEER_NB, gdy kolegujący się klaster ma też podobne cechy
  statyczne — patrz sekcja wyżej.
- `test_v1_blind_spot.py` / `test_v2_fix_verified.py` — testy opisane wyżej.

## Czego to NIE jest

- **Nie jest zwalidowane na realnych, oznaczonych danych AML.** Cały
  powyższy wynik to jeden syntetyczny scenariusz (jeden kształt klastra,
  jeden poziom dryfu 0.1→0.85, jeden graf). Prawdziwe pranie pieniędzy nie
  zawsze wygląda jak izolowany, w pełni połączony pierścień — subtelniejsze
  wzorce (częściowe powiązania z resztą sieci, wolniejszy dryf, mieszanie
  z legalnym ruchem) nie zostały przetestowane.
- **W v2 `eq` to historyczny baseline WŁASNY węzła, nie baseline grupy
  rówieśniczej** (peer group) — jeśli węzeł jest podejrzany od samego
  początku okresu kalibracji, w v2 nadal będzie niewidoczny. `v3` dodaje
  peer-group `eq` (kohortowy), zweryfikowany jako rozwiązanie tego
  konkretnego problemu — ale **tylko gdy `cohort_id` pochodzi z etykiety
  niezależnej od grafu i od `risk`**; automatyczne wyprowadzanie kohort z
  cech (k-means) ma udokumentowany, przetestowany tryb awarii (patrz sekcja
  "Auto-klastrowanie kohort" wyżej) i nie jest bezpiecznym zamiennikiem
  gotowej etykiety bez dodatkowej kontroli czystości kohort.
- **Brak realnego podłączenia do danych on-chain.** `step_live()` przyjmuje
  gotowy `dict {node_id: wartość}` — kto/jak liczy tę wartość z rzeczywistych
  transakcji blockchain (features, agregacja, częstotliwość próbkowania) nie
  jest tu w ogóle zaadresowane.
- **Progi/parametry (`fast_alpha=0.4`, `resonance_w=0.05`, długość okresu
  kalibracji, poziom "podejrzanego" dryfu) są arbitralne**, dobrane żeby
  test był czytelny, nie skalibrowane na żadnych realnych danych ani
  rozkładzie fałszywych alarmów.
- Rezonans (sprzężenie z sąsiadami) jest tylko modulacją `state()`, **nigdy
  nie wchodzi do `defect`/`omega_hotspot`** — zgodnie z lekcją z
  `TIMDR-Quantum-Lattice`, gdzie rezonans jako składnik Ω szkodził we
  wszystkich dotąd przetestowanych wariantach (dwa razy na abstrakcyjnej
  siatce, raz na symulowanym polu sejsmicznym).

## Powiązane projekty TIMDR

- [TIMDR-Quantum-Lattice](../TIMDR-Quantum-Lattice) — źródło rdzenia
  (helisa/rezonans/defekt), tam na siatce 2D zamiast dowolnego grafu, plus
  test tego samego rdzenia na symulowanym realnym polu sejsmicznym.
