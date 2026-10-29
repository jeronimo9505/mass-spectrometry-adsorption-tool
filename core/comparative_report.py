"""
Comparative Analysis Report Engine (MS CO₂ Adsorption/Desorption & TGA/DTG)
===========================================================================
Generates publication-grade comparative reports for any user-selected subset
of samples/materials and saves them into a dedicated vault folder:

    data_vault/Comparative_Analysis_Reports/
        ├── MS_Comparisons/<report_folder>/
        │     ├── Comparative_MS_<name>_Complete_Report.pdf
        │     ├── Comparative_MS_<name>_Complete_Data.xlsx
        │     ├── Comparative_MS_<name>_1200dpi.png
        │     └── Comparative_MS_<name>_Report.html
        └── TGA_Comparisons/<report_folder>/
              ├── Comparative_TGA_<name>_Complete_Report.pdf
              ├── Comparative_TGA_<name>_Complete_Data.xlsx
              ├── Comparative_TGA_<name>_styleA_journal_1200dpi.png
              ├── Comparative_TGA_<name>_styleB_presentation_1200dpi.png
              └── Comparative_TGA_<name>_Report.html
"""

import os
import io
import json
import html
import base64
import datetime
import statistics
import textwrap

import numpy as np
import pandas as pd
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.ticker import AutoMinorLocator
from matplotlib.backends.backend_pdf import PdfPages

from core.tga_engine import load_tga_data
from core import tga_report as TR

COMP_PALETTE = [
    "#1d3557",  # deep navy
    "#c0392b",  # crimson red
    "#2a9d8f",  # teal green
    "#e67e22",  # burnt orange
    "#8e44ad",  # royal purple
    "#2980b9",  #cerulean blue
    "#d35400",  # rust
    "#27ae60",  # emerald
    "#34495e",  # slate
    "#c2185b",  # magenta
]


def get_comparative_root_dir(vault_path, sub=None):
    base = os.path.join(os.path.abspath(vault_path), "Comparative_Analysis_Reports")
    if sub:
        base = os.path.join(base, sub)
    os.makedirs(base, exist_ok=True)
    return base


def _safe_name(s):
    return "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in str(s)).strip("_") or "Comparison"


def _line(fig, x0, x1, y, color="#222222", lw=0.8):
    fig.add_artist(Line2D([x0, x1], [y, y], transform=fig.transFigure, color=color, lw=lw))


# =========================================================================== #
# 1. MASS SPECTROMETRY (ADSORPTION / DESORPTION) COMPARATIVE REPORT
# =========================================================================== #

def collect_ms_sample_records(vault, sample_ids=None):
    """Collects MS cycle-by-cycle and summary capacity data for the selected sample_ids (or all samples if None)."""
    sample_list = vault.db.list_samples()
    all_samples = {s["sample_id"]: s for s in sample_list}
    if sample_ids is None:
        sample_ids = [s["sample_id"] for s in sample_list]
    records = []
    max_cycles = 3

    for sid in sample_ids:
        s = all_samples.get(sid)
        if not s:
            continue
        mat_name = s.get("material_name", sid)
        disp_name = mat_name if (sid in mat_name or "ref" in mat_name.lower()) else f"{mat_name} ({sid})"

        with vault.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT capacity_json, ranges_json, filename FROM mass_spec_analyses WHERE sample_id = ? ORDER BY id DESC LIMIT 1",
                (sid,)
            )
            an_row = cur.fetchone()

        cap_dict = {}
        ms_filename = ""
        if an_row and an_row["capacity_json"]:
            ms_filename = an_row["filename"] or ""
            try:
                cap_dict = json.loads(an_row["capacity_json"])
            except Exception:
                cap_dict = {}

        rows = cap_dict.get("rows", [])
        ads_peaks = [r for r in rows if r.get("phase") == "adsorption"]
        des_peaks = [r for r in rows if r.get("phase") == "desorption"]
        max_cycles = max(max_cycles, len(ads_peaks), len(des_peaks))

        def _stats(vals):
            if not vals:
                return None, None
            m = sum(vals) / len(vals)
            sd = statistics.stdev(vals) if len(vals) >= 2 else 0.0
            return m, sd

        ads_dry = [float(r.get("q_dry", 0.0)) for r in ads_peaks]
        des_dry = [float(r.get("q_dry", 0.0)) for r in des_peaks]
        avg_ads_dry, sd_ads_dry = _stats(ads_dry)
        avg_des_dry, sd_des_dry = _stats(des_dry)
        pct_diff_dry = (avg_des_dry / avg_ads_dry * 100.0) if (avg_ads_dry and avg_des_dry is not None and avg_ads_dry > 0) else None

        ads_100 = [float(r.get("q_100", 0.0)) for r in ads_peaks]
        des_100 = [float(r.get("q_100", 0.0)) for r in des_peaks]
        avg_ads_100, sd_ads_100 = _stats(ads_100)
        avg_des_100, sd_des_100 = _stats(des_100)
        pct_diff_100 = (avg_des_100 / avg_ads_100 * 100.0) if (avg_ads_100 and avg_des_100 is not None and avg_ads_100 > 0) else None

        has_ms = bool(ads_dry or des_dry)
        records.append({
            "sample": s,
            "sample_id": sid,
            "material_name": mat_name,
            "display_name": disp_name,
            "date": s.get("date", "-"),
            "mass_total_g": float(s.get("mass_total_g", 0.0) or 0.0),
            "has_ms": has_ms,
            "mean_ads": avg_ads_dry or 0.0,
            "mean_des": avg_des_dry or 0.0,
            "ms_filename": ms_filename,
            "ads_dry_vals": ads_dry,
            "des_dry_vals": des_dry,
            "avg_ads_dry": avg_ads_dry,
            "avg_des_dry": avg_des_dry,
            "sd_ads_dry": sd_ads_dry,
            "sd_des_dry": sd_des_dry,
            "pct_diff_dry": pct_diff_dry,
            "ads_100_vals": ads_100,
            "des_100_vals": des_100,
            "avg_ads_100": avg_ads_100,
            "avg_des_100": avg_des_100,
            "sd_ads_100": sd_ads_100,
            "sd_des_100": sd_des_100,
            "pct_diff_100": pct_diff_100,
            "all_rows": rows,
        })
    return records, max_cycles


