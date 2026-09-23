def compute_co2_capacity(
    mass_total_g: float,
    water_loss_pct: float,
    c0: float,
    flow_total_ml_min: float,
    temp_c: float,
    s_baseline_a: float,
    area_ads_a_min: float,
    area_des_a_min: float,
    ref_ads_mmol_g: float = 0.23,
    ref_des_mmol_g: float = 0.00
):
    """
    Computes rigorous physical adsorption and desorption capacities for CO2.
    Formula identical to analytical model in 'ZZ 30 Ads des final.xlsx'.
    """
    # 1. Temperature & Molar Volume correction
    T1_K = 25.0 + 273.15
    T2_K = temp_c + 273.15
    Vm_25 = 24465.0  # mL/mol
    Vm_exp = Vm_25 * (T2_K / T1_K)

    # 2. Total Molar Flow Rate
    n_total = (flow_total_ml_min / Vm_exp) if Vm_exp > 0 else 0.0  # mol/min

    # 3. Calibration factor k
    k_factor = (c0 / s_baseline_a) if s_baseline_a > 0 else 0.0  # A^-1

    # 4. Active mass (deducting water/binder loss percentage)
    mass_active_g = mass_total_g * (1.0 - (water_loss_pct / 100.0))

    # 5. Adsorption capacity calculations
    # Area ads is negative (gas consumed), take absolute magnitude
    abs_area_ads = abs(area_ads_a_min)
    n_mol_ads = n_total * k_factor * abs_area_ads
    n_mmol_ads = n_mol_ads * 1000.0
    q_raw_ads = (n_mmol_ads / mass_total_g) if mass_total_g > 0 else 0.0
    q_act_ads = (n_mmol_ads / mass_active_g) if mass_active_g > 0 else 0.0
    q_net_ads = q_act_ads - ref_ads_mmol_g

    # 6. Desorption capacity calculations
    abs_area_des = abs(area_des_a_min)
    n_mol_des = n_total * k_factor * abs_area_des
    n_mmol_des = n_mol_des * 1000.0
    q_raw_des = (n_mmol_des / mass_total_g) if mass_total_g > 0 else 0.0
    q_act_des = (n_mmol_des / mass_active_g) if mass_active_g > 0 else 0.0
    q_net_des = q_act_des - ref_des_mmol_g

    # 7. Desorption Recovery Ratio
    recovery_pct = (q_net_des / q_net_ads * 100.0) if q_net_ads > 0 else 0.0

    return {
        "temp_c": temp_c,
        "Vm_exp": round(Vm_exp, 2),
        "n_total_mol_min": n_total,
        "k_factor": k_factor,
        "mass_total_g": mass_total_g,
        "water_loss_pct": water_loss_pct,
        "mass_active_g": round(mass_active_g, 4),
        "c0": c0,
        "flow_total_ml_min": flow_total_ml_min,
        "s_baseline_a": s_baseline_a,
        "ref_ads_mmol_g": ref_ads_mmol_g,
        "ref_des_mmol_g": ref_des_mmol_g,
        "adsorption": {
            "area_a_min": abs_area_ads,
            "n_mmol": round(n_mmol_ads, 4),
            "q_raw_mmol_g": round(q_raw_ads, 4),
            "q_active_mmol_g": round(q_act_ads, 4),
            "q_net_mmol_g": round(q_net_ads, 4)
        },
        "desorption": {
            "area_a_min": abs_area_des,
            "n_mmol": round(n_mmol_des, 4),
            "q_raw_mmol_g": round(q_raw_des, 4),
            "q_active_mmol_g": round(q_act_des, 4),
            "q_net_mmol_g": round(q_net_des, 4)
        },
        "recovery_pct": round(recovery_pct, 2)
    }
