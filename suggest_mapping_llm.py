"""
Sugerowane mapowanie QB -> Level 2 / Level 3 z uzyciem embeddingow (BERT / sentence-transformers).
Dla kazdego wpisu QB (tag_name_resolved, tag_description_resolved) znajduje najbardziej
podobne zmienne Level 2 i Level 3 w przestrzeni wektorowej (np. o_pH_mod <-> tag z "pH", "SoftSensor").
Wymaga: pip install sentence-transformers
"""
import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sfmf.config import OUTPUT, BUCKETY, ensure_output
from semantic_var_rules import resolve_semantic_var
from map_influx_to_l2_l3 import map_single_signal

DICT_PATH = OUTPUT / "metadata_dictionary.json"
# Obowiazujacy plik mapowania QB -> Level 2 -> Level 3 (generowany z regul)
QB_LEVEL2_LEVEL3_CSV = OUTPUT / "QB_Level2_Level3_mapping.csv"
# Mapowanie Level 2 (Matlab) -> Level 3 (Python) + opisy (do uzupelnienia Opis)
REFERENCE_L2_L3_CSV = BUCKETY / "Mapowanie_Matlab_Python.csv"
REFERENCE_MAPPING_CSV = BUCKETY / "Mapowanie_QB_Matlab_Python_Opis.csv"

# Kluczowe zalozenia mapowania (identyfikacja urzadzen):
# Pompa 01: devices/616ad07e-52e7-4293-aba1-2848073e1c33  |  Pompa 02: devices/ae8f16e0-b975-43df-9fd7-cba7530be7c9
# Sensor 1 (2757a0c4): pH (SoftSensorpH)  |  Sensor 2 (23c5c821): Tlen (TransportO2)  |  Sensor 3 (e43ea21d): Temp. plaszcza  |  Sensor 5 (0d2fa025): Temp. procesu
# Agitator (d2304eda): predkosc, energia  |  Sparger 1 (f67a5705): temp. gazu  |  CoolingStyle (185f554f): przeplyw (poziom), temp. (SP)

# Progi: ponizej tego score NIE wpisujemy sugerowanego mapowania (zostaje puste)
MIN_SCORE_L2 = 0.45
MIN_SCORE_L3 = 0.45

# Mapowanie typow sygnalu MTP na role (do dopasowania do Level 2: _Fbk/_PV vs _SP)
# Logika: VFbk/Actual = feedback (PV), VOut/Actual lub VMan/Setpoint = setpoint (SP), VMan/Actual = Manual
SIGNAL_TYPE_TO_ROLE = {
    "VFbk": "PV",
    "VOut": "SP",
    "VMan": "Manual",
    "V": "Value",
}


def signal_role_from_path(signal_type: str, influx_path: str) -> str:
    """Rola z pelnej sciezki: VFbk/Actual=PV, VOut/Actual lub VMan/Setpoint=SP, VMan/Actual=Manual."""
    suffix = (influx_path.split("/")[-1] or "").strip() if influx_path else ""
    if signal_type == "VFbk" and suffix == "Actual":
        return "PV"
    if signal_type == "VOut" and suffix == "Actual":
        return "SP"
    if signal_type == "VMan":
        return "SP" if suffix == "Setpoint" else "Manual"
    return SIGNAL_TYPE_TO_ROLE.get(signal_type, "Value")

# Klasyfikacja sygnalow Level 2: feedback (Fbk/PV/mod) vs setpoint (SP/set/flowrate)
def level2_role(measurement: str) -> str:
    """Zwraca 'feedback', 'setpoint' lub 'other' na podstawie nazwy zmiennej Level 2."""
    sig = (measurement.split("/")[-1] if "/" in measurement else measurement).lower()
    if "_sp" in sig or "setpoint" in sig or "flowrate" in sig or "qset" in sig or sig.startswith("i_to") or "compress" in sig or "frac_" in sig or "elemdepth" in sig or "elemdiameters" in sig or "medvolume" in sig:
        return "setpoint"
    if "_fbk" in sig or "_pv" in sig or "_mod" in sig or "medlevel" in sig or "medair" in sig or "medcoolant" in sig or "dword" in sig:
        return "feedback"
    return "other"