def render_ms_comparative_figure(fig, records, title="CO₂ Adsorption / Desorption Comparative Analysis"):
    """
    Renders a publication landscape figure comparing selected MS samples:
      - Left panel: Grouped bar chart of Avg Adsorption vs Avg Desorption (Dry Mass Basis, mmol/g) with SD error bars
      - Right panel: Cycle-by-cycle Desorption/Adsorption capacity stability across cycles + Summary Table
    """
    fig.clear()
    fig.set_size_inches(12.0, 6.75)
    ink = "#1f2937"
    navy = "#1d3557"
    red = "#c0392b"
    teal = "#2a9d8f"
    grey = "#555555"

    fig.text(0.055, 0.945, title, fontsize=14.0, fontweight="bold", color=navy, va="center")
    fig.text(0.055, 0.910,
             f"Comparative evaluation of {len(records)} selected sample(s)   •   15% CO₂ in N₂, 100 mL/min, 24 °C (m/z 44)",
             fontsize=8.8, color=grey, va="center")

    ax_bar = fig.add_axes([0.07, 0.42, 0.45, 0.43])
    ax_cyc = fig.add_axes([0.58, 0.42, 0.37, 0.43])

    valid = [r for r in records if r["avg_ads_dry"] is not None or r["avg_des_dry"] is not None]
    if not valid:
        valid = records

    labels = [r["sample_id"] for r in valid]
    x = np.arange(len(valid))
    width = 0.36
    ads_means = [r["avg_ads_dry"] or 0.0 for r in valid]
    des_means = [r["avg_des_dry"] or 0.0 for r in valid]
    ads_sds = [r["sd_ads_dry"] or 0.0 for r in valid]
    des_sds = [r["sd_des_dry"] or 0.0 for r in valid]

    b1 = ax_bar.bar(x - width / 2, ads_means, width, yerr=ads_sds, capsize=3.5,
                    label="Avg Adsorption (dry)", color=navy, alpha=0.88, edgecolor="#111", lw=0.7)
    b2 = ax_bar.bar(x + width / 2, des_means, width, yerr=des_sds, capsize=3.5,
                    label="Avg Desorption (dry)", color=teal, alpha=0.88, edgecolor="#111", lw=0.7)

    ymax = max(max(ads_means + des_means, default=1.0) * 1.24, 0.5)
    ax_bar.set_ylim(0, ymax)
    ax_bar.set_xticks(x)
    ax_bar.set_xticklabels(labels, rotation=18 if len(labels) > 4 else 0, ha="right" if len(labels) > 4 else "center", fontsize=8.5)
    ax_bar.set_ylabel("CO₂ Capacity – Dry Basis (mmol/g)", fontsize=9.8, color=ink)
    ax_bar.set_title("Average Adsorption vs. Desorption Capacity", fontsize=10.2, fontweight="bold", color=navy, pad=8)
    ax_bar.legend(loc="upper right", frameon=True, fontsize=8.0)
    ax_bar.grid(axis="y", ls=":", alpha=0.5)

    for bar in b1:
        h = bar.get_height()
        if h > 0:
            ax_bar.text(bar.get_x() + bar.get_width() / 2, h + 0.02 * ymax, f"{h:.2f}",
                        ha="center", va="bottom", fontsize=7.2, color=navy, fontweight="bold")
    for bar in b2:
        h = bar.get_height()
        if h > 0:
            ax_bar.text(bar.get_x() + bar.get_width() / 2, h + 0.02 * ymax, f"{h:.2f}",
                        ha="center", va="bottom", fontsize=7.2, color=teal, fontweight="bold")

    # Right plot: Cycle-by-cycle Adsorption (solid) and Desorption (dashed)
    for idx, r in enumerate(valid):
        col = COMP_PALETTE[idx % len(COMP_PALETTE)]
        if r["ads_dry_vals"]:
            c_idx = np.arange(1, len(r["ads_dry_vals"]) + 1)
            ax_cyc.plot(c_idx, r["ads_dry_vals"], "-o", color=col, lw=1.8, ms=5.5,
                        label=f"{r['sample_id']} (Ads)")
        if r["des_dry_vals"]:
            c_idx = np.arange(1, len(r["des_dry_vals"]) + 1)
            ax_cyc.plot(c_idx, r["des_dry_vals"], "--s", color=col, lw=1.4, ms=4.8, alpha=0.82,
                        label=f"{r['sample_id']} (Des)")

    ax_cyc.set_xlabel("Cycle Number", fontsize=9.5, color=ink)
    ax_cyc.set_ylabel("Cycle Capacity – Dry Basis (mmol/g)", fontsize=9.5, color=ink)
    ax_cyc.set_title("Cycle-by-Cycle Capacity & Regenerability", fontsize=10.2, fontweight="bold", color=navy, pad=8)
    ax_cyc.set_ylim(0, ymax)
    ax_cyc.grid(True, ls=":", alpha=0.5)
    if valid:
        ax_cyc.legend(loc="best", fontsize=7.0, ncol=2, frameon=True)

    for ax in (ax_bar, ax_cyc):
        ax.tick_params(direction="in", top=True, right=True, labelsize=8.5)
        for sp in ax.spines.values():
            sp.set_color("#333333")
            sp.set_linewidth(0.85)

    # Bottom comparative table inside figure
    y = 0.315
    fig.text(0.055, y, "Comparative Summary Table (Dry Mass Basis & As-Weighed Basis)",
             fontsize=10.2, fontweight="bold", color=navy, va="center")
    y -= 0.026
    _line(fig, 0.055, 0.955, y + 0.009, color=navy, lw=1.1)
    cols = [
        (0.055, "Sample / Material"),
        (0.305, "Mass (g)"),
        (0.380, "Dry Mass (g)"),
        (0.465, "Ads C1"),
        (0.530, "Des C1"),
        (0.595, "Avg Ads (Dry)"),
        (0.690, "Avg Des (Dry)"),
        (0.785, "Avg Ads (Wet)"),
        (0.880, "Recovery %"),
    ]
    for cx, h in cols:
        fig.text(cx, y - 0.003, h, fontsize=7.8, fontweight="bold", color=navy, va="center")
    y -= 0.015
    _line(fig, 0.055, 0.955, y, color=navy, lw=0.8)
    y -= 0.016

    for r in records[:10]:
        s = r["sample"]
        m_tot = float(s.get("mass_total_g", 0.0) or 0.0)
        m_act = float(s.get("mass_active_g", 0.0) or 0.0)
        c1_a = f"{r['ads_dry_vals'][0]:.3f}" if r["ads_dry_vals"] else "-"
        c1_d = f"{r['des_dry_vals'][0]:.3f}" if r["des_dry_vals"] else "-"
        aa_d = f"{r['avg_ads_dry']:.3f} ± {r['sd_ads_dry']:.3f}" if r["avg_ads_dry"] is not None else "-"
        ad_d = f"{r['avg_des_dry']:.3f} ± {r['sd_des_dry']:.3f}" if r["avg_des_dry"] is not None else "-"
        aa_w = f"{r['avg_ads_100']:.3f}" if r["avg_ads_100"] is not None else "-"
        rec = f"{r['pct_diff_dry']:.1f} %" if r["pct_diff_dry"] is not None else "-"
        vals = [
            r["display_name"][:38],
            f"{m_tot:.4f}" if m_tot > 0 else "-",
            f"{m_act:.4f}" if m_tot > 0 else "-",
            c1_a, c1_d, aa_d, ad_d, aa_w, rec
        ]
        for (cx, _), v in zip(cols, vals):
            fig.text(cx, y, v, fontsize=7.5, color=ink, va="center")
        y -= 0.022
        _line(fig, 0.055, 0.955, y + 0.009, color="#e5e7eb", lw=0.5)

    _line(fig, 0.055, 0.955, y + 0.009, color=navy, lw=1.0)
    return fig


