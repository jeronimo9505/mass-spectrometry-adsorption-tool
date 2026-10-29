"""
TGA Thermal Analysis panel (Publication Report Styles A & B) for the Characterization Hub.

Provides `TGAPanelMixin` – mixed into `CharacterizationHubView` – which builds the
"TGA Thermal Analysis" tab:

  left  : files, experimental conditions, paste composition (editable, with
          templates), key results
  right : live publication figure switcher:
            - Style B – Presentation (Landscape: curves + tables)
            - Style A – Journal (Vertical: DTG top + Mass bottom with callouts)
            - Both Styles (Side-by-Side preview)
          export at 150/300/600/1200 DPI (PNG / PDF / SVG / TIFF) and a
          one-click "Generate Full Report" that stores:
            - Complete Multi-Page PDF Report (registered in Official Documents)
            - Single Combined Master Excel Workbook (all 8 sheets in one file)
            - High-Res Style A & Style B graphs (600 / 1200 DPI + vector PDF)
            - Interactive HTML report
"""

import os
import io
import json
import copy
import tempfile
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

from PIL import Image, ImageTk

from core.tga_engine import load_tga_data
from core import tga_report as TR

BUILTIN_TEMPLATE = "Zeolite 13X paste – Batch 7 (default)"
SILICA_TEMPLATE = "Silica gel paste – Batch 1 (default)"
BUILTIN_TEMPLATES = (BUILTIN_TEMPLATE, SILICA_TEMPLATE)
TGA_EXTS = (".xlsx", ".xls", ".csv", ".txt", ".dat")
IMG_EXTS = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".gif")

STYLE_OPTIONS = [
    ("Style B – Presentation (Landscape)", TR.STYLE_B),
    ("Style A – Journal (Vertical)", TR.STYLE_A),
    ("Both Styles (Side-by-Side)", TR.STYLE_BOTH),
]
STYLE_LABEL_TO_KEY = dict(STYLE_OPTIONS)
STYLE_KEY_TO_LABEL = {v: k for k, v in STYLE_OPTIONS}


def _num(var, default=0.0):
    try:
        return float(var.get())
    except (tk.TclError, ValueError, TypeError):
        return default


