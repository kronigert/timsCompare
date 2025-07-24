import os
import tkinter as tk
import pandas as pd
from typing import Optional, Any, Dict, List, Tuple

class Segment:
    """
    A data model that encapsulates all information for a single segment
    within an instrument method.
    """
    def __init__(self, start_time: float, end_time: float):
        """
        Initializes a Segment object.

        Args:
            start_time: The start time of the segment in minutes.
            end_time: The end time of the segment in minutes.
        """
        self.start_time: float = start_time
        self.end_time: float = end_time
        self.end_time_display: str = f"{end_time:.2f} min"
        
        self.workflow_name: Optional[str] = None
        self.scan_mode_id: Optional[int] = None  # NEW: Store the numeric ID
        self.parameters: Dict[str, Any] = {}
        
        self.dia_windows_data: Optional[pd.DataFrame] = None
        self.diagonal_pasef_data: Optional[pd.DataFrame] = None
        self.pasef_polygon_data: Optional[Tuple] = None

class Dataset:
    """
    A data model that encapsulates all information for a single loaded
    instrument method folder (e.g., a .d or .m folder).
    """
    def __init__(self, key_path: str):
        self.key_path: str = key_path
        self.display_name: str = os.path.basename(key_path)
        self.method_file_path: Optional[str] = None
        self.sqlite_path: Optional[str] = None
        self.segments: List[Segment] = []
        self.active_segment_index: int = 0
        self.is_plotted_var = tk.BooleanVar(value=True)

        # --- NEW: Store discovered parameters ---
        self.default_params: List[Dict] = []
        self.available_optional_params: List[Dict] = []
        self.user_added_params: List[Dict] = [] # For params added via the dialog
        self.xml_root: Optional[ET.Element] = None # To support reparsing
        
    def get_parameter_value(self, permname: str) -> Any:
        """
        Safely retrieves a parameter value from the currently active segment.

        Args:
            permname: The 'permname' of the parameter to retrieve.

        Returns:
            The parameter's value from the active segment, or None if it does not exist.
        """
        try:
            active_segment = self.segments[self.active_segment_index]
            return active_segment.parameters.get(permname)
        except IndexError:
            # This can happen if no segments are loaded or the index is invalid.
            return None