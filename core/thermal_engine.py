import os
import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

PROFILE_CATEGORIES = [
    ("All", "All Profiles & Files"),
    ("Vertical", "↕️ Vertical Profile (V-series)"),
    ("Horizontal", "↔️ Horizontal Profile (H-series)"),
    ("Comparison", "⚖️ Hori vs Ver Comparison (e.g. V7 vs H5)"),
    ("Heatmap", "🗺️ 2D Thermal Heatmap"),
    ("Raw Data", "📄 Raw Thermocouple Data (.csv/.xlsx)")
]

def detect_profile_category(filename):
    """
    Intelligently detects the profile sub-category based on the file name and extension.
    """
    fn = filename.lower()
    ext = os.path.splitext(fn)[1]

    if "heat" in fn or "map" in fn or "contour" in fn:
        return "Heatmap"
    if ("hori" in fn or "h5" in fn) and ("ver" in fn or "v7" in fn):
        return "Comparison"
    if "vert" in fn or "axial" in fn or fn.startswith("v_") or re.search(r'\bv\d+\b', fn):
        return "Vertical"
    if "hori" in fn or "radial" in fn or fn.startswith("h_") or re.search(r'\bh\d+\b', fn):
        return "Horizontal"
    if ext in [".csv", ".xlsx", ".xls", ".txt", ".dat"]:
        return "Raw Data"
    return "Vertical"


def parse_time_to_minutes(val):
    """Converts seconds, strings like 'MM:SS' or 'HH:MM:SS', or floats into minutes."""
    if pd.isna(val):
        return np.nan
    if isinstance(val, (int, float)):
        return float(val)
    val_str = str(val).strip()
    parts = val_str.split(":")
    if len(parts) == 3:  # HH:MM:SS
        try:
            return float(parts[0]) * 60.0 + float(parts[1]) + float(parts[2]) / 60.0
        except ValueError:
            pass
    elif len(parts) == 2:  # MM:SS
        try:
            return float(parts[0]) + float(parts[1]) / 60.0
        except ValueError:
            pass
    try:
        return float(val_str)
    except ValueError:
        return np.nan


