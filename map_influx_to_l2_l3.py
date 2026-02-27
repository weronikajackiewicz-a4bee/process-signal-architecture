# -*- coding: utf-8 -*-
"""
Mapowanie QB (Influx) → Level 2 (Matlab) → Level 3 (Python).
Źródło prawdy mapowania: reguły (słownik UUID urządzeń, logika VFbk/VOut, sygnały puste).
Używane przez suggest_mapping_llm.py do generowania QB_Level2_Level3_mapping.csv.
"""

from __future__ import annotations

import re
from typing import List, Tuple

import pandas as pd


# --- 1. Słownik Identyfikatorów Urządzeń (Device Registry) ---
DEVICE_REGISTRY = {
    "0d2fa025-787e-406b-baf3-08e502346a8a": "Sensor5",      # Temperatura procesu
    "e43ea21d-3c09-4a55-abad-d0ae3fa74e5a": "Sensor3",      # Temperatura płaszcza
    "616ad07e-52e7-4293-aba1-2848073e1c33": "Pompa_01",
    "ae8f16e0-b975-43df-9fd7-cba7530be7c9": "Pompa_02",
    "d2304eda-30b4-41bc-a866-b39bdf7f4b90": "Agitator",     # Mieszadło
    "185f554f-b1db-4a60-a733-fe05d4f2a428": "CoolingStyle", # System chłodzenia i poziom
    "f67a5705-092b-48a0-a6ee-e538aadf5c55": "Sparger1",    # Napowietrzanie
    "2757a0c4-af81-4273-87fb-2b0d87c5da34": "Sensor1",      # pH
    "23c5c821-2349-470f-8050-e9c028495916": "Sensor2",      # Tlen rozpuszczony (DO)
}

# --- Sygnały puste (nie mapujemy na L2/L3) ---
EMPTY_SIGNAL_PATTERNS = [
    "/faultCode",
    "/moduleIdentificationTrigger",
    "/qualityIndicator",
    "/VAHEn",           # alarm high (wszystkie warianty VAHEn*, VALEn*)
    "/VALEn",
    "/interlockSwitch",
    "/safePosSwitch",
    "/rpmHighEn",
    "/rpmLowEn",
    "/rpmALEN",
    "/tmpAHEN",
    "/tmpALEN",
    "/protectReset",
    "/resetTotalizer",
    "/safeposEnable",
    "/safeposSwitch",
    "/totaliserReset",
    "/tubeDescription",
    "/coefficient",
    "/current",
    "/totaliser",
    "/tare",
    "/userGasType",
    "/valveDrive",
    "/totalizer",
    "/powerToggle",
    "/measurementSecondProbe",
    "/measurementThirdProbe",
]
# Wzorce alarmów (VAHEn*, VALEn* itd.) – sprawdzamy po nazwie zmiennej
EMPTY_VARIABLE_REGEX = re.compile(
    r"^(VAHEn|VALEn|VAHEnFirstProbe|VAHEnSecondProbe|VAHEnThirdProbe|"
    r"VALEnFirstProbe|VALEnSecondProbe|VALEnThirdProbe)$"
)

# --- Mapowanie Level 2 → Level 3 ---
L2_TO_L3 = {
    "Output/TransportCiepla_01/i_T_PV": "heatmodel/out_heatmodel_t_1001",
    "Output/Zbiornik_01/o_medLevel": "tankgeometry/out_tankgeometry_mediumlevel_1010",
    "Output/TransportCiepla_01/i_T_SP": "tcumodel/out_tcumodel_tinternal_1001",
    "Output/TransportO2_01/o_DO_mod": "oxygentransport/out_oxygentransport_do_mgl",
    "Output/SoftSensorpH_01/o_pH_mod": "softsensorph/out_softsensorph_ph_est",
    "Output/Pompa_01/o_Flow_Fbk": "peristalticpump/out_peristalticpump_speed_rpm",
    "Output/Pompa_01/i_Speed_SP": "peristalticpump/out_peristalticpump_speed_rpm",
    "Output/Pompa_02/o_Flow_Fbk": "peristalticpump/out_peristalticpump_speed_rpm",
    "Output/Pompa_02/i_Speed_SP": "peristalticpump/out_peristalticpump_speed_rpm",
    "Output/Mieszanie_01/o_Speed_Fbk": "mixer/out_mixer_model_angular_velocity_rads",
    "Output/Mieszanie_01/i_Speed_SP": "mixer/out_mixer_rpm_setpoint",
    "Output/Mieszanie_01/o_usedEnergy": "mixer/out_mixer_energy_consumption_w",
    "Output/TransportCiepla_01/i_To": "heatmodel/out_heatmodel_tj_1001",
    "Output/Bubble_01/o_r_Bubble_01": "bubblegenerator/out_bubgen_r_bubble_m",
}


