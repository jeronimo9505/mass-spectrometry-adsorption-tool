import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk
Image.MAX_IMAGE_PIXELS = None
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from core.sample_vault import CHARACTERIZATION_TYPES
from gui.tga_panel import TGAPanelMixin
from core.thermal_engine import (
    PROFILE_CATEGORIES, detect_profile_category,
    load_thermal_data, plot_thermal_curves, plot_thermal_heatmap
)

class CharacterizationHubView(TGAPanelMixin, ttk.Frame):
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
        self._refreshed_tabs = set()

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

        # Tab 1: Mass Spectrometry / Adsorption
        self.tab_mass = ttk.Frame(self.tech_notebook, padding=8)
        self.tech_notebook.add(self.tab_mass, text=" 🧪 Mass Spectrometry (.asc) ")
        self._build_mass_spec_tab(self.tab_mass)

        # Tab 2: Adsorption Exotherm & Thermal Profiles
        self.tab_thermal = ttk.Frame(self.tech_notebook, padding=8)
        self.tech_notebook.add(self.tab_thermal, text=" 🌡️ Adsorption Thermal Profiles ")
        self._build_thermal_profile_tab(self.tab_thermal)

        # Tab 3: TGA Thermal Analysis
        self.tab_tga = ttk.Frame(self.tech_notebook, padding=8)
        self.tech_notebook.add(self.tab_tga, text=" 🔥 TGA Thermal Analysis ")
        self._build_tga_tab(self.tab_tga)

        # Tab 3: Rheological Properties
        self.tab_rheology = ttk.Frame(self.tech_notebook, padding=8)
        self.tech_notebook.add(self.tab_rheology, text=" 🌊 Rheological Properties ")
        self._build_rheology_tab(self.tab_rheology)

        # Tab 4: Computed Tomography (micro-CT)
        self.tab_tomography = ttk.Frame(self.tech_notebook, padding=8)
        self.tech_notebook.add(self.tab_tomography, text=" 🧊 Computed Tomography (micro-CT) ")
        self._build_tomography_tab(self.tab_tomography)

        # Tab 5: SEM / TEM Microscopy
        self.tab_sem_tem = ttk.Frame(self.tech_notebook, padding=8)
        self.tech_notebook.add(self.tab_sem_tem, text=" 🔍 SEM / TEM Microscopy ")
        self._build_sem_tem_tab(self.tab_sem_tem)

        # Tab 6: Mercury Porosimetry (MIP)
        self.tab_hg_porosimetry = ttk.Frame(self.tech_notebook, padding=8)
        self.tech_notebook.add(self.tab_hg_porosimetry, text=" 💧 Mercury Porosimetry (MIP) ")
        self._build_hg_porosimetry_tab(self.tab_hg_porosimetry)

        # Tab 7: BET Surface Area
        self.tab_bet = ttk.Frame(self.tech_notebook, padding=8)
        self.tech_notebook.add(self.tab_bet, text=" 📐 N₂ Physisorption / BET ")
        self._build_bet_tab(self.tab_bet)

        # Listen to tab change for lazy loading heavy tabs (TGA)
        self.tech_notebook.bind("<<NotebookTabChanged>>", self.on_tech_tab_changed)

    def _update_banner(self):
        if not self.current_sample_id or self.current_sample_id not in self.vault.logbook:
            self.lbl_banner_title.config(text="🏷️ Active Sample: [ None Selected ]")
            self.lbl_banner_details.config(text="Select a sample in the 'Logbook' tab to inspect and attach characterization files.")
            return

        data = self.vault.logbook[self.current_sample_id]
        mat = data.get("material_name", "-")
        mass_tot = float(data.get("mass_total_g", 0.0) or 0.0)
        water = float(data.get("water_loss_pct", 0.0) or 0.0)
        mass_act = mass_tot * (1.0 - (water / 100.0)) if mass_tot > 0 else 0.0
        op = data.get("operator", "-")
        date_str = data.get("date", "-")

        mass_str = f"{mass_tot:.4f} g" if mass_tot > 0 else "-"
        water_str = f"{water:.1f}%" if (mass_tot > 0 or water > 0) else "-"
        act_str = f"{mass_act:.4f} g" if mass_tot > 0 else "-"

        self.lbl_banner_title.config(text=f"🏷️ Sample: {self.current_sample_id} — {mat}")
        self.lbl_banner_details.config(
            text=f"Date: {date_str}  |  Operator: {op}  |  Total Mass: {mass_str}  |  Water Loss: {water_str}  |  Active Mass: {act_str}"
        )

    def set_sample(self, sample_id, lazy=False):
        """
        Sets the active sample in the Characterization Hub.
        If lazy=True (e.g. user browsing samples in Tab 1 Logbook), only the banner updates.
        Sub-tabs are refreshed strictly on-demand when the user actually navigates to them.
        """
        if self.current_sample_id != sample_id:
            self.current_sample_id = sample_id
            self._refreshed_tabs.clear()
            self._update_banner()
            if not lazy:
                self.refresh_active_tab()
        else:
            self._update_banner()
            if not lazy:
                self.refresh_active_tab()

    def refresh_active_tab(self):
        """
        Refreshes strictly the currently selected sub-tab in the Hub.
        Prevents loading/parsing all characterizations simultaneously.
        """
        if not self.current_sample_id or self.current_sample_id not in self.vault.logbook:
            return

        try:
            current_tab_id = self.tech_notebook.select()
        except Exception:
            return

        tab_map = {
            str(self.tab_mass): ("mass_spec", self._refresh_mass_table),
            str(self.tab_thermal): ("thermal_profile", self._refresh_thermal_tab),
            str(self.tab_tga): ("tga", self._refresh_tga_tab),
            str(self.tab_rheology): ("rheology", self._refresh_rheology_tab),
            str(self.tab_tomography): ("tomography", self._refresh_tomography_tab),
            str(self.tab_sem_tem): ("sem_tem", self._refresh_sem_tem_tab),
            str(self.tab_hg_porosimetry): ("hg_porosimetry", self._refresh_hg_porosimetry_tab),
            str(self.tab_bet): ("bet", self._refresh_bet_tab)
        }

        entry = tab_map.get(current_tab_id)
        if entry:
            tech_key, refresh_fn = entry
            if tech_key not in self._refreshed_tabs:
                refresh_fn()
                self._refreshed_tabs.add(tech_key)

    def on_tech_tab_changed(self, event=None):
        """Called whenever user clicks a different technique sub-tab."""
        self.refresh_active_tab()

    def refresh_all_tabs(self):
        """Forces full refresh of all tabs (e.g. on manual vault rescan)."""
        self._refreshed_tabs.clear()
        self.refresh_active_tab()

    def show_technique(self, tech_key):
        """Switches to the specified characterization technique tab and refreshes it."""
        tab_map = {
            "mass_spec": self.tab_mass,
            "thermal_profile": self.tab_thermal,
            "tga": self.tab_tga,
            "rheology": self.tab_rheology,
            "tomography": self.tab_tomography,
            "sem_tem": self.tab_sem_tem,
            "hg_porosimetry": self.tab_hg_porosimetry,
            "bet": self.tab_bet
        }
        tab = tab_map.get(tech_key)
        if tab:
            self.tech_notebook.select(tab)
            self.refresh_active_tab()

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
        tree.bind("<Double-1>", lambda e: self.on_open_selected_file(tech_key))
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

        fpaths = filedialog.askopenfilenames(
            title=f"Select {CHARACTERIZATION_TYPES.get(tech_key, {}).get('name', tech_key)} File(s)",
            filetypes=filetypes
        )
        if fpaths:
            added = 0
            errors = []
            for fpath in fpaths:
                try:
                    self.vault.add_characterization_file(self.current_sample_id, tech_key, fpath)
                    added += 1
                except Exception as e:
                    errors.append(f"{os.path.basename(fpath)}: {e}")

            if tech_key == "sem_tem":
                self._refresh_sem_tem_tab()
            elif tech_key == "thermal_profile":
                self._refresh_thermal_tab()
            elif tech_key == "tga":
                self._refresh_tga_tab()
            elif tech_key == "bet":
                self._refresh_bet_tab()
            elif tech_key == "rheology":
                self._refresh_rheology_tab()
            elif tech_key == "tomography":
                self._refresh_tomography_tab()
            elif tech_key == "hg_porosimetry":
                self._refresh_hg_porosimetry_tab()
            else:
                self._refresh_generic_table(tech_key)

            if errors:
                messagebox.showwarning("Attached with warnings", f"Attached {added} file(s).\nErrors encountered:\n" + "\n".join(errors))
            else:
                messagebox.showinfo("Files Attached", f"Successfully attached {added} file(s) to sample {self.current_sample_id}.")

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
            messagebox.showinfo("Select File", "Please select file(s) to delete.")
            return

        filenames = [tree.item(item_id, "values")[0] for item_id in sel]
        if len(filenames) == 1:
            msg = f"Delete '{filenames[0]}' from sample {self.current_sample_id}?"
        else:
            msg = f"Delete {len(filenames)} selected files from sample {self.current_sample_id}?"

        if messagebox.askyesno("Confirm Deletion", msg):
            for fn in filenames:
                self.vault.delete_characterization_file(self.current_sample_id, tech_key, fn)

            if tech_key == "mass_spec":
                self._refresh_mass_table()
            elif tech_key == "thermal_profile":
                self._refresh_thermal_tab()
            elif tech_key == "sem_tem":
                self._refresh_sem_tem_tab()
            elif tech_key == "tga":
                self._refresh_tga_tab()
            elif tech_key == "bet":
                self._refresh_bet_tab()
            elif tech_key == "rheology":
                self._refresh_rheology_tab()
            elif tech_key == "tomography":
                self._refresh_tomography_tab()
            elif tech_key == "hg_porosimetry":
                self._refresh_hg_porosimetry_tab()
            else:
                self._refresh_generic_table(tech_key)

    def on_open_tech_folder(self, tech_key):
        if not self.current_sample_id:
            return
        folder = self.vault.get_technique_dir(self.current_sample_id, tech_key, create=False)
        if os.path.exists(folder):
            os.startfile(folder)
        else:
            s_folder = self.vault.get_sample_dir(self.current_sample_id)
            if os.path.exists(s_folder):
                os.startfile(s_folder)

    # ==================== TAB: BET SURFACE AREA ====================

    def _build_bet_tab(self, parent):
        top_frame = ttk.Frame(parent)
        top_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Button(top_frame, text="➕ Attach BET Isotherm (.xls, .csv)", command=lambda: self.on_attach_generic_file("bet", [("BET Data", "*.xls;*.xlsx;*.csv;*.txt")])).pack(side=tk.LEFT, padx=3)
        ttk.Button(top_frame, text="🗑️ Delete File", command=lambda: self.on_delete_file("bet")).pack(side=tk.LEFT, padx=3)
        ttk.Button(top_frame, text="📂 Open File", command=lambda: self.on_open_selected_file("bet")).pack(side=tk.LEFT, padx=3)
        ttk.Button(top_frame, text="📁 View in Folder", command=lambda: self.on_open_tech_folder("bet")).pack(side=tk.LEFT, padx=3)

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
        self.tree_bet.bind("<Double-1>", lambda e: self.on_open_selected_file("bet"))

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

    # ==================== TAB: ADSORPTION EXOTHERM & THERMAL PROFILES ====================

    def _build_thermal_profile_tab(self, parent):
        thermal_paned = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
        thermal_paned.pack(fill=tk.BOTH, expand=True)

        left_side = ttk.Frame(thermal_paned, width=470)
        right_side = ttk.Frame(thermal_paned)
        thermal_paned.add(left_side, weight=0)
        thermal_paned.add(right_side, weight=1)

        # Header Info Banner
        header_f = ttk.Frame(left_side)
        header_f.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(
            header_f, 
            text="🌡️ Adsorption Thermal Profiles (Time-Temp-Position)", 
            font=("Segoe UI", 10, "bold"), 
            foreground="#d35400"
        ).pack(side=tk.LEFT)

        # Section Filter Bar
        filter_row = ttk.Frame(left_side)
        filter_row.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(filter_row, text="Section Filter:", font=("Segoe UI", 8, "bold")).pack(side=tk.LEFT, padx=(0, 4))
        self.thermal_cat_filter_var = tk.StringVar(value="All Profiles & Files")
        self.thermal_cat_combo = ttk.Combobox(
            filter_row, 
            textvariable=self.thermal_cat_filter_var, 
            values=[
                "All Profiles & Files",
                "↕️ Vertical Profile (V-series)",
                "↔️ Horizontal Profile (H-series)",
                "⚖️ Hori vs Ver Comparison",
                "🗺️ 2D Thermal Heatmap",
                "📄 Raw Thermocouple Data"
            ],
            state="readonly",
            width=24
        )
        self.thermal_cat_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.thermal_cat_combo.bind("<<ComboboxSelected>>", self._apply_thermal_filter)

        # Toolbar
        toolbar = ttk.Frame(left_side)
        toolbar.pack(fill=tk.X, pady=(0, 6))

        ttk.Button(toolbar, text="➕ Attach Image(s)", command=self.on_attach_thermal_images).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="➕ Raw Data", command=self.on_attach_thermal_data).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="🏷️ Set Section", command=self.on_set_thermal_category).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="🗑️ Delete", command=lambda: self.on_delete_file("thermal_profile")).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="📂 Open", command=lambda: self.on_open_selected_file("thermal_profile")).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="📁 Folder", command=lambda: self.on_open_tech_folder("thermal_profile")).pack(side=tk.LEFT, padx=2)

        # Table of Thermal Files
        cols = ("fn", "section", "size")
        self.tree_thermal = ttk.Treeview(left_side, columns=cols, show="headings", selectmode="browse", height=6)
        self.tree_thermal.heading("fn", text="Graph / Data File")
        self.tree_thermal.heading("section", text="Section / Profile Type")
        self.tree_thermal.heading("size", text="Size")
        self.tree_thermal.column("fn", width=190, anchor="w")
        self.tree_thermal.column("section", width=160, anchor="center")
        self.tree_thermal.column("size", width=70, anchor="e")

        self.tree_thermal.pack(side=tk.TOP, fill=tk.X, pady=(0, 4))
        self.tree_thermal.bind("<<TreeviewSelect>>", self.on_thermal_file_selected)
        self.tree_thermal.bind("<Double-1>", lambda e: self.on_open_selected_file("thermal_profile"))
        self.tree_thermal.bind("<Button-3>", self._on_thermal_tree_right_click)

        # Raw Data Action Buttons
        act_row = ttk.Frame(left_side)
        act_row.pack(fill=tk.X, pady=(0, 6))
        self.btn_thermal_curves = ttk.Button(act_row, text="📈 Plot Raw Curves", command=self.on_plot_thermal_curves)
        self.btn_thermal_curves.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        self.btn_thermal_heat = ttk.Button(act_row, text="🗺️ Plot 2D Heatmap", command=self.on_plot_thermal_heatmap)
        self.btn_thermal_heat.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        self.btn_thermal_export = ttk.Button(act_row, text="💾 Export Plot...", command=self.on_export_thermal_plot)
        self.btn_thermal_export.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=2)

        # Parameters Frame (Auto-populated from Excel/CSV or manual)
        param_frame = ttk.LabelFrame(left_side, text=" 🔥 Exothermic Adsorption Kinetics & Parameters ", padding=8)
        param_frame.pack(fill=tk.BOTH, expand=True, pady=(2, 0))

        p_grid = ttk.Frame(param_frame)
        p_grid.pack(fill=tk.X)

        ttk.Label(p_grid, text="Bed Initial Temp T₀ (°C):").grid(row=0, column=0, sticky="w", pady=3)
        self.thermal_t0_var = tk.DoubleVar(value=28.0)
        self.thermal_t0_var.trace_add("write", self._update_thermal_delta)
        ttk.Spinbox(p_grid, from_=0.0, to=400.0, increment=0.5, textvariable=self.thermal_t0_var, width=10).grid(row=0, column=1, sticky="w", padx=4, pady=3)

        ttk.Label(p_grid, text="Peak Exotherm Temp T_max (°C):", font=("Segoe UI", 9, "bold")).grid(row=0, column=2, sticky="w", padx=(10, 0), pady=3)
        self.thermal_tmax_var = tk.DoubleVar(value=36.0)
        self.thermal_tmax_var.trace_add("write", self._update_thermal_delta)
        ttk.Spinbox(p_grid, from_=0.0, to=500.0, increment=0.5, textvariable=self.thermal_tmax_var, width=10).grid(row=0, column=3, sticky="w", padx=4, pady=3)

        ttk.Label(p_grid, text="Max Exotherm Rise ΔT (°C):", foreground="#c0392b", font=("Segoe UI", 9, "bold")).grid(row=1, column=0, sticky="w", pady=3)
        self.thermal_delta_var = tk.DoubleVar(value=8.0)
        ttk.Spinbox(p_grid, from_=0.0, to=200.0, increment=0.5, textvariable=self.thermal_delta_var, width=10).grid(row=1, column=1, sticky="w", padx=4, pady=3)

        ttk.Label(p_grid, text="Time to Peak (min):").grid(row=1, column=2, sticky="w", padx=(10, 0), pady=3)
        self.thermal_tpeak_var = tk.DoubleVar(value=3.0)
        ttk.Spinbox(p_grid, from_=0.0, to=600.0, increment=0.5, textvariable=self.thermal_tpeak_var, width=10).grid(row=1, column=3, sticky="w", padx=4, pady=3)

        ttk.Label(p_grid, text="Hotspot Bed Position:").grid(row=2, column=0, sticky="w", pady=3)
        self.thermal_hotspot_var = tk.StringVar(value="V7 (Center)")
        ttk.Combobox(p_grid, textvariable=self.thermal_hotspot_var, values=["V0", "V1", "V2", "V3", "V4", "V5", "V6", "V7 (Center)", "V8", "V9", "V10", "V11", "V12", "V13", "V14", "H5 (Center)", "Inlet", "Outlet"], width=10).grid(row=2, column=1, sticky="w", padx=4, pady=3)

        ttk.Label(p_grid, text="Reaction Duration (min):").grid(row=2, column=2, sticky="w", padx=(10, 0), pady=3)
        self.thermal_duration_var = tk.DoubleVar(value=22.0)
        ttk.Spinbox(p_grid, from_=0.0, to=1440.0, increment=1.0, textvariable=self.thermal_duration_var, width=10).grid(row=2, column=3, sticky="w", padx=4, pady=3)

        ttk.Label(p_grid, text="Reaction Notes:").grid(row=3, column=0, sticky="w", pady=3)
        self.thermal_notes_var = tk.StringVar(value="")
        ttk.Entry(p_grid, textvariable=self.thermal_notes_var, width=32).grid(row=3, column=1, columnspan=3, sticky="ew", padx=4, pady=3)

        btn_save_thermal = ttk.Button(param_frame, text="💾 Save Thermal Parameters to Sample", command=self.on_save_thermal_params)
        btn_save_thermal.pack(fill=tk.X, pady=(8, 0))

        # ================= RIGHT SIDE: High-Resolution Graphic & Plot Viewer =================
        right_header = ttk.Frame(right_side)
        right_header.pack(fill=tk.X, pady=(0, 4))

        self.lbl_thermal_preview_title = ttk.Label(
            right_header, 
            text="📈 Interactive Thermal Graph & Profile Viewer", 
            font=("Segoe UI", 10, "bold"), 
            foreground="#1d3557"
        )
        self.lbl_thermal_preview_title.pack(side=tk.LEFT)

        zoom_controls = ttk.Frame(right_header)
        zoom_controls.pack(side=tk.RIGHT)

        ttk.Button(zoom_controls, text="🔍+", width=4, command=lambda: self.on_thermal_zoom(1.25)).pack(side=tk.LEFT, padx=1)
        ttk.Button(zoom_controls, text="🔍-", width=4, command=lambda: self.on_thermal_zoom(0.8)).pack(side=tk.LEFT, padx=1)
        ttk.Button(zoom_controls, text="🔄 Fit", width=5, command=self.on_thermal_fit).pack(side=tk.LEFT, padx=1)
        ttk.Button(zoom_controls, text="↗️ External", width=9, command=lambda: self.on_open_selected_file("thermal_profile")).pack(side=tk.LEFT, padx=1)

        self.thermal_viewer_container = ttk.Frame(right_side)
        self.thermal_viewer_container.pack(fill=tk.BOTH, expand=True)

        # Image Frame with Canvas
        self.thermal_image_frame = ttk.Frame(self.thermal_viewer_container)
        self.thermal_canvas = tk.Canvas(self.thermal_image_frame, bg="#1e1e1e", highlightthickness=0)
        self.thermal_canvas.pack(fill=tk.BOTH, expand=True)
        self.thermal_canvas.bind("<Configure>", self._on_thermal_canvas_resize)
        self.thermal_canvas.bind("<MouseWheel>", self._on_thermal_canvas_wheel)
        self.thermal_canvas.bind("<ButtonPress-1>", self._on_thermal_canvas_press)
        self.thermal_canvas.bind("<B1-Motion>", self._on_thermal_canvas_drag)

        # Plot Frame with Matplotlib
        self.thermal_plot_frame = ttk.Frame(self.thermal_viewer_container)
        self.thermal_fig, _ = plt.subplots(figsize=(6.5, 5.2), dpi=100)
        self.thermal_plot_canvas = FigureCanvasTkAgg(self.thermal_fig, master=self.thermal_plot_frame)
        self.thermal_plot_canvas.draw()
        thermal_nav_f = ttk.Frame(self.thermal_plot_frame)
        thermal_nav_f.pack(side=tk.TOP, fill=tk.X)
        self.thermal_nav = NavigationToolbar2Tk(self.thermal_plot_canvas, thermal_nav_f)
        self.thermal_nav.update()
        self.thermal_plot_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self.thermal_preview_info = ttk.Label(
            right_side, 
            text="Select an exothermic graph or attach raw data to inspect thermal kinetics.", 
            font=("Segoe UI", 9, "italic")
        )
        self.thermal_preview_info.pack(side=tk.BOTTOM, anchor="w", pady=(4, 0))

        self.thermal_image_frame.pack(fill=tk.BOTH, expand=True)

        self._current_thermal_img_path = None
        self._current_thermal_photo = None
        self._thermal_pil_orig = None
        self._thermal_zoom_ratio = 1.0
        self._thermal_fit_mode = True
        self._thermal_drag_start = (0, 0)
        self._thermal_img_offset = [0, 0]
        self._current_thermal_df = None
        self._current_thermal_meta = {}

    def _update_thermal_delta(self, *args):
        try:
            t0 = float(self.thermal_t0_var.get())
            tmax = float(self.thermal_tmax_var.get())
            self.thermal_delta_var.set(round(tmax - t0, 2))
        except Exception:
            pass

    def on_attach_thermal_images(self):
        if not self.current_sample_id:
            messagebox.showinfo("Select Sample", "Please select a sample in the logbook first.")
            return

        fpaths = filedialog.askopenfilenames(
            title="Select Exotherm Thermal Graph Image(s)",
            filetypes=[("Graph Images", "*.png;*.jpg;*.jpeg;*.tif;*.tiff;*.bmp;*.gif"), ("All Files", "*.*")]
        )
        if fpaths:
            added = 0
            cur_filter = self.thermal_cat_filter_var.get()
            for fp in fpaths:
                fn = os.path.basename(fp)
                if "Vertical" in cur_filter:
                    cat = "Vertical Profile"
                elif "Horizontal" in cur_filter:
                    cat = "Horizontal Profile"
                elif "Comparison" in cur_filter:
                    cat = "Hori vs Ver Comparison"
                elif "Heatmap" in cur_filter:
                    cat = "2D Thermal Heatmap"
                else:
                    cat = detect_profile_category(fn)

                self.vault.add_characterization_file(
                    self.current_sample_id, "thermal_profile", fp, description=cat
                )
                added += 1

            self._refresh_thermal_tab()
            messagebox.showinfo("Images Attached", f"Successfully attached {added} graph image(s) to sample {self.current_sample_id}.")

    def on_attach_thermal_data(self):
        if not self.current_sample_id:
            messagebox.showinfo("Select Sample", "Please select a sample in the logbook first.")
            return

        fpath = filedialog.askopenfilename(
            title="Select Raw Thermocouple Data File (Excel / CSV / TXT)",
            filetypes=[("Data Files", "*.csv;*.xlsx;*.xls;*.txt;*.dat"), ("All Files", "*.*")]
        )
        if fpath:
            try:
                dest = self.vault.add_characterization_file(
                    self.current_sample_id, "thermal_profile", fpath, description="Raw Thermocouple Data"
                )
                self._refresh_thermal_tab()
                df, meta = load_thermal_data(dest)
                self._current_thermal_df = df
                self._current_thermal_meta = meta
                self.thermal_t0_var.set(meta.get("t_initial_c", 28.0))
                self.thermal_tmax_var.set(meta.get("t_max_c", 36.0))
                self.thermal_delta_var.set(meta.get("delta_t_c", 8.0))
                self.thermal_tpeak_var.set(meta.get("time_to_peak_min", 3.0))
                self.thermal_hotspot_var.set(meta.get("hotspot_position", "V7 (Center)"))
                self.thermal_duration_var.set(meta.get("duration_min", 22.0))

                self.on_plot_thermal_curves()
                messagebox.showinfo("Data Loaded", f"Raw data attached and analyzed!\nPeak Exotherm: {meta.get('t_max_c')} °C at {meta.get('hotspot_position')}.")
            except Exception as e:
                messagebox.showerror("Error Attaching Data", f"Could not process data file:\n{e}")

    def on_thermal_file_selected(self, event=None):
        sel = self.tree_thermal.selection()
        if not sel or not self.current_sample_id:
            return
        fn = self.tree_thermal.item(sel[0], "values")[0]
        fpath = self.vault.get_characterization_file_path(self.current_sample_id, "thermal_profile", fn)
        if not fpath or not os.path.exists(fpath):
            return

        ext = os.path.splitext(fn)[1].lower()
        if ext in [".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif"]:
            self.display_thermal_image(fpath)
        elif ext in [".csv", ".xlsx", ".xls", ".txt", ".dat"]:
            try:
                df, meta = load_thermal_data(fpath)
                self._current_thermal_df = df
                self._current_thermal_meta = meta
                self.on_plot_thermal_curves()
            except Exception as e:
                messagebox.showwarning("Plot Warning", f"Could not auto-plot data file:\n{e}")
        else:
            self.on_open_selected_file("thermal_profile")

    def display_thermal_image(self, fpath):
        self._current_thermal_img_path = fpath
        fn = os.path.basename(fpath)

        self.thermal_plot_frame.pack_forget()
        self.thermal_image_frame.pack(fill=tk.BOTH, expand=True)

        try:
            self._thermal_pil_orig = Image.open(fpath)
            orig_w, orig_h = self._thermal_pil_orig.size
            self._thermal_fit_mode = True
            self._thermal_zoom_ratio = 1.0
            self._thermal_img_offset = [0, 0]
            self._render_thermal_image()

            sz_kb = os.path.getsize(fpath) / 1024.0
            sel = self.tree_thermal.selection()
            sec = self.tree_thermal.item(sel[0], "values")[1] if sel else "Profile"
            self.lbl_thermal_preview_title.config(text=f"🖼️ {fn}  [{sec}]")
            self.thermal_preview_info.config(
                text=f"Resolution: {orig_w} × {orig_h} px  |  Size: {sz_kb:.1f} KB  |  Zoom: Fit to Canvas"
            )
        except Exception as e:
            self.thermal_canvas.delete("all")
            self.thermal_preview_info.config(text=f"⚠️ Could not load image: {e}")

    def _render_thermal_image(self):
        if not self._thermal_pil_orig:
            return

        orig_w, orig_h = self._thermal_pil_orig.size
        canv_w = max(self.thermal_canvas.winfo_width(), 200)
        canv_h = max(self.thermal_canvas.winfo_height(), 200)

        if self._thermal_fit_mode:
            ratio = min(canv_w / orig_w, canv_h / orig_h)
            self._thermal_zoom_ratio = ratio
        else:
            ratio = self._thermal_zoom_ratio

        new_w = max(int(orig_w * ratio), 10)
        new_h = max(int(orig_h * ratio), 10)

        resized = self._thermal_pil_orig.resize((new_w, new_h), Image.Resampling.LANCZOS)
        self._current_thermal_photo = ImageTk.PhotoImage(resized)

        self.thermal_canvas.delete("all")
        cx = (canv_w // 2) + self._thermal_img_offset[0]
        cy = (canv_h // 2) + self._thermal_img_offset[1]
        self.thermal_canvas.create_image(cx, cy, image=self._current_thermal_photo, anchor="center")

    def _on_thermal_canvas_resize(self, event=None):
        if self._current_thermal_img_path and self._thermal_fit_mode:
            self._render_thermal_image()

    def on_thermal_zoom(self, factor):
        if not self._thermal_pil_orig:
            return
        self._thermal_fit_mode = False
        self._thermal_zoom_ratio = max(0.1, min(self._thermal_zoom_ratio * factor, 8.0))
        self._render_thermal_image()
        pct = int(self._thermal_zoom_ratio * 100)
        self.thermal_preview_info.config(text=f"Zoom: {pct}%  |  Pan with left mouse button")

    def on_thermal_fit(self):
        self._thermal_fit_mode = True
        self._thermal_img_offset = [0, 0]
        self._render_thermal_image()
        self.thermal_preview_info.config(text="Zoom: Fit to Canvas")

    def _on_thermal_canvas_wheel(self, event):
        if event.delta > 0:
            self.on_thermal_zoom(1.15)
        else:
            self.on_thermal_zoom(0.87)

    def _on_thermal_canvas_press(self, event):
        self._thermal_drag_start = (event.x, event.y)

    def _on_thermal_canvas_drag(self, event):
        dx = event.x - self._thermal_drag_start[0]
        dy = event.y - self._thermal_drag_start[1]
        self._thermal_drag_start = (event.x, event.y)
        self._thermal_img_offset[0] += dx
        self._thermal_img_offset[1] += dy
        self._render_thermal_image()

    def on_plot_thermal_curves(self):
        if self._current_thermal_df is None:
            children = self.tree_thermal.get_children()
            for c in children:
                fn = self.tree_thermal.item(c, "values")[0]
                if os.path.splitext(fn)[1].lower() in [".csv", ".xlsx", ".xls", ".txt", ".dat"]:
                    fpath = self.vault.get_characterization_file_path(self.current_sample_id, "thermal_profile", fn)
                    if fpath and os.path.exists(fpath):
                        df, meta = load_thermal_data(fpath)
                        self._current_thermal_df = df
                        self._current_thermal_meta = meta
                        break

        if self._current_thermal_df is None:
            messagebox.showinfo("No Raw Data", "Please attach a spreadsheet or CSV data file first to generate automated plots.")
            return

        self.thermal_image_frame.pack_forget()
        self.thermal_plot_frame.pack(fill=tk.BOTH, expand=True)

        mat_name = self.vault.logbook.get(self.current_sample_id, {}).get("material_name", self.current_sample_id)
        title = f"{mat_name} — Adsorption Thermal Kinetics Profile"
        plot_thermal_curves(self._current_thermal_df, title=title, fig=self.thermal_fig)
        self.thermal_plot_canvas.draw()
        self.lbl_thermal_preview_title.config(text=f"📈 {title}")
        self.thermal_preview_info.config(text=f"Multi-channel profile plotted ({len(self._current_thermal_meta.get('channels', []))} channels). Hotspot: {self._current_thermal_meta.get('hotspot_position')}.")

    def on_plot_thermal_heatmap(self):
        if self._current_thermal_df is None:
            children = self.tree_thermal.get_children()
            for c in children:
                fn = self.tree_thermal.item(c, "values")[0]
                if os.path.splitext(fn)[1].lower() in [".csv", ".xlsx", ".xls", ".txt", ".dat"]:
                    fpath = self.vault.get_characterization_file_path(self.current_sample_id, "thermal_profile", fn)
                    if fpath and os.path.exists(fpath):
                        df, meta = load_thermal_data(fpath)
                        self._current_thermal_df = df
                        self._current_thermal_meta = meta
                        break

        if self._current_thermal_df is None:
            messagebox.showinfo("No Raw Data", "Please attach a spreadsheet or CSV data file first to generate 2D heatmaps.")
            return

        self.thermal_image_frame.pack_forget()
        self.thermal_plot_frame.pack(fill=tk.BOTH, expand=True)

        mat_name = self.vault.logbook.get(self.current_sample_id, {}).get("material_name", self.current_sample_id)
        title = f"{mat_name} — 2D Spatio-Temporal Thermal Heat Map"
        plot_thermal_heatmap(self._current_thermal_df, title=title, fig=self.thermal_fig)
        self.thermal_plot_canvas.draw()
        self.lbl_thermal_preview_title.config(text=f"🗺️ {title}")
        self.thermal_preview_info.config(text=f"2D Thermal Heatmap rendered. Position vs Time with Turbo colormap.")

    def on_export_thermal_plot(self):
        out_path = filedialog.asksaveasfilename(
            title="Export Publication Thermal Graph",
            defaultextension=".png",
            filetypes=[("PNG Image (High-Res)", "*.png"), ("PDF Document (Vector)", "*.pdf"), ("SVG Vector", "*.svg"), ("All Files", "*.*")]
        )
        if out_path:
            try:
                self.thermal_fig.savefig(out_path, dpi=300, bbox_inches="tight")
                messagebox.showinfo("Export Successful", f"High-resolution plot saved to:\n{out_path}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Could not export plot:\n{e}")

    def on_set_thermal_category(self, target_cat=None):
        sel = self.tree_thermal.selection()
        if not sel or not self.current_sample_id:
            messagebox.showinfo("Select File", "Please select a file from the list first.")
            return

        fn = self.tree_thermal.item(sel[0], "values")[0]

        if not target_cat:
            cat_win = tk.Toplevel(self)
            cat_win.title("Assign Profile Section")
            cat_win.geometry("340x240")
            cat_win.transient(self)
            cat_win.grab_set()

            tk.Label(cat_win, text=f"Assign Section for:\n{fn}", font=("Segoe UI", 9, "bold")).pack(pady=10)
            sel_var = tk.StringVar(value="↕️ Vertical Profile")

            cats = [
                "↕️ Vertical Profile",
                "↔️ Horizontal Profile",
                "⚖️ Hori vs Ver Comparison",
                "🗺️ 2D Thermal Heatmap",
                "📄 Raw Thermocouple Data",
                "📊 General Profile"
            ]
            for c in cats:
                tk.Radiobutton(cat_win, text=c, variable=sel_var, value=c, anchor="w").pack(fill=tk.X, padx=30, pady=2)

            def apply_cat():
                c_chosen = sel_var.get()
                self.vault.update_file_description(self.current_sample_id, "thermal_profile", fn, c_chosen)
                cat_win.destroy()
                self._refresh_thermal_tab()

            ttk.Button(cat_win, text="Confirm", command=apply_cat).pack(pady=10)
        else:
            self.vault.update_file_description(self.current_sample_id, "thermal_profile", fn, target_cat)
            self._refresh_thermal_tab()

    def _on_thermal_tree_right_click(self, event):
        iid = self.tree_thermal.identify_row(event.y)
        if iid:
            self.tree_thermal.selection_set(iid)
            menu = tk.Menu(self, tearoff=0)
            menu.add_command(label="Set as ↕️ Vertical Profile", command=lambda: self.on_set_thermal_category("Vertical Profile"))
            menu.add_command(label="Set as ↔️ Horizontal Profile", command=lambda: self.on_set_thermal_category("Horizontal Profile"))
            menu.add_command(label="Set as ⚖️ Hori vs Ver Comparison", command=lambda: self.on_set_thermal_category("Hori vs Ver Comparison"))
            menu.add_command(label="Set as 🗺️ 2D Thermal Heatmap", command=lambda: self.on_set_thermal_category("2D Thermal Heatmap"))
            menu.add_command(label="Set as 📄 Raw Data", command=lambda: self.on_set_thermal_category("Raw Data"))
            menu.add_separator()
            menu.add_command(label="📂 Open in External Viewer", command=lambda: self.on_open_selected_file("thermal_profile"))
            menu.add_command(label="🗑️ Delete File", command=lambda: self.on_delete_file("thermal_profile"))
            menu.post(event.x_root, event.y_root)

    def _apply_thermal_filter(self, event=None):
        self._refresh_thermal_tab()

    def _refresh_thermal_tab(self):
        for item in self.tree_thermal.get_children():
            self.tree_thermal.delete(item)

        if not self.current_sample_id or self.current_sample_id not in self.vault.logbook:
            self.thermal_t0_var.set(28.0)
            self.thermal_tmax_var.set(36.0)
            self.thermal_delta_var.set(8.0)
            self.thermal_tpeak_var.set(3.0)
            self.thermal_hotspot_var.set("V7 (Center)")
            self.thermal_duration_var.set(22.0)
            self.thermal_notes_var.set("")
            self.thermal_canvas.delete("all")
            self.lbl_thermal_preview_title.config(text="📈 Interactive Thermal Graph & Profile Viewer")
            self.thermal_preview_info.config(text="Select a sample to inspect thermal profiles.")
            return

        data = self.vault.logbook[self.current_sample_id]
        tech_data = data.get("characterizations", {}).get("thermal_profile", {})
        files = tech_data.get("files", [])

        filter_text = self.thermal_cat_filter_var.get()

        for f in files:
            fn = f.get("filename", "-")
            desc = f.get("description", "")
            if not desc or desc.startswith("Discovered"):
                desc = detect_profile_category(fn)

            if "Vertical" in filter_text and "vert" not in desc.lower():
                continue
            if "Horizontal" in filter_text and ("hori" not in desc.lower() or "ver" in desc.lower()):
                continue
            if "Comparison" in filter_text and "comparison" not in desc.lower() and "hori vs ver" not in desc.lower():
                continue
            if "Heatmap" in filter_text and "heat" not in desc.lower() and "map" not in desc.lower():
                continue
            if "Raw" in filter_text and "raw" not in desc.lower() and os.path.splitext(fn)[1].lower() not in [".csv", ".xlsx", ".xls", ".txt", ".dat"]:
                continue

            sz = f.get("size_bytes", 0) / 1024.0
            self.tree_thermal.insert("", tk.END, values=(
                fn,
                desc,
                f"{sz:.1f} KB"
            ))

        self.thermal_t0_var.set(float(tech_data.get("t_initial_c", 28.0)))
        self.thermal_tmax_var.set(float(tech_data.get("t_max_c", 36.0)))
        self.thermal_delta_var.set(float(tech_data.get("delta_t_c", 8.0)))
        self.thermal_tpeak_var.set(float(tech_data.get("time_to_peak_min", 3.0)))
        self.thermal_hotspot_var.set(tech_data.get("hotspot_position", "V7 (Center)"))
        self.thermal_duration_var.set(float(tech_data.get("duration_min", 22.0)))
        self.thermal_notes_var.set(tech_data.get("notes", ""))

        children = self.tree_thermal.get_children()
        if children:
            self.tree_thermal.selection_set(children[0])
            self.on_thermal_file_selected()
        else:
            self.thermal_canvas.delete("all")
            self._display_thermal_welcome()

    def _display_thermal_welcome(self):
        self.thermal_plot_frame.pack_forget()
        self.thermal_image_frame.pack(fill=tk.BOTH, expand=True)
        self.thermal_canvas.delete("all")

        canv_w = max(self.thermal_canvas.winfo_width(), 400)
        canv_h = max(self.thermal_canvas.winfo_height(), 350)
        cx = canv_w // 2
        cy = canv_h // 2

        self.thermal_canvas.create_text(
            cx, cy - 60,
            text="🌡️ Adsorption Exotherm Profiles & Mapping",
            fill="#ffb703", font=("Segoe UI", 14, "bold")
        )
        self.thermal_canvas.create_text(
            cx, cy,
            text="No thermal files attached yet for this sample.\n\n"
                 "• Click '➕ Attach Image(s)' to add Vertical, Horizontal, Comparison, or Heatmap graphs.\n"
                 "• Click '➕ Raw Data' to load CSV/Excel thermocouple data for automated plotting.\n"
                 "• Use 'Section Filter' to organize by Profile Type.",
            fill="#e0e0e0", font=("Segoe UI", 10), justify=tk.CENTER
        )
        self.lbl_thermal_preview_title.config(text="📈 Interactive Thermal Graph & Profile Viewer")
        self.thermal_preview_info.config(text="Click '➕ Attach Image(s)' or '➕ Raw Data' to begin.")

    def on_save_thermal_params(self):
        if not self.current_sample_id:
            return
        props = {
            "t_initial_c": float(self.thermal_t0_var.get()),
            "t_max_c": float(self.thermal_tmax_var.get()),
            "delta_t_c": float(self.thermal_delta_var.get()),
            "time_to_peak_min": float(self.thermal_tpeak_var.get()),
            "hotspot_position": self.thermal_hotspot_var.get(),
            "duration_min": float(self.thermal_duration_var.get()),
            "notes": self.thermal_notes_var.get()
        }
        self.vault.save_technique_properties(self.current_sample_id, "thermal_profile", props, notes=self.thermal_notes_var.get())
        messagebox.showinfo("Saved", f"Adsorption thermal kinetics parameters saved for sample {self.current_sample_id}.")

    # ==================== TAB: SEM / TEM ELECTRON MICROSCOPY ====================

    def _build_sem_tem_tab(self, parent):
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill=tk.X, pady=(0, 8))

        filetypes = [
            ("Microscopy & Image Files", "*.tif;*.tiff;*.png;*.jpg;*.jpeg;*.bmp;*.gif;*.dm3;*.dm4;*.txt;*.csv"),
            ("All Files", "*.*")
        ]
        ttk.Button(toolbar, text="➕ Attach Micrograph(s) / EDX", command=lambda: self.on_attach_generic_file("sem_tem", filetypes)).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="🗑️ Delete Selected", command=lambda: self.on_delete_file("sem_tem")).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="🔍 Open in External Viewer", command=lambda: self.on_open_selected_file("sem_tem")).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="📁 Open Folder", command=lambda: self.on_open_tech_folder("sem_tem")).pack(side=tk.LEFT, padx=3)

        # Main Paned layout: Left (File list + morphology params) & Right (Interactive Image Viewer)
        sem_pane = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
        sem_pane.pack(fill=tk.BOTH, expand=True)

        # Left Column Frame
        left_frame = ttk.Frame(sem_pane, padding=(0, 0, 6, 0))
        sem_pane.add(left_frame, weight=1)

        cols = ("fn", "uploaded", "size")
        self.tree_sem = ttk.Treeview(left_frame, columns=cols, show="headings", selectmode="extended", height=7)
        self.tree_sem.heading("fn", text="Microscopy Micrograph / EDX File")
        self.tree_sem.heading("uploaded", text="Upload Date")
        self.tree_sem.heading("size", text="Size")
        self.tree_sem.column("fn", width=220, anchor="w")
        self.tree_sem.column("uploaded", width=110, anchor="center")
        self.tree_sem.column("size", width=70, anchor="e")

        sem_scroll = ttk.Scrollbar(left_frame, orient="vertical", command=self.tree_sem.yview)
        self.tree_sem.configure(yscrollcommand=sem_scroll.set)
        self.tree_sem.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        sem_scroll.pack(side=tk.LEFT, fill=tk.Y)

        self.tree_sem.bind("<<TreeviewSelect>>", self.on_sem_image_selected)
        self.tree_sem.bind("<Double-1>", lambda e: self.on_open_selected_file("sem_tem"))

        # SEM/TEM Parameters Frame
        param_frame = ttk.LabelFrame(left_frame, text=" Morphological & Nanostructure Analysis (SEM / TEM) ", padding=8)
        param_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(8, 0))

        p_grid = ttk.Frame(param_frame)
        p_grid.pack(fill=tk.X)

        ttk.Label(p_grid, text="Primary Particle Size (nm):").grid(row=0, column=0, sticky="w", pady=3)
        self.sem_particle_size_var = tk.DoubleVar(value=0.0)
        ttk.Spinbox(p_grid, from_=0.0, to=50000.0, increment=1.0, textvariable=self.sem_particle_size_var, width=14).grid(row=0, column=1, sticky="w", padx=4, pady=3)

        ttk.Label(p_grid, text="Macropore Size (μm):").grid(row=0, column=2, sticky="w", padx=(10, 0), pady=3)
        self.sem_macropore_var = tk.DoubleVar(value=0.0)
        ttk.Spinbox(p_grid, from_=0.0, to=1000.0, increment=0.5, textvariable=self.sem_macropore_var, width=14).grid(row=0, column=3, sticky="w", padx=4, pady=3)

        ttk.Label(p_grid, text="Wall / Skeleton (μm):").grid(row=1, column=0, sticky="w", pady=3)
        self.sem_wall_thick_var = tk.DoubleVar(value=0.0)
        ttk.Spinbox(p_grid, from_=0.0, to=1000.0, increment=0.1, textvariable=self.sem_wall_thick_var, width=14).grid(row=1, column=1, sticky="w", padx=4, pady=3)

        ttk.Label(p_grid, text="Morphology Type:").grid(row=1, column=2, sticky="w", padx=(10, 0), pady=3)
        self.sem_morphology_var = tk.StringVar(value="Porous Monolith")
        ttk.Combobox(p_grid, values=["Porous Monolith", "Spherical Beads", "Fibrous / Nanowires", "Platelets / Sheets", "Hierarchical Core-Shell", "Amorphous Aggregate"], textvariable=self.sem_morphology_var, width=14).grid(row=1, column=3, sticky="w", padx=4, pady=3)

        ttk.Label(p_grid, text="EDX Ratio / Notes:").grid(row=2, column=0, sticky="w", pady=3)
        self.sem_edx_notes_var = tk.StringVar(value="")
        ttk.Entry(p_grid, textvariable=self.sem_edx_notes_var, width=38).grid(row=2, column=1, columnspan=3, sticky="w", padx=4, pady=3)

        btn_save_sem = ttk.Button(param_frame, text="💾 Save SEM Parameters", command=self.on_save_sem_params)
        btn_save_sem.pack(anchor="e", pady=(6, 0))

        # Right Column Frame: Integrated Micrograph Viewer
        right_frame = ttk.LabelFrame(sem_pane, text=" Micrograph Preview ", padding=6)
        sem_pane.add(right_frame, weight=2)

        self.sem_preview_info = ttk.Label(right_frame, text="Select an image from the list on the left to preview.", font=("Segoe UI", 9, "italic"))
        self.sem_preview_info.pack(side=tk.TOP, anchor="w", pady=(0, 4))

        self.sem_canvas = tk.Canvas(right_frame, bg="#1e1e1e", highlightthickness=0)
        self.sem_canvas.pack(fill=tk.BOTH, expand=True)
        self.sem_canvas.bind("<Configure>", self._on_sem_canvas_resize)

        self._current_sem_img_path = None
        self._current_sem_photo = None

    def on_sem_image_selected(self, event=None):
        sel = self.tree_sem.selection()
        if not sel or not self.current_sample_id:
            return
        fn = self.tree_sem.item(sel[0], "values")[0]
        fpath = self.vault.get_characterization_file_path(self.current_sample_id, "sem_tem", fn)
        if fpath and os.path.exists(fpath):
            self.display_sem_image(fpath)

    def display_sem_image(self, fpath):
        self._current_sem_img_path = fpath
        fn = os.path.basename(fpath)
        ext = os.path.splitext(fn)[1].lower()

        if ext not in [".tif", ".tiff", ".png", ".jpg", ".jpeg", ".bmp", ".gif"]:
            self.sem_canvas.delete("all")
            self.sem_preview_info.config(text=f"📄 {fn} (Non-image file — use 'Open in External Viewer')")
            return

        try:
            with Image.open(fpath) as pil_img:
                orig_w, orig_h = pil_img.size
                canv_w = max(self.sem_canvas.winfo_width(), 200)
                canv_h = max(self.sem_canvas.winfo_height(), 200)

                # Maintain aspect ratio
                ratio = min(canv_w / orig_w, canv_h / orig_h)
                new_w = max(int(orig_w * ratio), 1)
                new_h = max(int(orig_h * ratio), 1)

                resized = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                self._current_sem_photo = ImageTk.PhotoImage(resized)

                self.sem_canvas.delete("all")
                # Center image on canvas
                cx = canv_w // 2
                cy = canv_h // 2
                self.sem_canvas.create_image(cx, cy, image=self._current_sem_photo, anchor="center")

                sz_kb = os.path.getsize(fpath) / 1024.0
                self.sem_preview_info.config(
                    text=f"🖼️ {fn}  |  Resolution: {orig_w} × {orig_h} px  |  Size: {sz_kb:.1f} KB"
                )
        except Exception as e:
            self.sem_canvas.delete("all")
            self.sem_preview_info.config(text=f"⚠️ Could not preview image: {e}")

    def _on_sem_canvas_resize(self, event=None):
        if self._current_sem_img_path and os.path.exists(self._current_sem_img_path):
            self.display_sem_image(self._current_sem_img_path)

    def _refresh_sem_tem_tab(self):
        for item in self.tree_sem.get_children():
            self.tree_sem.delete(item)

        if not self.current_sample_id or self.current_sample_id not in self.vault.logbook:
            self.sem_particle_size_var.set(0.0)
            self.sem_macropore_var.set(0.0)
            self.sem_wall_thick_var.set(0.0)
            self.sem_morphology_var.set("Porous Monolith")
            self.sem_edx_notes_var.set("")
            self.sem_canvas.delete("all")
            self.sem_preview_info.config(text="Select a sample to view microscopy images.")
            self._current_sem_img_path = None
            return

        data = self.vault.logbook[self.current_sample_id]
        tech_data = data.get("characterizations", {}).get("sem_tem", {})
        files = tech_data.get("files", [])
        for f in files:
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

        # Auto-select and preview first image if available
        children = self.tree_sem.get_children()
        if children:
            self.tree_sem.selection_set(children[0])
            self.on_sem_image_selected()
        else:
            self.sem_canvas.delete("all")
            self.sem_preview_info.config(text="No micrograph images attached. Click '+ Attach Micrograph(s)' to add.")
            self._current_sem_img_path = None

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

        filetypes = [
            ("Rheology & Graph Files", "*.png;*.jpg;*.jpeg;*.tif;*.tiff;*.bmp;*.csv;*.xlsx;*.xls;*.txt;*.rfd"),
            ("All Files", "*.*")
        ]
        ttk.Button(toolbar, text="➕ Attach Rheology Curve / Graph(s)", command=lambda: self.on_attach_generic_file("rheology", filetypes)).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="🗑️ Delete Selected", command=lambda: self.on_delete_file("rheology")).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="🔍 Open in External Viewer", command=lambda: self.on_open_selected_file("rheology")).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="📁 Open Folder", command=lambda: self.on_open_tech_folder("rheology")).pack(side=tk.LEFT, padx=3)

        # Main Paned layout: Left (File list + rheological parameters) & Right (Interactive Curve / Graph Viewer)
        rheo_pane = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
        rheo_pane.pack(fill=tk.BOTH, expand=True)

        # Left Column Frame
        left_frame = ttk.Frame(rheo_pane, padding=(0, 0, 6, 0))
        rheo_pane.add(left_frame, weight=1)

        cols = ("fn", "uploaded", "size")
        self.tree_rheo = ttk.Treeview(left_frame, columns=cols, show="headings", selectmode="extended", height=7)
        self.tree_rheo.heading("fn", text="Rheology Curve / Graph File")
        self.tree_rheo.heading("uploaded", text="Upload Date")
        self.tree_rheo.heading("size", text="Size")
        self.tree_rheo.column("fn", width=220, anchor="w")
        self.tree_rheo.column("uploaded", width=110, anchor="center")
        self.tree_rheo.column("size", width=70, anchor="e")

        rheo_scroll = ttk.Scrollbar(left_frame, orient="vertical", command=self.tree_rheo.yview)
        self.tree_rheo.configure(yscrollcommand=rheo_scroll.set)
        self.tree_rheo.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        rheo_scroll.pack(side=tk.LEFT, fill=tk.Y)

        self.tree_rheo.bind("<<TreeviewSelect>>", self.on_rheology_file_selected)
        self.tree_rheo.bind("<Double-1>", lambda e: self.on_open_selected_file("rheology"))

        # Rheology Key Parameters Box
        param_frame = ttk.LabelFrame(left_frame, text=" Rheological Parameters (Slurry, Paste & Printability) ", padding=8)
        param_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(8, 0))

        p_grid = ttk.Frame(param_frame)
        p_grid.pack(fill=tk.X)

        ttk.Label(p_grid, text="Zero-Shear Viscosity η₀ (Pa·s):").grid(row=0, column=0, sticky="w", pady=3)
        self.rheo_visc_var = tk.DoubleVar(value=0.0)
        ttk.Spinbox(p_grid, from_=0.0, to=100000.0, increment=1.0, textvariable=self.rheo_visc_var, width=14).grid(row=0, column=1, sticky="w", padx=4, pady=3)

        ttk.Label(p_grid, text="Yield Stress τ₀ (Pa):").grid(row=0, column=2, sticky="w", padx=(10, 0), pady=3)
        self.rheo_yield_var = tk.DoubleVar(value=0.0)
        ttk.Spinbox(p_grid, from_=0.0, to=10000.0, increment=0.5, textvariable=self.rheo_yield_var, width=14).grid(row=0, column=3, sticky="w", padx=4, pady=3)

        ttk.Label(p_grid, text="Storage Modulus G' (Pa):").grid(row=1, column=0, sticky="w", pady=3)
        self.rheo_gp_var = tk.DoubleVar(value=0.0)
        ttk.Spinbox(p_grid, from_=0.0, to=500000.0, increment=10.0, textvariable=self.rheo_gp_var, width=14).grid(row=1, column=1, sticky="w", padx=4, pady=3)

        ttk.Label(p_grid, text="Loss Modulus G'' (Pa):").grid(row=1, column=2, sticky="w", padx=(10, 0), pady=3)
        self.rheo_gpp_var = tk.DoubleVar(value=0.0)
        ttk.Spinbox(p_grid, from_=0.0, to=500000.0, increment=10.0, textvariable=self.rheo_gpp_var, width=14).grid(row=1, column=3, sticky="w", padx=4, pady=3)

        ttk.Label(p_grid, text="Loss Factor (tan δ):").grid(row=2, column=0, sticky="w", pady=3)
        self.rheo_tan_delta_var = tk.DoubleVar(value=0.0)
        ttk.Spinbox(p_grid, from_=0.0, to=10.0, increment=0.01, textvariable=self.rheo_tan_delta_var, width=14).grid(row=2, column=1, sticky="w", padx=4, pady=3)

        ttk.Label(p_grid, text="Flow Behavior:").grid(row=2, column=2, sticky="w", padx=(10, 0), pady=3)
        self.rheo_behavior_var = tk.StringVar(value="Shear-Thinning (Pseudoplastic)")
        ttk.Combobox(p_grid, values=["Shear-Thinning (Pseudoplastic)", "Newtonian", "Shear-Thickening (Dilatant)", "Bingham Plastic", "Viscoelastic Gel"], textvariable=self.rheo_behavior_var, width=18).grid(row=2, column=3, sticky="w", padx=4, pady=3)

        btn_save_rheo = ttk.Button(param_frame, text="💾 Save Rheology Parameters", command=self.on_save_rheology_params)
        btn_save_rheo.pack(anchor="e", pady=(6, 0))

        # Right Column Frame: Integrated Rheology Curve / Graph Viewer
        right_frame = ttk.LabelFrame(rheo_pane, text=" Rheology Curve & Viscosity Graph Preview ", padding=6)
        rheo_pane.add(right_frame, weight=2)

        self.rheo_preview_info = ttk.Label(right_frame, text="Select a rheology graph from the list on the left to preview.", font=("Segoe UI", 9, "italic"))
        self.rheo_preview_info.pack(side=tk.TOP, anchor="w", pady=(0, 4))

        self.rheo_canvas = tk.Canvas(right_frame, bg="#ffffff", highlightthickness=1, highlightbackground="#d3d3d3")
        self.rheo_canvas.pack(fill=tk.BOTH, expand=True)
        self.rheo_canvas.bind("<Configure>", self._on_rheo_canvas_resize)

        self._current_rheo_img_path = None
        self._current_rheo_photo = None

    def on_rheology_file_selected(self, event=None):
        sel = self.tree_rheo.selection()
        if not sel or not self.current_sample_id:
            return
        fn = self.tree_rheo.item(sel[0], "values")[0]
        fpath = self.vault.get_characterization_file_path(self.current_sample_id, "rheology", fn)
        if fpath and os.path.exists(fpath):
            self.display_rheology_image(fpath)

    def display_rheology_image(self, fpath):
        self._current_rheo_img_path = fpath
        fn = os.path.basename(fpath)
        ext = os.path.splitext(fn)[1].lower()

        if ext not in [".tif", ".tiff", ".png", ".jpg", ".jpeg", ".bmp", ".gif"]:
            self.rheo_canvas.delete("all")
            self.rheo_preview_info.config(text=f"📄 {fn} (Raw data file — use 'Open in External Viewer')")
            return

        try:
            with Image.open(fpath) as pil_img:
                orig_w, orig_h = pil_img.size
                canv_w = max(self.rheo_canvas.winfo_width(), 200)
                canv_h = max(self.rheo_canvas.winfo_height(), 200)

                # Maintain aspect ratio
                ratio = min(canv_w / orig_w, canv_h / orig_h)
                new_w = max(int(orig_w * ratio), 1)
                new_h = max(int(orig_h * ratio), 1)

                resized = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                self._current_rheo_photo = ImageTk.PhotoImage(resized)

                self.rheo_canvas.delete("all")
                # Center image on canvas
                cx = canv_w // 2
                cy = canv_h // 2
                self.rheo_canvas.create_image(cx, cy, image=self._current_rheo_photo, anchor="center")

                sz_kb = os.path.getsize(fpath) / 1024.0
                self.rheo_preview_info.config(
                    text=f"📊 {fn}  |  Resolution: {orig_w} × {orig_h} px  |  Size: {sz_kb:.1f} KB"
                )
        except Exception as e:
            self.rheo_canvas.delete("all")
            self.rheo_preview_info.config(text=f"⚠️ Could not preview image: {e}")

    def _on_rheo_canvas_resize(self, event=None):
        if self._current_rheo_img_path and os.path.exists(self._current_rheo_img_path):
            self.display_rheology_image(self._current_rheo_img_path)

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
            self.rheo_canvas.delete("all")
            self.rheo_preview_info.config(text="Select a sample to inspect rheology curves.")
            self._current_rheo_img_path = None
            return

        data = self.vault.logbook[self.current_sample_id]
        tech_data = data.get("characterizations", {}).get("rheology", {})
        files = tech_data.get("files", [])
        for f in files:
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

        # Auto-select and preview first image if available
        children = self.tree_rheo.get_children()
        if children:
            self.tree_rheo.selection_set(children[0])
            self.on_rheology_file_selected()
        else:
            self.rheo_canvas.delete("all")
            self.rheo_preview_info.config(text="No rheology curves attached. Click '+ Attach Rheology Curve / Graph(s)' to add.")
            self._current_rheo_img_path = None

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

    # ==================== TAB: COMPUTED TOMOGRAPHY (MICRO-CT) ====================

    def _build_tomography_tab(self, parent):
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill=tk.X, pady=(0, 8))

        filetypes = [
            ("Tomography & 3D Datasets", "*.tif;*.tiff;*.png;*.jpg;*.jpeg;*.bmp;*.raw;*.vol;*.vgi;*.stl;*.txt;*.csv;*.pdf"),
            ("All Files", "*.*")
        ]
        ttk.Button(toolbar, text="➕ Attach Micro-CT Slice / Scan(s)", command=lambda: self.on_attach_generic_file("tomography", filetypes)).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="🗑️ Delete Selected", command=lambda: self.on_delete_file("tomography")).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="🔍 Open in External 3D Viewer", command=lambda: self.on_open_selected_file("tomography")).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="📁 Open Folder", command=lambda: self.on_open_tech_folder("tomography")).pack(side=tk.LEFT, padx=3)

        # Main Paned layout: Left (File list + 3D morphometry params) & Right (Interactive Slice Viewer)
        tomo_pane = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
        tomo_pane.pack(fill=tk.BOTH, expand=True)

        # Left Column Frame
        left_frame = ttk.Frame(tomo_pane, padding=(0, 0, 6, 0))
        tomo_pane.add(left_frame, weight=1)

        cols = ("fn", "uploaded", "size")
        self.tree_tomography = ttk.Treeview(left_frame, columns=cols, show="headings", selectmode="extended", height=7)
        self.tree_tomography.heading("fn", text="Micro-CT Slice / Reconstruction File")
        self.tree_tomography.heading("uploaded", text="Upload Date")
        self.tree_tomography.heading("size", text="Size")
        self.tree_tomography.column("fn", width=220, anchor="w")
        self.tree_tomography.column("uploaded", width=110, anchor="center")
        self.tree_tomography.column("size", width=70, anchor="e")

        tomo_scroll = ttk.Scrollbar(left_frame, orient="vertical", command=self.tree_tomography.yview)
        self.tree_tomography.configure(yscrollcommand=tomo_scroll.set)
        self.tree_tomography.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        tomo_scroll.pack(side=tk.LEFT, fill=tk.Y)

        self.tree_tomography.bind("<<TreeviewSelect>>", self.on_tomo_file_selected)
        self.tree_tomography.bind("<Double-1>", lambda e: self.on_open_selected_file("tomography"))

        # Tomography 3D Morphometry & Porosity Parameters Frame
        param_frame = ttk.LabelFrame(left_frame, text=" 3D Morphometry & Micro-CT Quantitative Parameters ", padding=8)
        param_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(8, 0))

        p_grid = ttk.Frame(param_frame)
        p_grid.pack(fill=tk.X)

        ttk.Label(p_grid, text="Total 3D Porosity (%):").grid(row=0, column=0, sticky="w", pady=3)
        self.tomo_porosity_var = tk.DoubleVar(value=0.0)
        ttk.Spinbox(p_grid, from_=0.0, to=100.0, increment=0.1, textvariable=self.tomo_porosity_var, width=14).grid(row=0, column=1, sticky="w", padx=4, pady=3)

        ttk.Label(p_grid, text="Mean Pore / Throat (μm):").grid(row=0, column=2, sticky="w", padx=(10, 0), pady=3)
        self.tomo_pore_diam_var = tk.DoubleVar(value=0.0)
        ttk.Spinbox(p_grid, from_=0.0, to=5000.0, increment=0.5, textvariable=self.tomo_pore_diam_var, width=14).grid(row=0, column=3, sticky="w", padx=4, pady=3)

        ttk.Label(p_grid, text="Strut / Wall Thickness (μm):").grid(row=1, column=0, sticky="w", pady=3)
        self.tomo_wall_thick_var = tk.DoubleVar(value=0.0)
        ttk.Spinbox(p_grid, from_=0.0, to=2000.0, increment=0.1, textvariable=self.tomo_wall_thick_var, width=14).grid(row=1, column=1, sticky="w", padx=4, pady=3)

        ttk.Label(p_grid, text="Geometric Tortuosity (τ):").grid(row=1, column=2, sticky="w", padx=(10, 0), pady=3)
        self.tomo_tortuosity_var = tk.DoubleVar(value=1.0)
        ttk.Spinbox(p_grid, from_=1.0, to=20.0, increment=0.05, textvariable=self.tomo_tortuosity_var, width=14).grid(row=1, column=3, sticky="w", padx=4, pady=3)

        ttk.Label(p_grid, text="Voxel Size (μm/voxel):").grid(row=2, column=0, sticky="w", pady=3)
        self.tomo_voxel_size_var = tk.DoubleVar(value=5.0)
        ttk.Spinbox(p_grid, from_=0.01, to=500.0, increment=0.1, textvariable=self.tomo_voxel_size_var, width=14).grid(row=2, column=1, sticky="w", padx=4, pady=3)

        ttk.Label(p_grid, text="Scanner / Acquisition:").grid(row=2, column=2, sticky="w", padx=(10, 0), pady=3)
        self.tomo_notes_var = tk.StringVar(value="")
        ttk.Entry(p_grid, textvariable=self.tomo_notes_var, width=22).grid(row=2, column=3, sticky="w", padx=4, pady=3)

        btn_save_tomo = ttk.Button(param_frame, text="💾 Save Tomography Parameters", command=self.on_save_tomography_params)
        btn_save_tomo.pack(anchor="e", pady=(6, 0))

        # Right Column Frame: Integrated Micro-CT Slice Viewer
        right_frame = ttk.LabelFrame(tomo_pane, text=" Micro-CT Cross-Section & Slice Preview ", padding=6)
        tomo_pane.add(right_frame, weight=2)

        self.tomo_preview_info = ttk.Label(right_frame, text="Select a micro-CT slice from the list on the left to preview.", font=("Segoe UI", 9, "italic"))
        self.tomo_preview_info.pack(side=tk.TOP, anchor="w", pady=(0, 4))

        self.tomo_canvas = tk.Canvas(right_frame, bg="#121212", highlightthickness=0)
        self.tomo_canvas.pack(fill=tk.BOTH, expand=True)
        self.tomo_canvas.bind("<Configure>", self._on_tomo_canvas_resize)

        self._current_tomo_img_path = None
        self._current_tomo_photo = None

    def on_tomo_file_selected(self, event=None):
        sel = self.tree_tomography.selection()
        if not sel or not self.current_sample_id:
            return
        fn = self.tree_tomography.item(sel[0], "values")[0]
        fpath = self.vault.get_characterization_file_path(self.current_sample_id, "tomography", fn)
        if fpath and os.path.exists(fpath):
            self.display_tomo_slice(fpath)

    def display_tomo_slice(self, fpath):
        self._current_tomo_img_path = fpath
        fn = os.path.basename(fpath)
        ext = os.path.splitext(fn)[1].lower()

        if ext not in [".tif", ".tiff", ".png", ".jpg", ".jpeg", ".bmp", ".gif"]:
            self.tomo_canvas.delete("all")
            self.tomo_preview_info.config(text=f"🧊 {fn} (3D Volume / Mesh / Raw dataset — use 'Open in External 3D Viewer')")
            return

        try:
            with Image.open(fpath) as pil_img:
                orig_w, orig_h = pil_img.size
                canv_w = max(self.tomo_canvas.winfo_width(), 200)
                canv_h = max(self.tomo_canvas.winfo_height(), 200)

                ratio = min(canv_w / orig_w, canv_h / orig_h)
                new_w = max(int(orig_w * ratio), 1)
                new_h = max(int(orig_h * ratio), 1)

                resized = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                self._current_tomo_photo = ImageTk.PhotoImage(resized)

                self.tomo_canvas.delete("all")
                cx = canv_w // 2
                cy = canv_h // 2
                self.tomo_canvas.create_image(cx, cy, image=self._current_tomo_photo, anchor="center")

                sz_kb = os.path.getsize(fpath) / 1024.0
                self.tomo_preview_info.config(
                    text=f"🧊 {fn}  |  Resolution: {orig_w} × {orig_h} px  |  Size: {sz_kb:.1f} KB"
                )
        except Exception as e:
            self.tomo_canvas.delete("all")
            self.tomo_preview_info.config(text=f"⚠️ Could not preview slice: {e}")

    def _on_tomo_canvas_resize(self, event=None):
        if self._current_tomo_img_path and os.path.exists(self._current_tomo_img_path):
            self.display_tomo_slice(self._current_tomo_img_path)

    def _refresh_tomography_tab(self):
        for item in self.tree_tomography.get_children():
            self.tree_tomography.delete(item)

        if not self.current_sample_id or self.current_sample_id not in self.vault.logbook:
            self.tomo_porosity_var.set(0.0)
            self.tomo_pore_diam_var.set(0.0)
            self.tomo_wall_thick_var.set(0.0)
            self.tomo_tortuosity_var.set(1.0)
            self.tomo_voxel_size_var.set(5.0)
            self.tomo_notes_var.set("")
            self.tomo_canvas.delete("all")
            self.tomo_preview_info.config(text="Select a sample to inspect micro-CT slices.")
            self._current_tomo_img_path = None
            return

        data = self.vault.logbook[self.current_sample_id]
        tech_data = data.get("characterizations", {}).get("tomography", {})
        files = tech_data.get("files", [])
        for f in files:
            sz = f.get("size_bytes", 0) / 1024.0
            self.tree_tomography.insert("", tk.END, values=(
                f.get("filename", "-"),
                f.get("uploaded_at", "-"),
                f"{sz:.1f} KB"
            ))

        self.tomo_porosity_var.set(float(tech_data.get("total_porosity_pct", 0.0)))
        self.tomo_pore_diam_var.set(float(tech_data.get("mean_pore_diameter_um", 0.0)))
        self.tomo_wall_thick_var.set(float(tech_data.get("strut_wall_thickness_um", 0.0)))
        self.tomo_tortuosity_var.set(float(tech_data.get("tortuosity_factor", 1.0)))
        self.tomo_voxel_size_var.set(float(tech_data.get("voxel_size_um", 5.0)))
        self.tomo_notes_var.set(tech_data.get("scanner_notes", ""))

        children = self.tree_tomography.get_children()
        if children:
            self.tree_tomography.selection_set(children[0])
            self.on_tomo_file_selected()
        else:
            self.tomo_canvas.delete("all")
            self.tomo_preview_info.config(text="No micro-CT slices attached. Click '+ Attach Micro-CT Slice / Scan(s)' to add.")
            self._current_tomo_img_path = None

    def on_save_tomography_params(self):
        if not self.current_sample_id:
            return
        data = self.vault.logbook[self.current_sample_id]
        tomo_dict = data.setdefault("characterizations", {}).setdefault("tomography", {})
        tomo_dict["total_porosity_pct"] = float(self.tomo_porosity_var.get())
        tomo_dict["mean_pore_diameter_um"] = float(self.tomo_pore_diam_var.get())
        tomo_dict["strut_wall_thickness_um"] = float(self.tomo_wall_thick_var.get())
        tomo_dict["tortuosity_factor"] = float(self.tomo_tortuosity_var.get())
        tomo_dict["voxel_size_um"] = float(self.tomo_voxel_size_var.get())
        tomo_dict["scanner_notes"] = self.tomo_notes_var.get().strip()
        self.vault.save_logbook()
        messagebox.showinfo("Saved", f"Computed Tomography parameters saved for {self.current_sample_id}.")

    # ==================== TAB: MERCURY INTRUSION POROSIMETRY (MIP) ====================

    def _build_hg_porosimetry_tab(self, parent):
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill=tk.X, pady=(0, 8))

        filetypes = [
            ("MIP & Graph Files", "*.txt;*.csv;*.xlsx;*.xls;*.dat;*.png;*.jpg;*.jpeg;*.tif;*.pdf"),
            ("All Files", "*.*")
        ]
        ttk.Button(toolbar, text="➕ Attach MIP File (.txt, .csv, .xlsx, .dat)", command=lambda: self.on_attach_generic_file("hg_porosimetry", filetypes)).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="🗑️ Delete File", command=lambda: self.on_delete_file("hg_porosimetry")).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="📂 Open File", command=lambda: self.on_open_selected_file("hg_porosimetry")).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="📁 View in Folder", command=lambda: self.on_open_tech_folder("hg_porosimetry")).pack(side=tk.LEFT, padx=3)

        # Paned layout: Left (File list + quantitative parameters) & Right (Intrusion curve preview & notes)
        hg_pane = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
        hg_pane.pack(fill=tk.BOTH, expand=True)

        # Left Column Frame
        left_frame = ttk.Frame(hg_pane, padding=(0, 0, 6, 0))
        hg_pane.add(left_frame, weight=1)

        cols = ("fn", "uploaded", "size")
        self.tree_hg_porosimetry = ttk.Treeview(left_frame, columns=cols, show="headings", selectmode="browse", height=7)
        self.tree_hg_porosimetry.heading("fn", text="Mercury Porosimetry File")
        self.tree_hg_porosimetry.heading("uploaded", text="Upload Date")
        self.tree_hg_porosimetry.heading("size", text="Size")
        self.tree_hg_porosimetry.column("fn", width=220, anchor="w")
        self.tree_hg_porosimetry.column("uploaded", width=110, anchor="center")
        self.tree_hg_porosimetry.column("size", width=70, anchor="e")

        hg_scroll = ttk.Scrollbar(left_frame, orient="vertical", command=self.tree_hg_porosimetry.yview)
        self.tree_hg_porosimetry.configure(yscrollcommand=hg_scroll.set)
        self.tree_hg_porosimetry.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        hg_scroll.pack(side=tk.LEFT, fill=tk.Y)

        self.tree_hg_porosimetry.bind("<<TreeviewSelect>>", self.on_hg_file_selected)
        self.tree_hg_porosimetry.bind("<Double-1>", lambda e: self.on_open_selected_file("hg_porosimetry"))

        # MIP Porosity & Textural Properties Frame
        param_frame = ttk.LabelFrame(left_frame, text=" Mercury Intrusion Porosimetry (MIP) Textural Properties ", padding=8)
        param_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(8, 0))

        p_grid = ttk.Frame(param_frame)
        p_grid.pack(fill=tk.X)

        ttk.Label(p_grid, text="Total Intrusion Volume (cm³/g):").grid(row=0, column=0, sticky="w", pady=3)
        self.hg_total_vol_var = tk.DoubleVar(value=0.0)
        ttk.Spinbox(p_grid, from_=0.0, to=10.0, increment=0.01, textvariable=self.hg_total_vol_var, width=14).grid(row=0, column=1, sticky="w", padx=4, pady=3)

        ttk.Label(p_grid, text="Median Pore Diameter (Vol) (μm):").grid(row=0, column=2, sticky="w", padx=(10, 0), pady=3)
        self.hg_median_pore_diam_var = tk.DoubleVar(value=0.0)
        ttk.Spinbox(p_grid, from_=0.0, to=1000.0, increment=0.01, textvariable=self.hg_median_pore_diam_var, width=14).grid(row=0, column=3, sticky="w", padx=4, pady=3)

        ttk.Label(p_grid, text="Total Porosity (MIP) (%):").grid(row=1, column=0, sticky="w", pady=3)
        self.hg_porosity_var = tk.DoubleVar(value=0.0)
        ttk.Spinbox(p_grid, from_=0.0, to=100.0, increment=0.1, textvariable=self.hg_porosity_var, width=14).grid(row=1, column=1, sticky="w", padx=4, pady=3)

        ttk.Label(p_grid, text="Apparent Skeletal Density (g/cm³):").grid(row=1, column=2, sticky="w", padx=(10, 0), pady=3)
        self.hg_skeletal_dens_var = tk.DoubleVar(value=0.0)
        ttk.Spinbox(p_grid, from_=0.0, to=20.0, increment=0.01, textvariable=self.hg_skeletal_dens_var, width=14).grid(row=1, column=3, sticky="w", padx=4, pady=3)

        ttk.Label(p_grid, text="Bulk Density @ Filling (g/cm³):").grid(row=2, column=0, sticky="w", pady=3)
        self.hg_bulk_dens_var = tk.DoubleVar(value=0.0)
        ttk.Spinbox(p_grid, from_=0.0, to=10.0, increment=0.01, textvariable=self.hg_bulk_dens_var, width=14).grid(row=2, column=1, sticky="w", padx=4, pady=3)

        ttk.Label(p_grid, text="Average Pore Diameter (4V/A) (nm):").grid(row=2, column=2, sticky="w", padx=(10, 0), pady=3)
        self.hg_avg_pore_diam_var = tk.DoubleVar(value=0.0)
        ttk.Spinbox(p_grid, from_=0.0, to=50000.0, increment=1.0, textvariable=self.hg_avg_pore_diam_var, width=14).grid(row=2, column=3, sticky="w", padx=4, pady=3)

        btn_save_hg = ttk.Button(param_frame, text="💾 Save MIP Parameters", command=self.on_save_hg_porosimetry_params)
        btn_save_hg.pack(anchor="e", pady=(6, 0))

        # Right Column Frame: Integrated Intrusion Graph / Curve Preview & Notes
        right_frame = ttk.Frame(hg_pane)
        hg_pane.add(right_frame, weight=2)

        preview_box = ttk.LabelFrame(right_frame, text=" Mercury Intrusion Curve & Pore Distribution Preview ", padding=6)
        preview_box.pack(fill=tk.BOTH, expand=True)

        self.hg_preview_info = ttk.Label(preview_box, text="Select a porosimetry curve/image or data file from the left to inspect.", font=("Segoe UI", 9, "italic"))
        self.hg_preview_info.pack(side=tk.TOP, anchor="w", pady=(0, 4))

        self.hg_canvas = tk.Canvas(preview_box, bg="#ffffff", highlightthickness=1, highlightbackground="#d3d3d3")
        self.hg_canvas.pack(fill=tk.BOTH, expand=True)
        self.hg_canvas.bind("<Configure>", self._on_hg_canvas_resize)

        self._current_hg_img_path = None
        self._current_hg_photo = None

        # Washburn & Experimental Notes box
        notes_box = ttk.LabelFrame(right_frame, text=" Washburn Contact Parameters & Pore Throat Observations ", padding=6)
        notes_box.pack(fill=tk.X, pady=(6, 0))

        self.notes_hg_porosimetry = tk.Text(notes_box, height=3, font=("Segoe UI", 9))
        self.notes_hg_porosimetry.pack(fill=tk.X, expand=True, side=tk.LEFT)
        btn_save_notes = ttk.Button(notes_box, text="💾 Save\nNotes", command=lambda: self.on_save_tech_notes("hg_porosimetry"))
        btn_save_notes.pack(side=tk.RIGHT, padx=(6, 0))

    def on_hg_file_selected(self, event=None):
        sel = self.tree_hg_porosimetry.selection()
        if not sel or not self.current_sample_id:
            return
        fn = self.tree_hg_porosimetry.item(sel[0], "values")[0]
        fpath = self.vault.get_characterization_file_path(self.current_sample_id, "hg_porosimetry", fn)
        if fpath and os.path.exists(fpath):
            self.display_hg_image(fpath)

    def display_hg_image(self, fpath):
        self._current_hg_img_path = fpath
        fn = os.path.basename(fpath)
        ext = os.path.splitext(fn)[1].lower()

        if ext not in [".tif", ".tiff", ".png", ".jpg", ".jpeg", ".bmp", ".gif"]:
            self.hg_canvas.delete("all")
            self.hg_preview_info.config(text=f"📄 {fn} (Raw data file — double-click or use 'Open File' to inspect)")
            return

        try:
            with Image.open(fpath) as pil_img:
                orig_w, orig_h = pil_img.size
                canv_w = max(self.hg_canvas.winfo_width(), 200)
                canv_h = max(self.hg_canvas.winfo_height(), 200)

                ratio = min(canv_w / orig_w, canv_h / orig_h)
                new_w = max(int(orig_w * ratio), 1)
                new_h = max(int(orig_h * ratio), 1)

                resized = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                self._current_hg_photo = ImageTk.PhotoImage(resized)

                self.hg_canvas.delete("all")
                cx = canv_w // 2
                cy = canv_h // 2
                self.hg_canvas.create_image(cx, cy, image=self._current_hg_photo, anchor="center")

                sz_kb = os.path.getsize(fpath) / 1024.0
                self.hg_preview_info.config(
                    text=f"💧 {fn}  |  Resolution: {orig_w} × {orig_h} px  |  Size: {sz_kb:.1f} KB"
                )
        except Exception as e:
            self.hg_canvas.delete("all")
            self.hg_preview_info.config(text=f"⚠️ Could not preview image: {e}")

    def _on_hg_canvas_resize(self, event=None):
        if self._current_hg_img_path and os.path.exists(self._current_hg_img_path):
            self.display_hg_image(self._current_hg_img_path)

    def _refresh_hg_porosimetry_tab(self):
        for item in self.tree_hg_porosimetry.get_children():
            self.tree_hg_porosimetry.delete(item)

        if not self.current_sample_id or self.current_sample_id not in self.vault.logbook:
            self.hg_total_vol_var.set(0.0)
            self.hg_median_pore_diam_var.set(0.0)
            self.hg_porosity_var.set(0.0)
            self.hg_skeletal_dens_var.set(0.0)
            self.hg_bulk_dens_var.set(0.0)
            self.hg_avg_pore_diam_var.set(0.0)
            self.hg_canvas.delete("all")
            self.hg_preview_info.config(text="Select a sample to inspect porosimetry curves.")
            self._current_hg_img_path = None
            if hasattr(self, "notes_hg_porosimetry"):
                self.notes_hg_porosimetry.delete("1.0", tk.END)
            return

        data = self.vault.logbook[self.current_sample_id]
        tech_data = data.get("characterizations", {}).get("hg_porosimetry", {})
        files = tech_data.get("files", [])
        for f in files:
            sz = f.get("size_bytes", 0) / 1024.0
            self.tree_hg_porosimetry.insert("", tk.END, values=(
                f.get("filename", "-"),
                f.get("uploaded_at", "-"),
                f"{sz:.1f} KB"
            ))

        self.hg_total_vol_var.set(float(tech_data.get("total_intrusion_vol_cm3_g", 0.0)))
        self.hg_median_pore_diam_var.set(float(tech_data.get("median_pore_diam_um", 0.0)))
        self.hg_porosity_var.set(float(tech_data.get("total_porosity_pct", 0.0)))
        self.hg_skeletal_dens_var.set(float(tech_data.get("skeletal_density_g_cm3", 0.0)))
        self.hg_bulk_dens_var.set(float(tech_data.get("bulk_density_g_cm3", 0.0)))
        self.hg_avg_pore_diam_var.set(float(tech_data.get("avg_pore_diameter_nm", 0.0)))

        if hasattr(self, "notes_hg_porosimetry"):
            self.notes_hg_porosimetry.delete("1.0", tk.END)
            self.notes_hg_porosimetry.insert("1.0", tech_data.get("notes", ""))

        children = self.tree_hg_porosimetry.get_children()
        if children:
            self.tree_hg_porosimetry.selection_set(children[0])
            self.on_hg_file_selected()
        else:
            self.hg_canvas.delete("all")
            self.hg_preview_info.config(text="No porosimetry files attached. Click '+ Attach MIP File' to add.")
            self._current_hg_img_path = None

    def on_save_hg_porosimetry_params(self):
        if not self.current_sample_id:
            return
        data = self.vault.logbook[self.current_sample_id]
        hg_dict = data.setdefault("characterizations", {}).setdefault("hg_porosimetry", {})
        hg_dict["total_intrusion_vol_cm3_g"] = float(self.hg_total_vol_var.get())
        hg_dict["median_pore_diam_um"] = float(self.hg_median_pore_diam_var.get())
        hg_dict["total_porosity_pct"] = float(self.hg_porosity_var.get())
        hg_dict["skeletal_density_g_cm3"] = float(self.hg_skeletal_dens_var.get())
        hg_dict["bulk_density_g_cm3"] = float(self.hg_bulk_dens_var.get())
        hg_dict["avg_pore_diameter_nm"] = float(self.hg_avg_pore_diam_var.get())
        self.vault.save_logbook()
        messagebox.showinfo("Saved", f"Mercury Porosimetry parameters saved for {self.current_sample_id}.")


