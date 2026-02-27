"""
Reguły mapowania level2_name / tag_name_resolved -> semantic_var (Semantic Map).
Używane przez fill_semantic_var.py po zastosowaniu mapowania L2/L3.
"""
import re
from typing import Optional

# Ostatni segment level2_name (np. Output/TransportCiepla_01/i_T_PV -> i_T_PV) -> semantic_var
LEVEL2_TO_SEMANTIC: dict[str, str] = {
    # pH
    "o_pH_mod": "ph_value",
    "i_acid_flowrate": "acid_flowrate",
    "i_base_flowrate": "base_flowrate",
    # Tlen rozpuszczony / O2
    "o_DO_mod": "do_value",
    "o_DO_mod_CO2": "do_value_co2",
    "o_kLa": "kla_value",
    "i_Qset": "oxygen_flow_setpoint",
    "o_Flow_mod": "gas_flow_value",
    "i_compress_P": "gas_pressure",
    "i_frac_CO2": "frac_co2",
    "i_frac_O2": "frac_o2",
    # Temperatura
    "i_T_PV": "temperature_process",
    "i_T_SP": "temperature_setpoint",
    "i_To": "temperature_jacket",
    "o_T_mod": "temperature_process_model",
    "o_Tj_mod": "temperature_jacket_model",
    "o_k_est": "heat_transfer_coefficient",
    "o_k_loss_est": "heat_loss_coefficient",
    # Przepływ / pompy
    "o_Flow_Fbk": "flow_value",
    "i_Speed_SP": "speed_setpoint",
    "o_Speed_Fbk": "speed_feedback",
    # Mieszanie
    "o_Speed_Fbk": "speed_feedback",  # mieszadło
    "i_Speed_SP": "speed_setpoint",
    "o_usedEnergy": "energy_consumption",
    "o_mix_Level": "mixing_level",
    # Zbiornik
    "o_medLevel": "level_value",
    "o_medAir": "medium_air",
    "o_medCoolant": "medium_coolant",
    "o_medVolume": "medium_volume",
    "i_medVolume": "medium_volume_input",
    "i_elemDepth": "tank_elem_depth",
    "i_elemDiameters": "tank_elem_diameters",
    # Bubble / Sparger
    "o_A_Total": "bubble_area_total",
    "o_r_Bubble_01": "bubble_radius",
    # CO2
    "o_CO2_mod": "co2_value",
    # Pompa – statusy (opcjonalnie, można zostawić puste lub ujednolicić)
    "o_kodBledu": "fault_code",
    "o_poziom": "level_aux",
    # Alarmy
    "DWord": "alarms_status",
}

# Tag_name_resolved (lub fragment opisu) -> semantic_var – fallback gdy brak level2
TAG_TO_SEMANTIC: dict[str, str] = {
    "flow": "flow_value",
    "temperature": "temperature_value",
    "measurementFirstProbe": "measurement_value",  # ogólny pomiar – nadpisany przez level2
    "gasTemp": "gas_temperature",
    "totalizer": "totalized_flow",
    "valveDrive": "valve_opening",
}

# Słowa kluczowe w tag_description_resolved -> semantic_var (sprawdzenie zawiera)
TAG_DESCRIPTION_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bpH\b", re.I), "ph_value"),
    (re.compile(r"\b(DO|oxygen|tlen)\b", re.I), "do_value"),
    (re.compile(r"\b(PT100|temp|temperature|temperatura)\b", re.I), "temperature_value"),
    (re.compile(r"\bflow|przepływ\b", re.I), "flow_value"),
    (re.compile(r"\blevel|poziom\b", re.I), "level_value"),
]


def level2_signal_from_path(level2_name: str) -> str:
    """Wyciąga ostatni segment ze ścieżki L2, np. Output/TransportCiepla_01/i_T_PV -> i_T_PV."""
    if not level2_name or not isinstance(level2_name, str):
        return ""
    return level2_name.strip().split("/")[-1] if "/" in level2_name else level2_name.strip()


def semantic_var_from_level2(level2_name: str) -> Optional[str]:
    """Zwraca semantic_var na podstawie level2_name (pełna ścieżka lub sam sygnał)."""
    signal = level2_signal_from_path(level2_name)
    return LEVEL2_TO_SEMANTIC.get(signal)


def semantic_var_from_tag(tag_name: str, tag_description: str = "") -> Optional[str]:
    """Fallback: semantic_var z tag_name_resolved lub tag_description_resolved."""
    if tag_name:
        t = (tag_name or "").strip()
        if t in TAG_TO_SEMANTIC:
            return TAG_TO_SEMANTIC[t]
    if tag_description:
        desc = (tag_description or "").strip()
        for pattern, semantic in TAG_DESCRIPTION_PATTERNS:
            if pattern.search(desc):
                return semantic
    return None


def resolve_semantic_var(
    level2_name: str = "",
    tag_name_resolved: str = "",
    tag_description_resolved: str = "",
    *,
    prefer_level2: bool = True,
) -> str:
    """
    Ustala semantic_var: najpierw z level2_name, potem z tag_name/tag_description.
    prefer_level2=True (domyślnie): level2 ma pierwszeństwo.
    Zwraca pusty string jeśli nic nie pasuje.
    """
    if prefer_level2 and level2_name:
        sv = semantic_var_from_level2(level2_name)
        if sv:
            return sv
    sv = semantic_var_from_tag(tag_name_resolved or "", tag_description_resolved or "")
    if sv:
        return sv
    if not prefer_level2 and level2_name:
        sv = semantic_var_from_level2(level2_name)
        if sv:
            return sv
    return ""
