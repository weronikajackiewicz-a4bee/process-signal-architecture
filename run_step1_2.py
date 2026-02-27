"""
Krok 1 i 2: Parser ścieżek QB + wyodrębnienie sygnałów wartościowych z linkami do TagName/TagDescription.
Uruchom z folderu Mapowanie zmiennych: python run_step1_2.py
"""
import json
import sys
from pathlib import Path

# Uruchomienie z katalogu Mapowanie zmiennych
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sfmf.config import CSV_PROCES_VALUE, VALUE_SIGNAL_TYPES, META_SIGNAL_TYPES, ensure_output, OUTPUT
from sfmf.parser import load_and_parse

def main():
    ensure_output()
    if not CSV_PROCES_VALUE.exists():
        print(f"Brak pliku: {CSV_PROCES_VALUE}")
        return 1

    data = load_and_parse(CSV_PROCES_VALUE, VALUE_SIGNAL_TYPES, META_SIGNAL_TYPES)

    print("--- Wynik krokow 1 i 2 ---")
    print(f"Rozparsowane sciezki (mtp/objects): {len(data['parsed_rows'])}")
    print(f"Unikalne urzadzenia (UUID): {len(data['unique_devices'])}")
    print(f"Sygnaly wartosciowe (VFbk/VOut/VMan/V): {len(data['value_signals'])}")

    # Zapis pełnej listy value_signals do JSON (do użycia w kroku 3 i 4)
    out_signals = OUTPUT / "value_signals_with_meta_sources.json"
    with open(out_signals, "w", encoding="utf-8") as f:
        json.dump(data["value_signals"], f, indent=2, ensure_ascii=False)
    print(f"Zapisano: {out_signals}")

    # Zapis listy unikalnych UUID (do P&ID / inwentaryzacji)
    out_uuids = OUTPUT / "unique_device_uuids.txt"
    with open(out_uuids, "w", encoding="utf-8") as f:
        for u in sorted(data["unique_devices"]):
            f.write(u + "\n")
    print(f"Zapisano: {out_uuids}")

    # Krótki podgląd: pierwsze 3 sygnały z linkami do TagName/TagDescription
    print("\nPrzyklad sygnalow (pierwsze 3 z TagName):")
    with_tag = [s for s in data["value_signals"] if s.get("tag_name_source")][:3]
    for s in with_tag:
        print(f"  {s['mtp_object']}/{s['mtp_property']} ({s['signal_type']}) -> TagName: {s['tag_name_source'] is not None}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
