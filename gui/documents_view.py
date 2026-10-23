import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime

DOCUMENT_CATEGORIES_DISPLAY = [
    "All Categories",
    "🎤 Conference Certificate (Oral / Poster / Attendance)",
    "🔬 Standard Operating Procedure (SOP)",
    "📑 PhD Research Plan & Project Proposal",
    "💾 Data Management Plan (DMP)",
    "📜 Certificate of Analysis (CoA) & Material Spec",
    "⚖️ Instrument Calibration & Training Certificate",
    "🎓 PhD Milestone & Progress Evaluation",
    "📝 Manuscript Draft & Peer Review",
    "🛡️ Safety Data Sheet (MSDS) & Risk Protocol",
    "🏛️ Fellowship, Grant & Official Letter",
    "📊 Official Laboratory Test Report",
    "📁 General Academic Document"
]

CATEGORY_NAME_MAP = {
    "🎤 Conference Certificate (Oral / Poster / Attendance)": "Conference Certificate",
    "Conference Certificate": "Conference Certificate",
    "Conference": "Conference Certificate",
    "🔬 Standard Operating Procedure (SOP)": "SOP",
    "SOP": "SOP",
    "📑 PhD Research Plan & Project Proposal": "Research Plan",
    "Research Plan": "Research Plan",
    "💾 Data Management Plan (DMP)": "Data Management Plan",
    "Data Management Plan": "Data Management Plan",
    "📜 Certificate of Analysis (CoA) & Material Spec": "Certificate",
    "Certificate": "Certificate",
    "⚖️ Instrument Calibration & Training Certificate": "Calibration",
    "Calibration": "Calibration",
    "🎓 PhD Milestone & Progress Evaluation": "PhD Milestone",
    "PhD Milestone": "PhD Milestone",
    "📝 Manuscript Draft & Peer Review": "Manuscript",
    "Manuscript": "Manuscript",
    "🛡️ Safety Data Sheet (MSDS) & Risk Protocol": "Safety / MSDS",
    "Safety / MSDS": "Safety / MSDS",
    "🏛️ Fellowship, Grant & Official Letter": "Fellowship / Grant",
    "Fellowship / Grant": "Fellowship / Grant",
    "📊 Official Laboratory Test Report": "Official Report",
    "Official Report": "Official Report",
    "📁 General Academic Document": "General",
    "General": "General"
}

CATEGORY_REV_MAP = {
    "Conference Certificate": "🎤 Conference Certificate (Oral / Poster / Attendance)",
    "Conference": "🎤 Conference Certificate (Oral / Poster / Attendance)",
    "SOP": "🔬 Standard Operating Procedure (SOP)",
    "Research Plan": "📑 PhD Research Plan & Project Proposal",
    "Data Management Plan": "💾 Data Management Plan (DMP)",
    "Certificate": "📜 Certificate of Analysis (CoA) & Material Spec",
    "Calibration": "⚖️ Instrument Calibration & Training Certificate",
    "PhD Milestone": "🎓 PhD Milestone & Progress Evaluation",
    "Manuscript": "📝 Manuscript Draft & Peer Review",
    "Safety / MSDS": "🛡️ Safety Data Sheet (MSDS) & Risk Protocol",
    "Fellowship / Grant": "🏛️ Fellowship, Grant & Official Letter",
    "Official Report": "📊 Official Laboratory Test Report",
    "General": "📁 General Academic Document"
}

