import numpy as np
import pandas as pd
import scipy.integrate as scipy_integ

def calculate_roi_integration(df, target_col, start_min, end_min, baseline_mode="straight_line", avg_baseline_val=None):
    """
    Computes OriginPro-identical Simpson integration and FWHM for a specified time range.
    
    Parameters:
      df: pandas DataFrame with Time_min and target_col
      target_col: column name (e.g. "'0/6'")
      start_min: start time in minutes
      end_min: end time in minutes
      baseline_mode: 'straight_line', 'horizontal_left', 'avg_ads_baseline', 'raw_zero'
      avg_baseline_val: float, optional baseline value for 'avg_ads_baseline'
      
    Returns:
      dict with: area, duration, baseline_y0, baseline_y1, baseline_y2, fwhm, peak_max, peak_time
    """
    if df is None or target_col not in df.columns:
        return {"area": 0.0, "duration": 0.0, "baseline_y0": 0.0, "fwhm": 0.0}

    t_min = df["Time_min"].values
    mask = (t_min >= start_min) & (t_min <= end_min)
    sub_df = df.loc[mask]

    if len(sub_df) < 3:
        return {"area": 0.0, "duration": abs(end_min - start_min), "baseline_y0": 0.0, "fwhm": 0.0}

    x_coords = sub_df["Time_min"].values
    y_raw = pd.to_numeric(sub_df[target_col], errors="coerce").values

    valid = ~(np.isnan(x_coords) | np.isnan(y_raw))
    x_coords = x_coords[valid]
    y_raw = y_raw[valid]

    if len(x_coords) < 3:
        return {"area": 0.0, "duration": abs(end_min - start_min), "baseline_y0": 0.0, "fwhm": 0.0}

    x1, x2 = x_coords[0], x_coords[-1]
    y1, y2 = y_raw[0], y_raw[-1]
    y_start_A = y1

    if baseline_mode == "straight_line":
        if x2 > x1:
            baseline_y = y1 + (y2 - y1) * (x_coords - x1) / (x2 - x1)
        else:
            baseline_y = np.full_like(y_raw, y1)
    elif baseline_mode == "horizontal_left":
        baseline_y = np.full_like(y_raw, y1)
    elif baseline_mode == "avg_ads_baseline":
        b_val = avg_baseline_val if avg_baseline_val is not None else y1
        baseline_y = np.full_like(y_raw, b_val)
        y_start_A = b_val
    else:  # raw_zero
        baseline_y = np.zeros_like(y_raw)
        y_start_A = 0.0

    y_subtracted = y_raw - baseline_y

    try:
        area_val = float(scipy_integ.simpson(y=y_subtracted, x=x_coords))
    except Exception:
        area_val = float(np.trapz(y_subtracted, x_coords))

    # Calculate FWHM
    fwhm_val = 0.0
    try:
        peak_sign = -1.0 if area_val < 0 else 1.0
        y_peak = y_subtracted * peak_sign
        max_idx = int(np.argmax(y_peak))
        peak_height = float(y_peak[max_idx])

        if peak_height > 1e-15:
            half_height = peak_height / 2.0
            left_mask = (x_coords <= x_coords[max_idx]) & (y_peak <= half_height)
            right_mask = (x_coords >= x_coords[max_idx]) & (y_peak <= half_height)

            left_x = x_coords[left_mask][-1] if np.any(left_mask) else x_coords[0]
            right_x = x_coords[right_mask][0] if np.any(right_mask) else x_coords[-1]
            fwhm_val = max(0.0, float(right_x - left_x))
    except Exception:
        fwhm_val = 0.0

    duration_val = float(abs(x2 - x1))
    return {
        "area": area_val,
        "duration": duration_val,
        "baseline_y0": float(y_start_A),
        "y1": float(y1),
        "y2": float(y2),
        "fwhm": round(fwhm_val, 4),
        "x1": float(x1),
        "x2": float(x2)
    }

def auto_detect_cycle_pairs(df, target_col="'0/6'"):
    """
    Scans mass spectrometry signal transitions to isolate Adsorption and Desorption cycles.
    """
    if df is None or target_col not in df.columns:
        return []

    t_min = df["Time_min"].values
    y_val = pd.to_numeric(df[target_col], errors="coerce").values

    med_val = np.median(y_val)
    is_low = y_val < (med_val * 0.7)

    transitions_down = np.where((is_low[:-1] == False) & (is_low[1:] == True))[0]
    transitions_up = np.where((is_low[:-1] == True) & (is_low[1:] == False))[0]

    if len(transitions_down) == 0 or len(transitions_up) == 0:
        return []

    detected_ranges = []
    cycle_num = 1

    for t_down_idx in transitions_down:
        t_down_min = t_min[t_down_idx]
        ups_after = [idx for idx in transitions_up if idx > t_down_idx]
        if not ups_after:
            continue
        t_up_idx = ups_after[0]
        t_up_min = t_min[t_up_idx]

        # 1. Adsorption (Yellow, Straight Line)
        detected_ranges.append({
            "id": len(detected_ranges) + 1,
            "type_name": f"C{cycle_num}_Ads",
            "phase": "adsorption",
            "start_min": round(float(t_down_min - 0.1), 2),
            "end_min": round(float(t_up_min - 0.1), 2),
            "baseline": "straight_line",
            "color": "#ffff99"
        })

        # 2. Desorption (Pink, Horizontal Line Y=Left)
        next_downs = [idx for idx in transitions_down if idx > t_up_idx]
        if next_downs:
            end_des_min = t_min[next_downs[0]] - 0.1
        else:
            end_des_min = min(t_up_min + 10.0, t_min[-1])

        detected_ranges.append({
            "id": len(detected_ranges) + 1,
            "type_name": f"C{cycle_num}_Des",
            "phase": "desorption",
            "start_min": round(float(t_up_min - 0.1), 2),
            "end_min": round(float(end_des_min), 2),
            "baseline": "horizontal_left",
            "color": "#ff99ff"
        })

        cycle_num += 1

    return detected_ranges
