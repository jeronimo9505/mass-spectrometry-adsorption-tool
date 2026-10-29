"""
TGA Report Engine (Publication Styles A & B + Combined Excel + Complete PDF Report)
===================================================================================
Takes raw TGA data (time / temperature / weight % / DTG) plus the paste
composition and experimental conditions and produces:

  * Automatic step detection (DTG minima + low-DTG tail) or manual step limits
    for both Zeolite 13X pastes (4-step) and Silica gel pastes (3-step with
    180–900 °C zoom insets and Zhuravlev silanol model)
  * Mass-loss table, interpretation, "expected from composition" comparison
  * Style A (Journal Vertical): DTG on top, Mass on bottom with step callout boxes
    (plus 180–900 °C zoom insets for Silica gel pastes)
  * Style B (Presentation Landscape): Mass + DTG on left, summary tables on right
    (plus 180–900 °C zoom insets for Silica gel pastes)
  * Export of both figures at any DPI (300 / 600 / 1200 ...), PDF, SVG
  * Single Combined Master Excel workbook with all 8 sheets:
      1. Info (Measuring conditions & summary)
      2. Paste composition
      3. Steps
      4. Interpretation
      5. Theory vs measured
      6. References
      7. Processed data
      8. Raw data (as exported)
  * Complete multi-page PDF report (Style B + Style A + Conditions, Composition,
    Interpretation, Theory vs Measured & References tables)
  * Self-contained HTML report with both Style A and Style B figures
"""

import os
import io
import json
import html
import base64
import textwrap
import datetime

import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.patches import FancyBboxPatch
from matplotlib.lines import Line2D
from matplotlib.ticker import AutoMinorLocator
from matplotlib.backends.backend_pdf import PdfPages

# --------------------------------------------------------------------------- #
# Constants / knowledge base
# --------------------------------------------------------------------------- #

STEP_COLORS = ["#3f8fe0", "#9b4dca", "#ef8a35", "#33b36b", "#d4a017", "#8d6e63", "#607d8b", "#c2185b"]
SILICA_STEP_COLORS = ["#3f8fe0", "#ef8a35", "#33b36b", "#9b4dca", "#d4a017"]
ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]

ROLE_ZEOLITE = "zeolite"
ROLE_SILICA = "silica"
ROLE_CLAY = "clay"
ROLE_ORGANIC = "organic"
ROLE_WATER = "water"
ROLE_OTHER = "other"
ROLES = [ROLE_ZEOLITE, ROLE_SILICA, ROLE_CLAY, ROLE_ORGANIC, ROLE_WATER, ROLE_OTHER]

CLAY_OH_FRACTION = 0.048          # smectite dehydroxylation: 4.7-4.9 % of clay mass
SILICA_OH_FULL_FRAC = 0.02060     # full condensation from 4.6 OH/nm² × 300 m²/g (2.06 % of silica mass)
SILICA_VICINAL_OH_FRAC = 0.01290  # 4.6 -> ~1.7 OH/nm² in Step II (0.36 wt% for 27.91 wt% silica)
SILICA_ISOLATED_OH_FRAC = 0.00466 # ~1.7 -> ~0.7 OH/nm² in Step III (0.13 wt% for 27.91 wt% silica)

STYLE_A = "style_a"       # Journal vertical (DTG top, Mass bottom with callout boxes)
STYLE_B = "style_b"       # Presentation landscape (Mass+DTG left, tables right)
STYLE_BOTH = "both"       # Side-by-side preview

DEFAULT_COMPOSITION = [
    {"component": "Zeolite 13X", "mass_g": 43.97, "role": ROLE_ZEOLITE, "note": ""},
    {"component": "Bentonite", "mass_g": 5.14, "role": ROLE_CLAY, "note": ""},
    {"component": "PEG-400", "mass_g": 9.0, "role": ROLE_ORGANIC, "note": "5 g before + 4 g after"},
    {"component": "Methyl cellulose", "mass_g": 1.31, "role": ROLE_ORGANIC, "note": ""},
    {"component": "Water", "mass_g": 57.0, "role": ROLE_WATER, "note": "50 g before + 7 g after"},
]
DEFAULT_ZEOLITE_PASTE = DEFAULT_COMPOSITION

DEFAULT_SILICA_COMPOSITION = [
    {"component": "Silica gel", "mass_g": 18.0, "role": ROLE_SILICA,
     "note": "90 wt% of dry mix; 150 Å pores, 1.15 cm³/g, ~300 m²/g, 35–70 µm"},
    {"component": "Bentonite", "mass_g": 1.4, "role": ROLE_CLAY,
     "note": "7 wt% of dry mix"},
    {"component": "Methyl cellulose", "mass_g": 0.6, "role": ROLE_ORGANIC,
     "note": "3 wt% of dry mix"},
    {"component": "Water", "mass_g": 44.5, "role": ROLE_WATER,
     "note": "Dry mix 90/7/3 (20 g) + 44.5 g water (2.23 g water per g of dry mix)"},
]
DEFAULT_SILICA_PASTE = DEFAULT_SILICA_COMPOSITION

DEFAULT_CONDITIONS = {
    "atmosphere": "Air",
    "flow_ml_min": 50.0,
    "heating_rate": 10.0,
    "sample_mass_mg": 0.0,
    "tail_threshold": 0.005,
    "manual_limits": "",
    "loaded_pct": 100.0,
}

REFERENCES_ZEOLITE = {
    1: dict(
        short="Marcos et al., Nanomaterials 8 (2018) 16. doi:10.3390/nano8010016",
        full="Marcos M.A., Cabaleiro D., Guimarey M.J.G., Comuñas M.J.P., Fedele L., Fernández J., Lugo L. "
             "PEG 400-based phase change materials nano-enhanced with functionalized graphene nanoplatelets. "
             "Nanomaterials 8 (2018) 16.",
        doi="10.3390/nano8010016",
        used="PEG-400 in N2 at 10 K/min: onset ~507 K (234 °C); main loss 460–670 K (187–397 °C)"),
    2: dict(
        short="Han, Kim, Kwon, Polymer 38 (1997) 317–323. doi:10.1016/S0032-3861(97)88175-X",
        full="Han S., Kim C., Kwon D. Thermal/oxidative degradation and stabilization of polyethylene glycol. "
             "Polymer 38 (1997) 317–323.",
        doi="10.1016/S0032-3861(97)88175-X",
        used="PEG undergoes thermal/oxidative degradation in air"),
    3: dict(
        short="Xiao et al., Polymers 13 (2021) 3291. doi:10.3390/polym13193291",
        full="Xiao Q., Huang M., Zhou X., Dai M., Zhao Z., Zhou H. Effect of molecular weight and degree of "
             "substitution on the physical-chemical properties of methylcellulose-starch nanocrystal "
             "nanocomposite films. Polymers 13 (2021) 3291.",
        doi="10.3390/polym13193291",
        used="Methyl cellulose films in N2 at 10 °C/min: water loss below 100 °C, then chain degradation; T10 = 292 °C"),
    4: dict(
        short="de Gennaro et al., Materials 15 (2022) 5574. doi:10.3390/ma15165574",
        full="de Gennaro B., Cappi A., de Gennaro M., Bianco N., Langella A., Cappelletti P., Marocco A., "
             "Aprea P., Pansini M. Use of zeolites in the capture and storage of thermal energy by water "
             "desorption–adsorption cycles. Materials 15 (2022) 5574.",
        doi="10.3390/ma15165574",
        used="Zeolite 13X: most of the zeolitic water is lost by 300 °C"),
    5: dict(
        short="Derkowski & Kuligiewicz, Clays Clay Miner. 70 (2022) 946–972. doi:10.1007/s42860-023-00222-y",
        full="Derkowski A., Kuligiewicz A. Thermal analysis and thermal reactions of smectites: a review of "
             "methodology, mechanisms, and kinetics. Clays and Clay Minerals 70 (2022) 946–972.",
        doi="10.1007/s42860-023-00222-y",
        used="Smectite (bentonite): dehydration ends below 200 °C; dehydroxylation between ~300 and 900 °C "
             "with 4.7–4.9 % mass loss"),
    6: dict(
        short="Guo et al., Coatings 10 (2020) 499. doi:10.3390/coatings10050499",
        full="Guo P., Wang F., Duo T., Xiao Z., Xu A., Liu R., Jiang C. Facile fabrication of "
             "methylcellulose/PLA membrane with improved properties. Coatings 10 (2020) 499.",
        doi="10.3390/coatings10050499",
        used="Methyl cellulose in N2 at 10 °C/min: decomposition temperature 343 °C"),
    7: dict(
        short="Thakkar et al., ACS Appl. Mater. Interfaces 8 (2016) 27753. doi:10.1021/acsami.6b09647",
        full="Thakkar H., Eastman S., Hajari A., Rownaghi A.A., Knox J.C., Rezaei F. 3D-printed zeolite "
             "monoliths for CO2 removal from enclosed environments. ACS Applied Materials & Interfaces 8 "
             "(2016) 27753–27761.",
        doi="10.1021/acsami.6b09647",
        used="Background: zeolite 13X / bentonite / methyl cellulose paste for 3D-printed CO2 monoliths"),
}

REFERENCES_SILICA = {
    1: dict(
        short="Zhuravlev, Colloids Surf. A 173 (2000) 1–38. doi:10.1016/S0927-7757(00)00556-2",
        full="Zhuravlev L.T. The surface chemistry of amorphous silica. Zhuravlev model. Colloids and "
             "Surfaces A: Physicochemical and Engineering Aspects 173 (2000) 1–38.",
        doi="10.1016/S0927-7757(00)00556-2",
        used="Silanol number of amorphous silica 4.6 OH/nm²; physisorbed water removed by 190 ± 10 °C; "
             "vicinal OH condense up to ~400 °C, isolated OH remain to >900 °C"),
    2: dict(
        short="Wan, Ramsey, Baran, J. Therm. Anal. Calorim. 99 (2010) 237–243. doi:10.1007/s10973-009-0139-8",
        full="Wan Q., Ramsey C., Baran G. Thermal pretreatment of silica composite filler materials. "
             "Journal of Thermal Analysis and Calorimetry 99 (2010) 237–243.",
        doi="10.1007/s10973-009-0139-8",
        used="TGA of silica in air: loss up to 200 °C = physically bound water; 200–1000 °C = silanol "
             "condensation; dehydroxylation irreversible above 400 °C"),
    3: dict(
        short="Thakkar et al., ACS Appl. Mater. Interfaces 9 (2017) 7489–7498. doi:10.1021/acsami.6b16732",
        full="Thakkar H., Eastman S., Al-Mamoori A., Hajari A., Rownaghi A.A., Rezaei F. Formulation of "
             "aminosilica adsorbents into 3D-printed monoliths and evaluation of their CO2 capture "
             "performance. ACS Applied Materials & Interfaces 9 (2017) 7489–7498.",
        doi="10.1021/acsami.6b16732",
        used="Background: silica / bentonite / methyl cellulose paste for 3D-printed CO2 adsorbent monoliths"),
    4: dict(
        short="Derkowski & Kuligiewicz, Clays Clay Miner. 70 (2022) 946–972. doi:10.1007/s42860-023-00222-y",
        full="Derkowski A., Kuligiewicz A. Thermal analysis and thermal reactions of smectites: a review of "
             "methodology, mechanisms, and kinetics. Clays and Clay Minerals 70 (2022) 946–972.",
        doi="10.1007/s42860-023-00222-y",
        used="Smectite (bentonite): dehydration ends below 200 °C; dehydroxylation between ~300 and 900 °C "
             "with 4.7–4.9 % mass loss"),
    5: dict(
        short="Xiao et al., Polymers 13 (2021) 3291. doi:10.3390/polym13193291",
        full="Xiao Q., Huang M., Zhou X., Dai M., Zhao Z., Zhou H. Effect of molecular weight and degree of "
             "substitution on the physical-chemical properties of methylcellulose-starch nanocrystal "
             "nanocomposite films. Polymers 13 (2021) 3291.",
        doi="10.3390/polym13193291",
        used="Methyl cellulose films in N2 at 10 °C/min: water loss below 100 °C, then chain degradation; T10 = 292 °C"),
    6: dict(
        short="Guo et al., Coatings 10 (2020) 499. doi:10.3390/coatings10050499",
        full="Guo P., Wang F., Duo T., Xiao Z., Xu A., Liu R., Jiang C. Facile fabrication of "
             "methylcellulose/PLA membrane with improved properties. Coatings 10 (2020) 499.",
        doi="10.3390/coatings10050499",
        used="Methyl cellulose in N2 at 10 °C/min: decomposition temperature 343 °C"),
}

REFERENCES = REFERENCES_ZEOLITE


def get_references_for(analysis_or_comp):
    if isinstance(analysis_or_comp, dict) and "is_silica" in analysis_or_comp:
        return REFERENCES_SILICA if analysis_or_comp["is_silica"] else REFERENCES_ZEOLITE
    if is_silica_paste(analysis_or_comp):
        return REFERENCES_SILICA
    return REFERENCES_ZEOLITE


# --------------------------------------------------------------------------- #
# Composition helpers
# --------------------------------------------------------------------------- #

def is_silica_paste(comp):
    """Returns True when the paste main solid is silica / silica gel."""
    for r in comp or []:
        role = str(r.get("role", "")).lower()
        name = str(r.get("component", "")).lower()
        if role == ROLE_SILICA or "silica" in name:
            return True
    return False


def normalise_composition(comp):
    """
    Returns a cleaned copy of the composition with 'pct' (wet basis) and 'dry_pct' (dry mix basis)
    per component, rounded to 2 decimal places such that the sum of rounded wet percentages is 100.00 %.
    """
    rows = []
    for c in comp or []:
        try:
            m = float(c.get("mass_g", 0.0) or 0.0)
        except (TypeError, ValueError):
            m = 0.0
        name = str(c.get("component", "")).strip()
        if not name or m <= 0:
            continue
        role = c.get("role", ROLE_OTHER)
        if role not in ROLES:
            role = ROLE_OTHER
        if "silica" in name.lower() and role in (ROLE_ZEOLITE, ROLE_OTHER):
            role = ROLE_SILICA
        rows.append({"component": name, "mass_g": m, "role": role, "note": str(c.get("note", "") or "")})
    total = sum(r["mass_g"] for r in rows)
    dry_total = sum(r["mass_g"] for r in rows if r["role"] != ROLE_WATER)
    if total > 0 and rows:
        raw_pcts = [r["mass_g"] / total * 100.0 for r in rows]
        rounded = [round(p, 2) for p in raw_pcts]
        diff = round(100.0 - sum(rounded), 2)
        if abs(diff) >= 0.01:
            candidates = [
                (raw_pcts[i], i)
                for i in range(len(rows))
                if (diff < 0 and rounded[i] > raw_pcts[i]) or (diff > 0 and rounded[i] < raw_pcts[i])
            ]
            if candidates:
                _, idx = min(candidates)
                rounded[idx] = round(rounded[idx] + diff, 2)
        for r, p in zip(rows, rounded):
            r["pct"] = p
            if r["role"] == ROLE_WATER or dry_total <= 0:
                r["dry_pct"] = None
            else:
                dp = r["mass_g"] / dry_total * 100.0
                r["dry_pct"] = int(round(dp)) if abs(dp - round(dp)) < 0.05 else round(dp, 2)
    else:
        for r in rows:
            r["pct"] = 0.0
            r["dry_pct"] = None
    return rows


