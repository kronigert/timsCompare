"""
Defines the main user interface for the timsCompare application.

This module contains the core `timsCompareApp` class, which orchestrates the
entire graphical user interface, including widget creation, event handling,
state management, and interaction with the backend services. It also defines
helper UI classes like `Tooltip` and the `AboutDialog`.
"""
import os
import logging
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
from tkinter.font import Font
from tkinterdnd2 import DND_FILES
from typing import List, Dict, Optional, Any
from collections import defaultdict
import webbrowser

import customtkinter as ctk
import pandas as pd

from app_config import AppConfig
from data_model import Dataset
from services import DataLoaderService, PlottingService, ReportGeneratorService, DataProcessingError
from utils import format_parameter_value, resource_path
from .parameter_selection import ParameterSelectionWindow
from PIL import Image, ImageTk


class Tooltip:
    """
    Creates a tooltip for a given widget that appears on mouse hover.

    This helper class attaches to a widget and displays a small pop-up window
    with informational text when the user's cursor enters the widget. The
    tooltip is hidden when the cursor leaves.
    """
    def __init__(self, widget: tk.Widget, text_callback: callable):
        """
        Initializes the Tooltip.

        Args:
            widget (tk.Widget): The widget to which the tooltip will be attached.
            text_callback (callable): A function that returns the string to be
                                      displayed in the tooltip.
        """
        self.widget = widget
        self.text_callback = text_callback
        self.tip_window = None
        self.id = None
        self.x = self.y = 0
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)
        self.widget.bind("<ButtonPress>", self.leave)

    def enter(self, event=None):
        """Schedules the tooltip to appear after a short delay."""
        self.schedule()

    def leave(self, event=None):
        """Hides the tooltip and cancels any scheduled appearance."""
        self.unschedule()
        self.hidetip()

    def schedule(self):
        """Schedules `showtip` to be called after a 500ms delay."""
        self.unschedule()
        self.id = self.widget.after(500, self.showtip)

    def unschedule(self):
        """Cancels a previously scheduled tooltip appearance."""
        if self.id:
            self.widget.after_cancel(self.id)
            self.id = None

    def showtip(self):
        """Creates and displays the tooltip window."""
        if self.tip_window:
            return

        full_text = self.text_callback()
        if not full_text:
            return

        # Check if the widget's text is truncated. If not, don't show tooltip.
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

        # Position the tooltip below the widget
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5

        self.tip_window = tk.Toplevel(self.widget)
        self.tip_window.wm_overrideredirect(True)  # Frameless window
        self.tip_window.wm_geometry(f"+{x}+{y}")

        label = ctk.CTkLabel(self.tip_window, text=full_text, fg_color="#3E3E3E",
                               bg_color="transparent", text_color="white",
                               corner_radius=4, padx=8, pady=4,
                               font=ctk.CTkFont(size=11))
        label.pack(ipadx=1)

    def hidetip(self):
        """Destroys the tooltip window if it exists."""
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None


class AboutDialog(ctk.CTkToplevel):
    """
    A custom modal dialog window to display application information.

    This dialog provides details about the application's version, purpose,
    key functionalities, and a link to its source code repository.
    """
    def __init__(self, master, about_icon: ctk.CTkImage, github_icon: ctk.CTkImage):
        """
        Initializes the About dialog.

        Args:
            master: The parent widget.
            about_icon (ctk.CTkImage): The icon to display for the application.
            github_icon (ctk.CTkImage): The icon for the GitHub link button.
        """
        super().__init__(master)
        
        self.bind("<Map>", self._set_icon)
        
        self.title("About timsCompare")
        self.geometry("600x500")
        self.resizable(False, False)
        self.transient(master)  # Keep on top of the main window
        self.grab_set()  # Modal behavior

        # --- Main Layout ---
        main_frame = ctk.CTkFrame(self, fg_color="#04304D")
        main_frame.pack(fill="both", expand=True)
        main_frame.grid_columnconfigure(0, weight=1)

        # --- Header ---
        top_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        top_frame.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        top_frame.grid_columnconfigure(1, weight=1)

        app_icon_label = ctk.CTkLabel(top_frame, image=about_icon, text="")
        app_icon_label.grid(row=0, column=0, padx=(0, 15))
        
        title_label = ctk.CTkLabel(
            top_frame,
            text="timsCompare v1.0",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#E4EFF7"
        )
        title_label.grid(row=0, column=1, sticky="w")

        # --- Description Text ---
        description_text = (
            "timsCompare is a desktop application for mass spectrometry users, designed to analyze "
            "Bruker's .d / .m methods. Methods can be loaded using the 'Add Data' "
            "button or via drag-and-drop.\n\n"
            "The tool's core functionalities are:\n\n"
            "1. Parameter Comparison: Provides a detailed, side-by-side view of acquisition "
            "parameters, automatically highlighting differences between methods.\n\n"
            "2. Window Export: Offers a function to export the isolation "
            "window definitions for PASEF, dia-PASEF, and diagonal-PASEF methods.\n\n"
            "3. Method Reporting: Generates comprehensive method reports in "
            "both PDF and CSV formats for documentation or publication.\n\n"
            "Disclaimer: This is an independent, third-party tool and is not an "
            "official Bruker product, nor is it affiliated with or supported by Bruker."
        )
        desc_label = ctk.CTkLabel(
            main_frame,
            text=description_text,
            wraplength=500,
            justify="left",
            text_color="#DCE4EE"
        )
        desc_label.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        
        # --- Footer Information ---
        libs_label = ctk.CTkLabel(
            main_frame,
            text="Built with: Python, CustomTkinter, Pandas, and Matplotlib",
            font=ctk.CTkFont(size=11),
            text_color="gray60"
        )
        libs_label.grid(row=2, column=0, padx=20, pady=(10, 15))

        separator = ctk.CTkFrame(main_frame, height=1, fg_color="#1A5680")
        separator.grid(row=3, column=0, padx=20, pady=0, sticky="ew")

        # --- GitHub Link ---
        github_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        github_frame.grid(row=4, column=0, padx=20, pady=(15, 20))

        def open_github_link():
            webbrowser.open_new_tab("https://github.com/kronigert/timsCompare")

        github_button = ctk.CTkButton(
            github_frame,
            text="",
            image=github_icon,
            compound="left",
            command=open_github_link,
            fg_color="#004E82",
            hover_color="#0071BC"
        )
        github_button.pack()
    
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

