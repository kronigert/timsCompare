import os
import tkinter as tk
import pandas as pd
import json
import io
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
        self.ion_polarity: Optional[str] = None 
        self.parameters: Dict[str, Any] = {}
        
        self.dia_windows_data: Optional[pd.DataFrame] = None
        self.diagonal_pasef_data: Optional[Any] = None 
        self.pasef_polygon_data: Optional[List[List[Tuple[float, float]]]] = None
        
        self.xml_scope_element: Optional[ET.Element] = None

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "start_time": self.start_time,
            "end_time": self.end_time,
            "end_time_display": self.end_time_display,
            "is_calibration_segment": self.is_calibration_segment,
            "workflow_name": self.workflow_name,
            "scan_mode_id": self.scan_mode_id,
            "ion_polarity": self.ion_polarity, 
            "parameters": self.parameters,
            "pasef_polygon_data": self.pasef_polygon_data
        }

        if self.dia_windows_data is not None and not self.dia_windows_data.empty:
            data["dia_windows_data"] = self.dia_windows_data.to_dict(orient='records')
        
        if self.diagonal_pasef_data is not None:
            if isinstance(self.diagonal_pasef_data, pd.DataFrame):
                data["diagonal_pasef_data"] = {
                    "type": "dataframe",
                    "content": self.diagonal_pasef_data.to_dict(orient='records')
                }
            else:
                data["diagonal_pasef_data"] = {
                    "type": "dict",
                    "content": self.diagonal_pasef_data
                }

        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Segment':
        """Restore segment from dictionary."""
        seg = cls(data["start_time"], data["end_time"])
        seg.end_time_display = data.get("end_time_display", "")
        seg.is_calibration_segment = data.get("is_calibration_segment", False)
        seg.workflow_name = data.get("workflow_name")
        seg.scan_mode_id = data.get("scan_mode_id")
        seg.ion_polarity = data.get("ion_polarity") 
        seg.parameters = data.get("parameters", {})
        
        seg.pasef_polygon_data = data.get("pasef_polygon_data")

        if "dia_windows_data" in data:
            try:
                seg.dia_windows_data = pd.DataFrame(data["dia_windows_data"])
            except Exception:
                pass 

        if "diagonal_pasef_data" in data:
            diag_entry = data["diagonal_pasef_data"]
            if diag_entry.get("type") == "dataframe":
                try:
                    seg.diagonal_pasef_data = pd.DataFrame(diag_entry["content"])
                except Exception:
                    pass
            elif diag_entry.get("type") == "dict":
                seg.diagonal_pasef_data = diag_entry["content"]

        return seg

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
        
        self.available_sources: List[str] = []
        
        self.xml_content: Optional[str] = None 
        self.xml_root: Optional[ET.Element] = None

    def get_parameter_value(self, permname: str) -> Any:
        try:
            active_segment = self.segments[self.active_segment_index]
            return active_segment.parameters.get(permname)
        except IndexError:
            return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key_path": self.key_path,
            "display_name": self.display_name,
            "instrument_model": self.instrument_model,
            "tims_control_version": self.tims_control_version,
            "last_modified_date": self.last_modified_date,
            "active_segment_index": self.active_segment_index,
            "is_plotted": self.is_plotted_var.get(),
            "default_params": self.default_params,
            "available_optional_params": self.available_optional_params,
            "available_sources": self.available_sources,
            "xml_content": self.xml_content,
            "segments": [s.to_dict() for s in self.segments]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Dataset':
        """Restore dataset from dictionary."""
        ds = cls(data.get("key_path", "Unknown"))
        ds.display_name = data.get("display_name", "Unknown Dataset")
        ds.instrument_model = data.get("instrument_model")
        ds.tims_control_version = data.get("tims_control_version")
        ds.last_modified_date = data.get("last_modified_date")
        ds.active_segment_index = data.get("active_segment_index", 0)
        ds.is_plotted_var = tk.BooleanVar(value=data.get("is_plotted", True))
        
        ds.default_params = data.get("default_params", [])
        ds.available_optional_params = data.get("available_optional_params", [])
        ds.available_sources = data.get("available_sources", [])
        ds.xml_content = data.get("xml_content")
        
        ds.segments = [Segment.from_dict(s_data) for s_data in data.get("segments", [])]
        
        return ds