# Tagi QB, ktore NIE sa zmiennymi procesowymi (alarmy, enable, toggle, status) - nie mapowac na Level 2/3
NON_PROCESS_KEYWORDS = (
    "alarm", "enable", "toggle", "fault", "safe position", "interlock", "reset",
    "status", "probe alarm", "alarm high", "alarm low", "not connected",
    "quality indicator", "fault code", "chiller on", "safe position enable",
)
# Fragmenty nazw tagow MTP typowo nie-procesowe (alarmy, enable, status)
NON_PROCESS_NAME_PATTERNS = (
    "Switch", "Toggle", "Enable", "Reset", "faultCode", "qualityIndicator",
    "safeposEnable", "powerToggle", "interlockSwitch", "VAHEn", "VALEn",
    "VState0", "VState1", "OSLevel", "moduleIdentification", "protectReset",
    "rpmHighEn", "rpmLowEn", "safePosSwitch", "totaliserReset", "tubeDescription",
    "motorStatus", "metadata", "serialNumber", "coefficient", "controller",
)


def is_likely_process_variable(rec):
    """False = to alarm/konfig/status, nie sugeruj mapowania na Level 2/3."""
    name_raw = (rec.get("tag_name_resolved") or "").strip()
    name = name_raw.lower()
    desc = (rec.get("tag_description_resolved") or "").strip().lower()
    text = f"{name} {desc}"
    for kw in NON_PROCESS_KEYWORDS:
        if kw in text:
            return False
    for pat in NON_PROCESS_NAME_PATTERNS:
        if pat in name_raw:  # dokladne fragmenty w nazwie tagu (np. VAHEn, safeposEnable)
            return False
    return True


# Krotkie opisy semantyczne dla nazw Level 2 (do lepszego dopasowania)
LEVEL2_HINTS = {
    "o_pH_mod": "pH model SoftSensor",
    "o_kLa": "kLa oxygen Sparger DO dissolved oxygen",
    "o_DO_mod": "dissolved oxygen DO",
    "o_CO2_mod": "CO2 carbon dioxide",
    "o_Flow_mod": "flow gas oxygen",
    "i_Qset": "flow setpoint oxygen",
    "o_T_mod": "temperature",
    "o_Tj_mod": "jacket temperature",
    "i_T_PV": "temperature process value",
    "i_T_SP": "temperature setpoint",
    "o_Speed_Fbk": "speed RPM mixer",
    "i_Speed_SP": "speed setpoint mixer",
    "o_Flow_Fbk": "flow pump",
    "o_medLevel": "level medium tank",
    "o_medAir": "air surface area",
    "o_medCoolant": "coolant surface",
    "i_acid_flowrate": "acid pump flow",
    "i_base_flowrate": "base pump flow",
}


def load_data():
    if not DICT_PATH.exists():
        return None, [], []
    with open(DICT_PATH, encoding="utf-8") as f:
        data = json.load(f)
    dict_entries = data.get("metadata_dictionary") or []
    level2 = data.get("level2_targets") or []
    level3 = data.get("level3_targets") or []
    return dict_entries, level2, level3


def expand_dict_entries(dict_entries):
    """
    Rozwija slownik: jeden wpis na (path_prefix, signal_type) dla sygnalow wartosciowych.
    Kazdy wiersz ma signal_type (VFbk, VOut, VMan, V) i signal_role (PV, SP, Manual, Value),
    zeby mozna bylo dopasowac VFbk -> o_Flow_Fbk, VOut -> i_Speed_SP.
    """
    expanded = []
    for rec in dict_entries:
        signal_types = rec.get("signal_types") or []
        influx_paths = rec.get("influx_paths") or {}
        # Jesli brak signal_types (teoretycznie), uzyj V jako domysl
        if not signal_types and influx_paths:
            signal_types = list(influx_paths.keys())
        for st in signal_types:
            if st not in influx_paths:
                continue
            influx_path = influx_paths[st]
            expanded.append({
                "path_prefix": rec["path_prefix"],
                "signal_type": st,
                "signal_role": signal_role_from_path(st, influx_path),
                "influx_path": influx_path,
                "tag_name_resolved": rec.get("tag_name_resolved") or "",
                "tag_description_resolved": rec.get("tag_description_resolved") or "",
                "unit": rec.get("unit"),
                "mtp_object": rec.get("mtp_object"),
                "mtp_property": rec.get("mtp_property"),
            })
    return expanded


