"""
Manages the application's configuration by parsing and providing access to settings.

This module defines the AppConfig class, which is responsible for loading all
parameter definitions from the embedded .cfg files and parsing JSON files that
control UI layouts (e.g., the default parameter view). It uses a lazy-loading
approach to parse these configurations only when they are first requested.
"""
import json
import logging
import re
import xml.etree.ElementTree as ET
from tkinter import messagebox
from typing import List, Dict, Optional, Any

from _config_data import CONFIG_DATA

# Defines special cases where the value of one parameter is used as a lookup
# key (e.g., an index) for another. This is primarily used for parameters
# stored in arrays within the method files.
# Format: { "dependent_parameter": "driving_parameter" }
PARAMETER_DEPENDENCY_MAP = {
    "IMS_imeX_RampStart": "IMS_imeX_Mode",
    "IMS_imeX_RampEnd": "IMS_imeX_Mode",
    "IMS_imeX_RampTime": "IMS_imeX_Mode",
}


class AppConfig:
    """
    Centralized handler for all application configuration data.

    This class provides access to parameter definitions and UI layout settings
    by parsing them from the embedded `CONFIG_DATA` source. It uses a
    lazy-loading pattern: data is parsed from the source strings only upon
    first access and then cached for subsequent calls.
    """
    def __init__(self):
        """Initializes the AppConfig, setting placeholders for lazy-loaded properties."""
        self.logger = logging.getLogger(__name__)
        self._all_definitions: Optional[List[Dict]] = None
        self._parameter_definitions: Optional[Dict[str, List[str]]] = None
        
    @property
    def all_definitions(self) -> List[Dict]:
        """
        Provides a comprehensive list of all parameter definitions.

        Lazily loads and parses all .cfg files from the embedded config data
        on its first call.

        Returns:
            List[Dict]: A sorted list of dictionaries, where each dictionary
                        represents the definition of a single parameter.
        """
        if self._all_definitions is None:
            self.logger.debug("First access to 'all_definitions', parsing .cfg files...")
            self._all_definitions = self._load_definitions_from_cfg_files()
        return self._all_definitions

    @property
    def parameter_definitions(self) -> Dict[str, List[str]]:
        """
        Provides the default parameter view configurations for different workflows.

        Lazily loads and parses the `parameter_definitions.json` file on its
        first call.

        Returns:
            Dict[str, List[str]]: A dictionary mapping workflow names to an
                                  ordered list of parameter permanent names.
        """
        if self._parameter_definitions is None:
            self.logger.debug("First access to 'parameter_definitions', parsing JSON file...")
            self._parameter_definitions = self._load_json_from_file("parameter_definitions.json")
        return self._parameter_definitions

    def _parse_valuetext(self, value_text: str) -> Optional[Dict[str, str]]:
        """
        Parses the VALUETEXT string from a .cfg file into a lookup dictionary.

        This handles two observed formats:
        - "key1:value1;key2:value2"
        - "key1|value1,key2|value2"

        Args:
            value_text (str): The string content from a VALUETEXT tag.

        Returns:
            Optional[Dict[str, str]]: A dictionary mapping codes to human-readable
                                      values, or None if parsing fails.
        """
        if not value_text:
            return None
        value_map = {}
        try:
            # Determine delimiters based on content
            delimiter, separator = (':', ';') if ';' in value_text else ('|', ',')
            for pair in value_text.split(separator):
                if delimiter in pair:
                    key, value = pair.split(delimiter, 1)
                    value_map[key.strip()] = value.strip()
            return value_map if value_map else None
        except ValueError:
            self.logger.warning(f"Could not parse VALUETEXT string: {value_text}")
            return None

    def _load_definitions_from_cfg_files(self) -> List[Dict]:
        """
        Parses all embedded .cfg files to build a master list of parameter definitions.

        Iterates through the `CONFIG_DATA` dictionary, finds all entries
        ending in .cfg, parses them as XML, and extracts metadata for each
        parameter definition within them.

        Returns:
            List[Dict]: A list of all parameter definition dictionaries found.
        """
        all_params = []
        loaded_count = 0
        skipped_count = 0
        
        cfg_keys = [key for key in CONFIG_DATA if key.lower().endswith('.cfg')]
        self.logger.debug(f"Found {len(cfg_keys)} embedded .cfg files to parse.")

        for key in cfg_keys:
            content_string = CONFIG_DATA[key]
            try:
                # The first character is often a BOM (Byte Order Mark), remove it if present.
                if content_string.startswith('\ufeff'):
                    content_string = content_string[1:]

                xml_root = ET.fromstring(content_string)
                group_element = xml_root.find(".//GROUP/DISPLAYNAME")
                group_name = group_element.text.strip() if group_element is not None and group_element.text else "General"
                
                for param_element in xml_root.findall(".//VARIABLES/*"):
                    permname_el = param_element.find("PERMANENTNAME")
                    if permname_el is None or not permname_el.text:
                        skipped_count += 1
                        continue
                    
                    permname = permname_el.text.strip()
                    param_def = {"permname": permname, "category": group_name, "source": key}

                    # Check for special lookup dependencies
                    if permname in PARAMETER_DEPENDENCY_MAP:
                        param_def["lookup_driven_by"] = PARAMETER_DEPENDENCY_MAP[permname]

                    # Extract label, falling back to permanent name
                    label_el = param_element.find("DISPLAYNAME")
                    param_def["label"] = label_el.text.strip() if label_el is not None and label_el.text else permname
                    
                    # Extract unit
                    if (unit_el := param_element.find("UNIT")) is not None and unit_el.text:
                        param_def["unit"] = unit_el.text.strip()
                    
                    # Extract rounding precision from format string (e.g., "%.2f")
                    if (vf_el := param_element.find("VALUEFORMAT")) is not None and vf_el.text:
                        if match := re.search(r'%\.(\d+)f', vf_el.text):
                            param_def["round_to"] = int(match.group(1))
                    
                    # Check for polarity dependency
                    if (dep_el := param_element.find("DEPENDENCY")) is not None and dep_el.text and 'P' in dep_el.text:
                        param_def["is_polarity_dependent"] = True
                    
                    # Extract location (e.g., 'method', 'instrument')
                    if (use_el := param_element.find("USE")) is not None and use_el.text:
                        param_def["location"] = use_el.text.strip()
                    
                    # Parse value maps for enumerated types
                    if (valuetext_el := param_element.find("VALUETEXT")) is not None and valuetext_el.text:
                        param_def["value_map"] = self._parse_valuetext(valuetext_el.text)
                    
                    all_params.append(param_def)
                    loaded_count += 1
            except ET.ParseError as e:
                self.logger.error(f"Error parsing embedded XML from '{key}': {e}")
                messagebox.showerror("Configuration Error", f"Error parsing embedded XML from: {key}\n\n{e}")
        
        self.logger.debug(f"Successfully loaded {loaded_count} parameter definitions, skipped {skipped_count}.")
        all_params.sort(key=lambda x: x.get('label', x.get('permname', '')))
        return all_params

    def _load_json_from_file(self, file_name: str) -> Any:
        """
        Loads and parses a specified JSON file from the embedded CONFIG_DATA.

        Args:
            file_name (str): The name of the JSON file to load (e.g., "blue_theme.json").

        Returns:
            Any: The parsed JSON content, typically a list or dictionary. Returns
                 an empty list on failure.
        """
        try:
            json_key = next(key for key in CONFIG_DATA if key.endswith(file_name))
            json_string = CONFIG_DATA[json_key]
            return json.loads(json_string)
        except (StopIteration, json.JSONDecodeError) as e:
            self.logger.error(f"Could not load or parse embedded file '{file_name}': {e}")
            messagebox.showerror("Configuration Error", f"Could not load or parse embedded file: {file_name}\n\nDetails: {e}")
            return []