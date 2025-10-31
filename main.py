# main.py

import os
import logging
import tkinter as tk
import customtkinter as ctk
from tkinterdnd2 import TkinterDnD
from PIL import Image, ImageTk
import sys
import ctypes

log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(log_formatter)
early_logger = logging.getLogger()
early_logger.addHandler(console_handler)
early_logger.setLevel(logging.DEBUG)

early_logger.info(">>> main.py: Starting execution <<<")

from utils import resource_path
from app_config import AppConfig
from services import DataLoaderService, PlottingService, ReportGeneratorService
from ui.main_window import timsCompareApp
from logger_setup import setup_logging
from settings import LOGGING_ENABLED

early_logger.debug(">>> main.py: Imports successful <<<")

if sys.platform == 'win32':
    ctypes.windll.shcore.SetProcessDpiAwareness(1)

class DndCTk(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.TkdndVersion = TkinterDnD._require(self)


if __name__ == "__main__":
    early_logger.debug(">>> main.py: Inside __main__ block <<<")
    if LOGGING_ENABLED:
        from tkinter import messagebox
        log_setup_error = setup_logging()
        if log_setup_error:
            temp_root = tk.Tk()
            temp_root.withdraw()
            messagebox.showwarning("Logging Issue", log_setup_error, parent=temp_root)
            temp_root.destroy()
        else:
            logging.basicConfig(level=logging.WARNING)


    logger = logging.getLogger(__name__)
    logger.info("timsCompare starting...")
    logger.debug(">>> main.py: Creating AppConfig <<<")
    config = AppConfig()
    logger.debug(">>> main.py: Setting appearance mode <<<")

    ctk.set_appearance_mode("dark")
    logger.debug(">>> main.py: Attempting to load theme file <<<")
    try:
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
             base_path = sys._MEIPASS
        elif getattr(sys, 'frozen', False):
             base_path = os.path.dirname(sys.executable)
        else:
             base_path = os.path.dirname(os.path.abspath(__file__))

        theme_file_path = os.path.join(base_path, 'blue_theme.json')

        logger.debug(f"Looking for theme file at: {theme_file_path}")

        if os.path.exists(theme_file_path):
            ctk.set_default_color_theme(theme_file_path)
            logger.info(f"Successfully loaded theme file: {theme_file_path}")
        else:
            logger.warning(f"Theme file not found at '{theme_file_path}'. Using default 'blue' theme.")
            ctk.set_default_color_theme("blue")
    except Exception as e:
        logger.error(f"Failed during theme file loading: {e}. Using default 'blue' theme.", exc_info=True)
        ctk.set_default_color_theme("blue")
        
    logger.debug(">>> main.py: Creating DndCTk root window <<<")
    root = DndCTk()
    
    logger.debug(">>> main.py: Creating services <<<")
    data_loader = DataLoaderService(config)
    plot_service = PlottingService()
    report_generator = ReportGeneratorService(plot_service, config, data_loader)
        
    logger.debug(">>> main.py: Creating timsCompareApp instance <<<")
    app = timsCompareApp(root, config, data_loader, plot_service, report_generator)
    app.root.title("timsCompare")
    
    try:
        icon_path_assets = resource_path('assets/icon.ico')
        if os.path.exists(icon_path_assets):
             root.iconbitmap(icon_path_assets)
             logger.debug(f"Set icon from assets: {icon_path_assets}")
        else: 
             icon_path_root = os.path.join(base_path, 'icon.ico')
             if os.path.exists(icon_path_root):
                  root.iconbitmap(icon_path_root)
                  logger.debug(f"Set icon from root: {icon_path_root}")
             else:
                  logger.warning(f"Icon file not found at '{icon_path_assets}' or '{icon_path_root}'")
    except Exception as e:
        logger.warning(f"Failed to set window icon: {e}")
    
    logger.debug(">>> main.py: Starting mainloop <<<")
    root.mainloop()
    logger.debug(">>> main.py: Mainloop finished <<<")