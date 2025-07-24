# ui/parameter_selection.py

import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
from typing import Optional, List, Dict

from data_model import Dataset
from utils import format_parameter_value


class ParameterSelectionWindow(ctk.CTkToplevel):
    """
    A modal dialog window for searching, filtering, and selecting additional
    parameters to display in the main comparison table.
    """
    def __init__(self, master, dataset: Dataset, all_params: List[Dict], previously_selected_params: List[Dict]):
        super().__init__(master)
        self.transient(master)
        self.grab_set()
        self.title("Add Additional Parameters")
        self.geometry("1050x700")

        self.dataset = dataset
        self.all_parameters = all_params
        self.final_selection: Optional[List[Dict]] = None 
        self.all_categories = sorted(list(set(p.get('category', 'General') for p in self.all_parameters)))
        
        self._create_widgets()
        self._update_list()

    def _create_widgets(self):
        """Creates and lays out the widgets for the dialog."""
        main_frame = ctk.CTkFrame(self, fg_color=self.cget("fg_color"))
        main_frame.pack(padx=10, pady=10, fill="both", expand=True)
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(1, weight=1)

        filter_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        filter_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        
        filter_frame.grid_columnconfigure(1, weight=1) 
        filter_frame.grid_columnconfigure(3, weight=1) 

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

        selection_button_frame = ctk.CTkFrame(filter_frame, fg_color="transparent")
        selection_button_frame.grid(row=0, column=4, padx=(5, 10))
        
        self.select_all_button = ctk.CTkButton(selection_button_frame, text="Select All", width=100, command=self._select_all_visible)
        self.select_all_button.pack(side="left", padx=(0, 5))
        
        tree_frame = ctk.CTkFrame(main_frame, fg_color="#E4EFF7", corner_radius=6)
        tree_frame.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        tree_frame.pack_propagate(False)

        self.tree = ttk.Treeview(tree_frame, columns=('Parameter', 'Category', 'Value'), show="headings")
        self.tree.pack(side="left", fill="both", expand=True, padx=1, pady=1)
        
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        vsb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=vsb.set)

        self.tree.heading('Parameter', text='Parameter Label'); self.tree.column('Parameter', anchor='w', width=400)
        self.tree.heading('Category', text='Group'); self.tree.column('Category', anchor='w', width=200)
        self.tree.heading('Value', text='Value'); self.tree.column('Value', anchor='w', width=150)

        self.tree.tag_configure('oddrow', background='#E4EFF7')
        self.tree.tag_configure('evenrow', background='#FFFFFF')

        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.grid(row=2, column=0, pady=(10,0), sticky="e")
        ctk.CTkButton(button_frame, text="Add Selected", command=self._on_ok).pack(side="right", padx=10)
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
        self.tree.selection_set(visible_items)
        
    def _get_param_key(self, param: Dict) -> str:
        return f"{param['permname']}|{param.get('polarity')}|{param.get('source')}"

    def _update_list(self, _=None):
        self.tree.delete(*self.tree.get_children())
        
        visible_keys = self._get_visible_param_keys()
        param_map = {self._get_param_key(p): p for p in self.all_parameters}

        for i, key in enumerate(visible_keys):
            param = param_map.get(key)
            if not param: continue

            tag = 'evenrow' if i % 2 == 0 else 'oddrow'

            raw_value = self.dataset.get_parameter_value(param['permname'])
            formatted_value = format_parameter_value(raw_value, param)
            
            self.tree.insert("", "end", iid=key,
                values=(
                    param.get('label', ''),
                    param.get('category', 'General'),
                    formatted_value
                ),
                tags=(tag,))

    def _on_ok(self):
        selected_iids = self.tree.selection()
        
        self.final_selection = [
            p for p in self.all_parameters 
            if self._get_param_key(p) in selected_iids
        ]
        self.grab_release()
        self.destroy()

    def get_selection(self) -> Optional[List[Dict]]:
        self.wait_window()
        return self.final_selection