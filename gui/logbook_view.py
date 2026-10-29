import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
from core import comparative_report as CR


class SampleDialog(tk.Toplevel):
    """Modal dialog for creating or editing sample metadata."""
    def __init__(self, parent, title="New Sample", sample_data=None):
        super().__init__(parent)
        self.title(title)
        self.geometry("540x480")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.result = None
        self.sample_data = sample_data or {}

        self.create_widgets()
        self.center_window(parent)

    def center_window(self, parent):
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_rooty() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

    def create_widgets(self):
        container = ttk.Frame(self, padding=16)
        container.pack(fill=tk.BOTH, expand=True)

        header = ttk.Label(container, text="Sample Information & Synthesis Details", font=("Segoe UI", 11, "bold"))
        header.pack(anchor="w", pady=(0, 10))

        form = ttk.Frame(container)
        form.pack(fill=tk.X, expand=True)

        row = 0
        ttk.Label(form, text="Sample ID:*").grid(row=row, column=0, sticky="w", pady=5)
        self.id_var = tk.StringVar(value=self.sample_data.get("sample_id", ""))
        self.id_entry = ttk.Entry(form, textvariable=self.id_var, width=30)
        self.id_entry.grid(row=row, column=1, sticky="ew", pady=5)
        if self.sample_data.get("sample_id"):
            self.id_entry.config(state="readonly")
        row += 1

        ttk.Label(form, text="Complete Material Information:*").grid(row=row, column=0, sticky="w", pady=5)
        self.mat_var = tk.StringVar(value=self.sample_data.get("material_name", ""))
        ttk.Entry(form, textvariable=self.mat_var, width=30).grid(row=row, column=1, sticky="ew", pady=5)
        row += 1

        ttk.Label(form, text="Operator / Researcher:").grid(row=row, column=0, sticky="w", pady=5)
        op_val = self.sample_data.get("operator", "Shayan")
        if op_val == "Shayan / Jeronimo":
            op_val = "Shayan"
        self.op_var = tk.StringVar(value=op_val)
        ttk.Entry(form, textvariable=self.op_var, width=30).grid(row=row, column=1, sticky="ew", pady=5)
        row += 1

        ttk.Label(form, text="Assay Date (YYYY-MM-DD):").grid(row=row, column=0, sticky="w", pady=5)
        default_date = self.sample_data.get("date") or datetime.now().strftime("%Y-%m-%d")
        self.date_var = tk.StringVar(value=default_date)
        ttk.Entry(form, textvariable=self.date_var, width=30).grid(row=row, column=1, sticky="ew", pady=5)
        row += 1

        # Optional Mass / Water Loss / Ref Ads (leave blank for '-' in Sample Inventory)
        existing_mass = float(self.sample_data.get("mass_total_g", 0.0) or 0.0)
        existing_water = float(self.sample_data.get("water_loss_pct", 0.0) or 0.0)
        existing_ref_ads = float(self.sample_data.get("ref_ads", self.sample_data.get("ref_ads_mmol_g", 0.0)) or 0.0)

        ttk.Label(form, text="Total Mass (g) [optional — blank = '-']:").grid(row=row, column=0, sticky="w", pady=5)
        self.mass_var = tk.StringVar(value=f"{existing_mass:.4f}" if existing_mass > 0 else "")
        ttk.Entry(form, textvariable=self.mass_var, width=30).grid(row=row, column=1, sticky="ew", pady=5)
        row += 1

        ttk.Label(form, text="Water Loss (%) [optional — blank = '-']:").grid(row=row, column=0, sticky="w", pady=5)
        self.water_var = tk.StringVar(value=f"{existing_water:.2f}" if (existing_mass > 0 and existing_water > 0) else "")
        ttk.Entry(form, textvariable=self.water_var, width=30).grid(row=row, column=1, sticky="ew", pady=5)
        row += 1

        ttk.Label(form, text="Ref Ads (mmol/g) [optional — blank = '-']:").grid(row=row, column=0, sticky="w", pady=5)
        self.ref_ads_var = tk.StringVar(value=f"{existing_ref_ads:.4f}" if (existing_mass > 0 and existing_ref_ads > 0) else "")
        ttk.Entry(form, textvariable=self.ref_ads_var, width=30).grid(row=row, column=1, sticky="ew", pady=5)
        row += 1

        ttk.Label(
            form,
            text="Tip: Leave Mass / Water Loss blank if not applicable (e.g. TGA-only pastes); '-' will be shown.",
            font=("Segoe UI", 8, "italic"),
            foreground="#6c757d"
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 4))
        row += 1

        ttk.Label(form, text="Notes / Observations:").grid(row=row, column=0, sticky="nw", pady=5)
        self.notes_text = tk.Text(form, height=3, width=30, font=("Segoe UI", 9))
        self.notes_text.grid(row=row, column=1, sticky="ew", pady=5)
        self.notes_text.insert("1.0", self.sample_data.get("notes", ""))
        row += 1

        form.columnconfigure(1, weight=1)

        # Buttons
        btn_frame = ttk.Frame(container)
        btn_frame.pack(fill=tk.X, pady=(12, 0))

        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side=tk.RIGHT, padx=4)
        ttk.Button(btn_frame, text="💾 Save Sample", command=self.on_save).pack(side=tk.RIGHT, padx=4)

    @staticmethod
    def _parse_optional_float(val_str):
        s = (val_str or "").strip()
        if not s or s in ("-", "—", "none", "null"):
            return 0.0
        return float(s.replace(",", "."))

    def on_save(self):
        sample_id = self.id_var.get().strip()
        mat_name = self.mat_var.get().strip()

        if not sample_id:
            messagebox.showwarning("Required Field", "Sample ID cannot be empty.", parent=self)
            self.id_entry.focus_set()
            return
        if not mat_name:
            messagebox.showwarning("Required Field", "Material name cannot be empty.", parent=self)
            return

        try:
            mass_val = self._parse_optional_float(self.mass_var.get())
            water_val = self._parse_optional_float(self.water_var.get())
            ref_ads_val = self._parse_optional_float(self.ref_ads_var.get())
        except ValueError:
            messagebox.showwarning(
                "Invalid Number",
                "Total Mass, Water Loss, and Ref Ads must be valid numbers or left blank ('-').",
                parent=self
            )
            return

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.result = {
            "sample_id": sample_id,
            "material_name": mat_name,
            "operator": self.op_var.get().strip() or "Shayan",
            "date": self.date_var.get().strip(),
            "mass_total_g": mass_val,
            "water_loss_pct": water_val if mass_val > 0 else 0.0,
            "ref_ads": ref_ads_val if mass_val > 0 else 0.0,
            "ref_des": float(self.sample_data.get("ref_des", 0.00) or 0.0),
            "c0": float(self.sample_data.get("c0", 0.15) or 0.15),
            "flow_total": float(self.sample_data.get("flow_total", 100.0) or 100.0),
            "temp_c": float(self.sample_data.get("temp_c", 24.0) or 24.0),
            "notes": self.notes_text.get("1.0", tk.END).strip(),
            "status": self.sample_data.get("status", "Registered"),
            "created_at": self.sample_data.get("created_at") or now_str,
        }
        self.destroy()


