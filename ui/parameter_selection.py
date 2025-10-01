# ui/parameter_selection.py

import os
import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk
from typing import Optional, List, Dict, Set
from PIL import Image, ImageTk
import logging
import copy

from data_model import Dataset
from services import DataLoaderService
from utils import format_parameter_value, resource_path, apply_dark_title_bar


class ParameterSelectionWindow(ctk.CTkToplevel):
    def __init__(self, master, loader_service: DataLoaderService, dataset: Dataset, 
                 all_params: List, all_sources: List, previously_selected_params: List, last_used_source: Optional[str] = None):
        super().__init__(master)
        
        self.bind("<Map>", self._on_map)
        
        self.transient(master)
        self.grab_set()
        self.title("Add Additional Parameters")
        self.geometry("1200x700")

        self.loader_service = loader_service
        self.dataset = dataset
        self.all_parameters = all_params
        self.all_sources = all_sources
        self.final_selection: Optional[List[Dict]] = None
        self.all_categories = sorted(list(set(p.get('category', 'General') for p in self.all_parameters)))

        self.last_used_source = last_used_source

        self.selection_state: Set[str] = {self._get_param_key(p) for p in previously_selected_params}
        self.source_var = ctk.StringVar()

        self.checked_img = None
        self.unchecked_img = None

        self._load_and_anchor_images()
        self._create_widgets()
        self._update_list()
    
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

    def _load_and_anchor_images(self):
        try:
            if hasattr(self.master, '_image_references') and \
               'param_dialog_checked' in self.master._image_references:
                self.checked_img = self.master._image_references['param_dialog_checked']
                self.unchecked_img = self.master._image_references['param_dialog_unchecked']
                return

            script_dir = os.path.dirname(os.path.abspath(__file__))
            assets_path = os.path.join(script_dir, "..", "assets")

            checked_path = os.path.join(assets_path, "checkbox_checked.png")
            unchecked_path = os.path.join(assets_path, "checkbox_unchecked.png")

            if not os.path.exists(checked_path) or not os.path.exists(unchecked_path):
                raise FileNotFoundError(f"Checkbox image files not found in '{assets_path}'")

            checked_pil_img = Image.open(checked_path).resize((20, 20), Image.Resampling.LANCZOS)
            unchecked_pil_img = Image.open(unchecked_path).resize((20, 20), Image.Resampling.LANCZOS)

            checked_img_obj = ImageTk.PhotoImage(checked_pil_img)
            unchecked_img_obj = ImageTk.PhotoImage(unchecked_pil_img)

            self.checked_img = checked_img_obj
            self.unchecked_img = unchecked_img_obj

            if not hasattr(self.master, '_image_references'):
                self.master._image_references = {}
            self.master._image_references['param_dialog_checked'] = checked_img_obj
            self.master._image_references['param_dialog_unchecked'] = unchecked_img_obj

        except Exception as e:
            messagebox.showerror(
                "Image Load Error",
                f"Failed to load checkbox images for the dialog.\n\nError: {e}",
                parent=self
            )

    def _create_widgets(self):
        main_frame = ctk.CTkFrame(self, fg_color=self.cget("fg_color"))
        main_frame.pack(padx=10, pady=10, fill="both", expand=True)
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(1, weight=1)

        filter_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        filter_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        filter_frame.grid_columnconfigure(1, weight=1)
        filter_frame.grid_columnconfigure(3, weight=1)
        filter_frame.grid_columnconfigure(5, weight=1)

        ctk.CTkLabel(filter_frame, text="Search:", text_color="#E4EFF7").grid(row=0, column=0, padx=(10,5), pady=5)
        self.search_var = ctk.StringVar()
        self.search_entry = ctk.CTkEntry(filter_frame, textvariable=self.search_var)
        self.search_entry.grid(row=0, column=1, padx=(0,10), pady=5, sticky="ew")
        self.search_var.trace_add("write", lambda *args: self._update_list())

        ctk.CTkLabel(filter_frame, text="Group:", text_color="#E4EFF7").grid(row=0, column=2, padx=(10,5), pady=5)
        self.category_filter = ctk.CTkOptionMenu(
            filter_frame,
            values=["All"] + self.all_categories,
            command=self._update_list
        )
        self.category_filter.grid(row=0, column=3, padx=(0,10), pady=5, sticky="ew")
        
        ctk.CTkLabel(filter_frame, text="Source:", text_color="#E4EFF7").grid(row=0, column=4, padx=(10,5), pady=5)

        self.source_filter = ctk.CTkOptionMenu(
            filter_frame,
            values=self.all_sources if self.all_sources else ["-"],
            variable=self.source_var,
            command=self._update_list
        )

        if self.last_used_source and self.last_used_source in self.all_sources:
            self.source_var.set(self.last_used_source)

        elif "captivespray" in self.all_sources:
            self.source_var.set("captivespray")

        elif self.all_sources:
            self.source_var.set(self.all_sources[0])

        self.source_filter.grid(row=0, column=5, padx=(0,10), pady=5, sticky="ew")
        if not self.all_sources:
            self.source_filter.configure(state="disabled")

        selection_button_frame = ctk.CTkFrame(filter_frame, fg_color="transparent")
        selection_button_frame.grid(row=0, column=6, padx=(5, 10))

        self.select_all_button = ctk.CTkButton(selection_button_frame, text="Select All", width=100, command=self._select_all_visible)
        self.select_all_button.pack(side="left", padx=(0, 5))

        self.deselect_all_button = ctk.CTkButton(selection_button_frame, text="Deselect All", width=100, command=self._deselect_all_visible)
        self.deselect_all_button.pack(side="left")

        tree_frame = ctk.CTkFrame(main_frame, fg_color="#E4EFF7", corner_radius=6)
        tree_frame.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        tree_frame.pack_propagate(False)

        self.tree = ttk.Treeview(tree_frame, columns=('Category', 'Value'), show="tree headings")
        self.tree.pack(side="left", fill="both", expand=True, padx=1, pady=1)

        self.tree.bind("<ButtonPress-1>", self._on_click)

        vsb = ctk.CTkScrollbar(tree_frame, command=self.tree.yview)
        vsb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=vsb.set)

        self.tree.heading('#0', text='Parameter'); self.tree.column('#0', anchor='w', width=400)
        self.tree.heading('Category', text='Group'); self.tree.column('Category', anchor='w', width=200)
        self.tree.heading('Value', text='Value'); self.tree.column('Value', anchor='w', width=150)

        self.tree.tag_configure('oddrow', background='#E4EFF7')
        self.tree.tag_configure('evenrow', background='#FFFFFF')

        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.grid(row=2, column=0, pady=(10,0), sticky="e")
        ctk.CTkButton(button_frame, text="Apply", command=self._on_ok).pack(side="right", padx=10)
        ctk.CTkButton(button_frame, text="Cancel", command=self.destroy).pack(side="right")

    def _get_visible_param_keys(self) -> List[str]:
        search_term = self.search_var.get().lower()
        category = self.category_filter.get()

        visible_keys = []
        for param in self.all_parameters:
            label_lower = param.get('label', '').lower()
            permname_lower = param.get('permname', '').lower()
            param_category = param.get('category', 'General')

            if (search_term and search_term not in label_lower and search_term not in permname_lower) or \
               (category != "All" and param_category != category):
                continue

            visible_keys.append(self._get_param_key(param))
        return visible_keys

    def _select_all_visible(self):
        visible_items = self.tree.get_children('')
        if not visible_items:
            return

        for iid in visible_items:
            if iid not in self.selection_state:
                self.selection_state.add(iid)
                self.tree.item(iid, image=self.checked_img)

    def _deselect_all_visible(self):
        visible_items = self.tree.get_children('')
        if not visible_items:
            return

        for iid in visible_items:
            if iid in self.selection_state:
                self.selection_state.remove(iid)
                self.tree.item(iid, image=self.unchecked_img)

    def _get_param_key(self, param: Dict) -> str:
        return f"{param['permname']}|{param.get('polarity')}|{param.get('source')}"

    def _update_list(self, _=None):
        self.tree.delete(*self.tree.get_children())

        if not self.checked_img or not self.unchecked_img:
            return

        visible_keys = self._get_visible_param_keys()
        param_map = {self._get_param_key(p): p for p in self.all_parameters}
        selected_source = self.source_var.get()

        if not selected_source or not self.all_sources:
            return

        for i, key in enumerate(visible_keys):
            param = param_map.get(key)
            if not param: continue

            tag = 'evenrow' if i % 2 == 0 else 'oddrow'
            image = self.checked_img if key in self.selection_state else self.unchecked_img

            raw_value = self.loader_service.get_parameter_value_for_source(
                self.dataset, param['permname'], selected_source
            )
            
            formatted_value = format_parameter_value(raw_value, param)
            
            category_name = param.get('category', 'General')
            if category_name == 'Source':
                category_name = f"Source - {selected_source}"

            self.tree.insert("", "end", iid=key,
                text=f" {param.get('label', '')}",
                image=image,
                values=(
                    category_name,
                    formatted_value
                ),
                tags=(tag,))

    def _on_click(self, event):
        iid = self.tree.identify_row(event.y)
        if not iid: return

        if self.tree.identify_region(event.x, event.y) == 'tree':
            if iid in self.selection_state:
                self.selection_state.remove(iid)
                self.tree.item(iid, image=self.unchecked_img)
            else:
                self.selection_state.add(iid)
                self.tree.item(iid, image=self.checked_img)

    def _on_ok(self):
        initial_selection = [
            p for p in self.all_parameters
            if self._get_param_key(p) in self.selection_state
        ]
        
        selected_source = self.source_var.get()
        
        if selected_source and self.all_sources:
            modified_selection = []
            for param in initial_selection:
                if param.get('category') == 'Source':
                    new_param = copy.copy(param)
                    new_param['category'] = f"Source - {selected_source}"
                    modified_selection.append(new_param)
                else:
                    modified_selection.append(param)
            
            self.final_selection = (modified_selection, selected_source)
        
        else:
            self.final_selection = (initial_selection, None)

        self.grab_release()
        self.destroy()

    def get_selection(self) -> Optional[List[Dict]]:
        self.wait_window()
        return self.final_selection