import os
import io
import pandas as pd
import numpy as np

# Gas Channel Mapping for Quadrupole Mass Spectrometry
GAS_MAPPING = {
    "'0/0'": {"id": "N", "label": "N+ (m/z 14.13)", "full_name": "N+ / N2++ (Atomic Nitrogen)", "color": "#1f77b4"},
    "'0/1'": {"id": "O", "label": "O+ (m/z 16.13)", "full_name": "O+ (Atomic Oxygen)", "color": "#ff7f0e"},
    "'0/2'": {"id": "H2O", "label": "H2O (m/z 18.16)", "full_name": "H2O (Water Vapor)", "color": "#2ca02c"},
    "'0/3'": {"id": "N2", "label": "N2 / CO (m/z 28.19)", "full_name": "N2 / CO (Molecular Nitrogen)", "color": "#d62728"},
    "'0/4'": {"id": "O2", "label": "O2 (m/z 32.22)", "full_name": "O2 (Molecular Oxygen)", "color": "#9467bd"},
    "'0/5'": {"id": "Ar", "label": "Ar (m/z 40.22)", "full_name": "Ar (Argon)", "color": "#8c564b"},
    "'0/6'": {"id": "CO2", "label": "CO2 (m/z 44.28)", "full_name": "CO2 (Carbon Dioxide)", "color": "#e377c2"}
}

def load_asc_dataframe(fpath):
    """
    Load and parse a multi-channel MID mass spectrometry .asc file.
    Handles legacy Mac carriage returns ('\\r') and extracts assay metadata.
    
    Returns:
        tuple: (df, info_dict)
    """
    if not os.path.exists(fpath):
        raise FileNotFoundError(f"File not found: {fpath}")

    with open(fpath, "rb") as f:
        raw_bytes = f.read()

    text = raw_bytes.decode("utf-8", errors="ignore")
    # Normalize carriage returns
    content = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = content.split("\n")

    date_str = "-"
    time_str = "-"
    total_cycles = "-"

    for line in lines[:18]:
        l_strip = line.strip()
        if "DATE :" in l_strip:
            parts = l_strip.split("DATE :")[1].split("TIME :")
            date_str = parts[0].strip()
            if len(parts) > 1:
                time_str = parts[1].strip()
        elif "CONVERTED CYCLES :" in l_strip:
            total_cycles = l_strip.split("CONVERTED CYCLES :")[1].strip()

    # Data matrix starts at line 19 (skiprows=18)
    df = pd.read_csv(io.StringIO(content), skiprows=18, sep="\t")
    # Clean trailing or unnamed columns
    df = df.loc[:, ~df.columns.str.contains("^Unnamed")]
    df.columns = [c.strip() for c in df.columns]

    # Process time axes
    if "RelTime[s]" in df.columns:
        df["Time_sec"] = pd.to_numeric(df["RelTime[s]"], errors="coerce")
    elif "Cycle" in df.columns:
        df["Time_sec"] = pd.to_numeric(df["Cycle"], errors="coerce")
    else:
        df["Time_sec"] = np.arange(len(df), dtype=float)

    df["Time_min"] = df["Time_sec"] / 60.0

    duration_sec = float(df["Time_sec"].max()) if not df.empty else 0.0
    duration_min = duration_sec / 60.0

    info = {
        "filename": os.path.basename(fpath),
        "filepath": os.path.abspath(fpath),
        "date": date_str,
        "time": time_str,
        "cycles": total_cycles if total_cycles != "-" else str(len(df)),
        "row_count": len(df),
        "duration_min": round(duration_min, 2),
        "duration_h": round(duration_min / 60.0, 2)
    }

    return df, info
