# Plan: Słownik metadanych + integracja schematów P&ID z InfluxDB

**Źródło koncepcji:** dokument [Mapowania w bucketach](Mapowania%20w%20bucketach.md) — Semantic-Functional Mapping Framework (SFMF).

---

## 1. Kontekst i cel (z „Mapowania w bucketach”)

**Cel inicjalizacji mapowania:** Stworzenie pomostu (adaptera) danych pomiędzy fizycznym bioreaktorem a wielopoziomowym modelem Digital Twin (DT).

**Wyzwanie:** Dane rzeczywiste (QB) używają identyfikatorów UUID oraz struktury MTP (np. `Sensor5/VAHEn/VFbk`), podczas gdy DT Level 2 używa nazw funkcjonalnych (np. `SoftSensorpH_01/o_pH_mod`), a Level 3 definiuje moduły procesowe (np. `bubblegenerator`).

**Stan:** Posiadamy surowe listy tagów bez zdefiniowanych relacji 1:1.

**Podejście:** Hybrydowe Mapowanie Semantyczne — łączenie analizy tekstowej z korelacyjną weryfikacją danych.

---

## 2. Architektura poziomów (format tagów i odpowiedzialność)

Zgodnie z „Mapowania w bucketach” mapowanie realizuje się na czterech poziomach:

| Poziom | Format taga | Odpowiedzialność |
|--------|-------------|------------------|
| **Physical (QB)** | `devices/{UUID}/mtp/objects/{ID}/{Property}` | Surowy odczyt z czujnika |
| **Semantic Map** | `dt/physical_entity/{bioreactor_id}/{process_var}` | Ujednolicona nazwa (np. `ph_value`) |
| **DT Level 2** | `simulation/level2/{module}/{signal}` | Model matematyczny uproszczony |
| **DT Level 3** | `simulation/level3/{component}` | Model mechanistyczny / CFD |

W planie słownika i integracji InfluxDB uwzględniamy wszystkie cztery poziomy; warstwa Semantic Map to pośrednia nazwa ujednolicona, z której korzysta DT.

---

## 3. Stan danych (pliki CSV)

- **proces_value_from_qb.csv** (~2352 wiersze): lista ścieżek pomiarów z fizycznego bioreaktora — poziom **Physical (QB)**. Format: `devices/{UUID}/mtp/objects/{ObiektMTP}/{Właściwość}/Actual` (czasem `Setpoint`). Występują m.in. właściwości: `VFbk`, `VOut`, `VMan`, `TagName`, `TagDescription`, `VUnit`, `V`. Około 328 ścieżek to `TagName/Actual` lub `TagDescription/Actual` — wg dokumentu to one są kluczowe do Ekstrakcji Metadanych.

- **E04_level2_simulation_data.csv** (40 zmiennych): warstwa **DT Level 2** (nazwy funkcjonalne), np. `Output/Bubble_01/o_kLa`, `Output/Mieszanie_01/o_Speed_Fbk`, `Output/TransportO2_01/o_DO_mod`, z konwencją `i_` (input) / `o_` (output) i blokami: Bubble, Mieszanie, Pompa, TransportCiepla, TransportO2, SoftSensorpH, Zbiornik.

- **E04_level3_simulation_data.csv** (39 zmiennych): warstwa **DT Level 3** (moduły procesowe), np. `bubblegenerator/out_bubgen_kla_1s`, `oxygentransport/out_oxygentransport_do_mgl`, z modułami: bubblegenerator, heatmodel, mixer, oxygentransport, peristalticpump, softsensorph, tankgeometry, tcumodel.

---

## 4. CZĘŚĆ 1: Słownik metadanych (SFMF — Ekstrakcja i mapowanie)

### 4.1 Cel słownika

