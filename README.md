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
* You can configure the storage folder at any time using the header bar button **`📁 Change Folder...`** or via the menu `File -> Change Vault Directory...`.
* **Automatic Architecture Recognition**: Regardless of where the folder is located (another drive, a shared folder, or a restored backup), the system automatically recognizes and reconciles the architecture, scanning and registering all samples, characterization files, and analyses into the database.
* Use **`🔄 Re-scan`** at any time to discover files manually added or copied into sample directories.

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
