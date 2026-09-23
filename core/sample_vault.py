import os
import json
import shutil
import glob
import pandas as pd
from .config import config
from .db_manager import DBManager

CHARACTERIZATION_TYPES = {
    "mass_spec": {
        "name": "Mass Spectrometry / Gas Adsorption",
        "folder": "mass_spec",
        "extensions": [".asc", ".dat", ".txt", ".csv"],
        "icon": "🧪"
    },
    "xrd": {
        "name": "X-Ray Diffraction (XRD)",
        "folder": "xrd",
        "extensions": [".raw", ".xy", ".dat", ".csv", ".txt"],
        "icon": "🔬"
    },
    "bet": {
        "name": "N₂ Physisorption / BET Surface Area",
        "folder": "bet",
        "extensions": [".xls", ".xlsx", ".csv", ".txt"],
        "icon": "📐"
    },
    "raman": {
        "name": "Raman Spectroscopy",
        "folder": "raman",
        "extensions": [".txt", ".csv", ".spc"],
        "icon": "💡"
    },
    "tga": {
        "name": "Thermogravimetric Analysis (TGA)",
        "folder": "tga",
        "extensions": [".txt", ".csv", ".xls", ".xlsx"],
        "icon": "🔥"
    },
    "documents": {
        "name": "Attached Documents & Reports",
        "folder": "documents",
        "extensions": [".pdf", ".png", ".jpg", ".docx", ".xlsx", ".txt"],
        "icon": "📁"
    }
}