class timsCompareApp:
    """
    The main application class for the timsCompare user interface.

    This class is responsible for initializing and managing all UI components,
    handling user interactions, maintaining the application's state (e.g., loaded
    datasets), and coordinating with the service layer to perform backend tasks
    like data loading, plotting, and report generation.
    """
    def __init__(self, root: tk.Tk, config: AppConfig, data_loader: DataLoaderService, plot_service: PlottingService, report_generator: ReportGeneratorService):
        """
        Initializes the main application window.

        Args:
            root (tk.Tk): The root tkinter window.
            config (AppConfig): The application's configuration object.
            data_loader (DataLoaderService): Service for loading and parsing data.
            plot_service (PlottingService): Service for generating plots.
            report_generator (ReportGeneratorService): Service for creating reports.
        """
        self.root = root

        # --- Service and Config Injection ---
        self.config = config
        self.loader = data_loader
        self.plotter = plot_service
        self.report_generator = report_generator
        self.logger = logging.getLogger(__name__)

        # --- Compatibility for dnd on Toplevels ---
        if not hasattr(self.root, "block_update_dimensions_event"):
            self.root.block_update_dimensions_event = lambda: None
        if not hasattr(self.root, "unblock_update_dimensions_event"):
            self.root.unblock_update_dimensions_event = lambda: None

        self.root.title("timsCompare")
        self.root.geometry("1500x800")

        # --- Application State Variables ---
        self.datasets: List[Dataset] = []  # Holds all loaded Dataset objects.
        self.displayed_params: Optional[List[Dict]] = None  # List of parameter configs to display. None means use default.
        self.dropdown_name_map: Dict[str, str] = {}  # Maps truncated names in dropdowns to full display names.
        self.status_label_full_text: str = ""  # Full text for the status bar tooltip.

        # --- UI Widget References ---
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

        # --- UI State Tracking Variables ---
        self.active_row_iid: Optional[str] = None  # Treeview row ID under cursor
        self.active_column_id: Optional[str] = None  # Treeview column ID under cursor
        self.remove_var = ctk.StringVar()
        self.plots_visible = tk.BooleanVar(value=True)
        self.show_only_diffs_var = tk.BooleanVar(value=False)
        self._resize_job: Optional[str] = None  # To debounce resize events

        self.optionmenu_font = ctk.CTkFont()

        # --- Initialization Steps ---
        self._setup_styles()
        self._load_icons()
        self._create_widgets()
        self._redraw_ui()

    def _create_widgets(self):
        """Creates and arranges all the widgets in the main window."""
        self.main_frame = ctk.CTkFrame(self.root, fg_color="#04304D", corner_radius=0)
        self.main_frame.pack(fill="both", expand=True)
        self.main_frame.grid_rowconfigure(2, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(1, weight=1)

        # --- Top Control Frame ---
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

        # --- Segment Controls Frame (hidden by default) ---
        self.segment_controls_frame = ctk.CTkScrollableFrame(
            self.main_frame, fg_color="transparent", orientation="horizontal", label_text="", height=40
        )
        self.segment_controls_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=(5, 0), sticky="ew")
        self.segment_controls_frame.grid_remove() # Hidden until a multi-segment file is loaded

        # --- Menus ---
        self.plot_toggle_menu = tk.Menu(self.root, tearoff=0)
        self.add_menu = tk.Menu(self.root, tearoff=0)
        self.add_menu.add_command(label="Add .d Folder...", command=lambda: self._add_folder_dialog(".d"))
        self.add_menu.add_command(label="Add .m Folder...", command=lambda: self._add_folder_dialog(".m"))

        # --- Main Table (Treeview) ---
        self.table_frame = ctk.CTkFrame(self.main_frame, fg_color="#E4EFF7", corner_radius=0, border_width=0)
        self.table_frame.grid(row=2, column=0, sticky="nsew", padx=(10, 2), pady=5)
        self.table_frame.grid_propagate(False)
        self.table_frame.grid_rowconfigure(0, weight=1)
        self.table_frame.grid_columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(self.table_frame, show="tree headings")
        self.tree.grid(row=0, column=0, sticky="nsew")

        # Configure styles for treeview rows
        self.tree.tag_configure('oddrow', background='#E4EFF7')
        self.tree.tag_configure('evenrow', background='#FFFFFF')
        self.tree.tag_configure('diff', font=('TkDefaultFont', 10, 'bold'))

        # Scrollbars for the Treeview
        vsb = ctk.CTkScrollbar(self.table_frame, orientation="vertical", command=self.tree.yview)
        hsb = ctk.CTkScrollbar(self.table_frame, orientation="horizontal", command=self.tree.xview)
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        # Cover the bottom-right corner where scrollbars meet
        ctk.CTkFrame(self.table_frame, fg_color="#E4EFF7", border_width=0, width=16, height=16).place(relx=1.0, rely=1.0, anchor="se")

        # Bind events to the Treeview
        self.tree.bind("<Motion>", self._on_tree_motion)
        self.tree.bind("<Control-c>", self._copy_selection_to_clipboard)
        self.tree.bind("<Button-3>", self._show_context_menu)
        self.tree.bind("<Button-1>", self._on_cell_select)

        self._create_context_menu()

        # --- Right Plot Pane ---
        self.right_plot_container = ctk.CTkFrame(self.main_frame, fg_color="#E4EFF7", corner_radius=0, border_width=0)
        self.right_plot_container.grid(row=2, column=1, sticky="nsew", padx=(2, 10), pady=5)
        self.right_plot_container.grid_columnconfigure(0, weight=1)
        self.right_plot_container.grid_rowconfigure(0, weight=0) # Row for plot toggle button
        self.right_plot_container.grid_rowconfigure(1, weight=1) # Row for scrollable plot canvas
        self.right_plot_container.bind("<Configure>", self._on_container_resize)

        self.plot_toggle_button = ctk.CTkButton(self.right_plot_container, text="", image=self.plots_icon, command=self._show_plot_toggle_menu, width=28, fg_color="transparent", hover_color="#DFE5EA")
        self.plot_toggle_button.grid(row=0, column=0, sticky="ne", padx=5, pady=(5,0))
        Tooltip(self.plot_toggle_button, lambda: "Toggle plot visibility")

        # --- Bottom Controls and Status Bar ---
        bottom_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        bottom_frame.grid(row=3, column=0, columnspan=2, padx=10, pady=(15, 10), sticky="ew")

        # Split bottom area into two equal halves
        bottom_frame.grid_columnconfigure(0, weight=1, uniform="bottom_split")
        bottom_frame.grid_columnconfigure(1, weight=1, uniform="bottom_split")

        # Left side: File selection and actions
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

        # Right side: Status bar label
        right_status_frame = ctk.CTkFrame(bottom_frame, fg_color="transparent")
        right_status_frame.grid(row=0, column=1, sticky="ew")

        self.status_bar_label = ctk.CTkLabel(right_status_frame, text="", anchor="e", text_color="#E4EFF7")
        self.status_bar_label.pack(side="right", fill="x", expand=True, padx=(10, 0))

        # Add tooltips to widgets that may have truncated text
        Tooltip(self.remove_menu, lambda: self.dropdown_name_map.get(self.remove_var.get(), ""))
        Tooltip(self.status_bar_label, lambda: self.status_label_full_text)

        # Enable drag and drop
        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind('<<Drop>>', self._handle_drop)

    def _on_segment_selected(self, dataset_key: str, choice: str):
        """
        Handles the selection of a new segment from a dropdown menu.

        Args:
            dataset_key (str): The key_path of the dataset being changed.
            choice (str): The selected string from the dropdown (e.g., "Segment 1").
        """
        target_dataset = next((d for d in self.datasets if d.key_path == dataset_key), None)
        if not target_dataset: return

        try:
            new_index = int(choice.split(' ')[1]) - 1
            if 0 <= new_index < len(target_dataset.segments):
                target_dataset.active_segment_index = new_index
                self._update_treeview_data()
                self._update_plot_grid()
        except (ValueError, IndexError):
            self.logger.warning(f"Could not parse segment index from choice '{choice}'")

    def _update_segment_controls(self):
        """
        Updates or creates dropdown controls for multi-segment datasets.

        This method checks if any loaded datasets have more than one segment.
        If so, it displays a scrollable frame with a dropdown for each such
        dataset, allowing the user to switch the active segment.
        """
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

                    # Update status bar on hover
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
        """
        Resets the parameter view in the main table to the default set.

        This is triggered by the "Reset View" button. It sets the currently
        displayed parameters to None, which causes the UI to recalculate the
        default view on the next redraw.
        """
        if self.displayed_params is not None:
            self.displayed_params = None
            self._redraw_ui()

    def _redraw_ui(self, *args):
        """
        Central method to refresh the entire UI based on the current state.

        This method orchestrates the update of all major UI components: the
        parameter table, the plot area, the remove/export dropdown, and the
        segment selection controls.
        """
        self._reconfigure_treeview()
        self._update_treeview_data()
        self.root.after(50, self._reconfigure_plot_area)
        self.root.after(100, self._update_remove_menu)
        self._update_segment_controls()

    def _handle_drop(self, event: tk.Event):
        """
        Handles files/folders being dropped onto the application window.

        Args:
            event (tk.Event): The drop event, containing file paths.
        """
        paths = self.root.tk.splitlist(event.data)
        valid_folders = [p for p in paths if os.path.isdir(p) and p.lower().endswith((".d", ".m"))]
        if not valid_folders:
            messagebox.showwarning("Drag & Drop Info", "No valid .d or .m folders were dropped.")
            return
        self._load_folders(valid_folders)

    def _add_folder_dialog(self, extension: str):
        """
        Opens a dialog to select a .d or .m folder.

        Args:
            extension (str): The folder extension to look for (e.g., ".d").
        """
        folder = filedialog.askdirectory(title=f"Select a {extension} folder")
        if not folder or not folder.lower().endswith(extension):
            return
        self._load_folders([folder])

    def _load_folders(self, folder_paths: List[str]):
        """
        Loads one or more datasets from the given folder paths.

        Iterates through paths, calls the DataLoaderService, appends successful
        loads to the application state, and triggers a UI redraw.

        Args:
            folder_paths (List[str]): A list of absolute paths to .d or .m folders.
        """
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
                self.logger.error(f"Unexpected error loading '{path}'", exc_info=True)
                messagebox.showerror("An Unexpected Error Occurred", f"An unexpected error occurred while loading '{os.path.basename(path)}':\n\n{e.__class__.__name__}: {e}")

        if loaded_count > 0:
            # Reset to default parameter view when new data is added
            self.displayed_params = None
            self._redraw_ui()

    def _remove_selected_folder(self):
        """Removes the dataset selected in the bottom dropdown menu."""
        selected_truncated_name = self.remove_var.get()
        if not selected_truncated_name or selected_truncated_name == "-": return

        full_name = self.dropdown_name_map.get(selected_truncated_name)
        if not full_name: return

        self.datasets = [d for d in self.datasets if d.display_name != full_name]
        self.displayed_params = None  # Reset view after removing data
        self._redraw_ui()

    def _get_default_param_configs(self) -> List[Dict]:
        """
        Determines the default set of parameters to display.

        This logic is centralized here. It gathers the workflows from all active
        segments of the loaded datasets, retrieves the corresponding default
        parameter lists from the configuration, and merges them with the
        "__GENERAL__" list to create a comprehensive default view.

        Returns:
            List[Dict]: A list of parameter configuration dictionaries.
        """
        if not self.datasets:
            return []

        default_params_by_workflow = self.config.parameter_definitions
        active_workflows = {ds.segments[ds.active_segment_index].workflow_name for ds in self.datasets if ds.segments}

        default_permnames_ordered = []
        seen_permnames = set()

        # Helper to add unique parameter names while preserving order
        def add_unique(permnames):
            for pname in permnames:
                if pname not in seen_permnames:
                    seen_permnames.add(pname)
                    default_permnames_ordered.append(pname)

        # Add general parameters first, then workflow-specific ones
        add_unique(default_params_by_workflow.get("__GENERAL__", []))
        for wf in active_workflows:
            add_unique(default_params_by_workflow.get(wf, []))

        all_definitions_map = {p['permname']: p for p in self.config.all_definitions}
        default_param_configs = []

        for pname in default_permnames_ordered:
            if pname in all_definitions_map:
                default_param_configs.append(all_definitions_map[pname])
            elif pname.startswith("calc_"):
                # Manually create configs for calculated parameters
                label_map = {
                    "calc_scan_area_mz": "Window Scan Area", "calc_ramps": "Ramps per Cycle",
                    "calc_ms1_scans": "MS1 Scans per Cycle", "calc_steps": "Isolation Steps per Cycle",
                    "calc_mz_width": "Isolation Window Width", "calc_ce_ramping_start": "CE Ramping Start",
                    "calc_ce_ramping_end": "CE Ramping End"
                }
                label = label_map.get(pname, pname.replace("calc_", "").replace("_", " ").title())
                category = "Mode" if "Scan Mode" in label else "Calculated Parameters"
                default_param_configs.append({"permname": pname, "label": label, "category": category})

        return default_param_configs

    def _open_add_parameters_dialog(self):
        """
        Opens the dialog for selecting optional parameters to display.
        
        This method gathers all available parameters from the loaded datasets,
        filters them based on context (e.g., ICC modes), and passes them to the
        `ParameterSelectionWindow`. If the user confirms a new selection, it
        requests the DataLoaderService to parse any newly added parameters and
        then triggers a UI redraw.
        """
        self.logger.info("Opening 'Add Parameters' dialog...")
        try:
            if not self.datasets:
                messagebox.showinfo("Information", "Please load at least one dataset before adding parameters.")
                return

            selected_name = self.remove_var.get()
            selected_dataset = next((d for d in self.datasets if d.display_name == self.dropdown_name_map.get(selected_name)), self.datasets[0])
            if not selected_dataset:
                self.logger.warning("No dataset selected for parameter dialog.")
                return

            # Check for specific modes across all datasets to conditionally show parameters
            has_icc_mode1 = any(ds.get_parameter_value("IMSICC_Mode") == '1' for ds in self.datasets if ds.segments)
            has_icc_mode2 = any(ds.get_parameter_value("IMSICC_Mode") == '2' for ds in self.datasets if ds.segments)
            
            # Gather all parameters found in the files across all datasets
            all_found_params_dict = {self._get_param_key(p): p for ds in self.datasets for p in (ds.default_params + ds.available_optional_params)}

            # Ensure any currently displayed calculated parameters are included in the list
            if self.displayed_params is None:
                self.displayed_params = self._get_default_param_configs()
            current_calc_params = [p for p in self.displayed_params if p.get('permname', '').startswith('calc_')]
            for p_calc in current_calc_params:
                param_key = self._get_param_key(p_calc)
                if param_key not in all_found_params_dict:
                    all_found_params_dict[param_key] = p_calc

            # Filter the master list of parameters based on conditional flags
            conditionally_valid_params = []
            mode2_permnames = {
                "IMSICC_ICC2_MaxTicTargetPercent", "IMSICC_ICC2_MinAccuTime",
                "IMSICC_ICC2_ReferenceTicTargetPercent", "IMSICC_ICC2_ReferenceTicCapacity", "IMSICC_ICC2_SmoothingFactor"
            }

            for param_config in all_found_params_dict.values():
                permname = param_config.get('permname')
                
                # Conditional filtering logic
                if permname == 'IMSICC_Target' and not has_icc_mode1: continue
                if permname in mode2_permnames and not has_icc_mode2: continue
                
                conditionally_valid_params.append(param_config)
            
            all_param_definitions = sorted(conditionally_valid_params, key=lambda p: p.get('label', ''))

            # Launch the dialog
            dialog = ParameterSelectionWindow(
                self.root,
                dataset=selected_dataset,
                all_params=all_param_definitions, 
                previously_selected_params=self.displayed_params
            )
            new_selection = dialog.get_selection()

            if new_selection is not None:
                self.logger.debug(f"Dialog returned {len(new_selection)} selected parameters.")

                # Determine which new parameters need their data to be parsed
                current_keys = {self._get_param_key(p) for p in self.displayed_params}
                new_keys = {self._get_param_key(p) for p in new_selection}

                keys_to_parse = new_keys - current_keys
                if keys_to_parse:
                    self.logger.info(f"Need to parse data for {len(keys_to_parse)} newly added parameters.")
                    configs_to_parse = [p for p in all_param_definitions if self._get_param_key(p) in keys_to_parse]
                    for ds in self.datasets:
                        self.loader.parse_additional_parameters(ds, configs_to_parse)

                self.displayed_params = new_selection
                self._redraw_ui()
        except Exception as e:
            self.logger.error("An error occurred while opening or processing the parameter selection dialog.", exc_info=True)
            messagebox.showerror("Error", f"An unexpected error occurred:\n{e}")

    def _insert_row(self, param_config: Dict, parent_node: str, values: List[str]):
        """
        Inserts a single, non-expandable row into the Treeview.

        Args:
            param_config (Dict): The configuration for the parameter.
            parent_node (str): The iid of the parent category node.
            values (List[str]): The list of formatted values for each dataset.
        """
        is_different = len(set([v for v in values if v not in ["", "N/A"]])) > 1
        
        # Skip row if "Show only differences" is on and values are the same
        if self.show_only_diffs_var.get() and not is_different:
            return

        label = param_config.get("label", param_config.get("permname"))
        self.tree.insert(parent_node, "end", text=label, values=tuple(values), tags=('diff',) if is_different else ())

    def _insert_expandable_list_rows(self, param_config: Dict, parent_node: str, raw_values: List[Any]):
        """
        Inserts an expandable parent row and its child rows for list-based parameters.

        Args:
            param_config (Dict): The configuration for the parameter.
            parent_node (str): The iid of the parent category node.
            raw_values (List[Any]): List of raw values, which may contain lists.
        """
        # The parent row shows a summary (e.g., "[3 items]")
        parent_row_values = [format_parameter_value(val, param_config) for val in raw_values]
        is_parent_different = len(set(parent_row_values)) > 1

        # Complex filtering for "show only differences"
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

        label = param_config.get("label", param_config.get("permname"))
        parent_iid = self.tree.insert(parent_node, "end", text=label, values=tuple(parent_row_values), open=False, tags=('diff',) if is_parent_different else ())

        # Insert a child row for each item in the lists
        max_len = max((len(v) for v in raw_values if isinstance(v, list)), default=0)
        for i in range(max_len):
            child_row_values = [format_parameter_value(v[i], param_config) if isinstance(v, list) and i < len(v) else "N/A" for v in raw_values]
            is_child_different = len(set(v for v in child_row_values if v != "N/A")) > 1

            if self.show_only_diffs_var.get() and not is_child_different:
                continue

            self.tree.insert(parent_iid, "end", text=f"  Item {i+1}", values=tuple(child_row_values), tags=('diff',) if is_child_different else ())

    def _setup_styles(self):
        """Configures the styles for the ttk.Treeview widget."""
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview.Heading", background="#004E82", foreground="white", font=('TkDefaultFont', 10, 'bold'), padding=5)
        style.map("Treeview.Heading", background=[('active', "#0071BC")])
        style.configure("Treeview", background="#E4EFF7", foreground="#04304D", fieldbackground="#E4EFF7", rowheight=25, borderwidth=0)
        style.map("Treeview", background=[('selected', '#0071BC')], foreground=[('selected', 'white')])

    def _update_treeview_data(self):
        """
        Populates the Treeview with parameter data from the loaded datasets.
        
        This is a core UI update method. It clears the tree, determines which
        parameters to show (default or custom), groups them by category, sorts
        them, and then inserts them as rows. It handles conditional display,
        expandable lists, and highlights differences.
        """
        for row in self.tree.get_children(): self.tree.delete(row)
        if not self.datasets:
            self.tree.configure(show="tree"); self.tree.heading("#0", text="")
            return

        self.tree.configure(show="tree headings")

        # Use default parameter set if a custom one isn't specified
        if self.displayed_params is None:
            self.displayed_params = self._get_default_param_configs()

        all_display_configs = self.displayed_params

        # Special handling to avoid showing both Mode_ScanMode and the calculated calc_scan_mode
        displayed_permnames = {p['permname'] for p in all_display_configs}
        if "calc_scan_mode" in displayed_permnames:
            all_display_configs = [p for p in all_display_configs if p.get('permname') != "Mode_ScanMode"]

        # --- Group parameters by category ---
        grouped_params = defaultdict(list)
        for p_config in all_display_configs:
            grouped_params[p_config.get("category", "General")].append(p_config)

        # --- Sort categories: Mode first, Calculated last, others alphabetical ---
        def sort_key(g):
            if g == "Mode": return (0, g)
            if g == "Calculated Parameters": return (2, g)
            return (1, g)
        sorted_groups = sorted(grouped_params.keys(), key=sort_key)

        # Get the default parameter order to maintain a consistent layout
        default_params_for_sorting = self._get_default_param_configs()
        order_map = {p['permname']: i for i, p in enumerate(default_params_for_sorting)}

        # --- Check for conditional parameters across all datasets ---
        has_multisegment_file = any(len(ds.segments) > 1 for ds in self.datasets)
        has_standard_ce_dataset = any(ds.get_parameter_value("Energy_Ramping_Advanced_Settings_Active") == '0' for ds in self.datasets if ds.segments)
        has_advanced_ce_dataset = any(ds.get_parameter_value("Energy_Ramping_Advanced_Settings_Active") == '1' for ds in self.datasets if ds.segments)
        has_icc_mode1 = any(ds.get_parameter_value("IMSICC_Mode") == '1' for ds in self.datasets if ds.segments)
        has_icc_mode2 = any(ds.get_parameter_value("IMSICC_Mode") == '2' for ds in self.datasets if ds.segments)

        # --- Populate the Treeview ---
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

                # Conditionally skip parameters that aren't relevant for any loaded dataset
                if permname in ["calc_segment_start_time", "calc_segment_end_time"] and not has_multisegment_file: continue
                if permname in ["calc_ce_ramping_start", "calc_ce_ramping_end"] and not has_standard_ce_dataset: continue
                if permname == "calc_advanced_ce_ramping_display_list" and not has_advanced_ce_dataset: continue
                if permname == 'IMSICC_Target' and not has_icc_mode1: continue
                mode2_params = [
                    "IMSICC_ICC2_MaxTicTargetPercent", "IMSICC_ICC2_MinAccuTime",
                    "IMSICC_ICC2_ReferenceTicCapacity", "IMSICC_ICC2_SmoothingFactor"
                ]
                if permname in mode2_params and not has_icc_mode2: continue

                raw_values = [ds.get_parameter_value(permname) for ds in self.datasets]
                is_list_param = any(isinstance(val, list) for val in raw_values)

                if is_list_param:
                    self._insert_expandable_list_rows(param_config, parent_node, raw_values)
                else:
                    formatted_values = [format_parameter_value(val, param_config) for val in raw_values]
                    self._insert_row(param_config, parent_node, formatted_values)

                displayed_param_keys.add(permname)

        # --- Final cleanup and styling ---
        for parent_iid in self.tree.get_children(''):
            children = self.tree.get_children(parent_iid)
            if not children:
                self.tree.delete(parent_iid)  # Remove empty category headers
            else:
                # Apply alternating row colors
                for i, child_iid in enumerate(children):
                    tag = 'evenrow' if i % 2 == 0 else 'oddrow'
                    current_tags = [t for t in list(self.tree.item(child_iid, 'tags')) if t not in ['evenrow', 'oddrow']]
                    current_tags.append(tag)
                    self.tree.item(child_iid, tags=tuple(current_tags))

    def _get_param_key(self, param: Dict) -> str:
        """
        Creates a unique key for a parameter definition dictionary.
        This helps differentiate parameters with the same permname but different
        polarities or sources.
        """
        return f"{param['permname']}|{param.get('polarity')}|{param.get('source')}"

    def _create_context_menu(self):
        """Creates the right-click context menu for the Treeview."""
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Copy Cell Value", command=self._copy_cell_value)
        self.context_menu.add_command(label="Copy Selected Row(s)", command=self._copy_selection_to_clipboard)

    def _show_context_menu(self, event: tk.Event):
        """
        Shows the context menu at the cursor's position on right-click.

        Args:
            event (tk.Event): The right-click event.
        """
        self._on_cell_select(event) # Identify which cell was clicked
        if self.active_row_iid and self.tree.exists(self.active_row_iid):
            # Special handling for expandable list parents
            is_adv_ce = self.tree.item(self.active_row_iid, "text").strip().startswith("CE Ramping (Advanced)")
            is_data = (self.active_column_id and self.tree.item(self.active_row_iid, "values")) or is_adv_ce
            
            # Enable/disable menu items based on context
            self.context_menu.entryconfigure("Copy Cell Value", state="normal" if is_data else "disabled")
            self.context_menu.entryconfigure("Copy Selected Row(s)", state="normal" if self.tree.selection() or is_adv_ce else "disabled")
            
            self.context_menu.tk_popup(event.x_root, event.y_root)

    def _on_cell_select(self, event: tk.Event):
        """
        Stores the row and column identifiers for the cell under the cursor.

        Args:
            event (tk.Event): The mouse event.
        """
        self.active_row_iid = self.tree.identify_row(event.y)
        self.active_column_id = self.tree.identify_column(event.x)

    def _copy_cell_value(self, event=None):
        """Copies the value of the currently active cell to the clipboard."""
        if not all([self.active_row_iid, self.active_column_id, self.tree.exists(self.active_row_iid)]): return
        
        cell_value = ""
        if self.active_column_id == '#0':  # Parameter name column
            cell_value = self.tree.item(self.active_row_iid, "text")
            # If it's a parent of an expandable list, copy children too
            if cell_value.strip().startswith("CE Ramping (Advanced)"):
                children_text = [f"{self.tree.item(cid, 'text')}\t" + '\t'.join(map(str, self.tree.item(cid, 'values'))) for cid in self.tree.get_children(self.active_row_iid)]
                if children_text: cell_value += "\n" + "\n".join(children_text)
        else:  # Data column
            try:
                col_idx = int(self.active_column_id.replace('#', '')) - 1
                values = self.tree.item(self.active_row_iid, "values")
                if values and 0 <= col_idx < len(values): cell_value = values[col_idx]
            except (ValueError, IndexError): return

        if cell_value: 
            self.root.clipboard_clear()
            self.root.clipboard_append(cell_value)

    def _copy_selection_to_clipboard(self, event=None):
        """Copies the selected rows (including headers) as tab-separated text."""
        selected_iids = self.tree.selection()
        
        # Special case: if no selection, but right-clicked on an expandable parent
        if not selected_iids and self.active_row_iid and self.tree.exists(self.active_row_iid) and self.tree.item(self.active_row_iid, "text").strip().startswith("CE Ramping (Advanced)"):
            selected_iids = (self.active_row_iid,)
        if not selected_iids: return

        headers = [self.tree.heading("#0", "text")] + [self.tree.heading(c, "text") for c in self.tree['columns']]
        text_lines = ["\t".join(headers)]
        for item_iid in selected_iids:
            text_lines.append("\t".join(map(str, [self.tree.item(item_iid, "text")] + list(self.tree.item(item_iid, "values")))))
            # If it's an expandable parent, also copy its children
            if self.tree.item(item_iid, "text").strip().startswith("CE Ramping (Advanced)"):
                for child_iid in self.tree.get_children(item_iid):
                    text_lines.append(f"{self.tree.item(child_iid, 'text')}\t" + "\t".join(map(str, self.tree.item(child_iid, "values"))))
        
        if len(text_lines) > 1: 
            self.root.clipboard_clear()
            self.root.clipboard_append("\n".join(text_lines))

    def _reconfigure_treeview(self):
        """
        Sets up the Treeview columns based on the currently loaded datasets.
        
        This method is called whenever datasets are added or removed. It sets
        the number of columns, their headers (using dataset display names),
        and default widths.
        """
        if not self.datasets:
            self.tree.configure(show="tree", columns=()); self.tree.heading("#0", text="")
            return

        column_ids = tuple(d.key_path for d in self.datasets)
        self.tree.configure(show="tree headings", columns=column_ids)
        self.tree.heading("#0", text="Parameter")
        self.tree.column("#0", width=250, anchor="w", minwidth=200)

        for ds in self.datasets:
            self.tree.heading(ds.key_path, text=ds.display_name, anchor="center")
            self.tree.column(ds.key_path, width=150, anchor="center", minwidth=100)

    def _toggle_plot_pane(self):
        """Shows or hides the right-hand plot pane."""
        is_visible = self.plots_visible.get()
        if is_visible:
            # Hide plots, expand table
            self.right_plot_container.grid_forget()
            self.table_frame.grid_configure(columnspan=2, padx=(10, 10))
            self.hide_plots_button.configure(text="Show Plots")
        else:
            # Show plots, shrink table
            self.table_frame.grid_configure(columnspan=1, padx=(10, 2))
            self.right_plot_container.grid(row=2, column=1, sticky="nsew", padx=(2, 10), pady=5)
            self.hide_plots_button.configure(text="Hide Plots")
        self.plots_visible.set(not is_visible)

    def _on_container_resize(self, event=None):
        """
        Debounces resize events for the plot container to avoid excessive redraws.
        """
        if self._resize_job: self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(250, self._update_plot_grid)

    def _reconfigure_plot_area(self):
        """
        Reinitializes the plot area.
        
        This clears the plot toggle menu and rebuilds it with the current datasets.
        It also recreates the scrollable canvas to ensure a clean state before
        redrawing the plots.
        """
        self.plot_toggle_menu.delete(0, "end")
        for ds in self.datasets:
            self.plot_toggle_menu.add_checkbutton(label=ds.display_name, variable=ds.is_plotted_var, command=self._update_plot_grid)

        if hasattr(self, 'plots_canvas') and self.plots_canvas:
            self.plots_canvas.destroy()

        self.plots_canvas = ctk.CTkScrollableFrame(self.right_plot_container, label_text="")
        self.plots_canvas.grid(row=1, column=0, sticky="nsew")
        self.plots_canvas.grid_columnconfigure(0, weight=1)
        self.plots_canvas.grid_columnconfigure(1, weight=1)
        self._update_plot_grid()

    def _show_plot_toggle_menu(self):
        """Displays the menu for toggling individual plot visibility."""
        self.plot_toggle_menu.tk_popup(self.plot_toggle_button.winfo_rootx(), self.plot_toggle_button.winfo_rooty() + self.plot_toggle_button.winfo_height())

    def _update_plot_grid(self):
        """
        Renders the scan geometry plots for all visible datasets.
        
        It calculates the optimal grid layout (1 or 2 columns) and cell size
        based on the container's width, then iterates through visible datasets,
        creating a frame for each and requesting a plot image from the
        PlottingService.
        """
        if not self.plots_canvas or not self.plots_canvas.winfo_exists(): return
        for widget in self.plots_canvas.winfo_children(): widget.destroy()

        plots_to_render = [ds for ds in self.datasets if ds.is_plotted_var.get()]
        if not plots_to_render: return

        self.root.update_idletasks()

        # Determine layout (1 or 2 columns)
        num_cols = 2 if len(plots_to_render) > 1 else 1
        container_width = self.plots_canvas._current_width if hasattr(self.plots_canvas, '_current_width') else self.plots_canvas.winfo_width()
        if container_width < 100: container_width = 800  # Default fallback width

        # Calculate cell dimensions
        cell_width_px = max(50, (container_width // num_cols) - 25)
        cell_height_px = max(50, int(cell_width_px * 0.8))

        for i, ds in enumerate(plots_to_render):
            row, col = divmod(i, num_cols)
            self.plots_canvas.grid_rowconfigure(row, minsize=cell_height_px)
            
            plot_frame = ctk.CTkFrame(self.plots_canvas, fg_color="transparent", width=cell_width_px, height=cell_height_px)
            plot_frame.grid(row=row, column=col, sticky="nsew", padx=5, pady=5)
            plot_frame.grid_propagate(False)

            ctk_image = self.plotter.create_plot_image(ds, cell_width_px, cell_height_px)
            if ctk_image:
                plot_label = ctk.CTkLabel(plot_frame, image=ctk_image, text="")
                plot_label.pack(fill="both", expand=True)
                # Add hover effect to show full dataset name in status bar
                for widget in [plot_frame, plot_label]:
                    widget.bind("<Enter>", lambda e, name=ds.display_name: self._set_status_bar_text(name))
                    widget.bind("<Leave>", lambda e: self._set_status_bar_text(""))

    def _truncate_text(self, text: str, max_width_px: int, font: Font) -> str:
        """
        Truncates a string to fit within a given pixel width, adding an ellipsis.

        This is used for long filenames in dropdown menus. It tries to preserve
        both the start and end of the string.

        Args:
            text (str): The text to truncate.
            max_width_px (int): The maximum allowed width in pixels.
            font (Font): The font used for measuring the text width.

        Returns:
            str: The truncated string, or the original if it fits.
        """
        if not text or font.measure(text) <= max_width_px: return text
        
        ellipsis = "..."
        basename, extension = os.path.splitext(text)
        
        if not extension or not basename: # Fallback for texts without extensions
            for i in range(len(text) // 2, 0, -1):
                if font.measure(f"{text[:i]}{ellipsis}{text[len(text)-i:]}") <= max_width_px:
                    return f"{text[:i]}{ellipsis}{text[len(text)-i:]}"
            return ""

        available_width = max_width_px - font.measure(extension)
        if available_width <= font.measure(ellipsis): return ellipsis + extension

        # Try to keep start and end of the basename
        for i in range(len(basename) // 2, 0, -1):
            if font.measure(f"{basename[:i]}{ellipsis}{basename[len(basename)-i:]}") <= available_width:
                return f"{basename[:i]}{ellipsis}{basename[len(basename)-i:]}{extension}"

        # Fallback to truncating just the end of the basename
        for i in range(len(basename) - 1, 0, -1):
            if font.measure(f"{basename[:i]}{ellipsis}") <= available_width:
                return f"{basename[:i]}{ellipsis}{extension}"
                
        return ellipsis + extension

    def _set_status_bar_text(self, full_text: str):
        """
        Updates the status bar text and stores the full text for the tooltip.
        """
        self.status_label_full_text = full_text
        self.status_bar_label.configure(text=full_text)

    def _on_tree_motion(self, event: tk.Event):
        """
        Updates the status bar with the full column header text on hover.

        Args:
            event (tk.Event): The mouse motion event.
        """
        region = self.tree.identify_region(event.x, event.y)
        if region == "heading":
            col_id = self.tree.identify_column(event.x)
            if col_id != "#0":  # Not the "Parameter" column
                try:
                    col_index = int(col_id.replace('#', '')) - 1
                    if 0 <= col_index < len(self.datasets):
                        self._set_status_bar_text(self.datasets[col_index].display_name)
                        return
                except (ValueError, IndexError): pass
        self._set_status_bar_text("")

    def export_scan_windows(self):
        """
        Exports the isolation window definitions for the selected dataset.
        
        The format of the export depends on the scan mode of the active segment
        (dia-PASEF, diagonal-PASEF, or PASEF).
        """
        selected_name = self.remove_var.get()
        if not selected_name or selected_name == "-": return messagebox.showwarning("No Selection", "Please select a dataset to export.")
        full_name = self.dropdown_name_map.get(selected_name)
        dataset = next((d for d in self.datasets if d.display_name == full_name), None)
        if not dataset or not dataset.segments: return

        active_segment = dataset.segments[dataset.active_segment_index]
        base_name, _ = os.path.splitext(dataset.display_name)

        # Map scan mode IDs to their respective data conversion functions and filenames
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
        """Converts a dia-PASEF DataFrame to the 'diaParameters.txt' format."""
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
        """Converts diagonal-PASEF data to the 'diagonalSlices.txt' format."""
        if not diag_params: return ""
        p = diag_params
        try: 
            start_im, end_im = float(seg_params.get("calc_im_start", 0)), float(seg_params.get("calc_im_end", 0))
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
        """Converts PASEF polygon data to a two-column text format."""
        if not polygon_data: return ""
        mass, mobility = polygon_data
        return "Mass [m/z],Mobility [1/K0]\n" + "\n".join(f"{m:.4f},{im:.4f}" for m, im in zip(mass, mobility))

    def _show_add_menu(self):
        """Displays the 'Add Data' menu below its button."""
        self.add_menu.tk_popup(self.add_menu_button.winfo_rootx(), self.add_menu_button.winfo_rooty() + self.add_menu_button.winfo_height())

    def _update_remove_menu(self):
        """
        Updates the file selection dropdown with truncated names of loaded datasets.
        
        It handles potential name collisions after truncation by adding suffixes.
        It also preserves the current selection if possible.
        """
        self.dropdown_name_map.clear()
        if not self.datasets:
            self.remove_menu.configure(values=["-"])
            self.remove_var.set("-")
            return
            
        self.root.update_idletasks() # Ensure widget has its correct size
        max_width = self.remove_menu.winfo_width() - 30
        
        display_names = []
        for d in self.datasets:
            trunc_name = self._truncate_text(d.display_name, max_width, self.optionmenu_font)
            original_trunc, count = trunc_name, 2
            # Handle potential duplicates after truncation
            while trunc_name in self.dropdown_name_map:
                base = original_trunc.rsplit('...', 1)[0] if '...' in original_trunc else original_trunc
                trunc_name = f"{base} ({count})"
                count += 1
            display_names.append(trunc_name)
            self.dropdown_name_map[trunc_name] = d.display_name
            
        self.remove_menu.configure(values=display_names)
        
        # Try to maintain the previous selection
        current_full = self.dropdown_name_map.get(self.remove_var.get())
        if not current_full or current_full not in [d.display_name for d in self.datasets]:
            self.remove_var.set(display_names[0] if display_names else "-")
        else:
            for t, f in self.dropdown_name_map.items():
                if f == current_full: 
                    self.remove_var.set(t)
                    break

    def _show_export_menu(self):
        """Displays the 'Export' menu below its button."""
        self.export_menu.tk_popup(self.export_menu_button.winfo_rootx(), self.export_menu_button.winfo_rooty() + self.export_menu_button.winfo_height())

    def _open_report_generator_dialog(self):
        """Opens the dialog for generating a method report for the active dataset."""
        selected_name = self.remove_var.get()
        if not selected_name or selected_name == "-": return messagebox.showwarning("No Selection", "Please select a dataset to export.")
        
        dataset = next((d for d in self.datasets if d.display_name == self.dropdown_name_map.get(selected_name)), None)
        if not dataset or not dataset.segments: return

        # Late import to avoid circular dependency
        from .report_generator_window import ReportGeneratorWindow

        # Determine the initial set of parameters to show in the report dialog
        if self.displayed_params is not None:
            initial_params = self.displayed_params # Use current view
        else:
            initial_params = self.loader.get_default_parameters_for_dataset(dataset)

        initial_param_keys = {self._get_param_key(p) for p in initial_params}

        # Find all other available (but not currently shown) parameters
        all_additional_params = [
            p for p in (dataset.default_params + dataset.available_optional_params)
            if self._get_param_key(p) not in initial_param_keys
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
        """Loads all PNG icon assets from the assets folder."""
        try:
            assets = resource_path("assets")
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
            
            gh_logo_original = Image.open(os.path.join(assets, "GitHub_Logo.png"))
            self.github_icon = ctk.CTkImage(
                light_image=gh_logo_original,
                dark_image=gh_logo_original,
                size=(49, 20) 
            )
        except FileNotFoundError as e:
            self.logger.warning(f"Could not load icon files: {e}")

    def _toggle_show_differences(self):
        """
        Toggles the 'Show only differences' feature and redraws the table.
        """
        new_state = not self.show_only_diffs_var.get()
        self.show_only_diffs_var.set(new_state)
        self.show_diffs_button.configure(image=self.diffs_checked_icon if new_state else self.diffs_unchecked_icon)
        self._update_treeview_data()

    def _show_about_dialog(self):
        """Opens the custom 'About' dialog window."""
        AboutDialog(self.root, self.about_icon, self.github_icon)