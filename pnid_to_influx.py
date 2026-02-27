"""
Pkt 5 (krok 4): Zapis mapowania UUID -> P&ID do InfluxDB (bucket metadanych).
Measurement: device_assets. Pola: device_uuid (tag), pnid_asset_id, functional_name_pl, functional_name_en, asset_type.
Wymaga: INFLUX_URL, INFLUX_TOKEN, INFLUX_ORG oraz INFLUX_BUCKET_METADATA (lub INFLUX_BUCKET).
Uruchom: python pnid_to_influx.py
"""
import csv
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

from sfmf.config import OUTPUT, ensure_output

PNID_CSV = OUTPUT / "pnid_assets.csv"
INFLUX_URL = os.environ.get("INFLUX_URL", "").rstrip("/")
INFLUX_TOKEN = os.environ.get("INFLUX_TOKEN", "")
INFLUX_ORG = os.environ.get("INFLUX_ORG", "")
INFLUX_BUCKET_METADATA = os.environ.get("INFLUX_BUCKET_METADATA") or os.environ.get("INFLUX_BUCKET", "")


def load_pnid_rows(csv_path: Path) -> list[dict]:
    if not csv_path.exists():
        return []
    rows = []
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if (row.get("device_uuid") or "").strip():
                rows.append(row)
    return rows


def write_device_assets_to_influx(rows: list[dict], bucket: str, org: str, url: str, token: str) -> bool:
    try:
        from influxdb_client import InfluxDBClient
        from influxdb_client import Point
    except ImportError:
        print("Zainstaluj: pip install influxdb-client")
        return False
    if not url or not token or not bucket:
        print("Ustaw INFLUX_URL, INFLUX_TOKEN i INFLUX_BUCKET_METADATA (lub INFLUX_BUCKET).")
        return False

    now = datetime.now(timezone.utc)
    points = []
    for r in rows:
        uuid_val = (r.get("device_uuid") or "").strip()
        pnid = (r.get("pnid_asset_id") or "").strip()
        name_pl = (r.get("functional_name_pl") or "").strip()
        name_en = (r.get("functional_name_en") or "").strip()
        asset_type = (r.get("asset_type") or "").strip()
        pt = (
            Point("device_assets")
            .tag("device_uuid", uuid_val)
            .field("pnid_asset_id", pnid)
            .field("functional_name_pl", name_pl)
            .field("functional_name_en", name_en)
            .field("asset_type", asset_type)
            .time(now)
        )
        points.append(pt)

    try:
        with InfluxDBClient(url=url, token=token, org=org, timeout=10_000) as client:
            with client.write_api() as write_api:
                write_api.write(bucket=bucket, org=org, record=points)
        print(f"Zapisano {len(points)} punktów do bucket={bucket}, measurement=device_assets")
        return True
    except Exception as e:
        print(f"Błąd zapisu do Influx: {e}")
        return False


def main():
    ensure_output()
    rows = load_pnid_rows(PNID_CSV)
    if not rows:
        print(f"Brak danych w {PNID_CSV}")
        return 1
    if not INFLUX_BUCKET_METADATA:
        print("Ustaw INFLUX_BUCKET_METADATA lub INFLUX_BUCKET w .env")
        return 1
    ok = write_device_assets_to_influx(
        rows, INFLUX_BUCKET_METADATA, INFLUX_ORG, INFLUX_URL, INFLUX_TOKEN
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
