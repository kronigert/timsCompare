"""
Provides centralized, stateless utility functions for the application.

This module contains common helper functions that are shared across different
parts of the application, such as the UI and service layers. Adhering to the
DRY (Don't Repeat Yourself) principle, these utilities handle tasks like value
formatting and resource path resolution.
"""

import os
import sys
from typing import Any, Dict



def format_parameter_value(value: Any, param_config: Dict) -> str:
    """
    Centralized function to format a raw parameter value into a user-friendly string.

    This function applies a set of rules to convert a parameter's raw value
    into a display-ready string, based on its configuration dictionary.
    The formatting rules include:
    - Handling None or empty values.
    - Mapping codified values to readable text (e.g., '0' -> 'Off').
    - Formatting boolean-like values as 'On'/'Off'.
    - Summarizing lists with an item count.
    - Applying numeric rounding to a specified number of decimal places.
    - Appending units where applicable.

    Args:
        value (Any): The raw value of the parameter.
        param_config (Dict): The configuration dictionary for the parameter,
                             containing keys like 'value_map', 'round_to', 'unit', etc.

    Returns:
        str: The formatted, user-friendly string.
    """
    if value is None or value == '':
        return "N/A"

    # Use value_map for direct lookups (e.g., '0' -> 'Positive')
    value_map = param_config.get("value_map")
    if value_map and str(value) in value_map:
        return value_map[str(value)]

    permname = param_config.get("permname")

    # Handle boolean-like parameters
    param_type = param_config.get("type")
    if (param_type == "boolean") or (permname and permname.endswith("Switch")):
        return "On" if str(value) in ["1", "true", "True"] else "Off"
    
    # Provide summary text for list-based parameters in the main table view
    if permname == "calc_advanced_ce_ramping_display_list" and isinstance(value, list):
        return f"List ({len(value)} items)"
    if permname in ["IMS_PolygonFilter_Mass", "IMS_PolygonFilter_Mobility"] and isinstance(value, list):
        return f"Polygon ({len(value)} points)"
    if isinstance(value, list):
        return f"List ({len(value)} items)"
    
    # Handle numeric formatting and rounding
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

    # Append unit if defined
    unit = param_config.get("unit")
    if unit and formatted_string != "N/A":
        return f"{formatted_string} {unit}"
    else:
        return formatted_string
    
def resource_path(relative_path: str) -> str:
    """
    Get the absolute path to a resource, working for both development and PyInstaller.

    This function is critical for ensuring that assets (like icons and themes)
    can be found regardless of whether the application is running from source code
    or as a bundled, single-file executable. When packaged with PyInstaller,
    assets are extracted to a temporary directory, and the path to this directory
    is stored in `sys._MEIPASS`.

    Args:
        relative_path (str): The relative path to the resource from the project root
                             (e.g., 'assets/icon.ico').

    Returns:
        str: The absolute path to the resource.
    """
    try:
        # PyInstaller creates a temp folder and stores its path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # If _MEIPASS is not defined, we are in a development environment
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)