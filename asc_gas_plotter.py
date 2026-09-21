import os
import io
import glob
import json
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# SciPy imports for Origin-style integration and peak analysis
import scipy.integrate as scipy_integ
import scipy.interpolate as scipy_interp
import scipy.signal as scipy_signal

# Gas Mapping Dictionary (English Labels)
GAS_MAPPING = {
    "'0/0'": {"label": "N+ (m/z 14.13)", "full_name": "N+ / N2++ (Atomic Nitrogen)", "color": "#1f77b4"},
    "'0/1'": {"label": "O+ (m/z 16.13)", "full_name": "O+ (Atomic Oxygen)", "color": "#ff7f0e"},
    "'0/2'": {"label": "H2O (m/z 18.16)", "full_name": "H2O (Water Vapor)", "color": "#2ca02c"},
    "'0/3'": {"label": "N2 / CO (m/z 28.19)", "full_name": "N2 / CO (Molecular Nitrogen)", "color": "#d62728"},
    "'0/4'": {"label": "O2 (m/z 32.22)", "full_name": "O2 (Molecular Oxygen)", "color": "#9467bd"},
    "'0/5'": {"label": "Ar (m/z 40.22)", "full_name": "Ar (Argon)", "color": "#8c564b"},
    "'0/6'": {"label": "CO2 (m/z 44.28)", "full_name": "CO2 (Carbon Dioxide)", "color": "#e377c2"}
}

# Origin-style ROI Box Colors (Yellow for Adsorption, Pink/Magenta for Desorption, etc.)
ROI_PRESETS = {
    "adsorption": {"fill": "#ffff99", "border": "#d4af37", "label": "Adsorption", "baseline": "straight_line"},
    "desorption": {"fill": "#ff99ff", "border": "#c77dff", "label": "Desorption", "baseline": "horizontal_left"},
    "general": {"fill": "#99ff99", "border": "#38b000", "label": "General", "baseline": "straight_line"}
}

class ASCGasPlotterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Origin-Style Mass Spectrometry Integration & Cycle Pair Tool (.asc)")
        self.root.geometry("1420x900")
        self.root.minsize(1120, 740)

        # Base Directory
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.files_dict = {}
        self.current_df = None
        self.current_file_info = {}

        # Integration Ranges (Origin ROI Boxes): list of dicts
        self.ranges_list = []
        self.range_id_counter = 1

        # Persistent Saved Selections DB (.json)
        self.json_db_path = os.path.join(self.current_dir, "saved_roi_selections.json")
        self.saved_file_configs = self.load_all_saved_configs()

        # Interactive Dragging States
        self.drag_target = None  # (range_index, 'start' | 'end' | 'body')
        self.drag_initial_x = None
        self.drag_initial_range = None
        self.selected_range_idx = None

        self.has_plotted_once = False

        # CO2 Adsorption & Desorption Capacity Analysis (Tab 3)
        self.cap_mass_var = tk.DoubleVar(value=0.505)
        self.cap_water_pct_var = tk.DoubleVar(value=21.4)
        self.cap_c0_var = tk.DoubleVar(value=0.15)
        self.cap_flow_total_var = tk.DoubleVar(value=100.0)
        self.cap_temp_var = tk.DoubleVar(value=24.0)
        self.cap_ref_ads_var = tk.DoubleVar(value=0.23)
        self.cap_ref_des_var = tk.DoubleVar(value=0.00)
        
        self.cap_s_baseline_var = tk.DoubleVar(value=7.25e-10)
        self.cap_area_ads_var = tk.DoubleVar(value=1.5054e-9)
        self.cap_area_des_var = tk.DoubleVar(value=1.06058e-10)
        self.cap_auto_sync_var = tk.BooleanVar(value=True)
        self.last_capacity_results = {}

        # Set ttk style
        self.style = ttk.Style()
        if "vista" in self.style.theme_names():
            self.style.theme_use("vista")
        elif "clam" in self.style.theme_names():
            self.style.theme_use("clam")

        self.create_widgets()
        self.scan_files()

    def create_widgets(self):
        # Main Splitter: Left Control Panel, Right Plot Area
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Left Control Frame (Notebook with 2 Tabs)
        left_frame = ttk.Frame(main_paned, width=440)
        main_paned.add(left_frame, weight=0)

        # Right Plot Frame
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=1)

        # Left Notebook (Tabs)
        self.left_notebook = ttk.Notebook(left_frame)
        self.left_notebook.pack(fill=tk.BOTH, expand=True)

        tab_plot = ttk.Frame(self.left_notebook)
        tab_integ = ttk.Frame(self.left_notebook)
        tab_capacity = ttk.Frame(self.left_notebook)

        self.left_notebook.add(tab_plot, text=" 📊 Data & Plot ")
        self.left_notebook.add(tab_integ, text=" 📈 Adsorption / Desorption ")
        self.left_notebook.add(tab_capacity, text=" 🧪 CO₂ Capacity (q) ")

        # ==================== TAB 1: PLOT & GASES ====================
        
        file_frame = ttk.LabelFrame(tab_plot, text=" 1. Select Measurement File ", padding=8)
        file_frame.pack(fill=tk.X, padx=5, pady=5)

        self.file_combo = ttk.Combobox(file_frame, state="readonly", font=("Segoe UI", 9))
        self.file_combo.pack(fill=tk.X, pady=(0, 5))
        self.file_combo.bind("<<ComboboxSelected>>", self.on_file_selected)

        btn_row = ttk.Frame(file_frame)
        btn_row.pack(fill=tk.X)
        ttk.Button(btn_row, text="Refresh Folder", command=self.scan_files).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 2))
        ttk.Button(btn_row, text="Browse File...", command=self.browse_file).pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=(2, 0))

        # File Summary Info Panel
        self.info_frame = ttk.LabelFrame(tab_plot, text=" File Summary ", padding=8)
        self.info_frame.pack(fill=tk.X, padx=5, pady=5)

        self.lbl_date = ttk.Label(self.info_frame, text="Date: -", font=("Segoe UI", 9))
        self.lbl_date.pack(anchor=tk.W)
        self.lbl_time = ttk.Label(self.info_frame, text="Time: -", font=("Segoe UI", 9))
        self.lbl_time.pack(anchor=tk.W)
        self.lbl_cycles = ttk.Label(self.info_frame, text="Total Cycles: -", font=("Segoe UI", 9))
        self.lbl_cycles.pack(anchor=tk.W)
        self.lbl_duration = ttk.Label(self.info_frame, text="Duration: -", font=("Segoe UI", 9))
        self.lbl_duration.pack(anchor=tk.W)

        # Gas Selection Frame
        gas_frame = ttk.LabelFrame(tab_plot, text=" 2. Select Gases to Display ", padding=8)
        gas_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.gas_vars = {}
        for col, meta in GAS_MAPPING.items():
            var = tk.BooleanVar(value=False)
            self.gas_vars[col] = var

            chk_row = ttk.Frame(gas_frame)
            chk_row.pack(fill=tk.X, pady=2)

            color_box = tk.Label(chk_row, bg=meta["color"], width=2, height=1, relief="groove")
            color_box.pack(side=tk.LEFT, padx=(0, 6))

            chk = ttk.Checkbutton(
                chk_row, 
                text=meta["full_name"], 
                variable=var,
                command=lambda: self.update_plot(preserve_zoom=True)
            )
            chk.pack(side=tk.LEFT, anchor=tk.W)

        sel_btn_frame = ttk.Frame(gas_frame)
        sel_btn_frame.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(sel_btn_frame, text="Select All", command=self.select_all_gases).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 2))
        ttk.Button(sel_btn_frame, text="Clear All", command=self.clear_all_gases).pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=(2, 0))

        # Plot Options Frame
        opt_frame = ttk.LabelFrame(tab_plot, text=" 3. Plot Options ", padding=8)
        opt_frame.pack(fill=tk.X, padx=5, pady=5)

        scale_lbl = ttk.Label(opt_frame, text="Y-Axis Scale:", font=("Segoe UI", 9, "bold"))
        scale_lbl.pack(anchor=tk.W, pady=(0, 2))
        
        self.scale_var = tk.StringVar(value="linear")
        rb_lin = ttk.Radiobutton(opt_frame, text="Linear Scale", value="linear", variable=self.scale_var, command=lambda: self.update_plot(preserve_zoom=True))
        rb_lin.pack(anchor=tk.W)
        rb_log = ttk.Radiobutton(opt_frame, text="Logarithmic Scale (Log10)", value="log", variable=self.scale_var, command=lambda: self.update_plot(preserve_zoom=True))
        rb_log.pack(anchor=tk.W)

        xaxis_lbl = ttk.Label(opt_frame, text="X-Axis Unit:", font=("Segoe UI", 9, "bold"))
        xaxis_lbl.pack(anchor=tk.W, pady=(6, 2))

        self.xaxis_var = tk.StringVar(value="min")
        rb_min = ttk.Radiobutton(opt_frame, text="Time (min) [Minutes]", value="min", variable=self.xaxis_var, command=self.on_xaxis_change)
        rb_min.pack(anchor=tk.W)
        rb_sec = ttk.Radiobutton(opt_frame, text="Time (s) [Seconds]", value="sec", variable=self.xaxis_var, command=self.on_xaxis_change)
        rb_sec.pack(anchor=tk.W)
        rb_cyc = ttk.Radiobutton(opt_frame, text="Cycle Count", value="cycle", variable=self.xaxis_var, command=self.on_xaxis_change)
        rb_cyc.pack(anchor=tk.W)

        exp_frame = ttk.Frame(tab_plot, padding=5)
        exp_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(exp_frame, text="Export Plot Image (PNG)...", command=self.export_plot).pack(fill=tk.X, pady=2)


        # ==================== TAB 2: ADSORPTION / DESORPTION CYCLE INTEGRATION ====================

        # A. Target Gas & Auto-Detection
        origin_cfg_frame = ttk.LabelFrame(tab_integ, text=" Target Gas & Auto-Detect Pairs ", padding=8)
        origin_cfg_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(origin_cfg_frame, text="Target Data Plot (Gas):", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W)
        self.integ_gas_combo = ttk.Combobox(origin_cfg_frame, state="readonly", font=("Segoe UI", 9))
        self.integ_gas_combo["values"] = [meta["full_name"] for meta in GAS_MAPPING.values()]
        self.integ_gas_combo.current(6)  # Default CO2
        self.integ_gas_combo.pack(fill=tk.X, pady=(2, 6))
        self.integ_gas_combo.bind("<<ComboboxSelected>>", self.on_integ_gas_change)

        btn_detect_save_row = ttk.Frame(origin_cfg_frame)
        btn_detect_save_row.pack(fill=tk.X, pady=2)

        ttk.Button(
            btn_detect_save_row, 
            text="🤖 Auto-Detect Cycle Pairs", 
            command=self.auto_detect_cycle_pairs
        ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 2))

        ttk.Button(
            btn_detect_save_row, 
            text="💾 Save Selection for Current File", 
            command=self.save_current_file_selection
        ).pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=(2, 0))

        # B. Interactive Controls: Active Range Isolated Dragging & Fixed dx Width
        roi_ctrl_frame = ttk.LabelFrame(tab_integ, text=" Active ROI Controls & Fixed dx Width ", padding=8)
        roi_ctrl_frame.pack(fill=tk.X, padx=5, pady=5)

        lbl_instruct = ttk.Label(
            roi_ctrl_frame, 
            text="🔒 Isolation Protection: Only the ACTIVE ROI box (selected below)\ncan be dragged/edited on plot, protecting other ranges!", 
            font=("Segoe UI", 8, "italic"),
            foreground="#1d3557"
        )
        lbl_instruct.pack(fill=tk.X, pady=(0, 6))

        # Grid for x1, x2, dx and Lock Width
        edit_grid = ttk.Frame(roi_ctrl_frame)
        edit_grid.pack(fill=tk.X, pady=2)

        self.lbl_x1_name = ttk.Label(edit_grid, text="x1 (Start):", font=("Segoe UI", 9, "bold"))
        self.lbl_x1_name.grid(row=0, column=0, sticky=tk.W, padx=2)
        self.spn_start_var = tk.DoubleVar(value=0.0)
        self.spn_start = ttk.Spinbox(edit_grid, from_=0.0, to=100000.0, increment=0.5, textvariable=self.spn_start_var, width=8, command=self.on_spinbox_change)
        self.spn_start.grid(row=0, column=1, sticky=tk.W, padx=2)
        self.spn_start.bind("<Return>", self.on_spinbox_change)

        self.lbl_x2_name = ttk.Label(edit_grid, text="x2 (End):", font=("Segoe UI", 9, "bold"))
        self.lbl_x2_name.grid(row=0, column=2, sticky=tk.W, padx=2)
        self.spn_end_var = tk.DoubleVar(value=10.0)
        self.spn_end = ttk.Spinbox(edit_grid, from_=0.0, to=100000.0, increment=0.5, textvariable=self.spn_end_var, width=8, command=self.on_spinbox_change)
        self.spn_end.grid(row=0, column=3, sticky=tk.W, padx=2)
        self.spn_end.bind("<Return>", self.on_spinbox_change)

        ttk.Label(edit_grid, text="dx (Width):", font=("Segoe UI", 9, "bold")).grid(row=0, column=4, sticky=tk.W, padx=(8, 2))
        self.spn_dx_var = tk.DoubleVar(value=10.0)
        self.spn_dx = ttk.Spinbox(edit_grid, from_=0.1, to=100000.0, increment=0.5, textvariable=self.spn_dx_var, width=8, command=self.on_dx_spinbox_change)
        self.spn_dx.grid(row=0, column=5, sticky=tk.W, padx=2)
        self.spn_dx.bind("<Return>", self.on_dx_spinbox_change)

        # Lock Width Checkbox & Individual Baseline Mode Option
        bline_row = ttk.Frame(roi_ctrl_frame)
        bline_row.pack(fill=tk.X, pady=(6, 2))

        self.lock_dx_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bline_row, text="🔒 Lock Width (dx)", variable=self.lock_dx_var).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(bline_row, text="Baseline Mode:").pack(side=tk.LEFT, padx=(5, 2))
        self.roi_baseline_var = tk.StringVar(value="straight_line")
        self.combo_baseline = ttk.Combobox(
            bline_row, 
            state="readonly", 
            values=["Straight Line (Ads / Dip)", "Horizontal Line Y=Left (Des / Peak)", "Average Baseline (Ads Y0)", "Raw (Y=0)"],
            textvariable=self.roi_baseline_var,
            width=28
        )
        self.combo_baseline.pack(side=tk.LEFT, padx=2)
        self.combo_baseline.bind("<<ComboboxSelected>>", self.on_roi_baseline_change)

        btn_action_row = ttk.Frame(roi_ctrl_frame)
        btn_action_row.pack(fill=tk.X, pady=(8, 2))
        
        ttk.Button(btn_action_row, text="➕ Add Adsorption Box (Yellow)", command=self.add_adsorption_box).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        ttk.Button(btn_action_row, text="➕ Add Desorption Box (Pink)", command=self.add_desorption_box).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        ttk.Button(btn_action_row, text="🗑️ Delete Box", command=self.remove_selected_range).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        # C. Origin Data Display Table
        table_frame = ttk.LabelFrame(tab_integ, text=" Data Display (Origin Integration Output) ", padding=6)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        columns = ("id", "type", "x_range", "dx", "y0", "area", "fwhm")
        self.range_tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=7)
        
        self.range_tree.heading("id", text="ROI")
        self.range_tree.heading("type", text="Type")
        self.range_tree.heading("x_range", text="x = x1 to x2")
        self.range_tree.heading("dx", text="dx [min]")
        self.range_tree.heading("y0", text="Baseline y0 [A]")
        self.range_tree.heading("area", text="Area [A·min]")
        self.range_tree.heading("fwhm", text="FWHM [min]")

        self.range_tree.column("id", width=35, anchor=tk.CENTER)
        self.range_tree.column("type", width=80, anchor=tk.CENTER)
        self.range_tree.column("x_range", width=120, anchor=tk.CENTER)
        self.range_tree.column("dx", width=60, anchor=tk.CENTER)
        self.range_tree.column("y0", width=105, anchor=tk.E)
        self.range_tree.column("area", width=135, anchor=tk.E)
        self.range_tree.column("fwhm", width=70, anchor=tk.CENTER)

        self.range_tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.range_tree.yview)
        self.range_tree.configure(yscroll=scrollbar.set)

        self.range_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # D. Statistics & Average Summary Panel (Adsorption vs Desorption)
        stats_frame = ttk.LabelFrame(tab_integ, text=" Adsorption & Desorption Averages ", padding=8)
        stats_frame.pack(fill=tk.X, padx=5, pady=5)

        s_grid = ttk.Frame(stats_frame)
        s_grid.pack(fill=tk.X)

        self.lbl_ads_summary = ttk.Label(s_grid, text="Adsorption Avg: - A·min", font=("Segoe UI", 9, "bold"), foreground="#d4af37")
        self.lbl_ads_summary.grid(row=0, column=0, sticky=tk.W, padx=5)

        self.lbl_des_summary = ttk.Label(s_grid, text="Desorption Avg: - A·min", font=("Segoe UI", 9, "bold"), foreground="#c77dff")
        self.lbl_des_summary.grid(row=0, column=1, sticky=tk.W, padx=5)

        self.lbl_baseline_summary = ttk.Label(s_grid, text="Baseline Avg (Ads y₀): - A", font=("Segoe UI", 9, "bold"), foreground="#0077b6")
        self.lbl_baseline_summary.grid(row=1, column=0, sticky=tk.W, padx=5, pady=(4, 0))

        self.lbl_net_summary = ttk.Label(s_grid, text="Net Cycle Balance: - A·min", font=("Segoe UI", 9, "bold"), foreground="#1d3557")
        self.lbl_net_summary.grid(row=1, column=1, sticky=tk.W, padx=5, pady=(4, 0))

        btn_stats_row = ttk.Frame(tab_integ)
        btn_stats_row.pack(fill=tk.X, padx=5, pady=(2, 5))
        ttk.Button(btn_stats_row, text="Clear All Boxes", command=self.clear_all_ranges).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        ttk.Button(btn_stats_row, text="💾 Save Selection", command=self.save_current_file_selection).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        ttk.Button(btn_stats_row, text="Export CSV...", command=self.export_integration_csv).pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=2)

        # ==================== TAB 3: CO2 CAPACITY (q) ANALYSIS ====================
        self.setup_capacity_tab(tab_capacity)

        # ==================== RIGHT PANEL (MATPLOTLIB CANVAS) ====================
        
        self.fig, self.ax = plt.subplots(figsize=(8, 6), dpi=100)
        self.fig.patch.set_facecolor('#f8f9fa')
        self.ax.set_facecolor('#ffffff')

        self.canvas = FigureCanvasTkAgg(self.fig, master=right_frame)
        self.canvas.draw()
        
        toolbar_frame = ttk.Frame(right_frame)
        toolbar_frame.pack(side=tk.TOP, fill=tk.X)
        self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
        self.toolbar.update()

        ttk.Button(toolbar_frame, text="🔍 Reset Zoom (Fit Data)", command=self.reset_zoom).pack(side=tk.RIGHT, padx=5, pady=2)

        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.canvas.mpl_connect("button_press_event", self.on_mouse_press)
        self.canvas.mpl_connect("motion_notify_event", self.on_mouse_drag)
        self.canvas.mpl_connect("button_release_event", self.on_mouse_release)

    def load_all_saved_configs(self):
        if os.path.exists(self.json_db_path):
            try:
                with open(self.json_db_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def save_current_file_selection(self):
        filename = self.file_combo.get()
        if not filename or self.current_df is None:
            messagebox.showwarning("Warning", "No active file loaded to save.")
            return

        self.saved_file_configs = self.load_all_saved_configs()
        
        target_gas = self.integ_gas_combo.get()
        ranges_data = []
        for r in self.ranges_list:
            ranges_data.append({
                "id": r["id"],
                "type_name": r.get("type_name", "General"),
                "start_min": r["start_min"],
                "end_min": r["end_min"],
                "baseline": r.get("baseline", "straight_line"),
                "color": r.get("color", ROI_PRESETS["general"])
            })

        self.saved_file_configs[filename] = {
            "target_gas": target_gas,
            "ranges": ranges_data,
            "capacity_params": {
                "mass_g": self.cap_mass_var.get(),
                "water_pct": self.cap_water_pct_var.get(),
                "c0": self.cap_c0_var.get(),
                "flow_total": self.cap_flow_total_var.get(),
                "temp_c": self.cap_temp_var.get(),
                "ref_ads": self.cap_ref_ads_var.get(),
                "ref_des": self.cap_ref_des_var.get()
            }
        }

        try:
            with open(self.json_db_path, "w", encoding="utf-8") as f:
                json.dump(self.saved_file_configs, f, indent=2)
            messagebox.showinfo(
                "Selection Saved", 
                f"✅ Saved ROI selection for file:\n'{filename}'\n\n({len(ranges_data)} ROI boxes saved to database)"
            )
        except Exception as e:
            messagebox.showerror("Error Saving", f"Failed to save selection JSON:\n{str(e)}")

    def scan_files(self):
        pattern = os.path.join(self.current_dir, "*.asc")
        filepaths = glob.glob(pattern)
        
        self.files_dict = {os.path.basename(p): p for p in filepaths}
        file_list = list(self.files_dict.keys())
        
        self.file_combo["values"] = file_list
        if file_list:
            self.file_combo.current(0)
            self.on_file_selected()
        else:
            self.file_combo.set("No .asc files found in folder")

    def browse_file(self):
        fpath = filedialog.askopenfilename(
            title="Select .asc Data File",
            filetypes=[("ASC Files", "*.asc"), ("All Files", "*.*")]
        )
        if fpath:
            filename = os.path.basename(fpath)
            self.files_dict[filename] = fpath
            self.file_combo["values"] = list(self.files_dict.keys())
            self.file_combo.set(filename)
            self.on_file_selected()

    def load_asc_file(self, filepath):
        try:
            with open(filepath, "rb") as f:
                content_raw = f.read().decode("utf-8", errors="ignore")
            
            content = content_raw.replace("\r\n", "\n").replace("\r", "\n")
            lines = content.split("\n")

            date_str, time_str, total_cycles = "-", "-", "-"
            for l in lines[:15]:
                if "DATE :" in l:
                    parts = l.split("DATE :")[1].split("TIME :")
                    date_str = parts[0].strip()
                    if len(parts) > 1:
                        time_str = parts[1].strip()
                elif "CONVERTED CYCLES :" in l:
                    total_cycles = l.split("CONVERTED CYCLES :")[1].strip()

            df = pd.read_csv(io.StringIO(content), skiprows=18, sep="\t")
            df = df.loc[:, ~df.contains("^Unnamed") if hasattr(df, "contains") else ~df.columns.str.contains("^Unnamed")]
            
            df["Time_sec"] = pd.to_numeric(df["RelTime[s]"], errors="coerce")
            df["Time_min"] = df["Time_sec"] / 60.0

            total_duration_sec = df["Time_sec"].max() if "Time_sec" in df else 0
            total_duration_min = total_duration_sec / 60.0

            info = {
                "date": date_str,
                "time": time_str,
                "cycles": total_cycles,
                "duration_min": f"{total_duration_min:.2f} min ({total_duration_sec:.1f} s)"
            }

            return df, info
        except Exception as e:
            messagebox.showerror("Error Loading File", f"Failed to parse file:\n{str(e)}")
            return None, {}

    def on_file_selected(self, event=None):
        selected_name = self.file_combo.get()
        if selected_name not in self.files_dict:
            return
        
        filepath = self.files_dict[selected_name]
        df, info = self.load_asc_file(filepath)
        
        if df is not None:
            self.current_df = df
            self.current_file_info = info

            self.lbl_date.config(text=f"Date: {info.get('date', '-')}")
            self.lbl_time.config(text=f"Time: {info.get('time', '-')}")
            self.lbl_cycles.config(text=f"Total Cycles: {info.get('cycles', '-')}")
            self.lbl_duration.config(text=f"Duration: {info.get('duration_min', '-')}")

            if not any(v.get() for v in self.gas_vars.values()):
                self.gas_vars["'0/6'"].set(True)

            # Check if this file has saved ROI selections in JSON DB
            self.saved_file_configs = self.load_all_saved_configs()
            saved = self.saved_file_configs.get(selected_name)

            if saved and "ranges" in saved and len(saved["ranges"]) > 0:
                self.ranges_list.clear()
                self.range_id_counter = 1
                for r in saved["ranges"]:
                    r_copy = r.copy()
                    if "id" in r_copy:
                        self.range_id_counter = max(self.range_id_counter, r_copy["id"] + 1)
                    self.ranges_list.append(r_copy)
                if "target_gas" in saved:
                    self.integ_gas_combo.set(saved["target_gas"])
                if "capacity_params" in saved:
                    cp = saved["capacity_params"]
                    if "mass_g" in cp: self.cap_mass_var.set(cp["mass_g"])
                    if "water_pct" in cp: self.cap_water_pct_var.set(cp["water_pct"])
                    if "c0" in cp: self.cap_c0_var.set(cp["c0"])
                    if "flow_total" in cp: self.cap_flow_total_var.set(cp["flow_total"])
                    if "temp_c" in cp: self.cap_temp_var.set(cp["temp_c"])
                    if "ref_ads" in cp: self.cap_ref_ads_var.set(cp["ref_ads"])
                    if "ref_des" in cp: self.cap_ref_des_var.set(cp["ref_des"])
                self.selected_range_idx = 0 if self.ranges_list else None
                self.recalculate_and_plot()
            else:
                self.ranges_list.clear()
                self.auto_detect_cycle_pairs()

            self.update_plot(preserve_zoom=False)

    def select_all_gases(self):
        for v in self.gas_vars.values():
            v.set(True)
        self.update_plot(preserve_zoom=True)

    def clear_all_gases(self):
        for v in self.gas_vars.values():
            v.set(False)
        self.update_plot(preserve_zoom=True)

    def on_xaxis_change(self):
        x_mode = self.xaxis_var.get()
        if x_mode == "min":
            self.lbl_x1_name.config(text="x1 (min):")
            self.lbl_x2_name.config(text="x2 (min):")
        elif x_mode == "sec":
            self.lbl_x1_name.config(text="x1 (sec):")
            self.lbl_x2_name.config(text="x2 (sec):")
        else:
            self.lbl_x1_name.config(text="x1 (cycle):")
            self.lbl_x2_name.config(text="x2 (cycle):")
            
        self.recalculate_and_plot()

    def on_integ_gas_change(self, event=None):
        self.recalculate_and_plot()

    def get_selected_integ_col(self):
        full_name = self.integ_gas_combo.get()
        for col, meta in GAS_MAPPING.items():
            if meta["full_name"] == full_name:
                return col
        return "'0/6'"

    def reset_zoom(self):
        self.update_plot(preserve_zoom=False)

    # ==================== ORIGIN-STYLE SCIPI INTEGRATION & FWHM ====================

    def calculate_origin_integration(self, col, start_val, end_val, baseline_mode, x_mode):
        if self.current_df is None or col not in self.current_df.columns:
            return 0.0, "A·min", 0.0, "min", 0.0, 0.0

        if x_mode == "min":
            x_series = self.current_df["Time_min"]
            area_unit_str = "A·min"
            fwhm_unit_str = "min"
        elif x_mode == "sec":
            x_series = self.current_df["Time_sec"]
            area_unit_str = "A·s"
            fwhm_unit_str = "s"
        else:
            x_series = self.current_df["Cycle"]
            area_unit_str = "A·cycle"
            fwhm_unit_str = "cycles"

        t_min_series = self.current_df["Time_min"]
        mask = (t_min_series >= start_val) & (t_min_series <= end_val)
        sub_df = self.current_df.loc[mask]

        if len(sub_df) < 3:
            return 0.0, area_unit_str, 0.0, fwhm_unit_str, 0.0, 0.0

        x_val = x_series.loc[mask].values
        y_val = pd.to_numeric(sub_df[col], errors="coerce").values

        x1, x2 = x_val[0], x_val[-1]
        y1, y2 = y_val[0], y_val[-1]

        # Baseline Calculation per ROI Box
        if baseline_mode == "straight_line":
            if x2 > x1:
                baseline = y1 + (y2 - y1) * (x_val - x1) / (x2 - x1)
            else:
                baseline = np.full_like(y_val, y1)
        elif baseline_mode == "horizontal_left":
            baseline = np.full_like(y_val, y1)
        elif baseline_mode == "avg_ads_baseline":
            b_val = getattr(self, "current_avg_ads_baseline", y1)
            baseline = np.full_like(y_val, b_val)
        else: # raw_zero
            baseline = np.zeros_like(y_val)

        # Origin Simpson Rule Integration against current X-axis unit
        net_y = y_val - baseline
        area_val = scipy_integ.simpson(net_y, x=x_val)

        # FWHM Calculation
        fwhm_val = 0.0
        try:
            abs_net = np.abs(net_y)
            peak_idx = np.argmax(abs_net)
            half_max = abs_net[peak_idx] / 2.0
            
            spline = scipy_interp.UnivariateSpline(x_val, abs_net - half_max, s=0)
            roots = spline.roots()
            if len(roots) >= 2:
                fwhm_val = float(roots[-1] - roots[0])
            elif len(roots) == 1:
                fwhm_val = float(abs(roots[0] - x_val[peak_idx]) * 2.0)
        except Exception:
            fwhm_val = 0.0

        duration_val = x2 - x1
        return area_val, area_unit_str, fwhm_val, fwhm_unit_str, duration_val, y1

    # ==================== ROI BOX ADD / DETECT / EDIT CONTROLS ====================

    def _get_next_forward_start(self, default_start=1.0):
        """Find non-overlapping position after the last existing box."""
        if not self.ranges_list:
            return default_start
        max_end = max(r["end_min"] for r in self.ranges_list)
        return round(max_end + 0.5, 2)

    def add_adsorption_box(self, start_min=None, end_min=None, name=None):
        if start_min is None:
            start_min = self._get_next_forward_start(1.0)
            end_min = start_min + 10.0
        elif end_min is None:
            end_min = start_min + 10.0

        color = ROI_PRESETS["adsorption"]
        self._add_box_with_preset(start_min, end_min, color, "straight_line", name or "Adsorption")

    def add_desorption_box(self, start_min=None, end_min=None, name=None):
        if start_min is None:
            start_min = self._get_next_forward_start(1.0)
            end_min = start_min + 5.0
        elif end_min is None:
            end_min = start_min + 5.0

        color = ROI_PRESETS["desorption"]
        self._add_box_with_preset(start_min, end_min, color, "horizontal_left", name or "Desorption")

    def _add_box_with_preset(self, start_min, end_min, color_preset, baseline_mode, type_name):
        if start_min >= end_min:
            end_min = start_min + 2.0

        range_item = {
            "id": self.range_id_counter,
            "type_name": type_name,
            "start_min": round(start_min, 2),
            "end_min": round(end_min, 2),
            "baseline": baseline_mode,
            "color": color_preset
        }
        self.range_id_counter += 1
        self.ranges_list.append(range_item)
        self.selected_range_idx = len(self.ranges_list) - 1

        self.left_notebook.select(1)
        self.recalculate_and_plot()

    def auto_detect_cycle_pairs(self):
        """Automatically scan curve for cyclic adsorption and desorption pairs."""
        if self.current_df is None:
            return

        col = self.get_selected_integ_col()
        t_min = self.current_df["Time_min"].values
        y_val = pd.to_numeric(self.current_df[col], errors="coerce").values

        med_val = np.median(y_val)
        is_low = y_val < (med_val * 0.7)

        transitions_down = np.where((is_low[:-1] == False) & (is_low[1:] == True))[0]
        transitions_up = np.where((is_low[:-1] == True) & (is_low[1:] == False))[0]

        if len(transitions_down) == 0 or len(transitions_up) == 0:
            messagebox.showinfo("Auto-Detect", "Could not automatically isolate cycle transitions.")
            return

        self.ranges_list.clear()

        cycle_num = 1
        for t_down_idx in transitions_down:
            t_down_min = t_min[t_down_idx]
            ups_after = [idx for idx in transitions_up if idx > t_down_idx]
            if not ups_after:
                continue
            t_up_idx = ups_after[0]
            t_up_min = t_min[t_up_idx]

            # 1. Adsorption Box (Yellow, Straight Line)
            self.add_adsorption_box(
                start_min=t_down_min - 0.1, 
                end_min=t_up_min - 0.1, 
                name=f"C{cycle_num}_Ads"
            )

            # 2. Desorption Box (Pink, Horizontal Line Y=Left)
            next_downs = [idx for idx in transitions_down if idx > t_up_idx]
            if next_downs:
                end_des_min = t_min[next_downs[0]] - 0.1
            else:
                end_des_min = min(t_up_min + 10.0, t_min[-1])

            self.add_desorption_box(
                start_min=t_up_min - 0.1, 
                end_min=end_des_min, 
                name=f"C{cycle_num}_Des"
            )

            cycle_num += 1

        self.recalculate_and_plot()
        messagebox.showinfo("Auto-Detect Complete", f"Successfully detected and paired {cycle_num - 1} Adsorption/Desorption cycle pairs!")

    def add_new_range_pair(self, start_min=None, end_min=None):
        if start_min is None or end_min is None:
            start_min = self._get_next_forward_start(10.0)
            end_min = start_min + 10.0
        self.add_adsorption_box(start_min, end_min, "General")

    def remove_selected_range(self):
        if self.selected_range_idx is not None and 0 <= self.selected_range_idx < len(self.ranges_list):
            del self.ranges_list[self.selected_range_idx]
            self.selected_range_idx = len(self.ranges_list) - 1 if self.ranges_list else None
            self.recalculate_and_plot()
        else:
            messagebox.showinfo("Info", "Select an ROI box in the table to remove.")

    def clear_all_ranges(self):
        self.ranges_list.clear()
        self.selected_range_idx = None
        self.recalculate_and_plot()

    def on_tree_select(self, event):
        selected_items = self.range_tree.selection()
        if selected_items:
            item = selected_items[0]
            vals = self.range_tree.item(item, "values")
            r_id = int(vals[0].replace("R", ""))
            
            for idx, r in enumerate(self.ranges_list):
                if r["id"] == r_id:
                    self.selected_range_idx = idx
                    self.spn_start_var.set(r["start_min"])
                    self.spn_end_var.set(r["end_min"])
                    dx = r["end_min"] - r["start_min"]
                    self.spn_dx_var.set(round(dx, 2))

                    b_mode = r.get("baseline", "straight_line")
                    if b_mode == "straight_line":
                        self.combo_baseline.current(0)
                    elif b_mode == "horizontal_left":
                        self.combo_baseline.current(1)
                    elif b_mode == "avg_ads_baseline":
                        self.combo_baseline.current(2)
                    else:
                        self.combo_baseline.current(3)
                    break
            self.update_plot(preserve_zoom=True)

    def on_spinbox_change(self, event=None):
        if self.selected_range_idx is not None and 0 <= self.selected_range_idx < len(self.ranges_list):
            try:
                t1 = float(self.spn_start_var.get())
                t2 = float(self.spn_end_var.get())
                
                if self.lock_dx_var.get():
                    dx = float(self.spn_dx_var.get())
                    t2 = t1 + dx
                    self.spn_end_var.set(round(t2, 2))
                else:
                    dx = t2 - t1
                    self.spn_dx_var.set(round(dx, 2))

                if t1 < t2:
                    self.ranges_list[self.selected_range_idx]["start_min"] = round(t1, 2)
                    self.ranges_list[self.selected_range_idx]["end_min"] = round(t2, 2)
                    self.recalculate_and_plot()
            except ValueError:
                pass

    def on_dx_spinbox_change(self, event=None):
        if self.selected_range_idx is not None and 0 <= self.selected_range_idx < len(self.ranges_list):
            try:
                dx = float(self.spn_dx_var.get())
                t1 = float(self.spn_start_var.get())
                t2 = t1 + dx
                self.spn_end_var.set(round(t2, 2))
                self.ranges_list[self.selected_range_idx]["end_min"] = round(t2, 2)
                self.recalculate_and_plot()
            except ValueError:
                pass

    def on_roi_baseline_change(self, event=None):
        if self.selected_range_idx is not None and 0 <= self.selected_range_idx < len(self.ranges_list):
            b_text = self.combo_baseline.get()
            if "Straight Line" in b_text:
                b_mode = "straight_line"
            elif "Horizontal Line" in b_text:
                b_mode = "horizontal_left"
            elif "Average Baseline" in b_text:
                b_mode = "avg_ads_baseline"
            else:
                b_mode = "raw_zero"

            self.ranges_list[self.selected_range_idx]["baseline"] = b_mode
            self.recalculate_and_plot()

    # ==================== ISOLATED MOUSE DRAG FOR ACTIVE ROI ONLY ====================

    def on_mouse_press(self, event):
        """Allow mouse dragging ONLY on the ACTIVE/SELECTED ROI box to prevent interfering with other ranges."""
        if self.toolbar.mode != "":
            return

        if event.button != 1 or event.inaxes != self.ax or not self.ranges_list:
            return

        if self.xaxis_var.get() != "min":
            return

        x_click = event.xdata
        if x_click is None:
            return

        # First: If user clicks inside ANY box on graph, select that box as active
        clicked_idx = None
        for idx, r in enumerate(self.ranges_list):
            if r["start_min"] <= x_click <= r["end_min"]:
                clicked_idx = idx
                break

        if clicked_idx is not None and clicked_idx != self.selected_range_idx:
            self.selected_range_idx = clicked_idx
            r = self.ranges_list[clicked_idx]
            self.spn_start_var.set(r["start_min"])
            self.spn_end_var.set(r["end_min"])
            self.spn_dx_var.set(round(r["end_min"] - r["start_min"], 2))

            for item in self.range_tree.get_children():
                vals = self.range_tree.item(item, "values")
                if int(vals[0].replace("R", "")) == r["id"]:
                    self.range_tree.selection_set(item)
                    self.range_tree.focus(item)

        # ISOLATION: Only allow dragging the ACTIVE SELECTED range
        if self.selected_range_idx is None or not (0 <= self.selected_range_idx < len(self.ranges_list)):
            return

        idx = self.selected_range_idx
        r = self.ranges_list[idx]

        xlim = self.ax.get_xlim()
        x_range = xlim[1] - xlim[0]
        tolerance = x_range * 0.025

        d_start = abs(x_click - r["start_min"])
        d_end = abs(x_click - r["end_min"])

        if d_start < tolerance:
            self.drag_target = (idx, "start")
        elif d_end < tolerance:
            self.drag_target = (idx, "end")
        elif r["start_min"] <= x_click <= r["end_min"]:
            self.drag_target = (idx, "body")

        if self.drag_target is not None:
            self.drag_initial_x = x_click
            self.drag_initial_range = (r["start_min"], r["end_min"])

    def on_mouse_drag(self, event):
        """Update ONLY the active range boundaries live as mouse moves."""
        if self.drag_target is None or event.inaxes != self.ax or event.xdata is None:
            return

        idx, part = self.drag_target
        current_x = max(0.0, event.xdata)
        r = self.ranges_list[idx]
        is_locked_dx = self.lock_dx_var.get()
        dx_fixed = round(r["end_min"] - r["start_min"], 2)

        if part == "start":
            if is_locked_dx:
                r["start_min"] = round(current_x, 2)
                r["end_min"] = round(current_x + dx_fixed, 2)
            elif current_x < r["end_min"] - 0.2:
                r["start_min"] = round(current_x, 2)
            self.spn_start_var.set(r["start_min"])
            self.spn_end_var.set(r["end_min"])
            self.spn_dx_var.set(round(r["end_min"] - r["start_min"], 2))
        elif part == "end":
            if is_locked_dx:
                r["end_min"] = round(current_x, 2)
                r["start_min"] = round(max(0.0, current_x - dx_fixed), 2)
            elif current_x > r["start_min"] + 0.2:
                r["end_min"] = round(current_x, 2)
            self.spn_start_var.set(r["start_min"])
            self.spn_end_var.set(r["end_min"])
            self.spn_dx_var.set(round(r["end_min"] - r["start_min"], 2))
        elif part == "body":
            dx_mouse = current_x - self.drag_initial_x
            orig_start, orig_end = self.drag_initial_range
            dx_fixed = round(orig_end - orig_start, 2)
            new_start = round(max(0.0, orig_start + dx_mouse), 2)
            new_end = round(new_start + dx_fixed, 2)
            r["start_min"] = new_start
            r["end_min"] = new_end
            self.spn_start_var.set(new_start)
            self.spn_end_var.set(new_end)
            self.spn_dx_var.set(dx_fixed)

        self.recalculate_and_plot()

    def on_mouse_release(self, event):
        if self.drag_target is not None:
            self.drag_target = None
            self.drag_initial_x = None
            self.drag_initial_range = None
            self.recalculate_and_plot()

    def recalculate_and_plot(self):
        for item in self.range_tree.get_children():
            self.range_tree.delete(item)

        col = self.get_selected_integ_col()
        x_mode = self.xaxis_var.get()

        # Pre-compute initial y0 for all Adsorption ranges to determine the Average Baseline
        ads_y0_list = []
        if self.current_df is not None and col in self.current_df.columns:
            t_min_all = self.current_df["Time_min"].values
            y_all = pd.to_numeric(self.current_df[col], errors="coerce").values
            for r in self.ranges_list:
                t_name = r.get("type_name", "General")
                if "Ads" in t_name or "Adsorption" in t_name:
                    mask_r = (t_min_all >= r["start_min"]) & (t_min_all <= r["end_min"])
                    if np.any(mask_r):
                        y0_val = y_all[mask_r][0]
                        r["y_start"] = y0_val
                        ads_y0_list.append(y0_val)

        self.current_avg_ads_baseline = np.mean(ads_y0_list) if ads_y0_list else 0.0

        areas_ads = []
        areas_des = []
        last_unit_str = "A·min"

        for idx, r in enumerate(self.ranges_list):
            b_mode = r.get("baseline", "straight_line")
            area_val, area_unit_str, fwhm_val, fwhm_unit_str, dur_val, y_start = self.calculate_origin_integration(
                col, r["start_min"], r["end_min"], b_mode, x_mode
            )
            r["calculated_area"] = area_val
            r["area_unit"] = area_unit_str
            r["fwhm_val"] = fwhm_val
            r["fwhm_unit"] = fwhm_unit_str
            r["duration_val"] = dur_val
            r["y_start"] = y_start
            last_unit_str = area_unit_str

            t_name = r.get("type_name", "General")
            if "Ads" in t_name or "Adsorption" in t_name:
                areas_ads.append(area_val)
            elif "Des" in t_name or "Desorption" in t_name:
                areas_des.append(area_val)

            x_str = f"{r['start_min']:.2f} to {r['end_min']:.2f}"
            item = self.range_tree.insert(
                "", 
                tk.END, 
                values=(
                    f"R{r['id']}", 
                    t_name,
                    x_str, 
                    f"{dur_val:.2f}", 
                    f"{y_start:.5e}",
                    f"{area_val:.5e}", 
                    f"{fwhm_val:.3f}" if fwhm_val > 0 else "-"
                )
            )

            if idx == self.selected_range_idx:
                self.range_tree.selection_set(item)

        avg_ads = np.mean(areas_ads) if areas_ads else 0.0
        avg_des = np.mean(areas_des) if areas_des else 0.0
        net_balance = avg_des + avg_ads
        avg_baseline = self.current_avg_ads_baseline

        self.lbl_ads_summary.config(text=f"Adsorption Avg ({len(areas_ads)}): {avg_ads:.5e} {last_unit_str}" if areas_ads else "Adsorption Avg: -")
        self.lbl_des_summary.config(text=f"Desorption Avg ({len(areas_des)}): {avg_des:.5e} {last_unit_str}" if areas_des else "Desorption Avg: -")
        self.lbl_baseline_summary.config(text=f"Baseline Avg (Ads y₀): {avg_baseline:.5e} A" if ads_y0_list else "Baseline Avg (Ads): -")
        self.lbl_net_summary.config(text=f"Net Cycle Balance: {net_balance:.5e} {last_unit_str}" if (areas_ads or areas_des) else "Net Cycle Balance: -")

        self.update_plot(preserve_zoom=True)

        if hasattr(self, "cap_auto_sync_var") and self.cap_auto_sync_var.get():
            self.sync_capacity_from_plot()

    def export_integration_csv(self):
        if not self.ranges_list:
            messagebox.showinfo("Info", "No ROI box integration results to export.")
            return

        fpath = filedialog.asksaveasfilename(
            title="Export Origin Integration Results (CSV)",
            defaultextension=".csv",
            filetypes=[("CSV File", "*.csv"), ("Text File", "*.txt")]
        )
        if fpath:
            col = self.get_selected_integ_col()
            x_mode = self.xaxis_var.get()
            
            rows = []
            for r in self.ranges_list:
                rows.append({
                    "ROI_ID": f"R{r['id']}",
                    "Type": r.get("type_name", "General"),
                    "Gas_Channel": col,
                    "Baseline_Mode": r.get("baseline", "straight_line"),
                    "x1_Start": r["start_min"],
                    "x2_End": r["end_min"],
                    "dx_Duration": r.get("duration_val", 0.0),
                    "Baseline_y0_Start_A": r.get("y_start", 0.0),
                    "Area_Simpson": r.get("calculated_area", 0.0),
                    "Area_Unit": r.get("area_unit", "A·min"),
                    "FWHM": r.get("fwhm_val", 0.0),
                    "FWHM_Unit": r.get("fwhm_unit", "min")
                })
            
            df_exp = pd.DataFrame(rows)
            df_exp.to_csv(fpath, index=False)
            messagebox.showinfo("Export Successful", f"Origin Integration results saved to:\n{fpath}")

    # ==================== TAB 3: CO2 ADSORPTION & DESORPTION CAPACITY (q) ====================

    def setup_capacity_tab(self, parent):
        """Construct the CO2 Adsorption & Desorption Capacity (q in mmol/g) Analysis Tab."""
        cap_canvas = tk.Canvas(parent, borderwidth=0, highlightthickness=0)
        cap_scrollbar = ttk.Scrollbar(parent, orient="vertical", command=cap_canvas.yview)
        scroll_frame = ttk.Frame(cap_canvas, padding=6)

        scroll_frame.bind(
            "<Configure>",
            lambda e: cap_canvas.configure(scrollregion=cap_canvas.bbox("all"))
        )

        win_id = cap_canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        cap_canvas.bind("<Configure>", lambda e: cap_canvas.itemconfig(win_id, width=e.width))
        cap_canvas.configure(yscrollcommand=cap_scrollbar.set)

        cap_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        cap_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        def _on_mw(ev):
            cap_canvas.yview_scroll(int(-1 * (ev.delta / 120)), "units")
        cap_canvas.bind("<MouseWheel>", _on_mw)
        scroll_frame.bind("<MouseWheel>", _on_mw)

        # 1. INTEGRATED VALUES FRAME
        f_integ = ttk.LabelFrame(scroll_frame, text=" 1. Integration Inputs (Live Synced) ", padding=6)
        f_integ.pack(fill=tk.X, padx=3, pady=4)

        sync_row = ttk.Frame(f_integ)
        sync_row.pack(fill=tk.X, pady=(0, 4))
        ttk.Checkbutton(sync_row, text="🔄 Auto-sync with Plot", variable=self.cap_auto_sync_var).pack(side=tk.LEFT)
        ttk.Button(sync_row, text="Sync Now", command=self.sync_capacity_from_plot).pack(side=tk.RIGHT)

        g_integ = ttk.Frame(f_integ)
        g_integ.pack(fill=tk.X, pady=2)

        ttk.Label(g_integ, text="S_baseline (A):", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky=tk.W, padx=2, pady=2)
        sp_sbase = ttk.Entry(g_integ, textvariable=self.cap_s_baseline_var, width=13)
        sp_sbase.grid(row=0, column=1, sticky=tk.W, padx=2, pady=2)
        sp_sbase.bind("<KeyRelease>", self.calculate_co2_capacity)

        self.lbl_cap_k = ttk.Label(g_integ, text="k = - A⁻¹", font=("Segoe UI", 9, "bold"), foreground="#0077b6")
        self.lbl_cap_k.grid(row=0, column=2, sticky=tk.W, padx=6, pady=2)

        ttk.Label(g_integ, text="Area Ads (A·min):", font=("Segoe UI", 9, "bold")).grid(row=1, column=0, sticky=tk.W, padx=2, pady=2)
        sp_a_ads = ttk.Entry(g_integ, textvariable=self.cap_area_ads_var, width=13)
        sp_a_ads.grid(row=1, column=1, sticky=tk.W, padx=2, pady=2)
        sp_a_ads.bind("<KeyRelease>", self.calculate_co2_capacity)

        ttk.Label(g_integ, text="Area Des (A·min):", font=("Segoe UI", 9, "bold")).grid(row=2, column=0, sticky=tk.W, padx=2, pady=2)
        sp_a_des = ttk.Entry(g_integ, textvariable=self.cap_area_des_var, width=13)
        sp_a_des.grid(row=2, column=1, sticky=tk.W, padx=2, pady=2)
        sp_a_des.bind("<KeyRelease>", self.calculate_co2_capacity)

        # 2. EXPERIMENTAL CONDITIONS & SAMPLE PARAMETERS
        f_params = ttk.LabelFrame(scroll_frame, text=" 2. Experimental & Sample Parameters ", padding=6)
        f_params.pack(fill=tk.X, padx=3, pady=4)

        g_params = ttk.Frame(f_params)
        g_params.pack(fill=tk.X, pady=2)

        # Sample Mass
        ttk.Label(g_params, text="Sample Mass (g):", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky=tk.W, padx=2, pady=2)
        sp_mass = ttk.Spinbox(g_params, from_=0.001, to=100.0, increment=0.01, textvariable=self.cap_mass_var, width=9, command=self.calculate_co2_capacity)
        sp_mass.grid(row=0, column=1, sticky=tk.W, padx=2, pady=2)
        sp_mass.bind("<KeyRelease>", self.calculate_co2_capacity)

        # Water Content %
        ttk.Label(g_params, text="Water/Loss (%):", font=("Segoe UI", 9, "bold")).grid(row=0, column=2, sticky=tk.W, padx=(8, 2), pady=2)
        sp_water = ttk.Spinbox(g_params, from_=0.0, to=100.0, increment=0.5, textvariable=self.cap_water_pct_var, width=8, command=self.calculate_co2_capacity)
        sp_water.grid(row=0, column=3, sticky=tk.W, padx=2, pady=2)
        sp_water.bind("<KeyRelease>", self.calculate_co2_capacity)

        # Active Mass label
        self.lbl_cap_m_act = ttk.Label(g_params, text="Active Mass = - g", font=("Segoe UI", 8, "italic"), foreground="#495057")
        self.lbl_cap_m_act.grid(row=1, column=0, columnspan=4, sticky=tk.W, padx=2, pady=(0, 4))

        # CO2 Concentration & Total Flow
        ttk.Label(g_params, text="CO₂ Fraction C₀:", font=("Segoe UI", 9, "bold")).grid(row=2, column=0, sticky=tk.W, padx=2, pady=2)
        sp_c0 = ttk.Spinbox(g_params, from_=0.001, to=1.0, increment=0.01, textvariable=self.cap_c0_var, width=9, command=self.calculate_co2_capacity)
        sp_c0.grid(row=2, column=1, sticky=tk.W, padx=2, pady=2)
        sp_c0.bind("<KeyRelease>", self.calculate_co2_capacity)

        ttk.Label(g_params, text="Flow (mL/min):", font=("Segoe UI", 9, "bold")).grid(row=2, column=2, sticky=tk.W, padx=(8, 2), pady=2)
        sp_flow = ttk.Spinbox(g_params, from_=1.0, to=5000.0, increment=5.0, textvariable=self.cap_flow_total_var, width=8, command=self.calculate_co2_capacity)
        sp_flow.grid(row=2, column=3, sticky=tk.W, padx=2, pady=2)
        sp_flow.bind("<KeyRelease>", self.calculate_co2_capacity)

        # Temperature
        ttk.Label(g_params, text="Lab Temp (°C):", font=("Segoe UI", 9, "bold")).grid(row=3, column=0, sticky=tk.W, padx=2, pady=2)
        sp_temp = ttk.Spinbox(g_params, from_=-10.0, to=100.0, increment=1.0, textvariable=self.cap_temp_var, width=9, command=self.calculate_co2_capacity)
        sp_temp.grid(row=3, column=1, sticky=tk.W, padx=2, pady=2)
        sp_temp.bind("<KeyRelease>", self.calculate_co2_capacity)

        self.lbl_cap_vm = ttk.Label(g_params, text="Vₘ,24°C = - mL/mol", font=("Segoe UI", 8, "italic"), foreground="#495057")
        self.lbl_cap_vm.grid(row=3, column=2, columnspan=2, sticky=tk.W, padx=(8, 2), pady=2)

        self.lbl_cap_ntot = ttk.Label(g_params, text="n_total = - mol/min", font=("Segoe UI", 8, "italic"), foreground="#495057")
        self.lbl_cap_ntot.grid(row=4, column=0, columnspan=4, sticky=tk.W, padx=2, pady=(0, 4))

        # Blank Monolith Deductions
        ttk.Label(g_params, text="Ref Blank Ads (q):", font=("Segoe UI", 9, "bold")).grid(row=5, column=0, sticky=tk.W, padx=2, pady=2)
        sp_ref_ads = ttk.Spinbox(g_params, from_=0.0, to=5.0, increment=0.01, textvariable=self.cap_ref_ads_var, width=9, command=self.calculate_co2_capacity)
        sp_ref_ads.grid(row=5, column=1, sticky=tk.W, padx=2, pady=2)
        sp_ref_ads.bind("<KeyRelease>", self.calculate_co2_capacity)

        ttk.Label(g_params, text="Ref Blank Des (q):", font=("Segoe UI", 9, "bold")).grid(row=5, column=2, sticky=tk.W, padx=(8, 2), pady=2)
        sp_ref_des = ttk.Spinbox(g_params, from_=0.0, to=5.0, increment=0.01, textvariable=self.cap_ref_des_var, width=8, command=self.calculate_co2_capacity)
        sp_ref_des.grid(row=5, column=3, sticky=tk.W, padx=2, pady=2)
        sp_ref_des.bind("<KeyRelease>", self.calculate_co2_capacity)

        # 3. RESULTS: CO2 ADSORPTION & DESORPTION CAPACITY (q)
        f_res = ttk.LabelFrame(scroll_frame, text=" 3. CO₂ Adsorption & Desorption Capacity (q) ", padding=8)
        f_res.pack(fill=tk.X, padx=3, pady=4)

        # --- Adsorption Card ---
        card_ads = tk.LabelFrame(f_res, text=" 🟡 ADSORPTION CAPACITY ", font=("Segoe UI", 9, "bold"), fg="#b58300", bg="#fffdf0", padx=6, pady=4)
        card_ads.pack(fill=tk.X, pady=(0, 4))

        self.lbl_res_ads_mmol = tk.Label(card_ads, text="n(CO₂) = - mmol", font=("Segoe UI", 9), bg="#fffdf0", anchor="w")
        self.lbl_res_ads_mmol.pack(fill=tk.X)
        self.lbl_res_ads_raw = tk.Label(card_ads, text="q (raw, total mass) = - mmol/g", font=("Segoe UI", 9), bg="#fffdf0", anchor="w")
        self.lbl_res_ads_raw.pack(fill=tk.X)
        self.lbl_res_ads_act = tk.Label(card_ads, text="q (active mass, -21.4%) = - mmol/g", font=("Segoe UI", 9), bg="#fffdf0", anchor="w")
        self.lbl_res_ads_act.pack(fill=tk.X)
        self.lbl_res_ads_net = tk.Label(card_ads, text="q_net (minus 0.23 Ref) = - mmol/g", font=("Segoe UI", 11, "bold"), fg="#2b9348", bg="#fffdf0", anchor="w")
        self.lbl_res_ads_net.pack(fill=tk.X, pady=(2, 0))

        # --- Desorption Card ---
        card_des = tk.LabelFrame(f_res, text=" 🟣 DESORPTION CAPACITY ", font=("Segoe UI", 9, "bold"), fg="#7209b7", bg="#fbf5ff", padx=6, pady=4)
        card_des.pack(fill=tk.X, pady=(4, 4))

        self.lbl_res_des_mmol = tk.Label(card_des, text="n(CO₂) = - mmol", font=("Segoe UI", 9), bg="#fbf5ff", anchor="w")
        self.lbl_res_des_mmol.pack(fill=tk.X)
        self.lbl_res_des_raw = tk.Label(card_des, text="q (raw, total mass) = - mmol/g", font=("Segoe UI", 9), bg="#fbf5ff", anchor="w")
        self.lbl_res_des_raw.pack(fill=tk.X)
        self.lbl_res_des_act = tk.Label(card_des, text="q (active mass, -21.4%) = - mmol/g", font=("Segoe UI", 9), bg="#fbf5ff", anchor="w")
        self.lbl_res_des_act.pack(fill=tk.X)
        self.lbl_res_des_net = tk.Label(card_des, text="q_net (Desorption) = - mmol/g", font=("Segoe UI", 11, "bold"), fg="#7209b7", bg="#fbf5ff", anchor="w")
        self.lbl_res_des_net.pack(fill=tk.X, pady=(2, 0))

        # --- Cycle Efficiency ---
        self.lbl_res_recovery = ttk.Label(f_res, text="Desorption Recovery: - %", font=("Segoe UI", 9, "bold"), foreground="#1d3557")
        self.lbl_res_recovery.pack(anchor=tk.W, pady=(2, 4))

        # 4. ACTION BUTTONS (Save, Copy, Export)
        f_act = ttk.Frame(scroll_frame)
        f_act.pack(fill=tk.X, padx=3, pady=4)

        ttk.Button(f_act, text="💾 Save Parameters with File", command=self.save_current_file_selection).pack(fill=tk.X, pady=2)
        
        btn_sub_row = ttk.Frame(f_act)
        btn_sub_row.pack(fill=tk.X, pady=2)
        ttk.Button(btn_sub_row, text="📋 Copy Report", command=self.copy_capacity_summary).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 2))
        ttk.Button(btn_sub_row, text="Export CSV...", command=self.export_capacity_csv).pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=(2, 0))

        self.calculate_co2_capacity()

    def sync_capacity_from_plot(self):
        """Pull current average baseline and integration areas into capacity inputs."""
        if hasattr(self, "current_avg_ads_baseline") and self.current_avg_ads_baseline > 0:
            self.cap_s_baseline_var.set(self.current_avg_ads_baseline)

        areas_ads = [abs(r.get("calculated_area", 0.0)) for r in self.ranges_list if "Ads" in r.get("type_name", "") or "Adsorption" in r.get("type_name", "")]
        areas_des = [abs(r.get("calculated_area", 0.0)) for r in self.ranges_list if "Des" in r.get("type_name", "") or "Desorption" in r.get("type_name", "")]

        if areas_ads:
            self.cap_area_ads_var.set(np.mean(areas_ads))
        if areas_des:
            self.cap_area_des_var.set(np.mean(areas_des))

        self.calculate_co2_capacity()

    def calculate_co2_capacity(self, event=None):
        """Execute exact CO2 capacity math workflow matching ZZ 30 Ads des final.xlsx."""
        try:
            c0 = float(self.cap_c0_var.get())
            flow_total = float(self.cap_flow_total_var.get())
            temp_c = float(self.cap_temp_var.get())
            mass_tot = float(self.cap_mass_var.get())
            water_pct = float(self.cap_water_pct_var.get())
            ref_ads = float(self.cap_ref_ads_var.get())
            ref_des = float(self.cap_ref_des_var.get())
            s_base = float(self.cap_s_baseline_var.get())
            area_ads = float(self.cap_area_ads_var.get())
            area_des = float(self.cap_area_des_var.get())

            # 1. Temperature & Molar Volume correction
            T1_K = 25.0 + 273.15
            T2_K = temp_c + 273.15
            Vm_25 = 24465.0
            Vm_exp = Vm_25 * (T2_K / T1_K)
            n_total = flow_total / Vm_exp

            # 2. Calibration factor k
            k_factor = (c0 / s_base) if s_base > 0 else 0.0

            # 3. Active mass (water/binder loss deduction)
            mass_act = mass_tot * (1.0 - (water_pct / 100.0))

            # 4. Adsorption calculations
            n_mol_ads = n_total * k_factor * area_ads
            n_mmol_ads = n_mol_ads * 1000.0
            q_raw_ads = (n_mmol_ads / mass_tot) if mass_tot > 0 else 0.0
            q_act_ads = (n_mmol_ads / mass_act) if mass_act > 0 else 0.0
            q_net_ads = q_act_ads - ref_ads

            # 5. Desorption calculations
            n_mol_des = n_total * k_factor * area_des
            n_mmol_des = n_mol_des * 1000.0
            q_raw_des = (n_mmol_des / mass_tot) if mass_tot > 0 else 0.0
            q_act_des = (n_mmol_des / mass_act) if mass_act > 0 else 0.0
            q_net_des = q_act_des - ref_des

            # 6. Recovery Ratio
            recovery_pct = (q_net_des / q_net_ads * 100.0) if q_net_ads > 0 else 0.0

            # Update Labels
            self.lbl_cap_vm.config(text=f"Vₘ,{temp_c:.0f}°C = {Vm_exp:.1f} mL/mol")
            self.lbl_cap_ntot.config(text=f"n_total = {n_total:.6f} mol/min")
            self.lbl_cap_k.config(text=f"k = {k_factor:.4e} A⁻¹")
            self.lbl_cap_m_act.config(text=f"Active Mass = {mass_act:.4f} g  (-{water_pct:.1f}%)")

            self.lbl_res_ads_mmol.config(text=f"n(CO₂) = {n_mmol_ads:.4f} mmol")
            self.lbl_res_ads_raw.config(text=f"q (raw, total mass) = {q_raw_ads:.4f} mmol/g")
            self.lbl_res_ads_act.config(text=f"q (active mass, -{water_pct:.1f}%) = {q_act_ads:.4f} mmol/g")
            self.lbl_res_ads_net.config(text=f"q_net (minus {ref_ads:.2f} Ref) = {q_net_ads:.4f} mmol/g")

            self.lbl_res_des_mmol.config(text=f"n(CO₂) = {n_mmol_des:.4f} mmol")
            self.lbl_res_des_raw.config(text=f"q (raw, total mass) = {q_raw_des:.4f} mmol/g")
            self.lbl_res_des_act.config(text=f"q (active mass, -{water_pct:.1f}%) = {q_act_des:.4f} mmol/g")
            self.lbl_res_des_net.config(text=f"q_net (Desorption) = {q_net_des:.4f} mmol/g")

            self.lbl_res_recovery.config(text=f"Desorption Recovery = {recovery_pct:.1f}%")

            self.last_capacity_results = {
                "c0": c0,
                "flow_total": flow_total,
                "temp_c": temp_c,
                "Vm_exp": Vm_exp,
                "n_total": n_total,
                "s_base": s_base,
                "k_factor": k_factor,
                "mass_tot": mass_tot,
                "water_pct": water_pct,
                "mass_act": mass_act,
                "ref_ads": ref_ads,
                "ref_des": ref_des,
                "area_ads": area_ads,
                "n_mmol_ads": n_mmol_ads,
                "q_raw_ads": q_raw_ads,
                "q_act_ads": q_act_ads,
                "q_net_ads": q_net_ads,
                "area_des": area_des,
                "n_mmol_des": n_mmol_des,
                "q_raw_des": q_raw_des,
                "q_act_des": q_act_des,
                "q_net_des": q_net_des,
                "recovery_pct": recovery_pct
            }
        except Exception:
            pass

    def copy_capacity_summary(self):
        """Copy formatted report to system clipboard."""
        if not hasattr(self, "last_capacity_results") or not self.last_capacity_results:
            return
        res = self.last_capacity_results
        filename = self.file_combo.get()
        txt = (
            f"=== CO2 ADSORPTION & DESORPTION CAPACITY REPORT ===\n"
            f"Measurement File: {filename}\n"
            f"Sample Mass: {res['mass_tot']:.4f} g (Active Mass: {res['mass_act']:.4f} g with -{res['water_pct']:.1f}% water/binder)\n"
            f"Gas Flow: {res['flow_total']:.1f} mL/min | CO2 Conc (C0): {res['c0']*100:.1f}%\n"
            f"Temperature: {res['temp_c']:.1f} °C | Molar Flow n_total: {res['n_total']:.6f} mol/min\n"
            f"Baseline Signal S_baseline: {res['s_base']:.5e} A | k factor: {res['k_factor']:.4e} A⁻¹\n"
            f"---------------------------------------------------\n"
            f"[ADSORPTION]\n"
            f"Integrated Area: {res['area_ads']:.5e} A·min\n"
            f"Moles Adsorbed n(CO2): {res['n_mmol_ads']:.4f} mmol\n"
            f"Raw Capacity: {res['q_raw_ads']:.4f} mmol/g\n"
            f"Corrected Capacity (-{res['water_pct']:.1f}%): {res['q_act_ads']:.4f} mmol/g\n"
            f"NET CAPACITY (minus {res['ref_ads']:.2f} mmol/g Ref): {res['q_net_ads']:.4f} mmol/g\n"
            f"---------------------------------------------------\n"
            f"[DESORPTION]\n"
            f"Integrated Area: {res['area_des']:.5e} A·min\n"
            f"Moles Desorbed n(CO2): {res['n_mmol_des']:.4f} mmol\n"
            f"Raw Desorption: {res['q_raw_des']:.4f} mmol/g\n"
            f"Corrected Desorption: {res['q_act_des']:.4f} mmol/g\n"
            f"NET DESORPTION: {res['q_net_des']:.4f} mmol/g\n"
            f"Cycle Recovery: {res['recovery_pct']:.1f}%\n"
            f"==================================================="
        )
        self.root.clipboard_clear()
        self.root.clipboard_append(txt)
        messagebox.showinfo("Copied", "✅ Summary copied to clipboard!")

    def export_capacity_csv(self):
        """Export full calculation parameters and capacities to CSV."""
        if not hasattr(self, "last_capacity_results") or not self.last_capacity_results:
            messagebox.showinfo("Info", "No capacity calculation results to export.")
            return

        fpath = filedialog.asksaveasfilename(
            title="Export CO2 Capacity Calculation (CSV)",
            defaultextension=".csv",
            filetypes=[("CSV File", "*.csv"), ("Text File", "*.txt")]
        )
        if fpath:
            res = self.last_capacity_results
            filename = self.file_combo.get()
            rows = [
                {"Parameter": "Measurement_File", "Value": filename, "Unit": ""},
                {"Parameter": "CO2_Feed_Fraction_C0", "Value": res['c0'], "Unit": "mole fraction"},
                {"Parameter": "Total_Gas_Flow_F_total", "Value": res['flow_total'], "Unit": "mL/min"},
                {"Parameter": "Temperature_T", "Value": res['temp_c'], "Unit": "deg C"},
                {"Parameter": "Molar_Volume_Vm", "Value": res['Vm_exp'], "Unit": "mL/mol"},
                {"Parameter": "Total_Molar_Flow_n_total", "Value": res['n_total'], "Unit": "mol/min"},
                {"Parameter": "Baseline_Signal_S_base", "Value": res['s_base'], "Unit": "A"},
                {"Parameter": "Calibration_Factor_k", "Value": res['k_factor'], "Unit": "A^-1"},
                {"Parameter": "Sample_Mass_Total", "Value": res['mass_tot'], "Unit": "g"},
                {"Parameter": "Water_Binder_Loss_Percent", "Value": res['water_pct'], "Unit": "%"},
                {"Parameter": "Active_Adsorbent_Mass", "Value": res['mass_act'], "Unit": "g"},
                {"Parameter": "Ref_Monolith_Blank_Ads", "Value": res['ref_ads'], "Unit": "mmol/g"},
                {"Parameter": "Ref_Monolith_Blank_Des", "Value": res['ref_des'], "Unit": "mmol/g"},
                {"Parameter": "Area_Adsorption", "Value": res['area_ads'], "Unit": "A*min"},
                {"Parameter": "n_CO2_Adsorbed", "Value": res['n_mmol_ads'], "Unit": "mmol"},
                {"Parameter": "q_Raw_Adsorption", "Value": res['q_raw_ads'], "Unit": "mmol/g"},
                {"Parameter": "q_Active_Mass_Adsorption", "Value": res['q_act_ads'], "Unit": "mmol/g"},
                {"Parameter": "q_NET_Adsorption", "Value": res['q_net_ads'], "Unit": "mmol/g"},
                {"Parameter": "Area_Desorption", "Value": res['area_des'], "Unit": "A*min"},
                {"Parameter": "n_CO2_Desorbed", "Value": res['n_mmol_des'], "Unit": "mmol"},
                {"Parameter": "q_Raw_Desorption", "Value": res['q_raw_des'], "Unit": "mmol/g"},
                {"Parameter": "q_Active_Mass_Desorption", "Value": res['q_act_des'], "Unit": "mmol/g"},
                {"Parameter": "q_NET_Desorption", "Value": res['q_net_des'], "Unit": "mmol/g"},
                {"Parameter": "Cycle_Recovery_Percent", "Value": res['recovery_pct'], "Unit": "%"}
            ]
            df_exp = pd.DataFrame(rows)
            df_exp.to_csv(fpath, index=False)
            messagebox.showinfo("Export Successful", f"CO2 Capacity calculation saved to:\n{fpath}")

    def show_placeholder_plot(self):
        self.ax.clear()
        self.ax.set_title("Select a File and Gas Channels to Display Plot", fontsize=12, pad=15)
        self.ax.set_xlabel("Time (min)", fontsize=10)
        self.ax.set_ylabel("Ion Current [A]", fontsize=10)
        self.ax.grid(True, linestyle="--", alpha=0.5)
        self.canvas.draw()

    def update_plot(self, preserve_zoom=True):
        """Re-draw plot rendering OriginPro-style ROI shaded boxes, individual baselines, and FWHM."""
        if self.current_df is None:
            self.show_placeholder_plot()
            return

        prev_xlim = None
        prev_ylim = None
        if preserve_zoom and self.has_plotted_once:
            prev_xlim = self.ax.get_xlim()
            prev_ylim = self.ax.get_ylim()

        selected_channels = [c for c, var in self.gas_vars.items() if var.get()]
        integ_col = self.get_selected_integ_col()

        if self.ranges_list and integ_col not in selected_channels:
            selected_channels.append(integ_col)

        self.ax.clear()
        self.ax.grid(True, linestyle="--", alpha=0.5)

        if not selected_channels:
            self.ax.set_title("No gases selected. Please check at least one gas above.", fontsize=11, color="red")
            self.ax.set_xlabel("Time (min)", fontsize=10)
            self.ax.set_ylabel("Ion Current [A]", fontsize=10)
            self.canvas.draw()
            return

        x_mode = self.xaxis_var.get()
        if x_mode == "min":
            x_data = self.current_df["Time_min"]
            x_label = "Time (min)"
        elif x_mode == "sec":
            x_data = self.current_df["Time_sec"]
            x_label = "Time (s)"
        else:
            x_data = self.current_df["Cycle"]
            x_label = "Cycle Count"

        file_title = self.file_combo.get()
        is_log = self.scale_var.get() == "log"

        for col in selected_channels:
            if col in self.current_df.columns:
                meta = GAS_MAPPING[col]
                y_data = pd.to_numeric(self.current_df[col], errors="coerce")
                
                if is_log:
                    y_data = y_data.apply(lambda v: v if v > 0 else np.nan)

                self.ax.plot(
                    x_data, 
                    y_data, 
                    label=meta["label"], 
                    color=meta["color"], 
                    linewidth=1.2,
                    alpha=0.9
                )

        # RENDER ORIGINPRO-STYLE ROI BOXES, BASELINES & TOP CONTROL TAGS WITH INDIVIDUAL BASELINE MODES
        if integ_col in self.current_df.columns and self.ranges_list:
            y_integ_raw = pd.to_numeric(self.current_df[integ_col], errors="coerce").values
            t_min_arr = self.current_df["Time_min"].values
            t_sec_arr = self.current_df["Time_sec"].values

            y_min_plot, y_max_plot = self.ax.get_ylim()

            for idx, r in enumerate(self.ranges_list):
                mask = (t_min_arr >= r["start_min"]) & (t_min_arr <= r["end_min"])
                if not np.any(mask):
                    continue

                sub_t_min = t_min_arr[mask]
                sub_t_sec = t_sec_arr[mask]
                sub_y = y_integ_raw[mask]

                t1_sec, t2_sec = sub_t_sec[0], sub_t_sec[-1]
                y1, y2 = sub_y[0], sub_y[-1]
                
                b_mode = r.get("baseline", "straight_line")
                if b_mode == "straight_line":
                    if t2_sec > t1_sec:
                        baseline = y1 + (y2 - y1) * (sub_t_sec - t1_sec) / (t2_sec - t1_sec)
                    else:
                        baseline = np.full_like(sub_y, y1)
                elif b_mode == "horizontal_left":
                    baseline = np.full_like(sub_y, y1)
                elif b_mode == "avg_ads_baseline":
                    b_val = getattr(self, "current_avg_ads_baseline", y1)
                    baseline = np.full_like(sub_y, b_val)
                else: # raw_zero
                    baseline = np.zeros_like(sub_y)

                is_selected = (idx == self.selected_range_idx)
                roi_color = r.get("color", ROI_PRESETS["general"])
                fill_color = roi_color["fill"]
                border_color = roi_color["border"] if not is_selected else "#000000"
                fill_alpha = 0.60 if is_selected else 0.30

                if x_mode == "min":
                    sub_x = sub_t_min
                elif x_mode == "sec":
                    sub_x = sub_t_sec
                else:
                    sub_x = self.current_df["Cycle"].values[mask]

                x_start_plot = r["start_min"] if x_mode == "min" else sub_x[0]
                x_end_plot = r["end_min"] if x_mode == "min" else sub_x[-1]

                # 1. Origin Shaded Vertical ROI Box
                self.ax.axvspan(x_start_plot, x_end_plot, color=fill_color, alpha=fill_alpha, zorder=1)

                # 2. Origin Shaded Net Integration Region under/above baseline
                self.ax.fill_between(sub_x, baseline, sub_y, color="#6c757d", alpha=0.4, zorder=2)
                self.ax.plot(sub_x, baseline, color="#d90429" if is_selected else "#e63946", linestyle="-", linewidth=1.5, zorder=3)

                # 3. Vertical Boundary Lines
                self.ax.axvline(x_start_plot, color=border_color, linestyle="-", linewidth=2.5 if is_selected else 1.2, zorder=4)
                self.ax.axvline(x_end_plot, color=border_color, linestyle="-", linewidth=2.5 if is_selected else 1.2, zorder=4)

                # 4. Origin-style Top Control Tag (Box Header with Area & FWHM text)
                area_val = r.get("calculated_area", 0.0)
                area_unit = r.get("area_unit", "A·min")
                fwhm_val = r.get("fwhm_val", 0.0)
                fwhm_unit = r.get("fwhm_unit", "min")
                t_name = r.get("type_name", f"R{r['id']}")
                
                tag_text = f"[{t_name}]\nArea={area_val:.5E} {area_unit}\nFWHM={fwhm_val:.5f} {fwhm_unit}" if fwhm_val > 0 else f"[{t_name}]\nArea={area_val:.5E} {area_unit}"
                x_mid = (x_start_plot + x_end_plot) / 2.0

                box_bg = "#ffffcc" if is_selected else "#ffffff"
                self.ax.text(
                    x_mid, 
                    y_max_plot * 0.96 if not is_log else np.nanmax(sub_y) * 1.5, 
                    tag_text, 
                    fontsize=8, 
                    fontfamily="Arial",
                    fontweight="bold" if is_selected else "normal",
                    ha="center", 
                    va="top", 
                    bbox=dict(boxstyle="square,pad=0.25", facecolor=box_bg, alpha=0.92, edgecolor=border_color, linewidth=1.5 if is_selected else 1.0),
                    zorder=5
                )

        # Configure Axes & Title
        self.ax.set_title(f"Mass Spectrometry Measurement — {file_title}", fontsize=12, fontweight="bold", pad=12)
        self.ax.set_xlabel(x_label, fontsize=11, fontweight="bold")
        self.ax.set_ylabel("Ion Current [A]", fontsize=11, fontweight="bold")

        if is_log:
            self.ax.set_yscale("log")
            self.ax.set_ylabel("Ion Current [A] (Log Scale)", fontsize=11, fontweight="bold")

        self.ax.legend(fontsize=9, loc="upper right", frameon=True, facecolor="#ffffff", edgecolor="#cccccc")
        self.fig.tight_layout()

        if preserve_zoom and prev_xlim is not None and prev_ylim is not None:
            if prev_xlim != (0.0, 1.0):
                self.ax.set_xlim(prev_xlim)
                self.ax.set_ylim(prev_ylim)

        self.has_plotted_once = True
        self.canvas.draw_idle()

    def export_plot(self):
        """Export plot image to PNG or SVG."""
        if self.current_df is None:
            messagebox.showwarning("Warning", "No active plot to export.")
            return

        fpath = filedialog.asksaveasfilename(
            title="Export Plot Image",
            defaultextension=".png",
            filetypes=[("PNG Image", "*.png"), ("PDF Document", "*.pdf"), ("SVG Image", "*.svg")]
        )
        if fpath:
            self.fig.savefig(fpath, dpi=300, bbox_inches="tight")
            messagebox.showinfo("Export Successful", f"Plot image saved to:\n{fpath}")

def main():
    root = tk.Tk()
    app = ASCGasPlotterApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
