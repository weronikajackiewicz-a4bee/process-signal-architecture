# Ścieżki do danych (SFMF - Semantic-Functional Mapping Framework)
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUCKETY = ROOT / "buckety.2.0"
OUTPUT = ROOT / "output"

CSV_PROCES_VALUE = BUCKETY / "proces_value_from_qb.csv"
CSV_LEVEL2 = BUCKETY / "E04_level2_simulation_data.csv"
CSV_LEVEL3 = BUCKETY / "E04_level3_simulation_data.csv"

# Sygnały niosące wartość procesową (heurystyka MTP)
VALUE_SIGNAL_TYPES = {"VFbk", "VOut", "VMan", "V"}

# Metadane do pobrania z Influx (ścieżki w QB)
META_SIGNAL_TYPES = {"TagName", "TagDescription", "VUnit"}

def ensure_output():
    OUTPUT.mkdir(parents=True, exist_ok=True)
