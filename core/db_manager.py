import os
import sqlite3
import json
import shutil
import pandas as pd

class DBManager:
    """
    Central Database Manager using SQLite with automatic JSON export.
    Acts as the single source of truth for:
      - Samples registry
      - Multi-characterization files (cloned locally)
      - Mass spectrometry analysis results (q_net_ads, q_net_des, recovery, ROI ranges)
    """
    def __init__(self, db_path=None, json_path=None):
        if db_path is None:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            vault_dir = os.path.join(base, "data_vault")
            os.makedirs(vault_dir, exist_ok=True)
            self.db_path = os.path.join(vault_dir, "vault.db")
            self.json_path = os.path.join(vault_dir, "samples_logbook.json")
        else:
            self.db_path = os.path.abspath(db_path)
            self.json_path = os.path.abspath(json_path) if json_path else os.path.splitext(self.db_path)[0] + ".json"

        self.init_schema()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # 1. Samples Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS samples (
                sample_id TEXT PRIMARY KEY,
                material_name TEXT NOT NULL,
                operator TEXT,
                date TEXT,
                mass_total_g REAL DEFAULT 0.5055,
                water_loss_pct REAL DEFAULT 21.4,
                mass_active_g REAL DEFAULT 0.3973,
                ref_ads_mmol_g REAL DEFAULT 0.23,
                ref_des_mmol_g REAL DEFAULT 0.00,
                c0 REAL DEFAULT 0.15,
                flow_total REAL DEFAULT 100.0,
                temp_c REAL DEFAULT 24.0,
                notes TEXT,
                status TEXT DEFAULT 'Registered',
                created_at TEXT,
                updated_at TEXT
            )
            """)

            # 2. Cloned Characterization Files Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS characterization_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sample_id TEXT NOT NULL,
                technique TEXT NOT NULL,
                filename TEXT NOT NULL,
                cloned_path TEXT,
                size_bytes INTEGER DEFAULT 0,
                description TEXT,
                status TEXT DEFAULT 'Pending',
                uploaded_at TEXT,
                FOREIGN KEY (sample_id) REFERENCES samples (sample_id) ON DELETE CASCADE,
                UNIQUE (sample_id, technique, filename)
            )
            """)

            # 3. Mass Spectrometry Analyses & Capacities Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS mass_spec_analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sample_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                target_gas TEXT,
                q_net_ads REAL,
                q_net_des REAL,
                recovery_pct REAL,
                area_ads REAL,
                area_des REAL,
                temp_c REAL,
                vm_exp REAL,
                k_factor REAL,
                mass_active_g REAL,
                ranges_json TEXT,
                capacity_json TEXT,
                report_text TEXT,
                analyzed_at TEXT,
                FOREIGN KEY (sample_id) REFERENCES samples (sample_id) ON DELETE CASCADE,
                UNIQUE (sample_id, filename)
            )
            """)

            # 4. Textural & Structural Properties (BET, XRD notes, etc.)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS technique_properties (
                sample_id TEXT NOT NULL,
                technique TEXT NOT NULL,
                properties_json TEXT,
                notes TEXT,
                updated_at TEXT,
                PRIMARY KEY (sample_id, technique),
                FOREIGN KEY (sample_id) REFERENCES samples (sample_id) ON DELETE CASCADE
            )
            """)

            conn.commit()

    # ==================== SAMPLES CRUD ====================

    def save_sample(self, sample_data):
        s_id = str(sample_data.get("sample_id", "")).strip()
        if not s_id:
            raise ValueError("Sample ID cannot be empty.")

        mass_tot = float(sample_data.get("mass_total_g", 0.5055))
        water_pct = float(sample_data.get("water_loss_pct", 21.4))
        mass_act = mass_tot * (1.0 - (water_pct / 100.0))
        now_str = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO samples (
                sample_id, material_name, operator, date, mass_total_g, water_loss_pct, mass_active_g,
                ref_ads_mmol_g, ref_des_mmol_g, c0, flow_total, temp_c, notes, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(sample_id) DO UPDATE SET
                material_name=excluded.material_name,
                operator=excluded.operator,
                date=excluded.date,
                mass_total_g=excluded.mass_total_g,
                water_loss_pct=excluded.water_loss_pct,
                mass_active_g=excluded.mass_active_g,
                ref_ads_mmol_g=excluded.ref_ads_mmol_g,
                ref_des_mmol_g=excluded.ref_des_mmol_g,
                c0=excluded.c0,
                flow_total=excluded.flow_total,
                temp_c=excluded.temp_c,
                notes=excluded.notes,
                status=excluded.status,
                updated_at=excluded.updated_at
            """, (
                s_id,
                sample_data.get("material_name", "-"),
                sample_data.get("operator", "Shayan / Jeronimo"),
                sample_data.get("date", "-"),
                mass_tot,
                water_pct,
                round(mass_act, 4),
                float(sample_data.get("ref_ads", sample_data.get("ref_ads_mmol_g", 0.23))),
                float(sample_data.get("ref_des", sample_data.get("ref_des_mmol_g", 0.00))),
                float(sample_data.get("c0", 0.15)),
                float(sample_data.get("flow_total", 100.0)),
                float(sample_data.get("temp_c", 24.0)),
                sample_data.get("notes", ""),
                sample_data.get("status", "Registered"),
                sample_data.get("created_at", now_str),
                now_str
            ))
            conn.commit()

        self.export_to_json()
        return s_id

    def get_sample(self, sample_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM samples WHERE sample_id = ?", (sample_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_samples(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT s.*, 
                   COUNT(f.id) as files_count,
                   MAX(a.q_net_ads) as max_q_ads,
                   MAX(a.recovery_pct) as max_recovery
            FROM samples s
            LEFT JOIN characterization_files f ON s.sample_id = f.sample_id
            LEFT JOIN mass_spec_analyses a ON s.sample_id = a.sample_id
            GROUP BY s.sample_id
            ORDER BY s.sample_id ASC
            """)
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def delete_sample(self, sample_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM samples WHERE sample_id = ?", (sample_id,))
            cursor.execute("DELETE FROM characterization_files WHERE sample_id = ?", (sample_id,))
            cursor.execute("DELETE FROM mass_spec_analyses WHERE sample_id = ?", (sample_id,))
            cursor.execute("DELETE FROM technique_properties WHERE sample_id = ?", (sample_id,))
            conn.commit()
        self.export_to_json()

    # ==================== CLONED CHARACTERIZATION FILES ====================

    def register_and_clone_file(self, sample_id, technique, source_path, dest_dir, description=""):
        """
        Clones the original measurement file into the sample vault folder on the machine
        and registers the file record in SQLite.
        """
        filename = os.path.basename(source_path)
        dest_path = os.path.join(dest_dir, filename)

        # Clone file physically to local vault folder if different
        if os.path.abspath(source_path) != os.path.abspath(dest_path):
            os.makedirs(dest_dir, exist_ok=True)
            shutil.copy2(source_path, dest_path)

        file_sz = os.path.getsize(dest_path) if os.path.exists(dest_path) else 0
        now_str = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")

        # Check if an analysis already exists for this file
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM mass_spec_analyses WHERE sample_id = ? AND filename = ?",
                (sample_id, filename)
            )
            has_an = cursor.fetchone() is not None
            status = "Analyzed" if has_an else "Pending"

            cursor.execute("""
            INSERT INTO characterization_files (
                sample_id, technique, filename, cloned_path, size_bytes, description, status, uploaded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(sample_id, technique, filename) DO UPDATE SET
                cloned_path=excluded.cloned_path,
                size_bytes=excluded.size_bytes,
                description=excluded.description,
                status=CASE WHEN characterization_files.status='Analyzed' THEN 'Analyzed' ELSE excluded.status END
            """, (
                sample_id, technique, filename, dest_path, file_sz, description, status, now_str
            ))
            conn.commit()

        self.export_to_json()
        return dest_path

    def get_technique_files(self, sample_id, technique="mass_spec"):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if technique == "mass_spec":
                cursor.execute("""
                SELECT f.*, a.q_net_ads, a.q_net_des, a.recovery_pct, a.analyzed_at
                FROM characterization_files f
                LEFT JOIN mass_spec_analyses a ON f.sample_id = a.sample_id AND f.filename = a.filename
                WHERE f.sample_id = ? AND f.technique = ?
                ORDER BY f.uploaded_at DESC
                """, (sample_id, technique))
            else:
                cursor.execute("""
                SELECT * FROM characterization_files 
                WHERE sample_id = ? AND technique = ?
                ORDER BY uploaded_at DESC
                """, (sample_id, technique))
            return [dict(r) for r in cursor.fetchall()]

    def delete_file(self, sample_id, technique, filename):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT cloned_path FROM characterization_files WHERE sample_id=? AND technique=? AND filename=?",
                           (sample_id, technique, filename))
            row = cursor.fetchone()
            if row and row["cloned_path"] and os.path.exists(row["cloned_path"]):
                try:
                    os.remove(row["cloned_path"])
                except Exception:
                    pass

            cursor.execute("DELETE FROM characterization_files WHERE sample_id=? AND technique=? AND filename=?",
                           (sample_id, technique, filename))
            if technique == "mass_spec":
                cursor.execute("DELETE FROM mass_spec_analyses WHERE sample_id=? AND filename=?", (sample_id, filename))
            conn.commit()

        self.export_to_json()

    # ==================== MASS SPEC ANALYSES & CAPACITIES ====================

    def save_analysis(self, sample_id, filename, ranges, capacity_results, target_gas="CO2 (m/z 44.28)", report_text=""):
        """
        Stores the full analysis result into SQLite and updates the file and sample status to 'Analyzed'.
        """
        now_str = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
        q_ads = float(capacity_results.get("adsorption", {}).get("q_net_mmol_g", 0.0))
        q_des = float(capacity_results.get("desorption", {}).get("q_net_mmol_g", 0.0))
        rec = float(capacity_results.get("recovery_pct", 0.0))
        area_ads = float(capacity_results.get("adsorption", {}).get("area_a_min", 0.0))
        area_des = float(capacity_results.get("desorption", {}).get("area_a_min", 0.0))
        temp_c = float(capacity_results.get("temp_c", 24.0))
        vm_exp = float(capacity_results.get("Vm_exp", 24382.9))
        k_factor = float(capacity_results.get("k_factor", 0.0))
        m_act = float(capacity_results.get("mass_active_g", 0.0))

        with self.get_connection() as conn:
            cursor = conn.cursor()
            # 1. Insert/Update Analysis
            cursor.execute("""
            INSERT INTO mass_spec_analyses (
                sample_id, filename, target_gas, q_net_ads, q_net_des, recovery_pct,
                area_ads, area_des, temp_c, vm_exp, k_factor, mass_active_g,
                ranges_json, capacity_json, report_text, analyzed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(sample_id, filename) DO UPDATE SET
                target_gas=excluded.target_gas,
                q_net_ads=excluded.q_net_ads,
                q_net_des=excluded.q_net_des,
                recovery_pct=excluded.recovery_pct,
                area_ads=excluded.area_ads,
                area_des=excluded.area_des,
                temp_c=excluded.temp_c,
                vm_exp=excluded.vm_exp,
                k_factor=excluded.k_factor,
                mass_active_g=excluded.mass_active_g,
                ranges_json=excluded.ranges_json,
                capacity_json=excluded.capacity_json,
                report_text=excluded.report_text,
                analyzed_at=excluded.analyzed_at
            """, (
                sample_id, filename, target_gas, q_ads, q_des, rec,
                area_ads, area_des, temp_c, vm_exp, k_factor, m_act,
                json.dumps(ranges), json.dumps(capacity_results), report_text, now_str
            ))

            # 2. Update File status in characterization_files
            cursor.execute("""
            UPDATE characterization_files 
            SET status = 'Analyzed' 
            WHERE sample_id = ? AND filename = ?
            """, (sample_id, filename))

            # If file wasn't registered yet, add it
            cursor.execute("SELECT id FROM characterization_files WHERE sample_id=? AND filename=?", (sample_id, filename))
            if cursor.fetchone() is None:
                cursor.execute("""
                INSERT INTO characterization_files (
                    sample_id, technique, filename, size_bytes, description, status, uploaded_at
                ) VALUES (?, 'mass_spec', ?, 0, 'Mass Spectrometry Data File', 'Analyzed', ?)
                """, (sample_id, filename, now_str))

            # 3. Update Sample overall status to Analyzed
            cursor.execute("UPDATE samples SET status = 'Analyzed', updated_at = ? WHERE sample_id = ?", (now_str, sample_id))
            conn.commit()

        self.export_to_json()
        return {
            "sample_id": sample_id,
            "filename": filename,
            "q_net_ads": q_ads,
            "q_net_des": q_des,
            "recovery_pct": rec,
            "analyzed_at": now_str
        }

    def load_analysis(self, sample_id, filename):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM mass_spec_analyses WHERE sample_id=? AND filename=?", (sample_id, filename))
            row = cursor.fetchone()
            if row:
                res = dict(row)
                res["ranges"] = json.loads(res["ranges_json"]) if res.get("ranges_json") else []
                res["capacity"] = json.loads(res["capacity_json"]) if res.get("capacity_json") else {}
                return res
            return None

    # ==================== TECHNIQUE PROPERTIES (BET, XRD, NOTES) ====================

    def save_properties(self, sample_id, technique, props_dict, notes=""):
        now_str = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO technique_properties (sample_id, technique, properties_json, notes, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(sample_id, technique) DO UPDATE SET
                properties_json=excluded.properties_json,
                notes=excluded.notes,
                updated_at=excluded.updated_at
            """, (sample_id, technique, json.dumps(props_dict), notes, now_str))
            conn.commit()
        self.export_to_json()

    def get_properties(self, sample_id, technique):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM technique_properties WHERE sample_id=? AND technique=?", (sample_id, technique))
            row = cursor.fetchone()
            if row:
                d = dict(row)
                props = json.loads(d.get("properties_json") or "{}")
                props["notes"] = d.get("notes", "")
                return props
            return {}

    # ==================== JSON EXPORT / SYNC ====================

    def export_to_json(self):
        """
        Exports the entire SQLite database into samples_logbook.json
        so that human-readable JSON files are always 100% updated and preserved.
        """
        export_dict = {}
        samples = self.list_samples()
        for s in samples:
            s_id = s["sample_id"]
            export_dict[s_id] = {
                "sample_id": s_id,
                "material_name": s["material_name"],
                "operator": s["operator"],
                "date": s["date"],
                "mass_total_g": s["mass_total_g"],
                "water_loss_pct": s["water_loss_pct"],
                "mass_active_g": s["mass_active_g"],
                "ref_ads": s["ref_ads_mmol_g"],
                "ref_des": s["ref_des_mmol_g"],
                "c0": s["c0"],
                "flow_total": s["flow_total"],
                "temp_c": s["temp_c"],
                "notes": s["notes"],
                "status": s["status"],
                "created_at": s["created_at"],
                "updated_at": s["updated_at"],
                "characterizations": {
                    "mass_spec": {
                        "files": self.get_technique_files(s_id, "mass_spec"),
                        "notes": self.get_properties(s_id, "mass_spec").get("notes", "")
                    },
                    "xrd": {
                        "files": self.get_technique_files(s_id, "xrd"),
                        "notes": self.get_properties(s_id, "xrd").get("notes", "")
                    },
                    "bet": {
                        "files": self.get_technique_files(s_id, "bet"),
                        **self.get_properties(s_id, "bet")
                    },
                    "raman": {
                        "files": self.get_technique_files(s_id, "raman"),
                        "notes": self.get_properties(s_id, "raman").get("notes", "")
                    },
                    "documents": {
                        "files": self.get_technique_files(s_id, "documents"),
                        "notes": self.get_properties(s_id, "documents").get("notes", "")
                    }
                }
            }

        try:
            with open(self.json_path, "w", encoding="utf-8") as f:
                json.dump(export_dict, f, indent=2)
        except Exception:
            pass
        return export_dict
