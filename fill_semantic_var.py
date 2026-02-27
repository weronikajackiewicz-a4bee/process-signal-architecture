"""
Krok po mapowaniu L2/L3: automatyczne uzupełnienie semantic_var w słowniku metadanych.
Używa reguł z semantic_var_rules.py (level2_name oraz ewentualnie tag_name_resolved / tag_description_resolved).

Uruchomienie: po apply_mapping.py
  python fill_semantic_var.py

Opcje:
  --force   nadpisz semantic_var także tam, gdzie już jest ustawiony
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sfmf.config import OUTPUT, ensure_output
from semantic_var_rules import resolve_semantic_var

DICT_PATH = OUTPUT / "metadata_dictionary.json"


def main():
    ensure_output()
    force = "--force" in sys.argv

    if not DICT_PATH.exists():
        print("Brak metadata_dictionary.json. Uruchom build_dictionary.py, potem apply_mapping.py (lub suggest + apply).")
        return 1

    with open(DICT_PATH, encoding="utf-8") as f:
        data = json.load(f)

    entries = data.get("metadata_dictionary") or []
    filled = 0
    overwritten = 0

    for e in entries:
        level2 = (e.get("level2_name") or "").strip()
        tag_name = (e.get("tag_name_resolved") or "").strip()
        tag_desc = (e.get("tag_description_resolved") or "").strip()
        current = (e.get("semantic_var") or "").strip()

        suggested = resolve_semantic_var(level2_name=level2, tag_name_resolved=tag_name, tag_description_resolved=tag_desc)
        if not suggested:
            continue

        if current and not force:
            continue
        if current and force:
            overwritten += 1
        else:
            filled += 1
        e["semantic_var"] = suggested

    with open(DICT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"semantic_var: uzupelniono {filled} wpisow" + (f", nadpisano {overwritten} (--force)" if overwritten else ""))
    print(f"Zapisano: {DICT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
