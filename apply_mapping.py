"""
Krok 5: Aplikacja mapowania na slownik metadanych.
Czyta metadata_dictionary.json oraz QB_Level2_Level3_mapping.csv (--suggested)
lub manual_mapping.csv (path_prefix/tag_name_resolved -> level2, level3, functional_role, semantic_var).
Mapowanie L2/L3 pochodzi z regul (map_influx_to_l2_l3). Zapisuje zaktualizowany metadata_dictionary.json.
"""
import csv
import json
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sfmf.config import OUTPUT, ensure_output

MAPPING_CSV = OUTPUT / "manual_mapping.csv"
QB_LEVEL2_LEVEL3_CSV = OUTPUT / "QB_Level2_Level3_mapping.csv"
DICT_PATH = OUTPUT / "metadata_dictionary.json"


def load_dictionary():
    if not DICT_PATH.exists():
        return None
    with open(DICT_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_mapping_csv(path: Path):
    if not path.exists():
        return []
    rows = []
    with open(path, encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            path_prefix = (row.get("path_prefix") or "").strip()
            tag_name = (row.get("tag_name_resolved") or "").strip()
            level2 = (row.get("level2_name") or row.get("suggested_level2_name") or "").strip()
            level3 = (row.get("level3_name") or row.get("suggested_level3_name") or "").strip()
            role = (row.get("functional_role") or "").strip()
            semantic_var = (row.get("semantic_var") or "").strip()
            if path_prefix or tag_name:
                rows.append({
                    "path_prefix": path_prefix,
                    "tag_name_resolved": tag_name,
                    "level2_name": level2,
                    "level3_name": level3,
                    "functional_role": role,
                    "semantic_var": semantic_var,
                })
    return rows


def apply_mapping(data, mapping_rows):
    """Aktualizuje wpisy slownika na podstawie mapowania (dopasowanie po path_prefix lub tag_name_resolved)."""
    dict_entries = data.get("metadata_dictionary") or []
    by_prefix = {e["path_prefix"]: e for e in dict_entries}
    by_tag_name = defaultdict(list)
    for e in dict_entries:
        tn = (e.get("tag_name_resolved") or "").strip()
        if tn:
            by_tag_name[tn].append(e)

    applied = 0
    for m in mapping_rows:
        level2 = m.get("level2_name") or ""
        level3 = m.get("level3_name") or ""
        role = m.get("functional_role") or ""
        semantic_var = m.get("semantic_var") or ""
        if not level2 and not level3 and not role and not semantic_var:
            continue

        targets = []
        if m["path_prefix"]:
            if m["path_prefix"] in by_prefix:
                targets.append(by_prefix[m["path_prefix"]])
        if m["tag_name_resolved"] and m["tag_name_resolved"] in by_tag_name:
            targets.extend(by_tag_name[m["tag_name_resolved"]])

        for e in targets:
            if level2:
                e["level2_name"] = level2
            if level3:
                e["level3_name"] = level3
            if role:
                e["functional_role"] = role
            if semantic_var:
                e["semantic_var"] = semantic_var
            applied += 1

    return applied


def main():
    ensure_output()
    data = load_dictionary()
    if not data:
        print("Brak metadata_dictionary.json. Uruchom build_dictionary.py")
        return 1

    if "--suggested" in sys.argv and QB_LEVEL2_LEVEL3_CSV.exists():
        mapping_path = QB_LEVEL2_LEVEL3_CSV
    else:
        mapping_path = MAPPING_CSV
    if not mapping_path.exists():
        print(f"Brak pliku {mapping_path}. Uruchom suggest_mapping_llm.py (generuje QB_Level2_Level3_mapping.csv), potem apply_mapping.py --suggested.")
        return 1
    rows = load_mapping_csv(mapping_path)
    if not rows:
        print(f"Brak wierszy w {mapping_path}.")
        return 1

    n = apply_mapping(data, rows)
    with open(DICT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Zastosowano mapowanie do {n} wpisow. Zapisano: {DICT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
