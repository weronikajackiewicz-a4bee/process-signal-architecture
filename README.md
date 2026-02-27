# Process Signal Architecture (MODICA – Mapowanie zmiennych)

Pomost między danymi z bioreaktora (QB, ścieżki UUID/MTP) a modelem Digital Twin: **Level 2** (Matlab) i **Level 3** (Python). Pipeline buduje słownik metadanych i mapowanie sygnałów QB → L2 → L3 z reguł i opcjonalnie sugestii LLM.

---

## Szybki start

1. **Środowisko:** Python 3.x, zależności z `requirements.txt` (jeśli jest) lub `pip install` według importów w skryptach.
2. **Kolejność uruchamiania** (szczegóły w [README_SFMF.md](README_SFMF.md)):

   ```bash
   python run_step1_2.py
   python influx_fetcher.py          # opcjonalnie: --influx przy dostępie do InfluxDB
   python build_dictionary.py
   python suggest_mapping_llm.py     # generuje QB_Level2_Level3_mapping.csv
   python apply_mapping.py --suggested
   python fill_semantic_var.py      # opcjonalnie – uzupełnienie semantic_var
   ```

3. **Wyjście:** `output/metadata_dictionary.json`, `output/QB_Level2_Level3_mapping.csv` – główne artefakty do dalszej integracji.

---

## Dokumentacja w repo

| Plik | Opis |
|------|------|
| [DOKUMENTACJA_Realizacja_projektu_MODICA.md](DOKUMENTACJA_Realizacja_projektu_MODICA.md) | Podsumowanie: co zrobiono, pipeline, do zaimplementowania |
| [README_SFMF.md](README_SFMF.md) | Kroki uruchomienia, zmienne środowiskowe (InfluxDB) |
| [PLAN_Slownik_metadanych_i_integracja_InfluxDB.md](PLAN_Slownik_metadanych_i_integracja_InfluxDB.md) | Koncepcja słownika i integracji z InfluxDB |
| [PLAN_PnID_Integracja_InfluxDB.md](PLAN_PnID_Integracja_InfluxDB.md) | Plan integracji P&ID z InfluxDB |
| [Mapowania w bucketach.md](Mapowania%20w%20bucketach.md) | Semantic-Functional Mapping Framework (SFMF) |
| [REGULY_Mapowanie_L2_L3.md](REGULY_Mapowanie_L2_L3.md) | Reguły mapowania Level 2 → Level 3 |
| [REGULY_semantic_var.md](REGULY_semantic_var.md) | Reguły uzupełniania `semantic_var` |

---

## Struktura

- **`buckety.2.0/`** – dane wejściowe: `proces_value_from_qb.csv`, listy L2/L3, mapowanie Matlab↔Python.
- **`output/`** – słownik, CSV mapowania, listy UUID (wyniki pipeline’u).
- **`sfmf/`** – parser ścieżek MTP i konfiguracja.
- Skrypty główne: `run_step1_2.py`, `influx_fetcher.py`, `build_dictionary.py`, `suggest_mapping_llm.py`, `apply_mapping.py`, `map_influx_to_l2_l3.py`, `fill_semantic_var.py`.

---

## Licencja / kontakt

Projekt wewnętrzny (4BEE / MODICA). Pytania – kontakt z właścicielem repozytorium.