class ComparativeReportDialog(tk.Toplevel):
    """
    Modal dialog allowing the user to select any combination of samples/materials
    to generate:
      1) Combined MS Adsorption / Desorption Comparative Analysis Report
      2) Combined TGA / DTG Multi-Sample Comparative Analysis Report
    All outputs are saved into `data_vault/Comparative_Analysis_Reports/`.
    """
    def __init__(self, parent, vault, preselected_sample_ids=None, initial_tab=0):
        super().__init__(parent)
        self.title("📊 Generate Comparative Analysis Report (MS Adsorption/Desorption & TGA)")
        self.geometry("860x620")
        self.transient(parent)
        self.grab_set()

        self.vault = vault
        self.preselected_sample_ids = set(preselected_sample_ids or [])
        self.ms_vars = {}
        self.tga_items = []

        self._build_ui(initial_tab)
        self._center(parent)

    def _center(self, parent):
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_rooty() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

    def _build_ui(self, initial_tab=0):
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill=tk.BOTH, expand=True)

        top_lbl = ttk.Label(
            outer,
            text="📊 Comparative Analysis Report Generator — Saved in data_vault/Comparative_Analysis_Reports/",
            font=("Segoe UI", 11, "bold"),
            foreground="#1d3557"
        )
        top_lbl.pack(anchor="w", pady=(0, 8))

        self.nb = ttk.Notebook(outer)
        self.nb.pack(fill=tk.BOTH, expand=True)

        tab_ms = ttk.Frame(self.nb, padding=10)
        tab_tga = ttk.Frame(self.nb, padding=10)
        self.nb.add(tab_ms, text=" 🧪 1. MS Adsorption / Desorption Comparison ")
        self.nb.add(tab_tga, text=" 🔥 2. TGA / DTG Thermal Analysis Comparison ")

        self._build_ms_tab(tab_ms)
        self._build_tga_tab(tab_tga)

        if initial_tab in (0, 1):
            self.nb.select(initial_tab)

        bottom = ttk.Frame(outer)
        bottom.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(bottom, text="📁 Open Comparative_Analysis_Reports Folder",
                   command=self._open_comp_root).pack(side=tk.LEFT)
        ttk.Button(bottom, text="Close", command=self.destroy).pack(side=tk.RIGHT)

    # ---- Tab 1: MS Comparison ----
    def _build_ms_tab(self, parent):
        info = ttk.Label(
            parent,
            text="Check the samples/materials you want to combine into a single MS Adsorption & Desorption comparative table, graph (1200 DPI), Excel & PDF report:",
            font=("Segoe UI", 9)
        )
        info.pack(anchor="w", pady=(0, 6))

        title_row = ttk.Frame(parent)
        title_row.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(title_row, text="Report Title:").pack(side=tk.LEFT)
        self.ms_title_var = tk.StringVar(value="Comparative CO₂ Adsorption & Desorption Analysis Report")
        ttk.Entry(title_row, textvariable=self.ms_title_var, width=55).pack(side=tk.LEFT, padx=6, fill=tk.X, expand=True)

        sel_bar = ttk.Frame(parent)
        sel_bar.pack(fill=tk.X, pady=(0, 6))
        ttk.Button(sel_bar, text="✅ Select All With MS Data", command=self._ms_select_with_data).pack(side=tk.LEFT, padx=2)
        ttk.Button(sel_bar, text="☑️ Select All Samples", command=lambda: self._ms_set_all(True)).pack(side=tk.LEFT, padx=2)
        ttk.Button(sel_bar, text="⬜ Clear Selection", command=lambda: self._ms_set_all(False)).pack(side=tk.LEFT, padx=2)

        list_frame = ttk.LabelFrame(parent, text=" Select Samples for MS Comparative Table ", padding=6)
        list_frame.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(list_frame, bg="#ffffff", highlightthickness=0)
        scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=canvas.yview)
        inner = tk.Frame(canvas, bg="#ffffff")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        all_recs, _ = CR.collect_ms_sample_records(self.vault)
        self._ms_records_map = {r["sample_id"]: r for r in all_recs}

        for idx, rec in enumerate(all_recs):
            s_id = rec["sample_id"]
            has_ms = rec["has_ms"]
            default_chk = (s_id in self.preselected_sample_ids) if len(self.preselected_sample_ids) >= 2 else has_ms
            var = tk.BooleanVar(value=default_chk)
            self.ms_vars[s_id] = var

            mass_txt = f"{rec['mass_total_g']:.4f} g" if rec["mass_total_g"] > 0 else "-"
            ms_badge = (
                f"✅ MS Analyzed (Mean Ads: {rec['mean_ads']:.3f} mmol/g, Des: {rec['mean_des']:.3f} mmol/g)"
                if has_ms else "— No MS cycles attached (will show '-' in table)"
            )
            lbl_text = f"[{s_id}]  {rec['material_name']}   |   Date: {rec['date']}   |   Mass: {mass_txt}   |   {ms_badge}"
            cb = tk.Checkbutton(
                inner, text=lbl_text, variable=var, bg="#ffffff",
                anchor="w", font=("Segoe UI", 9),
                fg="#1d3557" if has_ms else "#6c757d"
            )
            cb.grid(row=idx, column=0, sticky="w", padx=6, pady=2)

        act_bar = ttk.Frame(parent)
        act_bar.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(
            act_bar,
            text="📄 Generate MS Comparative Report (Excel + PDF + 1200 DPI PNG + HTML)",
            command=self._on_generate_ms_report
        ).pack(side=tk.RIGHT, padx=4)

    def _ms_select_with_data(self):
        for s_id, var in self.ms_vars.items():
            rec = self._ms_records_map.get(s_id, {})
            var.set(bool(rec.get("has_ms")))

    def _ms_set_all(self, state):
        for var in self.ms_vars.values():
            var.set(bool(state))

    def _on_generate_ms_report(self):
        chosen = [s_id for s_id, var in self.ms_vars.items() if var.get()]
        if not chosen:
            messagebox.showwarning("No Samples Selected", "Please select at least one sample to compare.", parent=self)
            return
        try:
            out = CR.generate_ms_comparative_report(
                self.vault,
                chosen,
                report_title=self.ms_title_var.get().strip() or "Comparative CO₂ Adsorption & Desorption Analysis Report"
            )
        except Exception as e:
            messagebox.showerror("Error Generating Report", f"Could not generate MS comparative report:\n{e}", parent=self)
            return

        msg = (
            f"MS Comparative Report generated for {len(chosen)} sample(s)!\n\n"
            f"Saved in folder:\n{out['folder']}\n\n"
            f"Files created:\n"
            f"• {os.path.basename(out['excel'])}\n"
            f"• {os.path.basename(out['pdf'])}\n"
            f"• {os.path.basename(out['png_1200dpi'])}\n"
            f"• {os.path.basename(out['html'])}\n\n"
            f"Open the report folder now?"
        )
        if messagebox.askyesno("MS Comparative Report Ready", msg, parent=self):
            os.startfile(out["folder"])

    # ---- Tab 2: TGA Comparison ----
    def _build_tga_tab(self, parent):
        info = ttk.Label(
            parent,
            text="Select multiple TGA datasets (across Zeolite batches, Silica Paste, or external .xlsx/.csv files) to overlay TGA & DTG curves and compare mass-loss steps:",
            font=("Segoe UI", 9)
        )
        info.pack(anchor="w", pady=(0, 6))

        t_row = ttk.Frame(parent)
        t_row.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(t_row, text="Report Title:").pack(side=tk.LEFT)
        self.tga_title_var = tk.StringVar(value="Comparative TGA / DTG Thermal Analysis")
        ttk.Entry(t_row, textvariable=self.tga_title_var, width=42).pack(side=tk.LEFT, padx=6, fill=tk.X, expand=True)

        ttk.Label(t_row, text="Sub-header:").pack(side=tk.LEFT, padx=(6, 2))
        self.tga_sub_var = tk.StringVar(value="Multi-sample TGA & DTG comparison")
        ttk.Entry(t_row, textvariable=self.tga_sub_var, width=28).pack(side=tk.LEFT, padx=2)

        btn_bar = ttk.Frame(parent)
        btn_bar.pack(fill=tk.X, pady=(0, 6))
        ttk.Button(btn_bar, text="☑️ Select All TGA Files", command=lambda: self._tga_set_all(True)).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_bar, text="⬜ Clear Selection", command=lambda: self._tga_set_all(False)).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_bar, text="➕ Add External TGA File (.xlsx / .csv)…", command=self._tga_add_external).pack(side=tk.LEFT, padx=8)

        list_frame = ttk.LabelFrame(parent, text=" Available TGA Datasets (Check to Include & Edit Legend Label) ", padding=6)
        list_frame.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(list_frame, bg="#ffffff", highlightthickness=0)
        scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=canvas.yview)
        self.tga_inner = tk.Frame(canvas, bg="#ffffff")
        self.tga_inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.tga_inner, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        for ds in CR.list_available_tga_datasets(self.vault):
            self._add_tga_row(ds, checked=True)

        act_bar = ttk.Frame(parent)
        act_bar.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(
            act_bar,
            text="📄 Generate TGA Comparative Report (Style A & Style B 1200 DPI + Excel + PDF + HTML)",
            command=self._on_generate_tga_report
        ).pack(side=tk.RIGHT, padx=4)

    def _add_tga_row(self, ds, checked=True):
        row_idx = len(self.tga_items)
        var = tk.BooleanVar(value=checked)
        lbl_var = tk.StringVar(value=ds.get("label", ds.get("sample_id", "Sample")))

        cb = tk.Checkbutton(
            self.tga_inner,
            text=f"[{ds.get('sample_id', 'External')}]  {ds.get('filename', '')}",
            variable=var,
            bg="#ffffff",
            anchor="w",
            font=("Segoe UI", 9, "bold"),
            fg="#1d3557"
        )
        cb.grid(row=row_idx, column=0, sticky="w", padx=6, pady=3)

        tk.Label(self.tga_inner, text="Legend Label:", bg="#ffffff", font=("Segoe UI", 9)).grid(row=row_idx, column=1, padx=(12, 4))
        ent = ttk.Entry(self.tga_inner, textvariable=lbl_var, width=32)
        ent.grid(row=row_idx, column=2, sticky="w", pady=3)

        self.tga_items.append({
            "var": var,
            "label_var": lbl_var,
            "dataset": ds
        })

    def _tga_set_all(self, state):
        for item in self.tga_items:
            item["var"].set(bool(state))

    def _tga_add_external(self):
        paths = filedialog.askopenfilenames(
            parent=self,
            title="Select Additional TGA Data File(s) (.xlsx / .csv)",
            filetypes=[("TGA Data Files", "*.xlsx;*.xls;*.csv;*.txt"), ("All Files", "*.*")]
        )
        for p in paths:
            fn = os.path.basename(p)
            stem = os.path.splitext(fn)[0]
            ds = {
                "sample_id": "External",
                "material_name": stem,
                "filename": fn,
                "path": p,
                "label": stem,
                "composition": None,
                "conditions": {"atmosphere": "Air", "flow_ml_min": 50.0, "heating_rate": 10.0},
            }
            self._add_tga_row(ds, checked=True)

    def _on_generate_tga_report(self):
        selected = []
        for item in self.tga_items:
            if item["var"].get():
                ds = dict(item["dataset"])
                ds["label"] = item["label_var"].get().strip() or ds.get("label", "Sample")
                selected.append(ds)

        if not selected:
            messagebox.showwarning("No TGA Files Selected", "Please select at least one TGA dataset to compare.", parent=self)
            return

        try:
            out = CR.generate_tga_comparative_report(
                self.vault,
                selected,
                report_title=self.tga_title_var.get().strip() or "Comparative TGA / DTG Thermal Analysis",
                subtitle=self.tga_sub_var.get().strip()
            )
        except Exception as e:
            messagebox.showerror("Error Generating TGA Comparison", f"Failed to generate TGA comparative report:\n{e}", parent=self)
            return

        msg = (
            f"TGA Comparative Report generated for {len(selected)} dataset(s)!\n\n"
            f"Saved in folder:\n{out['folder']}\n\n"
            f"5-File Publication Package created:\n"
            f"• {os.path.basename(out['excel'])}\n"
            f"• {os.path.basename(out['pdf'])}\n"
            f"• {os.path.basename(out['styleA_1200dpi'])}\n"
            f"• {os.path.basename(out['styleB_1200dpi'])}\n"
            f"• {os.path.basename(out['html'])}\n\n"
            f"Open the report folder now?"
        )
        if messagebox.askyesno("TGA Comparative Report Ready", msg, parent=self):
            os.startfile(out["folder"])

    def _open_comp_root(self):
        folder = CR.get_comparative_root_dir(self.vault.vault_path)
        os.makedirs(folder, exist_ok=True)
        os.startfile(folder)