class TGAPanelMixin:
    # ------------------------------------------------------------------ #
    # Template store (paste compositions are remembered for the next batch)
    # ------------------------------------------------------------------ #

    def _tga_templates_path(self):
        return os.path.join(self.vault.vault_path, "tga_paste_templates.json")

    def _tga_load_templates(self):
        data = {"templates": {}, "last": BUILTIN_TEMPLATE}
        try:
            with open(self._tga_templates_path(), "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                data["templates"].update(loaded.get("templates", {}))
                data["last"] = loaded.get("last", BUILTIN_TEMPLATE)
        except Exception:
            pass
        data["templates"][BUILTIN_TEMPLATE] = copy.deepcopy(TR.DEFAULT_COMPOSITION)
        data["templates"][SILICA_TEMPLATE] = copy.deepcopy(TR.DEFAULT_SILICA_COMPOSITION)
        return data

    def _tga_save_templates(self, data):
        try:
            to_save = {"templates": {k: v for k, v in data["templates"].items() if k not in BUILTIN_TEMPLATES},
                       "last": data.get("last", BUILTIN_TEMPLATE)}
            with open(self._tga_templates_path(), "w", encoding="utf-8") as f:
                json.dump(to_save, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # UI
    # ------------------------------------------------------------------ #

    def _build_tga_tab(self, parent):
        self.tga_analysis = None
        self.tga_raw_df = None
        self.current_tga_path = None
        self.tga_composition = copy.deepcopy(TR.DEFAULT_COMPOSITION)
        self._tga_preview_img = None
        self._tga_photo = None
        self._tga_fit_job = None
        self._tga_bg = None
        self._tga_progress_msg = ""
        self.current_tga_df = None
        self.current_tga_meta = {}

        paned = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)
        left = ttk.Frame(paned, width=410)
        right = ttk.Frame(paned)
        paned.add(left, weight=0)
        paned.add(right, weight=1)

        # ---- files ----
        tb = ttk.Frame(left)
        tb.pack(fill=tk.X, pady=(0, 4))
        ft = [("TGA Files", "*.xlsx;*.xls;*.csv;*.txt"), ("All Files", "*.*")]
        ttk.Button(tb, text="➕ Attach TGA File", command=lambda: self.on_attach_tga_file(ft)).pack(side=tk.LEFT, padx=2)
        ttk.Button(tb, text="🗑️ Delete", command=lambda: self.on_delete_file("tga")).pack(side=tk.LEFT, padx=2)
        ttk.Button(tb, text="📂 Open", command=lambda: self.on_open_selected_file("tga")).pack(side=tk.LEFT, padx=2)
        ttk.Button(tb, text="📁 Folder", command=lambda: self.on_open_tech_folder("tga")).pack(side=tk.LEFT, padx=2)

        self.tree_tga = ttk.Treeview(left, columns=("fn", "size"), show="headings", selectmode="browse", height=3)
        self.tree_tga.heading("fn", text="TGA Data File (.xlsx / .csv)")
        self.tree_tga.heading("size", text="Size")
        self.tree_tga.column("fn", width=260, anchor="w")
        self.tree_tga.column("size", width=70, anchor="e")
        self.tree_tga.pack(fill=tk.X, pady=(0, 4))
        self.tree_tga.bind("<<TreeviewSelect>>", self.on_tga_file_selected)
        self.tree_tga.bind("<Double-1>", lambda e: self.on_open_selected_file("tga"))

        ttk.Button(left, text="📊 Plot / Analyze Selected File", command=self.on_plot_current_tga).pack(fill=tk.X, pady=(0, 4))

        nb = ttk.Notebook(left)
        nb.pack(fill=tk.BOTH, expand=True)
        t_cond = ttk.Frame(nb, padding=8)
        t_comp = ttk.Frame(nb, padding=8)
        t_res = ttk.Frame(nb, padding=8)
        nb.add(t_cond, text=" ⚙ Conditions ")
        nb.add(t_comp, text=" 🧪 Paste Composition ")
        nb.add(t_res, text=" 📋 Results ")

        self._build_tga_conditions(t_cond)
        self._build_tga_composition(t_comp)
        self._build_tga_results(t_res)

        # ---- right: preview ----
        head = ttk.Frame(right)
        head.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(head, text="📈 TGA / DTG Publication Graphs (Style A Journal & Style B Presentation)",
                  font=("Segoe UI", 10, "bold"), foreground="#1d3557").pack(side=tk.LEFT)

        bar = ttk.Frame(right)
        bar.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(bar, text="Graph Style:").pack(side=tk.LEFT, padx=(2, 2))
        self.tga_style_var = tk.StringVar(value=STYLE_OPTIONS[2][0])  # default: Both Styles (Side-by-Side)
        style_cb = ttk.Combobox(bar, values=[lbl for lbl, _ in STYLE_OPTIONS], textvariable=self.tga_style_var,
                                width=27, state="readonly")
        style_cb.pack(side=tk.LEFT, padx=(0, 6))
        style_cb.bind("<<ComboboxSelected>>", lambda e: self._tga_render_preview())

        ttk.Label(bar, text="DPI:").pack(side=tk.LEFT, padx=(2, 2))
        self.tga_dpi_var = tk.StringVar(value="1200")
        ttk.Combobox(bar, values=["150", "300", "600", "1200"], textvariable=self.tga_dpi_var, width=5,
                     state="readonly").pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(bar, text="💾 Export Graph…", command=self.on_export_tga_plot).pack(side=tk.LEFT, padx=2)
        ttk.Button(bar, text="🔍 Full Size", command=self.on_tga_open_fullsize).pack(side=tk.LEFT, padx=2)
        self.tga_report_btn = ttk.Button(bar, text="📄 Generate Complete Report (PDF + Excel + 1200 DPI)",
                                         command=self.on_generate_tga_report)
        self.tga_report_btn.pack(side=tk.LEFT, padx=(8, 2))
        ttk.Button(bar, text="📁 Report Folder", command=self.on_open_tga_report_folder).pack(side=tk.LEFT, padx=2)
        ttk.Button(bar, text="📊 Compare TGA Runs…", command=self.on_compare_tga_runs).pack(side=tk.LEFT, padx=(6, 2))
        ttk.Button(bar, text="📁 Comparative Folder", command=self.on_open_tga_comparative_folder).pack(side=tk.LEFT, padx=2)

        self.tga_status_var = tk.StringVar(value="")
        ttk.Label(right, textvariable=self.tga_status_var, foreground="#1d6f42").pack(fill=tk.X, pady=(0, 2))

        self.tga_canvas_w = tk.Canvas(right, bg="white", highlightthickness=1, highlightbackground="#cfd8e3")
        self.tga_canvas_w.pack(fill=tk.BOTH, expand=True)
        self.tga_canvas_w.bind("<Configure>", self._tga_on_resize)
        self.tga_canvas_w.bind("<Double-1>", lambda e: self.on_tga_open_fullsize())
        self._tga_show_message("Select a TGA data file (.xlsx / .csv) and click “Plot / Analyze”.")

    def _build_tga_conditions(self, p):
        g = ttk.Frame(p)
        g.pack(fill=tk.X)
        self.tga_plot_title_var = tk.StringVar(value="")
        self.tga_atmosphere_var = tk.StringVar(value="Air")
        self.tga_flow_var = tk.DoubleVar(value=50.0)
        self.tga_rate_var = tk.DoubleVar(value=10.0)
        self.tga_mass_mg_var = tk.DoubleVar(value=0.0)
        self.tga_limits_var = tk.StringVar(value="")
        self.tga_tail_var = tk.DoubleVar(value=0.005)

        r = 0
        ttk.Label(g, text="Graph title:").grid(row=r, column=0, sticky="w", pady=3)
        ttk.Entry(g, textvariable=self.tga_plot_title_var, width=30).grid(row=r, column=1, sticky="we", padx=4)
        r += 1
        ttk.Label(g, text="Purge atmosphere:").grid(row=r, column=0, sticky="w", pady=3)
        ttk.Combobox(g, values=["Air", "N2", "O2", "Ar", "CO2"], textvariable=self.tga_atmosphere_var, width=10,
                     state="readonly").grid(row=r, column=1, sticky="w", padx=4)
        r += 1
        ttk.Label(g, text="Gas flow (mL/min):").grid(row=r, column=0, sticky="w", pady=3)
        ttk.Spinbox(g, from_=0, to=500, increment=5, textvariable=self.tga_flow_var, width=10).grid(row=r, column=1, sticky="w", padx=4)
        r += 1
        ttk.Label(g, text="Heating rate (°C/min):").grid(row=r, column=0, sticky="w", pady=3)
        ttk.Spinbox(g, from_=0, to=100, increment=1, textvariable=self.tga_rate_var, width=10).grid(row=r, column=1, sticky="w", padx=4)
        r += 1
        ttk.Label(g, text="Sample mass (mg):").grid(row=r, column=0, sticky="w", pady=3)
        ttk.Spinbox(g, from_=0, to=500, increment=0.5, textvariable=self.tga_mass_mg_var, width=10).grid(row=r, column=1, sticky="w", padx=4)
        r += 1
        ttk.Label(g, text="Manual step limits (°C):").grid(row=r, column=0, sticky="w", pady=3)
        ttk.Entry(g, textvariable=self.tga_limits_var, width=30).grid(row=r, column=1, sticky="we", padx=4)
        r += 1
        ttk.Label(g, text="", foreground="#6c757d").grid(row=r, column=0)
        ttk.Label(g, text="e.g. 190, 224, 450  (blank = automatic from DTG minima)",
                  foreground="#6c757d", font=("Segoe UI", 8)).grid(row=r, column=1, sticky="w", padx=4)
        r += 1
        ttk.Label(g, text="Tail DTG threshold:").grid(row=r, column=0, sticky="w", pady=3)
        ttk.Spinbox(g, from_=0.0005, to=0.1, increment=0.0005, format="%.4f", textvariable=self.tga_tail_var,
                    width=10).grid(row=r, column=1, sticky="w", padx=4)
        g.columnconfigure(1, weight=1)

        ttk.Button(p, text="📊 Apply & Re-plot", command=self.on_plot_current_tga).pack(fill=tk.X, pady=(10, 2))
        ttk.Button(p, text="💾 Save TGA Settings to Sample", command=self.on_save_tga_params).pack(fill=tk.X, pady=2)

    def _build_tga_composition(self, p):
        top = ttk.Frame(p)
        top.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(top, text="Template:").pack(side=tk.LEFT)
        self.tga_template_var = tk.StringVar(value=BUILTIN_TEMPLATE)
        self.tga_template_cb = ttk.Combobox(top, textvariable=self.tga_template_var, state="readonly", width=30)
        self.tga_template_cb.pack(side=tk.LEFT, padx=4, fill=tk.X, expand=True)
        self.tga_template_cb.bind("<<ComboboxSelected>>", self._tga_on_template_selected)
        ttk.Button(top, text="Save as…", width=9, command=self._tga_save_template_as).pack(side=tk.LEFT)

        cols = ("component", "mass", "pct", "role", "note")
        self.tree_tga_comp = ttk.Treeview(p, columns=cols, show="headings", selectmode="browse", height=6)
        for c, t, w, a in (("component", "Component", 110, "w"), ("mass", "Mass (g)", 62, "e"),
                           ("pct", "wt %", 52, "e"), ("role", "Role", 62, "w"), ("note", "Note", 90, "w")):
            self.tree_tga_comp.heading(c, text=t)
            self.tree_tga_comp.column(c, width=w, anchor=a)
        self.tree_tga_comp.pack(fill=tk.X)
        self.tree_tga_comp.bind("<<TreeviewSelect>>", self._tga_on_comp_selected)

        self.tga_comp_total_var = tk.StringVar(value="")
        ttk.Label(p, textvariable=self.tga_comp_total_var, font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(3, 4))

        ed = ttk.Frame(p)
        ed.pack(fill=tk.X)
        self.tga_c_name = tk.StringVar()
        self.tga_c_mass = tk.StringVar()
        self.tga_c_role = tk.StringVar(value="other")
        self.tga_c_note = tk.StringVar()
        ttk.Label(ed, text="Component:").grid(row=0, column=0, sticky="w")
        ttk.Entry(ed, textvariable=self.tga_c_name, width=18).grid(row=0, column=1, sticky="we", padx=3, pady=2)
        ttk.Label(ed, text="Mass (g):").grid(row=0, column=2, sticky="w")
        ttk.Entry(ed, textvariable=self.tga_c_mass, width=8).grid(row=0, column=3, padx=3)
        ttk.Label(ed, text="Role:").grid(row=1, column=0, sticky="w")
        ttk.Combobox(ed, values=TR.ROLES, textvariable=self.tga_c_role, width=10, state="readonly").grid(row=1, column=1, sticky="w", padx=3, pady=2)
        ttk.Label(ed, text="Note:").grid(row=1, column=2, sticky="w")
        ttk.Entry(ed, textvariable=self.tga_c_note, width=14).grid(row=1, column=3, sticky="we", padx=3)
        ed.columnconfigure(1, weight=1)

        br = ttk.Frame(p)
        br.pack(fill=tk.X, pady=(4, 2))
        ttk.Button(br, text="➕ Add", command=self._tga_comp_add).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=1)
        ttk.Button(br, text="✏ Update", command=self._tga_comp_update).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=1)
        ttk.Button(br, text="🗑 Remove", command=self._tga_comp_remove).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=1)
        ttk.Label(p, text="Roles: zeolite · silica · clay (binder) · organic (burns off) · water · other",
                  foreground="#6c757d", font=("Segoe UI", 8)).pack(anchor="w")
        ttk.Button(p, text="📊 Apply Composition & Re-plot", command=self.on_plot_current_tga).pack(fill=tk.X, pady=(6, 0))
        self._tga_refresh_comp_tree()

    def _build_tga_results(self, p):
        g = ttk.Frame(p)
        g.pack(fill=tk.X)
        self.tga_init_weight_var = tk.DoubleVar(value=100.0)
        self.tga_residual_var = tk.DoubleVar(value=0.0)
        self.tga_delta_w_var = tk.DoubleVar(value=0.0)
        self.tga_peak_var = tk.DoubleVar(value=0.0)
        self.tga_onset_var = tk.DoubleVar(value=0.0)
        rows = [("Loaded mass (%):", self.tga_init_weight_var, 200, 0.1),
                ("Residual mass (%):", self.tga_residual_var, 100, 0.1),
                ("Net weight loss ΔW (%):", self.tga_delta_w_var, 100, 0.1),
                ("Main DTG peak (°C):", self.tga_peak_var, 1200, 1.0),
                ("Onset temp (°C):", self.tga_onset_var, 1200, 5.0)]
        for i, (lab, var, mx, inc) in enumerate(rows):
            ttk.Label(g, text=lab).grid(row=i, column=0, sticky="w", pady=2)
            ttk.Spinbox(g, from_=0.0, to=mx, increment=inc, textvariable=var, width=10).grid(row=i, column=1, sticky="w", padx=4)
        self.tga_summary_txt = tk.Text(p, height=9, wrap="word", font=("Consolas", 8), bg="#f8f9fa", relief="flat")
        self.tga_summary_txt.pack(fill=tk.BOTH, expand=True, pady=(6, 4))
        self.tga_summary_txt.configure(state="disabled")
        ttk.Button(p, text="💾 Save TGA Parameters to Sample", command=self.on_save_tga_params).pack(fill=tk.X)

    # ------------------------------------------------------------------ #
    # Composition editing
    # ------------------------------------------------------------------ #

    def _tga_refresh_comp_tree(self):
        for i in self.tree_tga_comp.get_children():
            self.tree_tga_comp.delete(i)
        norm = TR.normalise_composition(self.tga_composition)
        for r in norm:
            self.tree_tga_comp.insert("", tk.END, values=(r["component"], f"{r['mass_g']:.2f}", f"{r['pct']:.2f}", r["role"], r["note"]))
        self.tga_comp_total_var.set(f"Total: {TR.composition_total(norm):.2f} g  (100 %)   —  {len(norm)} components")

    def _tga_on_comp_selected(self, event=None):
        sel = self.tree_tga_comp.selection()
        if not sel:
            return
        v = self.tree_tga_comp.item(sel[0], "values")
        self.tga_c_name.set(v[0])
        self.tga_c_mass.set(v[1])
        self.tga_c_role.set(v[3])
        self.tga_c_note.set(v[4])

    def _tga_read_comp_entry(self):
        name = self.tga_c_name.get().strip()
        try:
            mass = float(self.tga_c_mass.get().replace(",", "."))
        except ValueError:
            messagebox.showwarning("Composition", "Enter a numeric mass in grams.")
            return None
        if not name or mass <= 0:
            messagebox.showwarning("Composition", "Component name and a mass > 0 are required.")
            return None
        return {"component": name, "mass_g": mass, "role": self.tga_c_role.get() or "other", "note": self.tga_c_note.get().strip()}

    def _tga_comp_add(self):
        row = self._tga_read_comp_entry()
        if row:
            self.tga_composition.append(row)
            self._tga_refresh_comp_tree()

    def _tga_comp_update(self):
        sel = self.tree_tga_comp.selection()
        if not sel:
            messagebox.showinfo("Composition", "Select a row to update.")
            return
        idx = self.tree_tga_comp.index(sel[0])
        row = self._tga_read_comp_entry()
        if row:
            norm = TR.normalise_composition(self.tga_composition)
            self.tga_composition = [{k: r[k] for k in ("component", "mass_g", "role", "note")} for r in norm]
            if idx < len(self.tga_composition):
                self.tga_composition[idx] = row
            self._tga_refresh_comp_tree()

    def _tga_comp_remove(self):
        sel = self.tree_tga_comp.selection()
        if not sel:
            return
        idx = self.tree_tga_comp.index(sel[0])
        norm = TR.normalise_composition(self.tga_composition)
        self.tga_composition = [{k: r[k] for k in ("component", "mass_g", "role", "note")} for r in norm]
        if idx < len(self.tga_composition):
            del self.tga_composition[idx]
        self._tga_refresh_comp_tree()

    def _tga_refresh_template_list(self, select=None):
        data = self._tga_load_templates()
        names = sorted((k for k in data["templates"] if not k.startswith("__")),
                       key=lambda n: (0 if n == BUILTIN_TEMPLATE else (1 if n == SILICA_TEMPLATE else 2), n))
        self.tga_template_cb["values"] = names
        if select:
            self.tga_template_var.set(select)

    def _tga_on_template_selected(self, event=None):
        data = self._tga_load_templates()
        comp = data["templates"].get(self.tga_template_var.get())
        if comp:
            self.tga_composition = copy.deepcopy(comp)
            self._tga_refresh_comp_tree()

    def _tga_save_template_as(self):
        name = simpledialog.askstring("Save paste template", "Template name (e.g. Zeolite 13X paste – Batch 8):",
                                      initialvalue=self.tga_template_var.get(), parent=self)
        if not name or not name.strip():
            return
        name = name.strip()
        if name == BUILTIN_TEMPLATE:
            messagebox.showinfo("Template", "The built-in default template cannot be overwritten. Use another name.")
            return
        data = self._tga_load_templates()
        norm = TR.normalise_composition(self.tga_composition)
        data["templates"][name] = [{k: r[k] for k in ("component", "mass_g", "role", "note")} for r in norm]
        data["last"] = name
        self._tga_save_templates(data)
        self._tga_refresh_template_list(select=name)
        self.tga_status_var.set(f"Template '{name}' saved in the vault.")

    # ------------------------------------------------------------------ #
    # File handling
    # ------------------------------------------------------------------ #

    def on_attach_tga_file(self, filetypes):
        if not self.current_sample_id:
            messagebox.showinfo("Select Sample", "Please select a sample in the logbook first.")
            return
        fpath = filedialog.askopenfilename(title="Select TGA Raw Data File (Excel / CSV)", filetypes=filetypes)
        if fpath:
            try:
                cloned = self.vault.add_characterization_file(self.current_sample_id, "tga", fpath)
                self._refresh_tga_tab(auto_plot=False)
                self.load_and_display_tga(cloned if cloned and os.path.exists(cloned) else fpath)
            except Exception as e:
                messagebox.showerror("Error Attaching File", f"Could not attach TGA file:\n{e}")

    def on_tga_file_selected(self, event=None):
        sel = self.tree_tga.selection()
        if not sel or not self.current_sample_id:
            return
        fn = self.tree_tga.item(sel[0], "values")[0]
        fpath = self.vault.get_characterization_file_path(self.current_sample_id, "tga", fn)
        if not fpath or not os.path.exists(fpath):
            return
        ext = os.path.splitext(fn)[1].lower()
        if ext in TGA_EXTS:
            self.load_and_display_tga(fpath)
        elif ext in IMG_EXTS:
            self._tga_clear_analysis()
            self._tga_show_message(f"🖼️ Attached image\n\n{fn}\n\nDouble-click the row or press “Open” to view it.\n"
                                   "Select a spreadsheet (.xlsx/.csv) to build the report graph.")
        else:
            self._tga_clear_analysis()
            self._tga_show_message(f"📄 Attached document\n\n{fn}\n\nPress “Open” to view it.")

    def on_plot_current_tga(self):
        sel = self.tree_tga.selection()
        if not sel:
            for c in self.tree_tga.get_children():
                if os.path.splitext(self.tree_tga.item(c, "values")[0])[1].lower() in TGA_EXTS:
                    self.tree_tga.selection_set(c)
                    return  # selection event triggers the load
        if self.tga_raw_df is not None:
            self._tga_run_analysis()
        elif sel:
            self.on_tga_file_selected()
        else:
            messagebox.showinfo("TGA", "Attach or select a TGA data file first.")

    def load_and_display_tga(self, fpath):
        try:
            df, meta = load_tga_data(fpath)
        except Exception as e:
            messagebox.showerror("TGA Load Error", f"Could not process TGA file:\n{e}")
            return
        self.tga_raw_df = df
        self.current_tga_df = df
        self.current_tga_meta = meta
        self.current_tga_path = fpath
        if not self.tga_plot_title_var.get().strip():
            mat = ""
            if self.current_sample_id in self.vault.logbook:
                mat = self.vault.logbook[self.current_sample_id].get("material_name", "")
            self.tga_plot_title_var.set(mat if mat and mat != "-" else os.path.splitext(os.path.basename(fpath))[0])
        self._tga_run_analysis()

    # ------------------------------------------------------------------ #
    # Analysis + preview
    # ------------------------------------------------------------------ #

    def _tga_collect_conditions(self):
        return {
            "atmosphere": self.tga_atmosphere_var.get() or "Air",
            "flow_ml_min": _num(self.tga_flow_var, 0.0),
            "heating_rate": _num(self.tga_rate_var, 0.0),
            "sample_mass_mg": _num(self.tga_mass_mg_var, 0.0),
            "tail_threshold": _num(self.tga_tail_var, 0.005) or 0.005,
            "manual_limits": self.tga_limits_var.get().strip(),
            "loaded_pct": 100.0,
        }

    def _tga_clear_analysis(self):
        self.tga_analysis = None
        self.tga_raw_df = None
        self.current_tga_df = None
        self.current_tga_meta = {}
        self.current_tga_path = None

    def _tga_run_analysis(self):
        if self.tga_raw_df is None:
            return
        try:
            self.tga_analysis = TR.analyze_tga(self.tga_raw_df, self.tga_composition, self._tga_collect_conditions())
        except Exception as e:
            messagebox.showerror("TGA Analysis Error", f"Could not analyse the TGA data:\n{e}")
            return
        A = self.tga_analysis
        tot = A["totals"]
        self.tga_init_weight_var.set(tot["loaded_pct"])
        self.tga_residual_var.set(round(tot["residue"], 2))
        self.tga_delta_w_var.set(round(tot["total_loss"], 2))
        self.tga_peak_var.set(round(tot["peak_t_main"], 1))
        self.tga_onset_var.set(round(A["onset"], 1))
        self._tga_update_summary()
        self._tga_render_preview()

    def _tga_update_summary(self):
        A = self.tga_analysis
        lines = []
        for r in A["interpretation"]:
            lines.append(f"{r['step']:>3}  {r['t_range']:<13} peak {r['peak_t']:.0f} °C   {r['loss']:.2f} wt%")
        tot = A["totals"]
        lines.append("-" * 44)
        lines.append(f"Total loss {tot['total_loss']:.2f} wt%   residue {tot['residue']:.2f} wt%")
        th = A["theory"]
        lines.append(f"Moisture in solids (est.): {th['moisture_pct_of_solids']:.1f} %")
        self.tga_summary_txt.configure(state="normal")
        self.tga_summary_txt.delete("1.0", tk.END)
        self.tga_summary_txt.insert("1.0", "\n".join(lines))
        self.tga_summary_txt.configure(state="disabled")

    def _tga_fig_title(self):
        return self.tga_plot_title_var.get().strip()

    def _tga_selected_style(self):
        return STYLE_LABEL_TO_KEY.get(self.tga_style_var.get(), TR.STYLE_BOTH)

    def _tga_render_preview(self):
        if not self.tga_analysis:
            return
        try:
            title = self._tga_fig_title() or "TGA sample"
            style = self._tga_selected_style()
            dpi = 140 if style == TR.STYLE_BOTH else 170
            png = TR.figure_to_png_bytes(self.tga_analysis, title, dpi=dpi, fig_title=f"TGA / DTG of {title}", style=style)
            self._tga_preview_img = Image.open(io.BytesIO(png)).convert("RGB")
            self._tga_fit_preview()
            self.tga_status_var.set("")
        except Exception as e:
            messagebox.showerror("TGA Plot Error", f"Could not draw the TGA report graph:\n{e}")

    def _tga_show_message(self, text):
        self._tga_last_msg = text
        self._tga_preview_img = None
        c = self.tga_canvas_w
        c.delete("all")
        c.create_text(max(c.winfo_width(), 300) // 2, max(c.winfo_height(), 200) // 2, text=text,
                      font=("Segoe UI", 11), fill="#495057", justify="center", tags="msg")

    def _tga_on_resize(self, event=None):
        if self._tga_fit_job:
            try:
                self.after_cancel(self._tga_fit_job)
            except Exception:
                pass
        self._tga_fit_job = self.after(80, self._tga_fit_preview)

    def _tga_fit_preview(self):
        self._tga_fit_job = None
        c = self.tga_canvas_w
        w, h = max(c.winfo_width(), 50), max(c.winfo_height(), 50)
        if self._tga_preview_img is None:
            c.delete("all")
            c.create_text(w // 2, h // 2, text=getattr(self, "_tga_last_msg", "") or "",
                          font=("Segoe UI", 11), fill="#495057", justify="center", tags="msg")
            return
        img = self._tga_preview_img
        scale = min(w / img.width, h / img.height)
        nw, nh = max(1, int(img.width * scale)), max(1, int(img.height * scale))
        photo = ImageTk.PhotoImage(img.resize((nw, nh), Image.LANCZOS))
        c.delete("all")
        c.create_image(w // 2, h // 2, image=photo, anchor="center")
        self._tga_photo = photo

    # ------------------------------------------------------------------ #
    # Background worker helper
    # ------------------------------------------------------------------ #

    def _tga_run_bg(self, func, on_done):
        if self._tga_bg is not None:
            messagebox.showinfo("TGA", "Another export is still running – please wait.")
            return
        state = {"done": False, "result": None, "error": None}

        def work():
            try:
                state["result"] = func()
            except Exception as e:  # noqa
                state["error"] = e
            state["done"] = True

        self._tga_bg = state
        self.configure(cursor="watch")
        threading.Thread(target=work, daemon=True).start()

        def poll():
            if self._tga_progress_msg:
                self.tga_status_var.set(self._tga_progress_msg)
            if state["done"]:
                self._tga_bg = None
                self.configure(cursor="")
                on_done(state["result"], state["error"])
            else:
                self.after(150, poll)

        self.after(150, poll)

    # ------------------------------------------------------------------ #
    # Export image
    # ------------------------------------------------------------------ #

    def _tga_require_analysis(self):
        if not self.tga_analysis:
            messagebox.showinfo("No Plot", "Load and plot a TGA data file first.")
            return False
        return True

    def on_export_tga_plot(self):
        if not self._tga_require_analysis():
            return
        dpi = int(self.tga_dpi_var.get() or 600)
        style = self._tga_selected_style()
        stem = os.path.splitext(os.path.basename(self.current_tga_path or "TGA"))[0]
        suffix = "styleA_journal" if style == TR.STYLE_A else ("styleB_presentation" if style == TR.STYLE_B else "styleB_and_styleA")
        out_path = filedialog.asksaveasfilename(
            title=f"Export TGA report graph ({dpi} DPI)",
            initialfile=f"{stem}_{suffix}_{dpi}dpi.png", defaultextension=".png",
            filetypes=[("PNG Image (high-res)", "*.png"), ("PDF (vector)", "*.pdf"), ("SVG (vector)", "*.svg"),
                       ("TIFF Image", "*.tif"), ("All Files", "*.*")])
        if not out_path:
            return
        title = self._tga_fig_title() or "TGA sample"
        fig_title = f"TGA / DTG of {title}"
        A = self.tga_analysis
        self._tga_progress_msg = f"Exporting {dpi} DPI image(s)…"
        self.tga_status_var.set(self._tga_progress_msg)

        def export_job():
            if style == TR.STYLE_BOTH:
                base_p, ext = os.path.splitext(out_path)
                p_a = f"{base_p}_styleA_journal{ext}"
                p_b = f"{base_p}_styleB_presentation{ext}"
                TR.export_figure(A, title, p_a, dpi=dpi, fig_title=fig_title, style=TR.STYLE_A)
                TR.export_figure(A, title, p_b, dpi=dpi, fig_title=fig_title, style=TR.STYLE_B)
                return f"{p_a}\n{p_b}"
            return TR.export_figure(A, title, out_path, dpi=dpi, fig_title=fig_title, style=style)

        def done(res, err):
            self._tga_progress_msg = ""
            if err:
                self.tga_status_var.set("")
                messagebox.showerror("Export Error", f"Could not export plot:\n{err}")
            else:
                self.tga_status_var.set(f"Saved: {out_path}")
                messagebox.showinfo("Export Successful", f"TGA publication graph(s) saved ({dpi} DPI):\n{res}")

        self._tga_run_bg(export_job, done)

    def on_tga_open_fullsize(self):
        if not self._tga_require_analysis():
            return
        title = self._tga_fig_title() or "TGA sample"
        style = self._tga_selected_style()
        try:
            png = TR.figure_to_png_bytes(self.tga_analysis, title, dpi=220, fig_title=f"TGA / DTG of {title}", style=style)
            p = os.path.join(tempfile.gettempdir(), f"tga_report_preview_{style}.png")
            with open(p, "wb") as f:
                f.write(png)
            os.startfile(p)
        except Exception as e:
            messagebox.showerror("Open Error", str(e))

    # ------------------------------------------------------------------ #
    # Full report
    # ------------------------------------------------------------------ #

    def _tga_report_dir(self, sample_id=None, stem=None):
        sample_id = sample_id or self.current_sample_id
        base = self.vault.get_technique_dir(sample_id, "tga", create=True)
        return os.path.join(base, "reports", TR._safe(stem) if stem else "")

    def on_open_tga_report_folder(self):
        if not self.current_sample_id:
            return
        stem = os.path.splitext(os.path.basename(self.current_tga_path or ""))[0] or None
        d = self._tga_report_dir(stem=stem)
        if not os.path.isdir(d):
            d = os.path.join(self.vault.get_technique_dir(self.current_sample_id, "tga", create=True), "reports")
            os.makedirs(d, exist_ok=True)
        try:
            os.startfile(d)
        except Exception as e:
            messagebox.showerror("Folder", str(e))

    def on_compare_tga_runs(self):
        from gui.logbook_view import ComparativeReportDialog
        pre = [self.current_sample_id] if self.current_sample_id else []
        dlg = ComparativeReportDialog(
            self.winfo_toplevel(),
            self.vault,
            preselected_sample_ids=pre,
            initial_tab=1
        )
        self.wait_window(dlg)

    def on_open_tga_comparative_folder(self):
        from core import comparative_report as CR
        d = os.path.join(CR.get_comparative_root_dir(self.vault.vault_path), "TGA_Comparisons")
        os.makedirs(d, exist_ok=True)
        try:
            os.startfile(d)
        except Exception as e:
            messagebox.showerror("Folder", str(e))

    def on_generate_tga_report(self):
        if not self.current_sample_id:
            messagebox.showinfo("Select Sample", "Please select a sample in the logbook first.")
            return
        if not self._tga_require_analysis():
            return
        self._tga_run_analysis()  # make sure latest composition / conditions are applied
        A = self.tga_analysis
        sid = self.current_sample_id
        sample = self.vault.logbook.get(sid, {})
        title = self._tga_fig_title() or sample.get("material_name", sid)
        stem = os.path.splitext(os.path.basename(self.current_tga_path or "TGA"))[0]
        out_dir = self._tga_report_dir(sid, stem)
        meta = {
            "sample_id": sid, "sample_title": title, "operator": sample.get("operator", ""),
            "date": sample.get("date", ""), "raw_file": os.path.basename(self.current_tga_path or ""),
            "base_name": f"TGA_{TR._safe(sid)}_{TR._safe(stem)}",
        }
        dpis = (1200,)
        fig_title = f"TGA / DTG of {title}"
        self.tga_report_btn.state(["disabled"])
        self._tga_progress_msg = "Generating Complete PDF, Combined Excel & 1200 DPI Figures…"

        def progress(msg):
            self._tga_progress_msg = msg

        def done(paths, err):
            self.tga_report_btn.state(["!disabled"])
            self._tga_progress_msg = ""
            if err:
                self.tga_status_var.set("")
                messagebox.showerror("Report Error", f"Could not generate the report:\n{err}")
                return
            doc_note = ""
            try:
                dm = self.vault.doc_manager
                doc_title = f"TGA Report – {title} ({stem})"
                for d in dm.list_documents(search_query=doc_title):
                    if d.get("title") == doc_title and d.get("related_sample_id") == sid:
                        dm.delete_document(d["id"], delete_file_on_disk=True)
                notes = (f"Complete TGA PDF Report (Style A Journal + Style B Presentation + Conditions, "
                         f"Composition, Interpretation & References). Total loss {A['totals']['total_loss']:.1f} wt%, "
                         f"residue {A['totals']['residue']:.1f} wt%. Source: {meta['raw_file']}. "
                         f"Combined Excel & 1200 DPI Figures: {out_dir}")
                dm.add_document(paths["pdf_report"], doc_title, category="Official Report", related_sample=sid,
                                prepared_by=sample.get("operator", ""), notes=notes)
                doc_note = "\n• Complete PDF Report added to 📋 Official Documents → Official Laboratory Test Report"
            except Exception as e:
                doc_note = f"\n• (Could not add to Official Documents: {e})"
            self._tga_save_settings(extra={"last_report_dir": out_dir, "last_report_file": meta["raw_file"]})
            self.tga_status_var.set(f"Complete report package saved: {out_dir}")
            msg = ("Complete TGA Report Package saved in the vault:\n\n"
                   f"📂 {out_dir}\n"
                   f"  1. Complete Multi-Page PDF Report:\n     {os.path.basename(paths['pdf_report'])}\n"
                   f"  2. Single Combined Master Excel (all 8 sheets in 1 file):\n     {os.path.basename(paths['xlsx_combined'])}\n"
                   f"  3. Both Style A (Journal) & Style B (Presentation) 1200 DPI PNGs\n"
                   f"  4. Interactive HTML Report:\n     {os.path.basename(paths['html'])}\n"
                   f"{doc_note}\n\nOpen the Complete PDF Report and Combined Excel now?")
            if messagebox.askyesno("Complete TGA Report Ready", msg):
                try:
                    os.startfile(paths["pdf_report"])
                except Exception:
                    pass
                try:
                    os.startfile(paths["xlsx_combined"])
                except Exception:
                    pass

        self._tga_run_bg(lambda: TR.save_report_package(out_dir, A, meta, title, dpis=dpis, progress=progress,
                                                        fig_title=fig_title), done)

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def _tga_save_settings(self, extra=None):
        if not self.current_sample_id:
            return False
        sid = self.current_sample_id
        old = {}
        try:
            old = dict(self.vault.db.get_properties(sid, "tga"))
        except Exception:
            pass
        old.pop("notes", None)
        norm = TR.normalise_composition(self.tga_composition)
        props = dict(old)
        props.update({
            "onset_temp_c": _num(self.tga_onset_var),
            "peak_temp_c": _num(self.tga_peak_var),
            "initial_weight_pct": _num(self.tga_init_weight_var, 100.0),
            "residual_mass_pct": _num(self.tga_residual_var),
            "delta_weight_pct": _num(self.tga_delta_w_var),
            "atmosphere": self.tga_atmosphere_var.get(),
            "plot_title": self.tga_plot_title_var.get().strip(),
            "conditions": self._tga_collect_conditions(),
            "composition": [{k: r[k] for k in ("component", "mass_g", "role", "note")} for r in norm],
        })
        if self.tga_analysis:
            props["steps"] = [{"label": s["label"], "t_start": s["t_start"], "t_end": s["t_end"],
                               "peak_t": s["peak_t"], "loss": round(s["loss"], 3)} for s in self.tga_analysis["steps"]]
        if extra:
            props.update(extra)
        self.vault.save_technique_properties(sid, "tga", props)
        data = self._tga_load_templates()
        data["last"] = self.tga_template_var.get()
        data["templates"]["__last_used__"] = props["composition"]
        self._tga_save_templates(data)
        return True

    def on_save_tga_params(self):
        if not self.current_sample_id:
            return
        if self._tga_save_settings():
            messagebox.showinfo("Saved", f"TGA settings, paste composition and results saved for {self.current_sample_id}.")

    def _refresh_tga_tab(self, auto_plot=True):
        for item in self.tree_tga.get_children():
            self.tree_tga.delete(item)
        self._tga_clear_analysis()
        self._tga_refresh_template_list()

        if not self.current_sample_id or self.current_sample_id not in self.vault.logbook:
            self.tga_onset_var.set(0.0)
            self.tga_peak_var.set(0.0)
            self.tga_init_weight_var.set(100.0)
            self.tga_residual_var.set(0.0)
            self.tga_delta_w_var.set(0.0)
            self._tga_show_message("Select a sample in the logbook, then attach a TGA data file.")
            return

        data = self.vault.logbook[self.current_sample_id]
        tech = data.get("characterizations", {}).get("tga", {})
        for f in tech.get("files", []):
            self.tree_tga.insert("", tk.END, values=(f.get("filename", "-"), f"{f.get('size_bytes', 0) / 1024.0:.1f} KB"))

        self.tga_onset_var.set(float(tech.get("onset_temp_c", 0.0) or 0.0))
        self.tga_peak_var.set(float(tech.get("peak_temp_c", 0.0) or 0.0))
        self.tga_init_weight_var.set(float(tech.get("initial_weight_pct", 100.0) or 100.0))
        self.tga_residual_var.set(float(tech.get("residual_mass_pct", 0.0) or 0.0))
        self.tga_delta_w_var.set(float(tech.get("delta_weight_pct", 0.0) or 0.0))
        self.tga_atmosphere_var.set(tech.get("atmosphere", "Air") or "Air")

        cond = dict(TR.DEFAULT_CONDITIONS)
        cond.update(tech.get("conditions", {}) or {})
        self.tga_atmosphere_var.set(cond.get("atmosphere", "Air"))
        self.tga_flow_var.set(cond.get("flow_ml_min", 50.0))
        self.tga_rate_var.set(cond.get("heating_rate", 10.0))
        self.tga_mass_mg_var.set(cond.get("sample_mass_mg", 0.0))
        self.tga_limits_var.set(cond.get("manual_limits", ""))
        self.tga_tail_var.set(cond.get("tail_threshold", 0.005))
        self.tga_plot_title_var.set(tech.get("plot_title", "") or "")

        if tech.get("composition"):
            self.tga_composition = copy.deepcopy(tech["composition"])
            if TR.is_silica_paste(self.tga_composition):
                self.tga_template_var.set(SILICA_TEMPLATE)
            else:
                self.tga_template_var.set(BUILTIN_TEMPLATE)
        else:
            tpls = self._tga_load_templates()["templates"]
            sample_label_low = f"{self.current_sample_id} {data.get('material_name', '')}".lower()
            if "silica" in sample_label_low:
                self.tga_composition = copy.deepcopy(tpls[SILICA_TEMPLATE])
                self.tga_template_var.set(SILICA_TEMPLATE)
            elif "zeolite" in sample_label_low:
                self.tga_composition = copy.deepcopy(tpls[BUILTIN_TEMPLATE])
                self.tga_template_var.set(BUILTIN_TEMPLATE)
            else:
                self.tga_composition = copy.deepcopy(tpls.get("__last_used__") or tpls[BUILTIN_TEMPLATE])
        self._tga_refresh_comp_tree()

        self._tga_show_message("Select a TGA data file (.xlsx / .csv) and click “Plot / Analyze”.")
        if auto_plot:
            for c in self.tree_tga.get_children():
                if os.path.splitext(self.tree_tga.item(c, "values")[0])[1].lower() in TGA_EXTS:
                    self.tree_tga.selection_set(c)  # triggers load + plot
                    break
