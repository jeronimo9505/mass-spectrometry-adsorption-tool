import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from core.sample_vault import sample_vault
from core.sync_manager import sync_to_supervisor
from gui.logbook_view import LogbookView
from gui.characterization_hub import CharacterizationHubView
from gui.mass_spec_tool import MassSpecToolView
from gui.documents_view import OfficialDocumentsView

class MainWindow(tk.Tk):
    """
    Main Application Window orchestrating the 4 Pillars:
      1. Sample Logbook
      2. Multi-Characterization Hub
      3. Mass Spectrometry & Gas Adsorption Tool
      4. Official Documents & Certificates Vault
    """
    def __init__(self):
        super().__init__()
        self.title("Lab Vault — Sample Logbook & CO₂ Adsorption Analysis System")
        self.geometry("1540x940")
        self.minsize(1180, 760)

        # Style Configuration
        self.style = ttk.Style(self)
        if "vista" in self.style.theme_names():
            self.style.theme_use("vista")
        elif "clam" in self.style.theme_names():
            self.style.theme_use("clam")

        self.style.configure("TNotebook.Tab", font=("Segoe UI", 10, "bold"), padding=[16, 6])
        self.style.configure("Header.TLabel", font=("Segoe UI", 12, "bold"))

        self.vault = sample_vault
        self.active_sample_id = None

        self.protocol("WM_DELETE_WINDOW", self.on_exit)
        # Background sync with supervisor folder on launch
        sync_to_supervisor(async_mode=True)

        self.create_menu()
        self.create_widgets()

    def create_menu(self):
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="📊 Open Sample Register & Summary (.xlsx)", command=self.on_open_master_excel)
        file_menu.add_command(label="📑 Open Official Documents Folder", command=self.on_open_documents_folder)
        file_menu.add_separator()
        file_menu.add_command(label="📁 Change Vault Directory...", command=self.on_change_vault_folder)
        file_menu.add_command(label="📂 Open Vault Directory in Explorer", command=self.on_open_vault_folder)
        file_menu.add_separator()
        file_menu.add_command(label="🔄 Sync with Supervisor (Shayan Ph.D. Student)", command=self.on_sync_supervisor)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_exit)
        menubar.add_cascade(label="File", menu=file_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="📖 Open Workflow Guide (SOP)", command=self.on_open_guide)
        help_menu.add_command(label="ℹ️ About Lab Vault", command=self.on_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.config(menu=menubar)

    def create_widgets(self):
        # Top Header Bar
        header_bar = tk.Frame(self, bg="#1d3557", height=50, padx=12, pady=6)
        header_bar.pack(fill=tk.X)

        lbl_app = tk.Label(
            header_bar,
            text="⚗️ LAB VAULT  |  Sample Logbook & Mass Spectrometry Analysis Tool",
            font=("Segoe UI", 11, "bold"),
            bg="#1d3557",
            fg="#ffffff"
        )
        lbl_app.pack(side=tk.LEFT)

        # Right side: Vault Directory Controls
        vault_controls = tk.Frame(header_bar, bg="#1d3557")
        vault_controls.pack(side=tk.RIGHT)

        self.lbl_vault_info = tk.Label(
            vault_controls,
            text=f"📁 Vault: {self.vault.vault_path}",
            font=("Segoe UI", 9, "bold"),
            bg="#1d3557",
            fg="#a8dadc"
        )
        self.lbl_vault_info.pack(side=tk.LEFT, padx=(0, 10))

        btn_master_xl = tk.Button(
            vault_controls,
            text="📊 Sample Register & Summary",
            font=("Segoe UI", 8, "bold"),
            bg="#2a9d8f",
            fg="#ffffff",
            activebackground="#21867a",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=8,
            pady=2,
            cursor="hand2",
            command=self.on_open_master_excel
        )
        btn_master_xl.pack(side=tk.LEFT, padx=3)

        btn_doc_vault = tk.Button(
            vault_controls,
            text="📑 Official Docs",
            font=("Segoe UI", 8, "bold"),
            bg="#e76f51",
            fg="#ffffff",
            activebackground="#d05a3d",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=8,
            pady=2,
            cursor="hand2",
            command=self.on_open_documents_tab
        )
        btn_doc_vault.pack(side=tk.LEFT, padx=3)

        btn_change_vault = tk.Button(
            vault_controls,
            text="📁 Change...",
            font=("Segoe UI", 8),
            bg="#457b9d",
            fg="#ffffff",
            activebackground="#3b6986",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=8,
            pady=2,
            cursor="hand2",
            command=self.on_change_vault_folder
        )
        btn_change_vault.pack(side=tk.LEFT, padx=3)

        btn_rescan = tk.Button(
            vault_controls,
            text="🔄 Re-scan",
            font=("Segoe UI", 8),
            bg="#3d5a80",
            fg="#ffffff",
            activebackground="#293d56",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=8,
            pady=2,
            cursor="hand2",
            command=self.on_rescan_vault
        )
        btn_rescan.pack(side=tk.LEFT, padx=3)

        btn_open_exp = tk.Button(
            vault_controls,
            text="📂 Open Vault",
            font=("Segoe UI", 8),
            bg="#34495e",
            fg="#ffffff",
            activebackground="#2c3e50",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=8,
            pady=2,
            cursor="hand2",
            command=self.on_open_vault_folder
        )
        btn_open_exp.pack(side=tk.LEFT, padx=3)

        # Main Navigation Tabs (4 Pillars)
        self.main_notebook = ttk.Notebook(self)
        self.main_notebook.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        # Pillar 1: Sample Logbook
        self.tab_logbook = LogbookView(
            self.main_notebook,
            vault=self.vault,
            on_select_sample_callback=self.on_sample_selected_in_logbook,
            on_open_mass_spec_callback=self.on_open_mass_spec,
            on_open_technique_callback=self.on_open_technique
        )
        self.main_notebook.add(self.tab_logbook, text=" 📋 1. Sample Logbook ")

        # Pillar 2: Multi-Characterization Hub
        self.tab_hub = CharacterizationHubView(
            self.main_notebook,
            vault=self.vault,
            on_open_mass_spec_callback=self.on_open_mass_spec
        )
        self.main_notebook.add(self.tab_hub, text=" 🔬 2. Characterization Hub ")

        # Pillar 3: Mass Spectrometry Tool
        self.tab_tool = MassSpecToolView(
            self.main_notebook,
            vault=self.vault,
            on_analysis_saved_callback=self.on_analysis_saved
        )
        self.main_notebook.add(self.tab_tool, text=" 📈 3. Mass Spectrometry Tool (MID) ")

        # Pillar 4: Official Documents & Certificates Vault
        self.tab_documents = OfficialDocumentsView(
            self.main_notebook,
            doc_manager=self.vault.doc_manager,
            vault=self.vault
        )
        self.main_notebook.add(self.tab_documents, text=" 📑 4. Official Documents & Certificates ")

        self.main_notebook.bind("<<NotebookTabChanged>>", self.on_main_tab_changed)
        self.update_vault_header()

    # ==================== INTER-MODULE NAVIGATION ====================

    def on_main_tab_changed(self, event=None):
        try:
            current_tab = self.main_notebook.select()
            if current_tab == str(self.tab_hub):
                self.tab_hub.refresh_active_tab()
            elif current_tab == str(self.tab_documents):
                self.tab_documents.refresh_table()
        except Exception:
            pass

    def on_open_technique(self, sample_id, tech_key):
        self.active_sample_id = sample_id
        if sample_id:
            self.tab_hub.set_sample(sample_id, lazy=False)
            self.tab_hub.show_technique(tech_key)
            self.main_notebook.select(1)  # Switch to Pillar 2 (Hub)

    def on_sample_selected_in_logbook(self, sample_id, switch_tab=False):
        self.active_sample_id = sample_id
        if sample_id:
            self.tab_hub.set_sample(sample_id, lazy=(not switch_tab))
            if switch_tab:
                self.main_notebook.select(1)  # Switch to Pillar 2 (Hub)

    def on_open_mass_spec(self, sample_id, asc_filepath):
        self.active_sample_id = sample_id
        self.tab_hub.set_sample(sample_id, lazy=True)
        # Load sample and file in Tool (Pillar 3)
        self.tab_tool.load_sample_and_file(sample_id, asc_filepath)
        # Switch to Pillar 3
        self.main_notebook.select(2)

    def on_analysis_saved(self, sample_id):
        # Refresh logbook and hub tables
        self.tab_logbook.refresh_table()
        self.tab_hub.set_sample(sample_id, lazy=False)

    def on_open_master_excel(self):
        try:
            ok = self.vault.open_master_excel()
            if not ok:
                messagebox.showwarning("Master Excel", "Could not open Master Excel file.")
        except Exception as e:
            messagebox.showerror("Master Excel Error", f"Failed to generate or open Master Excel file:\n{e}")

    def on_open_documents_tab(self):
        self.main_notebook.select(3)
        self.tab_documents.refresh_table()

    def on_open_documents_folder(self):
        self.vault.doc_manager.open_documents_folder()

    # ==================== MENU COMMANDS ====================

    def update_vault_header(self):
        vp = self.vault.vault_path
        if len(vp) > 45:
            display_path = "..." + vp[-42:]
        else:
            display_path = vp
        self.lbl_vault_info.config(text=f"📁 Vault: {display_path}")

    def on_change_vault_folder(self):
        new_dir = filedialog.askdirectory(title="Select Folder for Sample Vault", initialdir=self.vault.vault_path)
        if new_dir:
            self.vault.set_vault_path(new_dir)
            self.update_vault_header()
            if self.active_sample_id not in self.vault.logbook:
                self.active_sample_id = None
            self.tab_logbook.refresh_table()
            self.tab_hub.set_sample(self.active_sample_id)
            self.tab_documents.refresh_table()
            sample_count = len(self.vault.db.list_samples())
            doc_count = len(self.vault.doc_manager.list_documents())
            messagebox.showinfo(
                "Vault Connected",
                f"Sample Vault successfully connected to:\n{new_dir}\n\n"
                f"• Architecture recognized: SQLite database ('vault.db') + 'samples/' tree\n"
                f"• Live Master Excel: 'Sample_Register_and_Summary_Analysis.xlsx'\n"
                f"• Official Documents Archive: 'Official_Documents/' ({doc_count} files)\n"
                f"• Registered Samples: {sample_count}"
            )

    def on_rescan_vault(self):
        self.vault.reconcile_vault_filesystem()
        self.vault.sync_master_excel()
        self.vault.doc_manager.reconcile_filesystem()
        self.tab_logbook.refresh_table()
        self.tab_hub.set_sample(self.active_sample_id)
        self.tab_documents.refresh_table()
        sample_count = len(self.vault.db.list_samples())
        sync_to_supervisor(async_mode=True)
        messagebox.showinfo("Vault Re-scanned", f"Vault folder and Master Excel re-scanned and synchronized!\nActive Samples: {sample_count}")

    def on_sync_supervisor(self):
        def _done(success, msg):
            if success:
                self.after(0, lambda: messagebox.showinfo(
                    "Sync Complete",
                    "Successfully synchronized all code, analysis, and data with Supervisor OneDrive folder:\n\n"
                    "C:\\Users\\Lenovo\\OneDrive - unizar.es\\Shayan Ph.D. Student\\AI Antigravity software"
                ))
            else:
                self.after(0, lambda: messagebox.showerror("Sync Failed", f"Could not sync with supervisor folder:\n{msg}"))
        sync_to_supervisor(async_mode=True, on_complete=_done)

    def on_exit(self):
        try:
            # Sync latest files to supervisor before closing
            sync_to_supervisor(async_mode=False)
        except Exception:
            pass
        self.destroy()

    def on_open_vault_folder(self):
        if os.path.exists(self.vault.vault_path):
            os.startfile(self.vault.vault_path)
        else:
            messagebox.showwarning("Error", "Vault directory not found.")

    def on_open_guide(self):
        guide_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "WORKFLOW_GUIDE.md")
        if os.path.exists(guide_path):
            os.startfile(guide_path)
        else:
            messagebox.showinfo("Guide", f"Workflow Guide file not found at:\n{guide_path}")

    def on_about(self):
        messagebox.showinfo(
            "About Lab Vault",
            "Modular Laboratory System for Sample Management & Gas Adsorption Characterization.\n\n"
            "• Pillar 1: Sample Logbook & Synthesis Registry.\n"
            "• Pillar 2: Multi-Characterization Hub (Thermal Profiles, TGA, Rheology, Tomography, SEM/TEM, Hg Porosimetry, BET, Documents, Mass Spec).\n"
            "• Pillar 3: Origin-Style Mass Spectrometry Analysis Tool with Simpson integration, interactive draggable ROI boxes, and rigorous CO₂ capacity (q in mmol/g) calculation.\n\n"
            "Built with native Python Desktop (Tkinter + Matplotlib + SciPy)."
        )
