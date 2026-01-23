# ui/method_report_wizard.py

import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
from typing import List, Dict, Optional
from collections import defaultdict
import logging
from PIL import Image, ImageTk
import copy

from data_model import Dataset
from services import ReportGeneratorService, DataLoaderService
from utils import resource_path, apply_dark_title_bar
from .parameter_selection import ParameterSelectionWindow

class ReportWizard(ctk.CTkToplevel):
    def __init__(self, master, datasets: List[Dataset], 
                 loader_service: DataLoaderService, 
                 report_service: ReportGeneratorService,
                 initial_params: Optional[List[Dict]] = None):
        super().__init__(master)
        
        self.logger = logging.getLogger(__name__)
        self.datasets = datasets
        self.loader_service = loader_service
        self.report_service = report_service
        
        self.title("Report Wizard")
        self.geometry("1100x750")
        self.transient(master)
        self.grab_set()
        
        self.selected_datasets_vars: Dict[str, tk.BooleanVar] = {}
        for ds in self.datasets:
            self.selected_datasets_vars[ds.key_path] = tk.BooleanVar(value=True)

        if initial_params:
            self.current_params = copy.deepcopy(initial_params)
        else:
            self.current_params = self.loader_service.get_default_parameters_for_view(self.datasets)
            
        self.param_enabled_vars: Dict[str, tk.BooleanVar] = {}
        for p in self.current_params:
            self.param_enabled_vars[self._get_param_key(p)] = tk.BooleanVar(value=True)

        self.output_dir_var = ctk.StringVar()
        self.export_format_var = ctk.StringVar(value="PDF")
        self.segment_export_mode_var = ctk.StringVar(value="Export Active Segment Only")
        self.include_plot_var = tk.BooleanVar(value=True)
        self.show_filename_var = tk.BooleanVar(value=True)

        self.report_type_var = ctk.StringVar(value="Method Report (One file per dataset)")

        self.report_name_var = ctk.StringVar(value="MethodReport")
        
        self.is_exporting = False
        
        # Images
        self.checked_img = None
        self.unchecked_img = None
        self.checked_inv_icon = None
        self.unchecked_inv_icon = None

        self._load_images()
        self._create_ui()
        self.bind("<Map>", self._on_map)
        
    def _on_map(self, event=None):
        apply_dark_title_bar(self)
        self.after(100, self._set_icon)

    def _set_icon(self):
        try:
            icon_path = resource_path("assets/icon.ico")
            if os.path.exists(icon_path):
                image = Image.open(icon_path)
                icon_image = ImageTk.PhotoImage(image)
                setattr(self.master, f"_icon_image_ref_{self.winfo_id()}", icon_image)
                self.iconphoto(False, icon_image)
        except Exception:
            pass

    def _load_images(self):
        try:
            assets = resource_path("assets")
            c_path = os.path.join(assets, "checkbox_checked.png")
            u_path = os.path.join(assets, "checkbox_unchecked.png")
            self.checked_img = ImageTk.PhotoImage(Image.open(c_path).resize((20, 20), Image.Resampling.LANCZOS))
            self.unchecked_img = ImageTk.PhotoImage(Image.open(u_path).resize((20, 20), Image.Resampling.LANCZOS))

            self.checked_inv_icon = ctk.CTkImage(Image.open(os.path.join(assets, "checkbox_checked_inv.png")), size=(22, 22))
            self.unchecked_inv_icon = ctk.CTkImage(Image.open(os.path.join(assets, "checkbox_unchecked_inv.png")), size=(22, 22))
        except Exception as e:
            self.logger.warning(f"Could not load assets: {e}")

    def _create_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1) 
        self.grid_rowconfigure(1, weight=0)

        content_frame = ctk.CTkFrame(self, fg_color="transparent")
        content_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 0))
        content_frame.grid_columnconfigure(0, weight=2)
        content_frame.grid_columnconfigure(1, weight=3)
        content_frame.grid_rowconfigure(0, weight=1)

        left_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=0)
        left_frame.grid_columnconfigure(0, weight=1)
        left_frame.grid_rowconfigure(1, weight=1) 

        ctk.CTkLabel(left_frame, text="1. Select Datasets", font=ctk.CTkFont(weight="bold"), text_color="#E4EFF7").grid(row=0, column=0, sticky="w", padx=0, pady=5)
        
        left_tree_container = ctk.CTkFrame(left_frame)
        left_tree_container.grid(row=1, column=0, sticky="nsew", padx=0, pady=(0, 5))
        left_tree_container.grid_rowconfigure(0, weight=1)
        left_tree_container.grid_columnconfigure(0, weight=1)

        style = ttk.Style()
        style.configure("Batch.Treeview", rowheight=25, background="#E4EFF7", fieldbackground="#E4EFF7", foreground="#04304D")
        style.map("Batch.Treeview", background=[('selected', '#0071BC')], foreground=[('selected', 'white')])

        self.file_tree = ttk.Treeview(left_tree_container, columns=("Path",), show="tree", style="Batch.Treeview")
        self.file_tree.heading("#0", text="Dataset Name")
        self.file_tree.column("#0", width=250)
        self.file_tree.column("Path", width=0, stretch=False)
        
        file_vsb = ctk.CTkScrollbar(left_tree_container, command=self.file_tree.yview)
        file_vsb.grid(row=0, column=1, sticky="ns")
        self.file_tree.configure(yscrollcommand=file_vsb.set)
        self.file_tree.grid(row=0, column=0, sticky="nsew")
        self.file_tree.bind("<ButtonPress-1>", self._on_file_tree_click)
        
        btn_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        btn_frame.grid(row=2, column=0, sticky="ew", padx=0, pady=5)
        ctk.CTkButton(btn_frame, text="All", width=60, command=self._select_all_files).pack(side="left", padx=(0, 5), expand=True, fill="x")
        ctk.CTkButton(btn_frame, text="None", width=60, command=self._deselect_all_files).pack(side="left", expand=True, fill="x")

        self._populate_file_tree()

        right_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0), pady=0)
        right_frame.grid_columnconfigure(0, weight=1)
        right_frame.grid_rowconfigure(1, weight=1)

        header_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(header_frame, text="2. Parameter Template (Applied to all)", font=ctk.CTkFont(weight="bold"), text_color="#E4EFF7").pack(side="left", padx=0, pady=5)
        
        param_btn_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        param_btn_frame.pack(side="right")
        
        ctk.CTkButton(param_btn_frame, text="Reset Defaults", width=100, 
                      command=self._reset_params, fg_color="#C0392B", hover_color="#E74C3C").pack(side="left", padx=(0, 5))
        ctk.CTkButton(param_btn_frame, text="Add Parameters...", width=120, 
                      command=self._open_add_params).pack(side="left")

        tree_container = ctk.CTkFrame(right_frame)
        tree_container.grid(row=1, column=0, sticky="nsew", padx=0, pady=(0, 10))
        tree_container.grid_rowconfigure(0, weight=1)
        tree_container.grid_columnconfigure(0, weight=1)

        self.param_tree = ttk.Treeview(tree_container, columns=("Group",), show="tree headings", style="Batch.Treeview")
        self.param_tree.heading("#0", text="Parameter")
        self.param_tree.column("#0", width=350)
        self.param_tree.heading("Group", text="Group")
        self.param_tree.column("Group", width=120, anchor="center")
        
        param_vsb = ctk.CTkScrollbar(tree_container, command=self.param_tree.yview)
        param_vsb.grid(row=0, column=1, sticky="ns")
        self.param_tree.configure(yscrollcommand=param_vsb.set)
        self.param_tree.grid(row=0, column=0, sticky="nsew")
        self.param_tree.bind("<ButtonPress-1>", self._on_param_tree_click)
        
        self._populate_param_tree()

        bot_frame = ctk.CTkFrame(self, fg_color="transparent")
        bot_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=10)
        bot_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(bot_frame, text="3. Output Settings", font=ctk.CTkFont(weight="bold"), text_color="#E4EFF7").grid(row=0, column=0, sticky="w", padx=0, pady=5, columnspan=3)

        ctk.CTkLabel(bot_frame, text="Report Type:", text_color="#E4EFF7").grid(row=1, column=0, sticky="w", padx=0, pady=5)
        self.report_type_menu = ctk.CTkOptionMenu(
            bot_frame,
            values=["Method Report (One file per dataset)", "Comparison Report (Side-by-side)"],
            variable=self.report_type_var,
            width=300, 
            command=self._on_report_type_change 
        )
        self.report_type_menu.grid(row=1, column=1, sticky="w", padx=5, pady=5)

        ctk.CTkLabel(bot_frame, text="Report Name:", text_color="#E4EFF7").grid(row=2, column=0, sticky="w", padx=0, pady=5)
        self.report_name_entry = ctk.CTkEntry(bot_frame, textvariable=self.report_name_var, width=300)
        self.report_name_entry.grid(row=2, column=1, sticky="w", padx=5, pady=5)

        ctk.CTkLabel(bot_frame, text="Format:", text_color="#E4EFF7").grid(row=3, column=0, sticky="w", padx=0, pady=5)
        ctk.CTkSegmentedButton(bot_frame, values=["PDF", "CSV"], variable=self.export_format_var, width=300).grid(row=3, column=1, sticky="w", padx=5, pady=5)

        opt_frame = ctk.CTkFrame(bot_frame, fg_color="transparent")
        opt_frame.grid(row=4, column=0, columnspan=3, sticky="w", padx=0, pady=5)
        
        self.seg_menu = ctk.CTkOptionMenu(
            opt_frame, 
            values=["Export Active Segment Only", "Export All Segments"],
            variable=self.segment_export_mode_var,
            width=220,
            fg_color="#004E82", button_color="#004E82", button_hover_color="#0071BC", text_color="#E4EFF7"
        )
        self.seg_menu.pack(side="left", padx=(0, 15))
        
        self.plot_btn = ctk.CTkButton(opt_frame, text="Include Plots", image=self.checked_inv_icon, 
                                      command=self._toggle_plot_mode, fg_color="transparent", hover=False, text_color="#E4EFF7")
        self.plot_btn.pack(side="left", padx=(0, 15))

        self.filename_btn = ctk.CTkButton(opt_frame, text="Include Filename in Header", image=self.checked_inv_icon, 
                                          command=self._toggle_filename_mode, fg_color="transparent", hover=False, text_color="#E4EFF7")
        self.filename_btn.pack(side="left")

        ctk.CTkLabel(bot_frame, text="Output Folder:", text_color="#E4EFF7").grid(row=5, column=0, sticky="w", padx=0, pady=5)
        ctk.CTkEntry(bot_frame, textvariable=self.output_dir_var).grid(row=5, column=1, sticky="ew", padx=5)
        ctk.CTkButton(bot_frame, text="Browse...", width=80, command=self._browse_folder).grid(row=5, column=2, padx=(5,0))

        self.progress_bar = ctk.CTkProgressBar(bot_frame)
        self.progress_bar.grid(row=6, column=0, columnspan=3, sticky="ew", padx=0, pady=(15, 5))
        self.progress_bar.set(0)
        
        self.status_label = ctk.CTkLabel(bot_frame, text="Ready", text_color="#DCE4EE")
        self.status_label.grid(row=7, column=0, columnspan=3, sticky="w", padx=0, pady=(0, 5))


        self.gen_btn = ctk.CTkButton(bot_frame, text="Generate Reports", command=self._start_batch)
        self.gen_btn.grid(row=8, column=0, columnspan=3, pady=10)


    def _populate_file_tree(self):
        self.file_tree.delete(*self.file_tree.get_children())
        for ds in self.datasets:
            is_checked = self.selected_datasets_vars[ds.key_path].get()
            img = self.checked_img if is_checked else self.unchecked_img
            self.file_tree.insert("", "end", iid=ds.key_path, text=f" {ds.display_name}", image=img, tags=('evenrow',))
        self._apply_zebra_striping(self.file_tree)

    def _populate_param_tree(self):
        self.param_tree.delete(*self.param_tree.get_children())
        grouped = defaultdict(list)
        for p in self.current_params:
            grouped[p.get('category', 'General')].append(p)
        sorted_groups = sorted(grouped.keys(), key=lambda g: (0 if g=="General" else 1, g))
        
        for group in sorted_groups:
            parent = self.param_tree.insert("", "end", text=group, open=True)
            for p in grouped[group]:
                key = self._get_param_key(p)
                is_checked = self.param_enabled_vars[key].get()
                img = self.checked_img if is_checked else self.unchecked_img
                self.param_tree.insert(parent, "end", text=f" {p.get('label', p['permname'])}", 
                                       values=(group,), image=img, iid=key)
        self._apply_zebra_striping(self.param_tree)

    def _apply_zebra_striping(self, tree: ttk.Treeview):
        tree.tag_configure('oddrow', background='#E4EFF7', foreground='#04304D')
        tree.tag_configure('evenrow', background='#FFFFFF', foreground='#04304D')
        row_index = 0
        def recurse(parent):
            nonlocal row_index
            children = tree.get_children(parent)
            for child in children:
                tag = 'evenrow' if row_index % 2 == 0 else 'oddrow'
                tree.item(child, tags=(tag,))
                row_index += 1
                recurse(child)
        recurse("")

    def _on_file_tree_click(self, event):
        iid = self.file_tree.identify_row(event.y)
        if not iid: return
        if iid in self.selected_datasets_vars:
            current = self.selected_datasets_vars[iid].get()
            self.selected_datasets_vars[iid].set(not current)
            img = self.checked_img if not current else self.unchecked_img
            self.file_tree.item(iid, image=img)

    def _on_param_tree_click(self, event):
        iid = self.param_tree.identify_row(event.y)
        if not iid: return
        if iid in self.param_enabled_vars:
            current = self.param_enabled_vars[iid].get()
            self.param_enabled_vars[iid].set(not current)
            img = self.checked_img if not current else self.unchecked_img
            self.param_tree.item(iid, image=img)

    def _on_report_type_change(self, choice):
        if "Comparison" in choice:
            self.seg_menu.configure(state="disabled")
            self.report_name_var.set("ComparisonReport")
            self.filename_btn.configure(state="normal") 
        else:
            self.seg_menu.configure(state="normal")
            self.filename_btn.configure(state="normal")
            self.report_name_var.set("MethodReport")

    def _reset_params(self):
        default_params = self.loader_service.get_default_parameters_for_view(self.datasets)
        self.current_params = default_params
        self.param_enabled_vars.clear()
        for p in self.current_params:
            self.param_enabled_vars[self._get_param_key(p)] = tk.BooleanVar(value=True)
        self._populate_param_tree()

    def _toggle_plot_mode(self):
        val = not self.include_plot_var.get()
        self.include_plot_var.set(val)
        icon = self.checked_inv_icon if val else self.unchecked_inv_icon
        self.plot_btn.configure(image=icon)

    def _toggle_filename_mode(self):
        val = not self.show_filename_var.get()
        self.show_filename_var.set(val)
        icon = self.checked_inv_icon if val else self.unchecked_inv_icon
        self.filename_btn.configure(image=icon)

    def _browse_folder(self):
        d = filedialog.askdirectory()
        if d: self.output_dir_var.set(d)

    def _select_all_files(self):
        for key, var in self.selected_datasets_vars.items():
            var.set(True)
            if self.file_tree.exists(key):
                self.file_tree.item(key, image=self.checked_img)
    
    def _deselect_all_files(self):
        for key, var in self.selected_datasets_vars.items():
            var.set(False)
            if self.file_tree.exists(key):
                self.file_tree.item(key, image=self.unchecked_img)

    def _open_add_params(self):
        all_candidates = []
        seen_keys = set()
        all_unique_sources = set()
        
        for p in self.current_params:
            k = self._get_param_key(p)
            seen_keys.add(k)
            
        for ds in self.datasets:
            all_unique_sources.update(ds.available_sources)
            ds_all = ds.default_params + ds.available_optional_params
            for p in ds_all:
                k = self._get_param_key(p)
                if k not in seen_keys:
                    seen_keys.add(k)
                    all_candidates.append(p)
        
        if not all_candidates:
            messagebox.showinfo("Info", "No additional unique parameters found across loaded datasets.")
            return

        dialog = ParameterSelectionWindow(
            self, self.loader_service, self.datasets[0], 
            all_params=all_candidates, 
            all_sources=sorted(list(all_unique_sources)), 
            previously_selected_params=self.current_params
        )
        res = dialog.get_selection()
        
        if res:
            new_params, _ = res
            existing_keys = {self._get_param_key(p) for p in self.current_params}
            added_count = 0
            for p in new_params:
                k = self._get_param_key(p)
                if k not in existing_keys:
                    self.current_params.append(p)
                    self.param_enabled_vars[k] = tk.BooleanVar(value=True)
                    existing_keys.add(k)
                    added_count += 1
            if added_count > 0:
                self._populate_param_tree()

    def _get_param_key(self, p):
        return f"{p['permname']}|{p.get('polarity')}|{p.get('source')}"

    def _start_batch(self):
        target_files = [ds for ds in self.datasets if self.selected_datasets_vars[ds.key_path].get()]
        if not target_files: 
            messagebox.showwarning("Batch", "No datasets selected.")
            return
            
        out_dir = self.output_dir_var.get()
        if not out_dir or not os.path.isdir(out_dir): 
            messagebox.showwarning("Batch", "Please select a valid output directory.")
            return
            
        final_params = [p for p in self.current_params if self.param_enabled_vars[self._get_param_key(p)].get()]
        if not final_params: 
            messagebox.showwarning("Batch", "No parameters selected.")
            return

        self.is_exporting = True
        self._set_ui_state("disabled")
        self.progress_bar.set(0)
        
        is_comparison = "Comparison" in self.report_type_var.get()
        export_all = (self.segment_export_mode_var.get() == "Export All Segments")
        report_name = self.report_name_var.get()

        thread = threading.Thread(
            target=self._run_export, 
            args=(target_files, final_params, out_dir, export_all, is_comparison, report_name)
        )
        thread.start()

    def _run_export(self, datasets, params, out_dir, export_all, is_comparison, report_name):
        def update_progress(val, text):
            if not self.winfo_exists(): return
            self.status_label.configure(text=text)
            self.progress_bar.set(val)

        try:
            total_files = len(datasets)
            for i, ds in enumerate(datasets):
                prog_val = (i / total_files) * 0.5
                self.after(0, lambda v=prog_val, n=ds.display_name: update_progress(v, f"Parsing {n}..."))
                
                self.loader_service.parse_additional_parameters(ds, params)

            safe_name_str = "".join(c for c in report_name if c.isalnum() or c in (' ', '.', '_', '-')).strip()
            if not safe_name_str: safe_name_str = "Report"

            if is_comparison:
                self.after(0, lambda: update_progress(0.6, "Generating Comparison Report..."))
                
                view_data = self.loader_service.get_parameter_view_data(datasets, params)
                fmt = self.export_format_var.get().lower()
                
                filename = f"{safe_name_str}.{fmt}"
                file_path = os.path.join(out_dir, filename)
                
                show_filenames = self.show_filename_var.get()

                if fmt == 'csv':
                    self.report_service.generate_comparison_csv(file_path, view_data, datasets, show_filenames=show_filenames)
                else:
                    do_plot = self.include_plot_var.get()
                    self.report_service.generate_comparison_pdf(file_path, view_data, datasets, include_plots=do_plot, show_filenames=show_filenames)
                
                self.after(0, lambda: update_progress(1.0, "Done"))
                self.after(0, lambda: messagebox.showinfo("Success", f"Comparison report saved to:\n{file_path}", parent=self))
            
            else:
                def batch_callback(idx, total, msg):
                    relative_progress = 0.5 + ((idx / total) * 0.5)
                    self.after(0, lambda v=relative_progress, m=msg: update_progress(v, m))

                success_count, errors = self.report_service.generate_batch_report(
                    datasets=datasets,
                    params_to_include=params,
                    output_dir=out_dir,
                    export_format=self.export_format_var.get(),
                    include_all_segments=export_all,
                    include_plot=self.include_plot_var.get(),
                    show_filename=self.show_filename_var.get(),
                    report_name=report_name, 
                    progress_callback=batch_callback
                )
                
                if not errors:
                    self.after(0, lambda: messagebox.showinfo("Batch Complete", f"Successfully processed {success_count} files.", parent=self))
                else:
                    error_msg = "\n".join(errors[:10])
                    if len(errors) > 10: error_msg += "\n..."
                    self.after(0, lambda: messagebox.showwarning("Batch Errors", f"Completed with errors:\n{error_msg}", parent=self))
                
        except Exception as e:
            self.logger.error("Export failed", exc_info=True)
            err_msg = str(e)
            self.after(0, lambda: messagebox.showerror("Error", f"Error: {err_msg}", parent=self))
        finally:
            self.is_exporting = False
            self.after(0, lambda: self._set_ui_state("normal"))
            self.after(0, lambda: update_progress(1.0, "Ready"))
            self.after(1500, lambda: self.progress_bar.set(0))

    def _update_ui_progress(self, idx, total, msg):
        self.status_label.configure(text=msg)
        if total > 0:
            self.progress_bar.set((idx + 1) / total)
    
    def _set_ui_state(self, state: str):
        widgets = [
            self.file_tree, self.param_tree, 
            self.report_type_menu, self.report_name_entry, self.export_format_var,
            self.seg_menu, self.plot_btn, self.filename_btn, 
            self.output_dir_var, self.gen_btn
        ]
        
        self.gen_btn.configure(state=state)
        self.report_type_menu.configure(state=state)
        self.seg_menu.configure(state=state)
        self.plot_btn.configure(state=state)
        self.filename_btn.configure(state=state)
        
        cursor = "watch" if state == "disabled" else ""
        self.configure(cursor=cursor)