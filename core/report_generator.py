import os
import csv
import json
import pandas as pd
import numpy as np

def export_highres_figures(fig, sample_id, reports_dir):
    """
    Renders and saves publication-quality 600 DPI and 1200 DPI PNG figures
    directly into the sample's backend reports directory.
    """
    os.makedirs(reports_dir, exist_ok=True)
    p_600 = os.path.join(reports_dir, f"{sample_id}_MS_plot_600dpi.png")
    p_1200 = os.path.join(reports_dir, f"{sample_id}_MS_plot_1200dpi.png")

    try:
        fig.savefig(p_600, dpi=600, bbox_inches="tight", facecolor=fig.get_facecolor(), edgecolor="none")
    except Exception as e:
        p_600 = None

    try:
        fig.savefig(p_1200, dpi=1200, bbox_inches="tight", facecolor=fig.get_facecolor(), edgecolor="none")
    except Exception as e:
        p_1200 = None

    return {"600_dpi": p_600, "1200_dpi": p_1200}


def generate_comprehensive_report(sample_id, metadata, file_info, capacity_results, ranges_list, reports_dir, fig=None):
    """
    Generates a complete, publication-grade analytical report package for the material:
      1. 600 DPI & 1200 DPI PNG Figures
      2. Interactive, styled HTML report (with embedded high-res chromatogram, tables, equations)
      3. Plain text report (.txt)
      4. Excel-ready CSV analytical breakdown table (.csv)
    """
    os.makedirs(reports_dir, exist_ok=True)

    # 1. Export High-Res Figures if figure canvas provided
    img_paths = {}
    if fig is not None:
        img_paths = export_highres_figures(fig, sample_id, reports_dir)

    consts = capacity_results.get("constants", {})
    avgs = capacity_results.get("averages", {})
    rows = capacity_results.get("rows", [])
    ads_stat = avgs.get("ads", {})
    des_stat = avgs.get("des", {})

    m_tot = consts.get("mass_total_g", metadata.get("mass_total_g", 0.3785))
    m_tot_mg = m_tot * 1000.0
    w_pct = consts.get("water_loss_pct", metadata.get("water_loss_pct", 21.4))
    m_act = consts.get("mass_active_g", m_tot * (1.0 - w_pct / 100.0))
    m_act_mg = m_act * 1000.0

    c0 = consts.get("c0", 0.15)
    flow_tot = consts.get("flow_total_ml_min", 100.0)
    temp_c = consts.get("temp_c", 24.0)
    temp_ref = consts.get("temp_ref_c", 25.0)
    vm_ref = consts.get("Vm_25", 24465.0)
    vm_exp = consts.get("Vm_exp", 24382.9)
    n_tot = consts.get("n_total_mol_min", 4.1012e-3)
    s_base = consts.get("s_baseline_a", 7.5482e-10)
    k_fact = consts.get("k_factor", 1.987e8)
    k_mode = consts.get("k_mode", "global_average")

    q_ads_100 = ads_stat.get("q_100_mean", 0.0)
    q_ads_dry = ads_stat.get("q_dry_mean", 0.0)
    q_des_100 = des_stat.get("q_100_mean", 0.0)
    q_des_dry = des_stat.get("q_dry_mean", 0.0)
    rec_pct = avgs.get("recovery_pct", 0.0)

    mat_name = metadata.get("material_name", "ZZ 10 B6 Zeolite")
    operator = metadata.get("operator", "Shayan")
    meas_date = file_info.get("date", metadata.get("date", "2026-09-01"))
    src_file = file_info.get("filename", metadata.get("source_file", "-"))

    # 2. Generate CSV Breakdown Table (Matching Image 3 Excel format)
    csv_path = os.path.join(reports_dir, f"co2_breakdown_{sample_id}.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Sample ID", sample_id])
        writer.writerow(["Material Name", mat_name])
        writer.writerow(["Total Mass (mg)", f"{m_tot_mg:.1f}"])
        writer.writerow(["Total Mass (g)", f"{m_tot:.4f}"])
        writer.writerow(["Water Loss (%)", f"{w_pct:.1f}"])
        writer.writerow(["Dry Mass (mg)", f"{m_act_mg:.3f}"])
        writer.writerow(["Dry Mass (g)", f"{m_act:.6f}"])
        writer.writerow(["Feed C0", f"{c0:.2f}"])
        writer.writerow(["Total Flow (mL/min)", f"{flow_tot:.1f}"])
        writer.writerow(["Temperature T2 (°C)", f"{temp_c:.1f}"])
        writer.writerow([])
        writer.writerow([
            "Step", "Origin Area (A*min)", "|A| (A*min)", "S_base (A)", "k (A^-1)",
            "nCO2 (mol)", "nCO2 (mmol)", "q (mmol/g) 100% Mass", "q (mmol/g) (Dry Mass)",
            "FWHM (min)", "Duration (min)"
        ])
        for r in rows:
            writer.writerow([
                r["type_name"],
                f"{r['origin_area']:.4e}",
                f"{r['abs_area']:.4e}",
                f"{r['s_baseline']:.4e}",
                f"{r['k_factor']:.3e}",
                f"{r['n_mol']:.4e}",
                f"{r['n_mmol']:.4f}",
                f"{r['q_100']:.4f}",
                f"{r['q_dry']:.4f}",
                f"{r.get('fwhm', 0.0):.4f}",
                f"{r.get('duration', 0.0):.2f}"
            ])
        writer.writerow([])
        writer.writerow(["AVERAGES"])
        writer.writerow(["Adsorption q (100% Mass)", f"{q_ads_100:.4f}", "mmol/g"])
        writer.writerow(["Adsorption q (Dry Mass)", f"{q_ads_dry:.4f}", "mmol/g"])
        writer.writerow(["Desorption q (100% Mass)", f"{q_des_100:.4f}", "mmol/g"])
        writer.writerow(["Desorption q (Dry Mass)", f"{q_des_dry:.4f}", "mmol/g"])
        writer.writerow(["Desorption Recovery", f"{rec_pct:.2f}", "%"])

    # 3. Generate Plain Text Report (.txt)
    txt_path = os.path.join(reports_dir, f"co2_report_{sample_id}.txt")
    txt_lines = [
        "=" * 85,
        f"   MASS SPECTROMETRY CO2 ADSORPTION / DESORPTION REPORT — {mat_name}",
        "=" * 85,
        f"Sample ID:                 {sample_id}",
        f"Material Name:             {mat_name}",
        f"Operator:                  {operator}",
        f"Measurement Date:          {meas_date}",
        f"Measurement File:          {src_file}",
        "-" * 85,
        "1. EXPERIMENTAL MASS & OPERATING INPUTS (EXCEL MODEL):",
        f"  - Weighed Sample Mass:   {m_tot_mg:.1f} mg  ({m_tot:.4f} g)",
        f"  - Water / Binder Loss:   {w_pct:.1f} %",
        f"  - Dry (Active) Mass:     {m_act_mg:.3f} mg  ({m_act:.6f} g)",
        f"  - Feed Fraction C0:      {c0:.2f} (15% CO2 / 85% N2)",
        f"  - Total Gas Flow:        {flow_tot:.1f} mL/min",
        f"  - Temperature:           T2 = {temp_c:.1f} °C (Ref T1 = {temp_ref:.1f} °C)",
        f"  - Molar Volume Vm:       Vm,25 = {vm_ref:.1f} mL/mol  |  Vm,exp = {vm_exp:.1f} mL/mol",
        f"  - Total Molar Flow Rate: {n_tot:.4e} mol/min",
        f"  - Baseline S_base:       {s_base:.4e} A  (Sensitivity k = {k_fact:.3e} A⁻¹)",
        f"  - Baseline Mode:         {k_mode}",
        "-" * 85,
        "2. PERFORMANCE CAPACITY SUMMARY:",
        f"  - Average Adsorption q:  {q_ads_dry:.4f} mmol/g (Dry Mass)  |  {q_ads_100:.4f} mmol/g (100% Mass)",
        f"  - Average Desorption q:  {q_des_dry:.4f} mmol/g (Dry Mass)  |  {q_des_100:.4f} mmol/g (100% Mass)",
        f"  - Desorption Recovery:   {rec_pct:.2f} %",
        "-" * 85,
        "3. CYCLE-BY-CYCLE ANALYTICAL BREAKDOWN (MATCHING ORIGIN & EXCEL):",
        f"  {'Step':<8} {'Origin Area':<13} {'|A| (A·min)':<13} {'S_base (A)':<12} {'k (A⁻¹)':<11} {'nCO2 (mmol)':<12} {'q(100%)':<10} {'q(Dry)':<10}"
    ]
    for r in rows:
        txt_lines.append(
            f"  {r['type_name']:<8} {r['origin_area']:<13.4e} {r['abs_area']:<13.4e} {r['s_baseline']:<12.4e} {r['k_factor']:<11.3e} {r['n_mmol']:<12.4f} {r['q_100']:<10.4f} {r['q_dry']:<10.4f}"
        )
    txt_lines.extend([
        "-" * 85,
        "4. HIGH-RESOLUTION ARTIFACTS:",
        f"  - 600 DPI Print Image:   {img_paths.get('600_dpi', 'N/A')}",
        f"  - 1200 DPI Master Image: {img_paths.get('1200_dpi', 'N/A')}",
        f"  - Excel CSV Table:       {csv_path}",
        "=" * 85
    ])
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(txt_lines))

    # 4. Generate Interactive, Styled HTML Report
    html_path = os.path.join(reports_dir, f"co2_report_{sample_id}.html")
    
    # Relative path for embedded image if available
    img_tag = ""
    if img_paths.get("600_dpi") and os.path.exists(img_paths["600_dpi"]):
        rel_img = os.path.basename(img_paths["600_dpi"])
        img_tag = f"""
        <div class="card figure-card">
            <h3>📈 Multi-Cycle Mass Spectrometry Chromatogram & ROI Shading (600 DPI)</h3>
            <div class="img-container">
                <img src="{rel_img}" alt="Mass Spectrometry Chromatogram" class="responsive-img"/>
            </div>
            <p class="fig-caption">Figure: Continuous Multi-Cycle Adsorption (yellow fill) and Desorption (pink fill) Simpson Composite Integration.</p>
        </div>
        """

    # Build rows HTML
    rows_html = ""
    for r in rows:
        is_ads = "Ads" in r["type_name"]
        badge_cls = "badge-ads" if is_ads else "badge-des"
        rows_html += f"""
        <tr>
            <td><span class="badge {badge_cls}">{r['type_name']}</span></td>
            <td><code>{r['origin_area']:.4e}</code></td>
            <td><code>{r['abs_area']:.4e}</code></td>
            <td><code>{r['s_baseline']:.4e}</code></td>
            <td><code>{r['k_factor']:.3e}</code></td>
            <td>{r['n_mol']:.4e}</td>
            <td><strong>{r['n_mmol']:.4f}</strong></td>
            <td>{r['q_100']:.4f}</td>
            <td class="highlight-val"><strong>{r['q_dry']:.4f}</strong></td>
        </tr>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CO2 Adsorption/Desorption Report — {sample_id} ({mat_name})</title>
    <style>
        :root {{
            --primary: #1d3557;
            --accent: #457b9d;
            --success: #2a9d8f;
            --warm: #e76f51;
            --bg: #f8f9fa;
            --card-bg: #ffffff;
            --border: #e2e8f0;
            --text: #2d3748;
            --text-light: #718096;
        }}
        body {{
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
            background-color: var(--bg);
            color: var(--text);
            margin: 0;
            padding: 24px;
            line-height: 1.5;
        }}
        .container {{
            max-width: 1100px;
            margin: 0 auto;
        }}
        .header {{
            background: linear-gradient(135deg, #1d3557 0%, #457b9d 100%);
            color: white;
            padding: 28px 32px;
            border-radius: 12px;
            box-shadow: 0 4px 14px rgba(0,0,0,0.1);
            margin-bottom: 24px;
        }}
        .header h1 {{
            margin: 0 0 8px 0;
            font-size: 24px;
            letter-spacing: -0.5px;
        }}
        .header-meta {{
            display: flex;
            flex-wrap: wrap;
            gap: 16px;
            font-size: 13px;
            opacity: 0.95;
            margin-top: 12px;
        }}
        .header-meta span {{
            background: rgba(255,255,255,0.15);
            padding: 4px 10px;
            border-radius: 6px;
        }}
        .grid-summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}
        .stat-card {{
            background: var(--card-bg);
            padding: 20px;
            border-radius: 10px;
            border: 1px solid var(--border);
            box-shadow: 0 2px 6px rgba(0,0,0,0.03);
            text-align: center;
        }}
        .stat-card .label {{
            font-size: 12px;
            color: var(--text-light);
            text-transform: uppercase;
            font-weight: 600;
            letter-spacing: 0.5px;
        }}
        .stat-card .value {{
            font-size: 26px;
            font-weight: 700;
            color: var(--primary);
            margin: 6px 0;
        }}
        .stat-card .sub {{
            font-size: 11px;
            color: var(--text-light);
        }}
        .card {{
            background: var(--card-bg);
            border-radius: 10px;
            border: 1px solid var(--border);
            padding: 24px;
            margin-bottom: 24px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.03);
        }}
        .card h3 {{
            margin-top: 0;
            margin-bottom: 16px;
            font-size: 17px;
            color: var(--primary);
            border-bottom: 2px solid #edf2f7;
            padding-bottom: 8px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}
        th, td {{
            padding: 10px 12px;
            text-align: right;
            border-bottom: 1px solid var(--border);
        }}
        th {{
            background-color: #f1f5f9;
            color: var(--primary);
            font-weight: 600;
        }}
        th:first-child, td:first-child {{
            text-align: left;
        }}
        tr:hover {{
            background-color: #f8fafc;
        }}
        .highlight-val {{
            color: #1d3557;
            background-color: #f0fdf4;
        }}
        .badge {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: bold;
        }}
        .badge-ads {{
            background-color: #fef08a;
            color: #854d0e;
        }}
        .badge-des {{
            background-color: #fbcfe8;
            color: #9d174d;
        }}
        .params-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 16px;
            font-size: 13px;
        }}
        .param-row {{
            display: flex;
            justify-content: space-between;
            padding: 6px 0;
            border-bottom: 1px dashed #edf2f7;
        }}
        .param-row .p-name {{
            color: var(--text-light);
        }}
        .param-row .p-val {{
            font-weight: 600;
        }}
        .figure-card {{
            text-align: center;
        }}
        .img-container {{
            max-width: 100%;
            overflow: hidden;
            border-radius: 8px;
            border: 1px solid var(--border);
            margin: 12px 0;
            background: white;
        }}
        .responsive-img {{
            max-width: 100%;
            height: auto;
            display: block;
            margin: 0 auto;
        }}
        .fig-caption {{
            font-size: 12px;
            color: var(--text-light);
            margin-top: 6px;
        }}
        .footer {{
            text-align: center;
            font-size: 12px;
            color: var(--text-light);
            padding: 16px 0 24px 0;
        }}
        code {{
            background: #f1f5f9;
            padding: 2px 4px;
            border-radius: 4px;
            font-family: Consolas, monospace;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <h1>📑 Mass Spectrometry CO₂ Adsorption & Desorption Analysis</h1>
            <div style="font-size: 15px; font-weight: 500;">{mat_name} &nbsp;—&nbsp; Sample <code>{sample_id}</code></div>
            <div class="header-meta">
                <span>👤 Operator: <strong>{operator}</strong></span>
                <span>📅 Date: <strong>{meas_date}</strong></span>
                <span>📁 File: <strong>{src_file}</strong></span>
                <span>🔬 Instrument: <strong>Quadrupole MID Mass Spectrometer</strong></span>
            </div>
        </div>

        <!-- Key Performance Indicators (Cards) -->
        <div class="grid-summary">
            <div class="stat-card">
                <div class="label">Adsorption Capacity (Dry)</div>
                <div class="value">{q_ads_dry:.3f} <span style="font-size: 15px; font-weight: normal;">mmol/g</span></div>
                <div class="sub">100% Mass: {q_ads_100:.3f} mmol/g</div>
            </div>
            <div class="stat-card">
                <div class="label">Desorption Capacity (Dry)</div>
                <div class="value">{q_des_dry:.3f} <span style="font-size: 15px; font-weight: normal;">mmol/g</span></div>
                <div class="sub">100% Mass: {q_des_100:.3f} mmol/g</div>
            </div>
            <div class="stat-card">
                <div class="label">Desorption Recovery</div>
                <div class="value" style="color: {'#2a9d8f' if rec_pct >= 95 else '#e76f51'};">{rec_pct:.1f} %</div>
                <div class="sub">Cyclic regeneration efficiency</div>
            </div>
            <div class="stat-card">
                <div class="label">Active Dry Mass</div>
                <div class="value">{m_act_mg:.1f} <span style="font-size: 15px; font-weight: normal;">mg</span></div>
                <div class="sub">Weighed: {m_tot_mg:.1f} mg (Water: {w_pct:.1f}%)</div>
            </div>
        </div>

        <!-- Chromatogram Figure -->
        {img_tag}

        <!-- Cycle Breakdown Table -->
        <div class="card">
            <h3>📊 Cycle-by-Cycle Analytical Breakdown (Excel Model)</h3>
            <div style="overflow-x: auto;">
                <table>
                    <thead>
                        <tr>
                            <th>Step</th>
                            <th>Origin Area (A·min)</th>
                            <th>|A| (A·min)</th>
                            <th>S_base (A)</th>
                            <th>k (A⁻¹)</th>
                            <th>nCO₂ (mol)</th>
                            <th>nCO₂ (mmol)</th>
                            <th>q (100% Mass)</th>
                            <th>q (Dry Mass) [mmol/g]</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Experimental Parameters -->
        <div class="card">
            <h3>⚙️ Experimental Operating Parameters & Thermodynamic Constants</h3>
            <div class="params-grid">
                <div>
                    <div class="param-row"><span class="p-name">Sample Weighed Mass:</span><span class="p-val">{m_tot_mg:.1f} mg ({m_tot:.4f} g)</span></div>
                    <div class="param-row"><span class="p-name">Moisture / Water Loss:</span><span class="p-val">{w_pct:.1f} %</span></div>
                    <div class="param-row"><span class="p-name">Dry Active Mass:</span><span class="p-val">{m_act_mg:.3f} mg ({m_act:.6f} g)</span></div>
                    <div class="param-row"><span class="p-name">Feed CO₂ Fraction C₀:</span><span class="p-val">{c0:.2f} (15% CO₂ in N₂)</span></div>
                </div>
                <div>
                    <div class="param-row"><span class="p-name">Total Gas Flow:</span><span class="p-val">{flow_tot:.1f} mL/min</span></div>
                    <div class="param-row"><span class="p-name">Assay Temperature T₂:</span><span class="p-val">{temp_c:.1f} °C (Ref: {temp_ref:.1f} °C)</span></div>
                    <div class="param-row"><span class="p-name">Molar Volume Vₘ,exp:</span><span class="p-val">{vm_exp:.1f} mL/mol</span></div>
                    <div class="param-row"><span class="p-name">Total Molar Flow Rate:</span><span class="p-val">{n_tot:.4e} mol/min</span></div>
                </div>
                <div>
                    <div class="param-row"><span class="p-name">Mean Baseline Signal S_base:</span><span class="p-val">{s_base:.4e} A</span></div>
                    <div class="param-row"><span class="p-name">Sensitivity Factor k:</span><span class="p-val">{k_fact:.3e} A⁻¹</span></div>
                    <div class="param-row"><span class="p-name">Calibration Model:</span><span class="p-val">{k_mode}</span></div>
                    <div class="param-row"><span class="p-name">High-Res Exports:</span><span class="p-val">600 DPI & 1200 DPI PNG Saved</span></div>
                </div>
            </div>
        </div>

        <!-- Methodology & Equations -->
        <div class="card">
            <h3>📐 Mathematical Model & Formulas</h3>
            <div style="font-size: 13px; color: var(--text-light); line-height: 1.7;">
                <p>• <strong>Molar Volume at Experimental Temperature:</strong> <code>V_m(T₂) = V_m(T₁) × (T₂ + 273.15) / (T₁ + 273.15)</code></p>
                <p>• <strong>Total Molar Flow Rate:</strong> <code>ṅ_total = Flow_total / V_m(T₂)</code> (mol/min)</p>
                <p>• <strong>Detector Sensitivity Constant:</strong> <code>k = C₀ / S_base</code> (A⁻¹)</p>
                <p>• <strong>Moles of Adsorbed / Desorbed CO₂:</strong> <code>nCO₂ = ṅ_total × k × |A|</code> (mol)</p>
                <p>• <strong>Equilibrium Adsorption Capacity:</strong> <code>q = nCO₂ (mmol) / Mass_active (g)</code> (mmol/g)</p>
                <p>• <strong>Desorption Recovery Ratio:</strong> <code>Recovery (%) = [ q_des(dry) / q_ads(dry) ] × 100%</code></p>
            </div>
        </div>

        <div class="footer">
            Generated by AI Antigravity Software &nbsp;•&nbsp; Automated Research Vault &nbsp;•&nbsp; 600 & 1200 DPI Export Ready
        </div>
    </div>
</body>
</html>
"""
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return {
        "html": html_path,
        "txt": txt_path,
        "csv": csv_path,
        "600_dpi": img_paths.get("600_dpi"),
        "1200_dpi": img_paths.get("1200_dpi")
    }