class DocumentMetadataDialog(tk.Toplevel):
    """Modal dialog for adding or editing official document/certificate metadata."""
    def __init__(self, parent, title="Add Official Document / Certificate", doc_data=None, sample_ids=None):
        super().__init__(parent)
        self.title(title)
        self.geometry("560x490")
        self.minsize(500, 430)
        self.transient(parent)
        self.grab_set()

        self.result = None
        self.doc_data = doc_data or {}
        self.sample_ids = ["All / General"] + (sample_ids or [])

        self.create_widgets()
        self.center_window(parent)

    def center_window(self, parent):
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_rooty() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

    def create_widgets(self):
        container = ttk.Frame(self, padding=16)
        container.pack(fill=tk.BOTH, expand=True)

        header = ttk.Label(
            container, 
            text="Official Academic & Laboratory Document Record", 
            font=("Segoe UI", 11, "bold")
        )
        header.pack(anchor="w", pady=(0, 12))

        form = ttk.Frame(container)
        form.pack(fill=tk.BOTH, expand=True)

        row = 0
        # File path picker (if new document)
        if not self.doc_data.get("id"):
            ttk.Label(form, text="Source File:*").grid(row=row, column=0, sticky="w", pady=5)
            file_frame = ttk.Frame(form)
            file_frame.grid(row=row, column=1, sticky="ew", pady=5)
            self.path_var = tk.StringVar(value=self.doc_data.get("source_path", ""))
            self.path_entry = ttk.Entry(file_frame, textvariable=self.path_var, width=32)
            self.path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
            ttk.Button(file_frame, text="Browse...", command=self.on_browse_file).pack(side=tk.RIGHT)
            row += 1

        # Title
        ttk.Label(form, text="Document Title:*").grid(row=row, column=0, sticky="w", pady=5)
        self.title_var = tk.StringVar(value=self.doc_data.get("title", ""))
        self.title_entry = ttk.Entry(form, textvariable=self.title_var, width=38)
        self.title_entry.grid(row=row, column=1, sticky="ew", pady=5)
        row += 1

        # Category
        ttk.Label(form, text="Category:*").grid(row=row, column=0, sticky="w", pady=5)
        raw_cat = self.doc_data.get("category", "Conference Certificate")
        disp_cat = CATEGORY_REV_MAP.get(raw_cat, "🎤 Conference Certificate (Oral / Poster / Attendance)")
        self.cat_var = tk.StringVar(value=disp_cat)
        cat_choices = [c for c in DOCUMENT_CATEGORIES_DISPLAY if c != "All Categories"]
        self.cat_combo = ttk.Combobox(form, textvariable=self.cat_var, values=cat_choices, state="readonly", width=38, height=14)
        self.cat_combo.grid(row=row, column=1, sticky="ew", pady=5)
        row += 1

        # Document Prepared By (replaced Issuer)
        ttk.Label(form, text="Document Prepared By:*").grid(row=row, column=0, sticky="w", pady=5)
        initial_author = self.doc_data.get("issuer") or "Shayan Gul, Reyes"
        self.prepared_by_var = tk.StringVar(value=initial_author)
        ttk.Entry(form, textvariable=self.prepared_by_var, width=38).grid(row=row, column=1, sticky="ew", pady=5)
        row += 1

        # Related Sample
        ttk.Label(form, text="Related Sample:").grid(row=row, column=0, sticky="w", pady=5)
        self.sample_var = tk.StringVar(value=self.doc_data.get("related_sample_id", "All / General"))
        self.sample_combo = ttk.Combobox(form, textvariable=self.sample_var, values=self.sample_ids, state="readonly", width=36)
        self.sample_combo.grid(row=row, column=1, sticky="ew", pady=5)
        row += 1

        # Issue / Creation Date
        ttk.Label(form, text="Issue / Creation Date:").grid(row=row, column=0, sticky="w", pady=5)
        default_date = self.doc_data.get("issue_date") or datetime.now().strftime("%Y-%m-%d")
        self.date_var = tk.StringVar(value=default_date)
        ttk.Entry(form, textvariable=self.date_var, width=38).grid(row=row, column=1, sticky="ew", pady=5)
        row += 1

        # Notes
        ttk.Label(form, text="Notes / Description:").grid(row=row, column=0, sticky="nw", pady=5)
        self.notes_text = tk.Text(form, height=4, width=38, font=("Segoe UI", 9))
        self.notes_text.grid(row=row, column=1, sticky="ew", pady=5)
        self.notes_text.insert("1.0", self.doc_data.get("notes", ""))
        row += 1

        form.columnconfigure(1, weight=1)

        # Buttons
        btn_frame = ttk.Frame(container)
        btn_frame.pack(fill=tk.X, pady=(16, 0))

        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side=tk.RIGHT, padx=4)
        ttk.Button(btn_frame, text="💾 Save Record", command=self.on_save).pack(side=tk.RIGHT, padx=4)

    def on_browse_file(self):
        filetypes = [
            ("All Academic Documents", "*.pdf;*.docx;*.doc;*.xlsx;*.xls;*.pptx;*.ppt;*.png;*.jpg;*.jpeg;*.txt"),
            ("PDF Documents", "*.pdf"),
            ("Word Documents", "*.docx;*.doc"),
            ("Excel Spreadsheets", "*.xlsx;*.xls"),
            ("Presentations", "*.pptx;*.ppt"),
            ("Images", "*.png;*.jpg;*.jpeg"),
            ("All Files", "*.*")
        ]
        fpath = filedialog.askopenfilename(title="Select Document or Certificate to Archive", filetypes=filetypes)
        if fpath:
            self.path_var.set(fpath)
            if not self.title_var.get().strip():
                base = os.path.splitext(os.path.basename(fpath))[0].replace("_", " ").title()
                self.title_var.set(base)

    def on_save(self):
        title = self.title_var.get().strip()
        disp_cat = self.cat_var.get()
        cat_key = CATEGORY_NAME_MAP.get(disp_cat, "General")
        prepared_by = self.prepared_by_var.get().strip() or "Shayan Gul, Reyes"

        if not self.doc_data.get("id"):
            src_path = self.path_var.get().strip()
            if not src_path or not os.path.exists(src_path):
                messagebox.showwarning("File Required", "Please choose a valid file to archive.", parent=self)
                return
        else:
            src_path = None

        if not title:
            messagebox.showwarning("Title Required", "Document title cannot be empty.", parent=self)
            self.title_entry.focus_set()
            return

        self.result = {
            "source_path": src_path,
            "title": title,
            "category": cat_key,
            "related_sample_id": self.sample_var.get().strip() or "All / General",
            "prepared_by": prepared_by,
            "issue_date": self.date_var.get().strip(),
            "notes": self.notes_text.get("1.0", tk.END).strip()
        }
        self.destroy()


