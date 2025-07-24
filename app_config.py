import os
import json
import re  # Import regular expression module
import xml.etree.ElementTree as ET
from tkinter import messagebox
from typing import List, Dict, Optional, Any

from settings import ENABLE_DEBUG_LOGGING

PARAMETER_DEPENDENCY_MAP = {
    "IMS_imeX_RampStart": "IMS_imeX_Mode",
    "IMS_imeX_RampEnd": "IMS_imeX_Mode",
    "IMS_imeX_RampTime": "IMS_imeX_Mode",
}

class AppConfig:
    """
    Manages loading and providing access to application configuration files.
    This class now discovers and parses all .cfg files for parameter definitions.
    """
    def __init__(self):
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_dir = os.path.join(self.script_dir, "config")
        self.theme_path = os.path.join(self.config_dir, "blue_theme.json")
        
        self._all_definitions: Optional[List[Dict]] = None
        self._parameter_definitions: Optional[List[str]] = None
        
    @property
    def all_definitions(self) -> List[Dict]:
        if self._all_definitions is None:
            self._all_definitions = self._load_definitions_from_cfg_files()
        return self._all_definitions

    @property
    def parameter_definitions(self) -> List[str]:
        if self._parameter_definitions is None:
            self._parameter_definitions = self._load_json_from_file("parameter_definitions.json")
        return self._parameter_definitions

    def _parse_valuetext(self, value_text: str) -> Optional[Dict[str, str]]:
        if not value_text: return None
        value_map = {}
        try:
            delimiter, separator = (':', ';') if ';' in value_text else ('|', ',')
            for pair in value_text.split(separator):
                if delimiter in pair:
                    key, value = pair.split(delimiter, 1)
                    value_map[key.strip()] = value.strip()
            return value_map if value_map else None
        except ValueError:
            if ENABLE_DEBUG_LOGGING:
                print(f"  [DEBUG] Could not parse VALUETEXT: {value_text}")
            return None

    def _load_definitions_from_cfg_files(self) -> List[Dict]:
        if ENABLE_DEBUG_LOGGING:
            print("--- [DEBUG] Loading parameter definitions from .cfg files... ---")
        all_params = []
        if not os.path.exists(self.config_dir):
            messagebox.showwarning("Configuration Warning", f"Config directory not found:\n{self.config_dir}")
            return []

        for root, _, files in os.walk(self.config_dir):
            for file in files:
                if file.lower().endswith(".cfg"):
                    file_path = os.path.join(root, file)
                    try:
                        tree = ET.parse(file_path)
                        xml_root = tree.getroot()
                        group_element = xml_root.find(".//GROUP/DISPLAYNAME")
                        group_name = group_element.text.strip() if group_element is not None and group_element.text else "General"
                        
                        for param_element in xml_root.findall(".//VARIABLES/*"):
                            permname_el = param_element.find("PERMANENTNAME")
                            if permname_el is None or not permname_el.text: continue
                            
                            permname = permname_el.text.strip()
                            param_def = {"permname": permname, "category": group_name}

                            if permname in PARAMETER_DEPENDENCY_MAP:
                                param_def["lookup_driven_by"] = PARAMETER_DEPENDENCY_MAP[permname]

                            label_el = param_element.find("DISPLAYNAME")
                            param_def["label"] = label_el.text.strip() if label_el is not None and label_el.text else param_def["permname"]

                            unit_el = param_element.find("UNIT")
                            if unit_el is not None and unit_el.text:
                                param_def["unit"] = unit_el.text.strip()
                            
                            # --- NEW: Parse VALUEFORMAT for rounding info ---
                            vf_el = param_element.find("VALUEFORMAT")
                            if vf_el is not None and vf_el.text:
                                match = re.search(r'%\.(\d+)f', vf_el.text)
                                if match:
                                    param_def["round_to"] = int(match.group(1))
                            # -----------------------------------------------
                            
                            dep_el = param_element.find("DEPENDENCY")
                            if dep_el is not None and dep_el.text and 'P' in dep_el.text:
                                param_def["is_polarity_dependent"] = True
                            
                            use_el = param_element.find("USE")
                            if use_el is not None and use_el.text:
                                param_def["location"] = use_el.text.strip()
                            
                            valuetext_el = param_element.find("VALUETEXT")
                            if valuetext_el is not None and valuetext_el.text:
                                param_def["value_map"] = self._parse_valuetext(valuetext_el.text)
                            
                            all_params.append(param_def)
                    except ET.ParseError as e:
                        messagebox.showerror("Configuration Error", f"Error parsing XML file: {file}\n\n{e}")
        
        if ENABLE_DEBUG_LOGGING:
            print(f"--- [DEBUG] Total parameters loaded from .cfg files: {len(all_params)} ---\n")
        
        all_params.sort(key=lambda x: x.get('label', x.get('permname', '')))
        return all_params

    def _load_json_from_file(self, file_name: str) -> List[Any]:
        file_path = os.path.join(self.config_dir, file_name)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            messagebox.showerror("Configuration Error", f"Could not find the file:\n{file_path}")
            return []
        except json.JSONDecodeError as e:
            messagebox.showerror("Configuration Error", f"Error reading the JSON file:\n{file_path}\n\nDetails: {e}")
            return []