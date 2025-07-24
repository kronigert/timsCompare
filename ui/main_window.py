# ui/main_window.py

import os
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
from tkinter.font import Font
from tkinterdnd2 import DND_FILES
from typing import List, Dict, Optional, Any
from collections import defaultdict

import customtkinter as ctk
import pandas as pd

from app_config import AppConfig
from data_model import Dataset
from services import DataLoaderService, PlottingService, ReportGeneratorService, DataProcessingError
from utils import format_parameter_value
from .parameter_selection import ParameterSelectionWindow
from PIL import Image

class Tooltip:
    """
    Creates a tooltip for a given widget that appears when the mouse
    hovers over it.
    """
    def __init__(self, widget, text_callback):
        self.widget = widget
        self.text_callback = text_callback
        self.tip_window = None
        self.id = None
        self.x = self.y = 0
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)
        self.widget.bind("<ButtonPress>", self.leave)

    def enter(self, event=None):
        self.schedule()

    def leave(self, event=None):
        self.unschedule()
        self.hidetip()

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(500, self.showtip)

    def unschedule(self):
        id = self.id
        self.id = None
        if id:
            self.widget.after_cancel(id)

    def showtip(self):
        if self.tip_window:
            return
            
        full_text = self.text_callback()
        if not full_text:
            return

        displayed_text = ""
        try:
            displayed_text = self.widget.cget("text")
        except (ValueError, AttributeError):
            try:
                displayed_text = self.widget.get()
            except (ValueError, AttributeError):
                pass
        
        if len(displayed_text) >= len(full_text):
            return

        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        
        self.tip_window = tk.Toplevel(self.widget)
        self.tip_window.wm_overrideredirect(True)
        self.tip_window.wm_geometry(f"+{x}+{y}")
        
        label = ctk.CTkLabel(self.tip_window, text=full_text, fg_color="#3E3E3E", 
                               bg_color="transparent", text_color="white",
                               corner_radius=4, padx=8, pady=4,
                               font=ctk.CTkFont(size=11))
        label.pack(ipadx=1)

    def hidetip(self):
        tw = self.tip_window
        self.tip_window = None
        if tw:
            tw.destroy()