def _read_csv_semicolon(path, encodings=("utf-8", "utf-8-sig", "cp1250")):
    """Czyta CSV z separatorem ;, probuje rozne kodowania."""
    for enc in encodings:
        try:
            with open(path, encoding=enc, newline="") as f:
                return list(csv.reader(f, delimiter=";"))
        except (UnicodeDecodeError, OSError):
            continue
    return []


def load_reference_mapping():
    """
    Laduje Mapowanie_Matlab_Python.csv: L2->L3 + opisy (do uzupelnienia kolumny Opis).
    Zwraca: (l2_to_opis, l3_to_opis, l2_to_l3). Mapowanie L2/L3 pochodzi z regul (map_influx_to_l2_l3).
    """
    l2_to_opis = {}
    l3_to_opis = {}
    l2_to_l3 = {}

    if REFERENCE_L2_L3_CSV.exists():
        rows = _read_csv_semicolon(REFERENCE_L2_L3_CSV)
        for row in rows:
            if len(row) < 3:
                continue
            l2 = str(row[0]).strip()
            l3 = str(row[1]).strip()
            opis = str(row[2]).strip()
            if l2 and l2 != "-":
                l2_to_opis[l2] = opis or l2_to_opis.get(l2, "")
                if l3 and l3 != "-":
                    l2_to_l3[l2] = l3
            if l3 and l3 != "-":
                l3_to_opis[l3] = opis or l3_to_opis.get(l3, "")

    return l2_to_opis, l3_to_opis, l2_to_l3


def apply_opis_to_results(results, l2_to_opis, l3_to_opis):
    """Uzupelnia Opis (Znaczenie fizyczne) na podstawie L2/L3 z regul."""
    for r in results:
        l2 = r.get("suggested_level2_name") or ""
        l3 = r.get("suggested_level3_name") or ""
        r["opis_znaczenie_fizyczne"] = l2_to_opis.get(l2) or l3_to_opis.get(l3) or ""


def text_for_qb(rec, include_role=False):
    """Tekst do embedowania dla wpisu QB. include_role=True dodaje PV/SP dla lepszego dopasowania L2."""
    name = (rec.get("tag_name_resolved") or "").strip()
    desc = (rec.get("tag_description_resolved") or "").strip()
    base = f"{name} {desc}".strip() or rec.get("path_prefix", "")
    if include_role and rec.get("signal_role"):
        role = rec["signal_role"]
        if role == "PV":
            base += " feedback process value read"
        elif role == "SP":
            base += " setpoint command"
    return base


def text_for_level2(measurement: str):
    """Tekst do embedowania dla zmiennej Level 2 (np. Output/SoftSensorpH_01/o_pH_mod -> o_pH_mod + hint)."""
    part = measurement.split("/")[-1] if "/" in measurement else measurement
    hint = LEVEL2_HINTS.get(part, "")
    return f"{part} {hint}".strip()


def text_for_level3(measurement: str):
    """Tekst do embedowania dla zmiennej Level 3 (np. softsensorph/out_softsensorph_ph_est)."""
    return measurement.replace("/", " ").replace("_", " ")