def generate_ms_comparative_report(vault, sample_ids, report_title="MS Adsorption & Desorption Comparative Report"):
    """
    Generates a complete comparative report package for the selected sample_ids in:
      data_vault/Comparative_Analysis_Reports/MS_Comparisons/<timestamp_title>/
    Returns dict of generated file paths.
    """
    records, max_cycles = collect_ms_sample_records(vault, sample_ids)
    if not records:
        raise ValueError("No valid samples selected for comparative report.")

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    base_slug = _safe_name(f"Comparative_MS_{len(records)}Samples_{stamp}")
    out_dir = get_comparative_root_dir(vault.vault_path, os.path.join("MS_Comparisons", base_slug))

    # 1. Excel Workbook (using MasterExcelManager's exact table formatting for selected samples)
    xlsx_path = os.path.join(out_dir, f"{base_slug}_Complete_Data.xlsx")
    wb = openpyxl.Workbook()
    ws_cap = wb.active
    ws_cap.title = "CO2 Capacity Summary"
    ws_cap.views.sheetView[0].showGridLines = True
    ws_inv = wb.create_sheet(title="Sample Inventory & Materials")
    ws_inv.views.sheetView[0].showGridLines = True
    ws_det = wb.create_sheet(title="All Cycles Breakdown")
    ws_det.views.sheetView[0].showGridLines = True

    vault.excel_manager._populate_capacity_sheet(ws_cap, records, max_cycles)
    vault.excel_manager._populate_inventory_sheet(ws_inv, records)
    vault.excel_manager._populate_breakdown_sheet(ws_det, records)
    wb.save(xlsx_path)

    # 2. High-res 1200 DPI PNG
    png_path = os.path.join(out_dir, f"{base_slug}_1200dpi.png")
    fig = Figure(figsize=(12.0, 6.75), dpi=100, facecolor="white")
    render_ms_comparative_figure(fig, records, title=report_title)
    fig.savefig(png_path, dpi=1200, facecolor="white")

    # 3. Complete PDF Report
    pdf_path = os.path.join(out_dir, f"{base_slug}_Complete_Report.pdf")
    with PdfPages(pdf_path) as pdf:
        fig1 = Figure(figsize=(12.0, 6.75), dpi=100, facecolor="white")
        render_ms_comparative_figure(fig1, records, title=report_title)
        pdf.savefig(fig1, facecolor="white")

    # 4. Interactive HTML Report
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200, facecolor="white")
    img64 = base64.b64encode(buf.getvalue()).decode("ascii")
    e = html.escape
    rows_html = ""
    for r in records:
        s = r["sample"]
        m_tot = float(s.get("mass_total_g", 0.0) or 0.0)
        m_act = float(s.get("mass_active_g", 0.0) or 0.0)
        c1_a = f"{r['ads_dry_vals'][0]:.3f}" if r["ads_dry_vals"] else "-"
        c1_d = f"{r['des_dry_vals'][0]:.3f}" if r["des_dry_vals"] else "-"
        aa_d = f"{r['avg_ads_dry']:.3f}" if r["avg_ads_dry"] is not None else "-"
        ad_d = f"{r['avg_des_dry']:.3f}" if r["avg_des_dry"] is not None else "-"
        aa_w = f"{r['avg_ads_100']:.3f}" if r["avg_ads_100"] is not None else "-"
        ad_w = f"{r['avg_des_100']:.3f}" if r["avg_des_100"] is not None else "-"
        rec = f"{r['pct_diff_dry']:.1f} %" if r["pct_diff_dry"] is not None else "-"
        rows_html += (
            f"<tr><td><b>{e(r['display_name'])}</b></td>"
            f"<td>{f'{m_tot:.4f}' if m_tot > 0 else '-'}</td>"
            f"<td>{f'{m_act:.4f}' if m_tot > 0 else '-'}</td>"
            f"<td>{c1_a}</td><td>{c1_d}</td>"
            f"<td><b>{aa_d}</b></td><td><b>{ad_d}</b></td>"
            f"<td>{aa_w}</td><td>{ad_w}</td><td>{rec}</td></tr>"
        )

    html_path = os.path.join(out_dir, f"{base_slug}_Report.html")
    html_txt = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>{e(report_title)}</title>