class timsCompareApp:
    def __init__(self, root: tk.Tk, config: AppConfig, data_loader: DataLoaderService, plot_service: PlottingService, report_generator: ReportGeneratorService):
        self.root = root
        
        self.config = config
        self.loader = data_loader
        self.plotter = plot_service
        self.report_generator = report_generator

        if not hasattr(self.root, "block_update_dimensions_event"):
            self.root.block_update_dimensions_event = lambda: None
        if not hasattr(self.root, "unblock_update_dimensions_event"):
            self.root.unblock_update_dimensions_event = lambda: None

        self.root.title("timsCompare")
        self.root.geometry("1500x800")
        
        self.datasets: List[Dataset] = []
        self.user_added_params: List[Dict] = []
        self.dropdown_name_map: Dict[str, str] = {}
        self.status_label_full_text: str = ""
        
        self.main_frame: Optional[ctk.CTkFrame] = None
        self.tree: Optional[ttk.Treeview] = None
        self.table_frame: Optional[ctk.CTkFrame] = None
        self.right_plot_container: Optional[ctk.CTkFrame] = None
        self.plots_canvas: Optional[ctk.CTkScrollableFrame] = None 
        self.hide_plots_button: Optional[ctk.CTkButton] = None
        self.status_bar_label: Optional[ctk.CTkLabel] = None
        self.plot_toggle_button: Optional[ctk.CTkButton] = None
        self.plot_toggle_menu: Optional[tk.Menu] = None
        self.add_menu_button: Optional[ctk.CTkButton] = None
        self.add_menu: Optional[tk.Menu] = None
        self.remove_menu: Optional[ctk.CTkOptionMenu] = None
        self.context_menu: Optional[tk.Menu] = None
        self.show_diffs_button: Optional[ctk.CTkButton] = None
        self.export_menu_button: Optional[ctk.CTkButton] = None
        self.export_menu: Optional[tk.Menu] = None
        self.about_button: Optional[ctk.CTkButton] = None
        
        self.segment_controls_frame: Optional[ctk.CTkScrollableFrame] = None
        self.segment_dropdowns: Dict[str, Dict[str, Any]] = {}

        self.active_row_iid: Optional[str] = None
        self.active_column_id: Optional[str] = None

        self.remove_var = ctk.StringVar()
        self.plots_visible = tk.BooleanVar(value=True)
        self.show_only_diffs_var = ctk.BooleanVar(value=False)
        self._resize_job: Optional[str] = None
        
        self.optionmenu_font = ctk.CTkFont()

        self._setup_styles()
        self._load_icons()
        self._create_widgets()
        self._redraw_ui()

    def _create_widgets(self):
        self.main_frame = ctk.CTkFrame(self.root, fg_color="#04304D", corner_radius=0)
        self.main_frame.pack(fill="both", expand=True)
        self.main_frame.grid_rowconfigure(2, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(1, weight=1)

        top_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        top_frame.grid(row=0, column=0, columnspan=2, padx=10, pady=(10, 5), sticky="ew")

        self.add_menu_button = ctk.CTkButton(top_frame, text="Add Data", image=self.add_data_icon, command=self._show_add_menu)
        self.add_menu_button.pack(side="left", padx=(0, 10))

        self.add_params_button = ctk.CTkButton(top_frame, text="Add Parameters", image=self.add_params_icon, command=self._open_add_parameters_dialog)
        self.add_params_button.pack(side="left", padx=(0, 10))
        
        self.reset_params_button = ctk.CTkButton(top_frame, text="Reset View", image=self.reset_icon, command=self._reset_to_default_parameters)
        self.reset_params_button.pack(side="left", padx=(0, 15))

        self.show_diffs_button = ctk.CTkButton(top_frame, text="Show only differences", image=self.diffs_unchecked_icon, command=self._toggle_show_differences, width=28, height=28, fg_color="transparent")
        self.show_diffs_button.pack(side="left", padx=5)
        Tooltip(self.show_diffs_button, lambda: "Show only differences")

        self.about_button = ctk.CTkButton(top_frame, text="About", image=self.about_icon, command=self._show_about_dialog, width=28)
        self.about_button.pack(side="right", padx=(5, 0))
        Tooltip(self.about_button, lambda: "About timsCompare")

        self.hide_plots_button = ctk.CTkButton(top_frame, text="Hide Plots", image=self.hide_icon, command=self._toggle_plot_pane)
        self.hide_plots_button.pack(side="right")

        self.segment_controls_frame = ctk.CTkScrollableFrame(
            self.main_frame, fg_color="transparent", orientation="horizontal", label_text="", height=40
        )
        self.segment_controls_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=(5, 0), sticky="ew")
        self.segment_controls_frame.grid_remove()

        self.plot_toggle_menu = tk.Menu(self.root, tearoff=0)
        self.add_menu = tk.Menu(self.root, tearoff=0)
        self.add_menu.add_command(label="Add .d Folder...", command=lambda: self._add_folder_dialog(".d"))
        self.add_menu.add_command(label="Add .m Folder...", command=lambda: self._add_folder_dialog(".m"))

        self.table_frame = ctk.CTkFrame(self.main_frame, fg_color="#E4EFF7", corner_radius=0, border_width=0)
        self.table_frame.grid(row=2, column=0, sticky="nsew", padx=(10, 2), pady=5)
        self.table_frame.grid_propagate(False)
        self.table_frame.grid_rowconfigure(0, weight=1)
        self.table_frame.grid_columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(self.table_frame, show="tree headings")
        self.tree.grid(row=0, column=0, sticky="nsew")

        self.tree.tag_configure('oddrow', background='#E4EFF7')
        self.tree.tag_configure('evenrow', background='#FFFFFF')
        self.tree.tag_configure('diff', font=('TkDefaultFont', 10, 'bold'))

        vsb = ctk.CTkScrollbar(self.table_frame, orientation="vertical", command=self.tree.yview)
        hsb = ctk.CTkScrollbar(self.table_frame, orientation="horizontal", command=self.tree.xview)
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        ctk.CTkFrame(self.table_frame, fg_color="#E4EFF7", border_width=0, width=16, height=16).place(relx=1.0, rely=1.0, anchor="se")

        self.tree.bind("<Motion>", self._on_tree_motion)
        self.tree.bind("<Control-c>", self._copy_selection_to_clipboard)
        self.tree.bind("<Button-3>", self._show_context_menu)
        self.tree.bind("<Button-1>", self._on_cell_select)

        self._create_context_menu()

        self.right_plot_container = ctk.CTkFrame(self.main_frame, fg_color="#E4EFF7", corner_radius=0, border_width=0)
        self.right_plot_container.grid(row=2, column=1, sticky="nsew", padx=(2, 10), pady=5)
        self.right_plot_container.grid_columnconfigure(0, weight=1)
        self.right_plot_container.grid_rowconfigure(0, weight=0)
        self.right_plot_container.grid_rowconfigure(1, weight=1)
        self.right_plot_container.bind("<Configure>", self._on_container_resize)

        self.plot_toggle_button = ctk.CTkButton(self.right_plot_container, text="", image=self.plots_icon, command=self._show_plot_toggle_menu, width=28, fg_color="transparent", hover_color="#DFE5EA")
        self.plot_toggle_button.grid(row=0, column=0, sticky="ne", padx=5, pady=(5,0))
        Tooltip(self.plot_toggle_button, lambda: "Toggle plot visibility")

        bottom_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        bottom_frame.grid(row=3, column=0, columnspan=2, padx=10, pady=(15, 10), sticky="ew")

        bottom_frame.grid_columnconfigure(0, weight=1, uniform="bottom_split")
        bottom_frame.grid_columnconfigure(1, weight=1, uniform="bottom_split")

        left_controls = ctk.CTkFrame(bottom_frame, fg_color="transparent")
        left_controls.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        left_controls.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(left_controls, text="File:", text_color="#E4EFF7", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=(0, 8))

        self.remove_menu = ctk.CTkOptionMenu(
            left_controls, 
            variable=self.remove_var, 
            values=["-"]
        )
        self.remove_menu.grid(row=0, column=1, sticky="ew", padx=(0, 10))

        self.export_menu_button = ctk.CTkButton(left_controls, text="Export", image=self.export_icon, command=self._show_export_menu, width=90)
        self.export_menu_button.grid(row=0, column=2, padx=(0, 5))

        self.export_menu = tk.Menu(self.root, tearoff=0)
        self.export_menu.add_command(label="Windows", command=self.export_scan_windows)
        self.export_menu.add_command(label="Method Report...", command=self._open_report_generator_dialog)

        remove_button = ctk.CTkButton(left_controls, text="Remove", image=self.remove_icon, command=self._remove_selected_folder, width=28, height=28)
        remove_button.grid(row=0, column=3)
        Tooltip(remove_button, lambda: "Remove selected dataset")

        right_status_frame = ctk.CTkFrame(bottom_frame, fg_color="transparent")
        right_status_frame.grid(row=0, column=1, sticky="ew")

        self.status_bar_label = ctk.CTkLabel(right_status_frame, text="", anchor="e", text_color="#E4EFF7")
        self.status_bar_label.pack(side="right", fill="x", expand=True, padx=(10, 0))

        Tooltip(self.remove_menu, lambda: self.dropdown_name_map.get(self.remove_var.get(), ""))
        Tooltip(self.status_bar_label, lambda: self.status_label_full_text)

        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind('<<Drop>>', self._handle_drop)
        
    def _on_segment_selected(self, dataset_key: str, choice: str):
        target_dataset = next((d for d in self.datasets if d.key_path == dataset_key), None)
        if not target_dataset: return

        try:
            new_index = int(choice.split(' ')[1]) - 1
            if 0 <= new_index < len(target_dataset.segments):
                target_dataset.active_segment_index = new_index
                self._update_treeview_data()
                self._update_plot_grid()
        except (ValueError, IndexError):
            print(f"Warning: Could not parse segment index from choice '{choice}'")
    
    def _update_segment_controls(self):
        for widget in self.segment_controls_frame.winfo_children():
            widget.destroy()
        self.segment_dropdowns.clear()

        has_segmented_run = any(len(dataset.segments) > 1 for dataset in self.datasets)

        if has_segmented_run:
            self.segment_controls_frame.grid()
            for i, dataset in enumerate(self.datasets):
                if len(dataset.segments) > 1:
                    control_container = ctk.CTkFrame(self.segment_controls_frame, fg_color="transparent")
                    control_container.pack(side="left", padx=(0, 20), pady=2)
                    
                    label_text = self._truncate_text(dataset.display_name, 150, self.optionmenu_font)
                    label = ctk.CTkLabel(control_container, text=f"{label_text}:", text_color="#E4EFF7")
                    label.pack(side="left", padx=(0, 5))
                    Tooltip(label, lambda name=dataset.display_name: name)

                    label.bind("<Enter>", lambda e, name=dataset.display_name: self._set_status_bar_text(name))
                    label.bind("<Leave>", lambda e: self._set_status_bar_text(""))

                    var = ctk.StringVar()
                    menu_choices = [f"Segment {i+1} ({seg.start_time:.2f} - {seg.end_time_display})" for i, seg in enumerate(dataset.segments)]
                    
                    menu = ctk.CTkOptionMenu(
                        control_container, 
                        variable=var, 
                        values=menu_choices,
                        command=lambda choice, key=dataset.key_path: self._on_segment_selected(key, choice)
                    )
                    menu.pack(side="left")
                    
                    var.set(menu_choices[dataset.active_segment_index])
                    self.segment_dropdowns[dataset.key_path] = {'var': var, 'menu': menu}
        else:
            self.segment_controls_frame.grid_remove()
    
    def _reset_to_default_parameters(self):
        if self.user_added_params:
            self.user_added_params.clear()
            self._redraw_ui()
            
    def _redraw_ui(self, *args):
        self._reconfigure_treeview()
        self._update_treeview_data()
        self.root.after(50, self._reconfigure_plot_area) 
        self.root.after(100, self._update_remove_menu)
        self._update_segment_controls()

    def _handle_drop(self, event: tk.Event):
        paths = self.root.tk.splitlist(event.data)
        valid_folders = [p for p in paths if os.path.isdir(p) and p.lower().endswith((".d", ".m"))]
        if not valid_folders:
            messagebox.showwarning("Drag & Drop Info", "No valid .d or .m folders were dropped.")
            return
        self._load_folders(valid_folders)

    def _add_folder_dialog(self, extension: str):
        folder = filedialog.askdirectory(title=f"Select a {extension} folder")
        if not folder or not folder.lower().endswith(extension):
            return
        self._load_folders([folder])

    def _load_folders(self, folder_paths: List[str]):
        loaded_count = 0
        for path in folder_paths:
            if any(d.key_path == path for d in self.datasets):
                messagebox.showinfo("Already Loaded", f"The data for '{os.path.basename(path)}' is already loaded.")
                continue
            try:
                dataset = self.loader.load_dataset_from_folder(path)
                if dataset:
                    self.datasets.append(dataset)
                    loaded_count += 1
                else:
                    messagebox.showerror("Load Error", f"Failed to load dataset from:\n{path}\n\nThe service returned an invalid object.")
            except DataProcessingError as e:
                messagebox.showerror("Error Loading Data", str(e))
            except Exception as e:
                messagebox.showerror("An Unexpected Error Occurred", f"An unexpected error occurred while loading '{os.path.basename(path)}':\n\n{e.__class__.__name__}: {e}")

        if loaded_count > 0:
            self._redraw_ui()
            
    def _remove_selected_folder(self):
        selected_truncated_name = self.remove_var.get()
        if not selected_truncated_name or selected_truncated_name == "-": return
        
        full_name = self.dropdown_name_map.get(selected_truncated_name)
        if not full_name: return

        self.datasets = [d for d in self.datasets if d.display_name != full_name]
        self._redraw_ui()
        
    def _open_add_parameters_dialog(self):
        if not self.datasets:
            messagebox.showinfo("Information", "Please load at least one dataset before adding parameters.")
            return

        selected_name = self.remove_var.get()
        if not selected_name or selected_name == "-":
            selected_dataset = self.datasets[0]
        else:
            selected_dataset = next((d for d in self.datasets if d.display_name == self.dropdown_name_map.get(selected_name)), None)
        
        if not selected_dataset: return

        all_found_params = {
            self._get_param_key(p): p for ds in self.datasets 
            for p in (ds.default_params + ds.available_optional_params)
        }
        all_param_definitions = list(all_found_params.values())
        
        default_param_keys = {self._get_param_key(p) for p in selected_dataset.default_params}
        previously_selected_keys = default_param_keys.union({self._get_param_key(p) for p in self.user_added_params})
        previously_selected_params = [p for p in all_param_definitions if self._get_param_key(p) in previously_selected_keys]
        
        dialog = ParameterSelectionWindow(
            self.root,
            dataset=selected_dataset,
            all_params=all_param_definitions,
            previously_selected_params=previously_selected_params
        )
        new_selection = dialog.get_selection()

        if new_selection is not None:
            existing_user_param_keys = {self._get_param_key(p) for p in self.user_added_params}
            newly_added_configs = []

            for p_config in new_selection:
                key = self._get_param_key(p_config)
                if key not in default_param_keys and key not in existing_user_param_keys:
                    self.user_added_params.append(p_config)
                    newly_added_configs.append(p_config)

            if newly_added_configs:
                for ds in self.datasets:
                    self.loader.parse_additional_parameters(ds, newly_added_configs)

            self._redraw_ui()
            
    def _insert_row(self, param_config: Dict, parent_node: str, values: List[str]):
        is_different = len(set([v for v in values if v not in ["", "N/A"]])) > 1
        if self.show_only_diffs_var.get() and not is_different:
            return

        permname = param_config.get("permname")
        label = param_config.get("label", permname)
        
        self.tree.insert(parent_node, "end", text=label, values=tuple(values), tags=('diff',) if is_different else ())
    
    def _insert_expandable_list_rows(self, param_config: Dict, parent_node: str, raw_values: List[Any]):
        parent_row_values = [format_parameter_value(val, param_config) for val in raw_values]
        is_parent_different = len(set(parent_row_values)) > 1
        
        if self.show_only_diffs_var.get():
            any_child_different = False
            max_len = max((len(v) for v in raw_values if isinstance(v, list)), default=0)
            for i in range(max_len):
                temp_child_values = [format_parameter_value(v[i], param_config) if isinstance(v, list) and i < len(v) else "N/A" for v in raw_values]
                if len(set(v for v in temp_child_values if v != "N/A")) > 1:
                    any_child_different = True
                    break
            if not is_parent_different and not any_child_different:
                return

        permname = param_config.get("permname")
        label = param_config.get("label", permname)
        parent_iid = self.tree.insert(parent_node, "end", text=label, values=tuple(parent_row_values), open=False, tags=('diff',) if is_parent_different else ())

        max_len = max((len(v) for v in raw_values if isinstance(v, list)), default=0)
        for i in range(max_len):
            child_row_values = [format_parameter_value(v[i], param_config) if isinstance(v, list) and i < len(v) else "N/A" for v in raw_values]
            is_child_different = len(set(v for v in child_row_values if v != "N/A")) > 1
            
            if self.show_only_diffs_var.get() and not is_child_different:
                continue

            self.tree.insert(parent_iid, "end", text=f"  Item {i+1}", values=tuple(child_row_values), tags=('diff',) if is_child_different else ())
    
    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview.Heading", background="#004E82", foreground="white", font=('TkDefaultFont', 10, 'bold'), padding=5)
        style.map("Treeview.Heading", background=[('active', "#0071BC")])
        style.configure("Treeview", background="#E4EFF7", foreground="#04304D", fieldbackground="#E4EFF7", rowheight=25, borderwidth=0)
        style.map("Treeview", background=[('selected', '#0071BC')], foreground=[('selected', 'white')])
        
    def _update_treeview_data(self):
        for row in self.tree.get_children(): self.tree.delete(row)
        if not self.datasets:
            self.tree.configure(show="tree"); self.tree.heading("#0", text="")
            return
        
        self.tree.configure(show="tree headings")
        
        default_params_by_workflow = self.config.parameter_definitions
        active_workflows = {ds.segments[ds.active_segment_index].workflow_name for ds in self.datasets if ds.segments}

        default_permnames_ordered = []
        seen_permnames = set()

        def add_unique(permnames):
            for pname in permnames:
                if pname not in seen_permnames:
                    seen_permnames.add(pname)
                    default_permnames_ordered.append(pname)

        add_unique(default_params_by_workflow.get("__GENERAL__", []))
        for wf in active_workflows:
            add_unique(default_params_by_workflow.get(wf, []))
        
        all_definitions_map = {p['permname']: p for p in self.config.all_definitions}
        default_param_configs = []

        for pname in default_permnames_ordered:
            if pname in all_definitions_map:
                default_param_configs.append(all_definitions_map[pname])
            elif pname.startswith("calc_"):
                label_map = {
                    "calc_scan_area_mz": "Window Scan Area",
                    "calc_ramps": "Ramps per Cycle",
                    "calc_ms1_scans": "MS1 Scans per Cycle",
                    "calc_steps": "Isolation Steps per Cycle",
                    "calc_mz_width": "Isolation Window Width",
                    "calc_ce_ramping_start": "CE Ramping Start",
                    "calc_ce_ramping_end": "CE Ramping End"
                }
                label = label_map.get(pname, pname.replace("calc_", "").replace("_", " ").title())
                category = "Mode" if "Scan Mode" in label else "Calculated Parameters"
                default_param_configs.append({"permname": pname, "label": label, "category": category})                
        has_multisegment_file = any(len(ds.segments) > 1 for ds in self.datasets)
        
        sorted_user_added_params = sorted(self.user_added_params, key=lambda p: p.get('label', ''))
        all_display_configs = default_param_configs + sorted_user_added_params
        
        grouped_params = defaultdict(list)
        for p_config in all_display_configs:
            grouped_params[p_config.get("category", "General")].append(p_config)

        def sort_key(g):
            if g == "Mode": return (0, g)
            if g == "Calculated Parameters": return (2, g)
            return (1, g)
        sorted_groups = sorted(grouped_params.keys(), key=sort_key)
        
        order_map = {pname: i for i, pname in enumerate(default_permnames_ordered)}

        has_standard_ce_dataset = any(ds.get_parameter_value("Energy_Ramping_Advanced_Settings_Active") == '0' for ds in self.datasets if ds.segments)
        has_advanced_ce_dataset = any(ds.get_parameter_value("Energy_Ramping_Advanced_Settings_Active") == '1' for ds in self.datasets if ds.segments)
        has_icc_mode1 = any(ds.get_parameter_value("IMSICC_Mode") == '1' for ds in self.datasets if ds.segments)
        has_icc_mode2 = any(ds.get_parameter_value("IMSICC_Mode") == '2' for ds in self.datasets if ds.segments)

        displayed_param_keys = set()
        for group_name in sorted_groups:
            parent_node = self.tree.insert("", "end", text=group_name, open=True)
            
            params_in_group = sorted(
                grouped_params[group_name], 
                key=lambda p: (order_map.get(p['permname'], float('inf')), p.get('label', ''))
            )
            
            for param_config in params_in_group:
                permname = param_config['permname']
                if permname in displayed_param_keys: continue

                if permname in ["calc_segment_start_time", "calc_segment_end_time"] and not has_multisegment_file: continue
                if permname in ["calc_ce_ramping_start", "calc_ce_ramping_end"] and not has_standard_ce_dataset: continue
                if permname == "calc_advanced_ce_ramping_display_list" and not has_advanced_ce_dataset: continue
                if permname == 'IMSICC_Target' and not has_icc_mode1: continue
                
                mode2_params = [
                    "IMSICC_ICC2_MaxTicTargetPercent", 
                    "IMSICC_ICC2_MinAccuTime", 
                    "IMSICC_ICC2_ReferenceTicCapacity", 
                    "IMSICC_ICC2_SmoothingFactor"
                ]
                if permname in mode2_params and not has_icc_mode2: continue

                raw_values = []
                for ds in self.datasets:
                    val = ds.get_parameter_value(permname)
                    if permname == 'IMSICC_Mode' and val is None:
                        val = '0'
                    raw_values.append(val)

                is_list_param = any(isinstance(val, list) for val in raw_values)

                if is_list_param:
                    self._insert_expandable_list_rows(param_config, parent_node, raw_values)
                else:
                    formatted_values = [format_parameter_value(val, param_config) for val in raw_values]
                    self._insert_row(param_config, parent_node, formatted_values)
                
                displayed_param_keys.add(permname)

        for parent_iid in self.tree.get_children(''):
            children = self.tree.get_children(parent_iid)
            if not children:
                self.tree.delete(parent_iid) 
            else:
                for i, child_iid in enumerate(children):
                    tag = 'evenrow' if i % 2 == 0 else 'oddrow'
                    current_tags = [t for t in list(self.tree.item(child_iid, 'tags')) if t not in ['evenrow', 'oddrow']]
                    current_tags.append(tag)
                    self.tree.item(child_iid, tags=tuple(current_tags))
                
    def _generate_group_name(self, workflow_set: frozenset, all_active_workflows: set) -> str:
        if len(workflow_set) == len(all_active_workflows): return "Method Parameters"
        return f"{'/'.join(sorted([n.replace('-PASEF', '') for n in workflow_set]))} Parameters"
        
    def _get_param_key(self, param: Dict) -> str:
        return f"{param['permname']}|{param.get('polarity')}|{param.get('source')}"

    def _create_context_menu(self):
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Copy Cell Value", command=self._copy_cell_value)
        self.context_menu.add_command(label="Copy Selected Row(s)", command=self._copy_selection_to_clipboard)

    def _show_context_menu(self, event: tk.Event):
        self._on_cell_select(event)
        if self.active_row_iid and self.tree.exists(self.active_row_iid):
            is_adv_ce = self.tree.item(self.active_row_iid, "text").startswith("CE Ramping (Advanced)")
            is_data = (self.active_column_id and self.tree.item(self.active_row_iid, "values")) or is_adv_ce
            self.context_menu.entryconfigure("Copy Cell Value", state="normal" if is_data else "disabled")
            self.context_menu.entryconfigure("Copy Selected Row(s)", state="normal" if self.tree.selection() or is_adv_ce else "disabled")
            self.context_menu.tk_popup(event.x_root, event.y_root)

    def _on_cell_select(self, event: tk.Event):
        self.active_row_iid = self.tree.identify_row(event.y)
        self.active_column_id = self.tree.identify_column(event.x)

    def _copy_cell_value(self, event=None):
        if not all([self.active_row_iid, self.active_column_id, self.tree.exists(self.active_row_iid)]): return
        cell_value = ""
        if self.active_column_id == '#0':
            cell_value = self.tree.item(self.active_row_iid, "text")
            if cell_value.startswith("CE Ramping (Advanced)"):
                children = [f"{self.tree.item(cid, 'text')}\t" + '\t'.join(map(str, self.tree.item(cid, 'values'))) for cid in self.tree.get_children(self.active_row_iid)]
                if children: cell_value += "\n" + "\n".join(children)
        else:
            try:
                col_idx = int(self.active_column_id.replace('#', '')) - 1
                values = self.tree.item(self.active_row_iid, "values")
                if values and 0 <= col_idx < len(values): cell_value = values[col_idx]
            except (ValueError, IndexError): return
        if cell_value: self.root.clipboard_clear(); self.root.clipboard_append(cell_value)

    def _copy_selection_to_clipboard(self, event=None):
        selected = self.tree.selection()
        if not selected and self.active_row_iid and self.tree.exists(self.active_row_iid) and self.tree.item(self.active_row_iid, "text").startswith("CE Ramping (Advanced)"):
            selected = (self.active_row_iid,)
        if not selected: return
        
        headers = [self.tree.heading("#0", "text")] + [self.tree.heading(c, "text") for c in self.tree['columns']]
        text = ["\t".join(headers)]
        for item in selected:
            text.append("\t".join(map(str, [self.tree.item(item, "text")] + list(self.tree.item(item, "values")))))
            if self.tree.item(item, "text").startswith("CE Ramping (Advanced)"):
                for child in self.tree.get_children(item):
                    text.append(f"{self.tree.item(child, 'text')}\t" + "\t".join(map(str, self.tree.item(child, "values"))))
        if len(text) > 1: self.root.clipboard_clear(); self.root.clipboard_append("\n".join(text))
            
    def _reconfigure_treeview(self):
        if not self.datasets:
            self.tree.configure(show="tree", columns=()); self.tree.heading("#0", text="")
            return
        
        self.tree.configure(show="tree headings", columns=tuple(d.key_path for d in self.datasets))
        self.tree.heading("#0", text="Parameter"); self.tree.column("#0", width=250, anchor="w", minwidth=200)
        
        for ds in self.datasets:
            self.tree.heading(ds.key_path, text=ds.display_name, anchor="center")
            self.tree.column(ds.key_path, width=150, anchor="center", minwidth=100)
            
    def _toggle_plot_pane(self):
        is_visible = self.plots_visible.get()
        if is_visible:
            self.right_plot_container.grid_forget()
            self.table_frame.grid_configure(columnspan=2, padx=(10, 10))
            self.hide_plots_button.configure(text="Show Plots")
        else:
            self.table_frame.grid_configure(columnspan=1, padx=(10, 2))
            self.right_plot_container.grid(row=2, column=1, sticky="nsew", padx=(2, 10), pady=5)
            self.hide_plots_button.configure(text="Hide Plots")
        self.plots_visible.set(not is_visible)

    def _on_container_resize(self, event=None):
        if self._resize_job: self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(250, self._update_plot_grid)

    def _reconfigure_plot_area(self):
        self.plot_toggle_menu.delete(0, "end")
        for ds in self.datasets: self.plot_toggle_menu.add_checkbutton(label=ds.display_name, variable=ds.is_plotted_var, command=self._update_plot_grid)
        
        if hasattr(self, 'plots_canvas') and self.plots_canvas: self.plots_canvas.destroy()

        self.plots_canvas = ctk.CTkScrollableFrame(self.right_plot_container, label_text="")
        self.plots_canvas.grid(row=1, column=0, sticky="nsew")
        self.plots_canvas.grid_columnconfigure(0, weight=1); self.plots_canvas.grid_columnconfigure(1, weight=1)
        self._update_plot_grid()

    def _show_plot_toggle_menu(self):
        self.plot_toggle_menu.tk_popup(self.plot_toggle_button.winfo_rootx(), self.plot_toggle_button.winfo_rooty() + self.plot_toggle_button.winfo_height())

    def _update_plot_grid(self):
        if not self.plots_canvas or not self.plots_canvas.winfo_exists(): return
        for widget in self.plots_canvas.winfo_children(): widget.destroy()
            
        plots_to_render = [ds for ds in self.datasets if ds.is_plotted_var.get()]
        if not plots_to_render: return
        
        self.root.update_idletasks()
        
        num_cols = 2 if len(plots_to_render) > 1 else 1
        container_width = self.plots_canvas._current_width if hasattr(self.plots_canvas, '_current_width') else self.plots_canvas.winfo_width()
        if container_width < 100: container_width = 800
        
        cell_width_px = max(50, (container_width // num_cols) - 25)
        cell_height_px = max(50, int(cell_width_px * 0.8))
        
        for i, ds in enumerate(plots_to_render):
            row, col = divmod(i, num_cols)
            self.plots_canvas.grid_rowconfigure(row, minsize=cell_height_px)
            plot_frame = ctk.CTkFrame(self.plots_canvas, fg_color="transparent", width=cell_width_px, height=cell_height_px)
            plot_frame.grid(row=row, column=col, sticky="nsew", padx=5, pady=5); plot_frame.grid_propagate(False)
            
            ctk_image = self.plotter.create_plot_image(ds, cell_width_px, cell_height_px)
            if ctk_image:
                plot_label = ctk.CTkLabel(plot_frame, image=ctk_image, text="")
                plot_label.pack(fill="both", expand=True)
                for widget in [plot_frame, plot_label]:
                    widget.bind("<Enter>", lambda e, name=ds.display_name: self._set_status_bar_text(name))
                    widget.bind("<Leave>", lambda e: self._set_status_bar_text(""))
    
    def _truncate_text(self, text: str, max_width_px: int, font: ctk.CTkFont) -> str:
        if not text or font.measure(text) <= max_width_px: return text
        ellipsis = "..."; basename, extension = os.path.splitext(text)
        if not extension or not basename:
            for i in range(len(text) // 2, 0, -1):
                if font.measure(f"{text[:i]}{ellipsis}{text[len(text)-i:]}") <= max_width_px: return f"{text[:i]}{ellipsis}{text[len(text)-i:]}"
            return ""
        available_width = max_width_px - font.measure(extension)
        if available_width <= font.measure(ellipsis): return ellipsis + extension
        for i in range(len(basename) // 2, 0, -1):
            if font.measure(f"{basename[:i]}{ellipsis}{basename[len(basename)-i:]}") <= available_width: return f"{basename[:i]}{ellipsis}{basename[len(basename)-i:]}{extension}"
        for i in range(len(basename) - 1, 0, -1):
            if font.measure(f"{basename[:i]}{ellipsis}") <= available_width: return f"{basename[:i]}{ellipsis}{extension}"
        return ellipsis + extension

    def _set_status_bar_text(self, full_text: str):
        self.status_label_full_text = full_text; self.status_bar_label.configure(text=full_text)

    def _on_tree_motion(self, event: tk.Event):
        region = self.tree.identify_region(event.x, event.y)
        if region == "heading":
            col_id = self.tree.identify_column(event.x)
            if col_id != "#0":
                try:
                    col_index = int(col_id.replace('#', '')) - 1
                    if 0 <= col_index < len(self.datasets): self._set_status_bar_text(self.datasets[col_index].display_name)
                    return
                except (ValueError, IndexError): pass
        self._set_status_bar_text("")

    def export_scan_windows(self):
        selected_name = self.remove_var.get()
        if not selected_name or selected_name == "-": return messagebox.showwarning("No Selection", "Please select a dataset to export.")
        full_name = self.dropdown_name_map.get(selected_name)
        dataset = next((d for d in self.datasets if d.display_name == full_name), None)
        if not dataset or not dataset.segments: return
        
        active_segment = dataset.segments[dataset.active_segment_index]
        base_name, _ = os.path.splitext(dataset.display_name)
        
        content_map = {
            9: (self._convert_dia_spec_to_parameters(active_segment.dia_windows_data), f"{base_name}_Seg{dataset.active_segment_index+1}_diaParameters.txt"),
            11: (self._convert_diagonal_spec_to_parameters(active_segment.diagonal_pasef_data, active_segment.parameters), f"{base_name}_Seg{dataset.active_segment_index+1}_diagonalSlices.txt"),
            6: (self._convert_pasef_polygon_to_text(active_segment.pasef_polygon_data), f"{base_name}_Seg{dataset.active_segment_index+1}_Polygon.txt")
        }
        
        scan_mode_id = active_segment.scan_mode_id
        if scan_mode_id not in content_map:
            return messagebox.showwarning("No Export Available", f"No export data available for this scan mode.")
        
        content, filename = content_map[scan_mode_id]
        if not content: return messagebox.showerror("Export Error", "Failed to generate export data.")
            
        file_path = filedialog.asksaveasfilename(defaultextension=".txt", initialfile=filename, title="Export Scan Windows for Active Segment", filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if not file_path: return
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f: f.write(content)
            messagebox.showinfo("Success", f"Data successfully exported to\n{file_path}")
        except Exception as e:
            messagebox.showerror("Export Error", f"An error occurred while saving the file:\n{e}")
            
    def _convert_dia_spec_to_parameters(self, df: pd.DataFrame) -> str:
        lines = ["#MS Type,Cycle Id,Start IM [1/K0],End IM [1/K0],Start Mass [m/z],End Mass [m/z],CE [eV]"]
        if df is None or df.empty: return "\n".join(lines)
        required_cols = ['Id', 'Type', 'CycleId', 'OneOverK0Start', 'OneOverK0End', 'IsolationMz', 'IsolationWidth']
        if not all(c in df.columns for c in required_cols): return "\n".join(lines)
        df_exp = df.copy()
        df_exp['StartMass'] = df_exp['IsolationMz'] - (df_exp['IsolationWidth'] / 2)
        df_exp['EndMass'] = df_exp['IsolationMz'] + (df_exp['IsolationWidth'] / 2)
        for _, r in df_exp.sort_values(by=['CycleId', 'OneOverK0Start']).iterrows():
            if r['Type'] == 0: lines.append(f"MS1,{int(r['CycleId'])},-,-,-,-,-")
            elif r['Type'] == 1: lines.append(f"PASEF,{int(r['CycleId'])},{r['OneOverK0Start']:.4f},{r['OneOverK0End']:.4f},{r['StartMass']:.2f},{r['EndMass']:.2f},-")
        return "\n".join(lines)

    def _convert_diagonal_spec_to_parameters(self, diag_params: Dict, seg_params: Dict) -> str:
        if not diag_params: return ""
        p = diag_params
        try: start_im, end_im = float(seg_params.get("calc_im_start", 0)), float(seg_params.get("calc_im_end", 0))
        except (ValueError, TypeError): start_im, end_im = 0.0, 0.0
        lines = ["type, mobility pos.1 [1/K0], mass pos.1 start [m/z], mass pos.1 end [m/z], mobility pos.2 [1/K0], mass pos.2 start [m/z]"]
        for _ in range(int(p.get('insert_ms_scan', 0))): lines.append("ms,-,-,-,-,-")
        if p.get('slope', 0) == 0: return ""
        num, iso_mz = int(p.get('number_of_slices', 0)), p.get('isolation_mz', 0.0)
        c_mz1, c_mz2 = (start_im - p['origin']) / p['slope'], (end_im - p['origin']) / p['slope']
        p_start1, p_start2 = c_mz1 - (p['width_mz'] / 2), c_mz2 - (p['width_mz'] / 2)
        step = p['width_mz'] / num if num > 0 else 0
        for i in range(num):
            m1_start, m2_start = p_start1 + i * step, p_start2 + i * step
            lines.append(f"diagonal,{start_im:.2f},{m1_start:.2f},{m1_start + iso_mz:.2f},{end_im:.2f},{m2_start:.2f}")
        return "\n".join(lines)

    def _convert_pasef_polygon_to_text(self, polygon_data: tuple) -> str:
        if not polygon_data: return ""
        mass, mobility = polygon_data
        return "Mass [m/z],Mobility [1/K0]\n" + "\n".join(f"{m:.4f},{im:.4f}" for m, im in zip(mass, mobility))
        
    def _show_add_menu(self):
        self.add_menu.tk_popup(self.add_menu_button.winfo_rootx(), self.add_menu_button.winfo_rooty() + self.add_menu_button.winfo_height())
    
    def _update_remove_menu(self):
        self.dropdown_name_map.clear()
        if not self.datasets:
            self.remove_menu.configure(values=["-"]); self.remove_var.set("-")
            return
        self.root.update_idletasks()
        max_width = self.remove_menu.winfo_width() - 30
        display_names = []
        for d in self.datasets:
            trunc_name, count = self._truncate_text(d.display_name, max_width, self.optionmenu_font), 2
            original_trunc = trunc_name
            while trunc_name in self.dropdown_name_map:
                trunc_name = f"{original_trunc.rsplit('...', 1)[0] if '...' in original_trunc else original_trunc} ({count})"
                count += 1
            display_names.append(trunc_name); self.dropdown_name_map[trunc_name] = d.display_name
        self.remove_menu.configure(values=display_names)
        current_full = self.dropdown_name_map.get(self.remove_var.get())
        if not current_full or current_full not in [d.display_name for d in self.datasets]:
            self.remove_var.set(display_names[0] if display_names else "-")
        else:
            for t, f in self.dropdown_name_map.items():
                if f == current_full: self.remove_var.set(t); break
            
    def _show_export_menu(self):
        self.export_menu.tk_popup(self.export_menu_button.winfo_rootx(), self.export_menu_button.winfo_rooty() + self.export_menu_button.winfo_height())

    def _open_report_generator_dialog(self):
        """Opens the dialog for generating a method report for the active dataset."""
        selected_name = self.remove_var.get()
        if not selected_name or selected_name == "-": return messagebox.showwarning("No Selection", "Please select a dataset to export.")
        dataset = next((d for d in self.datasets if d.display_name == self.dropdown_name_map.get(selected_name)), None)
        if not dataset or not dataset.segments: return
        
        from .report_generator_window import ReportGeneratorWindow

        initial_params = []
        default_keys = set()
        
        has_multisegment_file = len(dataset.segments) > 1
        has_advanced_ce = any(s.parameters.get("Energy_Ramping_Advanced_Settings_Active") == '1' for s in dataset.segments)
        has_standard_ce = any(s.parameters.get("Energy_Ramping_Advanced_Settings_Active") != '1' for s in dataset.segments)
        has_icc_mode1 = any(s.parameters.get("IMSICC_Mode") == '1' for s in dataset.segments)
        has_icc_mode2 = any(s.parameters.get("IMSICC_Mode") == '2' for s in dataset.segments)
        
        all_workflows_in_dataset = {s.workflow_name for s in dataset.segments if s.workflow_name}
        default_params_by_workflow = self.config.parameter_definitions

        all_param_names = []
        seen_param_permnames = set()

        def add_unique_params(pnames):
            for name in pnames:
                if name not in seen_param_permnames:
                    all_param_names.append(name)
                    seen_param_permnames.add(name)

        add_unique_params(default_params_by_workflow.get('__GENERAL__', []))
        for wf in all_workflows_in_dataset:
            add_unique_params(default_params_by_workflow.get(wf, []))
        
        # FIX: Explicitly prefer 'calc_scan_mode' over 'Mode_ScanMode'
        if "calc_scan_mode" in seen_param_permnames and "Mode_ScanMode" in seen_param_permnames:
            all_param_names.remove("Mode_ScanMode")
            seen_param_permnames.remove("Mode_ScanMode")

        for pname in all_param_names:
            if pname in ["calc_segment_start_time", "calc_segment_end_time"] and not has_multisegment_file:
                continue
            if pname in ["calc_ce_ramping_start", "calc_ce_ramping_end"] and not has_standard_ce:
                continue
            if pname == "calc_advanced_ce_ramping_display_list" and not has_advanced_ce:
                continue
            if pname == 'IMSICC_Target' and not has_icc_mode1:
                continue
            mode2_params = [
                "IMSICC_ICC2_MaxTicTargetPercent", 
                "IMSICC_ICC2_MinAccuTime", 
                "IMSICC_ICC2_ReferenceTicCapacity", 
                "IMSICC_ICC2_SmoothingFactor"
            ]
            if pname in mode2_params and not has_icc_mode2:
                continue

            param_config = next((p for p in self.config.all_definitions if p['permname'] == pname), None)
            
            if not param_config and pname.startswith("calc_"):
                label_map = {
                    "calc_scan_area_mz": "Window Scan Area",
                    "calc_ramps": "Ramps per Cycle",
                    "calc_ms1_scans": "MS1 Scans per Cycle",
                    "calc_steps": "Isolation Steps per Cycle",
                    "calc_mz_width": "Isolation Window Width",
                    "calc_ce_ramping_start": "CE Ramping Start",
                    "calc_ce_ramping_end": "CE Ramping End"
                }
                label = label_map.get(pname, pname.replace("calc_", "").replace("_", " ").title())
                category = "Mode" if "Scan Mode" in label else "Calculated Parameters"
                param_config = {"permname": pname, "label": label, "category": category}
            
            if param_config:
                initial_params.append(param_config)
                default_keys.add(self._get_param_key(param_config))

        for p in self.user_added_params:
            if self._get_param_key(p) not in default_keys:
                initial_params.append(p)

        all_additional_params = [
            p for p in dataset.available_optional_params 
            if self._get_param_key(p) not in default_keys
        ]

        ReportGeneratorWindow(
            master=self.root, 
            dataset=dataset, 
            initial_params=initial_params, 
            all_additional_params=all_additional_params, 
            report_service=self.report_generator, 
            loader_service=self.loader,
            plotting_service=self.plotter
        )
    
    def _load_icons(self):
        try:
            assets = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")
            self.add_data_icon = ctk.CTkImage(Image.open(os.path.join(assets, "add_folder.png")), size=(20, 16))
            self.add_params_icon = ctk.CTkImage(Image.open(os.path.join(assets, "add_params.png")), size=(20, 19))
            self.export_icon = ctk.CTkImage(Image.open(os.path.join(assets, "export.png")), size=(20, 20))
            self.diffs_checked_icon = ctk.CTkImage(Image.open(os.path.join(assets, "checkbox_checked_inv.png")), size=(22, 22))
            self.diffs_unchecked_icon = ctk.CTkImage(Image.open(os.path.join(assets, "checkbox_unchecked_inv.png")), size=(22, 22))
            self.plots_icon = ctk.CTkImage(Image.open(os.path.join(assets, "plots.png")), size=(14, 20))
            self.hide_icon = ctk.CTkImage(Image.open(os.path.join(assets, "hide.png")), size=(20, 19))
            self.remove_icon = ctk.CTkImage(Image.open(os.path.join(assets, "remove.png")), size=(20, 20))
            self.about_icon = ctk.CTkImage(Image.open(os.path.join(assets, "about.png")), size=(20, 20))
            self.reset_icon = ctk.CTkImage(Image.open(os.path.join(assets, "reset.png")), size=(20, 17))
        except FileNotFoundError as e: print(f"Warning: Could not load icon files. {e}")

    def _toggle_show_differences(self):
        new_state = not self.show_only_diffs_var.get()
        self.show_only_diffs_var.set(new_state)
        self.show_diffs_button.configure(image=self.diffs_checked_icon if new_state else self.diffs_unchecked_icon)
        self._update_treeview_data()

    def _show_about_dialog(self):
        messagebox.showinfo("About timsCompare", "timsCompare v1.0\n\nA tool for viewing and comparing Bruker .d method parameters.\n\nDeveloped with customtkinter and Python.\nFor support, please visit the project's GitHub page.", parent=self.root)