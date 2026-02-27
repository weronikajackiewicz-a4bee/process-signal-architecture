"""
Krok 3: Pobieranie z InfluxDB wartosci TagName/Actual, TagDescription/Actual, VUnit/Actual
dla sciezek z value_signals. Wymaga konfiguracji polaczenia (env lub .env).
Bez konfiguracji zapisuje puste wartosci (dry-run).
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Ladowanie .env z tego samego folderu co skrypt
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

from sfmf.config import OUTPUT, ensure_output

# Konfiguracja InfluxDB 2.x (zmienne srodowiskowe lub .env)
INFLUX_URL = os.environ.get("INFLUX_URL", "").rstrip("/")
INFLUX_TOKEN = os.environ.get("INFLUX_TOKEN", "")
INFLUX_BUCKET = os.environ.get("INFLUX_BUCKET", "")
INFLUX_ORG = os.environ.get("INFLUX_ORG", "")

# Jak sciezka jest zapisana w Influx: _measurement lub tag "measurement"
INFLUX_MEASUREMENT_FIELD = os.environ.get("INFLUX_MEASUREMENT_FIELD", "_measurement")


def load_value_signals():
    path = OUTPUT / "value_signals_with_meta_sources.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def fetch_last_value_from_influx(measurement_path: str, bucket: str, org: str, url: str, token: str, debug: bool = False, client=None) -> str | None:
    """
    Pobiera ostatnia wartosc dla danej sciezki (measurement) z InfluxDB 2.x.
    Jesli podano client (InfluxDBClient), uzywa go; w przeciwnym razie tworzy wlasne polaczenie.
    """
    try:
        from influxdb_client import InfluxDBClient
    except ImportError:
        return None

    if not url or not token or not bucket:
        return None

    path_escaped = measurement_path.replace('"', '\\"')
    query = f'''
    from(bucket: "{bucket}")
      |> range(start: -365d)
      |> filter(fn: (r) => r["{INFLUX_MEASUREMENT_FIELD}"] == "{path_escaped}")
      |> last()
    '''
    try:
        if client is not None:
            tables = client.query_api().query(query, org=org)
        else:
            with InfluxDBClient(url=url, token=token, org=org, timeout=30_000) as c:
                tables = c.query_api().query(query, org=org)
        for table in tables or []:
            for record in table.records:
                val = record.get_value()
                if val is not None:
                    return str(val).strip()
    except Exception as e:
        if debug:
            print(f"  [blad] {measurement_path[:60]}...: {e}")
    return None


def run_dry():
    """Bez polaczenia: ustawia puste tag_name_resolved, tag_description_resolved, unit."""
    signals = load_value_signals()
    if not signals:
        print("Brak pliku value_signals_with_meta_sources.json. Uruchom najpierw run_step1_2.py")
        return 1

    # Unikalne sciezki do pobrania (zeby nie pytac wielokrotnie o to samo)
    meta_paths = set()
    for s in signals:
        if s.get("tag_name_source"):
            meta_paths.add(("tag_name", s["tag_name_source"]))
        if s.get("tag_description_source"):
            meta_paths.add(("tag_description", s["tag_description_source"]))
        if s.get("vunit_source"):
            meta_paths.add(("vunit", s["vunit_source"]))

    cache = {}  # path -> value (w dry-run puste)
    for kind, path in meta_paths:
        cache[path] = None

    for s in signals:
        s["tag_name_resolved"] = cache.get(s["tag_name_source"]) if s.get("tag_name_source") else None
        s["tag_description_resolved"] = cache.get(s["tag_description_source"]) if s.get("tag_description_source") else None
        s["unit"] = cache.get(s["vunit_source"]) if s.get("vunit_source") else None

    ensure_output()
    out = OUTPUT / "value_signals_with_resolved_meta.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(signals, f, indent=2, ensure_ascii=False)
    print(f"Dry-run: zapisano {out} (puste resolved - skonfiguruj Influx i uruchom z --influx)")
    return 0


def run_with_influx():
    """Z polaczeniem Influx: pobiera ostatnie wartosci i uzupelnia resolved."""
    debug = "--debug" in sys.argv

    if not INFLUX_URL or not INFLUX_TOKEN or not INFLUX_BUCKET or not INFLUX_ORG:
        print("Ustaw INFLUX_URL, INFLUX_TOKEN, INFLUX_BUCKET, INFLUX_ORG (env lub .env)")
        return 1

    print(f"Polaczenie: {INFLUX_URL} bucket={INFLUX_BUCKET} org={INFLUX_ORG}")

    signals = load_value_signals()
    if not signals:
        print("Brak pliku value_signals_with_meta_sources.json. Uruchom run_step1_2.py")
        return 1

    # Unikalne sciezki -> jedna kwerenda na sciezke
    meta_paths = set()
    for s in signals:
        if s.get("tag_name_source"):
            meta_paths.add(s["tag_name_source"])
        if s.get("tag_description_source"):
            meta_paths.add(s["tag_description_source"])
        if s.get("vunit_source"):
            meta_paths.add(s["vunit_source"])

    meta_paths = sorted(meta_paths)
    n = len(meta_paths)
    print(f"Pobieranie {n} unikalnych sciezek (TagName/TagDescription/VUnit) - moze potrwac kilka minut...")

    cache = {}
    try:
        from influxdb_client import InfluxDBClient
        with InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG, timeout=30_000) as client:
            for i, path in enumerate(meta_paths):
                val = fetch_last_value_from_influx(path, INFLUX_BUCKET, INFLUX_ORG, INFLUX_URL, INFLUX_TOKEN, debug=debug, client=client)
                cache[path] = val
                if (i + 1) % 10 == 0 or i == 0:
                    print(f"  {i+1}/{n} sciezek...")
    except Exception as e:
        print(f"Blad polaczenia z Influx: {e}")
        return 1

    for s in signals:
        s["tag_name_resolved"] = cache.get(s.get("tag_name_source") or "")
        s["tag_description_resolved"] = cache.get(s.get("tag_description_source") or "")
        s["unit"] = cache.get(s.get("vunit_source") or "")

    ensure_output()
    out = OUTPUT / "value_signals_with_resolved_meta.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(signals, f, indent=2, ensure_ascii=False)
    filled = sum(1 for v in cache.values() if v is not None and v != "")
    print(f"Zapisano: {out} (pobrano wartosci dla {filled}/{n} sciezek)")
    return 0


def main():
    use_influx = "--influx" in sys.argv or os.environ.get("INFLUX_FETCH") == "1"
    if use_influx:
        return run_with_influx()
    return run_dry()


def test_one_query():
    """Test jednego zapytania - wypisuje surowa odpowiedz Influx (do debugu)."""
    signals = load_value_signals()
    if not signals:
        print("Brak value_signals. Uruchom run_step1_2.py")
        return 1
    # Pierwsza sciezka TagName/Actual
    path = None
    for s in signals:
        if s.get("tag_name_source"):
            path = s["tag_name_source"]
            break
    if not path:
        print("Brak sciezki TagName w signals")
        return 1
    print(f"Test zapytania dla: {path[:80]}...")
    print(f"URL={INFLUX_URL} bucket={INFLUX_BUCKET} org={INFLUX_ORG}")
    try:
        from influxdb_client import InfluxDBClient
        query = f'''
        from(bucket: "{INFLUX_BUCKET}")
          |> range(start: -365d)
          |> filter(fn: (r) => r["_measurement"] == "{path.replace(chr(34), chr(92)+chr(34))}")
          |> last()
        '''
        with InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG, timeout=10_000) as client:
            tables = client.query_api().query(query, org=INFLUX_ORG)
            n = 0
            for table in tables or []:
                for record in table.records:
                    n += 1
                    if n <= 3:
                        print(f"  Rekord: _field={record.get_field()}, _value={record.get_value()}, _time={record.get_time()}")
            print(f"Liczba rekordow: {n}")
            if n == 0:
                print("Brak danych - sprawdz w UI, czy dla tej sciezki (_measurement) sa punkty w bucketcie.")
    except Exception as e:
        print(f"Blad: {e}")
    return 0


if __name__ == "__main__":
    if "--test-one" in sys.argv:
        # Ladowanie .env juz na górze; trzeba miec INFLUX_* ustawione
        sys.exit(test_one_query())
    sys.exit(main())
