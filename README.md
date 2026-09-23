# Lab Vault & Mass Spectrometry Analysis Platform

A modular desktop application built in Python (**Tkinter + Matplotlib + SciPy**) designed for materials laboratories, catalytic research, and gas adsorption characterization (e.g., cyclic $\text{CO}_2$ capture on monoliths, zeolites, and MOFs).

![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)
![SQLite](https://img.shields.io/badge/Database-SQLite3-003B57.svg)
![UI](https://img.shields.io/badge/UI-English-green.svg)
![License](https://img.shields.io/badge/License-MIT-teal.svg)

---

## 🏛️ The Three Pillars Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                        LAB VAULT PLATFORM                              │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         ▼                         ▼                         ▼
┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│  PILLAR 1:       │      │  PILLAR 2:       │      │  PILLAR 3:       │
│  Sample Logbook  │◄────►│  Characterization│◄────►│  Mass Spectro-   │
│  (Bitácora)      │      │  Hub             │      │  metry Tool      │
└──────────────────┘      └──────────────────┘      └──────────────────┘
```

### 1. 📋 Pillar 1: Sample Logbook (Bitácora de Muestras)
* **Sample Registry**: Track Sample ID, Material/Formulation, Operator, Synthesis Date, and notes.
* **Mass Corrections**: Computes dry active mass ($m_{\text{active}} = m_{\text{total}} \times (1 - \text{Loss}\%)$) from moisture/binder loss.
* **Real-time KPIs**: Live count of total samples, analyzed specimens, and average batch mass.
* **Search & Filters**: Instantly filter samples by ID, material name, or researcher.
* **Direct Actions**: Add, edit, delete, inspect folder, and jump directly to characterizations.

### 2. 🔬 Pillar 2: Multi-Characterization Hub
* **Multi-Technique Support**:
  * 🧪 **Mass Spectrometry / Gas Adsorption** (`.asc`, `.dat`, `.txt`, `.csv`)
  * 🔬 **X-Ray Diffraction (XRD)** (`.raw`, `.xy`, `.dat`, `.csv`)
  * 📐 **$\text{N}_2$ Physisorption / BET Surface Area** (`.xls`, `.xlsx`, `.csv`)
  * 💡 **Raman Spectroscopy** (`.txt`, `.csv`, `.spc`)
  * 🔥 **Thermogravimetric Analysis (TGA)** (`.txt`, `.csv`, `.xls`, `.xlsx`)
  * 📁 **Documents & Reports** (`.pdf`, `.png`, `.docx`, `.xlsx`)
* **Physical File Cloning**: When attaching an external measurement file, it is automatically cloned into the local machine vault under `<vault>/samples/<sample_id>/<technique>/`.
* **Seamless Tool Launch**: One-click button (`📈 Open in MS Tool`) to open `.asc` files directly into Pillar 3.

### 3. 📈 Pillar 3: High-Precision Mass Spectrometry & Adsorption Tool
* **Quadrupole MS Channel Mapping**:
  * $m/z = 14.13$ ($\text{N}^+$), $16.13$ ($\text{O}^+$), $18.16$ ($\text{H}_2\text{O}$), $28.19$ ($\text{N}_2/\text{CO}$), $32.22$ ($\text{O}_2$), $40.22$ ($\text{Ar}$), $44.28$ ($\text{CO}_2$).
* **OriginPro-Accurate Simpson Integration**:
  * **Adsorption (Yellow ROI)**: Negative consumption band below baseline.
  * **Desorption (Pink ROI)**: Release peak above baseline.
  * **Full Width at Half Maximum (FWHM)** and duration ($\Delta t$) calculated for every peak.
  * **Lock $\Delta t$ Mode**: Constrain or adjust peak duration via spinbox.
  * **Auto-Detect Cycle Pairs**: Automatically identifies cycle transitions across multi-cycle runs.
* **Rigorous Thermodynamic $\text{CO}_2$ Capacity ($q$ in mmol/g)**:
  * Temperature-corrected molar gas volume ($V_m(T)$).
  * Baseline detector calibration factor ($k = C_0 / S_{\text{baseline}}$).
  * Subtraction of blank reference monolith adsorption ($q_{\text{net}} = q_{\text{active}} - q_{\text{ref}}$).
  * Desorption Recovery Ratio ($\% = \frac{q_{\text{net,Des}}}{q_{\text{net,Ads}}} \times 100\%$).
* **Direct Vault Synchronization**: Saving analysis updates the sample status to `Analyzed`, updates maximum capacity in the Logbook, and saves both in SQLite and as a portable JSON record.

---

## 💾 Storage Architecture & Directory Portability

The application stores data in a clean, self-contained architecture backed by **SQLite** with synchronized **JSON**:

```text
<Selected Vault Folder>/
├── vault.db                         # SQLite Database (Single Source of Truth)
├── samples_logbook.json             # Portable synchronized JSON logbook
└── samples/                         # Local storage for all cloned files
    ├── <Sample_ID_1>/
    │   ├── metadata.json            # Cached sample metadata
    │   ├── mass_spec/
    │   │   ├── raw_measurement.asc  # Cloned raw data file
    │   │   ├── analyses/            # Saved ROI & capacity JSON records
    │   │   └── reports/             # Generated TXT analytical reports
    │   ├── xrd/                     # XRD files
    │   ├── bet/                     # BET surface area isotherms & reports
    │   ├── raman/                   # Raman spectra
    │   ├── tga/                     # TGA thermograms
    │   └── documents/               # Attached PDFs, SEM images, papers
    └── <Sample_ID_2>/
        └── ...
```

### 📁 Configurable Vault Location
* Configure the storage folder at any time using the header bar button **`📁 Change Folder...`** or via the menu `File -> Change Vault Directory...`.
* **Automatic Architecture Recognition**: Regardless of where the folder is located (another drive, a shared folder, or a restored backup), the system automatically recognizes and reconciles the architecture, scanning and registering all samples, characterization files, and analyses into the database.
* Use **`🔄 Re-scan`** at any time to discover files manually added or copied into sample directories.

---

## 🧠 Codebase Map & Module Architecture (AI & Developer Guide)

This section documents where each capability lives and what file an AI agent or human contributor should edit when making modifications:

```text
shayan/
├── main.py                          # 🚀 Primary application launcher & CLI entrypoint
├── asc_gas_plotter.py               # 📜 Historical standalone MS plotter (HEAD reference)
├── settings.json                    # ⚙️ Application preferences (vault path, etc.)
├── WORKFLOW_GUIDE.md                # 📖 Standard Operating Procedure (SOP)
├── Estructura_Archivos_Medicion.md  # 📊 Specification of .asc quadrupole mass spec files
│
├── core/                            # ⚙️ BUSINESS LOGIC & DATA LAYER (NO GUI CODE)
│   ├── config.py                    # Vault folder path resolution & settings management
│   ├── db_manager.py                # SQLite schema, CRUD operations, transactions, JSON sync
│   ├── sample_vault.py              # Vault coordinator, file cloner, directory reconciler
│   ├── asc_parser.py                # Parser for multi-channel quadrupole .asc files
│   ├── integration_engine.py        # Simpson composite integration, FWHM, ROI auto-detect
│   └── capacity_calculator.py       # Thermodynamic CO2 capacity model (q in mmol/g)
│
├── gui/                             # 🖥️ PRESENTATION LAYER (100% ENGLISH UI)
│   ├── main_window.py               # Root Tkinter window, header bar, menu, tab orchestrator
│   ├── logbook_view.py              # Pillar 1 UI: Table, search, KPIs, sample dialog
│   ├── characterization_hub.py      # Pillar 2 UI: Multi-technique tabs, file attachment
│   └── mass_spec_tool.py            # Pillar 3 UI: Matplotlib canvas, draggable ROIs, capacity panel
│
└── data_vault/                      # 📁 DEFAULT LOCAL DATA REPOSITORY
    ├── vault.db                     # Active SQLite database
    ├── samples_logbook.json         # Synchronized portable JSON dump
    └── samples/                     # Cloned characterization files partitioned by sample
```

### 🗺️ Quick Modification Guide for AI Agents:
| If you want to modify... | Look in file / module... | Key functions / classes |
| :--- | :--- | :--- |
| **Database Schema or SQL queries** | [`core/db_manager.py`](core/db_manager.py) | `DBManager.init_schema()`, `save_sample()`, `save_analysis()` |
| **Folder Architecture & Auto-Discovery** | [`core/sample_vault.py`](core/sample_vault.py) | `SampleVault.reconcile_vault_filesystem()`, `register_and_clone_file()` |
| **Vault Directory Preferences** | [`core/config.py`](core/config.py) | `AppConfig.get_vault_path()`, `set_vault_path()` |
| **Integration Math & ROI auto-detection** | [`core/integration_engine.py`](core/integration_engine.py) | `IntegrationEngine.integrate_peak()`, `auto_detect_cycle_pairs()` |
| **$CO_2$ Capacity Formula & Physics** | [`core/capacity_calculator.py`](core/capacity_calculator.py) | `CO2CapacityCalculator.calculate()` |
| **Sample Logbook Table & Modal Dialogs** | [`gui/logbook_view.py`](gui/logbook_view.py) | `LogbookView`, `SampleDialog` |
| **Multi-Technique Tabs (XRD, BET, etc.)** | [`gui/characterization_hub.py`](gui/characterization_hub.py) | `CharacterizationHubView` |
| **Interactive Plot, Draggable ROIs, $\Delta t$** | [`gui/mass_spec_tool.py`](gui/mass_spec_tool.py) | `MassSpecToolView`, Matplotlib event handlers |
| **Top Header Bar, Menu, Navigation Tabs** | [`gui/main_window.py`](gui/main_window.py) | `MainWindow`, `create_widgets()`, `create_menu()` |

---

## 🤖 AI Agent & Contributor Protocol

When an AI assistant or human developer contributes to this codebase, the following protocols **MUST** be strictly respected:

### 1. 📖 Inspection & Reading Protocol
1. **Always read this `README.md` first** to understand the 3 pillars and module breakdown.
2. **Review [`WORKFLOW_GUIDE.md`](WORKFLOW_GUIDE.md)** before modifying adsorption/desorption algorithms or experimental capacity models.
3. **Verify the active database state**: inspect `data_vault/vault.db` through `DBManager` rather than modifying raw JSON files directly.

### 2. 🛡️ Architectural & Coding Constraints
* **100% English UI Rule**: Every button, label, dialog title, error alert, and tooltip in the GUI **MUST** be in English. Never mix languages in user-facing components.
* **Native Desktop Lightweight Rule**: Use native **Python Tkinter + Matplotlib + SciPy**. **NEVER** introduce heavy web frameworks, Node/npm servers, or browser Plotly engines. Native Matplotlib handles 50,000+ data points in compiled C++ using $<80$ MB of RAM without lag.
* **Separation of Concerns**: Never import GUI modules (`tkinter`) inside `core/`. Business logic and mathematical engines must remain decoupled and testable via CLI.
* **Vault Portability & Data Integrity**:
  * All sample file additions must clone the file into the vault folder via `SampleVault.add_characterization_file()`.
  * Every mutation must commit to SQLite (`vault.db`) and immediately sync `samples_logbook.json`.

### 3. 🚀 Pre-Commit & Git Push Protocol
Before performing any `git push`, the following sequence **MUST** be completed:
1. **Clean Temporary & Lock Files**:
   * Delete any Excel lock files (`~$*`) or scratch folders (`scratch/`).
   * Verify that [`.gitignore`](.gitignore) is clean and up to date.
2. **Syntax Compilation Check**:
   * Run syntax compilation across all Python files to prevent runtime syntax errors:
     ```bash
     python -c "import py_compile, glob; [py_compile.compile(f, doraise=True) for f in glob.glob('**/*.py', recursive=True)]"
     ```
3. **Update Documentation**:
   * If modifying features, architecture, or settings, update `README.md` and/or `WORKFLOW_GUIDE.md` to reflect the exact changes.
4. **Git Commit & Push**:
   * Check status: `git status`
   * Stage changes: `git add .`
   * Commit with a standardized descriptive message: `git commit -m "feat/fix: <description>"`
   * Push to remote: `git push origin main`

---

## 🚀 Installation & Requirements

Ensure you have **Python 3.8+** installed. Install the necessary dependencies:

```bash
pip install numpy pandas matplotlib scipy openpyxl
```

---

## 💻 Quickstart

### Launch the Full Lab Vault Platform (Recommended)
```bash
python main.py
```

### Command-Line Arguments
```bash
# Pre-select a specific sample on startup:
python main.py --sample ZZ30_01

# Directly open an .asc file inside Pillar 3:
python main.py "24082026  final zz30 monoliths 1st.asc"
```

### Standalone MS Plotter (Legacy)
```bash
python asc_gas_plotter.py
```

---

## 📖 Standard Operating Procedure (SOP)

For detailed step-by-step lab instructions, mathematical derivations, and ROI integration best practices, see the comprehensive [WORKFLOW_GUIDE.md](WORKFLOW_GUIDE.md) (also accessible inside the application via `Help -> Open Workflow Guide`).

---

## 📄 License
This project is open-source and available under the [MIT License](LICENSE).
