import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime

class SampleDialog(tk.Toplevel):
    """Modal dialog for creating or editing sample metadata."""
    def __init__(self, parent, title="New Sample", sample_data=None):
        super().__init__(parent)
        self.title(title)
        self.geometry("490x580")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.result = None
        self.sample_data = sample_data or {}

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

        header = ttk.Label(container, text="Sample Information & Synthesis Details", font=("Segoe UI", 11, "bold"))
        header.pack(anchor="w", pady=(0, 12))

        form = ttk.Frame(container)
        form.pack(fill=tk.X, expand=True)

        row = 0
        ttk.Label(form, text="Sample ID:*").grid(row=row, column=0, sticky="w", pady=4)
        self.id_var = tk.StringVar(value=self.sample_data.get("sample_id", ""))
        self.id_entry = ttk.Entry(form, textvariable=self.id_var, width=28)
        self.id_entry.grid(row=row, column=1, sticky="ew", pady=4)
        if self.sample_data.get("sample_id"):
            self.id_entry.config(state="readonly")
        row += 1

        ttk.Label(form, text="Material Name / Formulation:*").grid(row=row, column=0, sticky="w", pady=4)
        self.mat_var = tk.StringVar(value=self.sample_data.get("material_name", ""))
        ttk.Entry(form, textvariable=self.mat_var, width=28).grid(row=row, column=1, sticky="ew", pady=4)
        row += 1

        ttk.Label(form, text="Operator / Researcher:").grid(row=row, column=0, sticky="w", pady=4)
        self.op_var = tk.StringVar(value=self.sample_data.get("operator", "Shayan / Jeronimo"))
        ttk.Entry(form, textvariable=self.op_var, width=28).grid(row=row, column=1, sticky="ew", pady=4)
        row += 1

        ttk.Label(form, text="Assay Date (YYYY-MM-DD):").grid(row=row, column=0, sticky="w", pady=4)
        default_date = self.sample_data.get("date") or datetime.now().strftime("%Y-%m-%d")
        self.date_var = tk.StringVar(value=default_date)
        ttk.Entry(form, textvariable=self.date_var, width=28).grid(row=row, column=1, sticky="ew", pady=4)
        row += 1

        ttk.Separator(form, orient="horizontal").grid(row=row, column=0, columnspan=2, sticky="ew", pady=10)
        row += 1

        ttk.Label(form, text="Total Initial Mass (g):*").grid(row=row, column=0, sticky="w", pady=4)
        self.mass_var = tk.DoubleVar(value=float(self.sample_data.get("mass_total_g", 0.5055)))
        ttk.Spinbox(form, from_=0.0001, to=100.0, increment=0.001, textvariable=self.mass_var, width=26).grid(row=row, column=1, sticky="ew", pady=4)
        row += 1

        ttk.Label(form, text="Water / Binder Loss (%):").grid(row=row, column=0, sticky="w", pady=4)
        self.water_var = tk.DoubleVar(value=float(self.sample_data.get("water_loss_pct", 21.4)))
        ttk.Spinbox(form, from_=0.0, to=100.0, increment=0.5, textvariable=self.water_var, width=26).grid(row=row, column=1, sticky="ew", pady=4)
        row += 1

        ttk.Label(form, text="Blank Ads Reference (mmol/g):").grid(row=row, column=0, sticky="w", pady=4)
        self.ref_ads_var = tk.DoubleVar(value=float(self.sample_data.get("ref_ads", 0.23)))
        ttk.Spinbox(form, from_=0.0, to=5.0, increment=0.01, textvariable=self.ref_ads_var, width=26).grid(row=row, column=1, sticky="ew", pady=4)
        row += 1

        ttk.Label(form, text="Notes / Observations:").grid(row=row, column=0, sticky="nw", pady=4)
        self.notes_text = tk.Text(form, height=4, width=28, font=("Segoe UI", 9))
        self.notes_text.grid(row=row, column=1, sticky="ew", pady=4)
        self.notes_text.insert("1.0", self.sample_data.get("notes", ""))
        row += 1

        form.columnconfigure(1, weight=1)

        # Buttons
        btn_frame = ttk.Frame(container)
        btn_frame.pack(fill=tk.X, pady=(16, 0))

        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side=tk.RIGHT, padx=4)
        ttk.Button(btn_frame, text="💾 Save Sample", command=self.on_save).pack(side=tk.RIGHT, padx=4)

    def on_save(self):
        sample_id = self.id_var.get().strip()
        mat_name = self.mat_var.get().strip()

        if not sample_id:
            messagebox.showwarning("Required Field", "Sample ID cannot be empty.", parent=self)
            self.id_entry.focus_set()
            return
        if not mat_name:
            messagebox.showwarning("Required Field", "Material name cannot be empty.", parent=self)
            return

        try:
            mass = float(self.mass_var.get())
            water = float(self.water_var.get())
            ref_ads = float(self.ref_ads_var.get())
        except ValueError:
            messagebox.showerror("Validation Error", "Mass and percentage values must be valid numbers.", parent=self)
            return

        self.result = {
            "sample_id": sample_id,
            "material_name": mat_name,
            "operator": self.op_var.get().strip(),
            "date": self.date_var.get().strip(),
            "mass_total_g": mass,
            "water_loss_pct": water,
            "ref_ads": ref_ads,
            "ref_des": 0.0,
            "c0": float(self.sample_data.get("c0", 0.15)),
            "flow_total": float(self.sample_data.get("flow_total", 100.0)),
            "temp_c": float(self.sample_data.get("temp_c", 24.0)),
            "notes": self.notes_text.get("1.0", tk.END).strip(),
            "status": self.sample_data.get("status", "Registered")
        }
        self.destroy()