<style>
 body {{ font-family:'Segoe UI',Arial,sans-serif; color:#222; max-width:1180px; margin:24px auto; padding:0 18px; }}
 h1 {{ color:#1d3557; border-bottom:3px solid #1d3557; padding-bottom:6px; }}
 table {{ border-collapse:collapse; width:100%; margin:12px 0; font-size:13.5px; }}
 th,td {{ border:1px solid #ccd; padding:6px 9px; text-align:center; }}
 th {{ background:#1d3557; color:#fff; }}
 td:first-child {{ text-align:left; }}
 img {{ width:100%; border:1px solid #ddd; margin:12px 0; }}
</style></head><body>
<h1>{e(report_title)}</h1>
<p><small>Generated on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} · Samples compared: {len(records)}</small></p>
<img src="data:image/png;base64,{img64}" alt="Comparative MS Chart">
<h2>Comparative CO₂ Capacity Table</h2>
<table>
<tr><th>Sample / Material</th><th>Total Mass (g)</th><th>Active Dry Mass (g)</th>
<th>Ads C1 (mmol/g)</th><th>Des C1 (mmol/g)</th>
<th>Avg Ads Dry (mmol/g)</th><th>Avg Des Dry (mmol/g)</th>
<th>Avg Ads Wet (mmol/g)</th><th>Avg Des Wet (mmol/g)</th><th>Recovery (%)</th></tr>
{rows_html}
</table>
</body></html>"""
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_txt)

    return {
        "out_dir": out_dir,
        "folder": out_dir,
        "pdf": pdf_path,
        "xlsx": xlsx_path,
        "excel": xlsx_path,
        "png_1200": png_path,
        "png_1200dpi": png_path,
        "html": html_path,
    }


# =========================================================================== #
# 2. TGA / DTG MULTI-SAMPLE COMPARATIVE REPORT
# =========================================================================== #

def list_available_tga_datasets(vault):
    """
    Returns all TGA spreadsheet files across all samples in the vault, newest sample first.
    Each item is a dict: {sample_id, material_name, filename, path, label, composition, conditions}.
    """
    items = []
    samples = vault.db.list_samples()
    # Sort newest first
    samples.sort(key=lambda s: (s.get("created_at") or s.get("date") or "", s.get("date") or "", s.get("sample_id") or ""), reverse=True)

    for s in samples:
        sid = s["sample_id"]
        mat = s.get("material_name", sid)
        s_data = vault.logbook.get(sid, {})
        tga_info = s_data.get("characterizations", {}).get("tga", {})
        comp = tga_info.get("composition")
        if not comp:
            if "silica" in f"{sid} {mat}".lower():
                comp = TR.DEFAULT_SILICA_COMPOSITION
            else:
                comp = TR.DEFAULT_COMPOSITION
        cond = tga_info.get("conditions") or dict(TR.DEFAULT_CONDITIONS)

        for f in tga_info.get("files", []):
            fn = f.get("filename", "")
            ext = os.path.splitext(fn)[1].lower()
            if ext in (".xlsx", ".xls", ".csv", ".txt", ".dat"):
                fpath = vault.get_characterization_file_path(sid, "tga", fn)
                if fpath and os.path.exists(fpath):
                    stem = os.path.splitext(fn)[0]
                    items.append({
                        "sample_id": sid,
                        "material_name": mat,
                        "filename": fn,
                        "path": fpath,
                        "label": f"{sid} ({stem})",
                        "composition": comp,
                        "conditions": cond,
                    })
    return items


def analyze_tga_comparison(datasets):
    """
    Loads and runs TR.analyze_tga on each dataset in `datasets`.
    Returns list of dicts with analysis results and assigned colors.
    """
    compared = []
    for idx, item in enumerate(datasets):
        df, raw_meta = load_tga_data(item["path"])
        A = TR.analyze_tga(df, item.get("composition"), item.get("conditions"))
        tot = A["totals"]
        steps = A["steps"]

        # Group losses into physical temperature windows for cross-material comparison:
        #   - Water / Low-T (< 205 °C)
        #   - Organics / Mid-T (205 – 500 °C)
        #   - Dehydroxylation / High-T (> 500 °C)
        loss_water = sum(s["loss"] for s in steps if s["peak_t"] < 200.0)
        loss_mid = sum(s["loss"] for s in steps if 200.0 <= s["peak_t"] <= 500.0)
        loss_high = sum(s["loss"] for s in steps if s["peak_t"] > 500.0)

        compared.append({
            "sample_id": item["sample_id"],
            "material_name": item.get("material_name", item["sample_id"]),
            "filename": item["filename"],
            "label": item.get("label") or f"{item['sample_id']} – {os.path.splitext(item['filename'])[0]}",
            "color": COMP_PALETTE[idx % len(COMP_PALETTE)],
            "analysis": A,
            "df": df,
            "loss_water": round(loss_water, 2),
            "loss_mid": round(loss_mid, 2),
            "loss_high": round(loss_high, 2),
            "total_loss": round(tot["total_loss"], 2),
            "residue": round(tot["residue"], 2),
            "peak_t_main": round(tot["peak_t_main"], 1),
        })
    return compared


def render_tga_comp_style_a(fig, compared, title="Comparative TGA / DTG Analysis"):
    """
    Style A (Journal Vertical) overlay of multiple TGA / DTG curves:
      - Top panel: Overlaid DTG (wt% °C⁻¹) curves with peak labels & legend
      - Bottom panel: Overlaid Mass (wt%) curves with residue markers & summary callout box
    """
    fig.clear()
    fig.set_size_inches(*TR.FIG_SIZE_A)
    ink = "#222222"
    grey = "#555555"

    fig.text(0.125, 0.955, title, fontsize=13.5, fontweight="bold", color=ink, va="center")
    sub = "  |  ".join(f"{c['label']} (res. {c['residue']:.1f}%)" for c in compared[:5])
    fig.text(0.125, 0.924, sub, fontsize=8.5, color=grey, va="center")

    ax_d = fig.add_axes([0.125, 0.565, 0.825, 0.330])
    ax_m = fig.add_axes([0.125, 0.105, 0.825, 0.435], sharex=ax_d)

    all_t_min = min(float(c["analysis"]["arrays"]["t"][0]) for c in compared)
    all_t_max = max(float(c["analysis"]["arrays"]["t"][-1]) for c in compared)
    x_min = 20.0 if all_t_min > 20 else 0.0
    x_max = float(np.ceil(all_t_max / 100.0) * 100.0)

    d_max = max(float(c["analysis"]["arrays"]["dtg_s"].max()) for c in compared)
    y_min = max(0.0, min(c["residue"] for c in compared) - 8.0)
    y_min = float(np.floor(y_min / 5.0) * 5.0)

    for c in compared:
        A = c["analysis"]
        t, w, dtg_s = A["arrays"]["t"], A["arrays"]["w"], A["arrays"]["dtg_s"]
        col = c["color"]
        lbl = f"{c['label']}  (Δm = {c['total_loss']:.1f}%, res. = {c['residue']:.1f}%)"
        ax_d.plot(t, dtg_s, color=col, lw=1.85, label=c["label"], zorder=4)
        ax_m.plot(t, w, color=col, lw=2.1, label=lbl, zorder=4)
        ax_m.plot([t[-1]], [w[-1]], "o", ms=5.0, mfc="white", mec=col, mew=1.4, zorder=6)

    ax_d.set_xlim(x_min, x_max)
    ax_d.set_ylim(0, max(0.05, d_max * 1.22))
    ax_d.set_ylabel("DTG (wt% °C$^{-1}$)", fontsize=11)
    ax_d.tick_params(labelbottom=False)
    ax_d.legend(loc="upper right", frameon=True, fontsize=8.4)
    ax_d.grid(True, ls=":", alpha=0.4)

    ax_m.set_xlim(x_min, x_max)
    ax_m.set_ylim(y_min, 105.0)
    ax_m.axhline(100.0, color="#888888", ls="--", lw=0.8)
    ax_m.set_ylabel("Mass (wt%)", fontsize=11)
    ax_m.set_xlabel("Temperature (°C)", fontsize=11)
    ax_m.legend(loc="upper right", frameon=True, fontsize=8.2)
    ax_m.grid(True, ls=":", alpha=0.4)

    for ax in (ax_d, ax_m):
        ax.tick_params(direction="in", which="both", top=True, right=True, left=True, bottom=True, labelsize=9.5, length=4.5)
        ax.xaxis.set_minor_locator(AutoMinorLocator(2))
        for sp in ax.spines.values():
            sp.set_linewidth(1.0)
            sp.set_color("#222222")

    fig.text(0.125, 0.035,
             f"Comparative TGA / DTG overlay of {len(compared)} datasets. Mass is relative to the sample loaded in the pan (100 wt%).",
             fontsize=7.6, color=grey, va="center")
    return fig


def render_tga_comp_style_b(fig, compared, title="Comparative TGA / DTG Analysis"):
    """
    Style B (Presentation Landscape) overlay of multiple TGA / DTG curves:
      - Left: Mass (top) + DTG (bottom) overlaid curves
      - Right: Comparative Summary Table of steps, peaks, total loss & residue
    """
    fig.clear()
    fig.set_size_inches(*TR.FIG_SIZE_B)
    ink = "#222222"
    navy = "#1d3557"
    grey = "#555555"

    fig.text(0.052, 0.952, title, fontsize=14.0, fontweight="bold", color=ink, va="center")
    fig.text(0.052, 0.915,
             f"Multi-sample thermal stability & mass-balance comparison ({len(compared)} datasets)",
             fontsize=8.6, color=grey, va="center")

    ax_m = fig.add_axes([0.062, 0.435, 0.465, 0.425])
    ax_d = fig.add_axes([0.062, 0.130, 0.465, 0.280], sharex=ax_m)

    all_t_min = min(float(c["analysis"]["arrays"]["t"][0]) for c in compared)
    all_t_max = max(float(c["analysis"]["arrays"]["t"][-1]) for c in compared)
    x_min = 20.0 if all_t_min > 20 else 0.0
    x_max = float(np.ceil(all_t_max / 100.0) * 100.0)
    d_max = max(float(c["analysis"]["arrays"]["dtg_s"].max()) for c in compared)
    y_min = max(0.0, float(np.floor((min(c["residue"] for c in compared) - 8.0) / 5.0) * 5.0))

    for c in compared:
        A = c["analysis"]
        t, w, dtg_s = A["arrays"]["t"], A["arrays"]["w"], A["arrays"]["dtg_s"]
        col = c["color"]
        ax_m.plot(t, w, color=col, lw=1.9, label=c["label"], zorder=4)
        ax_m.plot([t[-1]], [w[-1]], "o", ms=4.8, mfc="white", mec=col, mew=1.3, zorder=6)
        ax_d.plot(t, dtg_s, color=col, lw=1.6, label=c["label"], zorder=4)

    ax_m.set_xlim(x_min, x_max)
    ax_m.set_ylim(y_min, 105.0)
    ax_m.axhline(100.0, color="#999999", ls=":", lw=0.8)
    ax_m.set_ylabel("Mass (wt%)", fontsize=10)
    ax_m.tick_params(labelbottom=False)
    ax_m.legend(loc="upper right", frameon=True, fontsize=7.8)
    ax_m.grid(True, ls=":", alpha=0.4)

    ax_d.set_xlim(x_min, x_max)
    ax_d.set_ylim(0, max(0.05, d_max * 1.22))
    ax_d.set_ylabel("DTG (wt% °C$^{-1}$)", fontsize=10)
    ax_d.set_xlabel("Temperature (°C)", fontsize=10)
    ax_d.grid(True, ls=":", alpha=0.4)

    for ax in (ax_m, ax_d):
        ax.tick_params(direction="in", which="both", top=True, right=True, left=True, bottom=True, labelsize=8.5)
        ax.xaxis.set_minor_locator(AutoMinorLocator(2))
        for sp in ax.spines.values():
            sp.set_linewidth(0.9)
            sp.set_color("#333333")

    # Right column: Comparative Quantitative Table
    X0 = 0.555
    XR = 0.985
    y = 0.860
    fig.text(X0, y, "Comparative Mass-Loss & Residue Summary", fontsize=11.2, fontweight="bold", color=navy, va="center")
    y -= 0.042
    cols = [
        (X0, "Sample / Run"),
        (X0 + 0.165, "Main Peak"),
        (X0 + 0.225, "<200 °C"),
        (X0 + 0.280, "200–500 °C"),
        (X0 + 0.340, "Total Loss"),
        (X0 + 0.395, "Residue"),
    ]
    for cx, h in cols:
        fig.text(cx, y, h, fontsize=7.4, fontweight="bold", color=navy, va="center")
    _line(fig, X0, XR, y - 0.015, color=navy, lw=0.9)
    y -= 0.036

    for c in compared:
        fig.text(X0, y, "●", fontsize=9.5, color=c["color"], va="center")
        lbl_short = c["label"] if len(c["label"]) <= 24 else c["label"][:22] + "…"
        fig.text(X0 + 0.016, y, lbl_short, fontsize=7.3, fontweight="bold", color=ink, va="center")
        fig.text(X0 + 0.165, y, f"{c['peak_t_main']:.0f} °C", fontsize=7.3, color=ink, va="center")
        fig.text(X0 + 0.225, y, f"{c['loss_water']:.2f}%", fontsize=7.3, color=ink, va="center")
        fig.text(X0 + 0.280, y, f"{c['loss_mid']:.2f}%", fontsize=7.3, color=ink, va="center")
        fig.text(X0 + 0.340, y, f"{c['total_loss']:.2f}%", fontsize=7.5, fontweight="bold", color="#c0392b", va="center")
        fig.text(X0 + 0.395, y, f"{c['residue']:.2f}%", fontsize=7.5, fontweight="bold", color=navy, va="center")
        y -= 0.034
        _line(fig, X0, XR, y + 0.015, color="#e5e7eb", lw=0.5)

    _line(fig, X0, XR, y + 0.015, color=navy, lw=0.9)
    y -= 0.025

    # Step-by-step breakdown per sample
    fig.text(X0, y, "Individual Step Breakdown per Sample", fontsize=10.5, fontweight="bold", color=navy, va="center")
    y -= 0.032
    for c in compared[:6]:
        if y < 0.10:
            break
        fig.text(X0, y, f"■ {c['label']}:", fontsize=7.5, fontweight="bold", color=c["color"], va="center")
        y -= 0.022
        for s in c["analysis"]["steps"]:
            if y < 0.07:
                break
            tr = f"RT–{s['t_end']:.0f} °C" if s["t_start"] is None else f"{s['t_start']:.0f}–{s['t_end']:.0f} °C"
            fig.text(X0 + 0.020, y,
                     f"Step {s['label']} ({tr}):  −{s['loss']:.2f} wt%   [DTG peak {s['peak_t']:.0f} °C]",
                     fontsize=6.9, color=ink, va="center")
            y -= 0.019
        y -= 0.008

    fig.text(0.052, 0.036,
             "Comparative TGA / DTG analysis generated by Lab Vault. All mass losses are expressed in wt% relative to loaded sample mass (100 %).",
             fontsize=7.0, color=grey, va="center")
    return fig


def generate_tga_comparative_report(vault, datasets, report_title="Comparative TGA / DTG Analysis", subtitle=""):
    """
    Generates a complete comparative TGA package in:
      data_vault/Comparative_Analysis_Reports/TGA_Comparisons/<timestamp_slug>/
    Contains:
      1. Complete PDF Report (Style B + Style A + Comparative Tables)
      2. Single Combined Comparative Excel Workbook
      3. 1200 DPI PNGs for both Style A and Style B
      4. Interactive HTML Report
    """
    compared = analyze_tga_comparison(datasets)
    if not compared:
        raise ValueError("No TGA datasets selected for comparison.")

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    base_slug = _safe_name(f"Comparative_TGA_{len(compared)}Runs_{stamp}")
    out_dir = get_comparative_root_dir(vault.vault_path, os.path.join("TGA_Comparisons", base_slug))

    # 1. Render 1200 DPI Style A & Style B PNGs
    pa = os.path.join(out_dir, f"{base_slug}_styleA_journal_1200dpi.png")
    pb = os.path.join(out_dir, f"{base_slug}_styleB_presentation_1200dpi.png")

    fig_a = Figure(figsize=TR.FIG_SIZE_A, dpi=100, facecolor="white")
    render_tga_comp_style_a(fig_a, compared, title=report_title)
    fig_a.savefig(pa, dpi=1200, facecolor="white")

    fig_b = Figure(figsize=TR.FIG_SIZE_B, dpi=100, facecolor="white")
    render_tga_comp_style_b(fig_b, compared, title=report_title)
    fig_b.savefig(pb, dpi=1200, facecolor="white")

    # 2. Combined Comparative Excel Workbook
    xlsx_path = os.path.join(out_dir, f"{base_slug}_Complete_Data.xlsx")
    summary_rows = []
    step_rows = []
    for c in compared:
        tot = c["analysis"]["totals"]
        cond = c["analysis"]["conditions"]
        summary_rows.append({
            "Sample ID": c["sample_id"],
            "Material Name": c["material_name"],
            "TGA File": c["filename"],
            "Legend Label": c["label"],
            "Atmosphere": cond.get("atmosphere", "Air"),
            "Flow (mL/min)": cond.get("flow_ml_min", 50.0),
            "Heating Rate (°C/min)": cond.get("heating_rate", 10.0),
            "T Range (°C)": f"{tot['t_first']:.1f} → {tot['t_last']:.1f}",
            "Main DTG Peak (°C)": c["peak_t_main"],
            "Water / Low-T Loss <200 °C (wt%)": c["loss_water"],
            "Organics / Mid-T Loss 200–500 °C (wt%)": c["loss_mid"],
            "High-T Loss >500 °C (wt%)": c["loss_high"],
            "Total Mass Loss (wt%)": c["total_loss"],
            "Residue at Final T (wt%)": c["residue"],
            "Steps Detected": len(c["analysis"]["steps"]),
        })
        for s in c["analysis"]["steps"]:
            step_rows.append({
                "Sample ID": c["sample_id"],
                "Legend Label": c["label"],
                "Step": s["label"],
                "T start (°C)": "RT (loading)" if s["t_start"] is None else round(s["t_start"], 1),
                "T end (°C)": round(s["t_end"], 1),
                "DTG Peak (°C)": round(s["peak_t"], 1),
                "DTG Peak Height (wt%/°C)": round(s["peak_h"], 4),
                "Mass at start (wt%)": round(s["m_start"], 2),
                "Mass at end (wt%)": round(s["m_end"], 2),
                "Mass loss (wt%)": round(s["loss"], 2),
            })

    sum_df = pd.DataFrame(summary_rows)
    stp_df = pd.DataFrame(step_rows)

    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as xw:
        sum_df.to_excel(xw, sheet_name="Comparative Summary", index=False)
        stp_df.to_excel(xw, sheet_name="All Steps Comparison", index=False)
        TR._style_sheet(xw.book["Comparative Summary"], wrap_body=True)
        TR._style_sheet(xw.book["All Steps Comparison"], wrap_body=True)

        used_sheets = {"Comparative Summary", "All Steps Comparison"}
        for idx, c in enumerate(compared, 1):
            d = c["analysis"]["df"]
            proc = pd.DataFrame({
                "Temperature (°C)": d["temperature"].values,
                "Mass (wt%)": d["weight"].values,
                "DTG (wt%/°C)": d["deriv_weight"].values,
            })
            sh_name = f"{idx}_{_safe_name(c['sample_id'])}"[:28]
            while sh_name in used_sheets:
                sh_name = sh_name[:25] + f"_{idx}"
            used_sheets.add(sh_name)
            proc.to_excel(xw, sheet_name=sh_name, index=False)
            TR._style_sheet(xw.book[sh_name])

    # 3. Complete Multi-Page PDF Report
    pdf_path = os.path.join(out_dir, f"{base_slug}_Complete_Report.pdf")
    with PdfPages(pdf_path) as pdf:
        fb = Figure(figsize=TR.FIG_SIZE_B, dpi=100, facecolor="white")
        render_tga_comp_style_b(fb, compared, title=report_title)
        pdf.savefig(fb, facecolor="white")

        fa = Figure(figsize=TR.FIG_SIZE_A, dpi=100, facecolor="white")
        render_tga_comp_style_a(fa, compared, title=report_title)
        pdf.savefig(fa, facecolor="white")

        # Page 3: Quantitative Comparative Tables
        ft = Figure(figsize=(8.5, 11.0), dpi=100, facecolor="white")
        navy = "#1d3557"
        ft.text(0.06, 0.955, f"{report_title} – Quantitative Summary", fontsize=13.0, fontweight="bold", color=navy, va="center")
        ft.text(0.06, 0.935, f"Generated on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}   •   {len(compared)} TGA datasets compared",
                fontsize=8.5, color="#555555", va="center")
        _line(ft, 0.06, 0.94, 0.922, color=navy, lw=1.4)

        tbl1_rows = [
            (c["label"], f"{c['peak_t_main']:.1f}", f"{c['loss_water']:.2f}",
             f"{c['loss_mid']:.2f}", f"{c['loss_high']:.2f}", f"{c['total_loss']:.2f}", f"{c['residue']:.2f}")
            for c in compared
        ]
        y = TR._draw_pdf_table(
            ft, 0.06, 0.895,
            [0.06, 0.34, 0.44, 0.55, 0.67, 0.77, 0.86],
            ["Sample / Run Label", "Peak °C", "<200 °C %", "200–500 °C %", ">500 °C %", "Total Loss %", "Residue %"],
            tbl1_rows, title="1. Overall Mass-Loss & Residue Comparison",
            row_pad=0.007, wrap_widths=[30, 10, 10, 12, 10, 10, 10], font_size=7.4
        )

        tbl2_rows = [
            (r["Legend Label"], r["Step"], r["T start (°C)"], r["T end (°C)"],
             r["DTG Peak (°C)"], r["Mass at start (wt%)"], r["Mass at end (wt%)"], r["Mass loss (wt%)"])
            for r in step_rows[:24]
        ]
        TR._draw_pdf_table(
            ft, 0.06, y - 0.005,
            [0.06, 0.31, 0.37, 0.47, 0.56, 0.65, 0.75, 0.85],
            ["Sample / Run", "Step", "T start", "T end", "Peak °C", "M start %", "M end %", "Loss %"],
            tbl2_rows, title="2. Step-by-Step Comparison Across Selected Samples",
            row_pad=0.005, wrap_widths=[26, 6, 10, 10, 10, 10, 10, 10], font_size=7.0
        )
        pdf.savefig(ft, facecolor="white")

    # 4. Interactive HTML Report
    buf_b = io.BytesIO()
    fig_b.savefig(buf_b, format="png", dpi=180, facecolor="white")
    img_b_64 = base64.b64encode(buf_b.getvalue()).decode("ascii")

    buf_a = io.BytesIO()
    fig_a.savefig(buf_a, format="png", dpi=180, facecolor="white")
    img_a_64 = base64.b64encode(buf_a.getvalue()).decode("ascii")

    e = html.escape
    sum_html = "".join(
        f"<tr><td><b>{e(c['label'])}</b></td><td>{c['peak_t_main']:.1f} °C</td>"
        f"<td>{c['loss_water']:.2f} %</td><td>{c['loss_mid']:.2f} %</td><td>{c['loss_high']:.2f} %</td>"
        f"<td><b style='color:#c0392b'>{c['total_loss']:.2f} %</b></td>"
        f"<td><b style='color:#1d3557'>{c['residue']:.2f} %</b></td></tr>"
        for c in compared
    )
    html_path = os.path.join(out_dir, f"{base_slug}_Report.html")
    html_txt = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>{e(report_title)}</title>
<style>
 body {{ font-family:'Segoe UI',Arial,sans-serif; color:#222; max-width:1160px; margin:24px auto; padding:0 18px; }}
 h1 {{ color:#1d3557; border-bottom:3px solid #1d3557; padding-bottom:6px; }}
 h2 {{ color:#1d3557; margin-top:26px; }}
 table {{ border-collapse:collapse; width:100%; margin:10px 0; font-size:13.5px; }}
 th,td {{ border:1px solid #ccd; padding:6px 9px; text-align:center; }}
 th {{ background:#1d3557; color:#fff; }}
 td:first-child {{ text-align:left; }}
 img {{ width:100%; border:1px solid #ddd; margin:10px 0; }}
</style></head><body>
<h1>{e(report_title)}</h1>
<p><small>Generated on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} · Datasets compared: {len(compared)}</small></p>
<h2>1. Comparative Summary Table</h2>
<table>
<tr><th>Sample / Run</th><th>Main DTG Peak</th><th>&lt;200 °C Loss</th><th>200–500 °C Loss</th><th>&gt;500 °C Loss</th><th>Total Mass Loss</th><th>Final Residue</th></tr>
{sum_html}
</table>
<h2>2. Style B – Presentation Comparative Graph</h2>
<img src="data:image/png;base64,{img_b_64}" alt="Style B Comparative TGA">
<h2>3. Style A – Journal Vertical Comparative Graph</h2>
<img style="max-width:780px; display:block; margin:12px auto;" src="data:image/png;base64,{img_a_64}" alt="Style A Comparative TGA">
</body></html>"""
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_txt)

    return {
        "out_dir": out_dir,
        "folder": out_dir,
        "pdf": pdf_path,
        "xlsx": xlsx_path,
        "excel": xlsx_path,
        "styleA_png_1200": pa,
        "styleB_png_1200": pb,
        "styleA_1200dpi": pa,
        "styleB_1200dpi": pb,
        "html": html_path,
        "compared": compared,
    }
