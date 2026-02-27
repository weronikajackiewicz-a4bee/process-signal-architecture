"""
Parser ścieżek QB (proces_value_from_qb.csv) oraz wyodrębnienie sygnałów wartościowych
z powiązaniem do TagName/Actual i TagDescription/Actual.
Krok 1 i 2 planu SFMF.
"""
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

# devices/{uuid}/mtp/objects/{mtp_object}/{mtp_property}/{signal_type}/{suffix}
# np. devices/0d2fa025-.../mtp/objects/Sensor5/VAHEn/VFbk/Actual
RE_DEVICES = re.compile(
    r"^devices/([0-9a-f-]{36})/mtp/objects/([^/]+)/([^/]+)/([^/]+)/(Actual|Setpoint)$",
    re.I
)
# alternatywa: bez /Actual lub /Setpoint na końcu (np. metadata)
RE_DEVICES_ALT = re.compile(
    r"^devices/([0-9a-f-]{36})/mtp/objects/([^/]+)/([^/]+)/([^/]+)$",
    re.I
)


@dataclass
class ParsedPath:
    """Jedna rozparsowana ścieżka pomiaru."""
    uuid: str
    mtp_object: str
    mtp_property: str
    signal_type: str
    suffix: str  # Actual | Setpoint | ""
    measurement: str

    @property
    def prefix(self) -> str:
        """Prefix ścieżki do tego samego 'logicznego tagu' (uuid/object/property)."""
        return f"devices/{self.uuid}/mtp/objects/{self.mtp_object}/{self.mtp_property}"

    def is_value_signal(self, value_types: set) -> bool:
        return self.signal_type in value_types

    def is_meta_signal(self, meta_types: set) -> bool:
        return self.signal_type in meta_types


def parse_measurement(measurement: str) -> Optional[ParsedPath]:
    """
    Rozbija ścieżkę measurement na składniki.
    Zwraca None jeśli ścieżka nie jest w formacie devices/{uuid}/mtp/objects/...
    """
    m = RE_DEVICES.match(measurement.strip())
    if m:
        uuid, mtp_object, mtp_property, signal_type, suffix = m.groups()
        return ParsedPath(
            uuid=uuid,
            mtp_object=mtp_object,
            mtp_property=mtp_property,
            signal_type=signal_type,
            suffix=suffix,
            measurement=measurement,
        )
    m = RE_DEVICES_ALT.match(measurement.strip())
    if m:
        uuid, mtp_object, mtp_property, signal_type = m.groups()
        return ParsedPath(
            uuid=uuid,
            mtp_object=mtp_object,
            mtp_property=mtp_property,
            signal_type=signal_type,
            suffix="",
            measurement=measurement,
        )
    return None


def load_and_parse(csv_path: Path, value_types: set, meta_types: set):
    """
    Wczytuje CSV, parsuje każdy measurement, zwraca:
    - parsed_rows: lista ParsedPath (tylko te z mtp/objects)
    - by_prefix: dict prefix -> listę ParsedPath (dla grupowania)
    - value_signals: lista dict z sygnałami wartościowymi i linkami do TagName/TagDescription
    """
    import csv
    parsed_rows: list[ParsedPath] = []
    by_prefix: dict[str, list[ParsedPath]] = {}

    with open(csv_path, encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            meas = row.get("measurement", "").strip()
            if not meas:
                continue
            p = parse_measurement(meas)
            if p is None:
                continue
            parsed_rows.append(p)
            key = p.prefix
            if key not in by_prefix:
                by_prefix[key] = []
            by_prefix[key].append(p)

    # Sygnały wartościowe: tylko te prefiksy, gdzie jest VFbk/VOut/VMan/V
    value_signals = []
    for prefix, paths in by_prefix.items():
        value_paths = [x for x in paths if x.is_value_signal(value_types)]
        if not value_paths:
            continue
        tag_name_path = next((x.measurement for x in paths if x.signal_type == "TagName" and x.suffix == "Actual"), None)
        tag_desc_path = next((x.measurement for x in paths if x.signal_type == "TagDescription" and x.suffix == "Actual"), None)
        vunit_path = next((x.measurement for x in paths if x.signal_type == "VUnit" and x.suffix == "Actual"), None)
        first = paths[0]
        for vp in value_paths:
            value_signals.append({
                "device_uuid": first.uuid,
                "mtp_object": first.mtp_object,
                "mtp_property": first.mtp_property,
                "signal_type": vp.signal_type,
                "suffix": vp.suffix,
                "influx_measurement_path": vp.measurement,
                "path_prefix": prefix,
                "tag_name_source": tag_name_path,
                "tag_description_source": tag_desc_path,
                "vunit_source": vunit_path,
            })

    return {
        "parsed_rows": parsed_rows,
        "by_prefix": by_prefix,
        "value_signals": value_signals,
        "unique_devices": list({p.uuid for p in parsed_rows}),
    }


if __name__ == "__main__":
    from sfmf.config import CSV_PROCES_VALUE, VALUE_SIGNAL_TYPES, META_SIGNAL_TYPES, ensure_output, OUTPUT

    ensure_output()
    data = load_and_parse(CSV_PROCES_VALUE, VALUE_SIGNAL_TYPES, META_SIGNAL_TYPES)

    print(f"Rozparsowane wiersze (mtp/objects): {len(data['parsed_rows'])}")
    print(f"Unikalne urządzenia (UUID): {len(data['unique_devices'])}")
    print(f"Sygnały wartościowe (VFbk/VOut/VMan/V): {len(data['value_signals'])}")

    # Zapis do JSON
    import json
    out_parsed = OUTPUT / "parsed_paths.json"
    # ParsedPath nie jest JSON-serializable jako obiekt, więc zapisujemy value_signals i podsumowanie
    to_save = {
        "unique_devices": data["unique_devices"],
        "total_parsed_paths": len(data["parsed_rows"]),
        "value_signals": data["value_signals"],
    }
    with open(out_parsed, "w", encoding="utf-8") as f:
        json.dump(to_save, f, indent=2, ensure_ascii=False)
    print(f"Zapisano: {out_parsed}")
