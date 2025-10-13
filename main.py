# main.py

import os
import logging
import tkinter as tk
import customtkinter as ctk
from tkinterdnd2 import TkinterDnD
from PIL import Image, ImageTk
import sys
import ctypes

from utils import resource_path
from app_config import AppConfig
from services import DataLoaderService, PlottingService, ReportGeneratorService
from ui.main_window import timsCompareApp
from logger_setup import setup_logging
from settings import LOGGING_ENABLED


if sys.platform == 'win32':
    ctypes.windll.shcore.SetProcessDpiAwareness(1)

class DndCTk(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.TkdndVersion = TkinterDnD._require(self)


if __name__ == "__main__":
    if LOGGING_ENABLED:
        from tkinter import messagebox

        log_setup_error = setup_logging()
        if log_setup_error:
            temp_root = tk.Tk()
            temp_root.withdraw()
            messagebox.showwarning("Logging Issue", log_setup_error, parent=temp_root)
            temp_root.destroy()


    logger = logging.getLogger(__name__)
    logger.info("timsCompare starting...")

    config = AppConfig()

    ctk.set_appearance_mode("dark")
    theme_file_path = resource_path(config.theme_path)

    if os.path.exists(theme_file_path):
        ctk.set_default_color_theme(theme_file_path)
    else:
        logger.warning(f"Theme file not found at {theme_file_path}. Using default 'blue' theme.")
        ctk.set_default_color_theme("blue")

    root = DndCTk()
    
    data_loader = DataLoaderService(config)
    plot_service = PlottingService()
    report_generator = ReportGeneratorService(plot_service, config, data_loader)
        
    app = timsCompareApp(root, config, data_loader, plot_service, report_generator)
    app.root.title("timsCompare")
    
    try:
        icon_path = resource_path('assets/icon.ico')
        root.iconbitmap(icon_path)
    except Exception as e:
        logger.warning(f"Failed to set window icon from '{icon_path}': {e}")

    root.mainloop()