def run_embeddings(expanded_entries, level2, level3):
    """Uzywa sentence-transformers; jeden wiersz na (path_prefix, signal_type). L2 filtrowane po signal_role."""
    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np
    except ImportError:
        print("Zainstaluj: pip install sentence-transformers")
        return None

    model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

    qb_texts = [text_for_qb(r, include_role=True) for r in expanded_entries]
    l2_texts = [text_for_level2(m) for m in level2]
    l3_texts = [text_for_level3(m) for m in level3]

    print("Embedowanie tekstow QB (z rola PV/SP)...")
    qb_emb = model.encode(qb_texts)
    print("Embedowanie Level 2...")
    l2_emb = model.encode(l2_texts)
    print("Embedowanie Level 3...")
    l3_emb = model.encode(l3_texts)

    l2_roles = [level2_role(m) for m in level2]

    def cos_sim(a, b):
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9)

    results = []
    for i, rec in enumerate(expanded_entries):
        role = rec.get("signal_role") or "Value"
        # Dla SP rozpatruj tylko sygnaly L2 setpoint; dla PV/Value tylko feedback lub other
        if role == "SP":
            cand_l2 = [j for j in range(len(level2)) if l2_roles[j] in ("setpoint", "other")]
        else:
            cand_l2 = [j for j in range(len(level2)) if l2_roles[j] in ("feedback", "other")]
        if not cand_l2:
            cand_l2 = list(range(len(level2)))

        best_l2_idx = cand_l2[int(np.argmax([cos_sim(qb_emb[i], l2_emb[j]) for j in cand_l2]))]
        best_l3_idx = int(np.argmax([cos_sim(qb_emb[i], l3_emb[j]) for j in range(len(level3))]))
        score_l2 = float(cos_sim(qb_emb[i], l2_emb[best_l2_idx]))
        score_l3 = float(cos_sim(qb_emb[i], l3_emb[best_l3_idx]))
        l2_val = level2[best_l2_idx] if score_l2 >= MIN_SCORE_L2 else ""
        l3_val = level3[best_l3_idx] if score_l3 >= MIN_SCORE_L3 else ""
        is_non_process = not is_likely_process_variable(rec)
        if is_non_process:
            l2_val, l3_val = "", ""
        results.append({
            "path_prefix": rec["path_prefix"],
            "signal_type": rec["signal_type"],
            "signal_role": rec["signal_role"],
            "influx_path": rec.get("influx_path") or "",
            "tag_name_resolved": rec.get("tag_name_resolved") or "",
            "tag_description_resolved": rec.get("tag_description_resolved") or "",
            "suggested_level2_name": l2_val,
            "suggested_level3_name": l3_val,
            "score_l2": round(score_l2, 4),
            "score_l3": round(score_l3, 4),
            "alarm_konfig_status": "TAK" if is_non_process else "NIE",
        })
    return results


def run_keyword_fallback(expanded_entries, level2, level3):
    """Proste dopasowanie po slowach kluczowych; L2 filtrowane po signal_role."""
    results = []
    l2_by_role = {r: [m for m in level2 if level2_role(m) == r] for r in ("feedback", "setpoint", "other")}
    for rec in expanded_entries:
        text = text_for_qb(rec, include_role=True).lower()
        role = rec.get("signal_role") or "Value"
        if role == "SP":
            l2_candidates = l2_by_role["setpoint"] + l2_by_role["other"]
        else:
            l2_candidates = l2_by_role["feedback"] + l2_by_role["other"]
        if not l2_candidates:
            l2_candidates = level2

        best_l2, best_l3 = "", ""
        best_l2_n, best_l3_n = 0, 0
        for m in l2_candidates:
            t = text_for_level2(m).lower()
            n = sum(1 for w in t.split() if len(w) > 1 and w in text)
            if n > best_l2_n:
                best_l2_n, best_l2 = n, m
        for m in level3:
            t = text_for_level3(m).lower()
            n = sum(1 for w in t.split() if w in text)
            if n > best_l3_n:
                best_l3_n, best_l3 = n, m
        score_l2 = best_l2_n / max(len(text_for_level2(best_l2).split()), 1) if best_l2 else 0
        score_l3 = best_l3_n / max(len(text_for_level3(best_l3).split()), 1) if best_l3 else 0
        l2_val = best_l2 if score_l2 >= MIN_SCORE_L2 else ""
        l3_val = best_l3 if score_l3 >= MIN_SCORE_L3 else ""
        is_non_process = not is_likely_process_variable(rec)
        if is_non_process:
            l2_val, l3_val = "", ""
        results.append({
            "path_prefix": rec["path_prefix"],
            "signal_type": rec["signal_type"],
            "signal_role": rec["signal_role"],
            "influx_path": rec.get("influx_path") or "",
            "tag_name_resolved": rec.get("tag_name_resolved") or "",
            "tag_description_resolved": rec.get("tag_description_resolved") or "",
            "suggested_level2_name": l2_val,
            "suggested_level3_name": l3_val,
            "score_l2": score_l2,
            "score_l3": score_l3,
            "alarm_konfig_status": "TAK" if is_non_process else "NIE",
        })
    return results


