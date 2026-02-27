### skil1. Inicjalizacja Mapowania
Cel: Stworzenie pomostu (adaptera) danych pomiędzy fizycznym bioreaktorem a wielopoziomowym modelem Digital Twin (DT).
Wyzwanie: Dane rzeczywiste (QB) używają identyfikatorów UUID oraz struktury MTP (np. Sensor5/VAHEn/VFbk), podczas gdy DT Level 2 używa nazw funkcjonalnych (np. SoftSensorpH_01/o_pH_mod), a Level 3 definiuje moduły procesowe (np. bubblegenerator).
Stan: Posiadamy surowe listy tagów bez zdefiniowanych relacji 1:1.
### 2. Proponowany model: Semantic-Functional Mapping Framework (SFMF)
Proponowane podejście oparte na Hybrydowym Mapowaniu Semantycznym, które łączy analizę tekstową z korelacyjną weryfikacją danych.
Kluczowe kroki modelu:
Ekstrakcja Metadanych (Feature Engineering):
W pliku proces_value_from_qb.csv kluczowe są tagi typu TagName/Actual oraz TagDescription/Actual.

 gdzie każde T jest wektorem cech wyciągniętym ze ścieżki (UUID, SensorID, SubProperty).
Transformacja Semantyczna (Embedding):
Wykorzystanie modelu LLM (np. BERT lub GPT-4o) do zamiany nazw tagów na wektory w przestrzeni biotechnologicznej.
o_pH_mod (Level 2)->  wektor bliski tagowi zawierającemu frazę "pH" lub "SoftSensor" w danych QB.
o_kLa (Level 2) ->  wektor bliski "Oxygen", "Sparger" lub "DO" (Dissolved Oxygen).
Heurystyka Strukturalna (MTP Mapping):
Zastosowanie reguł wynikających ze standardu MTP (Module Type Package).
VFbk -> Value Feedback (Rzeczywisty odczyt).
VOut ->  Value Output (Sygnał sterujący).
VMan ->  Manual Value.
### 3. Walidacja
Zanim model mapowania zostanie wdrożony, zespół  powinien przeprowadzić walidację:
R² Correlation Mapping: Jeśli mamy dane czasowe, wykonujemy korelację wzajemną (Cross-Correlation) sygnałów. Sygnał i_acid_flowrate z symulatora musi wykazywać wysoką korelaryjność z fizyczną pompą kwasu w danych QB.
Metryka:  dla sygnałów sterujących (setpointy) oraz analiza opóźnień (Time Lag Analysis) dla sygnałów procesowych (pH, Temp).
### 4. Integracja z DT (Architektura)
Mapowanie powinno zostać zaimplementowane jako Warstwa Abstrakcji Danych (Data Abstraction Layer) w InfluxDB:
### 5. Next steps
Słownika Metadanych: Musimy wyciągnąć wartości z tagów TagName/Actual dla każdego SensorX. Bez wiedzy, że Sensor5 to np. czujnik tlenu, mapowanie będzie czysto statystyczne i podatne na błędy.
Datasetu Czasowego: Próbki danych z co najmniej jednego pełnego procesu (np. 24h), aby mogli uruchomić algorytmy korelacyjne.
P&ID (Digitized): Jeśli mamy schemat aparatury, możemy przypisać UUID do konkretnych jednostek procesowych (Mieszadło, Sparger, Płaszcz grzejny).


| Poziom | Format Taga | Odpowiedzialność |
|---|---|---|
| Physical (QB) | devices/{UUID}/mtp/objects/{ID}/{Property} | Surowy odczyt z czujnika |
| Semantic Map | dt/physical_entity/{bioreactor_id}/{process_var} | Ujednolicona nazwa (np. ph_value) |
| DT Level 2 | simulation/level2/{module}/{signal} | Model matematyczny uproszczony |
| DT Level 3 | simulation/level3/{component} | Model mechanistyczny / CFD |

### Reguły mapowania L2 → L3
Mapowanie bloków funkcjonalnych (Matlab) na przestrzenie nazw silnika Python (heatmodel, mixer, bubblegenerator, peristalticpump, oxygentransport, softsensorph, tankgeometry), logika zmiennych (PV, SP, Feedback, Estimates) oraz wyjątki (sygnały diagnostyczne, geometria) są opisane w **[REGULY_Mapowanie_L2_L3.md](REGULY_Mapowanie_L2_L3.md)**. Źródło tabel: `buckety.2.0/Mapowanie_Matlab_Python.csv`, `output/l2_l3_mapping_rules.csv`, `output/mapping_from_rules.csv`.
