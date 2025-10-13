import os
import json
import re
import xml.etree.ElementTree as ET
from tkinter import messagebox
from typing import List, Dict, Optional, Any
import logging

from settings import ENABLE_DEBUG_LOGGING
from _config_data import CONFIG_DATA

PARAMETER_DEPENDENCY_MAP = {
    "IMS_imeX_RampStart": "IMS_imeX_Mode",
    "IMS_imeX_RampEnd": "IMS_imeX_Mode",
    "IMS_imeX_RampTime": "IMS_imeX_Mode",
    "IMS_imeX_AccumulationTime": "IMS_imeX_Mode"
}

class AppConfig:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.theme_path = os.path.join("config", "blue_theme.json")
        
        self._all_definitions: Optional[List[Dict]] = None
        self._parameter_definitions: Optional[List[str]] = None
        self._display_name_map: Optional[Dict[str, str]] = None
        
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

    @property
    def display_name_map(self) -> Dict[str, str]:
        if self._display_name_map is None:
            self._display_name_map = self._load_properties_from_config("display_name_map.properties")
        return self._display_name_map

    def _parse_properties_content(self, content: str) -> Dict[str, str]:
        prop_map = {}
        pattern = re.compile(r"^\s*([a-zA-Z0-9_]+)\s*=\s*(.*)")
        
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue

            match = pattern.match(line)
            if match:
                key, value = match.groups()
                key = key.strip()
                value = value.strip().encode('latin-1', 'backslashreplace').decode('unicode-escape')
                if not key.endswith(("_tooltip", "_custom_tooltip")):
                    prop_map[key] = value       
        return prop_map

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
            self.logger.debug("Could not parse VALUETEXT: %s", value_text)
            return None

    def _load_definitions_from_cfg_files(self) -> List[Dict]:
        self.logger.info("Loading all parameter definitions from embedded config files...")
        all_params = []
        loaded_count = 0
        skipped_count = 0
        
        display_names = self.display_name_map

        manual_label_overrides = {
            "IMS_ATS_Active": "TIMS Stepping",
            "Internal_SWCompatibilityUseIMS": "TIMS",
            "Ims_Stepping_Active": "MS/MS Stepping",
            "TOF_DetectorTof_HighSensitivity_Enabled": "High Sensitivity Detection",
            "Collision_Energy_Offset_Set": "Collision Energy Offset"
        }

        for key, content_string in CONFIG_DATA.items():
            if not key.lower().endswith('.cfg'):
                continue
            
            self.logger.debug("Parsing definitions from: %s", key)
            
            try:
                xml_root = ET.fromstring(content_string)
                group_element = xml_root.find(".//GROUP/DISPLAYNAME")
                group_name = group_element.text.strip() if group_element is not None and group_element.text else "General"
                
                param_elements = xml_root.findall(".//VARIABLES/*")
                if not param_elements:
                    param_elements = xml_root.findall(".//*[PERMANENTNAME]")

                self.logger.debug("Found %d potential parameter definitions in %s.", len(param_elements), key)

                for param_element in param_elements:
                    permname_el = param_element.find("PERMANENTNAME")
                    if permname_el is None or not permname_el.text:
                        skipped_count += 1
                        continue
                    
                    permname = permname_el.text.strip()
                    param_def = {"permname": permname, "category": group_name}

                    if permname in PARAMETER_DEPENDENCY_MAP:
                        param_def["lookup_driven_by"] = PARAMETER_DEPENDENCY_MAP[permname]
                    
                    if permname in display_names:
                        param_def["label"] = display_names[permname]
                    else:
                        label_el = param_element.find("DISPLAYNAME")
                        param_def["label"] = label_el.text.strip() if label_el is not None and label_el.text else permname
                    
                    if permname in manual_label_overrides:
                        param_def["label"] = manual_label_overrides[permname]

                    unit_el = param_element.find("UNIT")
                    if unit_el is not None and unit_el.text: param_def["unit"] = unit_el.text.strip()
                    
                    vf_el = param_element.find("VALUEFORMAT")
                    if vf_el is not None and vf_el.text:
                        match = re.search(r'%\.(\d+)f', vf_el.text)
                        if match: param_def["round_to"] = int(match.group(1))
                    
                    dep_el = param_element.find("DEPENDENCY")
                    if dep_el is not None and dep_el.text and 'P' in dep_el.text: param_def["is_polarity_dependent"] = True
                    
                    use_el = param_element.find("USE")
                    if use_el is not None and use_el.text: param_def["location"] = use_el.text.strip()
                    
                    valuetext_el = param_element.find("VALUETEXT")
                    if valuetext_el is not None and valuetext_el.text: param_def["value_map"] = self._parse_valuetext(valuetext_el.text)
                    
                    type_el = param_element.find("TYPE")
                    if type_el is not None and type_el.text and type_el.text.strip().lower() == 'bool':
                        param_def["type"] = "boolean"

                    all_params.append(param_def)
                    loaded_count += 1

            except ET.ParseError as e:
                self.logger.error("XML parsing error in embedded file %s: %s", key, e)
                messagebox.showerror("Configuration Error", f"Error parsing embedded XML from: {key}\n\n{e}")
        
        self.logger.info("Parameter definition loading complete. Loaded: %d, Skipped: %d", loaded_count, skipped_count)
        all_params.sort(key=lambda x: x.get('label', x.get('permname', '')))
        return all_params

    def _load_json_from_file(self, file_name: str) -> List[Any]:
        try:
            json_key = next(key for key in CONFIG_DATA if key.endswith(file_name))
            json_string = CONFIG_DATA[json_key]
            return json.loads(json_string)
        except (StopIteration, json.JSONDecodeError) as e:
            self.logger.error("Failed to load or parse embedded JSON %s: %s", file_name, e)
            messagebox.showerror("Configuration Error", f"Could not load or parse embedded file: {file_name}\n\nDetails: {e}")
            return []
            
    def _load_properties_from_config(self, file_name: str) -> Dict[str, str]:
        try:
            prop_key = next(key for key in CONFIG_DATA if key.endswith(file_name))
            content_string = CONFIG_DATA[prop_key]
            return self._parse_properties_content(content_string)
        except StopIteration:
            self.logger.debug("Display name map file not found: %s. Using defaults.", file_name)
            return {}
        except Exception as e:
            self.logger.error("Failed to load or parse embedded properties file %s: %s", file_name, e)
            messagebox.showerror("Configuration Error", f"Could not load or parse embedded properties file: {file_name}\n\nDetails: {e}")
            return {}