def main():
    ensure_output()
    dict_entries, level2, level3 = load_data()
    if not dict_entries:
        print("Brak metadata_dictionary.json. Uruchom build_dictionary.py")
        return 1

    expanded = expand_dict_entries(dict_entries)
    print(f"Rozwinieto do {len(expanded)} wierszy (path_prefix + signal_type: VFbk=PV, VOut=SP).")

    # Mapowanie L2/L3 z regul (map_influx_to_l2_l3) – jedyne zrodlo prawdy
    results = []
    for rec in expanded:
        influx_path = rec.get("influx_path") or ""
        l2, l3 = map_single_signal(influx_path)
        is_non_process = not is_likely_process_variable(rec)
        score_l2 = 1.0 if l2 else 0.0
        score_l3 = 1.0 if l3 else 0.0
        results.append({
            "path_prefix": rec["path_prefix"],
            "signal_type": rec["signal_type"],
            "signal_role": rec.get("signal_role", ""),
            "influx_path": influx_path,
            "tag_name_resolved": rec.get("tag_name_resolved", ""),
            "tag_description_resolved": rec.get("tag_description_resolved", ""),
            "suggested_level2_name": l2,
            "suggested_level3_name": l3,
            "score_l2": score_l2,
            "score_l3": score_l3,
            "alarm_konfig_status": "TAK" if is_non_process else "NIE",
        })

    l2_to_opis, l3_to_opis, l2_to_l3 = load_reference_mapping()
    apply_opis_to_results(results, l2_to_opis, l3_to_opis)

    # Zapis CSV: obowiazujacy plik mapowania do wyslania do zespolu
    with open(QB_LEVEL2_LEVEL3_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "path_prefix", "signal_type", "signal_role", "influx_path",
            "tag_name_resolved", "tag_description_resolved",
            "level2_name", "level3_name", "functional_role", "semantic_var",
            "Opis (Znaczenie fizyczne)",
            "alarm_konfig_status", "score_l2", "score_l3"
        ])
        for r in results:
            role = ""
            if r["suggested_level2_name"]:
                sig = r["suggested_level2_name"].split("/")[-1]
                if "pH" in sig or "ph" in sig:
                    role = "pH"
                elif "DO" in sig or "oxygen" in sig.lower() or "kLa" in sig:
                    role = "dissolved oxygen / kLa"
                elif "T_" in sig or "temp" in sig.lower():
                    role = "temperature"
                elif "Flow" in sig or "flow" in sig.lower():
                    role = "flow"
                elif "Speed" in sig or "speed" in sig.lower():
                    role = "speed / RPM"
            semantic_var = resolve_semantic_var(
                level2_name=r.get("suggested_level2_name", ""),
                tag_name_resolved=r.get("tag_name_resolved", ""),
                tag_description_resolved=r.get("tag_description_resolved", ""),
            )
            w.writerow([
                r["path_prefix"],
                r.get("signal_type", ""),
                r.get("signal_role", ""),
                r.get("influx_path", ""),
                r["tag_name_resolved"],
                r["tag_description_resolved"],
                r["suggested_level2_name"],
                r["suggested_level3_name"],
                role,
                semantic_var,
                r.get("opis_znaczenie_fizyczne", ""),
                r.get("alarm_konfig_status", "NIE"),
                r.get("score_l2", ""),
                r.get("score_l3", ""),
            ])

    print(f"Zapisano: {QB_LEVEL2_LEVEL3_CSV}")
    print("Mapowanie z regul (map_influx_to_l2_l3). Aplikacja: python apply_mapping.py --suggested")
    return 0


if __name__ == "__main__":
    sys.exit(main())
