import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from core.sample_vault import CHARACTERIZATION_TYPES

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
        self.tech_notebook.add(self.tab_bet, text=" 📐 N₂ Physisorption / BET Surface Area ")
        self._build_bet_tab(self.tab_bet)

        # Tab: Raman / Spectroscopy
        self.tab_raman = ttk.Frame(self.tech_notebook, padding=8)
        self.tech_notebook.add(self.tab_raman, text=" 💡 Raman Spectroscopy ")
        self._build_generic_tab(self.tab_raman, "raman", "Raman Spectra (.txt, .csv, .spc):", [("Raman Data", "*.txt;*.csv;*.spc"), ("All Files", "*.*")])

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
        self._refresh_generic_table("raman")
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
