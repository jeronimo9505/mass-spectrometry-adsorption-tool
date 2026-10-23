import os
import shutil
import sqlite3
import pandas as pd

DOCUMENT_CATEGORIES = [
    ("🎤 Conference Certificate (Oral / Poster / Attendance)", "Conference Certificate"),
    ("🔬 Standard Operating Procedure (SOP)", "SOP"),
    ("📑 PhD Research Plan & Project Proposal", "Research Plan"),
    ("💾 Data Management Plan (DMP)", "Data Management Plan"),
    ("📜 Certificate of Analysis (CoA) & Material Spec", "Certificate"),
    ("⚖️ Instrument Calibration & Training Certificate", "Calibration"),
    ("🎓 PhD Milestone & Progress Evaluation", "PhD Milestone"),
    ("📝 Manuscript Draft & Peer Review", "Manuscript"),
    ("🛡️ Safety Data Sheet (MSDS) & Risk Protocol", "Safety / MSDS"),
    ("🏛️ Fellowship, Grant & Official Letter", "Fellowship / Grant"),
    ("📊 Official Laboratory Test Report", "Official Report"),
    ("📁 General Academic Document", "General")
]

class OfficialDocumentManager:
    """
    Dedicated manager for Official Documents, Certificates, SOPs, and Compliance Files.
    Completely separated from individual sample characterization folders.
    
    Files are stored in: '<vault_path>/Official_Documents/'
    Metadata is tracked in the central SQLite database ('vault.db' -> 'official_documents' table).
    """
    FOLDER_NAME = "Official_Documents"

    def __init__(self, vault_path, db_manager):
        self.vault_path = os.path.abspath(vault_path)
        self.db = db_manager
        self.documents_dir = os.path.join(self.vault_path, self.FOLDER_NAME)
        self.ensure_structure()
        self.init_schema()
        self.migrate_legacy_characterization_documents()
        self.reconcile_filesystem()

    def ensure_structure(self):
        os.makedirs(self.documents_dir, exist_ok=True)

    def init_schema(self):
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
            CREATE TABLE IF NOT EXISTS official_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'Certificate',
                filename TEXT NOT NULL,
                stored_path TEXT NOT NULL,
                file_size_bytes INTEGER DEFAULT 0,
                related_sample_id TEXT DEFAULT 'All / General',
                issuer TEXT DEFAULT '',
                issue_date TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                uploaded_at TEXT
            )
            """)
            conn.commit()

    def add_document(self, source_path, title, category="Certificate", related_sample="All / General", prepared_by="", issue_date="", notes="", issuer=""):
        """
        Copies a document/certificate to the Official_Documents vault directory
        and registers its record in the database.
        """
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Source document not found: {source_path}")

        author_val = prepared_by.strip() if prepared_by else issuer.strip()
        if not author_val:
            author_val = "Shayan Gul, Reyes"

        filename = os.path.basename(source_path)
        dest_path = os.path.join(self.documents_dir, filename)

        # Handle filename collisions
        base, ext = os.path.splitext(filename)
        counter = 1
        while os.path.exists(dest_path) and os.path.abspath(source_path) != os.path.abspath(dest_path):
            dest_path = os.path.join(self.documents_dir, f"{base}_{counter}{ext}")
            counter += 1

        final_filename = os.path.basename(dest_path)

        if os.path.abspath(source_path) != os.path.abspath(dest_path):
            shutil.copy2(source_path, dest_path)

        sz = os.path.getsize(dest_path) if os.path.exists(dest_path) else 0
        now_str = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")

        if not issue_date:
            issue_date = pd.Timestamp.now().strftime("%Y-%m-%d")

        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
            INSERT INTO official_documents (
                title, category, filename, stored_path, file_size_bytes,
                related_sample_id, issuer, issue_date, notes, uploaded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                title.strip() or final_filename,
                category,
                final_filename,
                dest_path,
                sz,
                related_sample.strip() or "All / General",
                author_val,
                issue_date.strip(),
                notes.strip(),
                now_str
            ))
            conn.commit()
            doc_id = cur.lastrowid

        return doc_id

    def list_documents(self, category_filter=None, search_query=None):
        """Lists all registered documents, optionally filtered."""
        query = "SELECT * FROM official_documents WHERE 1=1"
        params = []

        if category_filter and category_filter != "All Categories":
            query += " AND category = ?"
            params.append(category_filter)

        if search_query:
            sq = f"%{search_query.strip().lower()}%"
            query += " AND (LOWER(title) LIKE ? OR LOWER(filename) LIKE ? OR LOWER(issuer) LIKE ? OR LOWER(notes) LIKE ? OR LOWER(related_sample_id) LIKE ?)"
            params.extend([sq, sq, sq, sq, sq])

        query += " ORDER BY id DESC"

        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            rows = cur.fetchall()
            return [dict(r) for r in rows]

    def get_document(self, doc_id):
        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM official_documents WHERE id = ?", (doc_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def update_document(self, doc_id, title=None, category=None, related_sample=None, prepared_by=None, issue_date=None, notes=None, issuer=None):
        updates = []
        params = []
        if title is not None:
            updates.append("title = ?")
            params.append(title.strip())
        if category is not None:
            updates.append("category = ?")
            params.append(category.strip())
        if related_sample is not None:
            updates.append("related_sample_id = ?")
            params.append(related_sample.strip())
        
        author_val = prepared_by if prepared_by is not None else issuer
        if author_val is not None:
            updates.append("issuer = ?")
            params.append(author_val.strip())
        if issue_date is not None:
            updates.append("issue_date = ?")
            params.append(issue_date.strip())
        if notes is not None:
            updates.append("notes = ?")
            params.append(notes.strip())

        if not updates:
            return False

        params.append(doc_id)
        sql = f"UPDATE official_documents SET {', '.join(updates)} WHERE id = ?"

        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, params)
            conn.commit()
            return cur.rowcount > 0

    def delete_document(self, doc_id, delete_file_on_disk=True):
        doc = self.get_document(doc_id)
        if not doc:
            return False

        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM official_documents WHERE id = ?", (doc_id,))
            conn.commit()

        if delete_file_on_disk and doc.get("stored_path") and os.path.exists(doc["stored_path"]):
            try:
                os.remove(doc["stored_path"])
            except Exception:
                pass

        return True

    def open_document(self, doc_id):
        doc = self.get_document(doc_id)
        if doc and doc.get("stored_path") and os.path.exists(doc["stored_path"]):
            os.startfile(doc["stored_path"])
            return True
        return False

    def open_documents_folder(self):
        if os.path.exists(self.documents_dir):
            os.startfile(self.documents_dir)
            return True
        return False

    def migrate_legacy_characterization_documents(self):
        """
        Migrates any documents previously stored inside sample characterization folders
        (samples/<id>/documents/) to the new top-level Official_Documents vault directory.
        """
        samples_dir = os.path.join(self.vault_path, "samples")
        if not os.path.exists(samples_dir):
            return

        for s_entry in os.scandir(samples_dir):
            if not s_entry.is_dir():
                continue
            s_id = s_entry.name
            legacy_doc_dir = os.path.join(s_entry.path, "documents")

            if os.path.exists(legacy_doc_dir):
                for fname in os.listdir(legacy_doc_dir):
                    fpath = os.path.join(legacy_doc_dir, fname)
                    if os.path.isfile(fpath):
                        base_name = os.path.splitext(fname)[0].replace("_", " ").title()
                        lower_fn = fname.lower()
                        cat = "General"
                        if "conf" in lower_fn or "conference" in lower_fn:
                            cat = "Conference"
                        elif "sop" in lower_fn:
                            cat = "SOP"
                        elif "data_management" in lower_fn or "dmp" in lower_fn:
                            cat = "Data Management Plan"
                        elif "plan" in lower_fn or "research" in lower_fn:
                            cat = "Research Plan"
                        elif "cert" in lower_fn:
                            cat = "Certificate"
                        elif "calib" in lower_fn:
                            cat = "Calibration"

                        with self.db.get_connection() as conn:
                            cur = conn.cursor()
                            cur.execute("SELECT id FROM official_documents WHERE filename = ?", (fname,))
                            exists = cur.fetchone()

                        if not exists:
                            self.add_document(
                                source_path=fpath,
                                title=base_name,
                                category=cat,
                                related_sample=s_id,
                                prepared_by="Shayan Gul, Reyes",
                                notes=f"Migrated from sample {s_id} characterization"
                            )

                try:
                    if not os.listdir(legacy_doc_dir):
                        os.rmdir(legacy_doc_dir)
                except Exception:
                    pass

    def reconcile_filesystem(self):
        """
        Scans the Official_Documents directory for any files placed there externally
        by the user in Windows Explorer and auto-registers them.
        """
        if not os.path.exists(self.documents_dir):
            return

        with self.db.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT filename FROM official_documents")
            registered_filenames = {row["filename"] for row in cur.fetchall()}

        for fname in os.listdir(self.documents_dir):
            fpath = os.path.join(self.documents_dir, fname)
            if os.path.isfile(fpath) and fname not in registered_filenames:
                base_name = os.path.splitext(fname)[0].replace("_", " ").title()
                cat = "General"
                lower_fn = fname.lower()
                if "conf" in lower_fn or "conference" in lower_fn:
                    cat = "Conference"
                elif "sop" in lower_fn:
                    cat = "SOP"
                elif "data_management" in lower_fn or "dmp" in lower_fn:
                    cat = "Data Management Plan"
                elif "plan" in lower_fn or "research" in lower_fn:
                    cat = "Research Plan"
                elif "calib" in lower_fn:
                    cat = "Calibration"
                elif "cert" in lower_fn:
                    cat = "Certificate"
                elif "msds" in lower_fn or "sds" in lower_fn or "safety" in lower_fn:
                    cat = "Safety / MSDS"
                elif "paper" in lower_fn or "manuscript" in lower_fn:
                    cat = "Manuscript"
                elif "milestone" in lower_fn or "progress" in lower_fn:
                    cat = "PhD Milestone"
                elif "grant" in lower_fn or "fellowship" in lower_fn:
                    cat = "Fellowship / Grant"
                elif "report" in lower_fn:
                    cat = "Official Report"

                sz = os.path.getsize(fpath)
                now_str = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")

                with self.db.get_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("""
                    INSERT INTO official_documents (
                        title, category, filename, stored_path, file_size_bytes,
                        related_sample_id, issuer, issue_date, notes, uploaded_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        base_name,
                        cat,
                        fname,
                        fpath,
                        sz,
                        "All / General",
                        "Shayan Gul, Reyes",
                        pd.Timestamp.now().strftime("%Y-%m-%d"),
                        "Auto-discovered from Official_Documents folder",
                        now_str
                    ))
                    conn.commit()
