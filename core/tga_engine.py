"""
TGA Analysis & Publication-Quality Plotting Engine
Supports:
- Loading raw TGA data from Excel (.xlsx, .xls) and CSV/TXT
- Detecting Temperature, Weight %, and Deriv. Weight (%/°C) / DTG
- Computing numerical derivative (-dw/dT) if DTG is missing
- Generating Origin-style dual panel plot:
    Top: Deriv. Weight (%/°C) (Blue line)
    Bottom: Weight (%) vs Temperature (°C) (Red line)
    Annotations: Initial plateau, residual plateau, step delta weight loss (ΔW %) with dashed lines and magenta double-arrow
"""

import os
import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import AutoMinorLocator

_TGA_CACHE = {}

def load_tga_data(file_path):
    """
    Loads raw TGA data from Excel or CSV/TXT.
    Automatically detects column headers even if multi-index or metadata rows precede.
    Returns:
        df: pd.DataFrame with normalized columns:
            'temperature', 'weight', 'deriv_weight' (optional: 'time')
        meta: dict with metadata
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"TGA data file not found: {file_path}")

    # Check cache
    mtime = os.path.getmtime(file_path)
    cache_key = (os.path.abspath(file_path), mtime)
    if cache_key in _TGA_CACHE:
        cached_df, cached_meta = _TGA_CACHE[cache_key]
        return cached_df.copy(), dict(cached_meta)

    ext = os.path.splitext(file_path)[1].lower()
    if ext not in [".xlsx", ".xls", ".csv", ".txt", ".dat"]:
        raise ValueError(f"Unsupported file format '{ext}' for TGA curve parsing. Supported: .xlsx, .xls, .csv, .txt")

    raw_df = None
    if ext in [".xlsx", ".xls"]:
        # Try reading with multi-index header [0, 1] first
        try:
            raw_df = pd.read_excel(file_path, header=[0, 1])
            cols = [' '.join([str(c) for c in col if str(c) not in ('nan', '', 'Unnamed')]).strip().lower() for col in raw_df.columns]
            raw_df.columns = cols
        except Exception:
            raw_df = pd.read_excel(file_path)
            raw_df.columns = [str(c).strip().lower() for c in raw_df.columns]
    else:
        # CSV or TXT
        # Try finding delimiter (, or tab or whitespace)
        for sep in [",", "\t", r"\s+"]:
            try:
                raw_df = pd.read_csv(file_path, sep=sep, comment="#")
                raw_df.columns = [str(c).strip().lower() for c in raw_df.columns]
                if len(raw_df.columns) >= 2:
                    break
            except Exception:
                continue

    if raw_df is None or raw_df.empty:
        raise ValueError(f"Could not parse valid tabular data from {file_path}")

    # Locate Columns
    temp_col = None
    weight_col = None
    deriv_col = None
    time_col = None

    for col in raw_df.columns:
        c_str = str(col).lower()
        if "time" in c_str and not time_col:
            time_col = col
        elif ("temp" in c_str or "temperature" in c_str or "°c" in c_str) and not temp_col:
            temp_col = col
        elif ("deriv" in c_str or "dtg" in c_str or "dw/dt" in c_str) and not deriv_col:
            deriv_col = col
        elif ("weight" in c_str or "mass" in c_str or "%" in c_str) and "deriv" not in c_str and not weight_col:
            weight_col = col

    # Fallback by column position if not detected
    if not temp_col and len(raw_df.columns) >= 2:
        temp_col = raw_df.columns[1] if len(raw_df.columns) > 2 else raw_df.columns[0]
    if not weight_col and len(raw_df.columns) >= 2:
        weight_col = raw_df.columns[2] if len(raw_df.columns) > 2 else raw_df.columns[1]

    if not temp_col or not weight_col:
        raise ValueError(f"Could not automatically detect Temperature and Weight columns in {file_path}")

    # Clean & convert to numeric
    clean_df = pd.DataFrame()
    clean_df["temperature"] = pd.to_numeric(raw_df[temp_col], errors="coerce")
    clean_df["weight"] = pd.to_numeric(raw_df[weight_col], errors="coerce")

    if deriv_col and deriv_col in raw_df.columns:
        clean_df["deriv_weight"] = pd.to_numeric(raw_df[deriv_col], errors="coerce")
    else:
        # Calculate numerical derivative -dw/dT (Smoothed with Savitzky-Golay or gradient)
        clean_df["deriv_weight"] = np.nan

    if time_col and time_col in raw_df.columns:
        clean_df["time"] = pd.to_numeric(raw_df[time_col], errors="coerce")

    # Drop NaNs
    clean_df = clean_df.dropna(subset=["temperature", "weight"]).reset_index(drop=True)

    # If deriv_weight is all NaN or missing, calculate numerical derivative
    if clean_df["deriv_weight"].isna().all() or len(clean_df["deriv_weight"].dropna()) == 0:
        t_vals = clean_df["temperature"].values
        w_vals = clean_df["weight"].values
        # -dw/dT in %/°C
        dw = -np.gradient(w_vals, t_vals)
        # Smooth out noisy gradient
        try:
            from scipy.signal import savgol_filter
            win = min(31, len(dw) - (1 if len(dw) % 2 == 0 else 2))
            if win > 5:
                dw = savgol_filter(dw, win, 2)
        except Exception:
            pass
        clean_df["deriv_weight"] = np.maximum(0, dw)

    # Basic analysis metrics
    w_start = float(clean_df["weight"].iloc[0])
    w_end = float(clean_df["weight"].iloc[-1])
    delta_w = float(w_start - w_end)

    # Find peak degradation temp (max of deriv_weight between 50°C and 800°C)
    mask = (clean_df["temperature"] >= 50) & (clean_df["temperature"] <= 850)
    sub = clean_df[mask]
    if not sub.empty:
        max_idx = sub["deriv_weight"].idxmax()
        peak_temp = float(clean_df.loc[max_idx, "temperature"])
        peak_rate = float(clean_df.loc[max_idx, "deriv_weight"])
    else:
        peak_temp = float(clean_df["temperature"].iloc[0])
        peak_rate = 0.0

    meta = {
        "file_name": os.path.basename(file_path),
        "initial_weight_pct": round(w_start, 2),
        "residual_weight_pct": round(w_end, 2),
        "delta_weight_pct": round(delta_w, 2),
        "peak_temp_c": round(peak_temp, 1),
        "peak_rate": round(peak_rate, 4),
        "t_min": float(clean_df["temperature"].min()),
        "t_max": float(clean_df["temperature"].max()),
        "w_min": float(clean_df["weight"].min()),
        "w_max": float(clean_df["weight"].max())
    }

    _TGA_CACHE[cache_key] = (clean_df.copy(), dict(meta))
    return clean_df, meta


def plot_tga_dual_panel(df, meta, title="TGA / DTG Analysis", fig=None, show_annotations=True):
    """
    Renders an OriginPro-quality dual-panel TGA plot matching the user's reference:
    - Top: Deriv. Weight (%/°C) (Blue line)
    - Bottom: Weight (%) (Red line)
    - Shared X axis: Temperature (°C)
    - Dashed green lines for Initial Plateau and Residual Plateau
    - Magenta double arrow and text for Net Weight Loss (ΔW %)
    """
    if fig is None:
        fig, (ax_top, ax_bot) = plt.subplots(
            2, 1, 
            figsize=(5.5, 8.5), 
            dpi=120, 
            sharex=True, 
            gridspec_kw={"height_ratios": [1, 1], "hspace": 0.0}
        )
    else:
        fig.clear()
        gs = fig.add_gridspec(2, 1, height_ratios=[1, 1], hspace=0.0)
        ax_top = fig.add_subplot(gs[0])
        ax_bot = fig.add_subplot(gs[1], sharex=ax_top)

    t = df["temperature"].values
    w = df["weight"].values
    dw = df["deriv_weight"].values

    # TOP PANEL: Deriv. Weight (%/°C)
    ax_top.plot(t, dw, color="#0000ff", linewidth=1.5, label="Deriv. Weight")
    ax_top.set_ylabel("Deriv. Weight (%/°C)", fontsize=11, fontweight="bold", labelpad=8)
    ax_top.tick_params(direction="in", top=True, right=True, bottom=True, labelbottom=False, which="both", labelsize=10)
    ax_top.xaxis.set_minor_locator(AutoMinorLocator(2))
    ax_top.yaxis.set_minor_locator(AutoMinorLocator(2))

    # Top panel title (Red, bold, centered)
    ax_top.set_title(title, fontsize=12, fontweight="bold", color="#ff0000", pad=12)
    ax_top.legend(loc="upper right", frameon=True, edgecolor="#000000", fontsize=10, prop={'weight':'bold'})

    # Adjust top limits
    max_dw = np.nanmax(dw) if len(dw) > 0 else 1.0
    ax_top.set_ylim(bottom=0.0, top=round(max_dw * 1.15, 2))

    # BOTTOM PANEL: Weight (%)
    ax_bot.plot(t, w, color="#ff0000", linewidth=1.5, label="Weight")
    ax_bot.set_xlabel("Temperature (°C)", fontsize=12, fontweight="bold", labelpad=8)
    ax_bot.set_ylabel("Weight (%)", fontsize=11, fontweight="bold", labelpad=8)
    ax_bot.tick_params(direction="in", top=True, right=True, which="both", labelsize=10)
    ax_bot.xaxis.set_minor_locator(AutoMinorLocator(2))
    ax_bot.yaxis.set_minor_locator(AutoMinorLocator(2))
    ax_bot.legend(loc="upper right", frameon=True, edgecolor="#000000", fontsize=10, prop={'weight':'bold'})

    # X Limits
    x_min = 30
    x_max = 900
    if len(t) > 0:
        x_max = max(900, int(np.ceil(t.max() / 100) * 100))
    ax_bot.set_xlim(x_min, x_max)

    # Bottom Y Limits
    w_min = meta.get("residual_weight_pct", float(w.min()))
    w_max = meta.get("initial_weight_pct", float(w.max()))
    y_bot = 30.0 if w_min >= 30.0 else max(0.0, float(np.floor(w_min / 10) * 10))
    y_top = 100.0 if w_max <= 100.0 else float(np.ceil(w_max / 10) * 10)
    ax_bot.set_ylim(y_bot, y_top)

    # ANNOTATIONS matching User Reference:
    if show_annotations and len(t) > 0:
        w_start = meta.get("initial_weight_pct", w[0])
        w_end = meta.get("residual_weight_pct", w[-1])
        delta_w = meta.get("delta_weight_pct", w_start - w_end)

        # 1. Initial plateau dashed green line
        t_plat1_end = 600.0
        ax_bot.hlines(w_start, xmin=x_min, xmax=t_plat1_end, colors="#00ff00", linestyles=":", linewidth=2.0)
        ax_bot.text(
            300.0, 
            w_start - 2.8, 
            f"{w_start:.1f}", 
            fontsize=8, 
            fontweight="bold", 
            ha="center"
        )

        # 2. Residual plateau dashed green line
        t_plat2_end = 750.0
        ax_bot.hlines(w_end, xmin=x_min, xmax=t_plat2_end, colors="#00ff00", linestyles=":", linewidth=2.0)
        ax_bot.text(
            630.0, 
            w_end + 1.2, 
            f"{w_end:.1f}", 
            fontsize=8, 
            fontweight="bold", 
            ha="center"
        )

        # 3. Magenta double arrow with Delta W text
        arrow_x = 510.0
        ax_bot.annotate(
            "", 
            xy=(arrow_x, w_start), 
            xytext=(arrow_x, w_end),
            arrowprops=dict(
                arrowstyle="<->", 
                color="#e000d0", 
                linestyle=":", 
                linewidth=1.8,
                mutation_scale=12
            )
        )
        # Text for Delta W in middle of arrow
        mid_y = (w_start + w_end) / 2
        ax_bot.text(
            arrow_x + 12, 
            mid_y, 
            f"{round(delta_w)}", 
            fontsize=13, 
            fontweight="bold", 
            color="#000000", 
            va="center",
            ha="left"
        )

    # Style spines (bold border)
    for ax in [ax_top, ax_bot]:
        for spine in ax.spines.values():
            spine.set_linewidth(1.2)
            spine.set_color("#000000")

    fig.tight_layout()
    return fig
