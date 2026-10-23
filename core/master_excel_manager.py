import os
import re
import json
import statistics
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

class MasterExcelManager:
    """
    Manages the Master Excel Summary file in the Data Vault:
    'Master_CO2_Adsorption_Summary.xlsx'
    
    Structure:
      Sheet 1: 'CO2 Capacity Summary'
        - Table A: Dry mass basis (sample mass minus water loss %)
        - Table B: As-weighed mass basis (100% mass)
        Formatted exactly according to lab specifications with cycle-by-cycle
        adsorption/desorption mmol/g, averages, standard deviations, and % Difference.
      Sheet 2: 'Sample Inventory & Materials'
        - Comprehensive synthesis and sample metadata catalog.
      Sheet 3: 'All Cycles Detailed Breakdown'
        - Analytical integration breakdown for every individual cycle peak.
    """
    MASTER_FILENAME = "Sample_Register_and_Summary_Analysis.xlsx"

    def __init__(self, vault_path, db_manager):
        self.vault_path = os.path.abspath(vault_path)
        self.db = db_manager

    def get_master_path(self):
        return os.path.join(self.vault_path, self.MASTER_FILENAME)

    def generate_master_excel(self):
        """
        Extracts all sample information, multi-cycle adsorption/desorption data,
        calculates averages, standard deviations, recovery % and builds the styled
        Excel workbook. Automatically updates whenever samples or analyses change.
        """
        os.makedirs(self.vault_path, exist_ok=True)
        dest_path = self.get_master_path()

        # Ensure strictly only one Master Excel file exists and remove any legacy/alternate files
        for stray_fn in ["Master_CO2_Adsorption_Summary.xlsx", "Master_CO2_Adsorption_Summary_Updated.xlsx", "Sample_Register_and_Summary_Analysis_Updated.xlsx"]:
            stray_path = os.path.join(self.vault_path, stray_fn)
            if os.path.exists(stray_path):
                try:
                    os.remove(stray_path)
                except Exception:
                    pass

        wb = openpyxl.Workbook()
        # Default sheet
        ws_cap = wb.active
        ws_cap.title = "CO2 Capacity Summary"
        ws_cap.views.sheetView[0].showGridLines = True

        ws_inv = wb.create_sheet(title="Sample Inventory & Materials")
        ws_inv.views.sheetView[0].showGridLines = True

        ws_det = wb.create_sheet(title="All Cycles Breakdown")
        ws_det.views.sheetView[0].showGridLines = True

        # Fetch samples and analyses
        samples = self.db.list_samples()

        # Sort samples: Place references first, then alphanumeric by sample_id
        def _sort_key(s):
            sid = s.get("sample_id", "").lower()
            mat = s.get("material_name", "").lower()
            is_ref = 0 if ("ref" in sid or "ref" in mat or "reference" in mat) else 1
            return (is_ref, s.get("sample_id", ""))

        sorted_samples = sorted(samples, key=_sort_key)

        # Gather sample cycle data
        sample_data_list = []
        max_ads_cycles = 3
        max_des_cycles = 3

        for s in sorted_samples:
            s_id = s["sample_id"]
            mat_name = s.get("material_name", s_id)

            # Query mass spec analyses for this sample
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT capacity_json, ranges_json, filename FROM mass_spec_analyses WHERE sample_id = ? ORDER BY id DESC LIMIT 1",
                    (s_id,)
                )
                an_row = cur.fetchone()

            cap_dict = {}
            if an_row and an_row["capacity_json"]:
                try:
                    cap_dict = json.loads(an_row["capacity_json"])
                except Exception:
                    cap_dict = {}

            rows = cap_dict.get("rows", [])
            ads_peaks = [r for r in rows if r.get("phase") == "adsorption"]
            des_peaks = [r for r in rows if r.get("phase") == "desorption"]

            if len(ads_peaks) > max_ads_cycles:
                max_ads_cycles = len(ads_peaks)
            if len(des_peaks) > max_des_cycles:
                max_des_cycles = len(des_peaks)

            # Statistics calculation helper
            def _compute_stats(values):
                if not values:
                    return None, None
                mean_val = sum(values) / len(values)
                std_val = statistics.stdev(values) if len(values) >= 2 else 0.0
                return mean_val, std_val

            # Dry mass basis
            ads_dry_vals = [r.get("q_dry", 0.0) for r in ads_peaks]
            des_dry_vals = [r.get("q_dry", 0.0) for r in des_peaks]
            avg_ads_dry, sd_ads_dry = _compute_stats(ads_dry_vals)
            avg_des_dry, sd_des_dry = _compute_stats(des_dry_vals)

            pct_diff_dry = None
            if avg_ads_dry is not None and avg_des_dry is not None and avg_ads_dry > 0:
                pct_diff_dry = (avg_des_dry / avg_ads_dry) * 100.0

            # As-weighed mass basis (100% mass)
            ads_100_vals = [r.get("q_100", 0.0) for r in ads_peaks]
            des_100_vals = [r.get("q_100", 0.0) for r in des_peaks]
            avg_ads_100, sd_ads_100 = _compute_stats(ads_100_vals)
            avg_des_100, sd_des_100 = _compute_stats(des_100_vals)

            pct_diff_100 = None
            if avg_ads_100 is not None and avg_des_100 is not None and avg_ads_100 > 0:
                pct_diff_100 = (avg_des_100 / avg_ads_100) * 100.0

            sample_data_list.append({
                "sample": s,
                "sample_id": s_id,
                "material_name": mat_name,
                "ads_peaks": ads_peaks,
                "des_peaks": des_peaks,
                "ads_dry_vals": ads_dry_vals,
                "des_dry_vals": des_dry_vals,
                "avg_ads_dry": avg_ads_dry,
                "avg_des_dry": avg_des_dry,
                "sd_ads_dry": sd_ads_dry,
                "sd_des_dry": sd_des_dry,
                "pct_diff_dry": pct_diff_dry,
                "ads_100_vals": ads_100_vals,
                "des_100_vals": des_100_vals,
                "avg_ads_100": avg_ads_100,
                "avg_des_100": avg_des_100,
                "sd_ads_100": sd_ads_100,
                "sd_des_100": sd_des_100,
                "pct_diff_100": pct_diff_100,
                "all_rows": rows
            })

        max_cycles = max(max_ads_cycles, max_des_cycles, 3)

        # =========================================================================
        # 1. POPULATE SHEET 1: CO2 Capacity Summary (Exact replica of user design)
        # =========================================================================
        self._populate_capacity_sheet(ws_cap, sample_data_list, max_cycles)

        # =========================================================================
        # 2. POPULATE SHEET 2: Sample Inventory & Materials
        # =========================================================================
        self._populate_inventory_sheet(ws_inv, sample_data_list)

        # =========================================================================
        # 3. POPULATE SHEET 3: All Cycles Breakdown
        # =========================================================================
        self._populate_breakdown_sheet(ws_det, sample_data_list)

        # Save workbook strictly to Sample_Register_and_Summary_Analysis.xlsx
        try:
            wb.save(dest_path)
            return dest_path
        except PermissionError:
            # If the user currently has the file open in Microsoft Excel, Windows locks it.
            # We never create alternate Excel files - we notify and return dest_path.
            print(f"[MasterExcelManager] Notice: '{self.MASTER_FILENAME}' is locked by another process (e.g. open in Excel). Please close it to allow auto-updates.")
            return dest_path
        except Exception as e:
            print(f"[MasterExcelManager] Error saving '{dest_path}': {e}")
            return dest_path

    def _populate_capacity_sheet(self, ws, sample_data_list, max_cycles):
        # Styles
        font_banner = Font(name="Calibri", size=11, bold=True, color="000000")
        font_sec_a = Font(name="Calibri", size=10, bold=True, color="000000")
        font_sec_b = Font(name="Calibri", size=10, bold=True, color="000000")
        font_tbl_hdr = Font(name="Calibri", size=9, bold=True, color="FFFFFF")
        font_data_id = Font(name="Calibri", size=9, bold=True, color="000000")
        font_data_num = Font(name="Calibri", size=9, color="000000")

        fill_sec_a = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")      # Bright yellow
        fill_sec_b = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid")      # Peach / soft orange
        fill_hdr_navy = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")   # Navy Blue
        fill_hdr_sd = PatternFill(start_color="1B365D", end_color="1B365D", fill_type="solid")     # Slightly darker blue for SD

        thin_side = Side(border_style="thin", color="000000")
        box_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)

        align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
        align_left = Alignment(horizontal="left", vertical="center")
        align_right = Alignment(horizontal="right", vertical="center")

        # Dynamic cycle columns
        cycle_cols = []
        for c in range(1, max_cycles + 1):
            cycle_cols.append(f"Ads cycle {c} (mmol/g)")
            cycle_cols.append(f"Desorp cycle {c} (mmol/g)")

        headers = ["Sample ID"] + cycle_cols + [
            "Avg Adsorption", "Avg Desorption",
            "Standard Deviation (Ads)", "Standard Deviation (Des)",
            "% Difference"
        ]
        total_cols = len(headers)

        # Row 2: Top Title Banner
        ws.row_dimensions[2].height = 24
        title_text = "CO₂ adsorption / desorption capacity, all samples (15% CO₂ in N₂, 100 mL/min, 24 °C, m/z 44)"
        ws.cell(row=2, column=1, value=title_text)
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=total_cols)
        c2 = ws.cell(row=2, column=1)
        c2.font = font_banner
        c2.alignment = align_center

        for col in range(1, total_cols + 1):
            ws.cell(row=2, column=col).border = box_border

        # -------------------------------------------------------------
        # TABLE A: Dry mass basis
        # -------------------------------------------------------------
        row_idx = 4
        ws.row_dimensions[row_idx].height = 20
        sec_a_title = "A) Dry mass basis (sample mass minus 21.4% water / active dry mass)"
        ws.cell(row=row_idx, column=1, value=sec_a_title)
        ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx, end_column=total_cols)
        for col in range(1, total_cols + 1):
            cell = ws.cell(row=row_idx, column=col)
            cell.font = font_sec_a
            cell.fill = fill_sec_a
            cell.alignment = align_center
            cell.border = box_border

        row_idx = 5
        ws.row_dimensions[row_idx].height = 32
        for col_idx, h_text in enumerate(headers, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=h_text)
            cell.font = font_tbl_hdr
            cell.fill = fill_hdr_sd if "Deviation" in h_text else fill_hdr_navy
            cell.alignment = align_center
            cell.border = box_border

        # Data rows for Table A
        for s_data in sample_data_list:
            row_idx += 1
            ws.row_dimensions[row_idx].height = 19

            # Display Sample ID / Material name (matching screenshot format)
            disp_name = s_data["material_name"] if s_data["material_name"] else s_data["sample_id"]
            if s_data["sample_id"] not in disp_name and "ref" not in disp_name.lower():
                disp_name = f"{s_data['material_name']} ({s_data['sample_id']})"

            cell_id = ws.cell(row=row_idx, column=1, value=disp_name)
            cell_id.font = font_data_id
            cell_id.alignment = align_left
            cell_id.border = box_border

            # Cycle values
            col_curr = 2
            for c in range(max_cycles):
                # Ads
                ads_val = s_data["ads_dry_vals"][c] if c < len(s_data["ads_dry_vals"]) else None
                cell = ws.cell(row=row_idx, column=col_curr, value=round(ads_val, 3) if ads_val is not None else "-")
                cell.font = font_data_num
                cell.alignment = align_center
                cell.border = box_border
                if ads_val is not None:
                    cell.number_format = "0.000"
                col_curr += 1

                # Desorp
                des_val = s_data["des_dry_vals"][c] if c < len(s_data["des_dry_vals"]) else None
                cell = ws.cell(row=row_idx, column=col_curr, value=round(des_val, 3) if des_val is not None else "-")
                cell.font = font_data_num
                cell.alignment = align_center
                cell.border = box_border
                if des_val is not None:
                    cell.number_format = "0.000"
                col_curr += 1

            # Avg Ads
            avg_a = s_data["avg_ads_dry"]
            cell = ws.cell(row=row_idx, column=col_curr, value=round(avg_a, 3) if avg_a is not None else "-")
            cell.font = font_data_num
            cell.alignment = align_center
            cell.border = box_border
            if avg_a is not None:
                cell.number_format = "0.000"
            col_curr += 1

            # Avg Des
            avg_d = s_data["avg_des_dry"]
            cell = ws.cell(row=row_idx, column=col_curr, value=round(avg_d, 3) if avg_d is not None else "-")
            cell.font = font_data_num
            cell.alignment = align_center
            cell.border = box_border
            if avg_d is not None:
                cell.number_format = "0.000"
            col_curr += 1

            # SD Ads
            sd_a = s_data["sd_ads_dry"]
            cell = ws.cell(row=row_idx, column=col_curr, value=round(sd_a, 3) if sd_a is not None else "-")
            cell.font = font_data_num
            cell.alignment = align_center
            cell.border = box_border
            if sd_a is not None:
                cell.number_format = "0.000"
            col_curr += 1

            # SD Des
            sd_d = s_data["sd_des_dry"]
            cell = ws.cell(row=row_idx, column=col_curr, value=round(sd_d, 3) if sd_d is not None else "-")
            cell.font = font_data_num
            cell.alignment = align_center
            cell.border = box_border
            if sd_d is not None:
                cell.number_format = "0.000"
            col_curr += 1

            # % Difference
            p_diff = s_data["pct_diff_dry"]
            cell = ws.cell(row=row_idx, column=col_curr, value=round(p_diff, 1) if p_diff is not None else "-")
            cell.font = font_data_num
            cell.alignment = align_center
            cell.border = box_border
            if p_diff is not None:
                cell.number_format = "0.0"

        # -------------------------------------------------------------
        # TABLE B: As-weighed mass basis (100% mass)
        # -------------------------------------------------------------
        row_idx += 2  # Blank line separator
        ws.row_dimensions[row_idx].height = 20
        sec_b_title = "B) As-weighed mass basis (100% mass)"
        ws.cell(row=row_idx, column=1, value=sec_b_title)
        ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx, end_column=total_cols)
        for col in range(1, total_cols + 1):
            cell = ws.cell(row=row_idx, column=col)
            cell.font = font_sec_b
            cell.fill = fill_sec_b
            cell.alignment = align_center
            cell.border = box_border

        row_idx += 1
        ws.row_dimensions[row_idx].height = 32
        for col_idx, h_text in enumerate(headers, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=h_text)
            cell.font = font_tbl_hdr
            cell.fill = fill_hdr_sd if "Deviation" in h_text else fill_hdr_navy
            cell.alignment = align_center
            cell.border = box_border

        # Data rows for Table B
        for s_data in sample_data_list:
            row_idx += 1
            ws.row_dimensions[row_idx].height = 19

            disp_name = s_data["material_name"] if s_data["material_name"] else s_data["sample_id"]
            if s_data["sample_id"] not in disp_name and "ref" not in disp_name.lower():
                disp_name = f"{s_data['material_name']} ({s_data['sample_id']})"

            cell_id = ws.cell(row=row_idx, column=1, value=disp_name)
            cell_id.font = font_data_id
            cell_id.alignment = align_left
            cell_id.border = box_border

            col_curr = 2
            for c in range(max_cycles):
                # Ads 100%
                ads_val = s_data["ads_100_vals"][c] if c < len(s_data["ads_100_vals"]) else None
                cell = ws.cell(row=row_idx, column=col_curr, value=round(ads_val, 3) if ads_val is not None else "-")
                cell.font = font_data_num
                cell.alignment = align_center
                cell.border = box_border
                if ads_val is not None:
                    cell.number_format = "0.000"
                col_curr += 1

                # Desorp 100%
                des_val = s_data["des_100_vals"][c] if c < len(s_data["des_100_vals"]) else None
                cell = ws.cell(row=row_idx, column=col_curr, value=round(des_val, 3) if des_val is not None else "-")
                cell.font = font_data_num
                cell.alignment = align_center
                cell.border = box_border
                if des_val is not None:
                    cell.number_format = "0.000"
                col_curr += 1

            # Avg Ads 100%
            avg_a = s_data["avg_ads_100"]
            cell = ws.cell(row=row_idx, column=col_curr, value=round(avg_a, 3) if avg_a is not None else "-")
            cell.font = font_data_num
            cell.alignment = align_center
            cell.border = box_border
            if avg_a is not None:
                cell.number_format = "0.000"
            col_curr += 1

            # Avg Des 100%
            avg_d = s_data["avg_des_100"]
            cell = ws.cell(row=row_idx, column=col_curr, value=round(avg_d, 3) if avg_d is not None else "-")
            cell.font = font_data_num
            cell.alignment = align_center
            cell.border = box_border
            if avg_d is not None:
                cell.number_format = "0.000"
            col_curr += 1

            # SD Ads 100%
            sd_a = s_data["sd_ads_100"]
            cell = ws.cell(row=row_idx, column=col_curr, value=round(sd_a, 3) if sd_a is not None else "-")
            cell.font = font_data_num
            cell.alignment = align_center
            cell.border = box_border
            if sd_a is not None:
                cell.number_format = "0.000"
            col_curr += 1

            # SD Des 100%
            sd_d = s_data["sd_des_100"]
            cell = ws.cell(row=row_idx, column=col_curr, value=round(sd_d, 3) if sd_d is not None else "-")
            cell.font = font_data_num
            cell.alignment = align_center
            cell.border = box_border
            if sd_d is not None:
                cell.number_format = "0.000"
            col_curr += 1

            # % Difference 100%
            p_diff = s_data["pct_diff_100"]
            cell = ws.cell(row=row_idx, column=col_curr, value=round(p_diff, 1) if p_diff is not None else "-")
            cell.font = font_data_num
            cell.alignment = align_center
            cell.border = box_border
            if p_diff is not None:
                cell.number_format = "0.0"

        # Auto-adjust column widths
        ws.column_dimensions["A"].width = 34
        for col_idx in range(2, total_cols + 1):
            col_letter = get_column_letter(col_idx)
            header_str = headers[col_idx - 1]
            ws.column_dimensions[col_letter].width = max(len(header_str) // 2 + 5, 13)

    def _populate_inventory_sheet(self, ws, sample_data_list):
        headers = [
            "Sample ID", "Material Information", "Operator", "Date",
            "Total Mass (g)", "Water Loss (%)", "Active Dry Mass (g)",
            "Ref Ads (mmol/g)", "Ref Des (mmol/g)", "Flow (mL/min)", "Temp (°C)", "CO₂ Feed C0",
            "Avg Ads Dry (mmol/g)", "Avg Des Dry (mmol/g)", "Recovery (%)",
            "Status", "Registered Files", "Notes & Observations"
        ]

        font_hdr = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
        fill_hdr = PatternFill(start_color="2E5B82", end_color="2E5B82", fill_type="solid")
        thin_side = Side(border_style="thin", color="D9D9D9")
        cell_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)
        align_c = Alignment(horizontal="center", vertical="center")
        align_l = Alignment(horizontal="left", vertical="center")

        ws.row_dimensions[1].height = 28
        for col_idx, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_idx, value=h)
            cell.font = font_hdr
            cell.fill = fill_hdr
            cell.alignment = align_c
            cell.border = cell_border

        for row_idx, s_data in enumerate(sample_data_list, 2):
            s = s_data["sample"]
            ws.row_dimensions[row_idx].height = 20

            files_cnt = s.get("files_count", 0)
            avg_a = s_data["avg_ads_dry"]
            avg_d = s_data["avg_des_dry"]
            rec = s_data["pct_diff_dry"]

            row_values = [
                s.get("sample_id", ""),
                s.get("material_name", ""),
                s.get("operator", ""),
                s.get("date", ""),
                float(s.get("mass_total_g", 0.0)),
                float(s.get("water_loss_pct", 0.0)),
                float(s.get("mass_active_g", 0.0)),
                float(s.get("ref_ads_mmol_g", 0.0)),
                float(s.get("ref_des_mmol_g", 0.0)),
                float(s.get("flow_total", 100.0)),
                float(s.get("temp_c", 24.0)),
                float(s.get("c0", 0.15)),
                round(avg_a, 4) if avg_a is not None else "-",
                round(avg_d, 4) if avg_d is not None else "-",
                round(rec, 1) if rec is not None else "-",
                s.get("status", "Registered"),
                files_cnt,
                s.get("notes", "")
            ]

            for col_idx, val in enumerate(row_values, 1):
                cell = ws.cell(row=row_idx, column=col_idx, value=val)
                cell.font = Font(name="Calibri", size=9)
                cell.border = cell_border
                if col_idx in [1, 3, 4, 16, 17]:
                    cell.alignment = align_c
                elif col_idx in [2, 18]:
                    cell.alignment = align_l
                else:
                    cell.alignment = align_c
                    if isinstance(val, float):
                        cell.number_format = "0.0000" if col_idx in [5, 7, 8, 9, 13, 14] else "0.00"

        # Widths
        for col_idx in range(1, len(headers) + 1):
            col_letter = get_column_letter(col_idx)
            ws.column_dimensions[col_letter].width = max(len(headers[col_idx - 1]) + 4, 12)
        ws.column_dimensions["B"].width = 28
        ws.column_dimensions["R"].width = 35

    def _populate_breakdown_sheet(self, ws, sample_data_list):
        headers = [
            "Sample ID", "Material Name", "Phase", "ROI Peak Name",
            "Start Time (min)", "End Time (min)", "Duration (min)",
            "Baseline Signal (A)", "Simpson Area", "k-Factor",
            "n(CO₂) mol", "n(CO₂) mmol",
            "q As-Weighed (mmol/g)", "q Dry Mass (mmol/g)", "q Net (mmol/g)"
        ]

        font_hdr = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
        fill_hdr = PatternFill(start_color="1B6A78", end_color="1B6A78", fill_type="solid")
        thin_side = Side(border_style="thin", color="D9D9D9")
        cell_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)
        align_c = Alignment(horizontal="center", vertical="center")
        align_l = Alignment(horizontal="left", vertical="center")

        ws.row_dimensions[1].height = 28
        for col_idx, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_idx, value=h)
            cell.font = font_hdr
            cell.fill = fill_hdr
            cell.alignment = align_c
            cell.border = cell_border

        curr_row = 2
        for s_data in sample_data_list:
            rows = s_data["all_rows"]
            s_id = s_data["sample_id"]
            mat = s_data["material_name"]

            for r in rows:
                ws.row_dimensions[curr_row].height = 19
                vals = [
                    s_id,
                    mat,
                    r.get("phase", ""),
                    r.get("type_name", ""),
                    round(float(r.get("start_min", 0.0)), 2),
                    round(float(r.get("end_min", 0.0)), 2),
                    round(float(r.get("duration", 0.0)), 2),
                    float(r.get("s_baseline", 0.0)),
                    float(r.get("abs_area", 0.0)),
                    float(r.get("k_factor", 0.0)),
                    float(r.get("n_mol", 0.0)),
                    float(r.get("n_mmol", 0.0)),
                    round(float(r.get("q_100", 0.0)), 4),
                    round(float(r.get("q_dry", 0.0)), 4),
                    round(float(r.get("q_net", 0.0)), 4),
                ]

                for col_idx, val in enumerate(vals, 1):
                    cell = ws.cell(row=curr_row, column=col_idx, value=val)
                    cell.font = Font(name="Calibri", size=9)
                    cell.border = cell_border
                    if col_idx in [1, 3, 4]:
                        cell.alignment = align_c
                    elif col_idx == 2:
                        cell.alignment = align_l
                    else:
                        cell.alignment = align_c
                        if col_idx in [8, 9, 11]:
                            cell.number_format = "0.00E+00"
                        elif col_idx in [10]:
                            cell.number_format = "#,##0"
                        elif col_idx in [12, 13, 14, 15]:
                            cell.number_format = "0.0000"

                curr_row += 1

        for col_idx in range(1, len(headers) + 1):
            col_letter = get_column_letter(col_idx)
            ws.column_dimensions[col_letter].width = max(len(headers[col_idx - 1]) + 4, 13)
        ws.column_dimensions["B"].width = 28

    def open_master_excel(self):
        """Regenerates the Excel summary file and opens it with the OS default viewer."""
        p = self.generate_master_excel()
        if os.path.exists(p):
            os.startfile(p)
            return True
        return False
