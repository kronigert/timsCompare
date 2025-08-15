"""
Defines the core data models for the application.

This module contains simple data-holding classes (`Segment` and `Dataset`) that
represent the parsed information from an instrument method. These classes have no
business logic and serve as the primary data structures passed between the
service and UI layers, adhering to the "Separation of Concerns" principle.
"""
import os
import tkinter as tk
import xml.etree.ElementTree as ET
from typing import Optional, Any, Dict, List, Tuple

import pandas as pd


class Segment:
    """
    A data model that encapsulates all information for a single segment
    within an instrument method.
    """
    def __init__(self, start_time: float, end_time: float):
        """
        Initializes a Segment object.

        Args:
            start_time (float): The start time of the segment in minutes.
            end_time (float): The end time of the segment in minutes.
        """
        # --- Basic Segment Information ---
        self.start_time: float = start_time
        self.end_time: float = end_time
        self.end_time_display: str = f"{end_time:.2f} min" if end_time < float('inf') else "end"
        
        # --- Method and Parameter Data ---
        self.workflow_name: Optional[str] = None
        self.scan_mode_id: Optional[int] = None
        # A dictionary holding all parsed parameter key-value pairs for this segment.
        self.parameters: Dict[str, Any] = {}
        
        # --- Scan Geometry Data (for plotting and export) ---
        self.dia_windows_data: Optional[pd.DataFrame] = None
        self.diagonal_pasef_data: Optional[Dict] = None
        self.pasef_polygon_data: Optional[Tuple] = None


class Dataset:
    """
    A data model that encapsulates all information for a single loaded
    instrument method folder (e.g., a .d or .m folder).

    This class acts as a container for all segments and associated metadata
    for one complete method file.
    """
    def __init__(self, key_path: str):
        """
        Initializes a Dataset object.

        Args:
            key_path (str): The absolute path to the method folder (e.g., 'C:/.../method.d').
                            This path is used as a unique identifier for the dataset.
        """
        # --- File and Path Information ---
        self.key_path: str = key_path
        self.display_name: str = os.path.basename(key_path)
        self.method_file_path: Optional[str] = None
        self.sqlite_path: Optional[str] = None
        
        # --- Segments and State ---
        self.segments: List[Segment] = []
        self.active_segment_index: int = 0
        
        # --- UI-specific State ---
        # A Tkinter variable to control plot visibility in the main window.
        self.is_plotted_var = tk.BooleanVar(value=True)
        
        # --- Parameter Definition Storage ---
        # List of parameter definitions determined to be the default set for this dataset.
        self.default_params: List[Dict] = []
        # List of all other parameter definitions found in the method's config files.
        self.available_optional_params: List[Dict] = []
        
        # --- Raw Data ---
        # The parsed XML root of the method's main configuration file.
        self.xml_root: Optional[ET.Element] = None
        
    def get_parameter_value(self, permname: str, segment_index: Optional[int] = None) -> Any:
        """
        Safely retrieves a parameter value from a specific or active segment.

        Args:
            permname (str): The 'permname' of the parameter to retrieve.
            segment_index (Optional[int]): The index of the segment to get the value
                                           from. If None, the currently active
                                           segment is used.

        Returns:
            The parameter's value, or None if the segment or parameter does not exist.
        """
        try:
            target_index = self.active_segment_index if segment_index is None else segment_index
            active_segment = self.segments[target_index]
            return active_segment.parameters.get(permname)
        except IndexError:
            return None