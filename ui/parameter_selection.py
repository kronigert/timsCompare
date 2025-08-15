"""
Defines the parameter selection dialog for the timsCompare application.

This module contains the `ParameterSelectionWindow`, a modal dialog that allows
users to interactively search, filter, and select parameters to be displayed
in the main application's comparison view.
"""
import os
import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk
from typing import Optional, List, Dict, Set
from PIL import Image, ImageTk
import logging

from data_model import Dataset
from utils import format_parameter_value, resource_path


class ParameterSelectionWindow(ctk.CTkToplevel):
    """
    A modal dialog window for searching, filtering, and selecting additional
    parameters to display in the main comparison table.
    """
    def __init__(self, master, dataset: Dataset, all_params: List, previously_selected_params: List):
        """
        Initializes the ParameterSelectionWindow dialog.

        Args:
            master: The parent widget, typically the main application window.
            dataset (Dataset): The primary dataset used to display current values
                               for parameters in the list.
            all_params (List): A list of all available parameter definition
                               dictionaries.
            previously_selected_params (List): A list of parameter definitions that
                                               are already selected, to set the
                                               initial state of the checkboxes.
        """
        super().__init__(master)
        
        self.bind("<Map>", self._set_icon)
        
        # --- Window Configuration ---
        self.transient(master)  # Keep window on top of the parent
        self.grab_set()  # Make the dialog modal
        self.title("Add Additional Parameters")
        self.geometry("1050x700")

        # --- State Variables ---
        self.dataset = dataset
        self.all_parameters = all_params
        self.final_selection: Optional[List[Dict]] = None # Stores the result after 'Apply' is clicked
        self.all_categories = sorted(list(set(p.get('category', 'General') for p in self.all_parameters)))

        # A set of unique parameter keys representing the current selection
        self.selection_state: Set[str] = {self._get_param_key(p) for p in previously_selected_params}

        # --- Image References ---
        self.checked_img = None
        self.unchecked_img = None
        self.icon_image_ref = None # To prevent garbage collection of the window icon

        # --- UI Initialization ---
        self._load_and_anchor_images()
        self._create_widgets()
        self._update_list()
    
    def _set_icon(self, event=None):
        """
        Loads and sets the Toplevel window icon.
        
        This method is bound to the <Map> event to ensure the icon is set
        reliably when the window is displayed. It keeps a reference to the
        ImageTk object to prevent garbage collection.
        """
        try:
            logger = logging.getLogger(__name__)
            icon_path = resource_path("assets/icon.ico")
            image = Image.open(icon_path)
            icon_image = ImageTk.PhotoImage(image)

            # Keep a reference to prevent garbage collection
            self.icon_image_ref = icon_image

            self.iconphoto(False, icon_image)
        except Exception as e:
            logger.warning(f"Could not set Toplevel window icon: {e}")
    
    def _load_and_anchor_images(self):
        """
        Loads checkbox images and anchors them to the master widget.

        This robustly prevents the images from being garbage-collected by Python,
        a common issue in Tkinter when references are not maintained at a stable
        scope. It uses a shared dictionary on the master window to cache the
        images, avoiding redundant file loads if the dialog is opened multiple
        times.
        """
        try:
            # Check if images are already cached on the master window
            if hasattr(self.master, '_image_references') and \
               'param_dialog_checked' in self.master._image_references:
                self.checked_img = self.master._image_references['param_dialog_checked']
                self.unchecked_img = self.master._image_references['param_dialog_unchecked']
                return

            # Construct path to assets folder
            assets_path = resource_path("assets")

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

            # Anchor references to the main application window to prevent garbage collection
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
        """Creates and lays out all the widgets for the dialog."""
        main_frame = ctk.CTkFrame(self, fg_color=self.cget("fg_color"))
        main_frame.pack(padx=10, pady=10, fill="both", expand=True)
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(1, weight=1)

        # --- Top Filter Frame ---
        filter_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        filter_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        filter_frame.grid_columnconfigure(1, weight=1) # Search entry
        filter_frame.grid_columnconfigure(3, weight=1) # Category dropdown

        # Search Bar
        ctk.CTkLabel(filter_frame, text="Search:", text_color="#E4EFF7").grid(row=0, column=0, padx=(10,5), pady=5)
        self.search_var = ctk.StringVar()
        self.search_entry = ctk.CTkEntry(filter_frame, textvariable=self.search_var)
        self.search_entry.grid(row=0, column=1, padx=(0,10), pady=5, sticky="ew")
        self.search_var.trace_add("write", lambda *args: self._update_list())

        # Category Filter Dropdown
        ctk.CTkLabel(filter_frame, text="Group:", text_color="#E4EFF7").grid(row=0, column=2, padx=(10,5), pady=5)
        self.category_filter = ctk.CTkOptionMenu(
            filter_frame,
            values=["All"] + self.all_categories,
            command=self._update_list
        )
        self.category_filter.grid(row=0, column=3, padx=(0,10), pady=5, sticky="ew")

        # Select/Deselect All Buttons
        selection_button_frame = ctk.CTkFrame(filter_frame, fg_color="transparent")
        selection_button_frame.grid(row=0, column=4, padx=(5, 10))
        self.select_all_button = ctk.CTkButton(selection_button_frame, text="Select All", width=100, command=self._select_all_visible)
        self.select_all_button.pack(side="left", padx=(0, 5))
        self.deselect_all_button = ctk.CTkButton(selection_button_frame, text="Deselect All", width=100, command=self._deselect_all_visible)
        self.deselect_all_button.pack(side="left")

        # --- Parameter List (Treeview) ---
        tree_frame = ctk.CTkFrame(main_frame, fg_color="#E4EFF7", corner_radius=6)
        tree_frame.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        tree_frame.pack_propagate(False)

        self.tree = ttk.Treeview(tree_frame, columns=('Category', 'Value'), show="tree headings")
        self.tree.pack(side="left", fill="both", expand=True, padx=1, pady=1)
        self.tree.bind("<ButtonPress-1>", self._on_click)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        vsb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=vsb.set)

        # Configure Treeview columns
        self.tree.heading('#0', text='Parameter'); self.tree.column('#0', anchor='w', width=400)
        self.tree.heading('Category', text='Group'); self.tree.column('Category', anchor='w', width=200)
        self.tree.heading('Value', text='Value'); self.tree.column('Value', anchor='w', width=150)

        # Configure row styles for alternating colors
        self.tree.tag_configure('oddrow', background='#E4EFF7')
        self.tree.tag_configure('evenrow', background='#FFFFFF')

        # --- Bottom Action Buttons ---
        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.grid(row=2, column=0, pady=(10,0), sticky="e")
        ctk.CTkButton(button_frame, text="Apply", command=self._on_ok).pack(side="right", padx=10)
        ctk.CTkButton(button_frame, text="Cancel", command=self.destroy).pack(side="right")

    def _get_visible_param_keys(self) -> List[str]:
        """
        Filters the full parameter list based on the current search and category.

        Returns:
            List[str]: A list of unique keys for the parameters that should be
                       visible in the treeview.
        """
        search_term = self.search_var.get().lower()
        category = self.category_filter.get()

        visible_keys = []
        for param in self.all_parameters:
            label_lower = param.get('label', '').lower()
            permname_lower = param.get('permname', '').lower()
            param_category = param.get('category', 'General')

            # Apply search filter (checks both label and permname)
            search_miss = search_term and search_term not in label_lower and search_term not in permname_lower
            # Apply category filter
            category_miss = category != "All" and param_category != category
            
            if search_miss or category_miss:
                continue

            visible_keys.append(self._get_param_key(param))
        return visible_keys

    def _select_all_visible(self):
        """Adds all currently visible parameters to the selection."""
        visible_iids = self.tree.get_children('')
        if not visible_iids:
            return

        for iid in visible_iids:
            if iid not in self.selection_state:
                self.selection_state.add(iid)
                self.tree.item(iid, image=self.checked_img)

    def _deselect_all_visible(self):
        """Removes all currently visible parameters from the selection."""
        visible_iids = self.tree.get_children('')
        if not visible_iids:
            return

        for iid in visible_iids:
            if iid in self.selection_state:
                self.selection_state.remove(iid)
                self.tree.item(iid, image=self.unchecked_img)

    def _get_param_key(self, param: Dict) -> str:
        """
        Creates a unique key for a parameter definition dictionary.
        This helps differentiate parameters with the same permname but different
        polarities or sources.
        """
        return f"{param['permname']}|{param.get('polarity')}|{param.get('source')}"

    def _update_list(self, _=None):
        """
        Clears and repopulates the treeview based on current filter settings.
        
        This is the main refresh function for the parameter list. It gets the
        list of visible parameters, then iterates through them to insert rows
        into the treeview with the correct data and checkbox state.
        """
        self.tree.delete(*self.tree.get_children())

        if not self.checked_img or not self.unchecked_img:
            # Don't try to render if images failed to load
            return

        visible_keys = self._get_visible_param_keys()
        param_map = {self._get_param_key(p): p for p in self.all_parameters}

        for i, key in enumerate(visible_keys):
            param = param_map.get(key)
            if not param: continue

            tag = 'evenrow' if i % 2 == 0 else 'oddrow'
            image = self.checked_img if key in self.selection_state else self.unchecked_img

            # Get the parameter's value from the reference dataset
            raw_value = self.dataset.get_parameter_value(param['permname'])
            formatted_value = format_parameter_value(raw_value, param)

            self.tree.insert("", "end", iid=key,
                text=f" {param.get('label', '')}", # Add padding for checkbox
                image=image,
                values=(
                    param.get('category', 'General'),
                    formatted_value
                ),
                tags=(tag,))

    def _on_click(self, event):
        """
        Handles click events on the treeview to toggle a parameter's selection.
        
        Args:
            event: The tkinter mouse event.
        """
        iid = self.tree.identify_row(event.y)
        if not iid: return

        # Only toggle if the click is on the checkbox/text area (region='tree')
        if self.tree.identify_region(event.x, event.y) == 'tree':
            if iid in self.selection_state:
                self.selection_state.remove(iid)
                self.tree.item(iid, image=self.unchecked_img)
            else:
                self.selection_state.add(iid)
                self.tree.item(iid, image=self.checked_img)

    def _on_ok(self):
        """
        Finalizes the selection and closes the dialog.
        
        This method constructs the final list of selected parameter dictionaries
        based on the keys in `selection_state` and then destroys the window.
        """
        self.final_selection = [
            p for p in self.all_parameters
            if self._get_param_key(p) in self.selection_state
        ]
        self.grab_release()
        self.destroy()

    def get_selection(self) -> Optional[List[Dict]]:
        """
        Public method to show the dialog and retrieve the result.

        This method blocks until the window is closed (either by 'Apply', 'Cancel',
        or the window manager).

        Returns:
            Optional[List[Dict]]: A list of the selected parameter dictionaries if
                                  the user clicked 'Apply', otherwise None.
        """
        self.wait_window()
        return self.final_selection