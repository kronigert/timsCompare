import os
import tkinter as tk
import pandas as pd
from typing import Optional, Any, Dict, List, Tuple
import xml.etree.ElementTree as ET

class Segment:
    def __init__(self, start_time: float, end_time: float):
        self.start_time: float = start_time
        self.end_time: float = end_time
        self.end_time_display: str = f"{end_time:.2f} min"
        self.is_calibration_segment: bool = False
        
        self.workflow_name: Optional[str] = None
        self.scan_mode_id: Optional[int] = None 
        self.parameters: Dict[str, Any] = {}
        
        self.dia_windows_data: Optional[pd.DataFrame] = None
        self.diagonal_pasef_data: Optional[pd.DataFrame] = None
        self.pasef_polygon_data: Optional[Tuple] = None
        self.xml_scope_element: Optional[ET.Element] = None

class Dataset:
    def __init__(self, key_path: str):
        self.key_path: str = key_path
        self.display_name: str = os.path.basename(key_path)
        self.method_file_path: Optional[str] = None
        self.sqlite_path: Optional[str] = None
        self.segments: List[Segment] = []
        self.active_segment_index: int = 0
        self.is_plotted_var = tk.BooleanVar(value=True)

        self.instrument_model: Optional[str] = None
        self.tims_control_version: Optional[str] = None
        self.last_modified_date: Optional[str] = None

        self.default_params: List[Dict] = []
        self.available_optional_params: List[Dict] = []
        self.user_added_params: List[Dict] = [] 
        self.xml_root: Optional[ET.Element] = None
        self.available_sources: List[str] = []
        
    def get_parameter_value(self, permname: str) -> Any:
        try:
            active_segment = self.segments[self.active_segment_index]
            return active_segment.parameters.get(permname)
        except IndexError:
            return None