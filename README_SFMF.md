# SFMF – pipeline slownika metadanych i mapowania

Kroki do wykonania po kolei:

## 1. Parser sciezek + sygnaly wartosciowe (krok 1 i 2)

```bash
python run_step1_2.py
```

- Czyta `buckety.2.0/proces_value_from_qb.csv`, parsuje sciezki MTP, wyciaga sygnaly VFbk/VOut/VMan/V z linkami do TagName/TagDescription.
- Zapisuje: `output/value_signals_with_meta_sources.json`, `output/unique_device_uuids.txt`.

## 2. Pobranie TagName/TagDescription z InfluxDB (krok 3)

**Bez konfiguracji (dry-run):**

```bash
python influx_fetcher.py
```

- Zapisuje `output/value_signals_with_resolved_meta.json` z pustymi `tag_name_resolved` / `tag_description_resolved` / `unit`.

**Z InfluxDB:** ustaw zmienne srodowiskowe (lub plik `.env` w tym folderze, jesli uzywasz python-dotenv):

- `INFLUX_URL` – adres InfluxDB 2.x (np. https://localhost:8086)
- `INFLUX_TOKEN` – token API
- `INFLUX_BUCKET` – nazwa bucketa z danymi QB
- `INFLUX_ORG` – organizacja

Nastepnie:

```bash
python influx_fetcher.py --influx
```

Opcjonalnie: `INFLUX_MEASUREMENT_FIELD` – jesli pelna sciezka jest w tagu z inna nazwa (domyslnie `_measurement`).

## 3. Budowanie slownika (krok 4)

```bash
python build_dictionary.py
```

- Czyta `output/value_signals_with_resolved_meta.json`, grupuje po `path_prefix` (jeden wpis na logiczny tag).
- Zapisuje: `output/metadata_dictionary.json` (slownik + listy Level 2/3).

## 4. Mapowanie na Level 2 / Level 3 (krok 5)

**Mapowanie z reguł** (słownik UUID urządzeń, logika VFbk/VOut, sygnały puste – `map_influx_to_l2_l3.py`; reguły L2→L3: **REGULY_Mapowanie_L2_L3.md**, tabele `output/l2_l3_mapping_rules.csv`, `output/mapping_from_rules.csv`):

```bash
python suggest_mapping_llm.py
```

- Zapisuje **`output/QB_Level2_Level3_mapping.csv`** (obowiazujacy plik mapowania do wyslania do zespolu): level2_name, level3_name, semantic_var (z regul), Opis.

**Aplikacja mapowania:**

```bash
# Zastosuj mapowanie z QB_Level2_Level3_mapping.csv
python apply_mapping.py --suggested

# Lub skopiuj QB_Level2_Level3_mapping.csv -> manual_mapping.csv, edytuj i:
python apply_mapping.py
```

- Skrypt dopasowuje wiersze po `path_prefix` lub `tag_name_resolved` i zapisuje zaktualizowany `metadata_dictionary.json` (w tym kolumna **semantic_var** z CSV, jesli obecna).

## 5. Uzupelnienie semantic_var (krok po mapowaniu L2/L3)

Po zastosowaniu mapowania mozesz automatycznie uzupelnic pole **semantic_var** (ujednolicone nazwy typu `ph_value`, `do_value`, `temperature_process`) na podstawie `level2_name` oraz ewentualnie `tag_name_resolved` / opisu:

```bash
python fill_semantic_var.py
```

- Reguly: **REGULY_semantic_var.md** (tabela: sygnal L2 / tag -> semantic_var).
- Opcja `--force` nadpisuje istniejace wartosci semantic_var.

---

## Doprecyzowania, ktorych mozesz potrzebowac

- **Ktory Sensor/obiekt MTP to co:** np. „Sensor5 to czujnik tlenu”, „Pompa UUID xxx to pompa kwasu”. Mozna to wpisac w `manual_mapping.csv` (functional_role) lub w osobnym pliku do uzupelnienia (np. `device_semantics.csv`: uuid, mtp_object, opis).
- **Polaczenie Influx:** dokladna struktura bucketa (czy pelna sciezka jest w `_measurement`, czy w tagu `measurement`) – w razie potrzeby zmien `INFLUX_MEASUREMENT_FIELD`.
- **P&ID:** lista UUID -> jednostka na rysunku (Sparger, Mieszadlo, Plaszcz) – mozna dodac kolumne `pnid_asset_id` w slowniku i uzupelnic w nastepnej iteracji.