- Jedno miejsce definiujące **co mierzy dany tag** (np. tlen rozpuszczony, pH, przepływ), niezależnie od nazwy w MTP. Bez wiedzy, że np. Sensor5 to czujnik tlenu, mapowanie byłoby czysto statystyczne i podatne na błędy (wg „Mapowania w bucketach”).
- Powiązanie: **Physical (QB)** → **Semantic Map** → **DT Level 2** → **DT Level 3**.
- Wektory cech: każdy tag można opisać wektorem wyciągniętym ze ścieżki (UUID, SensorID, SubProperty) oraz z wartości TagName/Actual i TagDescription/Actual.

### 4.2 Źródła do ekstrakcji (Feature Engineering)

1. **proces_value_from_qb.csv**
   - **Parsowanie ścieżek**: wydobycie z każdego `measurement`: `device_uuid`, `mtp_object` (np. Sensor5, Pump, CoolingStyle), `mtp_property` (np. flow, temperature, VFbk, TagName), `suffix` (Actual / Setpoint).
   - **Grupowanie po „logicznych tagach”**: dla każdego obiektu MTP + property (np. `Pump/flow`) mamy kilka ścieżek (VFbk, VOut, TagName, TagDescription, VUnit…). W słowniku — **jeden wpis na sensowny sygnał** (np. przepływ pompy – odczyt), z listą ścieżek Influx.
   - **TagName / TagDescription (kluczowe wg dokumentu):** wartości nie są w CSV — są w InfluxDB. Dla każdego prefiksu (device + mtp/objects + Object + Property): zarejestrować ścieżki do TagName/Actual i TagDescription/Actual, pobrać wartości z Influx i wpisać do słownika jako `tag_name_resolved`, `tag_description_resolved` — baza do mapowania semantycznego (np. „DO”, „Oxygen” → o_kLa / o_DO_mod).
   - **VUnit**: tam gdzie jest `VUnit/Actual`, przechować jednostkę (z Influx).

2. **Heurystyka strukturalna MTP (z „Mapowania w bucketach”)**
   - **VFbk** → Value Feedback (rzeczywisty odczyt).
   - **VOut** → Value Output (sygnał sterujący).
   - **VMan** → Manual Value.
   Reguły MTP pozwalają automatycznie przypisać typ sygnału (odczyt / sterowanie / manual) bez opierania się wyłącznie na nazwach.

3. **E04_level2 i E04_level3**
   - Lista nazw docelowych DT. Dla każdej zmiennej: nazwa, typ (input/output), blok/moduł, ewentualnie jednostka z nazwy (np. _mgl, _pct).

### 4.3 Transformacja semantyczna (Embedding) — odniesienie do dokumentu

Dokument przewiduje wykorzystanie LLM (np. BERT lub GPT-4o) do zamiany nazw tagów na wektory w przestrzeni biotechnologicznej, np.:

- `o_pH_mod` (Level 2) → wektor bliski tagowi QB zawierającemu „pH” lub „SoftSensor”.
- `o_kLa` (Level 2) → wektor bliski „Oxygen”, „Sparger” lub „DO” (Dissolved Oxygen).

Słownik metadanych (TagName/Actual, TagDescription/Actual) jest wejściem do tej transformacji: bez niego nie da się przypisać semantyki (np. że dany Sensor to czujnik tlenu).

### 4.4 Proponowana struktura słownika (logiczna)

Słownik można trzymać jako tabelę/JSON/plik lub w Influx (measurement „metadata” / osobny bucket). Pola z zachowaniem poziomów z tabeli architektury:

- **Poziom Physical (QB)**
  - `device_uuid`, `mtp_object`, `mtp_property`
  - `influx_measurement_path` (pełna ścieżka w zapytaniach)
  - `signal_type`: VFbk | VOut | VMan | V (wg heurystyki MTP)

- **Poziom Semantic Map**
  - `semantic_var` — ujednolicona nazwa (np. `ph_value`, `do_value`), odpowiadająca `dt/physical_entity/{bioreactor_id}/{process_var}`

- **Semantyka (z Influx)**
  - `tag_name_resolved` (z TagName/Actual), `tag_description_resolved` (z TagDescription/Actual), `unit` (z VUnit/Actual)

