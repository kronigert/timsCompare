import os
import customtkinter as ctk
from tkinterdnd2 import TkinterDnD

from app_config import AppConfig
from services import DataLoaderService, PlottingService, ReportGeneratorService
from ui.main_window import timsCompareApp

if __name__ == "__main__":
    # The application's root window must be created from TkinterDnD.Tk()
    # to enable drag-and-drop functionality across the entire application.
    root = TkinterDnD.Tk()
    
    # --- Centralized Initialization (Dependency Injection) ---
    config = AppConfig()
    data_loader = DataLoaderService(config)
    plot_service = PlottingService()
    # MODIFIED: Inject the plotting service into the report generator service
    report_generator = ReportGeneratorService(plot_service, config)

    # Apply CustomTkinter appearance and theme settings.
    ctk.set_appearance_mode("dark")
    if os.path.exists(config.theme_path):
        ctk.set_default_color_theme(config.theme_path)
    else:
        # Fallback to a default theme if the custom JSON file is not found.
        print(f"Warning: Theme file not found at {config.theme_path}. Using default 'blue' theme.")
        ctk.set_default_color_theme("blue")
        
    # --- Set Application Name and Icon ---
    app = timsCompareApp(root, config, data_loader, plot_service, report_generator)
    app.root.title("timsCompare")
    try:
        app.root.iconbitmap("icon.ico")
    except tk.TclError:
        print("Warning: 'icon.ico' not found. The application will use the default icon.")
        
   # Start the Tkinter event loop, which waits for user interaction.
    root.mainloop()