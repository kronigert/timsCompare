# ui/report_generator_window.py

import os
import glob
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Any, Dict, Optional, List, Tuple
from collections import defaultdict
import logging

import customtkinter as ctk

from data_model import Dataset
from services import ReportGeneratorService, DataLoaderService, PlottingService
from utils import format_parameter_value, resource_path, apply_dark_title_bar
from .parameter_selection import ParameterSelectionWindow
from PIL import Image, ImageDraw, ImageTk


class ReportGeneratorWindow(ctk.CTkToplevel):
    def __init__(self, master, dataset: Dataset, initial_params: List[Dict],
                 all_additional_params: List[Dict], report_service: ReportGeneratorService,
                 loader_service: DataLoaderService, plotting_service: PlottingService):
        super().__init__(master)
        
        self.bind("<Map>", self._on_map)
        
        self.transient(master)
        self.grab_set()
        self.title(f"Method Report for {dataset.display_name}")
        self.geometry("950x700")

        self.dataset = dataset
        self.is_multisegment = len(dataset.segments) > 1
        self.all_additional_params = all_additional_params
        self.report_service = report_service
        self.loader_service = loader_service
        self.plotting_service = plotting_service
        self.current_params = initial_params

        self.tree: Optional[ttk.Treeview] = None
        self.export_format_var = ctk.StringVar(value="PDF")
        self.show_filename_var = tk.BooleanVar(value=True)
        self.include_plot_var = tk.BooleanVar(value=True)
        self.progress_text_var = ctk.StringVar(value="")
        
        self.interactive_widgets: List[tk.Widget] = []
        self.progress_frame: Optional[ctk.CTkFrame] = None
        self.progress_bar: Optional[ctk.CTkProgressBar] = None
        self.progress_label: Optional[ctk.CTkLabel] = None

        self.is_exporting = False
        self.current_progress = 0
        self.total_progress_steps = 0

        self.segment_selection_vars: Dict[int, tk.BooleanVar] = {
            i: tk.BooleanVar(value=True) for i in range(len(self.dataset.segments))
        }
        self.segment_buttons: Dict[int, ctk.CTkButton] = {}

        self.drag_data = {"iid": None, "y": 0}
        self.param_enabled_vars: Dict[str, tk.BooleanVar] = {
            self._get_param_key(p): tk.BooleanVar(value=True) for p in self.current_params
        }

        self._load_images()

        self._create_widgets()
        self._update_parameter_list()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        
    def _on_map(self, event=None):
        apply_dark_title_bar(self)

        def set_icon():
            try:
                icon_path = resource_path("assets/icon.ico")

                image = Image.open(icon_path)
                icon_image = ImageTk.PhotoImage(image)

                setattr(self.master, f"_icon_image_ref_{self.winfo_id()}", icon_image)

                self.iconphoto(False, icon_image)

            except Exception as e:
                logging.getLogger(__name__).warning(f"Could not set Toplevel window icon: {e}")

        self.after(100, set_icon)



    def _load_images(self):
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            assets_path = os.path.join(script_dir, "..", "assets")
            
            checked_pil_img = Image.open(os.path.join(assets_path, "checkbox_checked.png")).resize((20, 20), Image.Resampling.LANCZOS)
            unchecked_pil_img = Image.open(os.path.join(assets_path, "checkbox_unchecked.png")).resize((20, 20), Image.Resampling.LANCZOS)
            self.checked_img = ImageTk.PhotoImage(checked_pil_img)
            self.unchecked_img = ImageTk.PhotoImage(unchecked_pil_img)

            self.checked_inv_icon = ctk.CTkImage(Image.open(os.path.join(assets_path, "checkbox_checked_inv.png")), size=(22, 22))
            self.unchecked_inv_icon = ctk.CTkImage(Image.open(os.path.join(assets_path, "checkbox_unchecked_inv.png")), size=(22, 22))

        except FileNotFoundError:
            print("Warning: Some image files not found in assets folder.")
            self.checked_img = self.unchecked_img = None
            self.checked_inv_icon = self.unchecked_inv_icon = None

    def _create_widgets(self):
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(padx=10, pady=10, fill="both", expand=True)
        main_frame.grid_columnconfigure(0, weight=1)
        
        tree_view_row = 1 if self.is_multisegment else 0
        main_frame.grid_rowconfigure(tree_view_row, weight=1)
        
        if self.is_multisegment:
            options_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
            options_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))

            segment_frame = ctk.CTkFrame(options_frame)
            segment_frame.pack(side="top", fill="x", expand=True, pady=(0, 10))
            ctk.CTkLabel(segment_frame, text="Segments to Include:", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(5, 15))
            for i, seg in enumerate(self.dataset.segments):
                label = f"Segment {i+1} ({seg.start_time:.1f}-{seg.end_time_display})"
                button = ctk.CTkButton(
                    segment_frame, text=label, image=self.checked_inv_icon,
                    fg_color="transparent", hover=False,
                    command=lambda index=i: self._toggle_segment_selection(index)
                )
                button.pack(side="left", padx=5)
                self.segment_buttons[i] = button
                self.interactive_widgets.append(button)

        tree_frame = ctk.CTkFrame(main_frame)
        tree_frame.grid(row=tree_view_row, column=0, columnspan=2, sticky="nsew")
        tree_frame.grid_columnconfigure(0, weight=1)
        tree_frame.grid_rowconfigure(0, weight=1)

        columns = tuple(f"Segment {i+1}" for i in range(len(self.dataset.segments))) if self.is_multisegment else ('Value',)
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="tree headings")
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.heading('#0', text='Parameter'); self.tree.column('#0', width=350, anchor='w')
        for col_name in columns:
            self.tree.heading(col_name, text=col_name); self.tree.column(col_name, width=150, anchor='w')
        
        vsb = ctk.CTkScrollbar(tree_frame, command=self.tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=vsb.set)
        
        self.tree.tag_configure('oddrow', background='#E4EFF7'); self.tree.tag_configure('evenrow', background='#FFFFFF')
        self.tree.tag_configure('category_header', font=('TkDefaultFont', 9, 'bold'))
        self.tree.bind("<ButtonPress-1>", self._on_drag_press); self.tree.bind("<B1-Motion>", self._on_drag_motion); self.tree.bind("<ButtonRelease-1>", self._on_drag_release)

        bottom_controls_row = tree_view_row + 1
        controls_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        controls_frame.grid(row=bottom_controls_row, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        controls_frame.grid_columnconfigure(1, weight=1)

        left_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        left_frame.grid(row=0, column=0, sticky="w")
        
        add_params_button = ctk.CTkButton(left_frame, text="Add Parameters...", command=self._add_parameters)
        add_params_button.pack(side="left", padx=(0, 5))

        self.default_params_button = ctk.CTkButton(left_frame, text="Default Parameters", command=self._reset_to_default_parameters)
        self.default_params_button.pack(side="left")

        center_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        center_frame.grid(row=0, column=1, sticky="e")
        self.show_filename_button = ctk.CTkButton(center_frame, text="Include Filename", image=self.checked_inv_icon,
                                                  command=self._toggle_filename_include, fg_color="transparent", hover=False)
        self.show_filename_button.pack(side="left", padx=10)
        self.include_plot_button = ctk.CTkButton(center_frame, text="Include Plot(s)", image=self.checked_inv_icon,
                                                 command=self._toggle_plot_include, fg_color="transparent", hover=False)
        self.include_plot_button.pack(side="left", padx=10)
        
        if not any(self._is_plot_available(i) for i in range(len(self.dataset.segments))):
            self.include_plot_button.configure(state=tk.DISABLED)
            self.include_plot_var.set(False)
            self._update_button_icon(self.include_plot_button, False)

        right_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        right_frame.grid(row=0, column=2, sticky="e")
        format_toggle = ctk.CTkSegmentedButton(right_frame, values=["PDF", "CSV"], variable=self.export_format_var)
        format_toggle.pack(side="left", padx=(0, 10))
        
        self.generate_button = ctk.CTkButton(right_frame, text="Generate Report", command=self._export_report)
        self.generate_button.pack(side="left")

        self.interactive_widgets.extend([
            add_params_button, self.default_params_button, self.show_filename_button, 
            self.include_plot_button, format_toggle, self.generate_button, self.tree
        ])

        progress_frame_row = bottom_controls_row + 1
        self.progress_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        self.progress_frame.grid(row=progress_frame_row, column=0, columnspan=2, sticky="ew", pady=(10,0))
        self.progress_frame.grid_columnconfigure(0, minsize=200) 
        self.progress_frame.grid_columnconfigure(1, weight=1) 
        self.progress_frame.grid_remove() 

        button_text_color = ctk.ThemeManager.theme["CTkButton"]["text_color"]
        self.progress_label = ctk.CTkLabel(self.progress_frame, 
                                           textvariable=self.progress_text_var, 
                                           text_color=button_text_color, 
                                           anchor="w")
        self.progress_label.grid(row=0, column=0, sticky="w", padx=(0, 10))

        self.progress_bar = ctk.CTkProgressBar(self.progress_frame)
        self.progress_bar.grid(row=0, column=1, sticky="ew")

    def _reset_to_default_parameters(self):
        default_params = self.loader_service.get_default_parameters_for_dataset(self.dataset)
        
        self.current_params = default_params
        
        self.param_enabled_vars = {
            self._get_param_key(p): tk.BooleanVar(value=True) for p in self.current_params
        }
        
        self._update_parameter_list()

    def _toggle_ui_interactive_state(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        for widget in self.interactive_widgets:
            if isinstance(widget, ttk.Treeview):
                if not enabled:
                    widget.unbind("<ButtonPress-1>")
                    widget.unbind("<B1-Motion>")
                    widget.unbind("<ButtonRelease-1>")
                else:
                    widget.bind("<ButtonPress-1>", self._on_drag_press)
                    widget.bind("<B1-Motion>", self._on_drag_motion)
                    widget.bind("<ButtonRelease-1>", self._on_drag_release)
            else:
                widget.configure(state=state)
        for button in self.segment_buttons.values():
            button.configure(state=state)

    def _update_progress(self, step_increment: int, message: str):
        if not self.winfo_exists():
            return

        def task():
            self.current_progress += step_increment
            progress_value = min(1.0, self.current_progress / self.total_progress_steps)
            
            if self.progress_bar and self.progress_bar.winfo_exists():
                self.progress_bar.set(progress_value)
            
            if self.progress_text_var:
                self.progress_text_var.set(message)

        self.after(0, task)

    def _export_report(self):
        export_format = self.export_format_var.get().lower()
        ext = "." + export_format
        base_name = os.path.splitext(self.dataset.display_name)[0]
        filename = f"{base_name}_MethodReport{ext}"
        
        file_path = filedialog.asksaveasfilename(
            parent=self, initialfile=filename, defaultextension=ext,
            filetypes=[(f"{export_format.upper()} files", f"*{ext}"), ("All files", "*.*")]
        )
        if not file_path: return

        param_map = {self._get_param_key(p): p for p in self.current_params}
        
        ordered_param_keys = []
        for group_iid in self.tree.get_children(''):
            for param_iid in self.tree.get_children(group_iid):
                ordered_param_keys.append(param_iid)

        enabled_params = [
            param_map[key] for key in ordered_param_keys
            if key in self.param_enabled_vars and self.param_enabled_vars[key].get() and key in param_map
        ]

        if not enabled_params:
            messagebox.showwarning("No Parameters Selected", "Please select at least one parameter to include.", parent=self)
            return

        selected_segment_indices = [i for i, var in self.segment_selection_vars.items() if var.get()]
        if self.is_multisegment and not selected_segment_indices:
            messagebox.showwarning("No Segments Selected", "Please select at least one segment to export.", parent=self)
            return

        self.current_progress = 0
        self.total_progress_steps = 1 
        for _ in selected_segment_indices:
            self.total_progress_steps += 1 
            if self.include_plot_var.get() and self.export_format_var.get() == 'PDF':
                self.total_progress_steps += 1 
        self.total_progress_steps += 1 

        self.is_exporting = True
        self._toggle_ui_interactive_state(enabled=False)
        
        self.progress_text_var.set("Starting export...") 
        self.progress_bar.configure(mode="determinate")
        self.progress_bar.set(0)
        
        self.progress_frame.grid()
        self.update_idletasks()

        export_thread = threading.Thread(
            target=self._run_export_in_thread,
            args=(
                file_path,
                selected_segment_indices,
                enabled_params,
                export_format,
                self.show_filename_var.get(),
                self.include_plot_var.get()
            )
        )
        export_thread.start()

    def _run_export_in_thread(self, file_path, selected_indices, params, export_format, show_filename, include_plot):
        try:
            self.report_service.generate_report(
                dataset=self.dataset,
                selected_segment_indices=selected_indices,
                params_to_include=params,
                export_format=export_format,
                file_path=file_path,
                show_filename=show_filename,
                include_plot=include_plot,
                progress_callback=self._update_progress
            )
            result = ("Success", f"Report successfully saved to:\n{file_path}")
        except Exception as e:
            result = ("Error", f"An error occurred during export:\n{e}")
        
        if self.winfo_exists():
            self.after(0, self._on_export_complete, result)

    def _on_export_complete(self, result: Tuple[str, str]):
        self.is_exporting = False
        self.progress_bar.set(1)
        self.progress_frame.grid_remove()
        self._toggle_ui_interactive_state(enabled=True)

        status, message = result
        if status == "Success":
            messagebox.showinfo("Success", message, parent=self)
            self.destroy()
        else:
            messagebox.showerror("Export Error", message, parent=self)

    def _on_close(self):
        if self.is_exporting:
            messagebox.showwarning("Export in Progress", "Please wait for the current export to finish.", parent=self)
        else:
            self.destroy()

    def _update_parameter_list(self):
        self.tree.delete(*self.tree.get_children())
        self.tree.tag_configure('category_header', font=('TkDefaultFont', 9, 'bold'))
        grouped_params = defaultdict(list)
        for p_config in self.current_params:
            grouped_params[p_config.get("category", "General")].append(p_config)
        def sort_key(g):
            if g == "General": return (0, g)
            if g == "Mode": return (1, g) 
            if g == "Calculated Parameters": return (99, g) 
            return (2, g)
        sorted_groups = sorted(grouped_params.keys(), key=sort_key)

        default_params_for_sorting = self.loader_service.get_default_parameters_for_dataset(self.dataset)
        order_map = {p['permname']: i for i, p in enumerate(default_params_for_sorting)}
 
        
        for group_name in sorted_groups:
            group_iid = self.tree.insert("", "end", text=group_name, open=True, tags=('category_header',))
            params_in_group = sorted(
                grouped_params[group_name],
                key=lambda p: (order_map.get(p['permname'], float('inf')), p.get('label', ''))
            )
            for p_config in params_in_group:
                param_key = self._get_param_key(p_config)
                param_label = p_config.get('label', p_config['permname'])
                is_enabled = self.param_enabled_vars.get(param_key, tk.BooleanVar(value=True)).get()
                image = self.checked_img if is_enabled else self.unchecked_img
                
                permname = p_config['permname']
                values = []

                if permname == "calc_instrument_model":
                    val = self.dataset.instrument_model or "N/A"
                    if val == "Unknown": val = "N/A"
                    values = [val] * len(self.dataset.segments)
                elif permname == "calc_tims_control_version":
                    val = self.dataset.tims_control_version or "N/A"
                    values = [val] * len(self.dataset.segments)
                elif permname == "calc_last_modified_date":
                    val = self.dataset.last_modified_date or "N/A"
                    try:
                        formatted_val = val.split('T')[0] if 'T' in val else val
                    except:
                        formatted_val = val
                    values = [formatted_val] * len(self.dataset.segments)
                else:
                    for i in range(len(self.dataset.segments)):
                        original_index = self.dataset.active_segment_index
                        self.dataset.active_segment_index = i
                        raw_val = self.dataset.get_parameter_value(p_config['permname'])
                        values.append(format_parameter_value(raw_val, p_config))
                        self.dataset.active_segment_index = original_index
                
                display_values = tuple(values) if self.is_multisegment else (values[0],)
                
                self.tree.insert(group_iid, "end", iid=param_key, text=f" {param_label}", image=image,
                                 values=display_values)
        self._apply_zebra_striping()

    def _toggle_segment_selection(self, index: int):
        var = self.segment_selection_vars.get(index)
        if var:
            new_state = not var.get()
            var.set(new_state)
            button = self.segment_buttons.get(index)
            if button: self._update_button_icon(button, new_state)
    def _toggle_filename_include(self):
        new_state = not self.show_filename_var.get()
        self.show_filename_var.set(new_state)
        self._update_button_icon(self.show_filename_button, new_state)
    def _toggle_plot_include(self):
        new_state = not self.include_plot_var.get()
        self.include_plot_var.set(new_state)
        self._update_button_icon(self.include_plot_button, new_state)
    def _update_button_icon(self, button: ctk.CTkButton, is_checked: bool):
        if self.checked_inv_icon and self.unchecked_inv_icon:
            button.configure(image=self.checked_inv_icon if is_checked else self.unchecked_inv_icon)
    def _is_plot_available(self, segment_index: int) -> bool:
        try:
            segment = self.dataset.segments[segment_index]
            scan_mode_id = segment.scan_mode_id
            if scan_mode_id == 9 and segment.dia_windows_data is not None: return True
            if scan_mode_id == 11 and segment.diagonal_pasef_data is not None: return True
            if scan_mode_id == 6 and segment.pasef_polygon_data: return True
        except IndexError: return False
        return False
    def _get_param_key(self, param: Dict) -> str:
        return f"{param['permname']}|{param.get('polarity')}|{param.get('source')}"
    def _add_parameters(self):
        all_possible_params = self.current_params + self.all_additional_params
        
        seen_keys = set()
        unique_params = []
        for p in all_possible_params:
            key = self._get_param_key(p)
            if key not in seen_keys:
                seen_keys.add(key)
                unique_params.append(p)

        dialog = ParameterSelectionWindow(
            self,
            loader_service=self.loader_service,
            dataset=self.dataset,
            all_params=unique_params,
            all_sources=self.dataset.available_sources,
            previously_selected_params=self.current_params,
            last_used_source=None 
        )
        
        dialog_result = dialog.get_selection()
        
        if dialog_result is not None:
            new_selection, selected_source = dialog_result

            if selected_source:
                self.loader_service.parse_additional_parameters(self.dataset, new_selection, ion_source=selected_source)

            self.current_params = new_selection
            
            self.param_enabled_vars = {
                self._get_param_key(p): tk.BooleanVar(value=True) for p in self.current_params
            }
            
            self._update_parameter_list()
    
    def _on_drag_press(self, event: tk.Event):
        iid = self.tree.identify_row(event.y)
        if not iid: return

        is_category_header = 'category_header' in self.tree.item(iid, "tags")

        if not is_category_header:
            try:
                bbox = self.tree.bbox(iid, column='#0')
                if bbox and bbox[0] < event.x < bbox[0] + 40:
                    current_state = self.param_enabled_vars[iid].get()
                    self.param_enabled_vars[iid].set(not current_state)
                    if self.checked_img:
                        self.tree.item(iid, image=self.checked_img if not current_state else self.unchecked_img)
            except Exception:
                pass
            return 

        self.tree.config(cursor="fleur")
        self.drag_data["iid"] = iid
        self.drag_data["y"] = event.y

    def _on_drag_motion(self, event: tk.Event):
        if self.drag_data["iid"]:
            iid_over = self.tree.identify_row(event.y)
            if iid_over: self.tree.selection_set(iid_over)

    def _on_drag_release(self, event: tk.Event):
        self.tree.config(cursor="")
        dragged_iid = self.drag_data["iid"]
        if not dragged_iid:
            self.drag_data["iid"] = None
            return

        drop_iid = self.tree.identify_row(event.y)

        if drop_iid and dragged_iid != drop_iid:
            drop_parent_iid = self.tree.parent(drop_iid)
            target_drop_iid = drop_iid if drop_parent_iid == '' else drop_parent_iid

            if target_drop_iid != dragged_iid:
                self.tree.move(dragged_iid, '', self.tree.index(target_drop_iid))
                self._apply_zebra_striping()

        self.drag_data["iid"] = None
    
    def _apply_zebra_striping(self):
        row_index = 0
        for group_iid in self.tree.get_children(''):
            for param_iid in self.tree.get_children(group_iid):
                tag = 'evenrow' if row_index % 2 == 0 else 'oddrow'
                current_tags = [t for t in self.tree.item(param_iid, 'tags') if t not in ('evenrow', 'oddrow')]
                current_tags.insert(0, tag)
                self.tree.item(param_iid, tags=tuple(current_tags))
                row_index += 1