def composition_total(comp):
    return sum(r["mass_g"] for r in comp)


def dry_mix_summary_line(comp):
    """For silica pastes, e.g. '(dry mix 90/7/3, 20 g + 44.5 g water)'."""
    dry_rows = [r for r in comp if r["role"] != ROLE_WATER]
    water_rows = [r for r in comp if r["role"] == ROLE_WATER]
    if not dry_rows or not water_rows:
        return ""
    dry_m = sum(r["mass_g"] for r in dry_rows)
    wat_m = sum(r["mass_g"] for r in water_rows)
    ratios = "/".join(
        f"{int(round(r['mass_g'] / dry_m * 100))}" if abs(r["mass_g"] / dry_m * 100 - round(r["mass_g"] / dry_m * 100)) < 0.15
        else f"{r['mass_g'] / dry_m * 100:.1f}"
        for r in dry_rows
    )
    return f"(dry mix {ratios}, {dry_m:g} g + {wat_m:g} g water)"


def _role_rows(comp, role):
    return [r for r in comp if r["role"] == role]


def _role_pct(comp, role):
    return round(sum(r["pct"] for r in _role_rows(comp, role)), 2)


def _names(comp, role, default):
    n = [r["component"] for r in _role_rows(comp, role)]
    return n if n else [default]


def _join_and(names):
    return " and ".join(names) if len(names) <= 2 else ", ".join(names[:-1]) + " and " + names[-1]


def _fmt_t(x):
    return f"{x:.0f}"


# --------------------------------------------------------------------------- #
# Analysis
# --------------------------------------------------------------------------- #

def parse_manual_limits(text):
    out = []
    for tok in str(text or "").replace(";", ",").replace(" ", ",").split(","):
        tok = tok.strip()
        if not tok:
            continue
        try:
            out.append(float(tok))
        except ValueError:
            pass
    return sorted(set(out))


def fit_heating_rate(df, lo=100.0, hi=800.0):
    """Linear fit of T vs time between lo and hi °C (needs a 'time' column in min)."""
    if "time" not in df.columns:
        return None
    sub = df[(df["temperature"] >= lo) & (df["temperature"] <= hi)].dropna(subset=["time"])
    if len(sub) < 10 or sub["time"].nunique() < 5:
        return None
    slope = np.polyfit(sub["time"].values, sub["temperature"].values, 1)[0]
    return float(slope)


