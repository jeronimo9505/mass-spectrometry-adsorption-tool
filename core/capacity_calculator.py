import numpy as np

def compute_co2_capacity_breakdown(
    ranges_list: list,
    mass_total_g: float,
    water_loss_pct: float,
    c0: float,
    flow_total_ml_min: float,
    temp_c: float,
    temp_ref_c: float = 25.0,
    vm_ref: float = 24465.0,
    s_baseline_a: float = None,
    k_mode: str = "per_cycle",
    ref_ads_mmol_g: float = 0.0,
    ref_des_mmol_g: float = 0.0
):
    """
    Computes rigorous physical adsorption and desorption capacities for CO2
    cycle by cycle with exact analytical breakdown identical to 'Zeolite rapeat alll calulations ads reference.xlsx'.

    Parameters:
      ranges_list: list of dicts with ROI regions (phases: 'baseline_signal', 'adsorption', 'desorption')
      mass_total_g: sample mass in grams
      water_loss_pct: water/binder loss percentage
      c0: CO2 feed concentration (e.g. 0.15)
      flow_total_ml_min: total flow rate (mL/min)
      temp_c: experimental temperature T2 (°C)
      temp_ref_c: reference temperature T1 (°C, default 25.0)
      vm_ref: molar volume at T1 (mL/mol, default 24465.0)
      s_baseline_a: optional manual baseline signal in Amperes
      k_mode: 'per_cycle' (rigorous cycle-specific k) or 'global_average' (Excel single average k)
      ref_ads_mmol_g: blank adsorption reference (mmol/g)
      ref_des_mmol_g: blank desorption reference (mmol/g)
    """
    # 1. Temperature & Molar Volume correction: Vm(T2) = Vm(T1) * (T2_K / T1_K)
    T1_K = temp_ref_c + 273.15
    T2_K = temp_c + 273.15
    Vm_exp = vm_ref * (T2_K / T1_K) if T1_K > 0 else vm_ref

    # 2. Total Molar Flow Rate: ntotal = F_total / Vm_exp (mol/min)
    n_total = (flow_total_ml_min / Vm_exp) if Vm_exp > 0 else 0.0

    # 3. Active dry mass: mass_active = mass_total * (1 - loss/100)
    mass_active_g = mass_total_g * (1.0 - (water_loss_pct / 100.0))

    # 4. Extract and pair baseline signals
    # Collect explicit baseline regions
    base_regions = [
        r for r in ranges_list 
        if r.get("phase") == "baseline_signal" or r.get("baseline") == "mean_signal"
    ]
    # Collect adsorption start baselines
    ads_start_baselines = [
        r.get("baseline_y0", 0.0)
        for r in ranges_list
        if r.get("phase") == "adsorption" and r.get("baseline_y0", 0.0) > 1e-12
    ]

    all_measured_baselines = []
    for b in base_regions:
        sig = b.get("mean_signal", b.get("baseline_y0", 0.0))
        if sig > 1e-12:
            all_measured_baselines.append(sig)
    if not all_measured_baselines:
        all_measured_baselines = ads_start_baselines

    # Compute global average baseline
    if all_measured_baselines:
        global_avg_baseline = sum(all_measured_baselines) / len(all_measured_baselines)
    else:
        global_avg_baseline = 7.726e-10

    # If manual baseline provided, override
    if s_baseline_a is not None and s_baseline_a > 1e-12:
        effective_global_baseline = s_baseline_a
    else:
        effective_global_baseline = global_avg_baseline

    global_k_factor = (c0 / effective_global_baseline) if effective_global_baseline > 0 else 0.0

    # 5. Process each peak (Adsorption and Desorption)
    breakdown_rows = []
    ads_rows = []
    des_rows = []

    # Map each peak to its cycle baseline
    for idx, r in enumerate(ranges_list):
        phase = r.get("phase", "adsorption")
        if phase == "baseline_signal" or r.get("baseline") == "mean_signal":
            continue  # Baseline regions are references, not capacity peaks

        type_name = r.get("type_name", f"ROI_{idx+1}")
        origin_area = float(r.get("calculated_area", 0.0))
        abs_area = abs(origin_area)

        # Determine cycle-specific baseline for this peak
        r_start = r.get("start_min", 0.0)
        cycle_base_sig = None

        if k_mode == "ads_first_point":
            # Baseline is strictly the first point (y1 / baseline_y0) of that cycle's Adsorption
            if phase == "adsorption":
                b0 = r.get("y1", r.get("baseline_y0", 0.0))
                if b0 > 1e-12:
                    cycle_base_sig = b0
            elif phase == "desorption":
                preceding_ads = [
                    a for a in ranges_list 
                    if a.get("phase") == "adsorption" and a.get("start_min", 0.0) < r_start
                ]
                if preceding_ads:
                    last_ads = preceding_ads[-1]
                    b0 = last_ads.get("y1", last_ads.get("baseline_y0", 0.0))
                    if b0 > 1e-12:
                        cycle_base_sig = b0
        elif k_mode == "baseline_plateau":
            # Use closest preceding baseline_signal region
            preceding_bases = [
                b for b in base_regions 
                if b.get("end_min", 0.0) <= r_start + 0.5
            ]
            if preceding_bases:
                last_base = preceding_bases[-1]
                cycle_base_sig = last_base.get("mean_signal", last_base.get("baseline_y0", 0.0))
        elif k_mode == "per_cycle":
            # 1. Look for closest preceding baseline_signal region
            preceding_bases = [
                b for b in base_regions 
                if b.get("end_min", 0.0) <= r_start + 0.5
            ]
            if preceding_bases:
                last_base = preceding_bases[-1]
                cycle_base_sig = last_base.get("mean_signal", last_base.get("baseline_y0", 0.0))
            
            # 2. If not found and this is adsorption, use its baseline_y0 or avg_baseline_val
            if (cycle_base_sig is None or cycle_base_sig <= 1e-12) and phase == "adsorption":
                b0 = r.get("avg_baseline_val", r.get("y1", r.get("baseline_y0", 0.0)))
                if b0 > 1e-12:
                    cycle_base_sig = b0

            # 3. If desorption, look for the adsorption of the same cycle
            if (cycle_base_sig is None or cycle_base_sig <= 1e-12) and phase == "desorption":
                preceding_ads = [
                    a for a in ranges_list 
                    if a.get("phase") == "adsorption" and a.get("start_min", 0.0) < r_start
                ]
                if preceding_ads:
                    last_ads = preceding_ads[-1]
                    b0 = last_ads.get("avg_baseline_val", last_ads.get("y1", last_ads.get("baseline_y0", 0.0)))
                    if b0 > 1e-12:
                        cycle_base_sig = b0

        # Fallback to manual input or global average if not found or if k_mode == 'global_average'
        if cycle_base_sig is None or cycle_base_sig <= 1e-12:
            if s_baseline_a is not None and s_baseline_a > 1e-12:
                cycle_base_sig = s_baseline_a
            else:
                cycle_base_sig = effective_global_baseline

        k_this_cycle = (c0 / cycle_base_sig) if cycle_base_sig > 0 else global_k_factor

        # Master equations:
        # nCO2 (mol) = ntotal * k * |A|
        # nCO2 (mmol) = nCO2 (mol) * 1000
        # q (mmol/g) 100% Mass = nCO2 (mmol) / mass_total_g
        # q (mmol/g) Dry Mass  = nCO2 (mmol) / mass_active_g
        n_mol = n_total * k_this_cycle * abs_area
        n_mmol = n_mol * 1000.0
        q_100 = (n_mmol / mass_total_g) if mass_total_g > 0 else 0.0
        q_dry = (n_mmol / mass_active_g) if mass_active_g > 0 else 0.0

        ref_val = ref_ads_mmol_g if phase == "adsorption" else ref_des_mmol_g
        q_net = q_dry - ref_val

        row_data = {
            "id": r.get("id", idx + 1),
            "type_name": type_name,
            "phase": phase,
            "origin_area": origin_area,
            "abs_area": abs_area,
            "s_baseline": cycle_base_sig,
            "k_factor": k_this_cycle,
            "n_mol": n_mol,
            "n_mmol": n_mmol,
            "q_100": q_100,
            "q_dry": q_dry,
            "q_net": q_net,
            "start_min": r.get("start_min", 0.0),
            "end_min": r.get("end_min", 0.0),
            "duration": r.get("duration", 0.0),
            "baseline_mode": r.get("baseline", "straight_line")
        }
        breakdown_rows.append(row_data)

        if phase == "adsorption":
            ads_rows.append(row_data)
        elif phase == "desorption":
            des_rows.append(row_data)

    # 6. Averages calculation
    def _calc_stats(row_list):
        if not row_list:
            return {
                "count": 0,
                "abs_area_mean": 0.0,
                "n_mmol_mean": 0.0,
                "q_100_mean": 0.0,
                "q_dry_mean": 0.0,
                "q_net_mean": 0.0,
                "k_mean": global_k_factor,
                "s_base_mean": effective_global_baseline
            }
        n = len(row_list)
        return {
            "count": n,
            "abs_area_mean": sum(x["abs_area"] for x in row_list) / n,
            "n_mmol_mean": sum(x["n_mmol"] for x in row_list) / n,
            "q_100_mean": sum(x["q_100"] for x in row_list) / n,
            "q_dry_mean": sum(x["q_dry"] for x in row_list) / n,
            "q_net_mean": sum(x["q_net"] for x in row_list) / n,
            "k_mean": sum(x["k_factor"] for x in row_list) / n,
            "s_base_mean": sum(x["s_baseline"] for x in row_list) / n
        }

    ads_stats = _calc_stats(ads_rows)
    des_stats = _calc_stats(des_rows)

    # Recovery Ratio (%) = (Average Des q_net / Average Ads q_net) * 100
    if ads_stats["q_net_mean"] > 0:
        recovery_pct = (des_stats["q_net_mean"] / ads_stats["q_net_mean"]) * 100.0
    elif ads_stats["q_dry_mean"] > 0:
        recovery_pct = (des_stats["q_dry_mean"] / ads_stats["q_dry_mean"]) * 100.0
    else:
        recovery_pct = 0.0

    return {
        "constants": {
            "T1_K": T1_K,
            "T2_K": T2_K,
            "temp_c": temp_c,
            "temp_ref_c": temp_ref_c,
            "Vm_25": vm_ref,
            "Vm_exp": round(Vm_exp, 2),
            "flow_total_ml_min": flow_total_ml_min,
            "n_total_mol_min": n_total,
            "s_baseline_a": effective_global_baseline,
            "k_factor": global_k_factor,
            "k_mode": k_mode,
            "mass_total_g": mass_total_g,
            "water_loss_pct": water_loss_pct,
            "mass_active_g": round(mass_active_g, 4),
            "c0": c0,
            "ref_ads_mmol_g": ref_ads_mmol_g,
            "ref_des_mmol_g": ref_des_mmol_g,
            "baselines_detected": all_measured_baselines
        },
        "rows": breakdown_rows,
        "averages": {
            "ads": ads_stats,
            "des": des_stats,
            "recovery_pct": round(recovery_pct, 2)
        }
    }


