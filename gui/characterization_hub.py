import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from core.sample_vault import CHARACTERIZATION_TYPES
from core.tga_engine import load_tga_data, plot_tga_dual_panel

class CharacterizationHubView(ttk.Frame):
    """
    Module 2: Multi-Characterization Hub.
    Allows managing different analytical techniques for the selected sample:
    Mass Spectrometry (.asc), XRD, BET, Raman, TGA, and attached documents.
    """
    def __init__(self, parent, vault, on_open_mass_spec_callback=None):
        super().__init__(parent, padding=8)
        self.vault = vault
        self.on_open_mass_spec_callback = on_open_mass_spec_callback
        self.current_sample_id = None

        self.create_widgets()

    def create_widgets(self):
        # 1. Sample Info Banner
        self.banner_frame = tk.Frame(self, bg="#e9f5ff", bd=1, relief="solid", padx=12, pady=10)
        self.banner_frame.pack(fill=tk.X, pady=(0, 10))

        self.lbl_banner_title = tk.Label(
            self.banner_frame, 
            text="🏷️ Active Sample: [ None Selected ]", 
            font=("Segoe UI", 12, "bold"), 
            bg="#e9f5ff", 
            fg="#1d3557"
        )
        self.lbl_banner_title.pack(anchor="w")

        self.lbl_banner_details = tk.Label(
            self.banner_frame, 
            text="Select a sample in the 'Logbook' tab to inspect and attach characterization files.", 
            font=("Segoe UI", 9), 
            bg="#e9f5ff", 
            fg="#457b9d"
        )
        self.lbl_banner_details.pack(anchor="w", pady=(2, 0))

        # 2. Characterization Techniques Notebook
        self.tech_notebook = ttk.Notebook(self)
        self.tech_notebook.pack(fill=tk.BOTH, expand=True)

        # Tab: Mass Spectrometry / Adsorption
        self.tab_mass = ttk.Frame(self.tech_notebook, padding=8)
        self.tech_notebook.add(self.tab_mass, text=" 🧪 Mass Spectrometry (.asc) ")
        self._build_mass_spec_tab(self.tab_mass)

        # Tab: XRD
        self.tab_xrd = ttk.Frame(self.tech_notebook, padding=8)
        self.tech_notebook.add(self.tab_xrd, text=" 🔬 X-Ray Diffraction (XRD) ")
        self._build_generic_tab(self.tab_xrd, "xrd", "XRD Pattern Files (.raw, .xy, .dat, .csv):", [("XRD Files", "*.raw;*.xy;*.dat;*.csv;*.txt"), ("All Files", "*.*")])

        # Tab: BET Surface Area
        self.tab_bet = ttk.Frame(self.tech_notebook, padding=8)
        self.tech_notebook.add(self.tab_bet, text=" 📐 N₂ Physisorption / BET ")
        self._build_bet_tab(self.tab_bet)

        # Tab: TGA
        self.tab_tga = ttk.Frame(self.tech_notebook, padding=8)
        self.tech_notebook.add(self.tab_tga, text=" 🔥 TGA Thermal Analysis ")
        self._build_tga_tab(self.tab_tga)

        # Tab: SEM / TEM Microscopy
        self.tab_sem_tem = ttk.Frame(self.tech_notebook, padding=8)
        self.tech_notebook.add(self.tab_sem_tem, text=" 🔍 SEM / TEM Microscopy ")
        self._build_sem_tem_tab(self.tab_sem_tem)

        # Tab: Rheological Properties
        self.tab_rheology = ttk.Frame(self.tech_notebook, padding=8)
        self.tech_notebook.add(self.tab_rheology, text=" 🌊 Rheological Properties ")
        self._build_rheology_tab(self.tab_rheology)

        # Tab: Documents & Attachments
        self.tab_docs = ttk.Frame(self.tech_notebook, padding=8)
        self.tech_notebook.add(self.tab_docs, text=" 📁 Documents & Reports ")
        self._build_generic_tab(self.tab_docs, "documents", "Supplementary Files (PDF, Images, Reports):", [("Documents", "*.pdf;*.png;*.jpg;*.xlsx;*.docx;*.txt"), ("All Files", "*.*")])

    def set_sample(self, sample_id):
        self.current_sample_id = sample_id
        if not sample_id or sample_id not in self.vault.logbook:
            self.lbl_banner_title.config(text="🏷️ Active Sample: [ None Selected ]")
            self.lbl_banner_details.config(text="Select a sample in the 'Logbook' tab to inspect and attach characterization files.")
            self.refresh_all_tabs()
            return

        data = self.vault.logbook[sample_id]
        mat = data.get("material_name", "-")
        mass_tot = float(data.get("mass_total_g", 0.0))
        water = float(data.get("water_loss_pct", 0.0))
        mass_act = mass_tot * (1.0 - (water / 100.0))
        op = data.get("operator", "-")
        date_str = data.get("date", "-")

        self.lbl_banner_title.config(text=f"🏷️ Sample: {sample_id} — {mat}")
        self.lbl_banner_details.config(
            text=f"Date: {date_str}  |  Operator: {op}  |  Total Mass: {mass_tot:.4f} g  |  Water Loss: {water:.1f}%  |  Active Mass: {mass_act:.4f} g"
        )
        self.refresh_all_tabs()

    def refresh_all_tabs(self):
        self._refresh_mass_table()
        self._refresh_generic_table("xrd")
        self._refresh_bet_tab()
        self._refresh_tga_tab()
        self._refresh_sem_tem_tab()
        self._refresh_rheology_tab()
        self._refresh_generic_table("documents")

    # ==================== TAB: MASS SPECTROMETRY ====================

    def _build_mass_spec_tab(self, parent):
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill=tk.X, pady=(0, 8))

        ttk.Button(toolbar, text="➕ Attach .asc File", command=self.on_attach_asc_file).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="🗑️ Delete File", command=lambda: self.on_delete_file("mass_spec")).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="📂 View in Folder", command=lambda: self.on_open_tech_folder("mass_spec")).pack(side=tk.LEFT, padx=3)

        self.btn_open_tool = ttk.Button(
            toolbar, 
            text="🚀 OPEN IN MASS SPECTROMETRY TOOL", 
            command=self.on_open_mass_spec_tool
        )
        self.btn_open_tool.pack(side=tk.RIGHT, padx=4)

        # Table of Mass Spec Files
        cols = ("fn", "uploaded", "size", "status", "q_ads", "q_des", "rec")
        self.tree_mass = ttk.Treeview(parent, columns=cols, show="headings", selectmode="browse", height=8)

        self.tree_mass.heading("fn", text="Measurement File (.asc)")
        self.tree_mass.heading("uploaded", text="Upload Date")
        self.tree_mass.heading("size", text="Size")
        self.tree_mass.heading("status", text="Status")
        self.tree_mass.heading("q_ads", text="q Ads (mmol/g)")
        self.tree_mass.heading("q_des", text="q Des (mmol/g)")
        self.tree_mass.heading("rec", text="Recovery %")

        self.tree_mass.column("fn", width=260, anchor="w")
        self.tree_mass.column("uploaded", width=130, anchor="center")
        self.tree_mass.column("size", width=80, anchor="e")
        self.tree_mass.column("status", width=95, anchor="center")
        self.tree_mass.column("q_ads", width=110, anchor="e")
        self.tree_mass.column("q_des", width=110, anchor="e")
        self.tree_mass.column("rec", width=110, anchor="e")

        self.tree_mass.pack(fill=tk.BOTH, expand=True)
        self.tree_mass.bind("<Double-1>", lambda e: self.on_open_mass_spec_tool())

        # Description / Info box
        hint_lbl = ttk.Label(
            parent, 
            text="💡 Tip: Select an .asc file and double-click or click 'OPEN IN MASS SPECTROMETRY TOOL' to determine regions, compute capacities, and generate reports.",
            font=("Segoe UI", 9, "italic")
        )
        hint_lbl.pack(anchor="w", pady=(8, 0))

    def _refresh_mass_table(self):
        for item in self.tree_mass.get_children():
            self.tree_mass.delete(item)

        if not self.current_sample_id or self.current_sample_id not in self.vault.logbook:
            return

        data = self.vault.logbook[self.current_sample_id]
        tech_data = data.get("characterizations", {}).get("mass_spec", {})
        file_list = tech_data.get("files", [])

        # Fallback to legacy files if empty
        if not file_list and "files" in data:
            file_list = [f for f in data.get("files", []) if f.get("filename", "").lower().endswith(".asc")]

        for f in file_list:
            fn = f.get("filename", "-")
            sz = f.get("size_bytes", 0) / 1024.0
            status = f.get("status", "Pending")
            q_ads = f.get("q_net_ads")
            q_des = f.get("q_net_des")
            rec = f.get("recovery_pct")

            # Auto-check if an analysis exists on disk
            if status != "Analyzed" and fn != "-":
                saved_an = self.vault.load_mass_spec_analysis(self.current_sample_id, fn)
                if saved_an:
                    status = "Analyzed"
                    cap = saved_an.get("capacity", {})
                    q_ads = cap.get("adsorption", {}).get("q_net_mmol_g")
                    q_des = cap.get("desorption", {}).get("q_net_mmol_g")
                    rec = cap.get("recovery_pct")
                    f["status"] = "Analyzed"
                    f["q_net_ads"] = q_ads
                    f["q_net_des"] = q_des
                    f["recovery_pct"] = rec

            self.tree_mass.insert("", tk.END, values=(
                fn,
                f.get("uploaded_at", "-"),
                f"{sz:.1f} KB",
                status,
                f"{q_ads:.4f}" if q_ads is not None else "-",
                f"{q_des:.4f}" if q_des is not None else "-",
                f"{rec:.2f}%" if rec is not None else "-"
            ))

    def on_attach_asc_file(self):
        if not self.current_sample_id:
            messagebox.showinfo("Select Sample", "Please select a sample in the logbook first.")
            return

        fpath = filedialog.askopenfilename(
            title="Select Mass Spectrometry Data File (.asc)",
            filetypes=[("ASC Files", "*.asc"), ("All Files", "*.*")]
        )
        if fpath:
            try:
                self.vault.add_characterization_file(self.current_sample_id, "mass_spec", fpath)
                self._refresh_mass_table()
                messagebox.showinfo("File Attached", f"File '{os.path.basename(fpath)}' attached to sample {self.current_sample_id}.")
            except Exception as e:
                messagebox.showerror("Error Attaching File", f"Could not attach file:\n{e}")

    def on_open_mass_spec_tool(self):
        if not self.current_sample_id:
            messagebox.showinfo("Select Sample", "Please select a sample in the logbook first.")
            return

        sel = self.tree_mass.selection()
        selected_fn = self.tree_mass.item(sel[0], "values")[0] if sel else None

        # If no file is selected but there is at least one file, take the first one
        if not selected_fn:
            children = self.tree_mass.get_children()
            if children:
                selected_fn = self.tree_mass.item(children[0], "values")[0]

        if not selected_fn:
            messagebox.showinfo("No File Selected", "Attach or select an .asc file to open in the Mass Spec Tool.")
            return

        asc_path = self.vault.get_characterization_file_path(self.current_sample_id, "mass_spec", selected_fn)
        if not asc_path or not os.path.exists(asc_path):
            messagebox.showerror("Error", f"Physical file not found:\n{asc_path}")
            return

        if self.on_open_mass_spec_callback:
            self.on_open_mass_spec_callback(self.current_sample_id, asc_path)

    # ==================== GENERIC TABS: XRD, RAMAN, DOCUMENTS ====================

    def _build_generic_tab(self, parent, tech_key, header_title, filetypes):
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill=tk.X, pady=(0, 8))

        ttk.Button(toolbar, text="➕ Attach File", command=lambda: self.on_attach_generic_file(tech_key, filetypes)).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="🗑️ Delete File", command=lambda: self.on_delete_file(tech_key)).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="📂 Open File", command=lambda: self.on_open_selected_file(tech_key)).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="📁 Open Folder", command=lambda: self.on_open_tech_folder(tech_key)).pack(side=tk.LEFT, padx=3)

        cols = ("fn", "uploaded", "size", "desc")
        tree = ttk.Treeview(parent, columns=cols, show="headings", selectmode="browse", height=7)
        tree.heading("fn", text="Filename")
        tree.heading("uploaded", text="Upload Date")
        tree.heading("size", text="Size")
        tree.heading("desc", text="Description / Notes")

        tree.column("fn", width=250, anchor="w")
        tree.column("uploaded", width=140, anchor="center")
        tree.column("size", width=90, anchor="e")
        tree.column("desc", width=250, anchor="w")

        tree.pack(fill=tk.BOTH, expand=True)
        setattr(self, f"tree_{tech_key}", tree)

        # Notes block
        notes_frame = ttk.LabelFrame(parent, text=" Key Observations & Structural Notes ", padding=6)
        notes_frame.pack(fill=tk.X, pady=(8, 0))

        text_widget = tk.Text(notes_frame, height=3, font=("Segoe UI", 9))
        text_widget.pack(fill=tk.X, expand=True, side=tk.LEFT)
        btn_save_notes = ttk.Button(notes_frame, text="💾 Save\nNotes", command=lambda: self.on_save_tech_notes(tech_key))
        btn_save_notes.pack(side=tk.RIGHT, padx=(6, 0))
        setattr(self, f"notes_{tech_key}", text_widget)

    def _refresh_generic_table(self, tech_key):
        tree = getattr(self, f"tree_{tech_key}", None)
        notes_widget = getattr(self, f"notes_{tech_key}", None)
        if not tree:
            return

        for item in tree.get_children():
            tree.delete(item)

        if not self.current_sample_id or self.current_sample_id not in self.vault.logbook:
            if notes_widget:
                notes_widget.delete("1.0", tk.END)
            return

        data = self.vault.logbook[self.current_sample_id]
        tech_data = data.get("characterizations", {}).get(tech_key, {})
        for f in tech_data.get("files", []):
            sz = f.get("size_bytes", 0) / 1024.0
            tree.insert("", tk.END, values=(
                f.get("filename", "-"),
                f.get("uploaded_at", "-"),
                f"{sz:.1f} KB",
                f.get("description", "-")
            ))

        if notes_widget:
            notes_widget.delete("1.0", tk.END)
            notes_widget.insert("1.0", tech_data.get("notes", ""))

    def on_attach_generic_file(self, tech_key, filetypes):
        if not self.current_sample_id:
            messagebox.showinfo("Select Sample", "Please select a sample in the logbook first.")
            return

        fpath = filedialog.askopenfilename(
            title=f"Select {CHARACTERIZATION_TYPES.get(tech_key, {}).get('name', tech_key)} File",
            filetypes=filetypes
        )
        if fpath:
            try:
                self.vault.add_characterization_file(self.current_sample_id, tech_key, fpath)
                self._refresh_generic_table(tech_key)
                messagebox.showinfo("File Attached", f"File '{os.path.basename(fpath)}' saved.")
            except Exception as e:
                messagebox.showerror("Error", f"Could not attach file:\n{e}")

    def on_save_tech_notes(self, tech_key):
        if not self.current_sample_id:
            return
        notes_widget = getattr(self, f"notes_{tech_key}", None)
        if not notes_widget:
            return
        txt = notes_widget.get("1.0", tk.END).strip()
        data = self.vault.logbook[self.current_sample_id]
        data.setdefault("characterizations", {}).setdefault(tech_key, {})["notes"] = txt
        self.vault.save_logbook()
        messagebox.showinfo("Notes Saved", f"Notes updated for {CHARACTERIZATION_TYPES.get(tech_key, {}).get('name', tech_key)}.")

    def on_open_selected_file(self, tech_key):
        tree = getattr(self, f"tree_{tech_key}", None)
        if not tree:
            return
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Select File", "Please select a file from the table.")
            return
        fn = tree.item(sel[0], "values")[0]
        fpath = self.vault.get_characterization_file_path(self.current_sample_id, tech_key, fn)
        if fpath and os.path.exists(fpath):
            os.startfile(fpath)
        else:
            messagebox.showwarning("Error", f"File not found:\n{fpath}")

    def on_delete_file(self, tech_key):
        tree = self.tree_mass if tech_key == "mass_spec" else getattr(self, f"tree_{tech_key}", None)
        if not tree:
            return
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Select File", "Please select a file to delete.")
            return
        fn = tree.item(sel[0], "values")[0]
        if messagebox.askyesno("Confirm Deletion", f"Delete '{fn}' from sample {self.current_sample_id}?"):
            self.vault.delete_characterization_file(self.current_sample_id, tech_key, fn)
            if tech_key == "mass_spec":
                self._refresh_mass_table()
            else:
                self._refresh_generic_table(tech_key)

    def on_open_tech_folder(self, tech_key):
        if not self.current_sample_id:
            return
        folder = self.vault.get_technique_dir(self.current_sample_id, tech_key)
        if os.path.exists(folder):
            os.startfile(folder)

    # ==================== TAB: BET SURFACE AREA ====================

    def _build_bet_tab(self, parent):
        top_frame = ttk.Frame(parent)
        top_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Button(top_frame, text="➕ Attach BET Isotherm (.xls, .csv)", command=lambda: self.on_attach_generic_file("bet", [("BET Data", "*.xls;*.xlsx;*.csv;*.txt")])).pack(side=tk.LEFT, padx=3)
        ttk.Button(top_frame, text="🗑️ Delete File", command=lambda: self.on_delete_file("bet")).pack(side=tk.LEFT, padx=3)
        ttk.Button(top_frame, text="📂 View in Folder", command=lambda: self.on_open_tech_folder("bet")).pack(side=tk.LEFT, padx=3)

        # Table of BET files
        cols = ("fn", "uploaded", "size")
        self.tree_bet = ttk.Treeview(parent, columns=cols, show="headings", selectmode="browse", height=5)
        self.tree_bet.heading("fn", text="BET Isotherm File")
        self.tree_bet.heading("uploaded", text="Upload Date")
        self.tree_bet.heading("size", text="Size")
        self.tree_bet.column("fn", width=280, anchor="w")
        self.tree_bet.column("uploaded", width=140, anchor="center")
        self.tree_bet.column("size", width=100, anchor="e")
        self.tree_bet.pack(fill=tk.X, pady=(0, 10))

        # BET Key Parameters Box
        param_frame = ttk.LabelFrame(parent, text=" BET Textural Properties & Porosity ", padding=10)
        param_frame.pack(fill=tk.X)

        p_grid = ttk.Frame(param_frame)
        p_grid.pack(fill=tk.X)

        ttk.Label(p_grid, text="BET Specific Surface Area (m²/g):").grid(row=0, column=0, sticky="w", pady=4)
        self.bet_area_var = tk.DoubleVar(value=0.0)
        ttk.Spinbox(p_grid, from_=0.0, to=5000.0, increment=5.0, textvariable=self.bet_area_var, width=18).grid(row=0, column=1, sticky="w", padx=8, pady=4)

        ttk.Label(p_grid, text="Total Pore Volume (cm³/g):").grid(row=1, column=0, sticky="w", pady=4)
        self.bet_vol_var = tk.DoubleVar(value=0.0)
        ttk.Spinbox(p_grid, from_=0.0, to=10.0, increment=0.01, textvariable=self.bet_vol_var, width=18).grid(row=1, column=1, sticky="w", padx=8, pady=4)

        ttk.Label(p_grid, text="Average Pore Diameter (nm):").grid(row=2, column=0, sticky="w", pady=4)
        self.bet_diam_var = tk.DoubleVar(value=0.0)
        ttk.Spinbox(p_grid, from_=0.0, to=100.0, increment=0.1, textvariable=self.bet_diam_var, width=18).grid(row=2, column=1, sticky="w", padx=8, pady=4)

        btn_save_bet = ttk.Button(param_frame, text="💾 Save BET Parameters", command=self.on_save_bet_params)
        btn_save_bet.pack(anchor="e", pady=(8, 0))

    def _refresh_bet_tab(self):
        for item in self.tree_bet.get_children():
            self.tree_bet.delete(item)

        if not self.current_sample_id or self.current_sample_id not in self.vault.logbook:
            self.bet_area_var.set(0.0)
            self.bet_vol_var.set(0.0)
            self.bet_diam_var.set(0.0)
            return

        data = self.vault.logbook[self.current_sample_id]
        tech_data = data.get("characterizations", {}).get("bet", {})
        for f in tech_data.get("files", []):
            sz = f.get("size_bytes", 0) / 1024.0
            self.tree_bet.insert("", tk.END, values=(
                f.get("filename", "-"),
                f.get("uploaded_at", "-"),
                f"{sz:.1f} KB"
            ))

        self.bet_area_var.set(float(tech_data.get("surface_area_m2_g", 0.0)))
        self.bet_vol_var.set(float(tech_data.get("pore_volume_cm3_g", 0.0)))
        self.bet_diam_var.set(float(tech_data.get("pore_diameter_nm", 0.0)))

    def on_save_bet_params(self):
        if not self.current_sample_id:
            return
        data = self.vault.logbook[self.current_sample_id]
        bet_dict = data.setdefault("characterizations", {}).setdefault("bet", {})
        bet_dict["surface_area_m2_g"] = float(self.bet_area_var.get())
        bet_dict["pore_volume_cm3_g"] = float(self.bet_vol_var.get())
        bet_dict["pore_diameter_nm"] = float(self.bet_diam_var.get())
        self.vault.save_logbook()
        messagebox.showinfo("Saved", f"BET textural parameters saved for {self.current_sample_id}.")

    # ==================== TAB: TGA (THERMOGRAVIMETRIC ANALYSIS) ====================

    def _build_tga_tab(self, parent):
        # Master horizontal PanedWindow: Left = Files & Parameters, Right = Publication Plot Canvas
        tga_paned = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
        tga_paned.pack(fill=tk.BOTH, expand=True)

        left_side = ttk.Frame(tga_paned, width=440)
        right_side = ttk.Frame(tga_paned)
        tga_paned.add(left_side, weight=0)
        tga_paned.add(right_side, weight=1)

        # Left: Toolbar
        toolbar = ttk.Frame(left_side)
        toolbar.pack(fill=tk.X, pady=(0, 6))

        filetypes = [("TGA Files", "*.xlsx;*.xls;*.csv;*.txt"), ("All Files", "*.*")]
        ttk.Button(toolbar, text="➕ Attach TGA File", command=lambda: self.on_attach_tga_file(filetypes)).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="🗑️ Delete File", command=lambda: self.on_delete_file("tga")).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="📁 Folder", command=lambda: self.on_open_tech_folder("tga")).pack(side=tk.LEFT, padx=2)

        # Table of files
        cols = ("fn", "size")
        self.tree_tga = ttk.Treeview(left_side, columns=cols, show="headings", selectmode="browse", height=5)
        self.tree_tga.heading("fn", text="TGA Data File (.xlsx / .csv)")
        self.tree_tga.heading("size", text="Size")
        self.tree_tga.column("fn", width=260, anchor="w")
        self.tree_tga.column("size", width=70, anchor="e")
        self.tree_tga.pack(fill=tk.X, pady=(0, 6))
        self.tree_tga.bind("<<TreeviewSelect>>", self.on_tga_file_selected)

        # Automated Plot & Analysis Actions
        act_row = ttk.Frame(left_side)
        act_row.pack(fill=tk.X, pady=(0, 6))
        ttk.Button(act_row, text="📊 Plot Selected File", command=self.on_plot_current_tga).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        ttk.Button(act_row, text="💾 Export Plot Image...", command=self.on_export_tga_plot).pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=2)

        # Parameters Frame (Auto-populated from Excel)
        param_frame = ttk.LabelFrame(left_side, text=" TGA Key Properties (Auto-Extracted & Manual) ", padding=8)
        param_frame.pack(fill=tk.BOTH, expand=True)

        p_grid = ttk.Frame(param_frame)
        p_grid.pack(fill=tk.X)

        ttk.Label(p_grid, text="Initial Weight (%):").grid(row=0, column=0, sticky="w", pady=3)
        self.tga_init_weight_var = tk.DoubleVar(value=100.0)
        ttk.Spinbox(p_grid, from_=0.0, to=200.0, increment=0.1, textvariable=self.tga_init_weight_var, width=12).grid(row=0, column=1, sticky="w", padx=4, pady=3)

        ttk.Label(p_grid, text="Residual Mass (%):").grid(row=1, column=0, sticky="w", pady=3)
        self.tga_residual_var = tk.DoubleVar(value=0.0)
        ttk.Spinbox(p_grid, from_=0.0, to=100.0, increment=0.1, textvariable=self.tga_residual_var, width=12).grid(row=1, column=1, sticky="w", padx=4, pady=3)

        ttk.Label(p_grid, text="Net Weight Loss ΔW (%):", font=("Segoe UI", 9, "bold")).grid(row=2, column=0, sticky="w", pady=3)
        self.tga_delta_w_var = tk.DoubleVar(value=0.0)
        ttk.Spinbox(p_grid, from_=0.0, to=100.0, increment=0.1, textvariable=self.tga_delta_w_var, width=12).grid(row=2, column=1, sticky="w", padx=4, pady=3)

        ttk.Label(p_grid, text="DTG Peak Temp T_max (°C):").grid(row=3, column=0, sticky="w", pady=3)
        self.tga_peak_var = tk.DoubleVar(value=0.0)
        ttk.Spinbox(p_grid, from_=0.0, to=1200.0, increment=1.0, textvariable=self.tga_peak_var, width=12).grid(row=3, column=1, sticky="w", padx=4, pady=3)

        ttk.Label(p_grid, text="Onset Temp (°C):").grid(row=4, column=0, sticky="w", pady=3)
        self.tga_onset_var = tk.DoubleVar(value=0.0)
        ttk.Spinbox(p_grid, from_=0.0, to=1200.0, increment=5.0, textvariable=self.tga_onset_var, width=12).grid(row=4, column=1, sticky="w", padx=4, pady=3)

        ttk.Label(p_grid, text="Purge Atmosphere:").grid(row=5, column=0, sticky="w", pady=3)
        self.tga_atmosphere_var = tk.StringVar(value="N2")
        ttk.Combobox(p_grid, values=["N2", "Air", "O2", "Ar", "CO2"], textvariable=self.tga_atmosphere_var, width=10, state="readonly").grid(row=5, column=1, sticky="w", padx=4, pady=3)

        # Plot Title Entry
        ttk.Label(p_grid, text="Graph Title:").grid(row=6, column=0, sticky="w", pady=3)
        self.tga_plot_title_var = tk.StringVar(value="Zeo Batch 6 (i)")
        ttk.Entry(p_grid, textvariable=self.tga_plot_title_var, width=18).grid(row=6, column=1, sticky="w", padx=4, pady=3)

        btn_save_tga = ttk.Button(param_frame, text="💾 Save TGA Parameters to Sample", command=self.on_save_tga_params)
        btn_save_tga.pack(fill=tk.X, pady=(10, 0))

        # Right: Matplotlib Dual-Panel Canvas
        right_header = ttk.Frame(right_side)
        right_header.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(right_header, text="📈 Dual-Panel TGA / DTG Publication Graph (OriginPro Style)", font=("Segoe UI", 10, "bold"), foreground="#1d3557").pack(side=tk.LEFT)

        self.tga_fig, _ = plt.subplots(figsize=(5.5, 7.5), dpi=100)
        self.tga_canvas = FigureCanvasTkAgg(self.tga_fig, master=right_side)
        self.tga_canvas.draw()

        tga_toolbar_f = ttk.Frame(right_side)
        tga_toolbar_f.pack(side=tk.TOP, fill=tk.X)
        self.tga_toolbar = NavigationToolbar2Tk(self.tga_canvas, tga_toolbar_f)
        self.tga_toolbar.update()

        self.tga_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self.current_tga_df = None
        self.current_tga_meta = {}

    def on_attach_tga_file(self, filetypes):
        if not self.current_sample_id:
            messagebox.showinfo("Select Sample", "Please select a sample in the logbook first.")
            return

        fpath = filedialog.askopenfilename(
            title="Select TGA Raw Data File (Excel / CSV)",
            filetypes=filetypes
        )
        if fpath:
            try:
                self.vault.add_characterization_file(self.current_sample_id, "tga", fpath)
                self._refresh_tga_tab()
                # Automatically plot newly attached file
                self.load_and_display_tga(fpath)
            except Exception as e:
                messagebox.showerror("Error Attaching File", f"Could not attach TGA file:\n{e}")

    def on_tga_file_selected(self, event=None):
        sel = self.tree_tga.selection()
        if not sel or not self.current_sample_id:
            return
        fn = self.tree_tga.item(sel[0], "values")[0]
        fpath = self.vault.get_characterization_file_path(self.current_sample_id, "tga", fn)
        if fpath and os.path.exists(fpath):
            self.load_and_display_tga(fpath)

    def on_plot_current_tga(self):
        sel = self.tree_tga.selection()
        fn = self.tree_tga.item(sel[0], "values")[0] if sel else None
        if not fn:
            children = self.tree_tga.get_children()
            if children:
                fn = self.tree_tga.item(children[0], "values")[0]
        if fn and self.current_sample_id:
            fpath = self.vault.get_characterization_file_path(self.current_sample_id, "tga", fn)
            if fpath and os.path.exists(fpath):
                self.load_and_display_tga(fpath)
        elif self.current_tga_df is not None:
            title = self.tga_plot_title_var.get().strip() or "TGA / DTG Analysis"
            plot_tga_dual_panel(self.current_tga_df, self.current_tga_meta, title=title, fig=self.tga_fig)
            self.tga_canvas.draw()

    def load_and_display_tga(self, fpath):
        try:
            df, meta = load_tga_data(fpath)
            self.current_tga_df = df
            self.current_tga_meta = meta

            # Auto-populate UI Spinboxes from data
            self.tga_init_weight_var.set(meta["initial_weight_pct"])
            self.tga_residual_var.set(meta["residual_weight_pct"])
            self.tga_delta_w_var.set(meta["delta_weight_pct"])
            self.tga_peak_var.set(meta["peak_temp_c"])
            if self.tga_onset_var.get() == 0.0:
                self.tga_onset_var.set(round(meta["peak_temp_c"] * 0.75, 1))

            # Suggest graph title from active sample or file name
            fn_clean = os.path.splitext(os.path.basename(fpath))[0]
            if self.current_sample_id and self.current_sample_id in self.vault.logbook:
                mat = self.vault.logbook[self.current_sample_id].get("material_name", "")
                self.tga_plot_title_var.set(mat if mat and mat != "-" else fn_clean)
            else:
                self.tga_plot_title_var.set(fn_clean)

            # Render dual panel plot
            title = self.tga_plot_title_var.get().strip()
            plot_tga_dual_panel(df, meta, title=title, fig=self.tga_fig)
            self.tga_canvas.draw()
        except Exception as e:
            messagebox.showerror("TGA Load Error", f"Could not process TGA file:\n{e}")

    def on_export_tga_plot(self):
        if self.current_tga_df is None:
            messagebox.showinfo("No Plot", "Load or plot a TGA data file first.")
            return

        out_path = filedialog.asksaveasfilename(
            title="Export Publication TGA Graph",
            defaultextension=".png",
            filetypes=[("PNG Image (High-Res)", "*.png"), ("PDF Document (Vector)", "*.pdf"), ("SVG Vector", "*.svg"), ("All Files", "*.*")]
        )
        if out_path:
            try:
                title = self.tga_plot_title_var.get().strip() or "TGA / DTG Analysis"
                plot_tga_dual_panel(self.current_tga_df, self.current_tga_meta, title=title, fig=self.tga_fig)
                self.tga_fig.savefig(out_path, dpi=300, bbox_inches="tight")
                messagebox.showinfo("Export Successful", f"High-resolution TGA publication plot saved to:\n{out_path}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Could not export plot:\n{e}")

    def _refresh_tga_tab(self):
        for item in self.tree_tga.get_children():
            self.tree_tga.delete(item)

        if not self.current_sample_id or self.current_sample_id not in self.vault.logbook:
            self.tga_onset_var.set(0.0)
            self.tga_peak_var.set(0.0)
            self.tga_init_weight_var.set(100.0)
            self.tga_residual_var.set(0.0)
            self.tga_delta_w_var.set(0.0)
            self.tga_atmosphere_var.set("N2")
            return

        data = self.vault.logbook[self.current_sample_id]
        tech_data = data.get("characterizations", {}).get("tga", {})
        files = tech_data.get("files", [])
        for f in files:
            sz = f.get("size_bytes", 0) / 1024.0
            self.tree_tga.insert("", tk.END, values=(
                f.get("filename", "-"),
                f"{sz:.1f} KB"
            ))

        self.tga_onset_var.set(float(tech_data.get("onset_temp_c", 0.0)))
        self.tga_peak_var.set(float(tech_data.get("peak_temp_c", 0.0)))
        self.tga_init_weight_var.set(float(tech_data.get("initial_weight_pct", 100.0)))
        self.tga_residual_var.set(float(tech_data.get("residual_mass_pct", 0.0)))
        self.tga_delta_w_var.set(float(tech_data.get("delta_weight_pct", 0.0)))
        self.tga_atmosphere_var.set(tech_data.get("atmosphere", "N2"))

        # If files exist, auto-select and render the first file
        children = self.tree_tga.get_children()
        if children:
            self.tree_tga.selection_set(children[0])
            fn = self.tree_tga.item(children[0], "values")[0]
            fpath = self.vault.get_characterization_file_path(self.current_sample_id, "tga", fn)
            if fpath and os.path.exists(fpath):
                self.load_and_display_tga(fpath)

    def on_save_tga_params(self):
        if not self.current_sample_id:
            return
        data = self.vault.logbook[self.current_sample_id]
        tga_dict = data.setdefault("characterizations", {}).setdefault("tga", {})
        tga_dict["onset_temp_c"] = float(self.tga_onset_var.get())
        tga_dict["peak_temp_c"] = float(self.tga_peak_var.get())
        tga_dict["initial_weight_pct"] = float(self.tga_init_weight_var.get())
        tga_dict["residual_mass_pct"] = float(self.tga_residual_var.get())
        tga_dict["delta_weight_pct"] = float(self.tga_delta_w_var.get())
        tga_dict["atmosphere"] = self.tga_atmosphere_var.get()
        self.vault.save_logbook()
        messagebox.showinfo("Saved", f"TGA thermal properties saved for {self.current_sample_id}.")

    # ==================== TAB: SEM / TEM ELECTRON MICROSCOPY ====================

    def _build_sem_tem_tab(self, parent):
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill=tk.X, pady=(0, 8))

        filetypes = [("Microscopy Files", "*.tif;*.tiff;*.png;*.jpg;*.dm3;*.dm4;*.txt;*.csv"), ("All Files", "*.*")]
        ttk.Button(toolbar, text="➕ Attach Micrograph / EDX", command=lambda: self.on_attach_generic_file("sem_tem", filetypes)).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="🗑️ Delete File", command=lambda: self.on_delete_file("sem_tem")).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="🔍 View Image / Open", command=lambda: self.on_open_selected_file("sem_tem")).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="📁 Open Folder", command=lambda: self.on_open_tech_folder("sem_tem")).pack(side=tk.LEFT, padx=3)

        cols = ("fn", "uploaded", "size")
        self.tree_sem = ttk.Treeview(parent, columns=cols, show="headings", selectmode="browse", height=5)
        self.tree_sem.heading("fn", text="Microscopy Micrograph / EDX File")
        self.tree_sem.heading("uploaded", text="Upload Date")
        self.tree_sem.heading("size", text="Size")
        self.tree_sem.column("fn", width=280, anchor="w")
        self.tree_sem.column("uploaded", width=140, anchor="center")
        self.tree_sem.column("size", width=100, anchor="e")
        self.tree_sem.pack(fill=tk.X, pady=(0, 10))

        # SEM/TEM Parameters Frame
        param_frame = ttk.LabelFrame(parent, text=" Morphological & Nanostructure Analysis (SEM / TEM) ", padding=10)
        param_frame.pack(fill=tk.X)

        p_grid = ttk.Frame(param_frame)
        p_grid.pack(fill=tk.X)

        ttk.Label(p_grid, text="Primary Particle Size (nm):").grid(row=0, column=0, sticky="w", pady=4)
        self.sem_particle_size_var = tk.DoubleVar(value=0.0)
        ttk.Spinbox(p_grid, from_=0.0, to=50000.0, increment=1.0, textvariable=self.sem_particle_size_var, width=18).grid(row=0, column=1, sticky="w", padx=8, pady=4)

        ttk.Label(p_grid, text="Monolith Macropore Size (μm):").grid(row=0, column=2, sticky="w", padx=(16, 0), pady=4)
        self.sem_macropore_var = tk.DoubleVar(value=0.0)
        ttk.Spinbox(p_grid, from_=0.0, to=1000.0, increment=0.5, textvariable=self.sem_macropore_var, width=18).grid(row=0, column=3, sticky="w", padx=8, pady=4)

        ttk.Label(p_grid, text="Wall / Skeleton Thickness (μm):").grid(row=1, column=0, sticky="w", pady=4)
        self.sem_wall_thick_var = tk.DoubleVar(value=0.0)
        ttk.Spinbox(p_grid, from_=0.0, to=1000.0, increment=0.1, textvariable=self.sem_wall_thick_var, width=18).grid(row=1, column=1, sticky="w", padx=8, pady=4)

        ttk.Label(p_grid, text="Morphology Type:").grid(row=1, column=2, sticky="w", padx=(16, 0), pady=4)
        self.sem_morphology_var = tk.StringVar(value="Porous Monolith")
        ttk.Combobox(p_grid, values=["Porous Monolith", "Spherical Beads", "Fibrous / Nanowires", "Platelets / Sheets", "Hierarchical Core-Shell", "Amorphous Aggregate"], textvariable=self.sem_morphology_var, width=16).grid(row=1, column=3, sticky="w", padx=8, pady=4)

        ttk.Label(p_grid, text="EDX Elemental Ratio / Notes:").grid(row=2, column=0, sticky="w", pady=4)
        self.sem_edx_notes_var = tk.StringVar(value="")
        ttk.Entry(p_grid, textvariable=self.sem_edx_notes_var, width=45).grid(row=2, column=1, columnspan=3, sticky="w", padx=8, pady=4)

        btn_save_sem = ttk.Button(param_frame, text="💾 Save SEM / TEM Parameters", command=self.on_save_sem_params)
        btn_save_sem.pack(anchor="e", pady=(8, 0))

    def _refresh_sem_tem_tab(self):
        for item in self.tree_sem.get_children():
            self.tree_sem.delete(item)

        if not self.current_sample_id or self.current_sample_id not in self.vault.logbook:
            self.sem_particle_size_var.set(0.0)
            self.sem_macropore_var.set(0.0)
            self.sem_wall_thick_var.set(0.0)
            self.sem_morphology_var.set("Porous Monolith")
            self.sem_edx_notes_var.set("")
            return

        data = self.vault.logbook[self.current_sample_id]
        tech_data = data.get("characterizations", {}).get("sem_tem", {})
        for f in tech_data.get("files", []):
            sz = f.get("size_bytes", 0) / 1024.0
            self.tree_sem.insert("", tk.END, values=(
                f.get("filename", "-"),
                f.get("uploaded_at", "-"),
                f"{sz:.1f} KB"
            ))

        self.sem_particle_size_var.set(float(tech_data.get("particle_size_nm", 0.0)))
        self.sem_macropore_var.set(float(tech_data.get("macropore_size_um", 0.0)))
        self.sem_wall_thick_var.set(float(tech_data.get("wall_thickness_um", 0.0)))
        self.sem_morphology_var.set(tech_data.get("morphology", "Porous Monolith"))
        self.sem_edx_notes_var.set(tech_data.get("edx_notes", ""))

    def on_save_sem_params(self):
        if not self.current_sample_id:
            return
        data = self.vault.logbook[self.current_sample_id]
        sem_dict = data.setdefault("characterizations", {}).setdefault("sem_tem", {})
        sem_dict["particle_size_nm"] = float(self.sem_particle_size_var.get())
        sem_dict["macropore_size_um"] = float(self.sem_macropore_var.get())
        sem_dict["wall_thickness_um"] = float(self.sem_wall_thick_var.get())
        sem_dict["morphology"] = self.sem_morphology_var.get()
        sem_dict["edx_notes"] = self.sem_edx_notes_var.get()
        self.vault.save_logbook()
        messagebox.showinfo("Saved", f"SEM / TEM morphological parameters saved for {self.current_sample_id}.")

    # ==================== TAB: RHEOLOGICAL PROPERTIES ====================

    def _build_rheology_tab(self, parent):
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill=tk.X, pady=(0, 8))

        filetypes = [("Rheometer Files", "*.csv;*.xlsx;*.xls;*.txt;*.rfd"), ("All Files", "*.*")]
        ttk.Button(toolbar, text="➕ Attach Rheology Curve", command=lambda: self.on_attach_generic_file("rheology", filetypes)).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="🗑️ Delete File", command=lambda: self.on_delete_file("rheology")).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="📂 Open File", command=lambda: self.on_open_selected_file("rheology")).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="📁 Open Folder", command=lambda: self.on_open_tech_folder("rheology")).pack(side=tk.LEFT, padx=3)

        cols = ("fn", "uploaded", "size")
        self.tree_rheo = ttk.Treeview(parent, columns=cols, show="headings", selectmode="browse", height=5)
        self.tree_rheo.heading("fn", text="Rheology Flow / Oscillation Data File")
        self.tree_rheo.heading("uploaded", text="Upload Date")
        self.tree_rheo.heading("size", text="Size")
        self.tree_rheo.column("fn", width=280, anchor="w")
        self.tree_rheo.column("uploaded", width=140, anchor="center")
        self.tree_rheo.column("size", width=100, anchor="e")
        self.tree_rheo.pack(fill=tk.X, pady=(0, 10))

        # Rheology Key Parameters Box
        param_frame = ttk.LabelFrame(parent, text=" Rheological Parameters (Slurry, Paste & Printability) ", padding=10)
        param_frame.pack(fill=tk.X)

        p_grid = ttk.Frame(param_frame)
        p_grid.pack(fill=tk.X)

        ttk.Label(p_grid, text="Zero-Shear Viscosity η₀ (Pa·s):").grid(row=0, column=0, sticky="w", pady=4)
        self.rheo_visc_var = tk.DoubleVar(value=0.0)
        ttk.Spinbox(p_grid, from_=0.0, to=100000.0, increment=1.0, textvariable=self.rheo_visc_var, width=18).grid(row=0, column=1, sticky="w", padx=8, pady=4)

        ttk.Label(p_grid, text="Yield Stress τ₀ (Pa):").grid(row=0, column=2, sticky="w", padx=(16, 0), pady=4)
        self.rheo_yield_var = tk.DoubleVar(value=0.0)
        ttk.Spinbox(p_grid, from_=0.0, to=10000.0, increment=0.5, textvariable=self.rheo_yield_var, width=18).grid(row=0, column=3, sticky="w", padx=8, pady=4)

        ttk.Label(p_grid, text="Storage Modulus G' (Pa):").grid(row=1, column=0, sticky="w", pady=4)
        self.rheo_gp_var = tk.DoubleVar(value=0.0)
        ttk.Spinbox(p_grid, from_=0.0, to=500000.0, increment=10.0, textvariable=self.rheo_gp_var, width=18).grid(row=1, column=1, sticky="w", padx=8, pady=4)

        ttk.Label(p_grid, text="Loss Modulus G'' (Pa):").grid(row=1, column=2, sticky="w", padx=(16, 0), pady=4)
        self.rheo_gpp_var = tk.DoubleVar(value=0.0)
        ttk.Spinbox(p_grid, from_=0.0, to=500000.0, increment=10.0, textvariable=self.rheo_gpp_var, width=18).grid(row=1, column=3, sticky="w", padx=8, pady=4)

        ttk.Label(p_grid, text="Loss Factor (tan δ = G''/G'):").grid(row=2, column=0, sticky="w", pady=4)
        self.rheo_tan_delta_var = tk.DoubleVar(value=0.0)
        ttk.Spinbox(p_grid, from_=0.0, to=10.0, increment=0.01, textvariable=self.rheo_tan_delta_var, width=18).grid(row=2, column=1, sticky="w", padx=8, pady=4)

        ttk.Label(p_grid, text="Flow Behavior:").grid(row=2, column=2, sticky="w", padx=(16, 0), pady=4)
        self.rheo_behavior_var = tk.StringVar(value="Shear-Thinning (Pseudoplastic)")
        ttk.Combobox(p_grid, values=["Shear-Thinning (Pseudoplastic)", "Newtonian", "Shear-Thickening (Dilatant)", "Bingham Plastic", "Viscoelastic Gel"], textvariable=self.rheo_behavior_var, width=24).grid(row=2, column=3, sticky="w", padx=8, pady=4)

        btn_save_rheo = ttk.Button(param_frame, text="💾 Save Rheology Parameters", command=self.on_save_rheology_params)
        btn_save_rheo.pack(anchor="e", pady=(8, 0))

    def _refresh_rheology_tab(self):
        for item in self.tree_rheo.get_children():
            self.tree_rheo.delete(item)

        if not self.current_sample_id or self.current_sample_id not in self.vault.logbook:
            self.rheo_visc_var.set(0.0)
            self.rheo_yield_var.set(0.0)
            self.rheo_gp_var.set(0.0)
            self.rheo_gpp_var.set(0.0)
            self.rheo_tan_delta_var.set(0.0)
            self.rheo_behavior_var.set("Shear-Thinning (Pseudoplastic)")
            return

        data = self.vault.logbook[self.current_sample_id]
        tech_data = data.get("characterizations", {}).get("rheology", {})
        for f in tech_data.get("files", []):
            sz = f.get("size_bytes", 0) / 1024.0
            self.tree_rheo.insert("", tk.END, values=(
                f.get("filename", "-"),
                f.get("uploaded_at", "-"),
                f"{sz:.1f} KB"
            ))

        self.rheo_visc_var.set(float(tech_data.get("zero_shear_viscosity_pa_s", 0.0)))
        self.rheo_yield_var.set(float(tech_data.get("yield_stress_pa", 0.0)))
        self.rheo_gp_var.set(float(tech_data.get("storage_modulus_gp_pa", 0.0)))
        self.rheo_gpp_var.set(float(tech_data.get("loss_modulus_gpp_pa", 0.0)))
        self.rheo_tan_delta_var.set(float(tech_data.get("loss_factor_tan_delta", 0.0)))
        self.rheo_behavior_var.set(tech_data.get("flow_behavior", "Shear-Thinning (Pseudoplastic)"))

    def on_save_rheology_params(self):
        if not self.current_sample_id:
            return
        data = self.vault.logbook[self.current_sample_id]
        rheo_dict = data.setdefault("characterizations", {}).setdefault("rheology", {})
        rheo_dict["zero_shear_viscosity_pa_s"] = float(self.rheo_visc_var.get())
        rheo_dict["yield_stress_pa"] = float(self.rheo_yield_var.get())
        rheo_dict["storage_modulus_gp_pa"] = float(self.rheo_gp_var.get())
        rheo_dict["loss_modulus_gpp_pa"] = float(self.rheo_gpp_var.get())
        rheo_dict["loss_factor_tan_delta"] = float(self.rheo_tan_delta_var.get())
        rheo_dict["flow_behavior"] = self.rheo_behavior_var.get()
        self.vault.save_logbook()
        messagebox.showinfo("Saved", f"Rheological parameters saved for {self.current_sample_id}.")

