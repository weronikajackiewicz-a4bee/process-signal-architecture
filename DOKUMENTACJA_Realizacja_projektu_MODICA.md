# MODICA – podsumowanie: słownik metadanych i mapowanie QB → Level 2/3

Dokument dla zespołu: **co jest zrobione**, **jak to działa**, **co zostało do zaimplementowania**.  
Szczegóły uruchamiania: **README_SFMF.md**. Koncepcja: **PLAN_Slownik_metadanych_i_integracja_InfluxDB.md**, **Mapowania w bucketach.md**.

---

## 1. Cel i architektura

**Cel:** Pomost między danymi z bioreaktora (QB, ścieżki UUID/MTP) a modelem Digital Twin (Level 2 – Matlab, Level 3 – Python).

| Poziom | W projekcie | Odpowiedzialność |
|--------|-------------|------------------|
| **Physical (QB)** | Ścieżki Influx `devices/{UUID}/mtp/objects/...` | Surowy odczyt |
| **Semantic Map** | Pole `semantic_var` w słowniku (np. `ph_value`, `do_value`) | Ujednolicona nazwa zmiennej |
| **DT Level 2** | Nazwy z E04_level2 (np. `Output/TransportCiepla_01/i_T_PV`) | Model uproszczony |
| **DT Level 3** | Nazwy z E04_level3 (np. `heatmodel/out_heatmodel_t_1001`) | Model mechanistyczny |

**Dane wejściowe:** `proces_value_from_qb.csv`, `E04_level2_simulation_data.csv`, `E04_level3_simulation_data.csv`, `Mapowanie_Matlab_Python.csv` (L2→L3 + opisy). **Mapowanie QB→L2→L3** realizowane jest **z reguł** (skrypt `map_influx_to_l2_l3.py`: słownik UUID urządzeń, logika sufiksów VFbk/VOut, sygnały puste). Zasady mapowania **Level 2 → Level 3** (bloki, zmienne PV/SP/Feedback, wyjątki): **[REGULY_Mapowanie_L2_L3.md](REGULY_Mapowanie_L2_L3.md)**; tabela reguł: `output/l2_l3_mapping_rules.csv`, `output/mapping_from_rules.csv`.

---

## 2. Co zrobiono (pipeline)

### Krok 1–2: Parser i sygnały wartościowe  
**Skrypt:** `run_step1_2.py` + `sfmf/parser.py`  
- Parsowanie ścieżek QB → `uuid`, `mtp_object`, `mtp_property`, `signal_type`, powiązanie z ścieżkami TagName/TagDescription/VUnit.  
- **Wyjście:** `output/value_signals_with_meta_sources.json`, `output/unique_device_uuids.txt`.

### Krok 3: Meta z InfluxDB  
**Skrypt:** `influx_fetcher.py`  
- Pobiera TagName, TagDescription, VUnit z Influx (po ścieżkach z kroku 1–2). Uruchomienie z danymi: `--influx` lub `INFLUX_FETCH=1`; bez tego – dry-run (puste meta).  
- **Wyjście:** `output/value_signals_with_resolved_meta.json`.

### Krok 4: Słownik metadanych  
**Skrypt:** `build_dictionary.py`  
- Grupuje po `path_prefix` (jeden wpis = jeden „logiczny tag”). Zbiera: `influx_paths`, `tag_name_resolved`, `tag_description_resolved`, `unit`; pola `semantic_var`, `level2_name`, `level3_name`, `functional_role` startują puste.  
- **Wyjście:** `output/metadata_dictionary.json`.

### Krok 5: Sugestia mapowania L2/L3 + semantic_var  
**Skrypt:** `suggest_mapping_llm.py`  
- Rozwija słownik do wierszy **(path_prefix, signal_type)** z pełną `influx_path`.  
- **Rola sygnału z ścieżki:** VFbk/Actual→PV, VOut/Actual i VMan/Setpoint→SP, VMan/Actual→Manual.  
- **Mapowanie L2/L3:** wyłącznie **z reguł** (`map_influx_to_l2_l3.map_single_signal(influx_path)`): słownik UUID urządzeń, logika VFbk/VOut/VMan, sygnały puste.  
- **semantic_var:** z reguł (`semantic_var_rules.resolve_semantic_var`) na podstawie level2_name i tag_name/tag_description.  
- **Opis:** uzupełniany z `Mapowanie_Matlab_Python.csv` (L2/L3 → opis).  
- **Wyjście:** `output/QB_Level2_Level3_mapping.csv` (obowiązujący plik mapowania do wysłania do zespołu; kolumny: path_prefix, signal_type, signal_role, influx_path, tag_name_resolved, tag_description_resolved, level2_name, level3_name, functional_role, semantic_var, Opis, alarm_konfig_status, score_l2, score_l3).

