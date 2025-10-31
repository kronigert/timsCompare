# app_config.py

import os
import json
import re
import xml.etree.ElementTree as ET
from tkinter import messagebox
from typing import List, Dict, Optional, Any
import logging

from settings import ENABLE_DEBUG_LOGGING
from _config_data import CONFIG_DATA

USER_CONFIG_DIR = os.path.join(os.path.expanduser('~'), '.timsCompare')
USER_VIEW_DEFINITIONS_FILENAME = "user_view_definitions.json"

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

        self.user_view_definitions_path = os.path.join(USER_CONFIG_DIR, USER_VIEW_DEFINITIONS_FILENAME)
        
        self._all_definitions: Optional[List[Dict]] = None
        self._parameter_definitions: Optional[Dict[str, List[str]]] = None
        self._parameter_definitions: Optional[List[str]] = None
        self._display_name_map: Optional[Dict[str, str]] = None
        self._third_party_licenses: Optional[Dict] = None
        
    @property
    def all_definitions(self) -> List[Dict]:
        if self._all_definitions is None:
            self._all_definitions = self._load_definitions_from_cfg_files()
        return self._all_definitions

    @property
    def parameter_definitions(self) -> Dict[str, List[str]]:
        if self._parameter_definitions is not None:
            return self._parameter_definitions

        if os.path.exists(self.user_view_definitions_path):
            self.logger.info(f"Loading user-defined view definitions from: {self.user_view_definitions_path}")
            try:
                with open(self.user_view_definitions_path, 'r', encoding='utf-8') as f:
                    user_defs = json.load(f)
                
                if isinstance(user_defs, dict) and '__GENERAL__' in user_defs:
                    self._parameter_definitions = user_defs
                    return self._parameter_definitions
                else:
                    self.logger.warning("User view definitions file is malformed. Falling back to default.")
            except (IOError, json.JSONDecodeError) as e:
                self.logger.warning(f"User view definitions file is corrupt or unreadable ({e}). Falling back to default.")
        
        self.logger.info("Loading factory default view definitions.")
        default_defs = self._load_json_from_file("parameter_definitions.json")
        
        if isinstance(default_defs, dict):
             self._parameter_definitions = default_defs
        else:
             self.logger.error("Factory default parameter_definitions.json is not a dict! Using empty config.")
             self._parameter_definitions = {} 
             
        return self._parameter_definitions

    @property
    def display_name_map(self) -> Dict[str, str]:
        if self._display_name_map is None:
            self._display_name_map = self._load_properties_from_config("display_name_map.properties")
        return self._display_name_map

    @property
    def third_party_licenses(self) -> Dict[str, Dict[str, str]]:
        if self._third_party_licenses is None:
            self._third_party_licenses = self._load_json_from_file("third_party_licenses.json")
        return self._third_party_licenses

    def get_embedded_config_content(self, relative_path: str) -> Optional[str]:
        normalized_key = relative_path.replace('\\', '/')
        content = CONFIG_DATA.get(normalized_key)
        if content is None:
             base_name_key = os.path.basename(normalized_key)
             content = CONFIG_DATA.get(base_name_key)
             if content:
                 self.logger.debug(f"Found embedded content using basename key: {base_name_key}")
             else:
                 self.logger.warning(f"Embedded config content not found for key '{normalized_key}' or basename '{base_name_key}'.")
        else:
             self.logger.debug(f"Found embedded content using key: {normalized_key}")
        return content

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
            "Collision_Energy_Offset_Set": "Collision Energy Offset",
            "Energy_Ramping_Advanced_Settings_Active": "Advanced Energy Ramping"
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

    def _load_json_from_file(self, file_name: str) -> Dict[str, Any]:
        json_string = self.get_embedded_config_content(file_name)
        if not json_string:
            self.logger.error(f"Failed to load embedded JSON content for: {file_name}")
            messagebox.showerror("Configuration Error", f"Could not load embedded file: {file_name}")
            return {}
        try:
            return json.loads(json_string)
        except json.JSONDecodeError as e:
            self.logger.error("Failed to parse embedded JSON %s: %s", file_name, e)
            messagebox.showerror("Configuration Error", f"Could not parse embedded file: {file_name}\n\nDetails: {e}")
            return {} 
            
    def _load_properties_from_config(self, file_name: str) -> Dict[str, str]:
        content_string = self.get_embedded_config_content(file_name)
        if not content_string:
            self.logger.warning(f"Embedded properties file not found: {file_name}. Using defaults.")
            return {}
        try:
            return self._parse_properties_content(content_string)
        except Exception as e:
            self.logger.error("Failed to load or parse embedded properties file %s: %s", file_name, e)
            messagebox.showerror("Configuration Error", f"Could not load or parse embedded properties file: {file_name}\n\nDetails: {e}")
            return {}
            
    def get_embedded_config_content(self, relative_path: str) -> Optional[str]:
        normalized_key = relative_path.replace('\\', '/')
        content = CONFIG_DATA.get(normalized_key)
        if content is None:
             base_name_key = os.path.basename(normalized_key)
             content = CONFIG_DATA.get(base_name_key)
             if content:
                 self.logger.debug(f"Found embedded content using basename key: {base_name_key}")
             else:
                 self.logger.warning(f"Embedded config content not found for key '{normalized_key}' or basename '{base_name_key}'.")
        else:
             self.logger.debug(f"Found embedded content using key: {normalized_key}")
        return content
    
    def get_factory_default_views(self) -> Dict[str, List[str]]:
        self.logger.info("Loading factory default view definitions directly.")
        
        default_defs = self._load_json_from_file("parameter_definitions.json")
        
        if isinstance(default_defs, dict):
             return default_defs
        else:
             self.logger.error("Factory default parameter_definitions.json is not a dict! Using empty config.")
             return {}