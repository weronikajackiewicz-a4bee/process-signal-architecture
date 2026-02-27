# Plan realizacji: Integracja cyfrowych schematów P&ID z InfluxDB (pkt 5)

**Odniesienie:** [PLAN_Slownik_metadanych_i_integracja_InfluxDB.md](PLAN_Slownik_metadanych_i_integracja_InfluxDB.md) — sekcja 5.

---

## Cel

- Powiązanie **UUID urządzeń** (z QB) z **jednostkami na schemacie P&ID** (Sparger, Mieszadło, Płaszcz grzejny, Pompa kwasu itd.).
- Możliwość filtrowania/agregacji w Influx po „urządzeniu z rysunku”, nie tylko po UUID.
- Jedna spójna struktura: **sygnał ↔ UUID ↔ P&ID ↔ Level 2/3**. Zasady mapowania tagów Level 2 (Matlab) na Level 3 (Python): **[REGULY_Mapowanie_L2_L3.md](REGULY_Mapowanie_L2_L3.md)**.

---

## Stan wyjściowy (już mamy)

- **Słownik metadanych** (`output/metadata_dictionary.json`) — każdy wpis ma pole `pnid_asset_id` (obecnie puste).
- **Lista UUID** — `output/unique_device_uuids.txt` (14 urządzeń).
- **Integracja z InfluxDB** — `influx_fetcher.py` (te same zmienne: `INFLUX_URL`, `INFLUX_TOKEN`, `INFLUX_ORG`, `INFLUX_BUCKET`).

---

## Plan krok po kroku

### Krok 1: Inwentaryzacja UUID (rozpoczęta)

- **Źródło:** `output/unique_device_uuids.txt`.
- **Do zrobienia:** W dokumentacji/konfiguracji ustalić, **co który UUID reprezentuje** (np. który to czujnik tlenu, która pompa). Można to zrobić na podstawie:
  - `mtp_object` w słowniku (Sensor5, CoolingStyle, Pump…) — już mamy;
  - TagName/TagDescription (np. „DO”, „PT100”, „Chiller”) — już w słowniku;
  - Konsultacja z zespołem / lista urządzeń z P&ID.

**Deliverable:** Lista UUID z proponowaną nazwą funkcjonalną (do weryfikacji z rysunkiem).

### Krok 2: Lista zasobów P&ID

- **Źródło:** Schemat P&ID (CAD, PDF) lub ręczna lista elementów.
- **Format:** Dla każdego elementu na rysunku: `pnid_asset_id` (np. z CAD), nazwa funkcjonalna (PL/EN), typ zasobu (Sensor, Pump, Actuator, HeaterJacket, Sparger, Mixer…), opcjonalnie lokalizacja na arkuszu.

**Deliverable:** Plik `output/pnid_assets.csv` (lub `.json`) — szablon wypełniany ręcznie lub eksportem z CAD.

### Krok 3: Mapowanie UUID → P&ID

- **Wejście:** Inwentaryzacja UUID (krok 1) + lista zasobów P&ID (krok 2).
- **Wyjście:** Tabela 1:1: `device_uuid` → `pnid_asset_id`, `functional_name_pl`, `functional_name_en`, `asset_type`.

**Deliverable:** Ten sam plik co w kroku 2, z kolumną `device_uuid` uzupełnioną (np. `output/pnid_assets.csv`).

### Krok 4: Zapis mapowania w warstwie metadanych (InfluxDB)

- **Opcja A (rekomendowana):** Osobny bucket w Influx (np. `metadata` lub `modica_metadata`) z measurement `device_assets`. Każdy punkt = jeden wiersz mapowania (device_uuid, pnid_asset_id, functional_name, asset_type). Umożliwia zapytania typu „daj wszystkie sygnały dla zasobu Sparger”.
- **Opcja B:** Tylko plik/słownik — bez zapisu do Influx; warstwa Data Abstraction Layer łączy przy odczycie słownik JSON z danymi z bucketu QB.

**Deliverable:** Skrypt `pnid_to_influx.py` (lub rozszerzenie istniejącego), który zapisuje `pnid_assets` do Influx; konfiguracja bucketu metadanych (np. w `.env`: `INFLUX_BUCKET_METADATA`).

### Krok 5: Dopięcie pnid_asset_id do słownika metadanych

- **Wejście:** `output/metadata_dictionary.json` + `output/pnid_assets.csv` (lub JSON).
- **Akcja:** Dla każdego wpisu słownika: po `device_uuid` wstawić odpowiadający `pnid_asset_id` (i opcjonalnie `functional_name`) z tabeli mapowania.
- **Wyjście:** Zaktualizowany `metadata_dictionary.json` (backup przed nadpisaniem).

**Deliverable:** Skrypt `apply_pnid_mapping.py` — czyta mapowanie, aktualizuje słownik, zapisuje wynik.

---

## Proponowana kolejność prac

| # | Działanie | Odpowiedzialność / narzędzie |
|---|-----------|------------------------------|
| 1 | Wypełnić szablon `pnid_assets.csv` na podstawie UUID + MTP (mtp_object, tag_description) | Ręcznie / eksport z CAD |
| 2 | Uruchomić `apply_pnid_mapping.py` → aktualizacja słownika | Skrypt (dostarczony) |
| 3 | (Opcjonalnie) Skonfigurować bucket metadanych w Influx i zapisać tam `device_assets` | Skrypt + Influx |
| 4 | Walidacja: w słowniku każdy device_uuid ma pnid_asset_id (lub świadomie pusty) | Przegląd / test |

---

## Struktura pliku mapowania P&ID (pnid_assets)

| Pole | Opis | Przykład |
|------|------|----------|
| device_uuid | UUID z QB (unique_device_uuids.txt) | `0d2fa025-787e-406b-baf3-08e502346a8a` |
| pnid_asset_id | Id z rysunku P&ID / CAD | `SENSOR_TEMP_01`, `SPARGER_01` |
| functional_name_pl | Nazwa funkcjonalna (PL) | Mieszadło 01, Sparger |
| functional_name_en | Nazwa funkcjonalna (EN) | Mixer 01, Sparger |
| asset_type | Sensor, Pump, Actuator, HeaterJacket, Sparger, Mixer, Cooling, … | Sensor |
| location_on_sheet | Opcjonalnie | Arkusz 1, obszar A2 |
| link_to_drawing | Opcjonalnie (ścieżka/URL) | — |

---

## Zależności od innych punktów planu

- **Słownik metadanych (część 1):** Musi być zbudowany (kroki 1–4 planu głównego), żeby mieć `device_uuid` i opcjonalnie `tag_description` do podpowiedzi przy mapowaniu. **Stan:** słownik jest.
- **Data Abstraction Layer (pkt 7):** Będzie korzystać z pól `pnid_asset_id` w słowniku oraz ewentualnie z bucketu metadanych w Influx.

---

## Pliki dostarczone w tym kroku

1. **PLAN_PnID_Integracja_InfluxDB.md** — ten dokument.
2. **output/pnid_assets.csv** — szablon z nagłówkiem i wierszami dla każdego z 14 UUID (pnid_asset_id do uzupełnienia).
3. **apply_pnid_mapping.py** — skrypt: wczytuje `pnid_assets.csv`, aktualizuje `metadata_dictionary.json` (pole `pnid_asset_id`), tworzy backup.
4. **pnid_to_influx.py** (opcjonalnie) — zapis tabeli `device_assets` do bucketu metadanych w InfluxDB.

Po wykonaniu kroków 1–3 będzie można „zacząć działać” z pkt 5: wypełnienie mapowania, uruchomienie skryptu i ewentualnie zapis do Influx.