def compute_co2_capacity(
    mass_total_g: float,
    water_loss_pct: float,
    c0: float,
    flow_total_ml_min: float,
    temp_c: float,
    s_baseline_a: float,
    area_ads_a_min: float,
    area_des_a_min: float,
    ref_ads_mmol_g: float = 0.0,
    ref_des_mmol_g: float = 0.0
):
    """
    Backwards-compatible interface for single adsorption/desorption capacity calculation.
    """
    dummy_ranges = [
        {"id": 1, "type_name": "Adsorption", "phase": "adsorption", "calculated_area": area_ads_a_min, "baseline_y0": s_baseline_a},
        {"id": 2, "type_name": "Desorption", "phase": "desorption", "calculated_area": area_des_a_min, "baseline_y0": 0.0}
    ]
    res = compute_co2_capacity_breakdown(
        ranges_list=dummy_ranges,
        mass_total_g=mass_total_g,
        water_loss_pct=water_loss_pct,
        c0=c0,
        flow_total_ml_min=flow_total_ml_min,
        temp_c=temp_c,
        s_baseline_a=s_baseline_a,
        k_mode="global_average",
        ref_ads_mmol_g=ref_ads_mmol_g,
        ref_des_mmol_g=ref_des_mmol_g
    )

    ads_stat = res["averages"]["ads"]
    des_stat = res["averages"]["des"]

    return {
        "temp_c": temp_c,
        "Vm_exp": res["constants"]["Vm_exp"],
        "n_total_mol_min": res["constants"]["n_total_mol_min"],
        "k_factor": res["constants"]["k_factor"],
        "mass_total_g": mass_total_g,
        "water_loss_pct": water_loss_pct,
        "mass_active_g": res["constants"]["mass_active_g"],
        "c0": c0,
        "flow_total_ml_min": flow_total_ml_min,
        "s_baseline_a": res["constants"]["s_baseline_a"],
        "ref_ads_mmol_g": ref_ads_mmol_g,
        "ref_des_mmol_g": ref_des_mmol_g,
        "adsorption": {
            "area_a_min": ads_stat["abs_area_mean"],
            "n_mmol": round(ads_stat["n_mmol_mean"], 4),
            "q_raw_mmol_g": round(ads_stat["q_100_mean"], 4),
            "q_active_mmol_g": round(ads_stat["q_dry_mean"], 4),
            "q_net_mmol_g": round(ads_stat["q_net_mean"], 4)
        },
        "desorption": {
            "area_a_min": des_stat["abs_area_mean"],
            "n_mmol": round(des_stat["n_mmol_mean"], 4),
            "q_raw_mmol_g": round(des_stat["q_100_mean"], 4),
            "q_active_mmol_g": round(des_stat["q_dry_mean"], 4),
            "q_net_mmol_g": round(des_stat["q_net_mean"], 4)
        },
        "recovery_pct": res["averages"]["recovery_pct"],
        "breakdown": res
    }
