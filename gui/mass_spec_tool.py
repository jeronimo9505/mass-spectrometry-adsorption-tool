import os
import io
import json
import pandas as pd
import numpy as np

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from core.asc_parser import GAS_MAPPING, load_asc_dataframe
from core.integration_engine import calculate_roi_integration, auto_detect_cycle_pairs
from core.capacity_calculator import compute_co2_capacity, compute_co2_capacity_breakdown

ROI_PRESETS = {
    "baseline_signal": {"fill": "#cce5ff", "border": "#3399ff", "label": "Baseline", "baseline": "mean_signal"},
    "adsorption": {"fill": "#ffff99", "border": "#d4af37", "label": "Adsorption", "baseline": "straight_line"},
    "desorption": {"fill": "#ff99ff", "border": "#c77dff", "label": "Desorption", "baseline": "raw_zero"},
    "general": {"fill": "#99ff99", "border": "#38b000", "label": "General", "baseline": "straight_line"}
}

class MassSpecToolView(ttk.Frame):
    """
    Module 3: Mass Spectrometry & Gas Adsorption/Desorption Analysis Tool.
    Origin-style Simpson Integration, Interactive Mouse-Draggable ROI Boxes,
    Auto-detection of cycle pairs, and CO2 capacity (q in mmol/g) calculation.
    """
    def __init__(self, parent, vault, on_analysis_saved_callback=None):
        super().__init__(parent)
        self.vault = vault
        self.on_analysis_saved_callback = on_analysis_saved_callback

        self.current_sample_id = None
        self.current_fpath = None
        self.current_df = None
        self.current_file_info = {}

        # Integration Ranges (list of dicts)
        self.ranges_list = []
        self.range_id_counter = 1
        self.selected_range_idx = None

        # Interactive Dragging States
        self.drag_target = None  # (idx, 'start' | 'end' | 'body')
        self.drag_initial_x = None
        self.drag_initial_range = None

        # Capacity Parameters (Matching Excel experimental parameters)
        self.cap_mass_mg_var = tk.DoubleVar(value=620.0)
        self.cap_mass_var = tk.DoubleVar(value=0.62)
        self.cap_water_pct_var = tk.DoubleVar(value=21.4)
        self.cap_c0_var = tk.DoubleVar(value=0.15)
        self.cap_flow_co2_var = tk.DoubleVar(value=15.0)
        self.cap_flow_n2_var = tk.DoubleVar(value=85.0)
        self.cap_flow_total_var = tk.DoubleVar(value=100.0)
        self.cap_temp_var = tk.DoubleVar(value=24.0)
        self.cap_temp_ref_var = tk.DoubleVar(value=25.0)
        self.cap_vm25_var = tk.DoubleVar(value=24465.0)
        self.cap_ref_ads_var = tk.DoubleVar(value=0.00)
        self.cap_ref_des_var = tk.DoubleVar(value=0.00)
        self.cap_s_baseline_var = tk.DoubleVar(value=0.0)
        self.cap_k_mode_var = tk.StringVar(value="ads_first_point")
        self.cap_area_ads_var = tk.DoubleVar(value=1.5054e-9)
        self.cap_area_des_var = tk.DoubleVar(value=1.06058e-10)
        self.cap_auto_sync_var = tk.BooleanVar(value=True)
        self._updating_mass = False
        self._updating_flow = False
        self.last_capacity_results = {}

        # Suggested Δt for Auto-Detection (Configurable)
        self.autodetect_dt_ads_var = tk.DoubleVar(value=22.0)
        self.autodetect_dt_des_var = tk.DoubleVar(value=8.0)
        self.autodetect_dt_base_var = tk.DoubleVar(value=2.0)

        self.create_widgets()

    def create_widgets(self):
        main_paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # Left Control Panel
        left_frame = ttk.Frame(main_paned, width=640)
        main_paned.add(left_frame, weight=0)

        # Right Matplotlib Plot Panel
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=1)

        # Top Sample Banner
        self.lbl_active_banner = tk.Label(
            left_frame,
            text="🏷️ Sample: [ None ]  |  File: [ None ]",
            font=("Segoe UI", 9, "bold"),
            bg="#f0f4f8",
            fg="#1d3557",
            padx=8,
            pady=4,
            relief="solid",
            bd=1
        )
        self.lbl_active_banner.pack(fill=tk.X, pady=(0, 4))

        # Left Notebook with 4 Tabs
        self.notebook = ttk.Notebook(left_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        tab_plot = ttk.Frame(self.notebook, padding=6)
        tab_integ = ttk.Frame(self.notebook, padding=6)
        tab_capacity = ttk.Frame(self.notebook, padding=6)
        tab_report = ttk.Frame(self.notebook, padding=6)

        self.notebook.add(tab_plot, text=" 📊 Channels & Plot ")
        self.notebook.add(tab_integ, text=" 📈 Regions & Integration ")
        self.notebook.add(tab_capacity, text=" 🧪 CO₂ Capacity (q) ")
        self.notebook.add(tab_report, text=" 📑 Report ")

        self._build_tab_plot(tab_plot)
        self._build_tab_integ(tab_integ)
        self._build_tab_capacity(tab_capacity)
        self._build_tab_report(tab_report)

        # Build Right Matplotlib Canvas
        self._build_plot_canvas(right_frame)

    # ==================== TAB 1: PLOT & GASES ====================

    def _build_tab_plot(self, parent):
        file_frame = ttk.LabelFrame(parent, text=" 1. Measurement File (.asc) ", padding=6)
        file_frame.pack(fill=tk.X, pady=(0, 6))

        row_f = ttk.Frame(file_frame)
        row_f.pack(fill=tk.X, pady=2)
        ttk.Button(row_f, text="📂 Load Another .asc File...", command=self.on_browse_file).pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.lbl_file_info = ttk.Label(file_frame, text="Duration: - | Cycles: - | Points: -", font=("Segoe UI", 8))
        self.lbl_file_info.pack(anchor="w", pady=(4, 0))

        # Gas Channels
        gas_frame = ttk.LabelFrame(parent, text=" 2. Quadrupole Mass Channels ", padding=6)
        gas_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

        btn_row = ttk.Frame(gas_frame)
        btn_row.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(btn_row, text="Select All", command=self.select_all_gases).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="Deselect All", command=self.clear_all_gases).pack(side=tk.LEFT, padx=2)

        self.gas_vars = {}
        for col, meta in GAS_MAPPING.items():
            is_def = (col in ["'0/2'", "'0/3'", "'0/6'"])
            var = tk.BooleanVar(value=is_def)
            self.gas_vars[col] = var
            cb = ttk.Checkbutton(
                gas_frame,
                text=f"{meta['label']} — {meta['full_name']}",
                variable=var,
                command=lambda: self.update_plot(preserve_zoom=True)
            )
            cb.pack(anchor="w", pady=1)

        # Axis & Scale Options
        axis_frame = ttk.LabelFrame(parent, text=" 3. Scale & Axes ", padding=6)
        axis_frame.pack(fill=tk.X)

        self.xaxis_var = tk.StringVar(value="min")
        r_row = ttk.Frame(axis_frame)
        r_row.pack(fill=tk.X, pady=2)
        ttk.Radiobutton(r_row, text="Minutes (min)", variable=self.xaxis_var, value="min", command=self.on_xaxis_change).pack(side=tk.LEFT, padx=4)
        ttk.Radiobutton(r_row, text="Seconds (s)", variable=self.xaxis_var, value="sec", command=self.on_xaxis_change).pack(side=tk.LEFT, padx=4)

        self.log_scale_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(axis_frame, text="Logarithmic Y-Scale (Ion Current)", variable=self.log_scale_var, command=lambda: self.update_plot(preserve_zoom=True)).pack(anchor="w", pady=2)

    # ==================== TAB 2: INTEGRATION & ROI ====================

    def _build_tab_integ(self, parent):
        top_row = ttk.Frame(parent)
        top_row.pack(fill=tk.X, pady=(0, 6))

        ttk.Label(top_row, text="Integrated Gas:").pack(side=tk.LEFT, padx=(0, 4))
        self.integ_gas_var = tk.StringVar(value="CO2 (m/z 44.28)")
        gas_names = [m["label"] for m in GAS_MAPPING.values()]
        self.combo_integ_gas = ttk.Combobox(top_row, textvariable=self.integ_gas_var, values=gas_names, state="readonly", width=18)
        self.combo_integ_gas.pack(side=tk.LEFT, padx=(0, 6))
        self.combo_integ_gas.bind("<<ComboboxSelected>>", lambda e: self.recalculate_and_plot())

        # Action Buttons
        btn_box = ttk.LabelFrame(parent, text=" ROI Region Actions ", padding=6)
        btn_box.pack(fill=tk.X, pady=(0, 6))

        b_row1 = ttk.Frame(btn_box)
        b_row1.pack(fill=tk.X, pady=2)
        ttk.Button(b_row1, text="🔵 + Baseline Signal", command=self.add_baseline_box).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        ttk.Button(b_row1, text="🟡 + Adsorption", command=self.add_adsorption_box).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        ttk.Button(b_row1, text="🟣 + Desorption", command=self.add_desorption_box).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        # Suggested Δt for Auto-Detection
        dt_frame = ttk.Frame(btn_box)
        dt_frame.pack(fill=tk.X, pady=(4, 2))
        ttk.Label(dt_frame, text="Suggested Δt (min):", font=("Segoe UI", 8, "bold")).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Label(dt_frame, text="Ads:").pack(side=tk.LEFT, padx=(2, 1))
        ttk.Spinbox(dt_frame, from_=1.0, to=120.0, increment=1.0, textvariable=self.autodetect_dt_ads_var, width=5).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Label(dt_frame, text="Des (max):").pack(side=tk.LEFT, padx=(2, 1))
        ttk.Spinbox(dt_frame, from_=1.0, to=60.0, increment=0.5, textvariable=self.autodetect_dt_des_var, width=4).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Label(dt_frame, text="Base:").pack(side=tk.LEFT, padx=(2, 1))
        ttk.Spinbox(dt_frame, from_=0.5, to=30.0, increment=0.5, textvariable=self.autodetect_dt_base_var, width=4).pack(side=tk.LEFT, padx=(0, 2))

        b_row2 = ttk.Frame(btn_box)
        b_row2.pack(fill=tk.X, pady=2)
        ttk.Button(b_row2, text="⚡ AUTO-DETECT CYCLES", command=self.on_auto_detect_cycles).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        ttk.Button(b_row2, text="🗑️ Clear All", command=self.clear_all_ranges).pack(side=tk.LEFT, padx=2)

        # Treeview table of ranges
        cols = ("id", "type", "start", "end", "dx", "area", "fwhm")
        self.tree_ranges = ttk.Treeview(parent, columns=cols, show="headings", selectmode="browse", height=7)
        self.tree_ranges.heading("id", text="#")
        self.tree_ranges.heading("type", text="Type")
        self.tree_ranges.heading("start", text="Start")
        self.tree_ranges.heading("end", text="End")
        self.tree_ranges.heading("dx", text="Δt")
        self.tree_ranges.heading("area", text="Net Area")
        self.tree_ranges.heading("fwhm", text="FWHM")

        self.tree_ranges.column("id", width=30, anchor="center")
        self.tree_ranges.column("type", width=95, anchor="w")
        self.tree_ranges.column("start", width=65, anchor="e")
        self.tree_ranges.column("end", width=65, anchor="e")
        self.tree_ranges.column("dx", width=55, anchor="e")
        self.tree_ranges.column("area", width=90, anchor="e")
        self.tree_ranges.column("fwhm", width=60, anchor="e")

        self.tree_ranges.pack(fill=tk.BOTH, expand=True, pady=(0, 6))
        self.tree_ranges.bind("<<TreeviewSelect>>", self.on_range_tree_select)

        # Fine-tuning adjustments
        adj_frame = ttk.LabelFrame(parent, text=" Fine-Tuning Boundaries (min) ", padding=6)
        adj_frame.pack(fill=tk.X)

        adj_grid = ttk.Frame(adj_frame)
        adj_grid.pack(fill=tk.X)

        # Row 0: Start and End
        ttk.Label(adj_grid, text="Start:").grid(row=0, column=0, sticky="w", pady=2)
        self.spin_start_var = tk.DoubleVar(value=0.0)
        self.spin_start = ttk.Spinbox(adj_grid, from_=0.0, to=9999.0, increment=0.2, textvariable=self.spin_start_var, width=8, command=self.on_spin_change)
        self.spin_start.grid(row=0, column=1, sticky="w", padx=3, pady=2)
        self.spin_start.bind("<Return>", lambda e: self.on_spin_change())
        self.spin_start.bind("<FocusOut>", lambda e: self.on_spin_change())

        ttk.Label(adj_grid, text="End:").grid(row=0, column=2, sticky="w", pady=2)
        self.spin_end_var = tk.DoubleVar(value=0.0)
        self.spin_end = ttk.Spinbox(adj_grid, from_=0.0, to=9999.0, increment=0.2, textvariable=self.spin_end_var, width=8, command=self.on_spin_change)
        self.spin_end.grid(row=0, column=3, sticky="w", padx=3, pady=2)
        self.spin_end.bind("<Return>", lambda e: self.on_spin_change())
        self.spin_end.bind("<FocusOut>", lambda e: self.on_spin_change())

        # Row 1: Δt (min) and Lock Δt
        ttk.Label(adj_grid, text="Δt (min):").grid(row=1, column=0, sticky="w", pady=2)
        self.spin_dt_var = tk.DoubleVar(value=0.0)
        self.spin_dt = ttk.Spinbox(adj_grid, from_=0.05, to=9999.0, increment=0.2, textvariable=self.spin_dt_var, width=8, command=self.on_dt_change)
        self.spin_dt.grid(row=1, column=1, sticky="w", padx=3, pady=2)
        self.spin_dt.bind("<Return>", lambda e: self.on_dt_change())
        self.spin_dt.bind("<FocusOut>", lambda e: self.on_dt_change())

        self.lock_dt_var = tk.BooleanVar(value=False)
        self.chk_lock_dt = ttk.Checkbutton(adj_grid, text="Lock Δt", variable=self.lock_dt_var)
        self.chk_lock_dt.grid(row=1, column=2, columnspan=2, sticky="w", padx=3, pady=2)

        # Row 2: Baseline and Delete button
        ttk.Label(adj_grid, text="Baseline:").grid(row=2, column=0, sticky="w", pady=2)
        self.roi_baseline_var = tk.StringVar(value="straight_line")
        b_combo = ttk.Combobox(
            adj_grid, 
            textvariable=self.roi_baseline_var, 
            values=["straight_line", "raw_zero", "horizontal_left", "mean_signal", "avg_ads_baseline"],
            state="readonly", 
            width=14
        )
        b_combo.grid(row=2, column=1, columnspan=2, sticky="w", padx=3, pady=2)
        b_combo.bind("<<ComboboxSelected>>", self.on_baseline_combo_change)

        ttk.Button(adj_grid, text="🗑️ Delete ROI", command=self.remove_selected_range).grid(row=2, column=3, sticky="e", pady=2)

        # Confirm & Advance Button to Tab 3
        btn_confirm = ttk.Button(
            parent,
            text="💾 Confirm Integration & Proceed to CO₂ Capacity ➡️",
            command=self.on_confirm_integration_and_proceed
        )
        btn_confirm.pack(fill=tk.X, pady=(6, 2))

    # ==================== TAB 3: CAPACITY CALCULATOR ====================

    def _build_tab_capacity(self, parent):
        scroll_c = ttk.Frame(parent)
        scroll_c.pack(fill=tk.BOTH, expand=True)

        # Top Action Button: User-requested "Usar 1er punto de cada Ads como Baseline"
        btn_use_ads_base = ttk.Button(
            scroll_c,
            text="🎯 Usar 1er punto de cada Ads como Baseline (Ciclo a Ciclo)",
            command=self.use_ads_first_point_baseline
        )
        btn_use_ads_base.pack(fill=tk.X, pady=(0, 4))

        # 1. Assay & Sample Parameters Frame
        p_frame = ttk.LabelFrame(scroll_c, text=" Assay & Sample Parameters (Excel Model) ", padding=5)
        p_frame.pack(fill=tk.X, pady=(0, 4))

        grid = ttk.Frame(p_frame)
        grid.pack(fill=tk.X)

        # Connect synchronization between mg and g, and flows
        self._trace_ids = []
        t1 = self.cap_mass_mg_var.trace_add("write", self._on_mass_mg_change)
        t2 = self.cap_mass_var.trace_add("write", self._on_mass_g_change)
        t3 = self.cap_flow_co2_var.trace_add("write", self._on_flow_parts_change)
        t4 = self.cap_flow_n2_var.trace_add("write", self._on_flow_parts_change)
        self._trace_ids.extend([
            (self.cap_mass_mg_var, t1),
            (self.cap_mass_var, t2),
            (self.cap_flow_co2_var, t3),
            (self.cap_flow_n2_var, t4)
        ])

        for var in [self.cap_water_pct_var, self.cap_temp_var, self.cap_temp_ref_var, self.cap_vm25_var, self.cap_c0_var, self.cap_ref_ads_var, self.cap_ref_des_var, self.cap_k_mode_var]:
            tid = var.trace_add("write", lambda *args: self.recalculate_capacity())
            self._trace_ids.append((var, tid))

        # Row 0: Sample Mass (mg) and Sample Mass (g)
        ttk.Label(grid, text="Mass (mg):", font=("Segoe UI", 8, "bold")).grid(row=0, column=0, sticky="w", pady=1)
        sb_mass_mg = ttk.Spinbox(grid, from_=0.1, to=100000.0, increment=10.0, textvariable=self.cap_mass_mg_var, width=8)
        sb_mass_mg.grid(row=0, column=1, padx=2, pady=1)
        sb_mass_mg.bind("<KeyRelease>", lambda e: self._on_mass_mg_change())

        ttk.Label(grid, text="Mass (g):", font=("Segoe UI", 8, "bold")).grid(row=0, column=2, sticky="w", pady=1)
        sb_mass = ttk.Spinbox(grid, from_=0.0001, to=100.0, increment=0.01, textvariable=self.cap_mass_var, width=8)
        sb_mass.grid(row=0, column=3, padx=2, pady=1)
        sb_mass.bind("<KeyRelease>", lambda e: self._on_mass_g_change())

        # Row 1: Water Loss % and Dry Mass (g)
        ttk.Label(grid, text="Water Loss (%):", font=("Segoe UI", 8)).grid(row=1, column=0, sticky="w", pady=1)
        sb_water = ttk.Spinbox(grid, from_=0.0, to=100.0, increment=0.5, textvariable=self.cap_water_pct_var, width=8, command=self.recalculate_capacity)
        sb_water.grid(row=1, column=1, padx=2, pady=1)
        sb_water.bind("<KeyRelease>", lambda e: self.recalculate_capacity())

        ttk.Label(grid, text="Dry Mass (g):", font=("Segoe UI", 8)).grid(row=1, column=2, sticky="w", pady=1)
        self.lbl_param_dry_mass = ttk.Label(grid, text="0.4873 g", font=("Segoe UI", 8, "bold"), foreground="#1d3557")
        self.lbl_param_dry_mass.grid(row=1, column=3, sticky="w", padx=2, pady=1)

        # Row 2: CO2 Flow (mL/min) and N2 Flow (mL/min)
        ttk.Label(grid, text="CO₂ Flow (mL/min):", font=("Segoe UI", 8)).grid(row=2, column=0, sticky="w", pady=1)
        sb_co2 = ttk.Spinbox(grid, from_=0.0, to=1000.0, increment=1.0, textvariable=self.cap_flow_co2_var, width=8)
        sb_co2.grid(row=2, column=1, padx=2, pady=1)
        sb_co2.bind("<KeyRelease>", lambda e: self._on_flow_parts_change())

        ttk.Label(grid, text="N₂ Flow (mL/min):", font=("Segoe UI", 8)).grid(row=2, column=2, sticky="w", pady=1)
        sb_n2 = ttk.Spinbox(grid, from_=0.0, to=5000.0, increment=5.0, textvariable=self.cap_flow_n2_var, width=8)
        sb_n2.grid(row=2, column=3, padx=2, pady=1)
        sb_n2.bind("<KeyRelease>", lambda e: self._on_flow_parts_change())

        # Row 3: Total Flow and C0 fraction
        ttk.Label(grid, text="Total Flow (mL/min):", font=("Segoe UI", 8)).grid(row=3, column=0, sticky="w", pady=1)
        sb_flow = ttk.Spinbox(grid, from_=1.0, to=6000.0, increment=5.0, textvariable=self.cap_flow_total_var, width=8, command=self.recalculate_capacity)
        sb_flow.grid(row=3, column=1, padx=2, pady=1)
        sb_flow.bind("<KeyRelease>", lambda e: self.recalculate_capacity())

        ttk.Label(grid, text="C₀ (Feed Fract):", font=("Segoe UI", 8)).grid(row=3, column=2, sticky="w", pady=1)
        sb_c0 = ttk.Spinbox(grid, from_=0.001, to=1.0, increment=0.01, textvariable=self.cap_c0_var, width=8, command=self.recalculate_capacity)
        sb_c0.grid(row=3, column=3, padx=2, pady=1)
        sb_c0.bind("<KeyRelease>", lambda e: self.recalculate_capacity())

        # Row 4: Temp T2 and Ref Temp T1
        ttk.Label(grid, text="Temp T₂ (°C):", font=("Segoe UI", 8)).grid(row=4, column=0, sticky="w", pady=1)
        sb_temp = ttk.Spinbox(grid, from_=0.0, to=500.0, increment=1.0, textvariable=self.cap_temp_var, width=8, command=self.recalculate_capacity)
        sb_temp.grid(row=4, column=1, padx=2, pady=1)
        sb_temp.bind("<KeyRelease>", lambda e: self.recalculate_capacity())

        ttk.Label(grid, text="Ref T₁ (°C):", font=("Segoe UI", 8)).grid(row=4, column=2, sticky="w", pady=1)
        sb_t1 = ttk.Spinbox(grid, from_=0.0, to=100.0, increment=1.0, textvariable=self.cap_temp_ref_var, width=8, command=self.recalculate_capacity)
        sb_t1.grid(row=4, column=3, padx=2, pady=1)
        sb_t1.bind("<KeyRelease>", lambda e: self.recalculate_capacity())

        # Row 5: Vm,25 and Vm,exp
        ttk.Label(grid, text="Vₘ,25 (mL/mol):", font=("Segoe UI", 8)).grid(row=5, column=0, sticky="w", pady=1)
        sb_vm = ttk.Spinbox(grid, from_=1000.0, to=50000.0, increment=50.0, textvariable=self.cap_vm25_var, width=8, command=self.recalculate_capacity)
        sb_vm.grid(row=5, column=1, padx=2, pady=1)
        sb_vm.bind("<KeyRelease>", lambda e: self.recalculate_capacity())

        ttk.Label(grid, text="Vₘ,exp (mL/mol):", font=("Segoe UI", 8)).grid(row=5, column=2, sticky="w", pady=1)
        self.lbl_param_vm_exp = ttk.Label(grid, text="24382.9", font=("Segoe UI", 8), foreground="#457b9d")
        self.lbl_param_vm_exp.grid(row=5, column=3, sticky="w", padx=2, pady=1)

        # Row 6: Blank References
        ttk.Label(grid, text="Blank Ads (mmol/g):", font=("Segoe UI", 8)).grid(row=6, column=0, sticky="w", pady=1)
        sb_ref_a = ttk.Spinbox(grid, from_=0.0, to=10.0, increment=0.01, textvariable=self.cap_ref_ads_var, width=8, command=self.recalculate_capacity)
        sb_ref_a.grid(row=6, column=1, padx=2, pady=1)
        sb_ref_a.bind("<KeyRelease>", lambda e: self.recalculate_capacity())

        ttk.Label(grid, text="Blank Des (mmol/g):", font=("Segoe UI", 8)).grid(row=6, column=2, sticky="w", pady=1)
        sb_ref_d = ttk.Spinbox(grid, from_=0.0, to=10.0, increment=0.01, textvariable=self.cap_ref_des_var, width=8, command=self.recalculate_capacity)
        sb_ref_d.grid(row=6, column=3, padx=2, pady=1)
        sb_ref_d.bind("<KeyRelease>", lambda e: self.recalculate_capacity())

        # Row 7: k Calculation Mode Selector (Radiobuttons)
        mode_f = ttk.LabelFrame(scroll_c, text=" k Factor & Baseline Calculation Mode ", padding=4)
        mode_f.pack(fill=tk.X, pady=(0, 4))
        
        ttk.Radiobutton(mode_f, text="1st Point of Adsorption (Cycle-by-Cycle)", variable=self.cap_k_mode_var, value="ads_first_point", command=self.recalculate_capacity).pack(anchor="w")
        ttk.Radiobutton(mode_f, text="Plateau Region 'Baseline Signal'", variable=self.cap_k_mode_var, value="baseline_plateau", command=self.recalculate_capacity).pack(anchor="w")
        ttk.Radiobutton(mode_f, text="Global Average (Classic Excel Mode)", variable=self.cap_k_mode_var, value="global_average", command=self.recalculate_capacity).pack(anchor="w")

        # 2. Analytical Breakdown Table (Matching Excel analytical model)
        table_frame = ttk.LabelFrame(scroll_c, text=" Analytical Breakdown (Excel Model) ", padding=4)
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 4))

        bd_cols = ("step", "origin_area", "abs_area", "s_base", "k_factor", "n_mol", "n_mmol", "q_100", "q_dry")
        self.tree_breakdown = ttk.Treeview(table_frame, columns=bd_cols, show="headings", height=6)
        self.tree_breakdown.heading("step", text="Step")
        self.tree_breakdown.heading("origin_area", text="Origin Area")
        self.tree_breakdown.heading("abs_area", text="|A| (A·min)")
        self.tree_breakdown.heading("s_base", text="S_base (A)")
        self.tree_breakdown.heading("k_factor", text="k (A⁻¹)")
        self.tree_breakdown.heading("n_mol", text="nCO₂ (mol)")
        self.tree_breakdown.heading("n_mmol", text="nCO₂ (mmol)")
        self.tree_breakdown.heading("q_100", text="q (100% Mass)")
        self.tree_breakdown.heading("q_dry", text="q (Dry Mass)")

        self.tree_breakdown.column("step", width=50, anchor="w")
        self.tree_breakdown.column("origin_area", width=78, anchor="e")
        self.tree_breakdown.column("abs_area", width=78, anchor="e")
        self.tree_breakdown.column("s_base", width=72, anchor="e")
        self.tree_breakdown.column("k_factor", width=70, anchor="e")
        self.tree_breakdown.column("n_mol", width=68, anchor="e")
        self.tree_breakdown.column("n_mmol", width=64, anchor="e")
        self.tree_breakdown.column("q_100", width=68, anchor="e")
        self.tree_breakdown.column("q_dry", width=68, anchor="e")

        sb_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree_breakdown.yview)
        self.tree_breakdown.configure(yscrollcommand=sb_y.set)
        self.tree_breakdown.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb_y.pack(side=tk.RIGHT, fill=tk.Y)

        # 3. Results Display Card (Average Recalculation)
        res_frame = ttk.LabelFrame(scroll_c, text=" CO₂ Capacity Results (q) — Summary Averages ", padding=6)
        res_frame.pack(fill=tk.X, pady=(0, 4))

        self.lbl_q_ads = ttk.Label(res_frame, text="Net Adsorption (q_net):   --- mmol/g", font=("Segoe UI", 9, "bold"), foreground="#d90429")
        self.lbl_q_ads.pack(anchor="w", pady=1)

        self.lbl_q_des = ttk.Label(res_frame, text="Net Desorption (q_net):   --- mmol/g", font=("Segoe UI", 9, "bold"), foreground="#7209b7")
        self.lbl_q_des.pack(anchor="w", pady=1)

        self.lbl_recovery = ttk.Label(res_frame, text="Recovery Ratio:           --- %", font=("Segoe UI", 9, "bold"), foreground="#2a9d8f")
        self.lbl_recovery.pack(anchor="w", pady=1)

        self.lbl_details = ttk.Label(res_frame, text="Active Mass: - | Vm: - | k: - | S_baseline: -", font=("Segoe UI", 8))
        self.lbl_details.pack(anchor="w", pady=(3, 0))

        # 4. Save to sample button
        btn_save_res = ttk.Button(scroll_c, text="💾 SAVE ANALYSIS TO SAMPLE", command=self.on_save_analysis_to_sample)
        btn_save_res.pack(fill=tk.X, pady=(2, 0))

    # ==================== TAB 4: REPORT ====================

    def _build_tab_report(self, parent):
        t_bar = ttk.Frame(parent)
        t_bar.pack(fill=tk.X, pady=(0, 6))

        ttk.Button(t_bar, text="📋 Copy Report", command=self.on_copy_report).pack(side=tk.LEFT, padx=3)
        ttk.Button(t_bar, text="💾 Save to Vault", command=self.on_save_report_file).pack(side=tk.LEFT, padx=3)

        self.report_text = tk.Text(parent, wrap="none", font=("Consolas", 9))
        scroll_rt = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.report_text.yview)
        self.report_text.configure(yscrollcommand=scroll_rt.set)
        self.report_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_rt.pack(side=tk.RIGHT, fill=tk.Y)

    # ==================== RIGHT MATPLOTLIB CANVAS ====================

    def _build_plot_canvas(self, parent):
        self.fig, self.ax = plt.subplots(figsize=(8, 6), dpi=100)
        self.fig.patch.set_facecolor("#f8f9fa")

        self.canvas = FigureCanvasTkAgg(self.fig, master=parent)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill=tk.BOTH, expand=True)

        toolbar_frame = ttk.Frame(parent)
        toolbar_frame.pack(fill=tk.X)
        self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
        self.toolbar.update()

        ttk.Button(toolbar_frame, text="🖼️ Export PNG/PDF", command=self.export_plot_image).pack(side=tk.RIGHT, padx=4)

        # Mouse Events for dragging ROI boundaries
        self.canvas.mpl_connect("button_press_event", self.on_mouse_press)
        self.canvas.mpl_connect("motion_notify_event", self.on_mouse_drag)
        self.canvas.mpl_connect("button_release_event", self.on_mouse_release)

        self.show_placeholder_plot()

    def show_placeholder_plot(self):
        self.ax.clear()
        self.ax.set_title("Load an .asc file or select a sample in the Logbook", fontsize=11, pad=12)
        self.ax.set_xlabel("Time (min)", fontsize=10)
        self.ax.set_ylabel("Ion Current [A]", fontsize=10)
        self.ax.grid(True, linestyle="--", alpha=0.5)
        self.canvas.draw()

    # ==================== DATA LOADING & SYNC ====================

    def load_sample_and_file(self, sample_id, asc_fpath):
        self.current_sample_id = sample_id
        self.current_fpath = asc_fpath

        # Pull parameters from sample metadata
        if sample_id and sample_id in self.vault.logbook:
            meta = self.vault.logbook[sample_id]
            self.cap_mass_var.set(float(meta.get("mass_total_g", 0.5055)))
            self.cap_water_pct_var.set(float(meta.get("water_loss_pct", 21.4)))
            self.cap_c0_var.set(float(meta.get("c0", 0.15)))
            self.cap_flow_total_var.set(float(meta.get("flow_total", 100.0)))
            self.cap_temp_var.set(float(meta.get("temp_c", 24.0)))
            self.cap_ref_ads_var.set(float(meta.get("ref_ads", 0.23)))

        self.lbl_active_banner.config(
            text=f"🏷️ Sample: {sample_id or 'No ID'}  |  File: {os.path.basename(asc_fpath)}"
        )

        self.load_asc_file(asc_fpath)

        # Check if saved analysis exists
        if sample_id:
            fn = os.path.basename(asc_fpath)
            saved_an = self.vault.load_mass_spec_analysis(sample_id, fn)
            if saved_an and "ranges" in saved_an:
                self.ranges_list = saved_an["ranges"]
                self.range_id_counter = len(self.ranges_list) + 1
                self.recalculate_and_plot()
                self.recalculate_capacity()
                return

        # Default: if no saved ranges, auto-detect cycle pairs
        self.on_auto_detect_cycles()

    def on_browse_file(self):
        fpath = filedialog.askopenfilename(
            title="Select .asc File",
            filetypes=[("ASC Files", "*.asc"), ("All Files", "*.*")]
        )
        if fpath:
            self.load_sample_and_file(self.current_sample_id, fpath)

    def load_asc_file(self, fpath):
        try:
            self.current_df, self.current_file_info = load_asc_dataframe(fpath)
            self.lbl_file_info.config(
                text=f"Duration: {self.current_file_info['duration_min']} min | Cycles: {self.current_file_info['cycles']} | Rows: {self.current_file_info['row_count']}"
            )
            self.update_plot()
        except Exception as e:
            messagebox.showerror("Loading Error", f"Could not load .asc file:\n{e}")

    # ==================== PLOTTING ENGINE ====================

    def update_plot(self, preserve_zoom=False):
        if self.current_df is None:
            self.show_placeholder_plot()
            return

        x_lim = self.ax.get_xlim() if preserve_zoom else None
        y_lim = self.ax.get_ylim() if preserve_zoom else None

        self.ax.clear()
        x_mode = self.xaxis_var.get()
        x_col = "Time_min" if x_mode == "min" else "Time_sec"
        x_label = f"Time ({x_mode})"
        is_log = self.log_scale_var.get()

        integ_col = self.get_selected_integ_col()

        # Plot Selected Gas Channels
        has_curve = False
        for col, meta in GAS_MAPPING.items():
            if col in self.current_df.columns and self.gas_vars.get(col, tk.BooleanVar()).get():
                has_curve = True
                x_data = self.current_df[x_col].values
                y_data = pd.to_numeric(self.current_df[col], errors="coerce").values
                if is_log:
                    y_data = np.where(y_data > 0, y_data, np.nan)
                self.ax.plot(x_data, y_data, label=meta["label"], color=meta["color"], linewidth=1.2, alpha=0.9)

        # Plot ROI Boxes and Simpson baseline
        if integ_col in self.current_df.columns and self.ranges_list:
            y_integ_raw = pd.to_numeric(self.current_df[integ_col], errors="coerce").values
            t_min_arr = self.current_df["Time_min"].values

            for idx, r in enumerate(self.ranges_list):
                s_min, e_min = r["start_min"], r["end_min"]
                mask = (t_min_arr >= s_min) & (t_min_arr <= e_min)
                if not np.any(mask):
                    continue

                sub_x = self.current_df.loc[mask, x_col].values
                sub_y = y_integ_raw[mask]
                b_mode = r.get("baseline", "straight_line")

                y1, y2 = sub_y[0], sub_y[-1]
                x1, x2 = sub_x[0], sub_x[-1]

                if b_mode == "straight_line" and x2 > x1:
                    baseline = y1 + (y2 - y1) * (sub_x - x1) / (x2 - x1)
                elif b_mode == "horizontal_left":
                    baseline = np.full_like(sub_y, y1)
                elif b_mode == "avg_ads_baseline":
                    b_val = getattr(self, "current_avg_baseline", y1)
                    baseline = np.full_like(sub_y, b_val)
                elif b_mode == "mean_signal":
                    mean_val = float(np.mean(sub_y))
                    baseline = np.full_like(sub_y, mean_val)
                else:
                    baseline = np.zeros_like(sub_y)

                is_sel = (idx == self.selected_range_idx)
                f_color = "#ffff66" if is_sel else r.get("color", "#ffff99")
                b_color = "#e63946" if is_sel else "#888888"

                x_s = s_min if x_mode == "min" else sub_x[0]
                x_e = e_min if x_mode == "min" else sub_x[-1]

                # ROI vertical span box
                self.ax.axvspan(x_s, x_e, color=f_color, alpha=0.25 if not is_sel else 0.4, zorder=1)
                
                if b_mode == "mean_signal":
                    # For baseline signal plateau, draw horizontal dashed line
                    self.ax.plot(sub_x, baseline, color="#0077b6" if not is_sel else "#d90429", linestyle="--", linewidth=2.0, zorder=3)
                else:
                    # Fill between curve and baseline
                    self.ax.fill_between(sub_x, baseline, sub_y, color="#6c757d", alpha=0.35, zorder=2)
                    # Baseline plot
                    self.ax.plot(sub_x, baseline, color="#d90429" if is_sel else "#457b9d", linestyle="-", linewidth=1.5, zorder=3)
                
                # Vertical boundary lines
                self.ax.axvline(x_s, color=b_color, linestyle="-", linewidth=2.0 if is_sel else 1.2, zorder=4)
                self.ax.axvline(x_e, color=b_color, linestyle="-", linewidth=2.0 if is_sel else 1.2, zorder=4)

        prefix = f"[{self.current_sample_id}] " if self.current_sample_id else ""
        fn_title = os.path.basename(self.current_fpath) if self.current_fpath else ""
        self.ax.set_title(f"{prefix}Mass Spectrometry Measurement — {fn_title}", fontsize=11, fontweight="bold", pad=10)
        self.ax.set_xlabel(x_label, fontsize=10, fontweight="bold")
        self.ax.set_ylabel("Ion Current [A]", fontsize=10, fontweight="bold")
        if is_log:
            self.ax.set_yscale("log")
        self.ax.grid(True, linestyle="--", alpha=0.5)

        if has_curve:
            self.ax.legend(fontsize=8, loc="upper right", frameon=True)

        if preserve_zoom and x_lim and y_lim:
            self.ax.set_xlim(x_lim)
            self.ax.set_ylim(y_lim)

        self.fig.tight_layout()
        self.canvas.draw_idle()

    # ==================== ROI RANGES & INTEGRATION ====================

    def get_selected_integ_col(self):
        txt = self.integ_gas_var.get()
        for col, meta in GAS_MAPPING.items():
            if meta["label"] == txt:
                return col
        return "'0/6'"

    def add_baseline_box(self, s_min=None, e_min=None, name=None):
        self._add_box_with_preset(s_min, e_min, "baseline_signal", name)

    def add_adsorption_box(self, s_min=None, e_min=None, name=None):
        self._add_box_with_preset(s_min, e_min, "adsorption", name)

    def add_desorption_box(self, s_min=None, e_min=None, name=None):
        self._add_box_with_preset(s_min, e_min, "desorption", name)

    def use_ads_first_point_baseline(self):
        self.cap_k_mode_var.set("ads_first_point")
        self.recalculate_and_plot()
        self.recalculate_capacity()
        ads_count = sum(1 for r in self.ranges_list if r.get("phase") == "adsorption")
        if ads_count > 0:
            messagebox.showinfo(
                "Baseline Synchronized", 
                f"✅ Successfully synchronized cycle baselines using the 1st point of each Adsorption ({ads_count} cycles).\n\n"
                f"Each cycle automatically applies its individual baseline (S_baseline) to both the Adsorption and corresponding Desorption steps."
            )
        else:
            messagebox.showwarning(
                "No Adsorption ROIs", 
                "No Adsorption regions found. Please add regions or click '⚡ AUTO-DETECT CYCLES' in the 'Regions & Integration' tab."
            )

    def _on_mass_mg_change(self, *args):
        if self._updating_mass:
            return
        try:
            self._updating_mass = True
            mg = float(self.cap_mass_mg_var.get())
            self.cap_mass_var.set(round(mg / 1000.0, 5))
        except Exception:
            pass
        finally:
            self._updating_mass = False
        self.recalculate_capacity()

    def _on_mass_g_change(self, *args):
        if self._updating_mass:
            return
        try:
            self._updating_mass = True
            g = float(self.cap_mass_var.get())
            self.cap_mass_mg_var.set(round(g * 1000.0, 2))
        except Exception:
            pass
        finally:
            self._updating_mass = False
        self.recalculate_capacity()

    def _on_flow_parts_change(self, *args):
        if self._updating_flow:
            return
        try:
            self._updating_flow = True
            f_co2 = float(self.cap_flow_co2_var.get())
            f_n2 = float(self.cap_flow_n2_var.get())
            f_tot = f_co2 + f_n2
            self.cap_flow_total_var.set(round(f_tot, 2))
            if f_tot > 0:
                self.cap_c0_var.set(round(f_co2 / f_tot, 4))
        except Exception:
            pass
        finally:
            self._updating_flow = False
        self.recalculate_capacity()

    def _add_box_with_preset(self, s_min, e_min, preset_key, name=None):
        preset = ROI_PRESETS[preset_key]
        if s_min is None or e_min is None:
            last_end = max([r["end_min"] for r in self.ranges_list], default=1.0)
            s_min = round(last_end + 0.5, 2)
            e_min = round(s_min + 6.0, 2)

        r_id = self.range_id_counter
        self.range_id_counter += 1
        t_name = name or f"{preset['label'][:3]}_{r_id}"

        self.ranges_list.append({
            "id": r_id,
            "type_name": t_name,
            "phase": preset_key,
            "start_min": float(s_min),
            "end_min": float(e_min),
            "baseline": preset["baseline"],
            "color": preset["fill"]
        })
        self.recalculate_and_plot()

    def on_auto_detect_cycles(self):
        if self.current_df is None:
            return
        col = self.get_selected_integ_col()
        try:
            dt_ads = float(self.autodetect_dt_ads_var.get())
            dt_des = float(self.autodetect_dt_des_var.get())
            dt_base = float(self.autodetect_dt_base_var.get())
        except Exception:
            dt_ads, dt_des, dt_base = 22.0, 8.0, 2.0

        detected = auto_detect_cycle_pairs(
            self.current_df,
            target_col=col,
            dt_ads=dt_ads,
            dt_des=dt_des,
            dt_base=dt_base
        )
        if not detected:
            messagebox.showinfo("Auto-Detect", "No distinct cycle transitions detected. You can add boxes manually.")
            return

        self.ranges_list = detected
        self.range_id_counter = len(self.ranges_list) + 1
        self.recalculate_and_plot()
        self.recalculate_capacity()

    def clear_all_ranges(self):
        self.ranges_list.clear()
        self.range_id_counter = 1
        self.selected_range_idx = None
        self.recalculate_and_plot()

    def remove_selected_range(self):
        if self.selected_range_idx is not None and 0 <= self.selected_range_idx < len(self.ranges_list):
            del self.ranges_list[self.selected_range_idx]
            self.selected_range_idx = None
            self.recalculate_and_plot()

    def on_confirm_integration_and_proceed(self):
        if not self.ranges_list:
            messagebox.showwarning("No ROIs", "No integration regions defined yet. Add regions or click Auto-Detect.")
            return
        self.recalculate_and_plot()
        self.recalculate_capacity()
        self.notebook.select(2)

    def recalculate_and_plot(self):
        if self.current_df is None:
            return

        integ_col = self.get_selected_integ_col()

        # Recalculate each range
        for r in self.ranges_list:
            s_min = r["start_min"]
            e_min = r["end_min"]
            res = calculate_roi_integration(
                self.current_df,
                integ_col,
                s_min,
                e_min,
                baseline_mode=r.get("baseline", "straight_line")
            )
            r["calculated_area"] = res["area"]
            r["duration"] = res["duration"]
            r["fwhm_val"] = res["fwhm"]
            r["baseline_y0"] = res["baseline_y0"]
            r["y1"] = res["y1"]
            r["y2"] = res["y2"]
            if "mean_signal" in res:
                r["mean_signal"] = res["mean_signal"]

        # Refresh Treeview
        for item in self.tree_ranges.get_children():
            self.tree_ranges.delete(item)

        for idx, r in enumerate(self.ranges_list):
            t_name = r.get("type_name", f"ROI_{idx+1}")
            ar = r.get("calculated_area", 0.0)
            if r.get("phase") == "baseline_signal" or r.get("baseline") == "mean_signal":
                mean_sig = r.get("mean_signal", r.get("baseline_y0", 0.0))
                area_str = f"Sig: {mean_sig:.3e}"
                fwhm_str = "-"
            else:
                area_str = f"{ar:.4e}"
                fwhm_str = f"{r.get('fwhm_val', 0.0):.3f}"
            item_id = self.tree_ranges.insert("", tk.END, values=(
                r["id"],
                t_name,
                f"{r['start_min']:.2f}",
                f"{r['end_min']:.2f}",
                f"{r['duration']:.2f}",
                area_str,
                fwhm_str
            ))
            if idx == self.selected_range_idx:
                self.tree_ranges.selection_set(item_id)

        self.update_plot(preserve_zoom=True)
        self.recalculate_capacity()
        self.update_report_preview()

    def on_range_tree_select(self, event=None):
        sel = self.tree_ranges.selection()
        if not sel:
            self.selected_range_idx = None
            return
        vals = self.tree_ranges.item(sel[0], "values")
        r_id = int(vals[0])
        for idx, r in enumerate(self.ranges_list):
            if r["id"] == r_id:
                self.selected_range_idx = idx
                s = r["start_min"]
                e = r["end_min"]
                self.spin_start_var.set(s)
                self.spin_end_var.set(e)
                self.spin_dt_var.set(round(e - s, 2))
                self.roi_baseline_var.set(r.get("baseline", "straight_line"))
                break
        self.update_plot(preserve_zoom=True)

    def on_spin_change(self):
        if self.selected_range_idx is not None and 0 <= self.selected_range_idx < len(self.ranges_list):
            try:
                r = self.ranges_list[self.selected_range_idx]
                s = float(self.spin_start_var.get())
                if self.lock_dt_var.get():
                    dt = float(self.spin_dt_var.get())
                    e = round(s + dt, 2)
                    self.spin_end_var.set(e)
                else:
                    e = float(self.spin_end_var.get())
                    dt = round(max(0.01, e - s), 2)
                    self.spin_dt_var.set(dt)

                if e > s:
                    r["start_min"] = round(s, 2)
                    r["end_min"] = round(e, 2)
                    self.recalculate_and_plot()
            except ValueError:
                pass

    def on_dt_change(self):
        if self.selected_range_idx is not None and 0 <= self.selected_range_idx < len(self.ranges_list):
            try:
                r = self.ranges_list[self.selected_range_idx]
                s = float(self.spin_start_var.get())
                dt = float(self.spin_dt_var.get())
                if dt > 0:
                    e = round(s + dt, 2)
                    self.spin_end_var.set(e)
                    r["end_min"] = round(e, 2)
                    self.recalculate_and_plot()
            except ValueError:
                pass

    def on_baseline_combo_change(self, event=None):
        if self.selected_range_idx is not None and 0 <= self.selected_range_idx < len(self.ranges_list):
            r = self.ranges_list[self.selected_range_idx]
            r["baseline"] = self.roi_baseline_var.get()
            self.recalculate_and_plot()

    # ==================== INTERACTIVE MOUSE DRAG ====================

    def on_mouse_press(self, event):
        if event.inaxes != self.ax or event.button != 1:
            return

        x_click = event.xdata
        if x_click is None:
            return

        tol = 0.5  # minutes
        for idx, r in enumerate(self.ranges_list):
            s = r["start_min"]
            e = r["end_min"]
            if abs(x_click - s) <= tol:
                self.drag_target = (idx, "start")
                self.selected_range_idx = idx
                self.drag_initial_x = x_click
                self.drag_initial_range = (s, e)
                return
            elif abs(x_click - e) <= tol:
                self.drag_target = (idx, "end")
                self.selected_range_idx = idx
                self.drag_initial_x = x_click
                self.drag_initial_range = (s, e)
                return
            elif s < x_click < e:
                self.drag_target = (idx, "body")
                self.selected_range_idx = idx
                self.drag_initial_x = x_click
                self.drag_initial_range = (s, e)
                return

    def on_mouse_drag(self, event):
        if not self.drag_target or event.inaxes != self.ax:
            return

        x_curr = event.xdata
        if x_curr is None:
            return

        idx, part = self.drag_target
        r = self.ranges_list[idx]
        init_s, init_e = self.drag_initial_range
        dx = x_curr - self.drag_initial_x

        if part == "start":
            new_s = round(min(x_curr, r["end_min"] - 0.2), 2)
            r["start_min"] = max(0.0, new_s)
        elif part == "end":
            new_e = round(max(x_curr, r["start_min"] + 0.2), 2)
            r["end_min"] = new_e
        elif part == "body":
            new_s = round(max(0.0, init_s + dx), 2)
            duration = init_e - init_s
            r["start_min"] = new_s
            r["end_min"] = round(new_s + duration, 2)

        self.update_plot(preserve_zoom=True)

    def on_mouse_release(self, event):
        if self.drag_target:
            idx, _ = self.drag_target
            self.drag_target = None
            if idx == self.selected_range_idx and 0 <= idx < len(self.ranges_list):
                r = self.ranges_list[idx]
                s = r["start_min"]
                e = r["end_min"]
                self.spin_start_var.set(s)
                self.spin_end_var.set(e)
                self.spin_dt_var.set(round(e - s, 2))
            self.recalculate_and_plot()

    # ==================== CO2 CAPACITY CALCULATION ====================

    def recalculate_capacity(self):
        def _safe_float(var, default=0.0):
            try:
                v = var.get()
                return float(v)
            except Exception:
                try:
                    return float(str(v).strip())
                except Exception:
                    return default

        m_tot = _safe_float(self.cap_mass_var, 0.62)
        if m_tot <= 0.0:
            return

        w_pct = _safe_float(self.cap_water_pct_var, 0.0)
        c0_val = _safe_float(self.cap_c0_var, 0.15)
        flow_val = _safe_float(self.cap_flow_total_var, 100.0)
        temp_val = _safe_float(self.cap_temp_var, 24.0)
        ref_a = _safe_float(self.cap_ref_ads_var, 0.0)
        ref_d = _safe_float(self.cap_ref_des_var, 0.0)
        s_base_in = _safe_float(self.cap_s_baseline_var, 0.0)

        try:
            res = compute_co2_capacity_breakdown(
                ranges_list=self.ranges_list,
                mass_total_g=m_tot,
                water_loss_pct=w_pct,
                c0=c0_val,
                flow_total_ml_min=flow_val,
                temp_c=temp_val,
                temp_ref_c=_safe_float(self.cap_temp_ref_var, 25.0),
                vm_ref=_safe_float(self.cap_vm25_var, 24465.0),
                s_baseline_a=s_base_in if s_base_in > 1e-12 else None,
                k_mode=self.cap_k_mode_var.get(),
                ref_ads_mmol_g=ref_a,
                ref_des_mmol_g=ref_d
            )

            consts = res["constants"]
            avgs = res["averages"]
            ads_stat = avgs["ads"]
            des_stat = avgs["des"]

            # Store for Database / JSON logbook compatibility
            self.last_capacity_results = {
                "temp_c": consts["temp_c"],
                "Vm_exp": consts["Vm_exp"],
                "n_total_mol_min": consts["n_total_mol_min"],
                "k_factor": consts["k_factor"],
                "mass_total_g": consts["mass_total_g"],
                "water_loss_pct": consts["water_loss_pct"],
                "mass_active_g": consts["mass_active_g"],
                "c0": consts["c0"],
                "flow_total_ml_min": consts["flow_total_ml_min"],
                "s_baseline_a": consts["s_baseline_a"],
                "ref_ads_mmol_g": consts["ref_ads_mmol_g"],
                "ref_des_mmol_g": consts["ref_des_mmol_g"],
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
                "recovery_pct": avgs["recovery_pct"],
                "constants": consts,
                "rows": res["rows"],
                "averages": avgs
            }

            # Update dry mass and Vm labels if present
            if hasattr(self, "lbl_param_dry_mass"):
                self.lbl_param_dry_mass.config(text=f"{consts['mass_active_g']:.4f} g")
            if hasattr(self, "lbl_param_vm_exp"):
                self.lbl_param_vm_exp.config(text=f"{consts['Vm_exp']:.1f}")

            # Update Treeview breakdown table
            if hasattr(self, "tree_breakdown"):
                for item in self.tree_breakdown.get_children():
                    self.tree_breakdown.delete(item)
                for row in res["rows"]:
                    self.tree_breakdown.insert("", tk.END, values=(
                        row["type_name"],
                        f"{row['origin_area']:.4e}",
                        f"{row['abs_area']:.4e}",
                        f"{row['s_baseline']:.4e}",
                        f"{row['k_factor']:.3e}",
                        f"{row['n_mol']:.4e}",
                        f"{row['n_mmol']:.4f}",
                        f"{row['q_100']:.4f}",
                        f"{row['q_dry']:.4f}"
                    ))

            # Update Summary Labels
            ads_q_net = ads_stat["q_net_mean"]
            ads_q_dry = ads_stat["q_dry_mean"]
            ads_q_100 = ads_stat["q_100_mean"]

            des_q_net = des_stat["q_net_mean"]
            des_q_dry = des_stat["q_dry_mean"]
            des_q_100 = des_stat["q_100_mean"]

            rec = avgs["recovery_pct"]

            self.lbl_q_ads.config(
                text=f"Net Adsorption (q_net):   {ads_q_net:.4f} mmol/g  (Dry: {ads_q_dry:.4f} | 100%: {ads_q_100:.4f})"
            )
            self.lbl_q_des.config(
                text=f"Net Desorption (q_net):   {des_q_net:.4f} mmol/g  (Dry: {des_q_dry:.4f} | 100%: {des_q_100:.4f})"
            )
            self.lbl_recovery.config(text=f"Recovery Ratio:           {rec:.2f} %")
            self.lbl_details.config(
                text=f"Active Mass: {consts['mass_active_g']} g (Total: {m_tot:.4f}g, Loss: {w_pct:.1f}%) | Vm: {consts['Vm_exp']} mL/mol\nMode: {consts.get('k_mode', 'ads_first_point')} | Global k: {consts['k_factor']:.3e} A⁻¹ | S_baseline: {consts['s_baseline_a']:.4e} A"
            )

            # Auto-update active sample metadata if present
            if self.current_sample_id and self.current_sample_id in self.vault.logbook:
                s_data = self.vault.logbook[self.current_sample_id]
                s_data["mass_total_g"] = m_tot
                s_data["water_loss_pct"] = w_pct
                s_data["mass_active_g"] = consts["mass_active_g"]

            # Keep report preview in sync
            self.update_report_preview()
        except Exception:
            pass

    def on_save_analysis_to_sample(self):
        if not self.current_sample_id:
            messagebox.showwarning("No Sample", "No active sample selected in the Logbook.")
            return

        if not self.current_fpath:
            messagebox.showwarning("No File", "No .asc file currently loaded.")
            return

        fn = os.path.basename(self.current_fpath)

        # 1. Clone measurement file into the sample's local vault directory
        try:
            self.vault.add_characterization_file(
                self.current_sample_id,
                "mass_spec",
                self.current_fpath,
                description="Mass Spectrometry Measurement Run"
            )
        except Exception:
            pass

        # 2. Save full analysis results into SQLite Database & JSON Logbook
        rep_txt = self.report_text.get("1.0", tk.END).strip()
        self.vault.save_mass_spec_analysis(
            sample_id=self.current_sample_id,
            filename=fn,
            ranges=self.ranges_list,
            capacity_results=self.last_capacity_results,
            target_gas=self.integ_gas_var.get(),
            report_text=rep_txt
        )

        # 3. Save report text file inside the sample's directory
        self.vault.save_sample_report(self.current_sample_id, rep_txt, title="co2_report")

        messagebox.showinfo(
            "Analysis Saved", 
            f"File '{fn}' cloned into local sample vault.\n"
            f"CO₂ capacity results recorded into Database for '{self.current_sample_id}'."
        )
        if self.on_analysis_saved_callback:
            self.on_analysis_saved_callback(self.current_sample_id)

    # ==================== REPORT GENERATION ====================

    def update_report_preview(self):
        meta = self.vault.logbook.get(self.current_sample_id, {}) if self.current_sample_id else {}
        cap = self.last_capacity_results
        consts = cap.get("constants", {})
        avgs = cap.get("averages", {})
        rows = cap.get("rows", [])

        lines = [
            "=" * 78,
            f"   MASS SPECTROMETRY CO2 ADSORPTION / DESORPTION REPORT",
            "=" * 78,
            f"Sample ID:                {self.current_sample_id or '-'}",
            f"Material Name:            {meta.get('material_name', '-')}",
            f"Operator:                 {meta.get('operator', '-')}",
            f"Measurement Date:         {self.current_file_info.get('date', '-')}",
            f"Source File:              {os.path.basename(self.current_fpath) if self.current_fpath else '-'}",
            "-" * 78,
            "1. EXPERIMENTAL PARAMETERS:",
            f"  - Total Initial Mass:   {consts.get('mass_total_g', cap.get('mass_total_g', 0.0)):.4f} g",
            f"  - Water / Binder Loss:  {consts.get('water_loss_pct', cap.get('water_loss_pct', 0.0)):.1f} %",
            f"  - Dry Active Mass:      {consts.get('mass_active_g', cap.get('mass_active_g', 0.0)):.4f} g",
            f"  - Temperature:          {consts.get('temp_c', cap.get('temp_c', 24.0)):.1f} °C (Vm={consts.get('Vm_exp', cap.get('Vm_exp', 0.0))} mL/mol)",
            f"  - Total Flow Rate:      {consts.get('flow_total_ml_min', cap.get('flow_total_ml_min', 100.0)):.1f} mL/min",
            f"  - Feed Fraction C0:     {consts.get('c0', cap.get('c0', 0.15)):.2f}",
            f"  - Baseline S_baseline:  {consts.get('s_baseline_a', cap.get('s_baseline_a', 0.0)):.4e} A (k={consts.get('k_factor', cap.get('k_factor', 0.0)):.3e} A⁻¹)",
            f"  - Blank Ads Reference:  {consts.get('ref_ads_mmol_g', cap.get('ref_ads_mmol_g', 0.0)):.4f} mmol/g",
            f"  - Blank Des Reference:  {consts.get('ref_des_mmol_g', cap.get('ref_des_mmol_g', 0.0)):.4f} mmol/g",
            "-" * 78,
            "2. SUMMARY OF AVERAGE CO2 CAPACITIES (q):",
            f"  - Net Adsorption (avg): {avgs.get('ads', {}).get('q_net_mean', cap.get('adsorption', {}).get('q_net_mmol_g', 0.0)):.4f} mmol/g  (Dry: {avgs.get('ads', {}).get('q_dry_mean', cap.get('adsorption', {}).get('q_active_mmol_g', 0.0)):.4f} | 100%: {avgs.get('ads', {}).get('q_100_mean', cap.get('adsorption', {}).get('q_raw_mmol_g', 0.0)):.4f})",
            f"  - Net Desorption (avg): {avgs.get('des', {}).get('q_net_mean', cap.get('desorption', {}).get('q_net_mmol_g', 0.0)):.4f} mmol/g  (Dry: {avgs.get('des', {}).get('q_dry_mean', cap.get('desorption', {}).get('q_active_mmol_g', 0.0)):.4f} | 100%: {avgs.get('des', {}).get('q_100_mean', cap.get('desorption', {}).get('q_raw_mmol_g', 0.0)):.4f})",
            f"  - Desorption Recovery:  {avgs.get('recovery_pct', cap.get('recovery_pct', 0.0)):.2f} %",
            "-" * 88,
            "3. CYCLE-BY-CYCLE BREAKDOWN (EXCEL ANALYTICAL MODEL):",
            f"  {'Step':<8} {'Origin Area':<13} {'|A| (A·min)':<13} {'S_base (A)':<12} {'k (A⁻¹)':<11} {'nCO2 (mmol)':<12} {'q(100%)':<10} {'q(Dry)':<10}"
        ]

        if rows:
            for r in rows:
                lines.append(
                    f"  {r['type_name']:<8} {r['origin_area']:<13.4e} {r['abs_area']:<13.4e} {r['s_baseline']:<12.4e} {r['k_factor']:<11.3e} {r['n_mmol']:<12.4f} {r['q_100']:<10.4f} {r['q_dry']:<10.4f}"
                )
        else:
            lines.append("  (No cycle breakdown computed yet)")

        lines.extend([
            "-" * 78,
            "4. INTEGRATED SIMPSON ROI REGIONS:"
        ])

        for r in self.ranges_list:
            lines.append(
                f"  [{r.get('type_name')}] t={r['start_min']:.2f}-{r['end_min']:.2f} min (Δt={r.get('duration', 0.0):.2f}) | Area={r.get('calculated_area', 0.0):.4e} A·min | Base={r.get('baseline', 'straight_line')} | FWHM={r.get('fwhm_val', 0.0):.3f}"
            )

        lines.append("=" * 78)
        txt = "\n".join(lines)
        self.report_text.delete("1.0", tk.END)
        self.report_text.insert("1.0", txt)

    def on_copy_report(self):
        txt = self.report_text.get("1.0", tk.END).strip()
        self.clipboard_clear()
        self.clipboard_append(txt)
        messagebox.showinfo("Copied", "Report copied to clipboard.")

    def on_save_report_file(self):
        if not self.current_sample_id:
            messagebox.showwarning("No Sample", "Select a sample in the Logbook.")
            return
        txt = self.report_text.get("1.0", tk.END).strip()
        p = self.vault.save_sample_report(self.current_sample_id, txt)
        messagebox.showinfo("Saved", f"Report saved to:\n{p}")

    def export_plot_image(self):
        fpath = filedialog.asksaveasfilename(
            title="Export Plot Image",
            defaultextension=".png",
            filetypes=[("PNG Image (300 DPI)", "*.png"), ("PDF Document", "*.pdf"), ("SVG Vector Image", "*.svg")]
        )
        if fpath:
            self.fig.savefig(fpath, dpi=300, bbox_inches="tight")
            messagebox.showinfo("Export Successful", f"Plot image saved to:\n{fpath}")

    def select_all_gases(self):
        for v in self.gas_vars.values():
            v.set(True)
        self.update_plot(preserve_zoom=True)

    def clear_all_gases(self):
        for v in self.gas_vars.values():
            v.set(False)
        self.update_plot(preserve_zoom=True)

    def on_xaxis_change(self):
        self.update_plot(preserve_zoom=False)
