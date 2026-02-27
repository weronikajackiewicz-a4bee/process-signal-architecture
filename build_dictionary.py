"""
Krok 4: Budowanie slownika metadanych (Physical -> Semantic Map -> Level 2 / Level 3).
Czyta value_signals z rozwiazanymi meta (krok 3) oraz listy Level 2 i Level 3.
Zapisuje metadata_dictionary.json oraz szablon mapowania recznego.
"""
import csv
import json
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sfmf.config import OUTPUT, BUCKETY, CSV_LEVEL2, CSV_LEVEL3, ensure_output


def load_value_signals():
    for name in ("value_signals_with_resolved_meta.json", "value_signals_with_meta_sources.json"):
        p = OUTPUT / name
        if p.exists():
            with open(p, encoding="utf-8") as f:
                return json.load(f)
    return None


def load_level2():
    if not CSV_LEVEL2.exists():
        return []
    out = []
    with open(CSV_LEVEL2, encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            m = row.get("measurement", "").strip()
            if m:
                out.append(m)
    return out


def load_level3():
    if not CSV_LEVEL3.exists():
        return []
    out = []
    with open(CSV_LEVEL3, encoding="utf-8") as f:
        for line in f:
            m = line.strip()
            if m and not m.startswith("lp,"):
                out.append(m)
    return out


def build_dictionary(signals):
    """
    Grupuje po path_prefix (jeden wpis na logiczny tag).
    Dla kazdego: zbiera signal_types, sciezki Influx, tag_name_resolved, tag_description_resolved, unit.
    """
    by_prefix = defaultdict(lambda: {
        "device_uuid": None,
        "mtp_object": None,
        "mtp_property": None,
        "path_prefix": None,
        "signal_types": [],
        "influx_paths": {},
        "tag_name_resolved": None,
        "tag_description_resolved": None,
        "unit": None,
        "semantic_var": "",
        "level2_name": "",
        "level3_name": "",
        "functional_role": "",
        "pnid_asset_id": "",
    })

    for s in signals:
        prefix = s["path_prefix"]
        rec = by_prefix[prefix]
        rec["device_uuid"] = s["device_uuid"]
        rec["mtp_object"] = s["mtp_object"]
        rec["mtp_property"] = s["mtp_property"]
        rec["path_prefix"] = prefix
        if s["signal_type"] not in rec["signal_types"]:
            rec["signal_types"].append(s["signal_type"])
        rec["influx_paths"][s["signal_type"]] = s["influx_measurement_path"]
        if s.get("tag_name_resolved") is not None and s["tag_name_resolved"] != "":
            rec["tag_name_resolved"] = s["tag_name_resolved"]
        if s.get("tag_description_resolved") is not None and s["tag_description_resolved"] != "":
            rec["tag_description_resolved"] = s["tag_description_resolved"]
        if s.get("unit") is not None and s["unit"] != "":
            rec["unit"] = s["unit"]

    return list(by_prefix.values())


def main():
    ensure_output()
    signals = load_value_signals()
    if not signals:
        print("Brak pliku value_signals. Uruchom run_step1_2.py i ewentualnie influx_fetcher.py")
        return 1

    dictionary = build_dictionary(signals)
    level2 = load_level2()
    level3 = load_level3()

    out = {
        "metadata_dictionary": dictionary,
        "level2_targets": level2,
        "level3_targets": level3,
    }

    out_path = OUTPUT / "metadata_dictionary.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"Slownik: {len(dictionary)} wpisow (po path_prefix). Zapisano: {out_path}")
    print(f"Level 2: {len(level2)} zmiennych, Level 3: {len(level3)} zmiennych.")
    print("Nastepny krok: python suggest_mapping_llm.py (mapowanie z regul -> QB_Level2_Level3_mapping.csv), potem apply_mapping.py --suggested")

    return 0


if __name__ == "__main__":
    sys.exit(main())
