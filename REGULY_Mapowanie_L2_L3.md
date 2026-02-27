# Reguły Mapowania Level 2 (Matlab) → Level 3 (Python)

Dokument definiuje zasady transformacji tagów z warstwy DT Level 2 (Matlab) do przestrzeni nazw silnika Level 3 (Python). Źródło mapowań: **Mapowanie_Matlab_Python.csv** (buckety.2.0) oraz słownik reguł poniżej.

**Dla Cursora:** Podczas mapowania traktuj Level 2 (Matlab) jako źródło danych o aktualnym stanie procesu, a Level 3 (Python) jako warstwę modeli fizycznych. Mapuj tagi po nazwach funkcjonalnych bloków. Jeśli w nazwie L2 występuje `_mod` lub `_est`, szukaj w L3 odpowiednika z prefiksem `heatmodelregressor` lub `softsensor`.

---

## 1. Mapowanie Domena–Model (Block Mapping)

Główną regułą jest przypisanie **prefiksu ścieżki z Matlaba** (blok funkcjonalny) do **konkretnej przestrzeni nazw (namespace)** w silniku Pythona:

| Prefiks Level 2 (Matlab) | Przestrzeń Level 3 (Python) | Opis domeny |
|-------------------------|----------------------------|-------------|
| Output/TransportCiepla_01/ | heatmodel/, tcumodel/ | Termodynamika i chłodzenie |
| Output/Mieszanie_01/ | mixer/ | Hydrodynamika i mieszanie |
| Output/Bubble_01/ | bubblegenerator/ | Dyspersja gazu i pęcherzyki |
| Output/Pompa_01/ lub _02/ | peristalticpump/ | Transfer cieczy (pompy) |
| Output/TransportO2_01/ | oxygentransport/ | Transfer masy tlenu i CO₂ |
| Output/SoftSensorpH_01/ | softsensorph/ | Estymacja parametrów chemicznych |
| Output/Zbiornik_01/ | tankgeometry/ | Geometria i poziomy |

**Uwaga:** Pompa_01 i Pompa_02 mapują się na ten sam model `peristalticpump/` w Level 3.

---

## 2. Logika Transformacji Zmiennych (Variable Matching)

Wewnątrz bloków obowiązują następujące reguły mapowania nazw zmiennych:

### Zmienne procesowe (PV)
- `i_T_PV` (L2) → `out_heatmodel_t_1001` (L3)
- `i_To` (L2) → `out_heatmodel_tj_1001` (L3)

### Wartości zadane (SP)
- `i_Speed_SP` (L2) → `..._rpm_setpoint` (L3)
- `i_T_SP` (L2) → `..._tinternal_1001` (L3)

### Sprzężenia zwrotne (Feedback)
- `o_Speed_Fbk` (L2) → `..._model_angular_velocity_rads` (L3) — **reguła:** zmiana jednostki z RPM na rad/s
- `o_Flow_Fbk` (L2) → `..._speed_rpm` (L3) — **reguła:** model pompy operuje na obrotach

### Współczynniki estymowane (Estimates)
- `o_k_est` (L2) → `..._k_1200` (L3)
- `o_kLa` (L2) → `..._kla_1s` (L3)

---

## 3. Wyjątki (Sygnały „Ghost”)

### Sygnały diagnostyczne
Tagi zawierające **DWord**, **kodBledu** lub **Alarms** w Level 2 **nie mają mapowania** do Level 3. Level 3 to silnik fizyczny i nie przetwarza logiki alarmowej.

### Sygnały geometrii
Parametry statyczne (np. `i_elemDepth`, `i_elemDiameters`) są w Level 3 **stałymi konfiguracyjnymi** modelu `tankgeometry` i nie są mapowane jako zmienne dynamiczne.

---

## 4. Pliki z regułami

- **Tabela mapowań L2→L3 (CSV):** `output/l2_l3_mapping_rules.csv` — kolumny: `level2_tag`, `level3_tag`, `description`.
- **Mapowanie z Influx:** `output/mapping_from_rules.csv` — zawiera zarówno reguły czyste L2→L3 (wiersze z pustym `influx_path`), jak i mapowanie ścieżek Influx → level2_name → level3_name.

---

## 5. Pseudokod Python (referencyjny)

```python
# Słownik reguł mapowania L2 -> L3
L2_TO_L3_RULES = {
    "Output/TransportCiepla_01/i_T_PV": "heatmodel/out_heatmodel_t_1001",
    "Output/TransportCiepla_01/i_To": "heatmodel/out_heatmodel_tj_1001",
    "Output/Mieszanie_01/o_Speed_Fbk": "mixer/out_mixer_model_angular_velocity_rads",
    "Output/Bubble_01/o_kLa": "bubblegenerator/out_bubgen_kla_1s",
    "Output/SoftSensorpH_01/o_pH_mod": "softsensorph/out_softsensorph_ph_est",
    "Output/Zbiornik_01/o_medLevel": "tankgeometry/out_tankgeometry_mediumlevel_1010",
    # ... pełna lista w l2_l3_mapping_rules.csv
}

def get_l3_tag(l2_tag):
    """
    Zwraca tag Level 3 na podstawie tagu Level 2.
    Jeśli tag zawiera 'Pompa_01' lub 'Pompa_02', mapuje obie na ten sam model 'peristalticpump'.
    """
    if "Pompa_" in l2_tag:
        return "peristalticpump/out_peristalticpump_speed_rpm"
    return L2_TO_L3_RULES.get(l2_tag, None)
```

---

## 6. Powiązanie z pipeline

- **map_influx_to_l2_l3.py** — używa słownika urządzeń i reguł L2→L3 do generowania `level2_name` i `level3_name`.
- **suggest_mapping_llm.py** — generuje `QB_Level2_Level3_mapping.csv` z reguł; opisy z `Mapowanie_Matlab_Python.csv` / `l2_l3_mapping_rules.csv`.
- **apply_mapping.py** — zapisuje `level2_name`, `level3_name` do `metadata_dictionary.json`.

Źródło danych wejściowych do tabel mapowań: **buckety.2.0/Mapowanie_Matlab_Python.csv**.