def _is_empty_signal(influx_path: str, variable: str) -> bool:
    """Sygnały diagnostyczne, alarmowe, techniczne → puste L2/L3."""
    if EMPTY_VARIABLE_REGEX.match(variable):
        return True
    for pattern in EMPTY_SIGNAL_PATTERNS:
        if pattern in influx_path:
            return True
    return False


def _is_feedback(influx_path: str) -> bool:
    """Feedback: /VFbk/Actual lub /measurementFirstProbe/V/Actual (V/Actual dla pomiaru)."""
    return "/VFbk/Actual" in influx_path or "/V/Actual" in influx_path


def _is_setpoint(influx_path: str) -> bool:
    """Setpoint: /VOut/Actual lub /VMan/Setpoint."""
    return "/VOut/Actual" in influx_path or "/VMan/Setpoint" in influx_path


def _parse_influx_path(influx_path: str) -> Tuple[str, str, str]:
    """
    Zwraca (device_id, object_name, variable).
    Ścieżka: devices/{UUID}/mtp/objects/{ObjectName}/{variable}/...
    """
    parts = influx_path.strip().split("/")
    if len(parts) < 6:
        return "", "", ""
    device_id = parts[1]
    object_name = parts[4]
    variable = parts[5]
    return device_id, object_name, variable