class LogbookView(ttk.Frame):
    """
    Module 1: Sample Logbook View.
    Displays sample list, KPI summaries, and allows creating, editing and managing samples.
    """
    def __init__(self, parent, vault, on_select_sample_callback=None, on_open_mass_spec_callback=None):
        super().__init__(parent, padding=8)
        self.vault = vault
        self.on_select_sample_callback = on_select_sample_callback
        self.on_open_mass_spec_callback = on_open_mass_spec_callback
        self.active_sample_id = None

        self.create_widgets()
        self.refresh_table()

    def create_widgets(self):
        # 1. Top KPI Summary Cards
        kpi_frame = ttk.Frame(self)
        kpi_frame.pack(fill=tk.X, pady=(0, 8))

        self.card_total = self._create_kpi_card(kpi_frame, "📦 Total Samples", "0", "#1d3557")
        self.card_total.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

        self.card_analyzed = self._create_kpi_card(kpi_frame, "✅ Analyzed", "0", "#2a9d8f")
        self.card_analyzed.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

        self.card_mass = self._create_kpi_card(kpi_frame, "⚖️ Average Mass", "0.00 g", "#457b9d")
        self.card_mass.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

        # 2. Search & Action Toolbar
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, pady=(4, 8))

        ttk.Label(toolbar, text="🔍 Search:").pack(side=tk.LEFT, padx=(0, 4))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self.filter_table())
        search_entry = ttk.Entry(toolbar, textvariable=self.search_var, width=24)
        search_entry.pack(side=tk.LEFT, padx=(0, 12))

        ttk.Button(toolbar, text="➕ New Sample", command=self.on_new_sample).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="✏️ Edit", command=self.on_edit_sample).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="🗑️ Delete", command=self.on_delete_sample).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="📂 Open Folder", command=self.on_open_folder).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="🔄 Refresh", command=self.on_refresh).pack(side=tk.LEFT, padx=3)

        self.btn_go_hub = ttk.Button(
            toolbar, 
            text="🔬 View Characterizations ➔", 
            command=self.on_go_to_hub
        )
        self.btn_go_hub.pack(side=tk.RIGHT, padx=4)

        # 3. Main Samples Treeview Table
        table_frame = ttk.Frame(self)
        table_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("id", "material", "date", "operator", "mass_tot", "water", "mass_act", "status", "files_cnt")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")

        self.tree.heading("id", text="Sample ID")
        self.tree.heading("material", text="Material / Formulation")
        self.tree.heading("date", text="Date")
        self.tree.heading("operator", text="Operator")
        self.tree.heading("mass_tot", text="Total Mass (g)")
        self.tree.heading("water", text="Loss %")
        self.tree.heading("mass_act", text="Active Mass (g)")
        self.tree.heading("status", text="Status")
        self.tree.heading("files_cnt", text="Files")

        self.tree.column("id", width=110, anchor="center")
        self.tree.column("material", width=220, anchor="w")
        self.tree.column("date", width=95, anchor="center")
        self.tree.column("operator", width=140, anchor="w")
        self.tree.column("mass_tot", width=95, anchor="e")
        self.tree.column("water", width=80, anchor="e")
        self.tree.column("mass_act", width=105, anchor="e")
        self.tree.column("status", width=95, anchor="center")
        self.tree.column("files_cnt", width=75, anchor="center")

        scroll_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        scroll_x = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        scroll_x.pack(side=tk.BOTTOM, fill=tk.X)

        self.tree.bind("<<TreeviewSelect>>", self.on_row_select)
        self.tree.bind("<Double-1>", lambda e: self.on_go_to_hub())

    def _create_kpi_card(self, parent, title, value, color):
        frame = tk.Frame(parent, bg="#ffffff", bd=1, relief="solid", padx=10, pady=8)
        lbl_title = tk.Label(frame, text=title, font=("Segoe UI", 9), bg="#ffffff", fg="#6c757d")
        lbl_title.pack(anchor="w")
        lbl_val = tk.Label(frame, text=value, font=("Segoe UI", 14, "bold"), bg="#ffffff", fg=color)
        lbl_val.pack(anchor="w")
        frame.val_label = lbl_val
        return frame

    def refresh_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        logbook = self.vault.logbook
        query = self.search_var.get().lower().strip()

        tot_samples = len(logbook)
        analyzed_count = 0
        masses = []

        for s_id, data in sorted(logbook.items()):
            mat = data.get("material_name", "")
            op = data.get("operator", "")
            
            # Filter check
            if query and (query not in s_id.lower() and query not in mat.lower() and query not in op.lower()):
                continue

            status = data.get("status", "Registered")
            if status in ["Analyzed", "Analizada"]:
                status = "Analyzed"
                analyzed_count += 1
            elif status == "Registrada":
                status = "Registered"

            mass_tot = float(data.get("mass_total_g", 0.0))
            water_pct = float(data.get("water_loss_pct", 0.0))
            mass_act = mass_tot * (1.0 - (water_pct / 100.0))
            if mass_tot > 0:
                masses.append(mass_tot)

            # Count total attached files across all characterizations
            total_files = 0
            chars = data.get("characterizations", {})
            for tech, tdata in chars.items():
                total_files += len(tdata.get("files", []))
            if total_files == 0 and "files" in data:
                total_files = len(data.get("files", []))

            item_id = self.tree.insert("", tk.END, values=(
                s_id,
                mat,
                data.get("date", "-"),
                op,
                f"{mass_tot:.4f}",
                f"{water_pct:.1f}%",
                f"{mass_act:.4f}",
                status,
                str(total_files)
            ))

            if self.active_sample_id == s_id:
                self.tree.selection_set(item_id)
                self.tree.see(item_id)

        # Update KPI Cards
        self.card_total.val_label.config(text=str(tot_samples))
        self.card_analyzed.val_label.config(text=str(analyzed_count))
        avg_mass = (sum(masses) / len(masses)) if masses else 0.0
        self.card_mass.val_label.config(text=f"{avg_mass:.3f} g")

    def filter_table(self):
        self.refresh_table()

    def get_selected_sample_id(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return self.tree.item(sel[0], "values")[0]

    def on_row_select(self, event=None):
        s_id = self.get_selected_sample_id()
        if s_id:
            self.active_sample_id = s_id
            if self.on_select_sample_callback:
                self.on_select_sample_callback(s_id)

    def on_new_sample(self):
        dialog = SampleDialog(self.winfo_toplevel(), title="Register New Sample")
        self.wait_window(dialog)
        if dialog.result:
            s_id = dialog.result["sample_id"]
            self.vault.create_or_update_sample(s_id, dialog.result)
            self.active_sample_id = s_id
            self.refresh_table()
            messagebox.showinfo("Sample Registered", f"Sample '{s_id}' registered successfully in logbook.")
            if self.on_select_sample_callback:
                self.on_select_sample_callback(s_id)

    def on_edit_sample(self):
        s_id = self.get_selected_sample_id()
        if not s_id:
            messagebox.showinfo("Select Sample", "Please select a sample from the table to edit.")
            return

        current_data = self.vault.logbook.get(s_id, {})
        dialog = SampleDialog(self.winfo_toplevel(), title=f"Edit Sample: {s_id}", sample_data=current_data)
        self.wait_window(dialog)
        if dialog.result:
            self.vault.create_or_update_sample(s_id, dialog.result)
            self.refresh_table()
            if self.on_select_sample_callback:
                self.on_select_sample_callback(s_id)

    def on_delete_sample(self):
        s_id = self.get_selected_sample_id()
        if not s_id:
            messagebox.showinfo("Select Sample", "Please select a sample to delete.")
            return

        confirm = messagebox.askyesno(
            "Confirm Deletion", 
            f"Are you sure you want to delete sample '{s_id}' and all associated files?\nThis action cannot be undone."
        )
        if confirm:
            self.vault.delete_sample(s_id)
            self.active_sample_id = None
            self.refresh_table()
            if self.on_select_sample_callback:
                self.on_select_sample_callback(None)

    def on_open_folder(self):
        s_id = self.get_selected_sample_id()
        if not s_id:
            messagebox.showinfo("Select Sample", "Please select a sample to open its directory.")
            return
        folder = self.vault.get_sample_dir(s_id)
        if os.path.exists(folder):
            os.startfile(folder)
        else:
            messagebox.showwarning("Folder Not Found", f"Directory not found:\n{folder}")

    def on_go_to_hub(self):
        s_id = self.get_selected_sample_id()
        if not s_id:
            messagebox.showinfo("Select Sample", "Please select a sample to inspect its characterizations.")
            return
        if self.on_select_sample_callback:
            self.on_select_sample_callback(s_id, switch_tab=True)

    def on_refresh(self):
        self.vault.reconcile_vault_filesystem()
        self.refresh_table()