def analyze_tga(df, composition=None, conditions=None):
    """
    Full TGA analysis. Returns a dict with: steps, totals, theory, interpretation, info.
    `df` needs columns temperature, weight, deriv_weight (and optional time).
    Automatically adapts to Zeolite 13X paste (4-step) or Silica gel paste (3-step + zoom insets).
    """
    from scipy.signal import find_peaks, savgol_filter

    cond = dict(DEFAULT_CONDITIONS)
    cond.update(conditions or {})
    comp = normalise_composition(composition if composition is not None else DEFAULT_COMPOSITION)
    silica_mode = is_silica_paste(comp)
    atm = str(cond.get("atmosphere", "Air"))
    loaded = float(cond.get("loaded_pct", 100.0) or 100.0)
    thr = float(cond.get("tail_threshold", 0.005) or 0.005)

    d = df.dropna(subset=["temperature", "weight"]).reset_index(drop=True)
    t = d["temperature"].values.astype(float)
    w = d["weight"].values.astype(float)
    dtg = np.nan_to_num(d["deriv_weight"].values.astype(float), nan=0.0)
    dtg = np.abs(dtg)
    n = len(t)
    if n < 20:
        raise ValueError("Not enough data points for TGA analysis.")
    t_mono = np.maximum.accumulate(t)

    win = max(11, (n // 150) | 1)
    if win >= n:
        win = (n - 1) | 1 if (n - 1) % 2 == 0 else n - 2
    dtg_s = savgol_filter(dtg, win, 2) if win > 3 else dtg.copy()
    dtg_s = np.maximum(dtg_s, 0.0)

    def w_at(x):
        return float(np.interp(x, t_mono, w))

    def idx_at(x):
        return int(np.clip(np.searchsorted(t_mono, x), 0, n - 1))

    manual = parse_manual_limits(cond.get("manual_limits", ""))
    limit_kinds = []
    if manual:
        bounds = [x for x in manual if t[0] < x < t[-1]]
        limit_kinds = ["manual"] * len(bounds)
    elif silica_mode:
        # Silica gel paste: 3 steps separated by DTG minima (~201 °C and ~543 °C)
        bounds = []
        m1_mask = (t_mono >= 170.0) & (t_mono <= 250.0)
        if m1_mask.any():
            i1 = np.where(m1_mask)[0][int(np.argmin(dtg[m1_mask]))]
            bounds.append(float(t_mono[i1]))
            limit_kinds.append("min")
        m2_mask = (t_mono >= 450.0) & (t_mono <= 565.0)
        if m2_mask.any():
            i2 = np.where(m2_mask)[0][int(np.argmin(dtg[m2_mask]))]
            if not bounds or t_mono[i2] > bounds[-1] + 20:
                bounds.append(float(t_mono[i2]))
                limit_kinds.append("min")
    else:
        dmax = float(dtg_s.max())
        pk, _ = find_peaks(dtg_s, prominence=max(0.005 * dmax, 0.5 * thr))
        bounds = []
        for a, b in zip(pk[:-1], pk[1:]):
            k = a + int(np.argmin(dtg_s[a:b + 1]))
            bounds.append(float(t_mono[k]))
            limit_kinds.append("min")
        if len(pk):
            above = np.where(dtg_s[pk[-1]:] >= thr)[0]
            tail_idx = pk[-1] + (int(above[-1]) if len(above) else 0)
            tail_t = float(np.ceil(t_mono[tail_idx] / 50.0) * 50.0)
            if tail_t < t[-1] - 20 and (not bounds or tail_t > bounds[-1] + 10):
                bounds.append(tail_t)
                limit_kinds.append("tail")

    edges_t = [float(t[0])] + [float(b) for b in bounds] + [float(t[-1])]
    palette = SILICA_STEP_COLORS if silica_mode else STEP_COLORS
    steps = []
    for i in range(len(edges_t) - 1):
        lo_t, hi_t = edges_t[i], edges_t[i + 1]
        lo_i, hi_i = (0 if i == 0 else idx_at(lo_t)), (n - 1 if i == len(edges_t) - 2 else idx_at(hi_t))
        # For silica step III (above 540 °C), ignore instrument artefact above 700 °C when finding peak
        search_hi_i = idx_at(min(hi_t, 690.0)) if (silica_mode and lo_t >= 450.0) else hi_i
        seg_s = dtg_s[lo_i:max(lo_i + 1, search_hi_i + 1)]
        seg_raw = dtg[lo_i:max(lo_i + 1, search_hi_i + 1)]
        peak_t, peak_h, weak = float(t_mono[lo_i]), 0.0, True
        if len(seg_s) > 5:
            if silica_mode:
                best = int(np.argmax(seg_raw))
                peak_t = float(t_mono[lo_i + best])
                peak_h = float(seg_raw[best])
                weak = peak_h < 0.005 * float(dtg.max())
            else:
                pks, props = find_peaks(seg_s, prominence=1e-4)
                if len(pks):
                    best = pks[int(np.argmax(props["prominences"]))]
                else:
                    best = int(np.argmax(seg_s))
                peak_t, peak_h = float(t_mono[lo_i + best]), float(seg_s[best])
                weak = peak_h < 0.05 * float(dtg_s.max())
        m_start = loaded if i == 0 else round(w_at(lo_t), 2) if silica_mode else w_at(lo_t)
        m_end = round(float(w[-1]), 2) if (i == len(edges_t) - 2 and silica_mode) else (
            float(w[-1]) if i == len(edges_t) - 2 else (round(w_at(hi_t), 2) if silica_mode else w_at(hi_t))
        )
        loss_val = round(m_start - m_end, 2) if silica_mode else (m_start - m_end)
        steps.append({
            "label": ROMAN[i] if i < len(ROMAN) else str(i + 1),
            "t_start": None if i == 0 else lo_t,
            "t_end": hi_t,
            "peak_t": peak_t,
            "peak_h": peak_h,
            "weak": bool(weak),
            "m_start": m_start,
            "m_end": m_end,
            "loss": loss_val,
            "color": palette[i % len(palette)],
            "kind_end": (limit_kinds[i] if i < len(limit_kinds) else "end"),
        })

    # Compute dry-paste basis (% of mass at end of step I)
    dry_paste_mass = steps[0]["m_end"] if steps else 0.0
    for idx, s in enumerate(steps):
        s["cls"] = _classify_step(s, silica_mode=silica_mode, step_idx=idx)
        if idx == 0 or dry_paste_mass <= 0:
            s["loss_dry_basis"] = None
        else:
            s["loss_dry_basis"] = round(s["loss"] / dry_paste_mass * 100.0, 2)

    residue = float(w[-1])
    total_loss = loaded - residue
    pre_loss = loaded - float(w[0])
    totals = {
        "loaded_pct": loaded,
        "residue": residue,
        "total_loss": total_loss,
        "recorded_loss": float(w[0]) - residue,
        "pre_loss": pre_loss,
        "first_weight": float(w[0]),
        "t_first": float(t[0]),
        "t_last": float(t[-1]),
        "n_points": int(n),
        "peak_t_main": float(t_mono[int(np.argmax(dtg if silica_mode else dtg_s))]),
        "peak_h_main": float((dtg if silica_mode else dtg_s).max()),
        "dry_paste_mass": round(dry_paste_mass, 2),
    }
    hr_fit = fit_heating_rate(d)
    if "time" in d.columns and d["time"].notna().any():
        totals["run_time_min"] = float(d["time"].max())
    totals["heating_rate_fit"] = hr_fit

    theory = _theory_vs_measured(steps, comp, totals, silica_mode=silica_mode)
    interp = _interpretation(steps, comp, atm, theory, silica_mode=silica_mode)

    onset = None
    for s in steps:
        if s["cls"] in ("bound", "organic") and s["t_start"]:
            onset = s["t_start"]
            break
    if onset is None:
        onset = round(totals["peak_t_main"] * 0.75, 1)

    return {
        "is_silica": silica_mode,
        "steps": steps,
        "totals": totals,
        "theory": theory,
        "interpretation": interp,
        "composition": comp,
        "conditions": cond,
        "limit_kinds": limit_kinds,
        "limits": [float(b) for b in bounds],
        "onset": float(onset),
        "arrays": {"t": t, "w": w, "dtg": dtg, "dtg_s": dtg_s},
        "df": d,
    }


def _classify_step(s, silica_mode=False, step_idx=0):
    pk = s["peak_t"]
    if silica_mode:
        if step_idx == 0 or pk < 200:
            return "water"
        if step_idx == 1 or pk < 480:
            return "organic"
        return "clay"
    if pk < 170:
        return "water"
    if pk < 230:
        return "bound"
    if pk <= 450:
        return "organic"
    return "clay"


def _theory_vs_measured(steps, comp, totals, silica_mode=False):
    water = _role_pct(comp, ROLE_WATER)
    org = _role_pct(comp, ROLE_ORGANIC)
    clay = _role_pct(comp, ROLE_CLAY)
    silica = _role_pct(comp, ROLE_SILICA)
    clay_oh = round(clay * CLAY_OH_FRACTION, 2)
    meas_water = sum(s["loss"] for s in steps if s["cls"] == "water")
    meas_org = sum(s["loss"] for s in steps if s["cls"] in ("bound", "organic"))
    meas_clay = sum(s["loss"] for s in steps if s["cls"] == "clay")
    residue = totals["residue"]

    if silica_mode:
        vicinal_oh = round(silica * SILICA_VICINAL_OH_FRAC, 2)
        isolated_oh = round(silica * SILICA_ISOLATED_OH_FRAC, 2)
        step2_exp = round(org + vicinal_oh, 2)
        step3_exp = round(clay_oh + isolated_oh, 2)
        tot_g = composition_total(comp) or 1.0
        w_unrounded = sum(r["mass_g"] for r in _role_rows(comp, ROLE_WATER)) / tot_g * 100.0
        o_unrounded = sum(r["mass_g"] for r in _role_rows(comp, ROLE_ORGANIC)) / tot_g * 100.0
        c_unrounded = sum(r["mass_g"] for r in _role_rows(comp, ROLE_CLAY)) / tot_g * 100.0
        s_unrounded = sum(r["mass_g"] for r in _role_rows(comp, ROLE_SILICA)) / tot_g * 100.0
        raw_total_exp = (w_unrounded + o_unrounded + s_unrounded * SILICA_VICINAL_OH_FRAC
                         + c_unrounded * CLAY_OH_FRACTION + s_unrounded * SILICA_ISOLATED_OH_FRAC)
        exp_loss_total = round(raw_total_exp, 2)
        exp_residue = round(100.0 - exp_loss_total, 2)
        org_dry_exp = round(sum((r["dry_pct"] or 0.0) for r in _role_rows(comp, ROLE_ORGANIC)), 2)
        org_dry_meas = steps[1]["loss_dry_basis"] if len(steps) > 1 and steps[1].get("loss_dry_basis") else 0.0
        # Water evaporated from paste before weighing (from residue ratio)
        water_lost_before_weighing = round((1.0 - exp_residue / residue) * 100.0, 1) if residue > exp_residue else 0.0
        return {
            "is_silica": True,
            "silica_exp": silica,
            "water_exp": water, "water_meas": round(meas_water, 2),
            "org_exp": org, "vicinal_oh_exp": vicinal_oh,
            "step2_exp": step2_exp, "org_meas": round(meas_org, 2),
            "clay_oh_exp": clay_oh, "isolated_oh_exp": isolated_oh,
            "step3_exp": step3_exp, "clay_oh_meas": round(meas_clay, 2),
            "silanol_full_pct_of_silica": round(SILICA_OH_FULL_FRAC * 100.0, 2),
            "loss_dry_exp": exp_loss_total, "loss_meas": round(totals["total_loss"], 2),
            "residue_exp": exp_residue, "residue_meas": round(residue, 2),
            "water_lost_before_weighing": water_lost_before_weighing,
            "org_dry_exp": org_dry_exp, "org_dry_meas": org_dry_meas,
            "moisture_pct_of_solids": 0.0,
            "has_water": water > 0, "has_org": org > 0, "has_clay": clay > 0,
        }

    exp_loss_dry = round(water + org, 2)
    exp_residue = round(100.0 - exp_loss_dry, 2)
    moisture = (exp_residue - residue) / exp_residue * 100.0 if exp_residue > 0 else 0.0
    return {
        "is_silica": False,
        "water_exp": water, "water_meas": meas_water,
        "org_exp": org, "org_meas": meas_org,
        "clay_oh_exp": clay_oh, "clay_oh_meas": meas_clay,
        "loss_dry_exp": exp_loss_dry, "loss_meas": totals["total_loss"],
        "residue_exp": exp_residue, "residue_meas": residue,
        "moisture_pct_of_solids": moisture,
        "has_water": water > 0, "has_org": org > 0, "has_clay": clay > 0,
    }


def _interpretation(steps, comp, atm, th, silica_mode=False):
    oxid = atm.lower() in ("air", "o2", "oxygen")
    if silica_mode:
        rows = []
        for idx, s in enumerate(steps):
            c = s["cls"]
            t_range = (f"RT–{_fmt_t(s['t_end'])} °C" if s["t_start"] is None
                       else f"{_fmt_t(s['t_start'])}–{_fmt_t(s['t_end'])} °C")
            if c == "water":
                assign = "Free water of the paste + physisorbed water in the silica gel pores + interlayer water of bentonite"
                assign_b = "Free water of the paste + physisorbed water in silica pores and clay"
                short_box = "Free paste water + physisorbed\nwater of silica gel and bentonite"
                expected = f"Water added: {th['water_exp']:.2f}"
                comment = (f"Largest step: one broad DTG peak at {s['peak_t']:.0f} °C that ends sharply at ~175 °C, "
                           f"when the last liquid water leaves the 150 Å silica pores. Zhuravlev puts the end of "
                           f"physisorbed-water removal from silica at 190 ± 10 °C; smectite interlayer water also "
                           f"leaves below ~200 °C. After this step the dry paste is {s['m_end']:.2f} wt% of the loaded mass.")
                refs = [1, 2, 4]
                refs_b = [2, 4]
            elif c == "organic":
                assign = "Oxidative burn-off of methyl cellulose + condensation of vicinal (hydrogen-bonded) silanols"
                assign_b = "Burn-off of methyl cellulose [5, 6] + condensation of vicinal silanols [1, 2]"
                short_box = "Oxidative burn-off of methyl\ncellulose + silanol condensation"
                expected = f"{th['step2_exp']:.2f} = methyl cellulose {th['org_exp']:.2f} + vicinal-silanol water {th['vicinal_oh_exp']:.2f}"
                dry_b = s.get("loss_dry_basis") or 0.0
                comment = (f"Small DTG peak at {s['peak_t']:.0f} °C with a long tail to ~500 °C. In N2, methyl cellulose "
                           f"has T10 ≈ 292 °C and decomposes at ~343 °C; in air it oxidises at similar or lower "
                           f"temperature, which matches the peak. Vicinal silanols condense (2 Si–OH → Si–O–Si + H2O) "
                           f"mainly between 200 and 450 °C and are removed by ~400 °C; this water gives the long tail. "
                           f"Expressed on the dry paste, step II = {dry_b:.2f} %.")
                refs = [1, 2, 5, 6]
                refs_b = [1, 2, 5, 6]
            else:
                assign = "Dehydroxylation of bentonite + slow condensation of isolated silanols"
                assign_b = "Dehydroxylation of bentonite [4] + condensation of isolated silanols [1]"
                short_box = "Dehydroxylation of bentonite +\nisolated-silanol condensation"
                expected = f"{th['step3_exp']:.2f} = bentonite OH {th['clay_oh_exp']:.2f} + isolated-silanol water {th['isolated_oh_exp']:.2f}"
                dry_b = s.get("loss_dry_basis") or 0.0
                comment = (f"Very small loss with a weak DTG peak at {s['peak_t']:.0f} °C, typical of the "
                           f"dehydroxylation of montmorillonite (4.7–4.9 % of the clay mass). Isolated silanols "
                           f"condense slowly up to and beyond 900 °C, so the mass is still falling slightly at "
                           f"900 °C. Expressed on the dry paste, step III = {dry_b:.2f} %.")
                refs = [1, 4]
                refs_b = [1, 4]
            rows.append({
                "step": s["label"], "t_range": t_range, "peak_t": s["peak_t"], "weak": s["weak"],
                "loss": s["loss"], "assignment": assign, "assignment_b": assign_b,
                "short_box": short_box, "expected": expected,
                "comment": comment, "refs": refs, "refs_b": refs_b, "color": s["color"], "cls": c,
            })
        return rows

    zeo = _names(comp, ROLE_ZEOLITE, "zeolite")[0]
    zeo_short = "13X" if "13x" in zeo.lower() else zeo
    clay_names = _names(comp, ROLE_CLAY, "clay binder")
    org_names = _names(comp, ROLE_ORGANIC, "organic additives")
    org_first = org_names[0]
    clay_s = clay_names[0]
    clay_low = clay_s.lower() if clay_s.lower() in ("bentonite", "kaolin", "smectite", "clay") else clay_s
    org_low = [n.lower() if n.lower() == "methyl cellulose" else n for n in org_names]
    org_detail = " + ".join(f"{r['component']} {r['pct']:.2f}" for r in _role_rows(comp, ROLE_ORGANIC)) or "none"
    biggest = max(steps, key=lambda s: s["loss"]) if steps else None
    rows = []
    for s in steps:
        c = s["cls"]
        t_range = (f"RT–{_fmt_t(s['t_end'])} °C" if s["t_start"] is None
                   else f"{_fmt_t(s['t_start'])}–{_fmt_t(s['t_end'])} °C")
        if c == "water":
            assign = f"Free water of the paste + adsorbed water of {zeo_short}" + (f" and {clay_low}" if th["has_clay"] else "")
            short_box = f"Free paste water +\nadsorbed water ({zeo_short}" + (", clay)" if th["has_clay"] else ")")
            expected = f"Water added: {th['water_exp']:.2f}"
            comment = (("Largest step. " if s is biggest else "") +
                       f"Evaporation of the mixing water; physisorbed water of {zeo_short}" +
                       (f" and the interlayer water of {clay_low} (which ends below ~200 °C)" if th["has_clay"] else "") +
                       " leave in the same range.")
            refs = [4, 5] if th["has_clay"] else [4]
        elif c == "bound":
            verb = "oxidation" if oxid else "decomposition"
            assign = f"Strongly bound zeolite water + onset of {org_first} {verb}"
            short_box = f"Strongly bound zeolite water +\nonset of {org_first} {verb}"
            expected = "Overlapping; not separable"
            comment = (f"Small DTG peak. {zeo_short} keeps releasing bound water up to ~300 °C; {org_first} starts to "
                       f"lose mass near 200–230 °C in N2" + (" and earlier in air because it oxidises." if oxid else "."))
            refs = [1, 2, 4] if oxid else [1, 4]
        elif c == "organic":
            if oxid:
                assign = f"Oxidative burn-off of {_join_and(org_low)}"
                short_box = f"Oxidative burn-off of\n{_join_and(org_low)}"
                comment = ("Sharp DTG peak. In N2, PEG-400 loses mass between ~187 and ~397 °C and methyl "
                           "cellulose has T10 ≈ 292 °C and decomposes at ~343 °C; in air both burn earlier, "
                           "which explains the peak below 300 °C.")
                refs = [1, 2, 3, 6]
            else:
                assign = f"Thermal decomposition of {_join_and(org_low)}"
                short_box = f"Thermal decomposition of\n{_join_and(org_low)}"
                comment = ("PEG-400 loses mass between ~187 and ~397 °C in N2; methyl cellulose has T10 ≈ 292 °C "
                           "and decomposes at ~343 °C.")
                refs = [1, 3, 6]
            expected = f"Organics added: {th['org_exp']:.2f} ({org_detail})"
        else:
            assign = f"Dehydroxylation of {clay_low} (4.7–4.9 % of clay mass)"
            short_box = f"Dehydroxylation\nof {clay_low}"
            expected = f"{clay_s} OH (upper bound): {th['clay_oh_exp']:.2f}"
            comment = ("Very small, broad loss with a weak DTG shoulder. Smectite dehydroxylation occurs between "
                       "~300 and 900 °C with 4.7–4.9 % mass loss of the clay.")
            refs = [5]
        rows.append({
            "step": s["label"], "t_range": t_range, "peak_t": s["peak_t"], "weak": s["weak"],
            "loss": s["loss"], "assignment": assign, "short_box": short_box, "expected": expected,
            "comment": comment, "refs": refs, "color": s["color"], "cls": c,
        })
    return rows


def used_reference_ids(analysis):
    if analysis.get("is_silica"):
        return [1, 2, 3, 4, 5, 6]
    ids = set()
    for r in analysis["interpretation"]:
        ids.update(r["refs"])
    return sorted(ids)


# --------------------------------------------------------------------------- #
# Figures: Style A (Journal Vertical) & Style B (Presentation Landscape)
# --------------------------------------------------------------------------- #

FIG_SIZE_A = (8.0, 9.6)
FIG_SIZE_B = (12.0, 6.75)
FIG_SIZE = FIG_SIZE_B


def new_figure(size=FIG_SIZE_B):
    return Figure(figsize=size, dpi=100, facecolor="white")


def _line(fig, x0, x1, y, color="#222222", lw=0.8):
    fig.add_artist(Line2D([x0, x1], [y, y], transform=fig.transFigure, color=color, lw=lw))


def _limits_note(analysis):
    lims, kinds = analysis["limits"], analysis["limit_kinds"]
    if not lims:
        return "Single step (no DTG minima found)."
    mins = [_fmt_t(l) for l, k in zip(lims, kinds) if k == "min"]
    tails = [_fmt_t(l) for l, k in zip(lims, kinds) if k == "tail"]
    man = [_fmt_t(l) for l, k in zip(lims, kinds) if k == "manual"]
    parts = []
    if mins:
        parts.append("DTG minima (" + " and ".join(mins) + " °C)")
    if man:
        parts.append("manually set limits (" + ", ".join(man) + " °C)")
    s = "Step limits at " + " and ".join(parts) if parts else "Step limit"
    if tails:
        thr = analysis["conditions"].get("tail_threshold", 0.005)
        s += (" and at " if parts else " at ") + f"{tails[0]} °C (DTG < {thr:g} wt% °C⁻¹)"
    return s + "."


def _short_comp_label(name):
    low = name.lower()
    if "zeolite 13x" in low:
        return "13X"
    if "silica gel" in low:
        return "silica gel"
    if low in ("bentonite", "methyl cellulose", "water"):
        return low
    return name


def _draw_silica_dtg_inset(ax_parent, t, dtg_s, steps, bounds_rect, ink="#222222", red="#c0392b"):
    """Draws the zoom 180–900 °C inset on the DTG panel (in ×10⁻³ wt% °C⁻¹)."""
    ax_in = ax_parent.inset_axes(bounds_rect)
    ax_in.set_facecolor("white")
    x0, x1 = 180.0, 900.0
    for s in steps:
        lo = max(x0, x0 if s["t_start"] is None else s["t_start"])
        hi = min(x1, s["t_end"])
        if hi > lo:
            ax_in.axvspan(lo, hi, color=s["color"], alpha=0.11, lw=0, zorder=0)
    mask = (t >= x0) & (t <= x1)
    t_sub = t[mask]
    d_sub = dtg_s[mask] * 1000.0
    ax_in.fill_between(t_sub, 0, d_sub, color=red, alpha=0.14, lw=0, zorder=2)
    ax_in.plot(t_sub, d_sub, color=red, lw=1.4, zorder=4)
    ax_in.set_xlim(x0, x1)
    y_top = max(12.5, float(d_sub.max()) * 1.18 if len(d_sub) else 12.5)
    ax_in.set_ylim(0.0, y_top)
    if y_top <= 13.0:
        ax_in.set_yticks([0.0, 2.5, 5.0, 7.5, 10.0, 12.5])
    ax_in.set_ylabel("DTG (×10$^{-3}$ wt% °C$^{-1}$)", fontsize=7.6, color=ink)
    ax_in.set_title("zoom 180–900 °C", fontsize=8.0, color="#555555", pad=3.5)
    ax_in.tick_params(direction="in", which="both", top=True, right=True, left=True, bottom=True, labelsize=7.5, length=3.2)
    for sp in ax_in.spines.values():
        sp.set_linewidth(0.75)
        sp.set_color("#555555")
    # Annotate Step II & Step III peaks inside inset
    for s in steps[1:]:
        pt, ph = s["peak_t"], s["peak_h"] * 1000.0
        if x0 <= pt <= x1 and ph > 0:
            if s["cls"] == "organic":
                ax_in.annotate(f"{pt:.0f} °C", xy=(pt, ph), xytext=(pt + 55, min(y_top * 0.90, ph + 0.8)),
                               ha="left", va="center", fontsize=8.0, color=ink,
                               arrowprops=dict(arrowstyle="-", color="#666666", lw=0.65), zorder=8)
            else:
                ax_in.annotate(f"{pt:.0f} °C", xy=(pt, ph), xytext=(pt + 42, ph + 3.2),
                               ha="left", va="bottom", fontsize=8.0, color=ink,
                               arrowprops=dict(arrowstyle="-", color="#666666", lw=0.65), zorder=8)
    return ax_in


def _draw_silica_mass_inset(ax_parent, t, w, steps, bounds_rect, show_ylabel=False, ink="#222222", navy="#16365c"):
    """Draws the zoom 180–900 °C inset on the Mass panel."""
    ax_in = ax_parent.inset_axes(bounds_rect)
    ax_in.set_facecolor("white")
    x0, x1 = 180.0, 900.0
    for s in steps:
        lo = max(x0, x0 if s["t_start"] is None else s["t_start"])
        hi = min(x1, s["t_end"])
        if hi > lo:
            ax_in.axvspan(lo, hi, color=s["color"], alpha=0.11, lw=0, zorder=0)
    mask = (t >= x0) & (t <= x1)
    t_sub, w_sub = t[mask], w[mask]
    ax_in.plot(t_sub, w_sub, color=navy, lw=1.6, zorder=4)
    ax_in.set_xlim(x0, x1)
    y_lo = min(29.85, float(w_sub.min()) - 0.22 if len(w_sub) else 29.85)
    y_hi = max(32.20, float(w_sub.max()) + 0.35 if len(w_sub) else 32.20)
    ax_in.set_ylim(y_lo, y_hi)
    if show_ylabel:
        ax_in.set_ylabel("Mass (wt%)", fontsize=7.6, color=ink)
    ax_in.set_title("zoom 180–900 °C", fontsize=8.0, color="#555555", pad=3.5)
    ax_in.tick_params(direction="in", which="both", top=True, right=True, left=True, bottom=True, labelsize=7.5, length=3.2)
    for sp in ax_in.spines.values():
        sp.set_linewidth(0.75)
        sp.set_color("#555555")
    # Boundary markers (end of step I, end of step II, end of step III)
    pts = []
    for s in steps:
        pts.append((s["t_end"], s["m_end"]))
    for idx, (px, py) in enumerate(pts):
        ax_in.plot([px], [py], "o", ms=4.5, mfc="white", mec=navy, mew=1.2, zorder=7, clip_on=False)
        if idx == 0:
            ax_in.annotate(f"{py:.2f}", (px, py), xytext=(6, 4), textcoords="offset points",
                           fontsize=7.6, color=ink, ha="left", va="bottom", zorder=8)
        elif idx == 1:
            ax_in.annotate(f"{py:.2f}", (px, py), xytext=(-4, 6), textcoords="offset points",
                           fontsize=7.6, color=ink, ha="center", va="bottom", zorder=8)
        else:
            ax_in.annotate(f"{py:.2f}", (px, py), xytext=(-6, 5), textcoords="offset points",
                           fontsize=7.6, color=ink, ha="right", va="bottom", zorder=8)
    # Step II and Step III loss labels inside the inset
    if len(steps) >= 2:
        s2 = steps[1]
        ax_in.text(390, y_lo + 0.72 * (y_hi - y_lo), f"II: −{s2['loss']:.2f}",
                   color=s2["color"], fontsize=8.0, fontweight="bold", ha="center", va="center", zorder=8)
    if len(steps) >= 3:
        s3 = steps[2]
        ax_in.text(725, y_lo + 0.48 * (y_hi - y_lo), f"III: −{s3['loss']:.2f}",
                   color=s3["color"], fontsize=8.0, fontweight="bold", ha="center", va="center", zorder=8)
    return ax_in


def render_style_a_figure(fig, analysis, title="TGA / DTG", fig_title=None):
    """
    Draws Style A (Journal Vertical figure):
      - Top panel: DTG (wt% °C⁻¹) with Roman step headers and peak leader lines
      - Bottom panel: Mass (wt%) vs Temperature (°C) with rounded step callout boxes,
        total mass loss arrow, and residue annotation.
      - For Silica gel pastes: automatically includes the 180–900 °C zoom insets in both panels.
    """
    fig.clear()
    fig.set_size_inches(*FIG_SIZE_A)
    A = analysis
    silica_mode = bool(A.get("is_silica"))
    t, w, dtg_s = A["arrays"]["t"], A["arrays"]["w"], A["arrays"]["dtg_s"]
    steps, tot, comp, cond = A["steps"], A["totals"], A["composition"], A["conditions"]
    interp = A["interpretation"]
    atm = str(cond.get("atmosphere", "Air"))
    ink = "#222222"
    grey = "#666666"
    navy = "#16365c"
    red = "#c0392b"

    # ---- titles ----
    fig.text(0.125, 0.955, fig_title or f"TGA / DTG of {title}", fontsize=13.5, fontweight="bold", color=ink, va="center")
    comp_str = " | ".join(f"{_short_comp_label(r['component'])} {r['pct']:.2f}" for r in comp) + " wt%"
    if silica_mode:
        dry_line = dry_mix_summary_line(comp)
        sub_txt = comp_str + (f"\n{dry_line}" if dry_line else "")
        fig.text(0.125, 0.918, sub_txt, fontsize=8.9, color=grey, va="center", linespacing=1.28)
    else:
        fig.text(0.125, 0.925, comp_str, fontsize=9.2, color=grey, va="center")

    # ---- axes (Top = DTG, Bottom = Mass) ----
    top_y = 0.565 if silica_mode else 0.575
    top_h = 0.325 if silica_mode else 0.330
    ax_d = fig.add_axes([0.125, top_y, 0.825, top_h])
    ax_m = fig.add_axes([0.125, 0.105, 0.825, 0.440], sharex=ax_d)

    x_min = 20.0 if t[0] > 20 else float(np.floor(t[0] / 10) * 10)
    x_max = float(np.ceil(t[-1] / 100.0) * 100.0)
    if x_max - t[-1] > 60:
        x_max = float(np.ceil(t[-1] / 50.0) * 50.0)
    resid = tot["residue"]
    y_min = 22.0 if silica_mode else (max(0.0, np.floor((resid - 8) / 5.0) * 5.0) if resid > 8 else 0.0)
    y_max = max(105.0, tot["loaded_pct"] + 5.0)

    # Shaded step regions & boundary dashed lines
    for ax in (ax_d, ax_m):
        for s in steps:
            lo = x_min if s["t_start"] is None else s["t_start"]
            ax.axvspan(lo, s["t_end"], color=s["color"], alpha=0.10, lw=0, zorder=0)
        for s in steps[:-1]:
            ax.axvline(s["t_end"], color="#777777", ls=":" if silica_mode else "--", lw=0.85, alpha=0.85, zorder=2)

    # ---- Top panel: DTG ----
    ax_d.fill_between(t, 0, dtg_s, color=red, alpha=0.12, lw=0, zorder=2)
    ax_d.plot(t, dtg_s, color=red, lw=1.9, zorder=4)
    d_top = 1.0 if (silica_mode and float(dtg_s.max()) <= 0.92) else max(0.05, float(dtg_s.max()) * 1.22)
    ax_d.set_ylim(0, d_top)
    ax_d.set_xlim(x_min, x_max)
    ax_d.set_ylabel("DTG (wt% °C$^{-1}$)", fontsize=11)
    ax_d.tick_params(labelbottom=False)

    # Roman numerals at top of DTG panel
    for s in steps:
        lo = x_min if s["t_start"] is None else s["t_start"]
        xc = (max(lo, x_min) + s["t_end"]) / 2.0
        ax_d.text(xc, d_top * 0.945, s["label"], color=s["color"], fontsize=11.5, fontweight="bold",
                  ha="center", va="top", zorder=6)

    if silica_mode:
        # Main water peak annotation + inset zoom 180-900 °C
        if steps:
            pt0, ph0 = steps[0]["peak_t"], steps[0]["peak_h"]
            ax_d.annotate(f"{pt0:.0f} °C", xy=(pt0, ph0), xytext=(pt0 + 30, ph0),
                          ha="left", va="center", fontsize=9.2, color=ink,
                          arrowprops=dict(arrowstyle="-", color="#666666", lw=0.75), zorder=8)
        _draw_silica_dtg_inset(ax_d, t, dtg_s, steps, [0.31, 0.21, 0.66, 0.56], ink=ink, red=red)
    else:
        peaks = [(s["peak_t"], s["peak_h"], s["weak"]) for s in steps]
        for i, (pt, ph, weak) in enumerate(peaks):
            if ph <= 0:
                continue
            if weak:
                ax_d.annotate(f"weak shoulder\n~{pt:.0f} °C", xy=(pt, ph + 0.004 * d_top),
                              xytext=(pt, ph + 0.20 * d_top), ha="center", va="bottom",
                              fontsize=8.8, color=ink, linespacing=1.15,
                              arrowprops=dict(arrowstyle="-", color="#666666", lw=0.75), zorder=8)
            elif i == 0:
                ax_d.annotate(f"{pt:.0f} °C", xy=(pt, ph), xytext=(pt + 42, ph),
                              ha="left", va="center", fontsize=9.2, color=ink,
                              arrowprops=dict(arrowstyle="-", color="#666666", lw=0.75), zorder=8)
            elif i == 1:
                ax_d.annotate(f"{pt:.0f} °C", xy=(pt, ph), xytext=(pt - 24, ph + 0.25 * d_top),
                              ha="center", va="bottom", fontsize=9.2, color=ink,
                              arrowprops=dict(arrowstyle="-", color="#666666", lw=0.75), zorder=8)
            else:
                ax_d.annotate(f"{pt:.0f} °C", xy=(pt, ph), xytext=(pt + 45, ph + 0.09 * d_top),
                              ha="left", va="bottom", fontsize=9.2, color=ink,
                              arrowprops=dict(arrowstyle="-", color="#666666", lw=0.75), zorder=8)

    # ---- Bottom panel: Mass ----
    ax_m.plot(t, w, color=navy, lw=2.2, zorder=4)
    ax_m.set_xlim(x_min, x_max)
    ax_m.set_ylim(y_min, y_max)
    ax_m.axhline(tot["loaded_pct"], color="#777777", ls="--", lw=0.85, zorder=1)
    ax_m.axhline(resid, color="#777777", ls="--", lw=0.85, zorder=1)
    ax_m.set_ylabel("Mass (wt%)", fontsize=11)
    ax_m.set_xlabel("Temperature (°C)", fontsize=11)

    if silica_mode:
        # 3 vertical stacked callout boxes in center-left + mass inset on right
        box_ys = [98.5, 83.5, 68.5]
        bx = 200.0
        for idx, (r, s) in enumerate(zip(interp[:3], steps[:3])):
            by = box_ys[idx]
            loss_str = f"−{r['loss']:.1f} wt%" if r["loss"] >= 10.0 else f"−{r['loss']:.2f} wt%"
            txt = f"Step {r['step']}  ({r['t_range']})  {loss_str}\n{r['short_box']}"
            ax_m.text(
                bx, by, txt, fontsize=8.4, color=ink, va="top", ha="left", linespacing=1.22, zorder=9,
                bbox=dict(boxstyle="round,pad=0.38,rounding_size=0.18", fc="white", ec=s["color"], lw=1.35, alpha=0.95)
            )
        _draw_silica_mass_inset(ax_m, t, w, steps, [0.615, 0.45, 0.355, 0.375], show_ylabel=False, ink=ink, navy=navy)

        # Total mass loss arrow at x = 188 °C
        arr_x = 188.0
        ax_m.annotate("", xy=(arr_x, tot["loaded_pct"] - 0.3), xytext=(arr_x, resid + 0.3),
                      arrowprops=dict(arrowstyle="<->", color=red, lw=1.4, mutation_scale=10), zorder=7)
        ax_m.text(212.0, 45.0, f"Total mass loss\n{tot['total_loss']:.1f} wt%",
                  color=red, fontsize=10.5, fontweight="bold", ha="left", va="center", linespacing=1.18, zorder=8)
        ax_m.text(882.0, resid - 3.6, f"Residue at {t[-1]:.0f} °C = {resid:.1f} wt%",
                  color=navy, fontsize=10.5, fontweight="bold", ha="right", va="top", zorder=8)
    else:
        # Step callout boxes inside Mass panel (2x2 grid in upper-middle clear space)
        box_positions = [
            (x_min + 0.205 * (x_max - x_min), y_max - 0.08 * (y_max - y_min)),
            (x_min + 0.595 * (x_max - x_min), y_max - 0.08 * (y_max - y_min)),
            (x_min + 0.205 * (x_max - x_min), y_max - 0.30 * (y_max - y_min)),
            (x_min + 0.595 * (x_max - x_min), y_max - 0.30 * (y_max - y_min)),
        ]
        for idx, (r, s) in enumerate(zip(interp[:4], steps[:4])):
            bx, by = box_positions[idx]
            loss_str = f"−{r['loss']:.1f} wt%" if r["loss"] >= 1.0 else f"−{r['loss']:.2f} wt%"
            txt = f"Step {r['step']}  ({r['t_range']})\n{loss_str}\n{r['short_box']}"
            ax_m.text(
                bx, by, txt, fontsize=8.6, color=ink, va="top", ha="left", linespacing=1.25, zorder=9,
                bbox=dict(boxstyle="round,pad=0.42,rounding_size=0.2", fc="white", ec=s["color"], lw=1.35, alpha=0.94)
            )

        # Total mass loss arrow & text
        arr_x = x_min + 0.955 * (x_max - x_min)
        ax_m.annotate("", xy=(arr_x, tot["loaded_pct"] - 0.3), xytext=(arr_x, resid + 0.3),
                      arrowprops=dict(arrowstyle="<->", color=red, lw=1.5, mutation_scale=11), zorder=7)
        ax_m.text(arr_x - 0.015 * (x_max - x_min), resid + 0.36 * (tot["loaded_pct"] - resid),
                  f"Total mass loss\n{tot['total_loss']:.1f} wt%", color=red, fontsize=10.5, fontweight="bold",
                  ha="right", va="center", linespacing=1.18, zorder=8)
        ax_m.text(arr_x - 0.015 * (x_max - x_min), resid + 0.032 * (y_max - y_min),
                  f"Residue at {t[-1]:.0f} °C = {resid:.1f} wt%", color=navy, fontsize=10.5, fontweight="bold",
                  ha="right", va="bottom", zorder=8)

    # Style axes ticks & borders
    for ax in (ax_d, ax_m):
        ax.tick_params(direction="in", which="both", top=True, right=True, left=True, bottom=True,
                       labelsize=9.5, length=4.5)
        ax.xaxis.set_minor_locator(AutoMinorLocator(2))
        for sp in ax.spines.values():
            sp.set_linewidth(1.0)
            sp.set_color("#222222")

    # Footnote
    foot1 = f"{atm}"
    if cond.get("flow_ml_min"):
        foot1 += f", {float(cond['flow_ml_min']):g} mL/min"
    if cond.get("heating_rate"):
        foot1 += f", {float(cond['heating_rate']):g} °C/min"
    foot1 += f", {t[0]:.0f}→{t[-1]:.0f} °C. " + _limits_note(A)
    if tot["pre_loss"] > 0.05:
        foot2 = (f"Mass is relative to the sample loaded in the pan; {tot['pre_loss']:.1f} wt% water evaporated "
                 f"before the first data point.")
    else:
        foot2 = "Mass is relative to the sample loaded in the pan."
    fig.text(0.125, 0.034, foot1 + "\n" + foot2, fontsize=7.5, color=grey, va="center", linespacing=1.42)
    return fig


def render_style_b_figure(fig, analysis, title="TGA / DTG", fig_title=None):
    """
    Draws Style B (Presentation Landscape figure):
      - Left: Mass (top) + DTG (bottom) panels with step boundaries & labels
        (plus 180–900 °C zoom insets for Silica gel pastes)
      - Right: Mass-loss steps table, Expected from paste composition table, References list
    """
    fig.clear()
    fig.set_size_inches(*FIG_SIZE_B)
    A = analysis
    silica_mode = bool(A.get("is_silica"))
    refs_dict = get_references_for(A)
    t, w, dtg_s = A["arrays"]["t"], A["arrays"]["w"], A["arrays"]["dtg_s"]
    steps, tot, th, comp, cond = A["steps"], A["totals"], A["theory"], A["composition"], A["conditions"]
    atm = str(cond.get("atmosphere", "Air"))
    ink = "#222222"
    grey = "#666666"
    navy = "#16365c"
    red = "#c0392b"

    # ---- titles ----
    fig.text(0.052, 0.955, fig_title or f"TGA / DTG of {title}", fontsize=14, fontweight="bold", color=ink, va="center")
    comp_str = " | ".join(f"{_short_comp_label(r['component'])} {r['pct']:.2f}" for r in comp)
    cond_bits = [atm]
    if cond.get("flow_ml_min"):
        cond_bits.append(f"{float(cond['flow_ml_min']):g} mL/min")
    if cond.get("heating_rate"):
        cond_bits.append(f"{float(cond['heating_rate']):g} °C/min")
    dry_extra = f"  {dry_mix_summary_line(comp)}" if silica_mode else ""
    sub = f"Paste (wet basis): {comp_str} wt%{dry_extra}   •   {', '.join(cond_bits)}"
    fig.text(0.052, 0.915, sub, fontsize=8.3, color=grey, va="center")

    # ---- axes ----
    ax_m = fig.add_axes([0.058, 0.435, 0.484, 0.426])
    ax_d = fig.add_axes([0.058, 0.135, 0.484, 0.282], sharex=ax_m)
    x_min = 20.0 if (silica_mode and t[0] > 20) else (30.0 if t[0] > 30 else float(np.floor(t[0] / 10) * 10))
    x_max = float(np.ceil(t[-1] / 100.0) * 100.0)
    if x_max - t[-1] > 60:
        x_max = float(np.ceil(t[-1] / 50.0) * 50.0)
    resid = tot["residue"]
    y_min = 22.0 if silica_mode else (max(0.0, np.floor((resid - 8) / 5.0) * 5.0) if resid > 8 else 0.0)
    y_max = max(104.5, tot["loaded_pct"] + 4.5)

    # step regions + vertical lines
    for ax in (ax_m, ax_d):
        for s in steps:
            lo = x_min if s["t_start"] is None else s["t_start"]
            ax.axvspan(lo, s["t_end"], color=s["color"], alpha=0.10, lw=0, zorder=0)
        for s in steps[:-1]:
            ax.axvline(s["t_end"], color="#666666" if silica_mode else s["color"], ls=":", lw=0.9, alpha=0.9, zorder=1)

    # mass panel
    ax_m.plot(t, w, color=navy, lw=1.8, zorder=4)
    ax_m.set_xlim(x_min, x_max)
    ax_m.set_ylim(y_min, y_max)
    ax_m.axhline(tot["loaded_pct"], color="#999999", ls=(0, (2, 3)), lw=0.8, zorder=1)
    ax_m.axhline(resid, color="#999999", ls=(0, (2, 3)), lw=0.8, zorder=1)
    ax_m.set_ylabel("Mass (wt%)", fontsize=10)
    ax_m.tick_params(labelbottom=False)
    for s in steps:
        lo = x_min if s["t_start"] is None else s["t_start"]
        xc = (max(lo, x_min) + s["t_end"]) / 2.0
        ax_m.text(xc, y_max - 1.2, s["label"], color=s["color"], fontsize=10, fontweight="bold",
                  ha="center", va="top", zorder=6)

    if silica_mode:
        # Total mass loss arrow at x = 188 °C + zoom 180-900 °C inset
        arr_x = 188.0
        ax_m.annotate("", xy=(arr_x, tot["loaded_pct"] - 0.3), xytext=(arr_x, resid + 0.3),
                      arrowprops=dict(arrowstyle="<->", color=red, lw=1.25, mutation_scale=9), zorder=6)
        ax_m.text(212.0, 39.5, f"Total mass loss\n{tot['total_loss']:.1f} wt%",
                  color=red, fontsize=9.5, fontweight="bold", ha="left", va="center", linespacing=1.15, zorder=8)
        ax_m.text(880.0, resid - 3.6, f"Residue at {t[-1]:.0f} °C = {resid:.1f} wt%",
                  color=navy, fontsize=9.5, fontweight="bold", ha="right", va="top", zorder=8)
        _draw_silica_mass_inset(ax_m, t, w, steps, [0.45, 0.36, 0.52, 0.48], show_ylabel=True, ink=ink, navy=navy)
    else:
        for i, s in enumerate(steps[:-1]):
            xb, yb = s["t_end"], s["m_end"]
            ax_m.plot([xb], [yb], "o", ms=5.5, mfc="white", mec=navy, mew=1.3, zorder=7)
            ax_m.annotate(f"{yb:.1f}%", (xb, yb), xytext=(-5 if i % 2 == 0 else 5, -11 if i % 2 == 0 else 6),
                          textcoords="offset points", fontsize=7.5, color=ink,
                          ha="right" if i % 2 == 0 else "left", va="center", zorder=8)
        ax_m.plot([t[-1]], [w[-1]], "o", ms=5.5, mfc="white", mec=navy, mew=1.3, zorder=7, clip_on=False)

        arr_x = float(x_max - 0.11 * (x_max - x_min))
        ax_m.annotate("", xy=(arr_x, tot["loaded_pct"]), xytext=(arr_x, resid),
                      arrowprops=dict(arrowstyle="<->", color=red, lw=1.2, mutation_scale=9), zorder=6)
        ax_m.text(arr_x - 0.012 * (x_max - x_min), (tot["loaded_pct"] + resid) / 2 + 3,
                  f"Total mass loss\n{tot['total_loss']:.1f} wt%", color=red, fontsize=9.5, fontweight="bold",
                  ha="right", va="center", linespacing=1.15, zorder=8)
        ax_m.text(arr_x - 0.012 * (x_max - x_min), resid + 5.5,
                  f"Residue at {t[-1]:.0f} °C\n{resid:.1f} wt%", color=navy, fontsize=9.5, fontweight="bold",
                  ha="right", va="center", linespacing=1.15, zorder=8)

    # DTG panel
    ax_d.fill_between(t, 0, dtg_s, color=red, alpha=0.12, lw=0, zorder=2)
    ax_d.plot(t, dtg_s, color=red, lw=1.5, zorder=4)
    d_top = 1.0 if (silica_mode and float(dtg_s.max()) <= 0.92) else max(0.05, float(dtg_s.max()) * 1.2)
    ax_d.set_ylim(0, d_top)
    ax_d.set_xlim(x_min, x_max)
    ax_d.set_ylabel("DTG (wt% °C$^{-1}$)", fontsize=10)
    ax_d.set_xlabel("Temperature (°C)", fontsize=10)

    if silica_mode:
        if steps:
            pt0, ph0 = steps[0]["peak_t"], steps[0]["peak_h"]
            ax_d.annotate(f"{pt0:.0f} °C", (pt0, ph0), xytext=(14, -2),
                          textcoords="offset points", fontsize=8.2, color=ink, ha="left", va="center", zorder=8)
        _draw_silica_dtg_inset(ax_d, t, dtg_s, steps, [0.395, 0.21, 0.575, 0.64], ink=ink, red=red)
    else:
        peaks = [(s["peak_t"], s["peak_h"], s["weak"]) for s in steps]
        for i, (pt, ph, weak) in enumerate(peaks):
            if ph <= 0:
                continue
            left_tall = any(o[1] > ph and 0 < pt - o[0] < 90 for j, o in enumerate(peaks) if j != i)
            right_tall = any(o[1] > ph and 0 < o[0] - pt < 90 for j, o in enumerate(peaks) if j != i)
            lab = (f"~{pt:.0f} °C" if weak else f"{pt:.0f} °C")
            kw = dict(textcoords="offset points", fontsize=7.6, color=ink, zorder=8)
            if weak:
                ax_d.annotate(lab, (pt, ph), xytext=(0, 14), ha="center", va="bottom",
                              arrowprops=dict(arrowstyle="-", color="#bbbbbb", lw=0.5), **kw)
            elif left_tall and right_tall:
                ax_d.annotate(lab, (pt, ph), xytext=(-14, 28), ha="center", va="bottom",
                              arrowprops=dict(arrowstyle="-", color="#777777", lw=0.6), **kw)
            elif left_tall:
                ax_d.annotate(lab, (pt, ph), xytext=(8, 4), ha="left", va="bottom", **kw)
            elif right_tall:
                ax_d.annotate(lab, (pt, ph), xytext=(-8, 4), ha="right", va="bottom", **kw)
            else:
                ax_d.annotate(lab, (pt, ph), xytext=(8, 2), ha="left", va="bottom", **kw)

    for ax in (ax_m, ax_d):
        ax.tick_params(direction="in", which="both", top=True, right=True, left=True, bottom=True, labelsize=8.5)
        ax.xaxis.set_minor_locator(AutoMinorLocator(2))
        for sp in ax.spines.values():
            sp.set_linewidth(0.9)
            sp.set_color("#333333")

    # footnote
    foot = [f"{atm}"]
    if cond.get("flow_ml_min"):
        foot[0] += f", {float(cond['flow_ml_min']):g} mL/min"
    if cond.get("heating_rate"):
        foot[0] += f", {float(cond['heating_rate']):g} °C/min"
    foot[0] += f", {t[0]:.0f}→{t[-1]:.0f} °C. " + _limits_note(A)
    if tot["pre_loss"] > 0.05:
        foot.append(f"Mass is relative to the sample loaded in the pan; {tot['pre_loss']:.1f} wt% water evaporated "
                    f"before the first data point.")
    else:
        foot.append("Mass is relative to the sample loaded in the pan.")
    wrapped = []
    for f_ in foot:
        wrapped.extend(textwrap.wrap(f_, 150))
    fig.text(0.052, 0.036, "\n".join(wrapped), fontsize=6.9, color=grey, va="center", linespacing=1.45)

    # ---------------- right column ----------------
    X0 = 0.588
    X_T, X_L, X_A = X0 + 0.037, X0 + 0.113, X0 + 0.180
    XR = 0.985
    y = 0.864
    fig.text(X0, y, "Mass-loss steps", fontsize=11.5, fontweight="bold", color=ink, va="center")
    y -= 0.050
    for x, s_ in ((X0, "Step"), (X_T, "T range"), (X_L, "Loss (wt%)"), (X_A, "Assignment")):
        fig.text(x, y, s_, fontsize=7.8, fontweight="bold", color=ink, va="center")
    _line(fig, X0, XR, y - 0.016, lw=0.9)
    y -= 0.044

    n_steps = len(steps)
    interp = A["interpretation"]
    min_row = 0.067 if n_steps <= 4 else max(0.040, 0.27 / n_steps)
    for r, s in zip(interp, steps):
        if silica_mode and r.get("assignment_b"):
            txt = r["assignment_b"] if "[" in r["assignment_b"] else (
                r["assignment_b"] + " [" + ", ".join(str(x) for x in r.get("refs_b", r["refs"])) + "]"
            )
        else:
            txt = r["assignment"] + " [" + ", ".join(str(x) for x in r["refs"]) + "]"
        lines = textwrap.wrap(txt, 44)
        row_h = max(min_row, 0.0175 * len(lines) + 0.02)
        top = y
        fig.add_artist(FancyBboxPatch((X0, top - 0.020), 0.021, 0.038, boxstyle="round,pad=0,rounding_size=0.002",
                                      transform=fig.transFigure, fc=s["color"], ec="none"))
        fig.text(X0 + 0.0105, top - 0.001, r["step"], fontsize=7.8, fontweight="bold", color="white",
                 ha="center", va="center")
        fig.text(X_T, top + 0.004, r["t_range"], fontsize=7.6, color=ink, va="center")
        loss_fmt = f"{r['loss']:.1f}" if r["loss"] >= 10.0 else (f"{r['loss']:.1f}" if (not silica_mode and r["loss"] >= 1.0) else f"{r['loss']:.2f}")
        fig.text(X_L, top + 0.004, loss_fmt, fontsize=8.6,
                 fontweight="bold", color=s["color"], va="center")
        fig.text(X_A, top + 0.010, "\n".join(lines), fontsize=7.1, color=ink, va="top", linespacing=1.35,
                 transform=fig.transFigure)
        y -= row_h
    _line(fig, X0, XR, y + 0.020, lw=0.9)
    y -= 0.002
    fig.text(X0, y, "Total", fontsize=8.2, fontweight="bold", color=ink, va="center")
    fig.text(X_L, y, f"{tot['total_loss']:.1f}", fontsize=8.6, fontweight="bold", color=red, va="center")
    if silica_mode:
        res_txt = f"Residue {tot['residue']:.1f} wt%: partly dehydroxylated\nsilica + dehydroxylated bentonite"
    else:
        zeo = _short_comp_label(_names(comp, ROLE_ZEOLITE, "zeolite")[0])
        clay_s = _short_comp_label(_names(comp, ROLE_CLAY, "clay")[0])
        res_txt = f"Residue {tot['residue']:.1f} wt%: dehydrated {zeo}" + (f" +\ndehydroxylated {clay_s}" if th["has_clay"] else "")
    fig.text(X_A, y + 0.008, res_txt, fontsize=7.1, color=ink, va="top", linespacing=1.35)
    y -= 0.062

    # expected from composition
    fig.text(X0, y, "Expected from the paste composition", fontsize=11.0, fontweight="bold", color=ink, va="center")
    y -= 0.040
    XE1, XE2 = X0 + 0.198, X0 + 0.285
    col1_hdr = "Step / item" if silica_mode else "Component"
    col2_hdr = "Expected (wt%)" if silica_mode else "Added (wt%)"
    for x, s_ in ((X0, col1_hdr), (XE1, col2_hdr), (XE2, "Measured (wt%)")):
        fig.text(x, y, s_, fontsize=7.8, fontweight="bold", color=ink, va="center")
    _line(fig, X0, XR, y - 0.014, lw=0.9)
    y -= 0.030

    if silica_mode:
        rows = [
            ("I   Water", f"{th['water_exp']:.2f}", f"{th['water_meas']:.2f}"),
            ("II  Methyl cellulose + vicinal OH", f"{th['org_exp']:.2f} + {th['vicinal_oh_exp']:.2f}", f"{th['org_meas']:.2f}"),
            ("III Bentonite OH + isolated OH", f"{th['clay_oh_exp']:.2f} + {th['isolated_oh_exp']:.2f}", f"{th['clay_oh_meas']:.2f}"),
            ("Residue at 900 °C", f"{th['residue_exp']:.2f}", f"{th['residue_meas']:.2f}"),
        ]
        for lab, a, b in rows:
            fig.text(X0, y, lab, fontsize=7.3, color=ink, va="center")
            fig.text(XE1, y, a, fontsize=7.4, color=ink, va="center", ha="left")
            fig.text(XE2, y, b, fontsize=7.4, color=ink, va="center", ha="left")
            y -= 0.026
        w_diff = abs(th["water_exp"] - th["water_meas"])
        r_diff = abs(th["residue_meas"] - th["residue_exp"])
        note = (f"Steps II and III match the methyl cellulose + OH water. Step I is {w_diff:.1f} wt% lower and the "
                f"residue {r_diff:.1f} wt% higher than expected: ≈2 wt% of the paste (water) evaporated "
                f"between mixing and weighing the TGA sample. OH water from Zhuravlev model [1].")
    else:
        zeo = _short_comp_label(_names(comp, ROLE_ZEOLITE, "zeolite")[0])
        clay_s = _short_comp_label(_names(comp, ROLE_CLAY, "clay")[0])
        org_label = " + ".join(_short_comp_label(n) for n in _names(comp, ROLE_ORGANIC, "organics"))
        rows = []
        if th["has_water"]:
            rows.append(("Water", f"{th['water_exp']:.2f}", f"{th['water_meas']:.1f} (step I)"))
        if th["has_org"]:
            rows.append((org_label, f"{th['org_exp']:.2f}", f"{th['org_meas']:.1f} (steps II + III)"))
        if th["has_clay"]:
            rows.append((f"{clay_s.capitalize()} OH (upper bound)", f"{th['clay_oh_exp']:.2f}", f"{th['clay_oh_meas']:.2f} (step IV)"))
        rows.append((f"Solids ({zeo}" + (f" + {clay_s}" if th["has_clay"] else "") + ", if dry)",
                     f"{th['residue_exp']:.2f}", f"{th['residue_meas']:.1f} (residue)"))
        for lab, a, b in rows:
            fig.text(X0, y, lab if len(lab) < 52 else lab[:50] + "…", fontsize=7.3, color=ink, va="center")
            fig.text(XE1, y, a, fontsize=7.4, color=ink, va="center", ha="left")
            fig.text(XE2, y, b, fontsize=7.4, color=ink, va="center", ha="left")
            y -= 0.026
        diff = th["residue_exp"] - th["residue_meas"]
        in_steps = [s["label"] for s in steps if s["cls"] != "clay"]
        rng = (in_steps[0] + "–" + in_steps[-1]) if len(in_steps) > 1 else (in_steps[0] if in_steps else "")
        if diff > 0.3 and th["has_clay"]:
            note = (f"The residue is {diff:.1f} wt% lower than the dry-solids value because the {zeo} and {clay_s} "
                    f"were weighed with their own moisture (≈{th['moisture_pct_of_solids']:.0f} % of the solids). "
                    f"This water leaves in steps {rng}, so these steps exceed the added water and organics.")
        elif diff < -0.3:
            note = (f"The residue is {abs(diff):.1f} wt% higher than the dry-solids value; check the weighed "
                    f"composition or whether some organics/water were not fully removed.")
        else:
            note = "The residue agrees with the dry-solids value of the composition."

    y -= 0.004
    nl = textwrap.wrap(note, 78)
    fig.text(X0, y, "\n".join(nl), fontsize=6.7, style="italic", color=grey, va="top", linespacing=1.4)
    y -= 0.0165 * len(nl) + 0.032

    # references
    fig.text(X0, y, "References", fontsize=10.5, fontweight="bold", color=ink, va="center")
    y -= 0.028
    for rid in used_reference_ids(A):
        if rid in refs_dict:
            fig.text(X0, y, f"[{rid}] {refs_dict[rid]['short']}", fontsize=5.6, color=grey, va="center")
            y -= 0.0235
    return fig


def render_report_figure(fig, analysis, title="TGA / DTG", fig_title=None, style=STYLE_B):
    """Dispatches to Style A (journal vertical) or Style B (presentation landscape)."""
    if style == STYLE_A:
        return render_style_a_figure(fig, analysis, title=title, fig_title=fig_title)
    return render_style_b_figure(fig, analysis, title=title, fig_title=fig_title)


def figure_to_png_bytes(analysis, title, dpi=200, fig_title=None, style=STYLE_B):
    if style == STYLE_BOTH:
        from PIL import Image
        b_a = figure_to_png_bytes(analysis, title, dpi=dpi, fig_title=fig_title, style=STYLE_A)
        b_b = figure_to_png_bytes(analysis, title, dpi=dpi, fig_title=fig_title, style=STYLE_B)
        im_a = Image.open(io.BytesIO(b_a)).convert("RGB")
        im_b = Image.open(io.BytesIO(b_b)).convert("RGB")
        target_h = max(im_a.height, im_b.height)
        im_a_r = im_a.resize((int(im_a.width * target_h / im_a.height), target_h), Image.LANCZOS)
        im_b_r = im_b.resize((int(im_b.width * target_h / im_b.height), target_h), Image.LANCZOS)
        gap = 24
        comb = Image.new("RGB", (im_b_r.width + gap + im_a_r.width, target_h), (245, 247, 250))
        comb.paste(im_b_r, (0, 0))
        comb.paste(im_a_r, (im_b_r.width + gap, 0))
        out = io.BytesIO()
        comb.save(out, format="PNG")
        return out.getvalue()

    size = FIG_SIZE_A if style == STYLE_A else FIG_SIZE_B
    fig = new_figure(size=size)
    render_report_figure(fig, analysis, title=title, fig_title=fig_title, style=style)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, facecolor="white")
    return buf.getvalue()


def export_figure(analysis, title, path, dpi=600, fig_title=None, style=STYLE_B):
    """Exports the figure in Style A or Style B; the format follows the extension (png/pdf/svg/tif)."""
    size = FIG_SIZE_A if style == STYLE_A else FIG_SIZE_B
    fig = new_figure(size=size)
    render_report_figure(fig, analysis, title=title, fig_title=fig_title, style=style)
    ext = os.path.splitext(path)[1].lower()
    kw = dict(facecolor="white")
    if ext in (".png", ".tif", ".tiff", ".jpg", ".jpeg"):
        kw["dpi"] = dpi
    fig.savefig(path, **kw)
    return path


# --------------------------------------------------------------------------- #
# Combined Master Excel Workbook (All 8 sheets in ONE Excel file)
# --------------------------------------------------------------------------- #

def _info_rows(analysis, meta):
    A = analysis
    silica_mode = bool(A.get("is_silica"))
    tot, cond = A["totals"], A["conditions"]
    first_note = (f"{tot['first_weight']:.2f} wt% at {tot['t_first']:.1f} °C, i.e. {tot['pre_loss']:.2f} wt% water "
                  f"evaporated before recording started")
    lim = " and ".join(f"{l:.1f} °C" for l in A["limits"]) if len(A["limits"]) <= 2 else ", ".join(f"{l:.1f}" for l in A["limits"]) + " °C"
    hr_fit = tot.get("heating_rate_fit")
    rows = [
        ("Sample", meta.get("sample_title", "")),
        ("Sample ID (vault)", meta.get("sample_id", "")),
        ("Operator", meta.get("operator", "")),
        ("Date", meta.get("date", "")),
        ("Raw data file", meta.get("raw_file", "")),
        ("Analysis", "Thermogravimetric analysis (TGA) with derivative curve (DTG)"),
        ("Atmosphere", f"{cond.get('atmosphere', '')} ({'oxidative' if str(cond.get('atmosphere', '')).lower() in ('air', 'o2') else 'inert'})"),
        ("Gas flow rate", f"{float(cond['flow_ml_min']):g} mL/min" if cond.get("flow_ml_min") else "not given"),
        ("Heating rate (set)", f"{float(cond['heating_rate']):g} °C/min" if cond.get("heating_rate") else "not given"),
    ]
    if hr_fit:
        rows.append(("Heating rate (fitted from data, 100–800 °C)", f"{hr_fit:.2f} °C/min"))
    rows += [
        ("Temperature range", f"{tot['t_first']:.1f} → {tot['t_last']:.1f} °C"),
        ("Run time", f"{tot['run_time_min']:.1f} min" if tot.get("run_time_min") else "not given"),
        ("Number of data points", str(tot["n_points"])),
        ("Sample mass (mg)", f"{cond['sample_mass_mg']:g}" if cond.get("sample_mass_mg") else "Not given in the export – fill in"),
        ("Mass basis", f"wt% relative to the mass loaded in the pan ({tot['loaded_pct']:g} %)"),
        ("First data point", first_note),
        ("Step limits", f"DTG minima at {lim}" if all(k == "min" for k in A["limit_kinds"]) else f"DTG minima at {lim}  [{', '.join(A['limit_kinds'])}]"),
        ("Total mass loss (from 100 %)", f"{tot['total_loss']:.2f} wt%"),
        ("Mass loss in the recorded part only", f"{tot['recorded_loss']:.2f} wt%"),
        (f"Residue at {tot['t_last']:.0f} °C", f"{tot['residue']:.2f} wt%"),
    ]
    if silica_mode and A["steps"]:
        rows.append(("Mass after drying (end of step I)",
                     f"{A['steps'][0]['m_end']:.2f} wt% = dry paste (silica + bentonite + methyl cellulose + surface OH)"))
        rows.append(("Note on DTG near 720 °C",
                     "Small step in the DTG trace at ~720 °C (< 0.0002 wt%/°C) is an instrument artefact, not a reaction"))
    rows += [
        ("Figures", "Style A (Journal Vertical) & Style B (Presentation Landscape) – 1200 DPI"),
        ("Generated", datetime.datetime.now().strftime("%Y-%m-%d %H:%M")),
        ("Generated by", "Lab Vault – TGA Report Engine"),
    ]
    return rows


def _steps_df(A):
    silica_mode = bool(A.get("is_silica"))
    rows = []
    for s in A["steps"]:
        row = {
            "Step": s["label"],
            "T start (°C)": "RT (loading)" if s["t_start"] is None else round(s["t_start"], 1),
            "T end (°C)": round(s["t_end"], 1),
            "DTG peak (°C)": round(s["peak_t"], 1) if s["peak_t"] < 500 else round(s["peak_t"]),
            "DTG peak height (wt%/°C)": round(s["peak_h"], 3) if s["peak_h"] >= 0.1 else round(s["peak_h"], 4),
            "Mass at start (wt%)": round(s["m_start"], 2),
            "Mass at end (wt%)": round(s["m_end"], 2),
            "Mass loss (wt%)": round(s["loss"], 2),
        }
        if silica_mode:
            row["Mass loss on dry-paste basis (% of mass at end of step I)"] = s.get("loss_dry_basis")
        rows.append(row)
    tot = A["totals"]
    tot_row = {
        "Step": "Total",
        "T start (°C)": "RT (loading)",
        "T end (°C)": round(tot["t_last"], 1),
        "DTG peak (°C)": None if silica_mode else round(tot["peak_t_main"], 1),
        "DTG peak height (wt%/°C)": None if silica_mode else round(tot["peak_h_main"], 3),
        "Mass at start (wt%)": tot["loaded_pct"],
        "Mass at end (wt%)": round(tot["residue"], 2),
        "Mass loss (wt%)": round(tot["total_loss"], 2),
    }
    if silica_mode:
        tot_row["Mass loss on dry-paste basis (% of mass at end of step I)"] = None
    rows.append(tot_row)
    return pd.DataFrame(rows)


def _interpretation_df(A):
    return pd.DataFrame([{
        "Step": r["step"],
        "T range": r["t_range"],
        "DTG peak (°C)": round(r["peak_t"]),
        "Measured loss (wt%)": round(r["loss"], 2),
        "Assignment": r["assignment"],
        "Expected from composition (wt%)": r["expected"],
        "Comment": r["comment"],
        "References": ", ".join(f"[{x}]" for x in r["refs"]),
    } for r in A["interpretation"]])


def _theory_vs_measured_df(A):
    th = A["theory"]
    if A.get("is_silica"):
        return pd.DataFrame([
            {"Item": "Step I: water",
             "Expected from composition (wt%)": round(th["water_exp"], 2),
             "Measured (wt%)": round(th["water_meas"], 2),
             "Note": f"Measured includes the {A['totals']['pre_loss']:.1f} wt% that left before the first data point (mass is from 100 %)."},
            {"Item": "Step II: methyl cellulose",
             "Expected from composition (wt%)": round(th["org_exp"], 2),
             "Measured (wt%)": None,
             "Note": f"{th['org_dry_exp']:g} % of the dry mix."},
            {"Item": "Step II: vicinal-silanol water (OH 4.6 → ~1.7 nm⁻², [1])",
             "Expected from composition (wt%)": round(th["vicinal_oh_exp"], 2),
             "Measured (wt%)": None,
             "Note": ""},
            {"Item": "Step II total",
             "Expected from composition (wt%)": round(th["step2_exp"], 2),
             "Measured (wt%)": round(th["org_meas"], 2),
             "Note": "Good agreement."},
            {"Item": "Step III: bentonite OH (4.8 % of clay, [4])",
             "Expected from composition (wt%)": round(th["clay_oh_exp"], 2),
             "Measured (wt%)": None,
             "Note": "Upper bound."},
            {"Item": "Step III: isolated-silanol water (OH ~1.7 → ~0.7 nm⁻², [1])",
             "Expected from composition (wt%)": round(th["isolated_oh_exp"], 2),
             "Measured (wt%)": None,
             "Note": ""},
            {"Item": "Step III total",
             "Expected from composition (wt%)": round(th["step3_exp"], 2),
             "Measured (wt%)": round(th["clay_oh_meas"], 2),
             "Note": "Good agreement."},
            {"Item": "Silanol water of silica gel (full condensation, % of silica mass)",
             "Expected from composition (wt%)": round(th["silanol_full_pct_of_silica"], 2),
             "Measured (wt%)": None,
             "Note": "From 4.6 OH/nm² [1] × 300 m²/g: upper bound. At 900 °C about 0.5–1 OH/nm² remain on silica [1], so only ~80 % of this leaves in the run."},
            {"Item": "Total mass loss",
             "Expected from composition (wt%)": round(th["loss_dry_exp"], 2),
             "Measured (wt%)": round(th["loss_meas"], 2),
             "Note": ""},
            {"Item": "Residue at 900 °C (silica + bentonite minus their lost OH)",
             "Expected from composition (wt%)": round(th["residue_exp"], 2),
             "Measured (wt%)": round(th["residue_meas"], 2),
             "Note": "The residue is slightly higher and step I slightly lower than expected."},
            {"Item": "Water lost from the paste before weighing (wt% of paste)",
             "Expected from composition (wt%)": None,
             "Measured (wt%)": round(th["water_lost_before_weighing"], 1),
             "Note": ""},
            {"Item": "Methyl cellulose on dry-paste basis",
             "Expected from composition (wt%)": round(th["org_dry_exp"], 2),
             "Measured (wt%)": round(th["org_dry_meas"], 2),
             "Note": "Step II as % of the mass at the end of step I; the extra is mainly vicinal-silanol water."},
        ])

    return pd.DataFrame([
        {"Item": "Water", "Expected from composition (wt%)": round(th["water_exp"], 2),
         "Measured (wt%)": round(th["water_meas"], 2),
         "Note": "Step I is larger than the added water because the 13X and bentonite moisture also leaves here."},
        {"Item": " + ".join(_names(A["composition"], ROLE_ORGANIC, "Organics")),
         "Expected from composition (wt%)": round(th["org_exp"], 2), "Measured (wt%)": round(th["org_meas"], 2),
         "Note": "Steps II + III also contain strongly bound zeolite water."},
        {"Item": f"Bentonite OH ({_role_pct(A['composition'], ROLE_CLAY):.2f} × {CLAY_OH_FRACTION * 100:.1f} %, upper bound)" if th["has_clay"] else "Clay OH (upper bound)",
         "Expected from composition (wt%)": round(th["clay_oh_exp"], 2),
         "Measured (wt%)": round(th["clay_oh_meas"], 2), "Note": "Step IV."},
        {"Item": "Total mass loss (if 13X and bentonite were dry)", "Expected from composition (wt%)": round(th["loss_dry_exp"], 2),
         "Measured (wt%)": round(th["loss_meas"], 2), "Note": ""},
        {"Item": "Residue (if 13X and bentonite were dry)", "Expected from composition (wt%)": round(th["residue_exp"], 2),
         "Measured (wt%)": round(th["residue_meas"], 2),
         "Note": "The measured residue is lower because the raw 13X and bentonite contained moisture when weighed."},
        {"Item": "Moisture in 13X + bentonite as weighed (% of solids)", "Expected from composition (wt%)": "",
         "Measured (wt%)": round(th["moisture_pct_of_solids"], 1),
         "Note": "Estimate from the residue. If the paste dried before loading, the true value is higher. A TGA of the raw 13X powder would confirm it."},
    ])


def _references_df(analysis=None):
    refs = get_references_for(analysis) if analysis is not None else REFERENCES_ZEOLITE
    return pd.DataFrame([{
        "No.": f"[{k}]", "Used for": v["used"], "Reference": v["full"], "DOI": v["doi"],
        "Link": "https://doi.org/" + v["doi"]} for k, v in refs.items()])


def _step_label_for_t(A, tval):
    for s in A["steps"]:
        if tval <= s["t_end"] + 1e-9:
            return s["label"]
    return A["steps"][-1]["label"]


def _style_sheet(ws, widths=None, wrap_body=False):
    from openpyxl.styles import Font, PatternFill, Alignment
    fill = PatternFill("solid", fgColor="1D3557")
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = fill
        c.alignment = Alignment(wrap_text=True, vertical="center")
    ws.freeze_panes = "A2"
    if wrap_body:
        for row in ws.iter_rows(min_row=2):
            for c in row:
                c.alignment = Alignment(wrap_text=True, vertical="top")
    for i, col in enumerate(ws.columns, start=1):
        letter = col[0].column_letter
        if widths and i - 1 < len(widths):
            ws.column_dimensions[letter].width = widths[i - 1]
        else:
            m = max((len(str(c.value)) for c in list(col)[:200] if c.value is not None), default=8)
            ws.column_dimensions[letter].width = min(65, max(12, m + 3))


def write_combined_excel(path, analysis, raw_df, meta):
    """
    Writes ONE complete, combined Excel workbook containing all 8 sheets:
      1. Info (Measuring conditions & summary)
      2. Paste composition
      3. Steps
      4. Interpretation
      5. Theory vs measured
      6. References
      7. Processed data
      8. Raw data (as exported)
    """
    A = analysis
    silica_mode = bool(A.get("is_silica"))
    comp = A["composition"]
    total_m = composition_total(comp)
    if silica_mode:
        comp_df = pd.DataFrame([{
            "No.": i + 1, "Component": r["component"], "Mass (g)": round(r["mass_g"], 4),
            "wt% of dry mix": r.get("dry_pct"), "wt% (wet basis, paste)": round(r["pct"], 2),
            "Note": r["note"]} for i, r in enumerate(comp)])
        comp_df.loc[len(comp_df)] = [None, "Total", round(total_m, 4), 100, 100.0, ""]
    else:
        comp_df = pd.DataFrame([{
            "No.": i + 1, "Component": r["component"], "Mass (g)": round(r["mass_g"], 4),
            "wt% (wet basis)": round(r["pct"], 2), "Role": r["role"], "Note": r["note"]} for i, r in enumerate(comp)])
        comp_df.loc[len(comp_df)] = ["Total", "", round(total_m, 4), 100.0, "", ""]

    d = A["df"]
    proc = pd.DataFrame({
        "Time (min)": d["time"].values if "time" in d.columns else np.nan,
        "Temperature (°C)": d["temperature"].values,
        "Mass (wt%)": d["weight"].values,
        "DTG (wt%/°C)": d["deriv_weight"].values,
        "Cumulative mass loss from 100 % (wt%)": np.round(A["totals"]["loaded_pct"] - d["weight"].values, 3),
        "Step": [_step_label_for_t(A, v) for v in d["temperature"].values],
    })
    raw_out = pd.DataFrame({
        "Time": d["time"].values if "time" in d.columns else np.nan,
        "Temperature": d["temperature"].values,
        "Weight": d["weight"].values,
        "Deriv. Weight": d["deriv_weight"].values,
    })
    info_df = pd.DataFrame(_info_rows(A, meta), columns=["Field", "Value"])
    steps_df = _steps_df(A)
    interp_df = _interpretation_df(A)
    tv_df = _theory_vs_measured_df(A)
    refs_df = _references_df(A)

    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        info_df.to_excel(xw, sheet_name="Info", index=False)
        comp_df.to_excel(xw, sheet_name="Paste composition", index=False)
        steps_df.to_excel(xw, sheet_name="Steps", index=False)
        interp_df.to_excel(xw, sheet_name="Interpretation", index=False)
        tv_df.to_excel(xw, sheet_name="Theory vs measured", index=False)
        refs_df.to_excel(xw, sheet_name="References", index=False)
        proc.to_excel(xw, sheet_name="Processed data", index=False)
        raw_out.to_excel(xw, sheet_name="Raw data (as exported)", index=False)

        _style_sheet(xw.book["Info"], [44, 92], wrap_body=True)
        _style_sheet(xw.book["Paste composition"], [8, 22, 14, 18, 22, 48], wrap_body=True)
        _style_sheet(xw.book["Steps"], [10, 16, 14, 16, 22, 18, 18, 16, 36], wrap_body=True)
        _style_sheet(xw.book["Interpretation"], [8, 14, 14, 18, 46, 36, 84, 16], wrap_body=True)
        _style_sheet(xw.book["Theory vs measured"], [52, 28, 18, 82], wrap_body=True)
        _style_sheet(xw.book["References"], [8, 60, 92, 28, 44], wrap_body=True)
        _style_sheet(xw.book["Processed data"])
        _style_sheet(xw.book["Raw data (as exported)"])
    return path


# Keep aliases for backwards compatibility if called elsewhere
write_data_record_xlsx = write_combined_excel


# --------------------------------------------------------------------------- #
# Complete Multi-Page PDF Report
# --------------------------------------------------------------------------- #

def _draw_pdf_table(fig, x0, y_top, col_xs, headers, rows, title=None, row_pad=0.014, wrap_widths=None,
                    font_size=7.6, line_h=0.0125, after_pad=0.018):
    """Helper to draw a clean publication table on a portrait PDF page."""
    ink = "#1f2937"
    navy = "#1d3557"
    XR = 0.94
    y = y_top
    if title:
        fig.text(x0, y, title, fontsize=10.6, fontweight="bold", color=navy, va="center")
        y -= 0.019
    _line(fig, x0, XR, y + 0.007, color=navy, lw=1.1)
    for cx, h in zip(col_xs, headers):
        fig.text(cx, y - 0.003, h, fontsize=font_size + 0.3, fontweight="bold", color=navy, va="center")
    y -= 0.014
    _line(fig, x0, XR, y, color=navy, lw=0.8)
    y -= 0.006
    for r in rows:
        wrapped_cols = []
        max_lines = 1
        for idx, val in enumerate(r):
            sval = "" if (val is None or (isinstance(val, float) and np.isnan(val))) else str(val)
            w_lim = wrap_widths[idx] if (wrap_widths and idx < len(wrap_widths)) else 90
            lines = textwrap.wrap(sval, w_lim) or [""]
            wrapped_cols.append("\n".join(lines))
            max_lines = max(max_lines, len(lines))
        for cx, txt in zip(col_xs, wrapped_cols):
            fig.text(cx, y, txt, fontsize=font_size, color=ink, va="top", linespacing=1.22)
        y -= max_lines * line_h + row_pad
        _line(fig, x0, XR, y + row_pad * 0.55, color="#e5e7eb", lw=0.5)
    _line(fig, x0, XR, y + row_pad * 0.55, color=navy, lw=1.0)
    return y - after_pad


def write_complete_pdf_report(path, analysis, meta, title="TGA / DTG", fig_title=None):
    """
    Creates a multi-page publication PDF report containing:
      Page 1: Style B (Presentation Landscape graph + summary tables)
      Page 2: Style A (Journal Vertical graph with callout boxes)
      Page 3: Experimental Conditions, Paste Composition & Quantitative Steps Summary
      Page 4: Detailed Step-by-Step Interpretation, Expected vs Measured & Literature References
    """
    A = analysis
    silica_mode = bool(A.get("is_silica"))
    refs_dict = get_references_for(A)
    with PdfPages(path) as pdf:
        # Page 1: Style B (Landscape)
        fig_b = new_figure(size=FIG_SIZE_B)
        render_style_b_figure(fig_b, A, title=title, fig_title=fig_title)
        pdf.savefig(fig_b, facecolor="white")

        # Page 2: Style A (Vertical Journal)
        fig_a = new_figure(size=FIG_SIZE_A)
        render_style_a_figure(fig_a, A, title=title, fig_title=fig_title)
        pdf.savefig(fig_a, facecolor="white")

        # Page 3: Experimental Conditions & Paste Composition + Step Summary
        fig_t1 = new_figure(size=(8.5, 11.0))
        navy = "#1d3557"
        grey = "#555555"
        hdr_title = title if len(str(meta.get("sample_title", ""))) > 38 else meta.get("sample_title", title)
        fig_t1.text(0.06, 0.958, f"TGA / DTG Complete Analytical Report – {hdr_title}",
                    fontsize=12.8, fontweight="bold", color=navy, va="center")
        fig_t1.text(0.06, 0.938,
                    f"Sample ID: {meta.get('sample_id', '')}   •   Operator: {meta.get('operator', '')}   •   "
                    f"Date: {meta.get('date', '')}   •   Raw file: {meta.get('raw_file', '')}",
                    fontsize=8.5, color=grey, va="center")
        _line(fig_t1, 0.06, 0.94, 0.925, color=navy, lw=1.5)

        y = 0.898
        info_pairs = _info_rows(A, meta)[:22]
        cond_rows = [(k, v) for k, v in info_pairs]
        y = _draw_pdf_table(fig_t1, 0.06, y, [0.06, 0.38], ["Measuring Parameter / Condition", "Value"],
                            cond_rows, title="1. Experimental & Measuring Conditions",
                            row_pad=0.006, wrap_widths=[40, 76], font_size=7.5)

        comp = A["composition"]
        if silica_mode:
            comp_rows = [
                (i + 1, r["component"], f"{r['mass_g']:g} g",
                 f"{r['dry_pct']} %" if r.get("dry_pct") is not None else "—",
                 f"{r['pct']:.2f} %", r["note"])
                for i, r in enumerate(comp)
            ]
            comp_rows.append(("Total", "", f"{composition_total(comp):g} g", "100 %", "100.00 %", ""))
            y = _draw_pdf_table(fig_t1, 0.06, y - 0.008, [0.06, 0.11, 0.28, 0.38, 0.49, 0.60],
                                ["No.", "Component", "Mass (g)", "Dry mix %", "Wet paste %", "Preparation / Supplier Note"],
                                comp_rows, title="2. Paste Composition (Dry Mix & Wet Paste Basis)",
                                row_pad=0.007, wrap_widths=[5, 20, 12, 12, 12, 44], font_size=7.4)
        else:
            comp_rows = [(i + 1, r["component"], f"{r['mass_g']:.2f} g", f"{r['pct']:.2f} %", r["note"])
                         for i, r in enumerate(comp)]
            comp_rows.append(("Total", "", f"{composition_total(comp):.2f} g", "100.00 %", ""))
            y = _draw_pdf_table(fig_t1, 0.06, y - 0.008, [0.06, 0.12, 0.36, 0.48, 0.62],
                                ["No.", "Component", "Mass (g)", "wt% (wet)", "Preparation Note"],
                                comp_rows, title="2. Paste Composition (Wet Basis)",
                                row_pad=0.008, wrap_widths=[6, 26, 14, 14, 42], font_size=7.8)

        steps_df = _steps_df(A)
        if silica_mode:
            step_tbl_rows = [
                (r["Step"], r["T start (°C)"], r["T end (°C)"],
                 "" if pd.isna(r["DTG peak (°C)"]) else r["DTG peak (°C)"],
                 "" if pd.isna(r["DTG peak height (wt%/°C)"]) else r["DTG peak height (wt%/°C)"],
                 r["Mass at start (wt%)"], r["Mass at end (wt%)"], r["Mass loss (wt%)"],
                 "" if pd.isna(r["Mass loss on dry-paste basis (% of mass at end of step I)"])
                 else f"{r['Mass loss on dry-paste basis (% of mass at end of step I)']:.2f} %")
                for _, r in steps_df.iterrows()
            ]
            y = _draw_pdf_table(fig_t1, 0.06, y - 0.008,
                                [0.06, 0.12, 0.23, 0.32, 0.42, 0.54, 0.65, 0.75, 0.84],
                                ["Step", "T start", "T end", "Peak °C", "Peak wt%/°C", "M start %", "M end %", "Loss %", "Dry-paste %"],
                                step_tbl_rows, title="3. Quantitative Mass-Loss Steps Summary",
                                row_pad=0.007, wrap_widths=[8, 12, 10, 10, 12, 10, 10, 10, 12], font_size=7.4)
        else:
            step_tbl_rows = [
                (r["Step"], r["T start (°C)"], r["T end (°C)"], r["DTG peak (°C)"],
                 r["Mass at start (wt%)"], r["Mass at end (wt%)"], r["Mass loss (wt%)"])
                for _, r in steps_df.iterrows()
            ]
            y = _draw_pdf_table(fig_t1, 0.06, y - 0.008, [0.06, 0.15, 0.28, 0.40, 0.53, 0.69, 0.83],
                                ["Step", "T start (°C)", "T end (°C)", "DTG peak (°C)", "Mass start (%)", "Mass end (%)", "Mass loss (%)"],
                                step_tbl_rows, title="3. Quantitative Mass-Loss Steps Summary",
                                row_pad=0.008, wrap_widths=[10, 14, 14, 14, 14, 14, 14], font_size=7.8)
        pdf.savefig(fig_t1, facecolor="white")

        # Page 4: Detailed Step-by-Step Interpretation, Theory vs Measured & Literature References
        fig_t2 = new_figure(size=(8.5, 11.0))
        fig_t2.text(0.06, 0.962, f"TGA / DTG Interpretation & Mass Balance – {hdr_title}",
                    fontsize=12.8, fontweight="bold", color=navy, va="center")
        fig_t2.text(0.06, 0.943,
                    f"Sample ID: {meta.get('sample_id', '')}   •   Atmosphere: {A['conditions'].get('atmosphere', 'Air')}, "
                    f"{A['conditions'].get('flow_ml_min', 50):g} mL/min, {A['conditions'].get('heating_rate', 10):g} °C/min",
                    fontsize=8.5, color=grey, va="center")
        _line(fig_t2, 0.06, 0.94, 0.931, color=navy, lw=1.5)

        y = 0.912
        interp_rows = [
            (r["step"], r["t_range"], f"{r['peak_t']:.0f}", f"{r['loss']:.2f}", r["assignment"],
             r["comment"], ", ".join(f"[{x}]" for x in r["refs"]))
            for r in A["interpretation"]
        ]
        y = _draw_pdf_table(fig_t2, 0.06, y, [0.06, 0.11, 0.21, 0.28, 0.35, 0.58, 0.88],
                            ["Step", "T range", "Peak °C", "Loss %", "Assignment", "Detailed Mechanism & Comment", "Refs"],
                            interp_rows, title="4. Step-by-Step Thermal Interpretation",
                            row_pad=0.0035, wrap_widths=[5, 12, 8, 8, 28, 48, 10], font_size=6.7,
                            line_h=0.0100, after_pad=0.010)

        tv_df = _theory_vs_measured_df(A)
        tv_rows = [(row["Item"], row["Expected from composition (wt%)"], row["Measured (wt%)"], row["Note"])
                   for _, row in tv_df.iterrows()]
        y = _draw_pdf_table(fig_t2, 0.06, y, [0.06, 0.44, 0.54, 0.63],
                            ["Component / Balance Item", "Expected %", "Measured %", "Analytical Note"],
                            tv_rows, title="5. Expected from Paste Composition vs. Measured Mass Balance",
                            row_pad=0.0030, wrap_widths=[46, 12, 12, 48], font_size=6.6,
                            line_h=0.0096, after_pad=0.010)

        fig_t2.text(0.06, y, "6. Literature References", fontsize=10.0, fontweight="bold", color=navy, va="center")
        y -= 0.013
        for rid in used_reference_ids(A):
            if rid not in refs_dict:
                continue
            ref = refs_dict[rid]
            txt = f"[{rid}]  {ref['full']}  (doi:{ref['doi']})\n       Used for: {ref['used']}"
            lines = []
            for para in txt.split("\n"):
                lines.extend(textwrap.wrap(para, 128))
            fig_t2.text(0.06, y, "\n".join(lines), fontsize=6.3, color="#333333", va="top", linespacing=1.15)
            y -= 0.0088 * len(lines) + 0.0028

        pdf.savefig(fig_t2, facecolor="white")
    return path


# --------------------------------------------------------------------------- #
# HTML report (includes both Style B and Style A figures)
# --------------------------------------------------------------------------- #

def build_html_report(analysis, meta, png_b_bytes, png_a_bytes=None, files=None):
    A = analysis
    silica_mode = bool(A.get("is_silica"))
    refs_dict = get_references_for(A)
    e = html.escape
    tot, th, cond, comp = A["totals"], A["theory"], A["conditions"], A["composition"]
    img_b_64 = base64.b64encode(png_b_bytes).decode("ascii")
    img_a_html = ""
    if png_a_bytes:
        img_a_64 = base64.b64encode(png_a_bytes).decode("ascii")
        img_a_html = f"""
<h2>4. TGA / DTG Graph – Style A (Journal Vertical Layout)</h2>
<img alt="TGA DTG Style A graph" style="max-width:760px; display:block; margin:12px auto;" src="data:image/png;base64,{img_a_64}">
"""
    total_m = composition_total(comp)

    if silica_mode:
        comp_hdr = "<tr><th>No.</th><th>Component</th><th>Mass (g)</th><th>wt% of dry mix</th><th>wt% (wet basis, paste)</th></tr>"
        comp_rows = "".join(
            f"<tr><td>{i + 1}</td><td>{e(r['component'])}"
            + (f"<br><small>{e(r['note'])}</small>" if r["note"] else "")
            + f"</td><td>{r['mass_g']:g} g</td><td>{r['dry_pct'] if r.get('dry_pct') is not None else ''}</td>"
            + f"<td>{r['pct']:.2f} %</td></tr>" for i, r in enumerate(comp))
        comp_rows += f"<tr class='tot'><td></td><td>Total</td><td>{total_m:g} g</td><td>100 %</td><td>100 %</td></tr>"
    else:
        comp_hdr = "<tr><th>Sr.</th><th>Component</th><th>Mass</th><th>Percentage (wet basis)</th></tr>"
        comp_rows = "".join(
            f"<tr><td>{i + 1}</td><td>{e(r['component'])}</td><td>{r['mass_g']:.2f} g"
            + (f"<br><small>{e(r['note'])}</small>" if r["note"] else "")
            + f"</td><td>{r['pct']:.2f} %</td></tr>" for i, r in enumerate(comp))
        comp_rows += f"<tr class='tot'><td></td><td>Total</td><td>{total_m:.2f} g</td><td>100 %</td></tr>"

    step_rows = ""
    for r in A["interpretation"]:
        step_rows += (f"<tr><td><span class='badge' style='background:{r['color']}'>{e(r['step'])}</span></td>"
                      f"<td>{e(r['t_range'])}</td><td>{r['peak_t']:.0f}{' (weak)' if r['weak'] else ''}</td>"
                      f"<td><b style='color:{r['color']}'>{r['loss']:.2f}</b></td>"
                      f"<td>{e(r['assignment'])} [{', '.join(str(x) for x in r['refs'])}]</td></tr>")
    step_rows += (f"<tr class='tot'><td colspan='3'>Total mass loss</td><td><b>{tot['total_loss']:.2f}</b></td>"
                  f"<td>Residue at {tot['t_last']:.0f} °C: {tot['residue']:.2f} wt%</td></tr>")

    interp_rows = "".join(
        f"<tr><td><span class='badge' style='background:{r['color']}'>{e(r['step'])}</span></td>"
        f"<td>{e(r['assignment'])}</td><td>{e(r['expected'])}</td><td>{e(r['comment'])}</td>"
        f"<td>{', '.join(f'[{x}]' for x in r['refs'])}</td></tr>" for r in A["interpretation"])

    tv_rows = ""
    for _, row in _theory_vs_measured_df(A).iterrows():
        exp_v = "" if pd.isna(row["Expected from composition (wt%)"]) else str(row["Expected from composition (wt%)"])
        meas_v = "" if pd.isna(row["Measured (wt%)"]) else str(row["Measured (wt%)"])
        tv_rows += (f"<tr><td>{e(str(row['Item']))}</td><td>{e(exp_v)}</td>"
                    f"<td>{e(meas_v)}</td><td><small>{e(str(row['Note'] or ''))}</small></td></tr>")

    ref_rows = "".join(
        f"<li>[{k}] {e(refs_dict[k]['full'])} <a href='https://doi.org/{e(refs_dict[k]['doi'])}'>"
        f"doi:{e(refs_dict[k]['doi'])}</a></li>" for k in used_reference_ids(A) if k in refs_dict)

    info = "".join(f"<tr><th>{e(str(k))}</th><td>{e(str(v))}</td></tr>" for k, v in _info_rows(A, meta))
    files_html = ""
    if files:
        files_html = "<h2>9. Files saved in the vault</h2><ul>" + "".join(
            f"<li>{e(os.path.basename(p))}</li>" for p in files if p) + "</ul>"

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>TGA report – {e(meta.get('sample_title', ''))}</title>
<style>
 body {{ font-family: 'Segoe UI', Arial, sans-serif; color:#222; max-width:1120px; margin:24px auto; padding:0 18px; }}
 h1 {{ color:#1d3557; border-bottom:3px solid #1d3557; padding-bottom:6px; }}
 h2 {{ color:#1d3557; margin-top:30px; }}
 table {{ border-collapse:collapse; width:100%; margin:8px 0; font-size:14px; }}
 th,td {{ border:1px solid #ccd; padding:6px 9px; text-align:left; vertical-align:top; }}
 th {{ background:#eef2f8; }} tr.tot td {{ font-weight:bold; background:#f6f8fb; }}
 .badge {{ color:#fff; font-weight:bold; padding:2px 9px; border-radius:4px; }}
 .kpi {{ display:flex; gap:14px; flex-wrap:wrap; }} .kpi div {{ flex:1; min-width:170px; background:#eef2f8; border-radius:8px; padding:10px 14px; }}
 .kpi b {{ font-size:22px; color:#c0392b; display:block; }} img {{ width:100%; border:1px solid #ddd; }}
 small {{ color:#666; }} li {{ margin:4px 0; font-size:13px; }}
 @media print {{ body {{ max-width:none; }} }}
</style></head><body>
<h1>TGA / DTG Complete Report – {e(meta.get('sample_title', ''))}</h1>
<p><small>Sample ID: {e(str(meta.get('sample_id', '')))} · Operator: {e(str(meta.get('operator', '')))} · Date: {e(str(meta.get('date', '')))} · Raw file: {e(str(meta.get('raw_file', '')))}</small></p>

<div class="kpi">
 <div>Total mass loss<b>{tot['total_loss']:.1f} wt%</b></div>
 <div>Residue at {tot['t_last']:.0f} °C<b style="color:#16365c">{tot['residue']:.1f} wt%</b></div>
 <div>Main DTG peak<b style="color:#16365c">{tot['peak_t_main']:.0f} °C</b></div>
 <div>Steps detected<b style="color:#16365c">{len(A['steps'])}</b></div>
</div>

<h2>1. Paste composition</h2>
<table>{comp_hdr}{comp_rows}</table>

<h2>2. Experimental & measuring conditions</h2>
<table>{info}</table>

<h2>3. TGA / DTG Graph – Style B (Presentation Layout)</h2>
<img alt="TGA DTG Style B graph" src="data:image/png;base64,{img_b_64}">
{img_a_html}

<h2>5. Mass-loss steps</h2>
<table><tr><th>Step</th><th>T range</th><th>DTG peak (°C)</th><th>Loss (wt%)</th><th>Assignment</th></tr>{step_rows}</table>

<h2>6. Detailed Interpretation</h2>
<table><tr><th>Step</th><th>Assignment</th><th>Expected from composition (wt%)</th><th>Comment</th><th>Refs</th></tr>{interp_rows}</table>

<h2>7. Expected vs measured</h2>
<table><tr><th>Item</th><th>Expected from composition (wt%)</th><th>Measured (wt%)</th><th>Note</th></tr>{tv_rows}</table>

<h2>8. References</h2>
<ul>{ref_rows}</ul>
{files_html}
<p><small>Generated automatically by Lab Vault – TGA Report Engine on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}.</small></p>
</body></html>"""


# --------------------------------------------------------------------------- #
# Full package
# --------------------------------------------------------------------------- #

def _safe(s):
    return "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in str(s)).strip("_")


def save_report_package(out_dir, analysis, meta, title, dpis=(1200,), progress=None, fig_title=None):
    """
    Writes into out_dir (cleaning any legacy split/extra files first):
      1. Complete multi-page PDF report (`<base>_Complete_TGA_Report.pdf`)
      2. Single Combined Master Excel (`<base>_Complete_Data_and_Interpretation.xlsx`) with all 8 sheets
      3. High-res 1200 DPI PNGs for BOTH Style A (journal) and Style B (presentation)
      4. Complete HTML report (`<base>_TGA_report.html`)
    """
    os.makedirs(out_dir, exist_ok=True)
    for old_f in os.listdir(out_dir):
        old_p = os.path.join(out_dir, old_f)
        if os.path.isfile(old_p):
            try:
                os.chmod(old_p, 0o666)
                os.remove(old_p)
            except Exception:
                pass

    base = _safe(meta.get("base_name") or meta.get("sample_id") or "TGA")
    paths = {}

    def tick(msg):
        if progress:
            progress(msg)

    tick("Generating Complete Multi-Page PDF Report (Style A + Style B + Tables)…")
    paths["pdf_report"] = write_complete_pdf_report(
        os.path.join(out_dir, f"{base}_Complete_TGA_Report.pdf"),
        analysis, meta, title=title, fig_title=fig_title
    )
    paths["pdf"] = paths["pdf_report"]

    for dpi in dpis:
        tick(f"Rendering Style A (Journal) & Style B (Presentation) at {dpi} DPI…")
        pa = os.path.join(out_dir, f"{base}_styleA_journal_{dpi}dpi.png")
        pb = os.path.join(out_dir, f"{base}_styleB_presentation_{dpi}dpi.png")
        try:
            export_figure(analysis, title, pa, dpi=dpi, fig_title=fig_title, style=STYLE_A)
            paths[f"styleA_png_{dpi}"] = pa
        except MemoryError:
            paths[f"styleA_png_{dpi}"] = None
        try:
            export_figure(analysis, title, pb, dpi=dpi, fig_title=fig_title, style=STYLE_B)
            paths[f"styleB_png_{dpi}"] = pb
        except MemoryError:
            paths[f"styleB_png_{dpi}"] = None

    tick("Writing Single Combined Master Excel Workbook (all 8 sheets)…")
    raw_df = analysis["df"]
    paths["xlsx_combined"] = write_combined_excel(
        os.path.join(out_dir, f"{base}_Complete_Data_and_Interpretation.xlsx"),
        analysis, raw_df, meta
    )
    paths["xlsx_data"] = paths["xlsx_combined"]

    tick("Writing interactive HTML report…")
    png_b_html = figure_to_png_bytes(analysis, title, dpi=200, fig_title=fig_title, style=STYLE_B)
    png_a_html = figure_to_png_bytes(analysis, title, dpi=200, fig_title=fig_title, style=STYLE_A)
    paths["html"] = os.path.join(out_dir, f"{base}_TGA_report.html")
    all_files = [v for k, v in paths.items() if v and k not in ("pdf", "xlsx_data")]
    html_txt = build_html_report(analysis, meta, png_b_html, png_a_bytes=png_a_html, files=all_files)
    with open(paths["html"], "w", encoding="utf-8") as f:
        f.write(html_txt)

    return paths


def analysis_summary(analysis, meta):
    A = analysis
    return {
        "meta": meta,
        "conditions": A["conditions"],
        "composition": [{k: v for k, v in r.items()} for r in A["composition"]],
        "totals": A["totals"],
        "limits": A["limits"],
        "limit_kinds": A["limit_kinds"],
        "steps": [{k: v for k, v in s.items()} for s in A["steps"]],
        "theory": A["theory"],
        "interpretation": A["interpretation"],
    }
