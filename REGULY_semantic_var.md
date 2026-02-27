# Reguły uzupełniania semantic_var (Semantic Map)

Pole `semantic_var` w słowniku metadanych to ujednolicona nazwa fizyczna (np. `ph_value`, `do_value`), odpowiadająca warstwie Semantic Map w architekturze QB → Semantic Map → Level 2/3.

**Powiązanie:** Reguły mapowania **Level 2 (Matlab) → Level 3 (Python)** (bloki funkcjonalne, zmienne PV/SP/Feedback, wyjątki „ghost”) są opisane w **[REGULY_Mapowanie_L2_L3.md](REGULY_Mapowanie_L2_L3.md)**. Tabela mapowań L2→L3: `output/l2_l3_mapping_rules.csv`; reguły w jednym pliku z mapowaniem Influx: `output/mapping_from_rules.csv` (wiersze z pustym `influx_path`).

## Sposób działania

1. **Źródło główne: level2_name**  
   Ze ścieżki L2 (np. `Output/TransportCiepla_01/i_T_PV`) brany jest **ostatni segment** (`i_T_PV`) i mapowany na `semantic_var` według słownika.

2. **Fallback: tag_name_resolved / tag_description_resolved**  
   Gdy wpis nie ma `level2_name`, można spróbować wyznaczyć `semantic_var` z nazwy tagu lub opisu (np. „pH”, „DO”, „temperature”, „flow”).

3. **Kolejność**  
   Najpierw stosowane są reguły na podstawie `level2_name`; jeśli brak dopasowania, opcjonalnie reguły na podstawie tagu/opisu.

## Propozycja reguł: level2_name (ostatni segment) → semantic_var

| Segment L2 (sygnał) | semantic_var | Opis |
|---------------------|--------------|------|
| `o_pH_mod` | `ph_value` | pH (model/estymacja) |
| `i_acid_flowrate` | `acid_flowrate` | Przepływ kwasu (regulacja pH) |
| `i_base_flowrate` | `base_flowrate` | Przepływ zasady (regulacja pH) |
| `o_DO_mod` | `do_value` | Tlen rozpuszczony (model) |
| `o_DO_mod_CO2` | `do_value_co2` | DO z uwzględnieniem CO2 |
| `o_kLa` | `kla_value` | Współczynnik kLa |
| `i_Qset` | `oxygen_flow_setpoint` | Zadany przepływ O2 |
| `o_Flow_mod` | `gas_flow_value` | Przepływ gazu (model) |
| `i_compress_P`, `i_frac_CO2`, `i_frac_O2` | `gas_pressure`, `frac_co2`, `frac_o2` | Parametry gazu |
| `i_T_PV` | `temperature_process` | Temperatura procesu (PV) |
| `i_T_SP` | `temperature_setpoint` | Zadana temperatura (SP) |
| `i_To` | `temperature_jacket` | Temperatura płaszcza |
| `o_T_mod`, `o_Tj_mod` | `temperature_process_model`, `temperature_jacket_model` | Temperatury z modelu |
| `o_k_est`, `o_k_loss_est` | `heat_transfer_coefficient`, `heat_loss_coefficient` | Współczynniki ciepła |
| `o_Flow_Fbk` | `flow_value` | Przepływ (feedback) |
| `i_Speed_SP`, `o_Speed_Fbk` | `speed_setpoint`, `speed_feedback` | Prędkość obrotowa (zadana / feedback) |
| `o_usedEnergy` | `energy_consumption` | Pobór energii (mieszadło) |
| `o_mix_Level` | `mixing_level` | Poziom mieszania |
| `o_medLevel` | `level_value` | Poziom cieczy |
| `o_medAir`, `o_medCoolant`, `o_medVolume` | `medium_air`, `medium_coolant`, `medium_volume` | Medium w zbiorniku |
| `i_elemDepth`, `i_elemDiameters` | `tank_elem_depth`, `tank_elem_diameters` | Geometria zbiornika |
| `o_A_Total`, `o_r_Bubble_01` | `bubble_area_total`, `bubble_radius` | Pęcherzyki / kLa |
| `o_CO2_mod` | `co2_value` | CO2 (model) |
| `o_kodBledu`, `o_poziom` | `fault_code`, `level_aux` | Błędy / poziom pomocniczy |
| `DWord` | `alarms_status` | Status alarmów |

## Reguły fallback: tag_name_resolved / opis

- `flow` → `flow_value`
- `temperature` → `temperature_value`
- `gasTemp` → `gas_temperature`
- `totalizer` → `totalized_flow`
- `valveDrive` → `valve_opening`
- W opisie: słowa „pH”, „DO/oxygen/tlen”, „temp/temperature”, „flow/przepływ”, „level/poziom” → odpowiednie `*_value`.

## Implementacja i integracja w pipeline

- **Moduł reguł:** `semantic_var_rules.py` (słowniki `LEVEL2_TO_SEMANTIC`, `TAG_TO_SEMANTIC`, wzorce w `TAG_DESCRIPTION_PATTERNS`).
- **`suggest_mapping_llm.py`** – generuje plik **`QB_Level2_Level3_mapping.csv`** (mapowanie z reguł `map_influx_to_l2_l3`) z kolumną **semantic_var** (wartość z `resolve_semantic_var`).
- **`apply_mapping.py`** – odczytuje kolumnę **semantic_var** z CSV (QB_Level2_Level3_mapping przy `--suggested` lub manual_mapping) i zapisuje ją w `metadata_dictionary.json` dla dopasowanych wpisów.
- **Skrypt uzupełniający:** `fill_semantic_var.py` – wczytuje `metadata_dictionary.json`, dla wpisów z pustym `semantic_var` wywołuje `resolve_semantic_var(...)` i uzupełnia pole; zapisuje zaktualizowany słownik. Użyteczny po apply_mapping, gdy w CSV nie było wartości dla części wpisów.

Uruchomienie fill_semantic_var (opcjonalnie):
```bash
python fill_semantic_var.py
```
Opcja `--force` nadpisuje istniejące wartości `semantic_var`.