class OfficialDocumentsView(ttk.Frame):
    """
    Module 4: Official Documents & Certificates Vault.
    Maintains an independent archive for PhD and lab documents:
      - 🎤 Conference Certificates & Presentations
      - 🔬 Standard Operating Procedures (SOPs) & Protocols
      - 📑 PhD Research Plans & Project Proposals
      - 💾 Data Management Plans (DMPs)
      - 📜 Certificates of Analysis & Material Specs
      - ⚖️ Equipment Calibration & Training Certificates
      - 🎓 PhD Milestones & Progress Reports
      - 📝 Manuscript Drafts & Peer Reviews
      - 🛡️ Safety Data Sheets (MSDS) & Risk Protocols
    """
    def __init__(self, parent, doc_manager, vault):
        super().__init__(parent, padding=8)
        self.doc_manager = doc_manager
        self.vault = vault
        self.active_doc_id = None

        self.create_widgets()
        self.refresh_table()

    def create_widgets(self):
        # 1. Header Banner
        banner_frame = tk.Frame(self, bg="#1d3557", bd=1, relief="solid", padx=14, pady=10)
        banner_frame.pack(fill=tk.X, pady=(0, 8))

        lbl_title = tk.Label(
            banner_frame,
            text="📑 OFFICIAL DOCUMENTS & PHD ACADEMIC ARCHIVE",
            font=("Segoe UI", 12, "bold"),
            bg="#1d3557",
            fg="#ffffff"
        )
        lbl_title.pack(anchor="w")

        lbl_desc = tk.Label(
            banner_frame,
            text="Dedicated laboratory repository for Conference Certificates, SOPs, PhD Research & Data Plans, Calibrations, Manuscripts, and Official Reports — safely isolated from sample characterizations.",
            font=("Segoe UI", 9),
            bg="#1d3557",
            fg="#a8dadc"
        )
        lbl_desc.pack(anchor="w", pady=(2, 0))

        # 2. KPI Cards
        kpi_frame = ttk.Frame(self)
        kpi_frame.pack(fill=tk.X, pady=(0, 8))

        self.card_total = self._create_kpi_card(kpi_frame, "📁 Total Documents", "0", "#1d3557")
        self.card_total.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

        self.card_conf = self._create_kpi_card(kpi_frame, "🎤 Conferences & Milestones", "0", "#2a9d8f")
        self.card_conf.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

        self.card_sops = self._create_kpi_card(kpi_frame, "🔬 SOPs & Protocols", "0", "#457b9d")
        self.card_sops.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

        self.card_plans = self._create_kpi_card(kpi_frame, "📑 Research Plans & DMPs", "0", "#e76f51")
        self.card_plans.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

        # 3. Action & Filter Toolbar
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, pady=(2, 6))

        ttk.Label(toolbar, text="Filter Category:").pack(side=tk.LEFT, padx=(0, 4))
        self.cat_filter_var = tk.StringVar(value="All Categories")
        self.cat_filter_combo = ttk.Combobox(
            toolbar, 
            textvariable=self.cat_filter_var, 
            values=DOCUMENT_CATEGORIES_DISPLAY, 
            state="readonly", 
            width=34,
            height=14
        )
        self.cat_filter_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.cat_filter_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_table())

        ttk.Label(toolbar, text="🔍 Search:").pack(side=tk.LEFT, padx=(0, 4))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self.refresh_table())
        search_entry = ttk.Entry(toolbar, textvariable=self.search_var, width=18)
        search_entry.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(toolbar, text="➕ Add Document / Certificate", command=self.on_add_document).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="📄 Open Selected", command=self.on_open_selected).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="📂 Open Folder", command=self.on_open_folder).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="✏️ Edit Info", command=self.on_edit_document).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="🗑️ Delete", command=self.on_delete_document).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="🔄 Refresh", command=self.on_refresh).pack(side=tk.LEFT, padx=3)

        # 4. Main Documents Treeview Table
        table_frame = ttk.Frame(self)
        table_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("id", "cat", "title", "filename", "sample", "prepared_by", "date", "size", "uploaded")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")

        self.tree.heading("id", text="ID")
        self.tree.heading("cat", text="Category")
        self.tree.heading("title", text="Document Title")
        self.tree.heading("filename", text="Archived File Name")
        self.tree.heading("sample", text="Related Sample")
        self.tree.heading("prepared_by", text="Document Prepared By")
        self.tree.heading("date", text="Issue / Creation Date")
        self.tree.heading("size", text="File Size")
        self.tree.heading("uploaded", text="Archived On")

        self.tree.column("id", width=40, anchor="center")
        self.tree.column("cat", width=155, anchor="w")
        self.tree.column("title", width=220, anchor="w")
        self.tree.column("filename", width=220, anchor="w")
        self.tree.column("sample", width=115, anchor="center")
        self.tree.column("prepared_by", width=160, anchor="w")
        self.tree.column("date", width=95, anchor="center")
        self.tree.column("size", width=80, anchor="center")
        self.tree.column("uploaded", width=120, anchor="center")

        scroll_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        scroll_x = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        scroll_x.pack(side=tk.BOTTOM, fill=tk.X)

        self.tree.bind("<<TreeviewSelect>>", self.on_row_select)
        self.tree.bind("<Double-1>", lambda e: self.on_open_selected())

        # 5. Detail Info Pane at Bottom
        self.detail_frame = tk.Frame(self, bg="#f8f9fa", bd=1, relief="solid", padx=12, pady=8)
        self.detail_frame.pack(fill=tk.X, pady=(8, 0))

        self.lbl_detail_title = tk.Label(
            self.detail_frame, 
            text="Selected Document: [ None Selected ]", 
            font=("Segoe UI", 10, "bold"), 
            bg="#f8f9fa", 
            fg="#1d3557"
        )
        self.lbl_detail_title.pack(anchor="w")

        self.lbl_detail_meta = tk.Label(
            self.detail_frame, 
            text="Double-click any document or select it and click '📄 Open Selected' to view with system viewer.", 
            font=("Segoe UI", 9), 
            bg="#f8f9fa", 
            fg="#6c757d"
        )
        self.lbl_detail_meta.pack(anchor="w", pady=(2, 0))

    def _create_kpi_card(self, parent, title, value, color):
        frame = tk.Frame(parent, bg="#ffffff", bd=1, relief="solid", padx=10, pady=6)
        lbl_title = tk.Label(frame, text=title, font=("Segoe UI", 9), bg="#ffffff", fg="#6c757d")
        lbl_title.pack(anchor="w")
        lbl_val = tk.Label(frame, text=value, font=("Segoe UI", 13, "bold"), bg="#ffffff", fg=color)
        lbl_val.pack(anchor="w")
        frame.val_label = lbl_val
        return frame

    def refresh_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        disp_cat = self.cat_filter_var.get()
        cat_key = CATEGORY_NAME_MAP.get(disp_cat) if disp_cat != "All Categories" else None
        sq = self.search_var.get().strip()

        docs = self.doc_manager.list_documents(category_filter=cat_key, search_query=sq)

        # Update KPI cards based on all documents
        all_docs = self.doc_manager.list_documents()
        total_cnt = len(all_docs)
        conf_cnt = sum(1 for d in all_docs if d.get("category") in ["Conference", "PhD Milestone", "Manuscript", "Fellowship / Grant"])
        sops_cnt = sum(1 for d in all_docs if d.get("category") in ["SOP", "Calibration", "Safety / MSDS"])
        plans_cnt = sum(1 for d in all_docs if d.get("category") in ["Research Plan", "Data Management Plan", "Certificate", "Official Report", "General"])

        self.card_total.val_label.config(text=str(total_cnt))
        self.card_conf.val_label.config(text=str(conf_cnt))
        self.card_sops.val_label.config(text=str(sops_cnt))
        self.card_plans.val_label.config(text=str(plans_cnt))

        # Populate table
        for d in docs:
            sz_b = d.get("file_size_bytes", 0)
            if sz_b > 1024 * 1024:
                sz_str = f"{sz_b / (1024 * 1024):.1f} MB"
            elif sz_b > 1024:
                sz_str = f"{sz_b / 1024:.0f} KB"
            else:
                sz_str = f"{sz_b} B"

            raw_c = d.get("category", "")
            disp_category = CATEGORY_REV_MAP.get(raw_c, raw_c)

            self.tree.insert(
                "",
                tk.END,
                iid=str(d["id"]),
                values=(
                    d["id"],
                    disp_category,
                    d.get("title", ""),
                    d.get("filename", ""),
                    d.get("related_sample_id", "All / General"),
                    d.get("issuer", "Shayan Gul, Reyes"),
                    d.get("issue_date", ""),
                    sz_str,
                    d.get("uploaded_at", "")
                )
            )

        if not docs:
            self.lbl_detail_title.config(text="Selected Document: [ None Selected ]")
            self.lbl_detail_meta.config(text="No documents match current filters.")
            self.active_doc_id = None

    def on_row_select(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        doc_id = int(sel[0])
        self.active_doc_id = doc_id
        doc = self.doc_manager.get_document(doc_id)
        if doc:
            t = doc.get("title", "Document")
            fn = doc.get("filename", "")
            prep = doc.get("issuer", "Shayan Gul, Reyes")
            dt = doc.get("issue_date", "-")
            sp = doc.get("stored_path", "")
            notes = doc.get("notes", "")

            self.lbl_detail_title.config(text=f"Selected: {t} ({fn})")
            meta_str = f"Document Prepared By: {prep}  |  Date: {dt}  |  Path: {sp}"
            if notes:
                meta_str += f"\nNotes: {notes}"
            self.lbl_detail_meta.config(text=meta_str)

    def on_add_document(self):
        sample_ids = list(self.vault.logbook.keys())
        dlg = DocumentMetadataDialog(self, title="➕ Add Official Document / Certificate", sample_ids=sample_ids)
        self.wait_window(dlg)

        if dlg.result:
            try:
                new_id = self.doc_manager.add_document(
                    source_path=dlg.result["source_path"],
                    title=dlg.result["title"],
                    category=dlg.result["category"],
                    related_sample=dlg.result["related_sample_id"],
                    prepared_by=dlg.result["prepared_by"],
                    issue_date=dlg.result["issue_date"],
                    notes=dlg.result["notes"]
                )
                self.refresh_table()
                self.tree.selection_set(str(new_id))
                self.tree.see(str(new_id))
                self.on_row_select()
                messagebox.showinfo("Document Archived", f"Official document successfully registered and archived!\nFile: {os.path.basename(dlg.result['source_path'])}")
            except Exception as e:
                messagebox.showerror("Error Adding Document", f"Failed to archive document:\n{e}")

    def on_edit_document(self):
        if not self.active_doc_id:
            messagebox.showinfo("Select Document", "Please select a document from the table to edit.")
            return

        doc = self.doc_manager.get_document(self.active_doc_id)
        if not doc:
            return

        sample_ids = list(self.vault.logbook.keys())
        dlg = DocumentMetadataDialog(self, title=f"✏️ Edit: {doc.get('title')}", doc_data=doc, sample_ids=sample_ids)
        self.wait_window(dlg)

        if dlg.result:
            try:
                self.doc_manager.update_document(
                    doc_id=self.active_doc_id,
                    title=dlg.result["title"],
                    category=dlg.result["category"],
                    related_sample=dlg.result["related_sample_id"],
                    prepared_by=dlg.result["prepared_by"],
                    issue_date=dlg.result["issue_date"],
                    notes=dlg.result["notes"]
                )
                self.refresh_table()
                self.tree.selection_set(str(self.active_doc_id))
                self.on_row_select()
                messagebox.showinfo("Updated", "Document record successfully updated.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update document:\n{e}")

    def on_delete_document(self):
        if not self.active_doc_id:
            messagebox.showinfo("Select Document", "Please select a document to delete.")
            return

        doc = self.doc_manager.get_document(self.active_doc_id)
        if not doc:
            return

        confirm = messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to permanently delete:\n\n'{doc.get('title')}' ({doc.get('filename')})?\n\nThis will remove the file from the vault archive."
        )
        if confirm:
            self.doc_manager.delete_document(self.active_doc_id, delete_file_on_disk=True)
            self.active_doc_id = None
            self.refresh_table()

    def on_open_selected(self):
        if not self.active_doc_id:
            messagebox.showinfo("Select Document", "Please select a document from the table to open.")
            return

        ok = self.doc_manager.open_document(self.active_doc_id)
        if not ok:
            messagebox.showwarning("File Missing", "Document file could not be found on disk.")

    def on_open_folder(self):
        self.doc_manager.open_documents_folder()

    def on_refresh(self):
        self.doc_manager.reconcile_filesystem()
        self.refresh_table()