def map_single_signal(influx_path: str) -> Tuple[str, str]:
    """
    Mapuje pojedynczą ścieżkę Influx na (level2_name, level3_name).
    Zwraca ("", "") jeśli sygnał jest pusty lub nie pasuje do reguł fizyki procesu.
    """
    device_id, object_name, variable = _parse_influx_path(influx_path)
    if not device_id or not variable:
        return "", ""

    device_key = DEVICE_REGISTRY.get(device_id)
    if not device_key:
        return "", ""

    if _is_empty_signal(influx_path, variable):
        return "", ""

    # --- Sensor 5 (Temperatura procesu) ---
    if device_id == "0d2fa025-787e-406b-baf3-08e502346a8a":
        if "measurementFirstProbe" in variable and "/V/Actual" in influx_path:
            l2 = "Output/TransportCiepla_01/i_T_PV"
            return l2, L2_TO_L3.get(l2, "")

    # --- Sensor 3 (Temperatura płaszcza) ---
    if device_id == "e43ea21d-3c09-4a55-abad-d0ae3fa74e5a":
        if "measurementFirstProbe" in variable and "/V/Actual" in influx_path:
            l2 = "Output/TransportCiepla_01/i_To"
            return l2, L2_TO_L3.get(l2, "")

    # --- Pompa 01 ---
    if device_id == "616ad07e-52e7-4293-aba1-2848073e1c33":
        if "flow" in variable:
            if _is_feedback(influx_path):
                l2 = "Output/Pompa_01/o_Flow_Fbk"
                return l2, L2_TO_L3.get(l2, "")
            if _is_setpoint(influx_path):
                l2 = "Output/Pompa_01/i_Speed_SP"
                return l2, L2_TO_L3.get(l2, "")

    # --- Pompa 02 ---
    if device_id == "ae8f16e0-b975-43df-9fd7-cba7530be7c9":
        if "flow" in variable:
            if _is_feedback(influx_path):
                l2 = "Output/Pompa_02/o_Flow_Fbk"
                return l2, L2_TO_L3.get(l2, "")
            if _is_setpoint(influx_path):
                l2 = "Output/Pompa_02/i_Speed_SP"
                return l2, L2_TO_L3.get(l2, "")

    # --- Agitator (Mieszadło) ---
    if device_id == "d2304eda-30b4-41bc-a866-b39bdf7f4b90":
        if "rpmAHEN" in variable and _is_feedback(influx_path):
            l2 = "Output/Mieszanie_01/o_Speed_Fbk"
            return l2, L2_TO_L3.get(l2, "")
        if "rpmAHEN" in variable and _is_setpoint(influx_path):
            l2 = "Output/Mieszanie_01/i_Speed_SP"
            return l2, L2_TO_L3.get(l2, "")
        if "temperature" in variable and "/V/Actual" in influx_path:
            l2 = "Output/Mieszanie_01/o_usedEnergy"
            return l2, L2_TO_L3.get(l2, "")

    # --- CoolingStyle (chłodzenie + poziom) ---
    if device_id == "185f554f-b1db-4a60-a733-fe05d4f2a428":
        if "flow" in variable and "/V/Actual" in influx_path:
            l2 = "Output/Zbiornik_01/o_medLevel"
            return l2, L2_TO_L3.get(l2, "")
        if "temperature" in variable and (_is_feedback(influx_path) or _is_setpoint(influx_path)):
            l2 = "Output/TransportCiepla_01/i_T_SP"
            return l2, L2_TO_L3.get(l2, "")

    # --- Sparger 1 (Napowietrzanie) ---
    if device_id == "f67a5705-092b-48a0-a6ee-e538aadf5c55":
        if "gasTemp" in variable and "/V/Actual" in influx_path:
            l2 = "Output/Bubble_01/o_r_Bubble_01"
            return l2, L2_TO_L3.get(l2, "")

    # --- Sensor 1 (pH) ---
    if device_id == "2757a0c4-af81-4273-87fb-2b0d87c5da34":
        if "measurementFirstProbe" in variable and "/V/Actual" in influx_path:
            l2 = "Output/SoftSensorpH_01/o_pH_mod"
            return l2, L2_TO_L3.get(l2, "")

    # --- Sensor 2 (DO) ---
    if device_id == "23c5c821-2349-470f-8050-e9c028495916":
        if "measurementFirstProbe" in variable and "/V/Actual" in influx_path:
            l2 = "Output/TransportO2_01/o_DO_mod"
            return l2, L2_TO_L3.get(l2, "")

    return "", ""


def map_influx_paths_to_dataframe(influx_paths: List[str]) -> pd.DataFrame:
    """
    Przyjmuje listę ścieżek z InfluxDB i zwraca ramkę danych z kolumnami:
    - influx_path
    - level2_name
    - level3_name

    Ścieżki niepasujące do reguł fizyki procesu mają puste level2_name i level3_name.
    """
    rows = []
    for path in influx_paths:
        path = path.strip()
        if not path:
            continue
        l2, l3 = map_single_signal(path)
        rows.append({"influx_path": path, "level2_name": l2, "level3_name": l3})
    return pd.DataFrame(rows)


# --- Skrypt porównawczy (uruchomienie bezpośrednie) ---
if __name__ == "__main__":
    import os

    base = os.path.dirname(os.path.abspath(__file__))
    mapping_path = os.path.join(base, "output", "QB_Level2_Level3_mapping.csv")
    out_path = os.path.join(base, "output", "mapping_from_rules.csv")

    if os.path.isfile(mapping_path):
        ref = pd.read_csv(mapping_path)
        if "influx_path" in ref.columns:
            paths = ref["influx_path"].dropna().astype(str).unique().tolist()
        else:
            paths = ref.iloc[:, 0].dropna().astype(str).unique().tolist()
        df = map_influx_paths_to_dataframe(paths)
        df.to_csv(out_path, index=False, encoding="utf-8-sig")
        print(f"Zapisano: {out_path} ({len(df)} wierszy)")
        print("Kolumny:", list(df.columns))
    else:
        print("Brak pliku QB_Level2_Level3_mapping.csv – podaj listę ścieżek do map_influx_paths_to_dataframe()")
