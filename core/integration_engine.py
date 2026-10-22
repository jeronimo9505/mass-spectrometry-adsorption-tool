import numpy as np
import pandas as pd
import scipy.integrate as scipy_integ
from scipy.signal import find_peaks

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

    if baseline_mode == "mean_signal":
        mean_val = float(np.mean(y_raw))
        return {
            "area": 0.0,
            "mean_signal": mean_val,
            "duration": float(abs(x2 - x1)),
            "baseline_y0": mean_val,
            "y1": float(y1),
            "y2": float(y2),
            "fwhm": 0.0,
            "x1": float(x1),
            "x2": float(x2)
        }

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

def auto_detect_cycle_pairs(df, target_col="'0/6'", dt_ads=10.0, dt_des=8.0, dt_base=2.0):
    """
    Intelligently identifies Adsorption and Desorption cycles by detecting the acute
    breakthrough drop minima from the 15% CO2 baseline, placing suggested Base, Ads,
    and Des bands according to experimental standard durations.
    """
    if df is None or target_col not in df.columns:
        return []

    t = df["Time_min"].values
    y = np.maximum(0.0, pd.to_numeric(df[target_col], errors="coerce").fillna(0.0).values)
    y_max = np.percentile(y, 99)
    if y_max <= 1e-12:
        return []

    dt_avg = np.median(np.diff(t))
    pts_03min = max(2, int(0.3 / dt_avg))

    # 1. Detect acute V-shaped minima (Picos de caida agudos)
    # Rejects flat zero plateaus (mesetas) using dwell time and immediate breakthrough rebound
    acute_minima = []
    for i in range(int(1.0 / dt_avg), len(y) - int(1.0 / dt_avg)):
        if y[i] < 0.15 * y_max and y[i] == np.min(y[max(0, i - pts_03min) : min(len(y), i + pts_03min + 1)]):
            w_start = max(0, i - int(2.5 / dt_avg))
            prior_max = np.max(y[w_start:i])
            if prior_max > 0.50 * y_max and (prior_max - y[i]) > 0.40 * y_max:
                # Dwell time near zero (< 0.05 * y_max): acute dip must dwell < 0.35 min
                dwell_pts = 0
                for k in range(i, min(len(y), i + int(1.5 / dt_avg))):
                    if y[k] < 0.05 * y_max:
                        dwell_pts += 1
                    else:
                        break
                dwell_time = dwell_pts * dt_avg

                # Rebound at +0.6 min: breakthrough must be strongly ascending
                idx_06 = min(len(y) - 1, i + int(0.6 / dt_avg))
                rebound_val = y[idx_06]

                # Immediate positive derivative
                idx_03 = min(len(y) - 1, i + int(0.3 / dt_avg))
                post_slope = (y[idx_03] - y[i]) / max(1e-4, t[idx_03] - t[i])

                if dwell_time < 0.35 and rebound_val > 0.15 * y_max and post_slope > 1e-10:
                    acute_minima.append(i)

    # Cluster only jitter of the exact same vertex (< 2.5 min)
    # Does NOT cap or hardcode the number of cycles (supports any arbitrary n cycles)
    cycle_min_indices = []
    for idx in acute_minima:
        if not cycle_min_indices:
            cycle_min_indices.append(idx)
        else:
            if (t[idx] - t[cycle_min_indices[-1]]) < 2.5:
                if y[idx] < y[cycle_min_indices[-1]]:
                    cycle_min_indices[-1] = idx
            else:
                cycle_min_indices.append(idx)

    detected_ranges = []
    t_max = float(t[-1])

    for cycle_num, min_idx in enumerate(cycle_min_indices, 1):
        # 2. Find onset of drop (highest baseline point right before plunge)
        w_start = max(0, min_idx - int(2.5 / dt_avg))
        local_base = np.percentile(y[w_start:min_idx], 95)

        # Find shoulder where steep plunge starts
        shoulder_idx = min_idx
        for j in range(min_idx, w_start, -1):
            if y[j] >= 0.99 * local_base:
                shoulder_idx = j
                break

        # Highest baseline point in a 0.35 min window around/before shoulder
        t_sh = t[shoulder_idx]
        w_hi = (t >= t_sh - 0.35) & (t <= t_sh + 0.05)
        sub_t_hi = t[w_hi]
        sub_y_hi = y[w_hi]
        if len(sub_y_hi) > 0:
            hi_idx = np.argmax(sub_y_hi)
            onset_t = round(float(sub_t_hi[hi_idx]), 2)
        else:
            onset_t = round(float(t_sh), 2)

        if onset_t >= t_max - 1.0:
            continue

        # Next cycle onset if any (prevents overlapping into next cycle)
        next_onset = t_max
        if cycle_num < len(cycle_min_indices):
            next_min_idx = cycle_min_indices[cycle_num]
            next_onset = float(t[next_min_idx] - 2.5)

        # 3. Create Baseline Region (dt_base before Ads onset)
        base_end = round(max(0.2, onset_t - 0.15), 2)
        base_start = round(max(0.0, base_end - dt_base), 2)
        m_base = (t >= base_start) & (t <= base_end)
        avg_base_val = float(np.mean(y[m_base])) if np.any(m_base) else float(local_base)

        if base_end > base_start:
            detected_ranges.append({
                "id": len(detected_ranges) + 1,
                "type_name": f"Bas_{len(detected_ranges) + 1}",
                "phase": "baseline_signal",
                "start_min": base_start,
                "end_min": base_end,
                "baseline": "mean_signal",
                "color": "#cce5ff",
                "mean_signal": avg_base_val
            })

        # 4. Search for Desorption Region First
        # Window starts from onset_t + max(5.0, dt_ads - 2.5) to avoid missing early takeoff
        des_search_start = onset_t + max(5.0, dt_ads - 2.5)
        des_search_end = min(t_max, onset_t + dt_ads + 8.0, next_onset)
        m_des_search = (t >= des_search_start) & (t <= des_search_end)
        sub_t_des = t[m_des_search]
        sub_y_des = y[m_des_search]

        des_start = round(onset_t + dt_ads, 2)
        des_end = round(min(t_max, des_start + dt_des, next_onset), 2)

        if len(sub_y_des) > 5:
            # Find the acute desorption peak
            pks, _ = find_peaks(sub_y_des, prominence=max(2e-11, 0.04 * y_max), distance=max(2, int(0.4 / dt_avg)))
            first_pk_idx = pks[0] if len(pks) > 0 else np.argmax(sub_y_des)
            first_pk_t = float(sub_t_des[first_pk_idx])
            first_pk_val = float(sub_y_des[first_pk_idx])

            # Measure flat breakthrough plateau before the desorption spike
            m_plat = (t >= first_pk_t - 2.2) & (t <= first_pk_t - 0.6)
            plat_mean = float(np.mean(y[m_plat])) if np.any(m_plat) else avg_base_val
            plat_std = float(np.std(y[m_plat])) if np.any(m_plat) else 1e-12

            # Find forward takeoff point ("jider sy bilkul peak uper jati hai")
            m_takeoff = (t >= first_pk_t - 1.2) & (t <= first_pk_t)
            t_takeoff = t[m_takeoff]
            y_takeoff = y[m_takeoff]
            rise_thresh = plat_mean + max(2.2 * plat_std, 1.2e-12)

            found_takeoff = None
            pts_015 = max(3, int(0.15 / dt_avg))
            for idx_to in range(len(t_takeoff)):
                if y_takeoff[idx_to] > rise_thresh:
                    # Initial takeoff begins right at the foot (~0.15 min before steep threshold crossing)
                    foot_idx = max(0, idx_to - pts_015)
                    found_takeoff = t_takeoff[foot_idx]
                    break

            if found_takeoff is not None:
                des_start = round(float(found_takeoff), 2)
            else:
                des_start = round(float(first_pk_t - 0.25), 2)

            # Locate return to zero floor, capped at dt_des
            max_des_end = min(t_max, des_start + dt_des, next_onset)
            m_tail = (t >= first_pk_t) & (t <= max_des_end + 0.2)
            tail_t = t[m_tail]
            tail_y = y[m_tail]
            if len(tail_y) > 0:
                floor_val = float(np.min(tail_y))
                zero_thresh = max(1.5e-13, floor_val + 6.0e-14, 0.0004 * y_max)
                zero_found_t = max_des_end
                for idx_m in range(len(tail_t)):
                    if tail_t[idx_m] - first_pk_t > 0.8:
                        if tail_y[idx_m] <= zero_thresh:
                            if np.all(tail_y[idx_m:min(len(tail_y), idx_m + 3)] <= zero_thresh * 1.5):
                                zero_found_t = float(tail_t[idx_m])
                                break
                des_end = round(min(max_des_end, zero_found_t), 2)
                if des_end < des_start + 1.5:
                    des_end = round(min(t_max, des_start + min(5.0, dt_des)), 2)

        # 5. Create Adsorption Region (ends right where Desorption takes off, capped at dt_ads)
        ads_start = onset_t
        ads_end = round(min(des_start, ads_start + dt_ads), 2)
        if ads_end > ads_start + 0.5:
            detected_ranges.append({
                "id": len(detected_ranges) + 1,
                "type_name": f"Ads_{len(detected_ranges) + 1}",
                "phase": "adsorption",
                "start_min": ads_start,
                "end_min": ads_end,
                "baseline": "avg_ads_baseline",
                "avg_baseline_val": avg_base_val,
                "color": "#ffff99"
            })

        # 6. Create Desorption Region (from takeoff to zero floor, raw_zero baseline)
        if des_end > des_start + 0.5:
            detected_ranges.append({
                "id": len(detected_ranges) + 1,
                "type_name": f"Des_{len(detected_ranges) + 1}",
                "phase": "desorption",
                "start_min": des_start,
                "end_min": des_end,
                "baseline": "raw_zero",
                "color": "#ff99ff"
            })

    return detected_ranges