### Krok 6: Aplikacja mapowania na słownik  
**Skrypt:** `apply_mapping.py`  
- Czyta słownik oraz CSV mapowania (`QB_Level2_Level3_mapping.csv` przy `--suggested` lub `manual_mapping.csv`). Dopasowanie po `path_prefix` / `tag_name_resolved`.  
- Do słownika wpisywane są: `level2_name`, `level3_name`, `functional_role`, **`semantic_var`** (jeśli kolumna w CSV jest i ma wartość).  
- **Wyjście:** zaktualizowany `output/metadata_dictionary.json`.

### Krok 7 (opcjonalnie): Uzupełnienie semantic_var regułami  
**Skrypt:** `fill_semantic_var.py`  
- Dla wpisów z pustym `semantic_var` uzupełnia wartość z reguł (level2_name, tag, opis).  
- Reguły i tabela mapowań: **REGULY_semantic_var.md**.

---

## 3. Logika kluczowa

- **Źródło prawdy mapowania:** **reguły** w `map_influx_to_l2_l3.py` (słownik UUID urządzeń, logika sufiksów VFbk/VOut, sygnały puste). Reguły mapowania L2→L3 (block mapping, variable matching, wyjątki) — **[REGULY_Mapowanie_L2_L3.md](REGULY_Mapowanie_L2_L3.md)**. Plik `QB_Level2_Level3_mapping.csv` jest generowany przez `suggest_mapping_llm.py` z tych reguł.  
- **Role PV/SP:** wynikają ze ścieżki (VFbk/Actual→PV, VOut/Actual i VMan/Setpoint→SP).  
- **Semantic_var:** generowany w QB_Level2_Level3_mapping (reguły L2/tag), przenoszony do słownika przez apply_mapping; ewentualnie dopełniany przez fill_semantic_var.  
- **Założenia urządzeń** (UUID → Pompa 01/02, Sensor pH/DO/temp itd.) są zdefiniowane w **słowniku urządzeń** w `map_influx_to_l2_l3.py`.

---

## 4. Do zaimplementowania

| Obszar | Stan | Uwagi |
|--------|------|--------|
| **P&ID, UUID↔pnid_asset_id** | Nie zrobione | Pole `pnid_asset_id` w słowniku puste. Brak skryptów inwentaryzacji UUID↔P&ID i zapisu do Influx. |
| **Walidacja R² / Time Lag** | Nie zrobione | Brak skryptów i datasetu czasowego (np. 24h) do korelacji i analizy opóźnień. |
| **Data Abstraction Layer (DAL)** | Nie zrobione | Słownik i CSV są podstawą; warstwa w Influx (zapytania, widoki, API) nie jest zaimplementowana. |
| **Mapowanie „tylko po założeniach”** | Częściowo | Działa filtrowanie po roli PV/SP i odrzucanie sygnałów nieprocesowych. Brak słownika UUID→typ urządzenia i zawężenia L2/L3 do zmiennych powiązanych z tym typem. |

---

## 5. Kolejność uruchamiania

1. `python run_step1_2.py`  
2. `python influx_fetcher.py` (z `--influx` przy dostępie do Influx)  
3. `python build_dictionary.py`  
4. `python suggest_mapping_llm.py` (opcjonalnie `--embeddings`)  
5. `python suggest_mapping_llm.py` (generuje `QB_Level2_Level3_mapping.csv` z reguł) → `python apply_mapping.py --suggested`; ewentualnie edycja i `manual_mapping.csv` + `apply_mapping.py`  
6. Opcjonalnie: `python fill_semantic_var.py`  

Szczegóły i zmienne środowiskowe: **README_SFMF.md**.
