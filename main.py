"""
The main entry point for the timsCompare application.

This script orchestrates the entire application startup sequence:
1. Initializes the centralized logging system.
2. Creates the main Tkinter window with drag-and-drop capabilities.
3. Instantiates the core services (config, data loading, plotting, reporting)
   following a Dependency Injection pattern.
4. Sets the application's visual theme using CustomTkinter.
5. Instantiates the main application UI class (`timsCompareApp`) and injects the
   necessary services.
6. Sets the window icon.
7. Starts the Tkinter main event loop to run the application.
"""
import logging
import os
import tkinter as tk

import customtkinter as ctk
from PIL import Image, ImageTk
from tkinterdnd2 import TkinterDnD

from app_config import AppConfig
from logger_setup import setup_logging
from services import DataLoaderService, PlottingService, ReportGeneratorService
from ui.main_window import timsCompareApp
from utils import resource_path


if __name__ == "__main__":
    # 1. Configure Logging
    # Set up the application-wide logger as the very first step.
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Application starting...")

    # 2. Create the main application window with Drag & Drop support
    # TkinterDnD.Tk() is used instead of tk.Tk() to enable the drag-and-drop
    # functionality across the application.
    root = TkinterDnD.Tk()
    
    # 3. Instantiate core services (Dependency Injection)
    # Each major piece of application logic is encapsulated in a service.
    # These services are created here and passed to the UI components that need them.
    config = AppConfig()
    data_loader = DataLoaderService(config)
    plot_service = PlottingService()
    report_generator = ReportGeneratorService(plot_service, config, data_loader)

    # 4. Configure UI theme
    ctk.set_appearance_mode("dark")
    theme_file_path = resource_path("config/blue_theme.json")

    if os.path.exists(theme_file_path):
        logger.debug(f"Loading custom theme from: {theme_file_path}")
        ctk.set_default_color_theme(theme_file_path)
    else:
        logger.warning(f"Theme file not found at {theme_file_path}. Using default 'blue' theme.")
        ctk.set_default_color_theme("blue")
        
    # 5. Create and run the main application UI
    # The main application class is instantiated, and all required services
    # are injected into it.
    app = timsCompareApp(root, config, data_loader, plot_service, report_generator)
    app.root.title("timsCompare")
    
    # 6. Set the window icon
    # This block attempts to load the application icon and set it for the main window.
    try:
        icon_path = resource_path('assets/icon.ico')
        image = Image.open(icon_path)
        icon_image = ImageTk.PhotoImage(image)
        
        # Keep a reference to the image to prevent garbage collection.
        root.icon = icon_image
        
        app.root.iconphoto(True, icon_image)
        logger.debug("Application icon set successfully.")
    except Exception as e:
        logger.warning(f"Failed to set window icon from '{icon_path}': {e}")

    # 7. Start the main event loop
    # This call starts the Tkinter event loop, which draws the UI and waits
    # for user interaction. The application will run until this window is closed.
    root.mainloop()