- **Mapowanie na DT**
  - `level2_name` (np. `Output/TransportO2_01/o_DO_mod`), `level3_name` (np. `oxygentransport/out_oxygentransport_do_mgl`)
  - `functional_role`: krótki opis (np. „dissolved oxygen”, „kLa”, „pH”)
  - Zasady mapowania L2→L3 (bloki funkcjonalne, zmienne PV/SP/Feedback, wyjątki): **REGULY_Mapowanie_L2_L3.md**; tabele: `output/l2_l3_mapping_rules.csv`, `output/mapping_from_rules.csv`

- **Opcjonalnie**
  - `pnid_asset_id`, `confidence` (ręczne / heurystyka MTP / korelacja R²)

### 4.5 Kroki realizacji słownika

1. **Parser ścieżek**  
   Z `proces_value_from_qb.csv`: rozbić `measurement` na (uuid, object, property, suffix). Dla każdej unikalnej (uuid, object, property) zanotować występujące właściwości MTP (VFbk, VOut, TagName, TagDescription, VUnit itd.).

2. **Sygnały wartościowe + powiązanie z TagName/TagDescription**  
   Zostawić ścieżki niosące wartość procesową (VFbk, VOut, VMan, V). Dla każdej powiązać odpowiadające ścieżki TagName/Actual i TagDescription/Actual (ten sam device + object + property).

3. **Pobranie TagName i TagDescription z InfluxDB**  
   Dla każdej ścieżki TagName/Actual i TagDescription/Actual: zapytanie do Influx (ostatnia wartość lub wybrany przedział). Wpisać wyniki do słownika i powiązać z sygnałem (uuid + object + property + signal_type).

4. **Wypełnienie Semantic Map oraz Level 2 / Level 3**  
   Na podstawie tag_name_resolved, tag_description_resolved i list z E04_level2 / E04_level3: zbudować mapowanie (ręcznie lub z pomocą LLM) — np. „DO”/„Oxygen” → o_DO_mod, out_oxygentransport_do_mgl; uzupełnić `semantic_var`, `level2_name`, `level3_name`, `functional_role`.

5. **Eksport słownika**  
   Zapisać w formacie nadającym się do użycia w Data Abstraction Layer (JSON/YAML/CSV lub zapis do Influx).

---

## 5. CZĘŚĆ 2: Integracja cyfrowych schematów P&ID z InfluxDB

**Odniesienie do „Mapowania w bucketach” (Next steps):** Jeśli mamy schemat aparatury, możemy przypisać UUID do konkretnych jednostek procesowych (Mieszadło, Sparger, Płaszcz grzejny).

### 5.1 Cel

- Powiązanie **UUID urządzeń** z **jednostkami na schemacie P&ID** (Sparger, Mieszadło, Płaszcz grzejny, Pompa kwasu itd.).
- Możliwość filtrowania/agregacji w Influx po „urządzeniu z rysunku”, nie tylko po UUID.

### 5.2 Założenia

- Schemat P&ID: plik (CAD, PDF, obraz) lub struktura danych (lista elementów z ID).
- Baza UUID: z `proces_value_from_qb.csv` (unikalne UUID z prefiksu `devices/`).

### 5.3 Integracja z InfluxDB

Chodzi o przechowanie **mapowania** UUID ↔ identyfikator zasobu P&ID (pnid_asset_id, nazwa funkcjonalna) i ewentualnie atrybutów (typ jednostki, lokalizacja), w formie dostępnej przy zapisie/odczycie (tagi w Influx lub osobny bucket/measurement z metadanymi). Rysunek P&ID jako taki nie jest przechowywany w Influx.

### 5.4 Struktura „schematu cyfrowego”