class LogbookView(ttk.Frame):
    """
    Module 1: Sample Logbook View.
    Displays sample list (newest added at the top), KPI summaries, and allows creating,
    editing, managing samples, and generating custom MS & TGA Comparative Reports.
    """
    def __init__(self, parent, vault, on_select_sample_callback=None, on_open_mass_spec_callback=None, on_open_technique_callback=None):
        super().__init__(parent, padding=8)
        self.vault = vault
        self.on_select_sample_callback = on_select_sample_callback
        self.on_open_mass_spec_callback = on_open_mass_spec_callback
        self.on_open_technique_callback = on_open_technique_callback
        self.active_sample_id = None

        self.create_widgets()
        self.refresh_table()

    def create_widgets(self):
        # 1. Top KPI Summary Cards
        kpi_frame = ttk.Frame(self)
        kpi_frame.pack(fill=tk.X, pady=(0, 8))

        self.card_total = self._create_kpi_card(kpi_frame, "📦 Total Samples", "0", "#1d3557")
        self.card_total.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

        self.card_analyzed = self._create_kpi_card(kpi_frame, "✅ Analyzed", "0", "#2a9d8f")
        self.card_analyzed.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

        self.card_pending = self._create_kpi_card(kpi_frame, "⏳ Pending Analysis", "0", "#e76f51")
        self.card_pending.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

        # 2. Search & Action Toolbar
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, pady=(4, 6))

        ttk.Label(toolbar, text="🔍 Search:").pack(side=tk.LEFT, padx=(0, 4))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self.filter_table())
        search_entry = ttk.Entry(toolbar, textvariable=self.search_var, width=20)
        search_entry.pack(side=tk.LEFT, padx=(0, 8))

        ttk.Button(toolbar, text="➕ New Sample", command=self.on_new_sample).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="✏️ Edit", command=self.on_edit_sample).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="🗑️ Delete", command=self.on_delete_sample).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="📂 Open Folder", command=self.on_open_folder).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="🔄 Refresh", command=self.on_refresh).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="📊 Sample Register & Summary", command=self.on_open_master_excel).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="📈 Comparative Report…", command=self.on_open_comparative_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="📁 Comparative Folder", command=self.on_open_comparative_folder).pack(side=tk.LEFT, padx=2)

        self.btn_go_hub = ttk.Button(
            toolbar,
            text="🔬 View Characterizations ➔",
            command=self.on_go_to_hub
        )
        self.btn_go_hub.pack(side=tk.RIGHT, padx=4)

        # 2b. Contextual Characterization Technique Bar (Direct 1-click jump buttons)
        self.tech_bar = tk.Frame(self, bg="#edf2f7", bd=1, relief="solid", padx=10, pady=5)
        self.tech_bar.pack(fill=tk.X, pady=(0, 6))

        self.lbl_tech_header = tk.Label(
            self.tech_bar,
            text="🏷️ Active Sample:",
            font=("Segoe UI", 9, "bold"),
            bg="#edf2f7",
            fg="#1d3557"
        )
        self.lbl_tech_header.pack(side=tk.LEFT, padx=(0, 8))

        self.tech_buttons_frame = tk.Frame(self.tech_bar, bg="#edf2f7")
        self.tech_buttons_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 3. Main Samples Treeview Table (extended selection supported for multi-sample comparison)
        table_frame = ttk.Frame(self)
        table_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("id", "material", "techs", "date", "operator", "status", "files_cnt")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="extended")

        self.tree.heading("id", text="Sample ID")
        self.tree.heading("material", text="Complete Material Information")
        self.tree.heading("techs", text="Characterizations")
        self.tree.heading("date", text="Date")
        self.tree.heading("operator", text="Operator")
        self.tree.heading("status", text="Status")
        self.tree.heading("files_cnt", text="Files")

        self.tree.column("id", width=110, anchor="center")
        self.tree.column("material", width=250, anchor="w")
        self.tree.column("techs", width=200, anchor="w")
        self.tree.column("date", width=95, anchor="center")
        self.tree.column("operator", width=120, anchor="center")
        self.tree.column("status", width=95, anchor="center")
        self.tree.column("files_cnt", width=65, anchor="center")

        scroll_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        scroll_x = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        scroll_x.pack(side=tk.BOTTOM, fill=tk.X)

        self.tree.bind("<<TreeviewSelect>>", self.on_row_select)
        self.tree.bind("<Double-1>", lambda e: self.on_go_to_hub())

    def _create_kpi_card(self, parent, title, value, color):
        frame = tk.Frame(parent, bg="#ffffff", bd=1, relief="solid", padx=10, pady=8)
        lbl_title = tk.Label(frame, text=title, font=("Segoe UI", 9), bg="#ffffff", fg="#6c757d")
        lbl_title.pack(anchor="w")
        lbl_val = tk.Label(frame, text=value, font=("Segoe UI", 14, "bold"), bg="#ffffff", fg=color)
        lbl_val.pack(anchor="w")
        frame.val_label = lbl_val
        return frame

    def refresh_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        logbook = self.vault.logbook
        query = self.search_var.get().lower().strip()

        tot_samples = len(logbook)
        analyzed_count = 0
        masses = []

        # Sort newest added at the TOP (descending by created_at, date, sample_id)
        sorted_items = sorted(
            logbook.items(),
            key=lambda kv: (
                str(kv[1].get("created_at") or kv[1].get("date") or ""),
                str(kv[1].get("date") or ""),
                str(kv[0])
            ),
            reverse=True
        )

        for s_id, data in sorted_items:
            mat = data.get("material_name", "")
            op = data.get("operator", "")

            if query and (query not in s_id.lower() and query not in mat.lower() and query not in op.lower()):
                continue

            status = data.get("status", "Registered")
            if status in ["Analyzed", "Analizada"]:
                status = "Analyzed"
                analyzed_count += 1
            elif status == "Registrada":
                status = "Registered"

            mass_tot = float(data.get("mass_total_g", 0.0) or 0.0)
            if mass_tot > 0:
                masses.append(mass_tot)

            chars = data.get("characterizations", {})
            TECH_BADGES = [
                ("mass_spec", "🧪 MS"),
                ("thermal_profile", "🌡️ Therm"),
                ("tga", "🔥 TGA"),
                ("rheology", "🌊 Rheo"),
                ("tomography", "🧊 CT"),
                ("sem_tem", "🔍 SEM"),
                ("hg_porosimetry", "💧 MIP"),
                ("bet", "📐 BET"),
            ]
            t_badges = []
            for t_k, t_lbl in TECH_BADGES:
                cnt = len(chars.get(t_k, {}).get("files", []))
                if cnt == 0 and t_k == "mass_spec" and "files" in data:
                    cnt = len([f for f in data.get("files", []) if f.get("filename", "").lower().endswith(".asc")])
                if cnt > 0:
                    t_badges.append(f"{t_lbl}({cnt})")
            techs_str = "  ".join(t_badges) if t_badges else "—"

            total_files = 0
            for tech, tdata in chars.items():
                total_files += len(tdata.get("files", []))
            if total_files == 0 and "files" in data:
                total_files = len(data.get("files", []))

            item_id = self.tree.insert("", tk.END, values=(
                s_id,
                mat,
                techs_str,
                data.get("date", "-"),
                op,
                status,
                str(total_files)
            ))

            if self.active_sample_id == s_id:
                self.tree.selection_set(item_id)
                self.tree.see(item_id)

        self.card_total.val_label.config(text=str(tot_samples))
        self.card_analyzed.val_label.config(text=str(analyzed_count))
        pending_cnt = max(0, tot_samples - analyzed_count)
        self.card_pending.val_label.config(text=str(pending_cnt))

        self.update_technique_buttons(self.active_sample_id)

    def filter_table(self):
        self.refresh_table()

    def get_selected_sample_id(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return self.tree.item(sel[0], "values")[0]

    def get_selected_sample_ids(self):
        return [self.tree.item(item, "values")[0] for item in self.tree.selection()]

    def on_row_select(self, event=None):
        s_id = self.get_selected_sample_id()
        if s_id:
            self.active_sample_id = s_id
            self.update_technique_buttons(s_id)
            if self.on_select_sample_callback:
                self.on_select_sample_callback(s_id)

    def update_technique_buttons(self, s_id):
        for w in self.tech_buttons_frame.winfo_children():
            w.destroy()

        if not s_id or s_id not in self.vault.logbook:
            self.lbl_tech_header.config(text="🏷️ No Sample Selected")
            lbl_none = tk.Label(
                self.tech_buttons_frame,
                text="Click on any sample row below to inspect and jump directly to its characterizations.",
                font=("Segoe UI", 9, "italic"),
                bg="#edf2f7",
                fg="#6c757d"
            )
            lbl_none.pack(side=tk.LEFT)
            return

        data = self.vault.logbook[s_id]
        chars = data.get("characterizations", {})

        self.lbl_tech_header.config(text=f"🏷️ [{s_id}] Characterizations:")

        TECH_SPECS = [
            ("mass_spec", "🧪 Mass Spec", "#1d3557", "#ffffff"),
            ("thermal_profile", "🌡️ Thermal Profile", "#d35400", "#ffffff"),
            ("tga", "🔥 TGA", "#c0392b", "#ffffff"),
            ("rheology", "🌊 Rheology", "#0277bd", "#ffffff"),
            ("tomography", "🧊 Tomography", "#4a148c", "#ffffff"),
            ("sem_tem", "🔍 SEM / TEM", "#2e7d32", "#ffffff"),
            ("hg_porosimetry", "💧 Hg Porosimetry", "#00695c", "#ffffff"),
            ("bet", "📐 BET", "#00796b", "#ffffff"),
        ]

        found_any = False
        for tech_key, btn_label, fg_col, bg_col in TECH_SPECS:
            f_list = chars.get(tech_key, {}).get("files", [])
            if not f_list and tech_key == "mass_spec" and "files" in data:
                f_list = [f for f in data.get("files", []) if f.get("filename", "").lower().endswith(".asc")]

            if f_list:
                found_any = True
                btn = tk.Button(
                    self.tech_buttons_frame,
                    text=f"{btn_label} ({len(f_list)}) ➔",
                    font=("Segoe UI", 8, "bold"),
                    fg=fg_col,
                    bg=bg_col,
                    activebackground=fg_col,
                    activeforeground="#ffffff",
                    relief=tk.RAISED,
                    bd=1,
                    padx=7,
                    pady=2,
                    cursor="hand2",
                    command=lambda tk=tech_key: self.on_technique_click(tk)
                )
                btn.pack(side=tk.LEFT, padx=3)

        if not found_any:
            lbl_empty = tk.Label(
                self.tech_buttons_frame,
                text="No characterization files attached to this sample yet.",
                font=("Segoe UI", 9, "italic"),
                bg="#edf2f7",
                fg="#6c757d"
            )
            lbl_empty.pack(side=tk.LEFT, padx=(0, 6))

            btn_attach = tk.Button(
                self.tech_buttons_frame,
                text="➕ Open Hub to Attach Files ➔",
                font=("Segoe UI", 8, "bold"),
                fg="#2a9d8f",
                bg="#ffffff",
                relief=tk.RAISED,
                bd=1,
                padx=6,
                pady=2,
                cursor="hand2",
                command=self.on_go_to_hub
            )
            btn_attach.pack(side=tk.LEFT)

    def on_technique_click(self, tech_key):
        if self.active_sample_id:
            if self.on_open_technique_callback:
                self.on_open_technique_callback(self.active_sample_id, tech_key)
            else:
                self.on_go_to_hub()

    def on_new_sample(self):
        dialog = SampleDialog(self.winfo_toplevel(), title="Register New Sample")
        self.wait_window(dialog)
        if dialog.result:
            s_id = dialog.result["sample_id"]
            self.vault.create_or_update_sample(s_id, dialog.result)
            self.active_sample_id = s_id
            self.refresh_table()
            messagebox.showinfo("Sample Registered", f"Sample '{s_id}' registered at the top of the logbook.")
            if self.on_select_sample_callback:
                self.on_select_sample_callback(s_id)

    def on_edit_sample(self):
        s_id = self.get_selected_sample_id()
        if not s_id:
            messagebox.showinfo("Select Sample", "Please select a sample from the table to edit.")
            return

        current_data = self.vault.logbook.get(s_id, {})
        dialog = SampleDialog(self.winfo_toplevel(), title=f"Edit Sample: {s_id}", sample_data=current_data)
        self.wait_window(dialog)
        if dialog.result:
            self.vault.create_or_update_sample(s_id, dialog.result)
            self.refresh_table()
            if self.on_select_sample_callback:
                self.on_select_sample_callback(s_id)

    def on_delete_sample(self):
        s_id = self.get_selected_sample_id()
        if not s_id:
            messagebox.showinfo("Select Sample", "Please select a sample to delete.")
            return

        confirm = messagebox.askyesno(
            "Confirm Deletion",
            f"Are you sure you want to delete sample '{s_id}' and all associated files?\nThis action cannot be undone."
        )
        if confirm:
            self.vault.delete_sample(s_id)
            self.active_sample_id = None
            self.refresh_table()
            if self.on_select_sample_callback:
                self.on_select_sample_callback(None)

    def on_open_folder(self):
        s_id = self.get_selected_sample_id()
        if not s_id:
            messagebox.showinfo("Select Sample", "Please select a sample to open its directory.")
            return
        folder = self.vault.get_sample_dir(s_id)
        if os.path.exists(folder):
            os.startfile(folder)
        else:
            messagebox.showwarning("Folder Not Found", f"Directory not found:\n{folder}")

    def on_go_to_hub(self):
        s_id = self.get_selected_sample_id()
        if not s_id:
            messagebox.showinfo("Select Sample", "Please select a sample to inspect its characterizations.")
            return
        if self.on_select_sample_callback:
            self.on_select_sample_callback(s_id, switch_tab=True)

    def on_open_master_excel(self):
        try:
            ok = self.vault.open_master_excel()
            if not ok:
                messagebox.showwarning("Master Excel", "Could not open Master Excel file.")
        except Exception as e:
            messagebox.showerror("Master Excel Error", f"Failed to generate or open Master Excel file:\n{e}")

    def on_open_comparative_dialog(self, initial_tab=0):
        selected_ids = self.get_selected_sample_ids()
        dlg = ComparativeReportDialog(
            self.winfo_toplevel(),
            self.vault,
            preselected_sample_ids=selected_ids,
            initial_tab=initial_tab
        )
        self.wait_window(dlg)

    def on_open_comparative_folder(self):
        folder = CR.get_comparative_root_dir(self.vault.vault_path)
        os.makedirs(folder, exist_ok=True)
        os.startfile(folder)

    def on_refresh(self):
        self.vault.reconcile_vault_filesystem()
        self.refresh_table()
