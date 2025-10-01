# utils.py

import logging
import logging.handlers
from typing import Any, Dict

import settings

import sys
import os

def format_parameter_value(value: Any, param_config: Dict) -> str:
    if value is None or value == '':
        return "N/A"

    value_map = param_config.get("value_map")
    if value_map and str(value) in value_map:
        return value_map[str(value)]

    permname = param_config.get("permname")

    param_type = param_config.get("type")
    if (param_type == "boolean") or (permname and permname.endswith("Switch")):
        return "On" if str(value) in ["1", "true", "True"] else "Off"
            
    if permname == "calc_advanced_ce_ramping_display_list" and isinstance(value, list):
        return f"List ({len(value)} items)"
    if permname in ["IMS_PolygonFilter_Mass", "IMS_PolygonFilter_Mobility"] and isinstance(value, list):
        return f"Polygon ({len(value)} points)"
    if isinstance(value, list):
        return f"List ({len(value)} items)"
        
    formatted_string = ""
    try:
        numeric_value = float(value)
        round_to = param_config.get("round_to")
        if round_to is not None:
            formatted_string = f"{numeric_value:.{int(round_to)}f}"
        else:
            formatted_string = str(value)
    except (ValueError, TypeError):
        formatted_string = str(value)

    unit = param_config.get("unit")
    if unit and formatted_string != "N/A":
        return f"{formatted_string} {unit}"
    else:
        return formatted_string
    
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    final_path = os.path.join(base_path, relative_path)
    return final_path

def apply_dark_title_bar(window):
    if sys.platform == 'win32':
        try:
            import ctypes
            
            window.update_idletasks() 
            hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20 
            
            value = ctypes.c_int(2) # 2 = Enable dark mode, 0 = Disable
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(value), ctypes.sizeof(value))
        except Exception as e:
            print(f"Failed to apply dark title bar: {e}")