import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Any, Dict, Optional, List
from collections import defaultdict

import customtkinter as ctk

from data_model import Dataset
from services import ReportGeneratorService, DataLoaderService, PlottingService
from utils import format_parameter_value
from .parameter_selection import ParameterSelectionWindow
from PIL import Image, ImageDraw, ImageTk


class ReportGeneratorWindow(ctk.CTkToplevel):
    def __init__(self, master, dataset: Dataset, initial_params: List[Dict],
                 all_additional_params: List[Dict], report_service: ReportGeneratorService,
                 loader_service: DataLoaderService, plotting_service: PlottingService):
        super().__init__(master)
        self.transient(master)
        self.grab_set()
        self.title(f"Method Report for {dataset.display_name}")
        self.geometry("950x700")

        # --- Injected Dependencies & State ---
        self.dataset = dataset
        self.is_multisegment = len(dataset.segments) > 1
        self.all_additional_params = all_additional_params
        self.report_service = report_service
        self.loader_service = loader_service
        self.plotting_service = plotting_service
        self.current_params = initial_params

        # --- UI Widgets & State ---
        self.tree: Optional[ttk.Treeview] = None
        self.export_format_var = ctk.StringVar(value="PDF")
        self.show_filename_var = tk.BooleanVar(value=True)
        self.include_plot_var = tk.BooleanVar(value=True)
        
        self.show_filename_button: Optional[ctk.CTkButton] = None
        self.include_plot_button: Optional[ctk.CTkButton] = None

        # --- State for segment selection ---
        self.segment_selection_vars: Dict[int, tk.BooleanVar] = {
            i: tk.BooleanVar(value=True) for i in range(len(self.dataset.segments))
        }
        self.segment_buttons: Dict[int, ctk.CTkButton] = {}

        # --- Checkbox & Drag State ---
        self.drag_data = {"iid": None, "y": 0}
        self.param_enabled_vars: Dict[str, tk.BooleanVar] = {
            self._get_param_key(p): tk.BooleanVar(value=True) for p in self.current_params
        }

        # --- Load Images ---
        self._load_images()

        self._create_widgets()
        self._update_parameter_list()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _load_images(self):
        """Loads all necessary images from the assets folder."""
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
        
        # Dynamically configure the correct row to expand and fill space
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
                    segment_frame,
                    text=label,
                    image=self.checked_inv_icon,
                    fg_color="transparent",
                    hover=False,
                    command=lambda index=i: self._toggle_segment_selection(index)
                )
                button.pack(side="left", padx=5)
                self.segment_buttons[i] = button

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
        
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=vsb.set)
        
        self.tree.tag_configure('oddrow', background='#E4EFF7'); self.tree.tag_configure('evenrow', background='#FFFFFF')
        self.tree.tag_configure('dragging', font=('TkDefaultFont', 9, 'bold'))
        self.tree.bind("<ButtonPress-1>", self._on_drag_press); self.tree.bind("<B1-Motion>", self._on_drag_motion); self.tree.bind("<ButtonRelease-1>", self._on_drag_release)

        # Reorganized bottom controls for better UI/UX
        bottom_controls_row = tree_view_row + 1
        controls_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        controls_frame.grid(row=bottom_controls_row, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        controls_frame.grid_columnconfigure(1, weight=1)

        # Left-aligned controls
        left_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        left_frame.grid(row=0, column=0, sticky="w")
        ctk.CTkButton(left_frame, text="Add Parameters...", command=self._add_parameters).pack(side="left")

        # Center-aligned controls
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

        # Right-aligned controls
        right_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        right_frame.grid(row=0, column=2, sticky="e")
        format_toggle = ctk.CTkSegmentedButton(right_frame, values=["PDF", "CSV"], variable=self.export_format_var)
        format_toggle.pack(side="left", padx=(0, 10))
        generate_button = ctk.CTkButton(right_frame, text="Generate Report", command=self._export_report)
        generate_button.pack(side="left")

    def _toggle_segment_selection(self, index: int):
        """Toggles the state of a segment's selection variable and updates its button icon."""
        var = self.segment_selection_vars.get(index)
        if var:
            new_state = not var.get()
            var.set(new_state)
            button = self.segment_buttons.get(index)
            if button:
                self._update_button_icon(button, new_state)

    def _toggle_filename_include(self):
        """Toggles the state of the show_filename_var and updates the button icon."""
        new_state = not self.show_filename_var.get()
        self.show_filename_var.set(new_state)
        self._update_button_icon(self.show_filename_button, new_state)

    def _toggle_plot_include(self):
        """Toggles the state of the include_plot_var and updates the button icon."""
        new_state = not self.include_plot_var.get()
        self.include_plot_var.set(new_state)
        self._update_button_icon(self.include_plot_button, new_state)

    def _update_button_icon(self, button: ctk.CTkButton, is_checked: bool):
        """Updates the icon of a toggle button based on its state."""
        if self.checked_inv_icon and self.unchecked_inv_icon:
            button.configure(image=self.checked_inv_icon if is_checked else self.unchecked_inv_icon)

    def _is_plot_available(self, segment_index: int) -> bool:
        """Checks if a plot can be generated for a specific segment."""
        try:
            segment = self.dataset.segments[segment_index]
            scan_mode_id = segment.scan_mode_id
            # --- MODIFIED: Use numeric scan_mode_id for logic ---
            if scan_mode_id == 9 and segment.dia_windows_data is not None: return True
            if scan_mode_id == 11 and segment.diagonal_pasef_data is not None: return True
            if scan_mode_id == 6 and segment.pasef_polygon_data: return True
        except IndexError:
            return False
        return False
        
    def _update_parameter_list(self):
        """Filters and redraws the treeview list with parameters grouped by category."""
        self.tree.delete(*self.tree.get_children())
        self.tree.tag_configure('category_header', font=('TkDefaultFont', 9, 'bold'))

        grouped_params = defaultdict(list)
        for p_config in self.current_params:
            grouped_params[p_config.get("category", "General")].append(p_config)

        def sort_key(g):
            if g == "Mode": return (0, g)
            if g == "Calculated Parameters": return (2, g)
            return (1, g)
        sorted_groups = sorted(grouped_params.keys(), key=sort_key)
        
        top_level_row_index = 0
        for group_name in sorted_groups:
            group_iid = self.tree.insert("", "end", text=group_name, open=True, tags=('category_header',))
            
            # --- MODIFIED: Removed alphabetical sort to preserve the original order ---
            params_in_group = grouped_params[group_name]
            
            for p_config in params_in_group:
                param_key = self._get_param_key(p_config)
                param_label = p_config.get('label', p_config['permname'])
                is_enabled = self.param_enabled_vars.get(param_key, tk.BooleanVar(value=True)).get()
                image = self.checked_img if is_enabled else self.unchecked_img
                tag = 'evenrow' if top_level_row_index % 2 == 0 else 'oddrow'
                
                values = []
                for i in range(len(self.dataset.segments)):
                    original_index = self.dataset.active_segment_index
                    self.dataset.active_segment_index = i
                    raw_val = self.dataset.get_parameter_value(p_config['permname'])
                    values.append(format_parameter_value(raw_val, p_config))
                    self.dataset.active_segment_index = original_index
                
                display_values = tuple(values) if self.is_multisegment else (values[0],)
                
                self.tree.insert(group_iid, "end", iid=param_key, text=f" {param_label}", image=image,
                                 values=display_values, tags=(tag,))
                top_level_row_index += 1

    def _insert_row(self, param_config: Dict, values: tuple, index: int):
        """Inserts a single parameter row into the treeview."""
        param_key = self._get_param_key(param_config)
        param_label = param_config.get('label', param_config['permname'])
        
        is_enabled = self.param_enabled_vars.get(param_key, tk.BooleanVar(value=True)).get()
        image = self.checked_img if is_enabled else self.unchecked_img
        tag = 'evenrow' if index % 2 == 0 else 'oddrow'

        self.tree.insert("", "end", iid=param_key, text=f" {param_label}", image=image,
                         values=values, tags=(tag,))

    def _export_report(self):
        """Gathers selections and passes them to the report service."""
        export_format = self.export_format_var.get().lower()
        ext = "." + export_format
        base_name = os.path.splitext(self.dataset.display_name)[0]
        filename = f"{base_name}_MethodReport{ext}"
        
        file_path = filedialog.asksaveasfilename(
            parent=self, initialfile=filename, defaultextension=ext,
            filetypes=[(f"{export_format.upper()} files", f"*{ext}"), ("All files", "*.*")]
        )
        if not file_path: return

        try:
            param_map = {self._get_param_key(p): p for p in self.current_params}
            
            # --- FIXED: Traverse the grouped tree to get all parameter keys in order ---
            ordered_param_keys = []
            for group_iid in self.tree.get_children(''):
                for param_iid in self.tree.get_children(group_iid):
                    ordered_param_keys.append(param_iid)
            # --------------------------------------------------------------------

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

            self.report_service.generate_report(
                dataset=self.dataset,
                selected_segment_indices=selected_segment_indices,
                params_to_include=enabled_params,
                export_format=export_format,
                file_path=file_path,
                show_filename=self.show_filename_var.get(),
                include_plot=self.include_plot_var.get()
            )
            
            messagebox.showinfo("Success", f"Report successfully saved to:\n{file_path}", parent=self)
            self.destroy()
        except Exception as e:
            messagebox.showerror("Export Error", f"An error occurred during export:\n{e}", parent=self)
        
    def _get_param_key(self, param: Dict) -> str:
        """Creates a unique key for a parameter based on its identity properties."""
        return f"{param['permname']}|{param.get('polarity')}|{param.get('source')}"
    
    def _add_parameters(self):
        """Opens the parameter selection dialog, parses new data, and updates the list."""
        # Find parameters that are not part of the default set for this report
        additional_param_keys = {self._get_param_key(p) for p in self.all_additional_params}
        default_params = [p for p in self.current_params if self._get_param_key(p) not in additional_param_keys]
        
        # --- FIXED: Corrected arguments passed to ParameterSelectionWindow ---
        dialog = ParameterSelectionWindow(
            self,
            dataset=self.dataset,
            all_params=self.all_additional_params,
            previously_selected_params=self.current_params
        )
        # -----------------------------------------------------------------
        
        selected_additional_params = dialog.get_selection()

        if selected_additional_params is not None:
            # Determine which parameters are newly added to parse their values
            current_additional_keys = {self._get_param_key(p) for p in self.current_params if self._get_param_key(p) in additional_param_keys}
            new_additional_keys = {self._get_param_key(p) for p in selected_additional_params}
            newly_added_keys = new_additional_keys - current_additional_keys

            if newly_added_keys:
                newly_added_configs = [p for p in self.all_additional_params if self._get_param_key(p) in newly_added_keys]
                self.loader_service.parse_additional_parameters(self.dataset, newly_added_configs)

            # Rebuild the list of current parameters for display
            self.current_params = default_params + selected_additional_params
            self.param_enabled_vars.update({
                self._get_param_key(p): tk.BooleanVar(value=True) for p in selected_additional_params
            })
            self._update_parameter_list()
    
    def _on_drag_press(self, event: tk.Event):
        """Handles the start of a drag operation or a checkbox click."""
        iid = self.tree.identify_row(event.y)
        if not iid: return

        # --- ADDED: Prevent dragging category headers ---
        if 'category_header' in self.tree.item(iid, "tags"):
            return
        # ---------------------------------------------
        
        try:
            bbox = self.tree.bbox(iid, column='#0')
            if bbox and bbox[0] < event.x < bbox[0] + 40:
                current_state = self.param_enabled_vars[iid].get()
                self.param_enabled_vars[iid].set(not current_state)
                
                if self.checked_img:
                    self.tree.item(iid, image=self.checked_img if not current_state else self.unchecked_img)
                return 
        except Exception:
            pass

        current_tags = list(self.tree.item(iid, "tags"))
        if 'dragging' not in current_tags:
            current_tags.append('dragging')
            self.tree.item(iid, tags=tuple(current_tags))

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
        
        if dragged_iid:
            current_tags = list(self.tree.item(dragged_iid, "tags"))
            if 'dragging' in current_tags:
                current_tags.remove('dragging')
                self.tree.item(dragged_iid, tags=tuple(current_tags))

        if not dragged_iid: return

        drop_iid = self.tree.identify_row(event.y)
        if drop_iid and dragged_iid != drop_iid:
            self.tree.move(dragged_iid, '', self.tree.index(drop_iid))
            self._apply_zebra_striping()

        self.drag_data["iid"] = None
    
    def _apply_zebra_striping(self):
        for i, iid in enumerate(self.tree.get_children('')):
            tag = 'evenrow' if i % 2 == 0 else 'oddrow'
            current_tags = [t for t in list(self.tree.item(iid, 'tags')) if t not in ('evenrow', 'oddrow')]
            self.tree.item(iid, tags=(tag,) + tuple(current_tags))
    
    def _insert_standard_row(self, param_config: Dict, value: str, index: int):
        """Inserts a single, standard parameter row into the treeview."""
        param_key = self._get_param_key(param_config)
        param_label = param_config.get('label', param_config['permname'])
        
        # Determine which checkbox image to use based on the selection state.
        is_enabled = self.param_enabled_vars.get(param_key, tk.BooleanVar(value=True)).get()
        image = self.checked_img if is_enabled else self.unchecked_img

        # Apply zebra striping based on the row's index.
        tag = 'evenrow' if index % 2 == 0 else 'oddrow'

        self.tree.insert("", "end", iid=param_key, text=f" {param_label}", image=image,
                         values=(value,), tags=(tag,))
    
    def _insert_advanced_ce_rows(self, param_config: Dict, index: int):
        """
        Inserts a hierarchical set of rows for the advanced CE parameter:
        a selectable parent row followed by informational child rows.
        """
        param_key = self._get_param_key(param_config)
        param_label = param_config.get('label', param_config['permname'])

        is_enabled = self.param_enabled_vars.get(param_key, tk.BooleanVar(value=True)).get()
        image = self.checked_img if is_enabled else self.unchecked_img
        
        parent_tag = 'evenrow' if index % 2 == 0 else 'oddrow'

        # The parent row is inserted with a checkbox. Its value is the total count.
        adv_values = self.dataset.get_parameter_value("calc_advanced_ce_ramping_display_list")
        count = len(adv_values) if isinstance(adv_values, list) else 0
        
        parent_iid = self.tree.insert("", "end", iid=param_key, text=f" {param_label}", image=image,
                                      values=(f"List ({count} items)",), tags=(parent_tag,), open=True)

        # Insert child rows for each entry. These have no checkbox and are for display only.
        if count > 0:
            for i, value_str in enumerate(adv_values):
                # Children inherit the parent's background color. They are not selectable.
                self.tree.insert(parent_iid, "end", text=f"    ↳ Entry {i+1}", 
                                 values=(value_str,), tags=(parent_tag,))