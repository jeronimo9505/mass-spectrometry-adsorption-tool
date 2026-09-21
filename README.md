# Origin-Style Mass Spectrometry Integration & CO₂ Capacity Tool

An interactive graphical application built in Python (Tkinter + Matplotlib + SciPy) for the analysis of mass spectrometry data (`.asc` files) from cyclic gas adsorption and desorption experiments (e.g. CO₂ capture on monoliths/zeolites).

![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

---

## 🌟 Key Features

### 1. Mass Spectrometry File Parsing (`.asc`)
- Automatically parses multi-channel quadrupole mass spectrometry output files (`.asc`).
- Maps mass-to-charge ratios ($m/z$):
  - **$m/z = 14.13$**: $\text{N}^+ / \text{N}_2^{++}$
  - **$m/z = 16.13$**: $\text{O}^+$
  - **$m/z = 18.16$**: $\text{H}_2\text{O}$ (Water Vapor)
  - **$m/z = 28.19$**: $\text{N}_2 / \text{CO}$
  - **$m/z = 32.22$**: $\text{O}_2$
  - **$m/z = 40.22$**: $\text{Ar}$
  - **$m/z = 44.28$**: $\text{CO}_2$ (Carbon Dioxide)
- Time units selectable in **Minutes (min)**, **Seconds (s)**, or **Cycles**.

### 2. OriginPro-Style Integration & ROI Boxes
- **Composite Simpson Integration Engine**: Exactly replicates OriginPro's peak integration algorithm.
- **ROI Bands**:
  - **Adsorption Boxes (Yellow)**: Negative consumption band below baseline, calculated with `Straight Line` baseline mode.
  - **Desorption Boxes (Pink)**: Release peak above baseline, calculated with `Horizontal Line (Y=Left)` baseline mode.
- **Full Width at Half Maximum (FWHM)** and duration ($dx$) computed for every peak.
- **Interactive isolated dragging**: Drag, move, or resize individual boxes without moving or disturbing neighboring cycles. Fixed $\Delta x$ mode allows locking the cycle duration.
- **Auto-Detect Cycle Pairs**: One-click algorithm detects transition steps to pair every adsorption and desorption phase across multi-cycle experiments.

### 3. Rigorous Physical CO₂ Capacity Calculation ($q$ in mmol/g)
Directly synchronized with experimental and laboratory parameters:
- **Temperature & Molar Volume Correction**:
  $$V_{m,T_2} = V_{m,25^\circ\text{C}} \times \frac{T_2 + 273.15}{298.15}$$
- **Total Molar Flow Rate**:
  $$n_{\text{total}} = \frac{F_{\text{total}}}{V_{m,T_2}}$$
- **Detector Calibration Factor ($k$)**:
  $$k = \frac{C_0}{S_{\text{baseline}}}$$
- **Moles Adsorbed / Desorbed**:
  $$n(\text{CO}_2) = n_{\text{total}} \times k \times \text{Area}_{\text{integrated}}$$
- **Active Mass Correction**:
  Deducts water/binder mass loss percentage ($m_{\text{active}} = m_{\text{total}} \times (1 - \text{Loss}\%)$).
- **Blank Reference Monolith Deduction**:
  Subtracts reference baseline adsorption ($q_{\text{net}} = q_{\text{active}} - q_{\text{ref}}$).
- **Desorption Recovery Ratio**:
  $$\text{Recovery} = \frac{q_{\text{net,Des}}}{q_{\text{net,Ads}}} \times 100\%$$

### 4. Persistence & Export
- **JSON Auto-Save**: Save ROI bounds and experimental parameters per file (`saved_roi_selections.json`).
- **CSV Export**: Export all integration results or full capacity reports with a single click.
- **Clipboard Report**: Copy a formatted summary directly to your clipboard.

---

## 🚀 Installation & Requirements

Ensure you have Python 3.8+ installed. Install the necessary dependencies:

```bash
pip install numpy pandas matplotlib scipy openpyxl
```

---

## 💻 Usage

Run the tool from your terminal:

```bash
python asc_gas_plotter.py
```

1. **Tab 1 (`📊 Data & Plot`)**: Select your `.asc` measurement file from the dropdown. Toggle individual gas channels or inspect the full mass spectrum.
2. **Tab 2 (`📈 Adsorption / Desorption`)**: Click `Auto-Detect Cycle Pairs` or add custom Adsorption (Yellow) and Desorption (Pink) boxes. Adjust start times or $dx$ width.
3. **Tab 3 (`🧪 CO₂ Capacity (q)`)**: View real-time capacity calculations ($q$ in mmol/g). Adjust sample mass, temperature, flow rates, and click `💾 Save Parameters with File` to store.

---

## 📁 Repository Structure

```text
├── asc_gas_plotter.py                 # Main GUI Application
├── Estructura_Archivos_Medicion.md    # Specification of .asc file data structure
├── saved_roi_selections.json          # Pre-saved ROI selections and parameter presets
├── ZZ 30 Ads des final.xlsx           # Analytical Excel reference calculations
└── README.md                          # Project documentation
```

---

## 📄 License
This project is open source and available under the [MIT License](LICENSE).
