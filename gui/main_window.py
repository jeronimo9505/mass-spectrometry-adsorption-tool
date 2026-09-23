import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from core.sample_vault import sample_vault
from gui.logbook_view import LogbookView
from gui.characterization_hub import CharacterizationHubView
from gui.mass_spec_tool import MassSpecToolView

class MainWindow(tk.Tk):
    """
    Main Application Window orchestrating the 3 Pillars:
      1. Sample Logbook (Bitácora)
      2. Multi-Characterization Hub
      3. Mass Spectrometry & Gas Adsorption Tool
    """
    def __init__(self):
        super().__init__()
        self.title("Lab Vault — Sample Logbook & CO₂ Adsorption Analysis System")
        self.geometry("1520x940")
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

        self.create_menu()
        self.create_widgets()

    def create_menu(self):
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="📁 Change Vault Directory...", command=self.on_change_vault_folder)
        file_menu.add_command(label="📂 Open Vault Directory in Explorer", command=self.on_open_vault_folder)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit)
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

        btn_change_vault = tk.Button(
            vault_controls,
            text="📁 Change Folder...",
            font=("Segoe UI", 8, "bold"),
            bg="#457b9d",
            fg="#ffffff",
            activebackground="#2a9d8f",
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
            bg="#2a9d8f",
            fg="#ffffff",
            activebackground="#264653",
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
            text="📂 Open",
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

        # Main Navigation Tabs (3 Pillars)
        self.main_notebook = ttk.Notebook(self)
        self.main_notebook.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        # Pillar 1: Sample Logbook
        self.tab_logbook = LogbookView(
            self.main_notebook,
            vault=self.vault,
            on_select_sample_callback=self.on_sample_selected_in_logbook,
            on_open_mass_spec_callback=self.on_open_mass_spec
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

        self.update_vault_header()

    # ==================== INTER-MODULE NAVIGATION ====================

    def on_sample_selected_in_logbook(self, sample_id, switch_tab=False):
        self.active_sample_id = sample_id
        if sample_id:
            self.tab_hub.set_sample(sample_id)
            if switch_tab:
                self.main_notebook.select(1)  # Switch to Pillar 2 (Hub)

    def on_open_mass_spec(self, sample_id, asc_filepath):
        self.active_sample_id = sample_id
        self.tab_hub.set_sample(sample_id)
        # Load sample and file in Tool (Pillar 3)
        self.tab_tool.load_sample_and_file(sample_id, asc_filepath)
        # Switch to Pillar 3
        self.main_notebook.select(2)

    def on_analysis_saved(self, sample_id):
        # Refresh logbook and hub tables
        self.tab_logbook.refresh_table()
        self.tab_hub.set_sample(sample_id)

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
            sample_count = len(self.vault.db.list_samples())
            messagebox.showinfo(
                "Vault Connected",
                f"Sample Vault successfully connected to:\n{new_dir}\n\n"
                f"• Architecture recognized: SQLite database ('vault.db') + 'samples/' tree\n"
                f"• Registered Samples: {sample_count}"
            )

    def on_rescan_vault(self):
        self.vault.reconcile_vault_filesystem()
        self.tab_logbook.refresh_table()
        self.tab_hub.set_sample(self.active_sample_id)
        sample_count = len(self.vault.db.list_samples())
        messagebox.showinfo("Vault Re-scanned", f"Vault folder re-scanned and synchronized!\nActive Samples: {sample_count}")

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
            "• Pillar 2: Multi-Characterization Hub (XRD, BET, Raman, TGA, Mass Spec).\n"
            "• Pillar 3: Origin-Style Mass Spectrometry Analysis Tool with Simpson integration, interactive draggable ROI boxes, and rigorous CO₂ capacity (q in mmol/g) calculation.\n\n"
            "Built with native Python Desktop (Tkinter + Matplotlib + SciPy)."
        )
