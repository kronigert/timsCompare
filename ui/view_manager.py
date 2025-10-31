# ui/view_manager.py

import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk
from typing import Optional, List, Dict, Set
import logging
import copy
import os
from collections import defaultdict 

from app_config import AppConfig
from services import DataLoaderService
from utils import resource_path, apply_dark_title_bar
from PIL import Image, ImageTk

class ViewManager(ctk.CTkToplevel):
    def __init__(self, master, config: AppConfig, loader_service: DataLoaderService):
        super().__init__(master)

        self.logger = logging.getLogger(__name__)
        self.config = config
        self.loader_service = loader_service

        self.current_view_definitions = copy.deepcopy(self.config.parameter_definitions)
        self.all_params_list = self.config.all_definitions
        self.available_workflows = sorted([wf for wf in self.current_view_definitions.keys() if wf != "__GENERAL__"])

        self.workflow_display_map = {"General": "__GENERAL__"}
        self.workflow_display_map.update({wf: wf for wf in self.available_workflows})
        self.workflow_display_names = ["General"] + self.available_workflows

        self.calc_param_details_map = {
            "calc_instrument_model": "Instrument Model",
            "calc_tims_control_version": "timsControl Version",
            "calc_last_modified_date": "Last Modified",
            "calc_segment_start_time": "Segment Start",
            "calc_segment_end_time": "Segment End",
            "calc_scan_mode": "Scan Mode",
            "calc_cycle_time": "Cycle Time",
            "calc_scan_area_mz": "Window Scan Area",
            "calc_ramps": "Ramps per Cycle",
            "calc_ms1_scans": "MS1 Scans per Cycle",
            "calc_steps": "Isolation Steps per Cycle",
            "calc_mz_width": "Isolation Window Width",
            "calc_ce_ramping_start": "CE Ramping Start",
            "calc_ce_ramping_end": "CE Ramping End",
            "calc_msms_stepping_display_list": "MS/MS Stepping Details",
            "calc_advanced_ce_ramping_display_list": "Advanced CE Ramping"
        }

        self.selected_workflow_display_var = ctk.StringVar(value="General") 

        self.all_categories = sorted(list(set(p.get('category', 'General') for p in self.all_params_list)))
        self.selected_category_var = ctk.StringVar(value="All")

        self.available_list: Optional[tk.Listbox] = None
        self.current_list: Optional[tk.Listbox] = None
        self.workflow_selector: Optional[ctk.CTkOptionMenu] = None
        self.category_filter_menu: Optional[ctk.CTkOptionMenu] = None 
        self.search_var = ctk.StringVar()

        self._available_map: Dict[int, str] = {} 
        self._current_map: Dict[int, str] = {}   

        self.title("Manage Default Parameter Views")
        self.geometry("900x650") 
        self.transient(master)
        self.grab_set()
        self.bind("<Map>", self._on_map)

        self._create_widgets()
        self._populate_lists()

    def _on_map(self, event=None):
        apply_dark_title_bar(self)
        self.after(100, self._set_icon)

    def _set_icon(self):
         try:
             icon_path = resource_path("assets/icon.ico")
             image = Image.open(icon_path)
             icon_image = ImageTk.PhotoImage(image)
             setattr(self.master, f"_icon_image_ref_{self.winfo_id()}", icon_image)
             self.iconphoto(False, icon_image)
         except Exception as e:
             self.logger.warning(f"Could not set ViewManager window icon: {e}")

    def _create_widgets(self):
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(padx=10, pady=10, fill="both", expand=True)
        main_frame.grid_columnconfigure(0, weight=1) 
        main_frame.grid_columnconfigure(1, weight=0) 
        main_frame.grid_columnconfigure(2, weight=1) 
        main_frame.grid_rowconfigure(3, weight=1)

        intro_label = ctk.CTkLabel(main_frame,
                                   text="Configure the default parameters shown when the application starts for each measuring mode.", text_color="#E4EFF7",
                                   wraplength=850, justify="left")
        intro_label.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 15))

        top_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        top_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        top_frame.grid_columnconfigure(5, weight=1)

        ctk.CTkLabel(top_frame, text="Scan Mode:", text_color="#E4EFF7").grid(row=0, column=0, padx=(0, 5), pady=5, sticky="w")
        self.workflow_selector = ctk.CTkOptionMenu(
            top_frame,
            values=self.workflow_display_names,
            variable=self.selected_workflow_display_var,
            command=self._on_workflow_change
        )
        self.workflow_selector.grid(row=0, column=1, padx=(0, 20), pady=5, sticky="w")

        ctk.CTkLabel(top_frame, text="Group:", text_color="#E4EFF7").grid(row=0, column=2, padx=(20, 5), pady=5, sticky="w")
        self.category_filter_menu = ctk.CTkOptionMenu(
            top_frame,
            values=["All"] + self.all_categories,
            variable=self.selected_category_var,
            command=self._populate_lists
        )
        self.category_filter_menu.grid(row=0, column=3, padx=(0, 20), pady=5, sticky="w")

        ctk.CTkLabel(top_frame, text="Search:", text_color="#E4EFF7").grid(row=0, column=4, padx=(20, 5), pady=5, sticky="w")
        search_entry = ctk.CTkEntry(top_frame, textvariable=self.search_var)
        search_entry.grid(row=0, column=5, pady=5, sticky="ew")
        self.search_var.trace_add("write", lambda *args: self._populate_lists())

        ctk.CTkLabel(main_frame, text="Available Parameters", font=ctk.CTkFont(weight="bold"), text_color="#E4EFF7").grid(row=2, column=0, pady=(5,0), sticky="w", padx=5) 
        ctk.CTkLabel(main_frame, text="Default View Parameters", font=ctk.CTkFont(weight="bold"), text_color="#E4EFF7").grid(row=2, column=2, pady=(5,0), sticky="w", padx=5) 

        list_frame_left = ctk.CTkFrame(main_frame)
        list_frame_left.grid(row=3, column=0, sticky="nsew", padx=(0, 5))
        list_frame_left.grid_rowconfigure(0, weight=1)
        list_frame_left.grid_columnconfigure(0, weight=1)

        self.available_list = tk.Listbox(list_frame_left, selectmode="extended", exportselection=False,
                                         bg="#FFFFFF", fg="#04304D", selectbackground="#0071BC", selectforeground="white",
                                         highlightthickness=1, highlightbackground="#ACACAC", borderwidth=0, activestyle='none')
        self.available_list.grid(row=0, column=0, sticky="nsew", padx=(1,0), pady=1)

        av_scroll = ctk.CTkScrollbar(master=list_frame_left, command=self.available_list.yview)
        av_scroll.grid(row=0, column=1, sticky="ns", padx=(0,1))
        self.available_list.configure(yscrollcommand=av_scroll.set)
        self.available_list.bind("<Double-Button-1>", lambda e: self._add_selected())

        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.grid(row=3, column=1, padx=10, pady=20, sticky="ns")
        btn_width = 35
        add_button = ctk.CTkButton(button_frame, text=">", width=btn_width, command=self._add_selected)
        add_button.pack(pady=5)
        remove_button = ctk.CTkButton(button_frame, text="<", width=btn_width, command=self._remove_selected)
        remove_button.pack(pady=5)
        move_up_button = ctk.CTkButton(button_frame, text="▲", width=btn_width, command=lambda: self._move_item(-1))
        move_up_button.pack(pady=(20, 5))
        move_down_button = ctk.CTkButton(button_frame, text="▼", width=btn_width, command=lambda: self._move_item(1))
        move_down_button.pack(pady=5)

        list_frame_right = ctk.CTkFrame(main_frame)
        list_frame_right.grid(row=3, column=2, sticky="nsew", padx=(5, 0))
        list_frame_right.grid_rowconfigure(0, weight=1)
        list_frame_right.grid_columnconfigure(0, weight=1)

        self.current_list = tk.Listbox(list_frame_right, selectmode="extended", exportselection=False,
                                       bg="#FFFFFF", fg="#04304D", selectbackground="#0071BC", selectforeground="white",
                                       highlightthickness=1, highlightbackground="#ACACAC", borderwidth=0, activestyle='none')
        self.current_list.grid(row=0, column=0, sticky="nsew", padx=(1,0), pady=1)

        cur_scroll = ctk.CTkScrollbar(master=list_frame_right, command=self.current_list.yview)
        cur_scroll.grid(row=0, column=1, sticky="ns", padx=(0,1))
        self.current_list.configure(yscrollcommand=cur_scroll.set)
        self.current_list.bind("<Double-Button-1>", lambda e: self._remove_selected())
        self.current_list.bind("<ButtonPress-1>", self._start_drag)
        self.current_list.bind("<B1-Motion>", self._drag_motion)
        self.current_list.bind("<ButtonRelease-1>", self._drop)
        self._drag_start_index = None


        bottom_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        bottom_frame.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(10, 0)) 
        bottom_frame.grid_columnconfigure(0, weight=1)

        reset_button = ctk.CTkButton(bottom_frame, text="Reset to Factory Defaults", command=self._reset_defaults)
        reset_button.grid(row=0, column=1, padx=(0,10))
        save_button = ctk.CTkButton(bottom_frame, text="Save Changes", command=self._save_changes)
        save_button.grid(row=0, column=2, padx=(0,10))
        cancel_button = ctk.CTkButton(bottom_frame, text="Cancel", command=self.destroy)
        cancel_button.grid(row=0, column=3)

    def _start_drag(self, event):
        widget = event.widget
        index = widget.nearest(event.y)
        if index == -1: return

        if (event.state & 0x0001) or (event.state & 0x0004):
            self._drag_start_index = None 
            return 

        self._drag_start_index = index

        if not widget.selection_includes(index):
            widget.selection_clear(0, tk.END)
            widget.selection_set(index)
            widget.activate(index)

    def _drag_motion(self, event):
        if self._drag_start_index is None: 
            return
        
        widget = event.widget
        index = widget.nearest(event.y)
        if index != -1:
            widget.activate(index)

    def _drop(self, event):
        if self._drag_start_index is None: 
            self._drag_start_index = None
            return

        widget = event.widget
        drop_index = widget.nearest(event.y)

        if drop_index == -1: 
            self._drag_start_index = None
            return

        selected_indices = list(widget.curselection())
        if not selected_indices:
            self._drag_start_index = None
            return

        selected_workflow = self.workflow_display_map[self.selected_workflow_display_var.get()]
        current_defaults = self.current_view_definitions.get(selected_workflow, [])

        moved_items = [self._current_map[i] for i in sorted(selected_indices) if i in self._current_map]

        temp_list = [pname for pname in current_defaults if pname not in moved_items]

        if drop_index >= len(self.current_list.get(0, "end")):
             final_insert_index = len(temp_list)
        else:
            try:
                drop_permname = self._current_map[drop_index]
                if drop_permname in temp_list:
                    final_insert_index = temp_list.index(drop_permname)
                else:
                    real_drop_index = drop_index
                    while real_drop_index > 0 and real_drop_index in selected_indices:
                         real_drop_index -= 1
                    
                    if real_drop_index not in selected_indices and real_drop_index in self._current_map:
                         drop_permname = self._current_map[real_drop_index]
                         final_insert_index = temp_list.index(drop_permname) + 1
                    else:
                         final_insert_index = 0 
            except (KeyError, ValueError):
                 final_insert_index = drop_index

        temp_list[final_insert_index:final_insert_index] = moved_items

        self.current_view_definitions[selected_workflow] = temp_list
        self._populate_lists()

        new_selection_indices = []
        current_map_inv = {pname: idx for idx, pname in self._current_map.items()} 
        for pname in moved_items:
            if pname in current_map_inv:
                new_selection_indices.append(current_map_inv[pname])

        if new_selection_indices:
            for idx in new_selection_indices:
                self.current_list.selection_set(idx)
            self.current_list.see(new_selection_indices[0]) 

        self._drag_start_index = None


    def _get_param_display_name(self, permname: str) -> str:
        
        if permname in self.calc_param_details_map:
            label = self.calc_param_details_map[permname]
            return f"{label} [{permname}]"

        param_def = next((p for p in self.all_params_list if p.get('permname') == permname), None)
        if param_def and 'label' in param_def:
            return f"{param_def['label']} [{permname}]"
        
        if permname.startswith("calc_"):
             label = permname.replace("calc_", "").replace("_", " ").title()
             return f"{label} [{permname}]"
             
        return permname 

    def _populate_lists(self, _=None):
        selected_workflow_display = self.selected_workflow_display_var.get()
        selected_workflow = self.workflow_display_map.get(selected_workflow_display, "__GENERAL__")

        selected_category = self.selected_category_var.get()
        search_term = self.search_var.get().lower()

        current_param_permnames = set(self.current_view_definitions.get(selected_workflow, []))

        self.available_list.delete(0, tk.END)
        available_params_data = []
        sorted_all_params = sorted(self.all_params_list, key=lambda p: p.get('label', p.get('permname', '')).lower())

        for param in sorted_all_params:
            permname = param.get('permname')
            category = param.get('category', 'General')

            if not permname or permname in current_param_permnames:
                continue

            if selected_category != "All" and category != selected_category:
                continue

            display_name = self._get_param_display_name(permname)

            if search_term and search_term not in display_name.lower():
                continue

            available_params_data.append((display_name, permname))

        for display_name, _ in available_params_data:
             self.available_list.insert(tk.END, display_name)
        self._available_map = {i: data[1] for i, data in enumerate(available_params_data)}

        self.current_list.delete(0, tk.END)
        current_params_data = []

        for permname in self.current_view_definitions.get(selected_workflow, []):
            display_name = self._get_param_display_name(permname)
            current_params_data.append((display_name, permname))

        for display_name, _ in current_params_data:
            self.current_list.insert(tk.END, display_name)
        self._current_map = {i: data[1] for i, data in enumerate(current_params_data)}


    def _on_workflow_change(self, choice=None):
        self.search_var.set("")
        self.selected_category_var.set("All") 
        self._populate_lists()

    def _add_selected(self):
        selected_indices = self.available_list.curselection()
        if not selected_indices: return

        selected_workflow = self.workflow_display_map[self.selected_workflow_display_var.get()]

        if selected_workflow not in self.current_view_definitions:
            self.current_view_definitions[selected_workflow] = []

        moved_permnames = []
        for i in reversed(selected_indices):
            permname = self._available_map.get(i)
            if permname:
                moved_permnames.append(permname)

        self.current_view_definitions[selected_workflow].extend(reversed(moved_permnames))
        self._populate_lists()

    def _remove_selected(self):
        selected_indices = self.current_list.curselection()
        if not selected_indices: return

        selected_workflow = self.workflow_display_map[self.selected_workflow_display_var.get()]

        current_defaults = self.current_view_definitions.get(selected_workflow, [])
        permnames_to_remove = set()

        for i in selected_indices:
            permname = self._current_map.get(i)
            if permname:
                permnames_to_remove.add(permname)

        self.current_view_definitions[selected_workflow] = [
            pname for pname in current_defaults if pname not in permnames_to_remove
        ]
        self._populate_lists()

    def _move_item(self, direction: int):
        selected_indices = list(self.current_list.curselection())
        if not selected_indices: return

        selected_workflow = self.workflow_display_map[self.selected_workflow_display_var.get()]

        current_defaults = self.current_view_definitions.get(selected_workflow, [])
        new_selection_indices = set()
        selected_indices.sort(reverse=(direction > 0))

        for i in selected_indices:
            if not (0 <= i < len(current_defaults)): continue
            new_i = i + direction
            if 0 <= new_i < len(current_defaults):
                current_defaults[i], current_defaults[new_i] = current_defaults[new_i], current_defaults[i]
                new_selection_indices.add(new_i)

        self.current_view_definitions[selected_workflow] = current_defaults
        self._populate_lists()

        self.current_list.selection_clear(0, tk.END)
        for idx in new_selection_indices:
            self.current_list.selection_set(idx)
            self.current_list.activate(idx)
        if new_selection_indices:
             self.current_list.see(min(new_selection_indices))


    def _save_changes(self):
        if "__GENERAL__" not in self.current_view_definitions:
             self.current_view_definitions["__GENERAL__"] = [] 

        if self.loader_service.save_user_view_definitions(self.current_view_definitions):
            messagebox.showinfo("Success", "Default view settings saved successfully.\nPlease restart the application for changes to take full effect.", parent=self)
            self.destroy()
        else:
            messagebox.showerror("Error", "Failed to save settings. Please check logs for details.", parent=self)

    def _reset_defaults(self):
        confirm = messagebox.askyesno("Confirm Reset",
                                      "Are you sure you want to reset all custom default views to the factory settings?",
                                      parent=self)
        if confirm:
            if self.loader_service.reset_user_view_definitions():
                self.current_view_definitions = copy.deepcopy(self.config.get_factory_default_views())
                self._populate_lists()
                messagebox.showinfo("Success", "Settings reset to factory defaults.\nPlease restart the application for changes to take full effect.", parent=self)
            else:
                messagebox.showerror("Error", "Failed to reset settings. Please check logs for details.", parent=self)