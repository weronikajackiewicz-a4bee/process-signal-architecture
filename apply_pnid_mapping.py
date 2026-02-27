"""
Pkt 5: Dopięcie mapowania P&ID (UUID -> pnid_asset_id) do słownika metadanych.
Czyta output/pnid_assets.csv, aktualizuje output/metadata_dictionary.json (pole pnid_asset_id).
Tworzy backup słownika przed zapisem.
Uruchom: python apply_pnid_mapping.py [--dry-run]
"""
import csv
import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sfmf.config import OUTPUT, ensure_output

PNID_CSV = OUTPUT / "pnid_assets.csv"
DICTIONARY_JSON = OUTPUT / "metadata_dictionary.json"
BACKUP_SUFFIX = ".backup_before_pnid"


def load_pnid_mapping(csv_path: Path) -> dict[str, dict]:
    """Wczytuje CSV mapowania. Zwraca dict: device_uuid -> {pnid_asset_id, functional_name_pl, functional_name_en, asset_type}."""
    mapping = {}
    if not csv_path.exists():
        return mapping
    with open(csv_path, encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            uuid_val = (row.get("device_uuid") or "").strip()
            if not uuid_val:
                continue
            pnid = (row.get("pnid_asset_id") or "").strip()
            mapping[uuid_val] = {
                "pnid_asset_id": pnid,
                "functional_name_pl": (row.get("functional_name_pl") or "").strip(),
                "functional_name_en": (row.get("functional_name_en") or "").strip(),
                "asset_type": (row.get("asset_type") or "").strip(),
            }
    return mapping


def apply_mapping_to_dictionary(dictionary: list[dict], mapping: dict[str, dict]) -> list[dict]:
    """Dla każdego wpisu słownika ustawia pnid_asset_id (i opcjonalnie functional_name) z mapowania po device_uuid."""
    for rec in dictionary:
        uuid_val = rec.get("device_uuid") or ""
        if uuid_val in mapping:
            m = mapping[uuid_val]
            rec["pnid_asset_id"] = m.get("pnid_asset_id") or ""
            # Opcjonalnie można dodać pole functional_name do słownika; na razie tylko pnid_asset_id
    return dictionary


def main():
    ensure_output()
    dry_run = "--dry-run" in sys.argv

    if not DICTIONARY_JSON.exists():
        print(f"Brak pliku słownika: {DICTIONARY_JSON}")
        return 1

    if not PNID_CSV.exists():
        print(f"Brak pliku mapowania P&ID: {PNID_CSV}")
        print("Dodaj wiersze z device_uuid i pnid_asset_id (szablon już istnieje).")
        return 1

    mapping = load_pnid_mapping(PNID_CSV)
    if not mapping:
        print("Mapowanie puste (brak wierszy z device_uuid w CSV).")
        return 1

    with open(DICTIONARY_JSON, encoding="utf-8") as f:
        data = json.load(f)

    dictionary = data.get("metadata_dictionary") if isinstance(data, dict) else data
    if not isinstance(dictionary, list):
        print("Nieprawidlowy format slownika (oczekiwano listy lub obiektu z kluczem metadata_dictionary).")
        return 1

    # Backup
    if not dry_run:
        backup_path = OUTPUT / f"metadata_dictionary{BACKUP_SUFFIX}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(backup_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Backup: {backup_path}")

    updated = apply_mapping_to_dictionary(dictionary, mapping)
    filled = sum(1 for r in updated if (r.get("pnid_asset_id") or "").strip())
    print(f"Zaktualizowano pnid_asset_id: {filled} wpisow (na {len(updated)} lacznie).")

    if dry_run:
        print("Dry-run: nie zapisano pliku.")
        return 0

    # Zachowaj pełną strukturę pliku (level2_targets, level3_targets)
    if isinstance(data, dict):
        out = {**data, "metadata_dictionary": updated}
    else:
        out = updated
    with open(DICTIONARY_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"Zapisano: {DICTIONARY_JSON}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