class SampleVault:
    """
    Manages the Sample Logbook and Multi-Characterization Vault.
    Backed by SQLite (vault.db) with automated JSON export (samples_logbook.json).
    Automatically clones files into the local machine vault and tracks all analysis results.
    """
    LOGBOOK_FILENAME = "samples_logbook.json"
    DB_FILENAME = "vault.db"

    def __init__(self, vault_path=None):
        if vault_path:
            self.vault_path = os.path.abspath(vault_path)
        else:
            self.vault_path = config.get_vault_path()

        self.samples_dir = os.path.join(self.vault_path, "samples")
        self.logbook_path = os.path.join(self.vault_path, self.LOGBOOK_FILENAME)
        self.db_path = os.path.join(self.vault_path, self.DB_FILENAME)
        self.ensure_structure()

        self.db = DBManager(self.db_path, self.logbook_path)
        self.reconcile_vault_filesystem()
        self.logbook = self.load_logbook()

    def set_vault_path(self, new_path):
        self.vault_path = config.set_vault_path(new_path)
        self.samples_dir = os.path.join(self.vault_path, "samples")
        self.logbook_path = os.path.join(self.vault_path, self.LOGBOOK_FILENAME)
        self.db_path = os.path.join(self.vault_path, self.DB_FILENAME)
        self.ensure_structure()
        self.db = DBManager(self.db_path, self.logbook_path)
        self.reconcile_vault_filesystem()
        self.logbook = self.load_logbook()
        return self.vault_path

    def ensure_structure(self):
        os.makedirs(self.samples_dir, exist_ok=True)
        if not os.path.exists(self.logbook_path):
            with open(self.logbook_path, "w", encoding="utf-8") as f:
                json.dump({}, f, indent=2)

    def load_logbook(self):
        # Refresh in-memory logbook directly from the SQLite database
        self.logbook = self.db.export_to_json()
        return self.logbook

    def save_logbook(self):
        self.logbook = self.db.export_to_json()

    def reconcile_vault_filesystem(self):
        """
        Recognizes and reconciles the Vault architecture across any selected directory:
        1. Checks SQLite database.
        2. If empty, restores from samples_logbook.json.
        3. Scans samples/ folder on disk for any existing sample subfolders & metadata.json.
        4. Scans and registers all characterization files (mass_spec, xrd, bet, raman, tga, docs).
        5. Scans and registers all mass_spec analyses (analyses/analysis_*.json).
        6. If still empty in the root project data_vault, bootstraps candidate sample templates.
        7. Synchronizes SQLite to samples_logbook.json.
        """
        existing_samples = {s["sample_id"]: s for s in self.db.list_samples()}

        # Step 1: If DB is empty, check samples_logbook.json
        if not existing_samples and os.path.exists(self.logbook_path):
            try:
                with open(self.logbook_path, "r", encoding="utf-8") as f:
                    json_data = json.load(f)
                if isinstance(json_data, dict):
                    for s_id, s_data in json_data.items():
                        if isinstance(s_data, dict):
                            self.db.save_sample(s_data)
                            for tech, tdata in s_data.get("characterizations", {}).items():
                                for f_rec in tdata.get("files", []):
                                    fn = f_rec.get("filename")
                                    if fn:
                                        fpath = os.path.join(self.get_technique_dir(s_id, tech), fn)
                                        dest_dir = self.get_technique_dir(s_id, tech)
                                        self.db.register_and_clone_file(s_id, tech, fpath, dest_dir, f_rec.get("description", ""))
            except Exception:
                pass

        # Step 2: Auto-discover samples from the filesystem in samples/
        if os.path.exists(self.samples_dir):
            for entry in os.scandir(self.samples_dir):
                if entry.is_dir():
                    s_id = entry.name
                    meta_p = os.path.join(entry.path, "metadata.json")
                    if s_id not in self.db.logbook if hasattr(self.db, "logbook") else s_id not in [s["sample_id"] for s in self.db.list_samples()]:
                        s_data = None
                        if os.path.exists(meta_p):
                            try:
                                with open(meta_p, "r", encoding="utf-8") as mf:
                                    s_data = json.load(mf)
                            except Exception:
                                s_data = None
                        if not s_data:
                            s_data = {
                                "sample_id": s_id,
                                "material_name": s_id,
                                "operator": "Lab Researcher",
                                "date": pd.Timestamp.now().strftime("%Y-%m-%d"),
                                "mass_total_g": 0.5055,
                                "water_loss_pct": 21.4,
                                "ref_ads": 0.23,
                                "status": "Registered"
                            }
                        self.db.save_sample(s_data)

        # Step 3: Scan all samples on disk to register newly added files and analyses
        current_samples = self.db.list_samples()
        for s in current_samples:
            s_id = s["sample_id"]
            self.ensure_sample_folders(s_id)
            s_dir = self.get_sample_dir(s_id)

            # Reconcile characterization files
            for tech, conf in CHARACTERIZATION_TYPES.items():
                tech_dir = os.path.join(s_dir, conf["folder"])
                if os.path.exists(tech_dir):
                    for fname in os.listdir(tech_dir):
                        fpath = os.path.join(tech_dir, fname)
                        if os.path.isfile(fpath):
                            with self.db.get_connection() as conn:
                                cur = conn.cursor()
                                cur.execute(
                                    "SELECT id FROM characterization_files WHERE sample_id = ? AND technique = ? AND filename = ?",
                                    (s_id, tech, fname)
                                )
                                if not cur.fetchone():
                                    self.db.register_and_clone_file(s_id, tech, fpath, tech_dir, description=f"Discovered {tech} file")

            # Reconcile mass spec analyses
            ms_an_dir = os.path.join(s_dir, "mass_spec", "analyses")
            if os.path.exists(ms_an_dir):
                for an_fn in os.listdir(ms_an_dir):
                    if an_fn.startswith("analysis_") and an_fn.endswith(".json"):
                        an_p = os.path.join(ms_an_dir, an_fn)
                        try:
                            with open(an_p, "r", encoding="utf-8") as f:
                                an_data = json.load(f)
                            orig_fn = an_data.get("filename")
                            if orig_fn:
                                self.db.save_analysis(
                                    sample_id=s_id,
                                    filename=orig_fn,
                                    ranges=an_data.get("ranges", []),
                                    capacity_results=an_data.get("capacity", {}),
                                    target_gas=an_data.get("target_gas", "CO2 (m/z 44.28)")
                                )
                        except Exception:
                            pass

        # Step 4: If still empty and in default project vault, bootstrap candidate templates
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        default_vault = os.path.abspath(os.path.join(root_dir, "data_vault"))
        if not self.db.list_samples() and os.path.abspath(self.vault_path) == default_vault:
            candidates = [
                ("ZZ30_01", "ZZ30 Monolith (B6 Zeo)", "24082026  final zz30 monoliths 1st.asc", 0.5055, 21.4, 0.23, "Complete cyclic adsorption/desorption run"),
                ("ZZ20_01", "ZZ20 Monolith", "21082026  zz20 monoliths 1st.asc", 0.5000, 21.4, 0.23, "Preliminary ZZ20 run"),
                ("ZZ10_01", "ZZ10 Monolith", "01092026 zz10 monolith final full 3 cycles.asc", 0.5000, 21.4, 0.23, "Full 3 continuous cycles"),
                ("REF_MONO_01", "Reference Monolith Valencia", "28082026  ref monolith valencia zz20 sample final 3 cycles ads and desortion.asc", 0.9200, 0.0, 0.00, "Blank monolith without zeolite")
            ]
            for s_id, mat, fname, mass, water, r_ads, notes in candidates:
                s_data = {
                    "sample_id": s_id,
                    "material_name": mat,
                    "operator": "Shayan / Jeronimo",
                    "date": "2026-08-24" if "2408" in fname else ("2026-09-01" if "0109" in fname else "2026-08-28"),
                    "mass_total_g": mass,
                    "water_loss_pct": water,
                    "ref_ads": r_ads,
                    "notes": notes,
                    "status": "Registered"
                }
                self.db.save_sample(s_data)
                src_p = os.path.join(root_dir, fname)
                if os.path.exists(src_p):
                    dest_dir = self.get_technique_dir(s_id, "mass_spec")
                    self.db.register_and_clone_file(s_id, "mass_spec", src_p, dest_dir, f"Measurement file for {mat}")

        self.db.export_to_json()

    def get_sample_dir(self, sample_id):
        return os.path.join(self.samples_dir, sample_id)

    def get_technique_dir(self, sample_id, technique="mass_spec"):
        folder_name = CHARACTERIZATION_TYPES.get(technique, {}).get("folder", technique)
        tech_dir = os.path.join(self.get_sample_dir(sample_id), folder_name)
        os.makedirs(tech_dir, exist_ok=True)
        return tech_dir

    def ensure_sample_folders(self, sample_id):
        sample_dir = self.get_sample_dir(sample_id)
        os.makedirs(sample_dir, exist_ok=True)
        for tech, conf in CHARACTERIZATION_TYPES.items():
            tech_folder = os.path.join(sample_dir, conf["folder"])
            os.makedirs(tech_folder, exist_ok=True)
            if tech == "mass_spec":
                os.makedirs(os.path.join(tech_folder, "analyses"), exist_ok=True)
                os.makedirs(os.path.join(tech_folder, "reports"), exist_ok=True)

    def create_or_update_sample(self, sample_id, metadata):
        sample_id = sample_id.strip()
        self.ensure_sample_folders(sample_id)
        metadata["sample_id"] = sample_id

        # Save into SQLite database
        self.db.save_sample(metadata)
        self.load_logbook()

        # Update metadata.json inside the sample directory on the machine
        meta_file = os.path.join(self.get_sample_dir(sample_id), "metadata.json")
        try:
            with open(meta_file, "w", encoding="utf-8") as f:
                json.dump(self.logbook.get(sample_id, metadata), f, indent=2)
        except Exception:
            pass

        return self.logbook.get(sample_id, metadata)

    def add_characterization_file(self, sample_id, technique, source_file_path, description=""):
        """
        Clones the original file into the local sample vault directory on the machine
        and registers the record in the SQLite database and JSON logbook.
        """
        if sample_id not in self.logbook:
            raise KeyError(f"Sample '{sample_id}' not found.")

        dest_dir = self.get_technique_dir(sample_id, technique)
        cloned_path = self.db.register_and_clone_file(
            sample_id=sample_id,
            technique=technique,
            source_path=source_file_path,
            dest_dir=dest_dir,
            description=description
        )
        self.load_logbook()
        return cloned_path

    def get_characterization_file_path(self, sample_id, technique, filename):
        dest_folder = self.get_technique_dir(sample_id, technique)
        p = os.path.join(dest_folder, filename)
        if os.path.exists(p):
            return p
        leg1 = os.path.join(self.get_sample_dir(sample_id), "raw_data", filename)
        if os.path.exists(leg1):
            return leg1
        return None

    def delete_characterization_file(self, sample_id, technique, filename):
        self.db.delete_file(sample_id, technique, filename)
        self.load_logbook()
        return True

    def save_mass_spec_analysis(self, sample_id, filename, ranges, capacity_results, target_gas="CO2 (m/z 44.28)", report_text=""):
        """
        Saves analysis results both into the SQLite database and as an analysis JSON file
        inside the sample's directory on the machine, updating the sample and file to 'Analyzed'.
        """
        # Ensure file is cloned locally if it exists outside
        file_path = self.get_characterization_file_path(sample_id, "mass_spec", filename)
        dest_dir = self.get_technique_dir(sample_id, "mass_spec")
        if file_path and os.path.exists(file_path):
            self.db.register_and_clone_file(sample_id, "mass_spec", file_path, dest_dir)

        # 1. Save JSON analysis file on disk
        an_dir = os.path.join(dest_dir, "analyses")
        os.makedirs(an_dir, exist_ok=True)
        analysis_fn = f"analysis_{os.path.splitext(filename)[0]}.json"
        analysis_path = os.path.join(an_dir, analysis_fn)

        record = {
            "sample_id": sample_id,
            "filename": filename,
            "target_gas": target_gas,
            "ranges": ranges,
            "capacity": capacity_results,
            "analyzed_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        with open(analysis_path, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2)

        # 2. Save directly into SQLite Database & Sync JSON
        res = self.db.save_analysis(
            sample_id=sample_id,
            filename=filename,
            ranges=ranges,
            capacity_results=capacity_results,
            target_gas=target_gas,
            report_text=report_text
        )

        self.load_logbook()
        return res

    def load_mass_spec_analysis(self, sample_id, filename):
        # First try SQLite
        res = self.db.load_analysis(sample_id, filename)
        if res:
            return res

        # Fallback to disk JSON
        tech_dir = self.get_technique_dir(sample_id, "mass_spec")
        analysis_fn = f"analysis_{os.path.splitext(filename)[0]}.json"
        p = os.path.join(tech_dir, "analyses", analysis_fn)
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return None

    def save_sample_report(self, sample_id, report_text, title="co2_report"):
        tech_dir = self.get_technique_dir(sample_id, "mass_spec")
        rep_dir = os.path.join(tech_dir, "reports")
        os.makedirs(rep_dir, exist_ok=True)
        txt_path = os.path.join(rep_dir, f"{title}_{sample_id}.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(report_text)
        return txt_path

    def delete_sample(self, sample_id):
        self.db.delete_sample(sample_id)
        sample_folder = self.get_sample_dir(sample_id)
        if os.path.exists(sample_folder):
            try:
                shutil.rmtree(sample_folder)
            except Exception:
                pass
        self.load_logbook()

sample_vault = SampleVault()
