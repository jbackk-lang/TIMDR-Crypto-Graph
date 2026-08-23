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
```

Oba deterministyczne (ustalone ziarna) — te same liczby za każdym razem.

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
- `test_v1_blind_spot.py` / `test_v2_fix_verified.py` — testy opisane wyżej.

## Czego to NIE jest

- **Nie jest zwalidowane na realnych, oznaczonych danych AML.** Cały
  powyższy wynik to jeden syntetyczny scenariusz (jeden kształt klastra,
  jeden poziom dryfu 0.1→0.85, jeden graf). Prawdziwe pranie pieniędzy nie
  zawsze wygląda jak izolowany, w pełni połączony pierścień — subtelniejsze
  wzorce (częściowe powiązania z resztą sieci, wolniejszy dryf, mieszanie
  z legalnym ruchem) nie zostały przetestowane.
- **`eq` to historyczny baseline WŁASNY węzła, nie baseline grupy
  rówieśniczej** (peer group). Jeśli węzeł jest podejrzany od samego
  początku okresu kalibracji, nadal będzie niewidoczny — to następny,
  nierozwiązany tu wariant tego samego problemu (peer-group `eq` zamiast
  czysto historycznego to zapowiedziany, ale nie zaimplementowany kolejny
  krok).
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