def load_thermal_data(file_path):
    """
    Loads and normalizes raw thermocouple measurement data from Excel, CSV, or TXT.
    Returns:
        df: DataFrame with 'Time_min' and numeric temperature channels.
        meta: Dictionary of calculated thermal kinetics (T_max, delta_T, peak_time, hotspot, etc.)
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext in [".xlsx", ".xls"]:
        df_raw = pd.read_excel(file_path)
    elif ext in [".csv"]:
        try:
            df_raw = pd.read_csv(file_path)
        except Exception:
            df_raw = pd.read_csv(file_path, sep=";")
    else:
        # Delimited TXT
        try:
            df_raw = pd.read_csv(file_path, sep=r'\s+')
        except Exception:
            df_raw = pd.read_csv(file_path, sep=",")

    # Clean column names
    df_raw.columns = [str(c).strip() for c in df_raw.columns]

    # Find time column
    time_col = None
    for c in df_raw.columns:
        c_low = c.lower()
        if "time" in c_low or "tiempo" in c_low or c_low in ["t", "min", "sec", "s"]:
            time_col = c
            break

    if not time_col:
        time_col = df_raw.columns[0]

    time_series = df_raw[time_col].apply(parse_time_to_minutes)
    df = pd.DataFrame({"Time_min": time_series})

    # Find channel columns (numeric temperature series)
    channels = []
    for c in df_raw.columns:
        if c == time_col:
            continue
        col_numeric = pd.to_numeric(df_raw[c], errors="coerce")
        if col_numeric.notna().sum() > 3:
            df[c] = col_numeric
            channels.append(c)

    # Sort channels logically (V0..V14, H0..H10, etc.)
    def channel_sort_key(ch):
        match = re.search(r'([A-Za-z]+)(\d+)', ch)
        if match:
            return (match.group(1), int(match.group(2)))
        return (ch, 0)

    channels.sort(key=channel_sort_key)

    # Calculate thermal kinetics
    meta = {
        "channels": channels,
        "t_initial_c": 25.0,
        "t_max_c": 25.0,
        "delta_t_c": 0.0,
        "time_to_peak_min": 0.0,
        "hotspot_position": "-",
        "duration_min": 0.0
    }

    if channels:
        t_init_vals = []
        max_vals = {}
        max_times = {}

        for ch in channels:
            series = df[ch].dropna()
            if not series.empty:
                t_init_vals.append(series.iloc[0])
                idx_max = series.idxmax()
                max_vals[ch] = series.loc[idx_max]
                max_times[ch] = df.loc[idx_max, "Time_min"]

        if t_init_vals:
            t0 = float(np.median(t_init_vals))
            meta["t_initial_c"] = round(t0, 2)

        if max_vals:
            best_ch = max(max_vals, key=max_vals.get)
            t_max = float(max_vals[best_ch])
            meta["t_max_c"] = round(t_max, 2)
            meta["delta_t_c"] = round(t_max - meta["t_initial_c"], 2)
            meta["hotspot_position"] = best_ch
            meta["time_to_peak_min"] = round(float(max_times.get(best_ch, 0.0)), 2)

        t_clean = df["Time_min"].dropna()
        if not t_clean.empty:
            meta["duration_min"] = round(float(t_clean.iloc[-1] - t_clean.iloc[0]), 2)

    return df, meta


def plot_thermal_curves(df, channels=None, title="Adsorption Thermal Profile", fig=None):
    """
    Renders publication-grade multi-channel temperature vs time curves.
    """
    if fig is None:
        fig, ax = plt.subplots(figsize=(6.5, 5.0), dpi=100)
    else:
        fig.clear()
        ax = fig.add_subplot(111)

    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#ffffff")

    if channels is None:
        channels = [c for c in df.columns if c != "Time_min"]

    # OriginPro Style Color Palette
    cmap = plt.cm.get_cmap("tab20", max(len(channels), 1))

    for idx, ch in enumerate(channels):
        if ch in df.columns:
            line_width = 2.4 if ("7" in ch or "5" in ch or idx == len(channels)//2) else 1.3
            ax.plot(
                df["Time_min"], 
                df[ch], 
                label=ch, 
                color=cmap(idx), 
                linewidth=line_width,
                alpha=0.92
            )

    ax.set_title(title, fontsize=12, fontweight="bold", pad=12, color="#111111")
    ax.set_xlabel("Time (min)", fontsize=11, fontweight="bold", color="#111111")
    ax.set_ylabel("Temp (°C)", fontsize=11, fontweight="bold", color="#111111")

    # Spines & Grid
    for spine in ax.spines.values():
        spine.set_color("#222222")
        spine.set_linewidth(1.2)

    ax.tick_params(axis="both", which="both", direction="in", length=5, width=1.1, labelsize=9.5)
    ax.xaxis.set_minor_locator(ticker.AutoMinorLocator())
    ax.yaxis.set_minor_locator(ticker.AutoMinorLocator())
    ax.grid(True, linestyle=":", alpha=0.45, color="#888888")

    # Legend
    if len(channels) <= 16:
        ncols = 1 if len(channels) <= 8 else 2
        ax.legend(
            loc="upper right", 
            fontsize=8.5, 
            frameon=True, 
            edgecolor="#333333", 
            fancybox=False,
            ncol=ncols,
            labelspacing=0.25
        )

    fig.tight_layout()
    return fig


def plot_thermal_heatmap(df, channels=None, title="Adsorption Exotherm Heat Map", fig=None):
    """
    Renders 2D Spatio-Temporal Heatmap (Position vs Time) with Temperature colormap.
    """
    if fig is None:
        fig, ax = plt.subplots(figsize=(6.5, 5.0), dpi=100)
    else:
        fig.clear()
        ax = fig.add_subplot(111)

    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#ffffff")

    if channels is None:
        channels = [c for c in df.columns if c != "Time_min"]

    # Prepare 2D matrix
    mat = df[channels].to_numpy().T  # (channels, time_steps)
    times = df["Time_min"].to_numpy()

    cax = ax.imshow(
        mat, 
        aspect="auto", 
        cmap="turbo", 
        origin="lower",
        extent=[times.min(), times.max(), -0.5, len(channels) - 0.5]
    )

    ax.set_title(title, fontsize=12, fontweight="bold", pad=12, color="#111111")
    ax.set_xlabel("Time (min)", fontsize=11, fontweight="bold", color="#111111")
    ax.set_ylabel("Position / Channel", fontsize=11, fontweight="bold", color="#111111")

    ax.set_yticks(range(len(channels)))
    ax.set_yticklabels(channels, fontsize=8.5, fontweight="bold")
    ax.tick_params(axis="both", direction="out", labelsize=9)

    cbar = fig.colorbar(cax, ax=ax, pad=0.03)
    cbar.set_label("Temp (°C)", fontsize=10, fontweight="bold")
    cbar.ax.tick_params(labelsize=8.5)

    fig.tight_layout()
    return fig