- **Tabela/słownik pnid_assets** (Influx measurement lub plik/DB):
  - `device_uuid`, `pnid_asset_id` (np. z rysunku), `functional_name_pl` / `functional_name_en` (np. Mieszadło 01, Sparger, Pompa kwasu), `asset_type` (Sensor, Pump, Actuator, HeaterJacket, Sparger), opcjonalnie `location_on_sheet`, `link_to_drawing`.

- W słowniku metadanych (część 1) dla każdego wpisu dodać `pnid_asset_id` (i ewentualnie functional_name) z tej tabeli.

### 5.5 Kroki realizacji P&ID

1. **Inwentaryzacja UUID** — z CSV lista unikalnych UUID; w dokumentacji/konfiguracji ustalić, co który UUID reprezentuje.
2. **Lista zasobów P&ID** — z CAD lub ręcznie: elementy (Sparger, Mieszadło, Pompa_01, Pompa_02…) i ich `pnid_asset_id`.
3. **Mapowanie UUID → P&ID** — tabela/plik: UUID → pnid_asset_id, functional_name, asset_type.
4. **Zapis w warstwie metadanych** — np. osobny bucket w Influx (metadata/pnid) z measurement `device_assets`; lub tagi przy zapisie danych; lub słownik zewnętrzny łączony przy odczycie. Rekomendacja: osobny bucket + spójny słownik z części 1.
5. **Dopięcie pnid_asset_id do słownika metadanych** — jedna struktura: sygnał ↔ UUID ↔ P&ID ↔ Level 2/3.

---

## 6. Walidacja (z „Mapowania w bucketach”)

Zanim model mapowania zostanie wdrożony:

- **R² Correlation Mapping:** przy danych czasowych — korelacja wzajemna (Cross-Correlation) sygnałów. Np. sygnał `i_acid_flowrate` z symulatora musi wykazywać wysoką korelację z fizyczną pompą kwasu w danych QB.
- **Metryki:** R² dla sygnałów sterujących (setpointy) oraz **Time Lag Analysis** dla sygnałów procesowych (pH, Temp).

Wymaga to **datasetu czasowego** z co najmniej jednego pełnego procesu (np. 24h) — zgodnie z Next steps z dokumentu.

---

## 7. Integracja z DT — Data Abstraction Layer (z dokumentu)

Mapowanie ma zostać zaimplementowane jako **Warstwa Abstrakcji Danych (Data Abstraction Layer)** w InfluxDB, łącząca:

- dane Physical (QB) po ścieżkach UUID/MTP,
- ujednolicone nazwy Semantic Map,
- sygnały DT Level 2 i Level 3.

Słownik metadanych i mapowanie P&ID są podstawą tej warstwy.

---

## 8. Podsumowanie kolejności

| Krok | Działanie |
|------|-----------|
| 1 | Parser ścieżek z `proces_value_from_qb.csv` → lista (uuid, mtp_object, mtp_property, signal_type, path) |
| 2 | Wyodrębnienie sygnałów wartościowych (VFbk, VOut, VMan, V) i powiązanie z TagName/TagDescription; zastosowanie heurystyki MTP |
| 3 | Pobranie z InfluxDB wartości TagName/Actual i TagDescription/Actual (oraz ewentualnie VUnit) |
| 4 | Zbudowanie słownika metadanych z poziomami Physical, Semantic Map, Level 2, Level 3 |
| 5 | Mapowanie na Semantic Map i Level 2/3 (ręcznie lub z LLM); uzupełnienie semantic_var, level2_name, level3_name, functional_role |
| 6 | Inwentaryzacja UUID i lista zasobów P&ID → tabela UUID ↔ pnid_asset_id |
| 7 | Zapis mapowania P&ID w Influx (bucket metadanych) i dopięcie pnid_asset_id do słownika |
| 8 | (Później) Walidacja: dataset 24h, R² Correlation Mapping, Time Lag Analysis |

Na tej podstawie można zaprojektować format pliku słownika (np. JSON schema), zapytania Influx do odczytu TagName/TagDescription oraz zapisu metadanych i strukturę Data Abstraction Layer.
