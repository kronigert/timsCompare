# services.py

import os
import json
import sqlite3
import xml.etree.ElementTree as ET
import io
import logging
import pandas as pd
import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches

from PIL import Image
import customtkinter as ctk
from typing import Optional, Any, List, Dict, Tuple, Callable
from fpdf import FPDF
import tempfile

from settings import ENABLE_DEBUG_LOGGING 
from app_config import AppConfig 
from data_model import Dataset, Segment 
from utils import format_parameter_value, resource_path 


class DataProcessingError(Exception): 
    pass
class MethodFileNotFoundError(DataProcessingError): 
    pass
class UnsupportedScanModeError(DataProcessingError): 
    pass
class ParsingError(DataProcessingError): 
    pass


class DataLoaderService: 
    def __init__(self, config: AppConfig): 
        self.config = config 
        self._find_cache = {} 
        self.logger = logging.getLogger(__name__) 

    def get_default_parameters_for_dataset(self, dataset: Dataset) -> List[Dict]: 
        return self.get_default_parameters_for_view([dataset]) 

    def get_default_parameters_for_view(self, datasets: List[Dataset]) -> List[Dict]: 
        if not datasets: 
            return [] 

        has_multisegment_file = any(len(ds.segments) > 1 for ds in datasets) 
        has_advanced_ce = any(s.parameters.get("Energy_Ramping_Advanced_Settings_Active") == '1' for ds in datasets for s in ds.segments) 
        has_standard_ce = any(s.parameters.get("Energy_Ramping_Advanced_Settings_Active") != '1' for ds in datasets for s in ds.segments) 
        has_icc_mode1 = any(s.parameters.get("IMSICC_Mode") == '1' for ds in datasets for s in ds.segments) 
        has_icc_mode2 = any(s.parameters.get("IMSICC_Mode") == '2' for ds in datasets for s in ds.segments) 
        has_msms_stepping = any(s.parameters.get("Ims_Stepping_Active") == '1' for ds in datasets for s in ds.segments)

        all_workflows_in_dataset = {s.workflow_name for ds in datasets for s in ds.segments if s.workflow_name} 
        default_params_by_workflow = self.config.parameter_definitions 

        default_permnames_ordered = [] 
        seen_permnames = set() 

        def add_unique(permnames): 
            for pname in permnames: 
                if pname not in seen_permnames: 
                    seen_permnames.add(pname) 
                    default_permnames_ordered.append(pname) 

        add_unique(default_params_by_workflow.get('__GENERAL__', [])) 
        for wf in sorted(list(all_workflows_in_dataset)):
            add_unique(default_params_by_workflow.get(wf, [])) 
        
        if "calc_scan_mode" in seen_permnames and "Mode_ScanMode" in seen_permnames: 
            default_permnames_ordered.remove("Mode_ScanMode") 

        all_definitions_map = {p['permname']: p for p in self.config.all_definitions} 
        default_param_configs = [] 

        for pname in default_permnames_ordered: 
            if pname in ["calc_segment_start_time", "calc_segment_end_time"] and not has_multisegment_file: continue 
            if pname in ["calc_ce_ramping_start", "calc_ce_ramping_end"] and not has_standard_ce: continue 
            if pname == "calc_advanced_ce_ramping_display_list" and not has_advanced_ce: continue 
            if pname == 'IMSICC_Target' and not has_icc_mode1: continue 
            if pname == 'calc_msms_stepping_display_list' and not has_msms_stepping: continue
            
            mode2_params = ["IMSICC_ICC2_MaxTicTargetPercent", "IMSICC_ICC2_MinAccuTime", "IMSICC_ICC2_ReferenceTicCapacity", "IMSICC_ICC2_SmoothingFactor"] 
            if pname in mode2_params and not has_icc_mode2: continue 

            param_config = all_definitions_map.get(pname)
            
            if not param_config:
                if pname.startswith("calc_"):
                    label_map = {
                        "calc_scan_area_mz": "Window Scan Area",
                        "calc_ramps": "Ramps per Cycle",
                        "calc_ms1_scans": "MS1 Scans per Cycle",
                        "calc_steps": "Isolation Steps per Cycle",
                        "calc_mz_width": "Isolation Window Width",
                        "calc_ce_ramping_start": "CE Ramping Start",
                        "calc_ce_ramping_end": "CE Ramping End",
                        "calc_msms_stepping_display_list": "MS/MS Stepping Details"
                    }
                    label = label_map.get(pname, pname.replace("calc_", "").replace("_", " ").title())
                    if "Stepping" in label:
                        category = "TIMS"
                    elif "Scan Mode" in label:
                        category = "Mode"
                    else:
                        category = "Calculated Parameters"
                    param_config = {"permname": pname, "label": label, "category": category}
                else:
                    param_config = {
                        "permname": pname,
                        "label": pname.replace("_", " "),
                        "category": "General" 
                    }

            if param_config:
                default_param_configs.append(param_config)
        
        final_params = [p for p in default_param_configs if p.get('permname') != 'Calibration_MarkSegment']
        
        return final_params

    def _discover_available_parameters(self, xml_root: ET.Element) -> Tuple[List[Dict], List[Dict]]: 
        all_definitions = self.config.all_definitions 
        
        defaults_by_workflow = self.config.parameter_definitions 
        default_param_permnames = set() 
        for workflow_permnames in defaults_by_workflow.values(): 
            default_param_permnames.update(workflow_permnames) 

        available_defaults = [p for p in all_definitions if p['permname'] in default_param_permnames] 
        
        available_optionals = [] 
        optional_definitions = [p for p in all_definitions if p['permname'] not in default_param_permnames] 
        
        found_optional_permnames = set() 
        for param_config in optional_definitions: 
            permname = param_config['permname'] 
            if xml_root.find(f".//*[@permname='{permname}']") is not None: 
                if permname not in found_optional_permnames: 
                    available_optionals.append(param_config) 
                    found_optional_permnames.add(permname) 
        return available_defaults, available_optionals 
    
    def _discover_available_sources(self, xml_root: ET.Element) -> List[str]:
        found_sources = set()
        for dep_element in xml_root.iter('dependent'):
            source_attr = dep_element.get('source')
            if source_attr:
                found_sources.add(source_attr)
        
        return sorted(list(found_sources))

    def load_dataset_from_folder(self, folder_path: str) -> Dataset: 
        self.logger.info(f"Attempting to load dataset from: {folder_path}") 
        self._find_cache.clear() 
        dataset = Dataset(key_path=folder_path) 
        method_file = self._find_file(folder_path, ["microtofqimpactemacquisition.method"]) 
        if not method_file: 
            error_msg = f"Could not find 'microtofqimpactemacquisition.method' in '{dataset.display_name}'." 
            self.logger.error(error_msg) 
            raise MethodFileNotFoundError(error_msg) 
            
        dataset.method_file_path = method_file 
        try: 
            tree = ET.parse(method_file, parser=ET.XMLParser(encoding="iso-8859-1")) 
            root = tree.getroot() 
            dataset.xml_root = root 
        except ET.ParseError as e: 
            error_msg = f"Failed to parse XML in {os.path.basename(method_file)}: {e}" 
            self.logger.error(error_msg, exc_info=True) 
            raise ParsingError(error_msg) 
        
        dataset.available_sources = self._discover_available_sources(root)
        self.logger.debug(f"Discovered {len(dataset.available_sources)} ion sources in method: {dataset.available_sources}")
        
        default_params, optional_params = self._discover_available_parameters(root) 
        dataset.default_params = default_params 
        dataset.available_optional_params = optional_params 
        
        all_defs_map = {p['permname']: p for p in self.config.all_definitions} 
        scan_mode_map = all_defs_map.get("Mode_ScanMode", {}).get("value_map", {}) 
        polarity_map = all_defs_map.get("Mode_IonPolarity", {}).get("value_map", {}) 
        segment_elements = root.findall('./method/qtofimpactemacq/timetable/segment') 
        instrument_element = root.find('instrument') 

        if not segment_elements: 
            new_segment = Segment(start_time=0.0, end_time=-1.0) 
            new_segment.end_time_display = "N/A" 
            method_element = root.find('method') 
            if method_element is None: raise ParsingError("Could not find the <method> tag in the file.") 
            new_segment.xml_scope_element = method_element 
            self._parse_and_populate_segment(new_segment, method_element, instrument_element, scan_mode_map, polarity_map, folder_path, {}) 
            dataset.segments.append(new_segment) 
        else: 
            last_end_time = 0.0 
            
            method_element = root.find('method') 
            if method_element is None: raise ParsingError("Could not find the <method> tag in the file.") 
            
            global_polarity_el = method_element.find(f".//*[@permname='Mode_IonPolarity']") 
            global_polarity_val = self._get_value_from_element(global_polarity_el, {}) or '0' 
            global_polarity_str = polarity_map.get(str(global_polarity_val)) #

            last_segment_params = self._parse_parameters_for_scope( 
                method_element, 
                instrument_element, 
                self.config.all_definitions, 
                global_polarity_str 
            ) 

            for seg_element in segment_elements: 
                end_time_str = seg_element.attrib.get("endtime", "-1") 
                try: 
                    end_time = float(end_time_str) 
                except ValueError: 
                    end_time = -1.0 
                
                new_segment = Segment(start_time=last_end_time, end_time=end_time) 
                
                if end_time < 0: 
                    new_segment.end_time_display = "Open End" 
                
                new_segment.xml_scope_element = seg_element 
                
                unfiltered_params_for_next_segment = self._parse_and_populate_segment(
                    new_segment, seg_element, instrument_element, 
                    scan_mode_map, polarity_map, folder_path, last_segment_params
                )
                dataset.segments.append(new_segment) 
                
                if end_time >= 0: 
                    last_end_time = end_time 
                
                last_segment_params = unfiltered_params_for_next_segment
        
        self.logger.info(f"Dataset '{dataset.display_name}' loaded successfully with {len(dataset.segments)} segment(s).") 

        if ENABLE_DEBUG_LOGGING: 
            known_permnames_set = {p['permname'] for p in self.config.all_definitions} 
            total_known_permnames = len(known_permnames_set) 
            
            self.logger.debug("--- Data Loading Summary for %s ---", dataset.display_name) 
            for i, segment in enumerate(dataset.segments): 
                found_with_values = sum(1 for p in segment.parameters if p in known_permnames_set) 
                
                self.logger.debug( 
                    "  Segment %d: Found values for %d of %d known parameters.", 
                    i + 1, 
                    found_with_values, 
                    total_known_permnames 
                ) 
            self.logger.debug("-------------------------------------------------") 
        
        return dataset 

    def _parse_and_populate_segment(self, new_segment: Segment, param_scope_element: ET.Element, 
                                     instrument_scope_element: Optional[ET.Element], 
                                     scan_mode_map: Dict, polarity_map: Dict, folder_path: str, previous_params: Dict) -> Dict:
        unfiltered_params = previous_params.copy() 
        
        current_polarity_el = param_scope_element.find(f".//*[@permname='Mode_IonPolarity']") 
        current_polarity_val = self._get_value_from_element(current_polarity_el, {}) 
        final_polarity_raw_val = current_polarity_val if current_polarity_val is not None else unfiltered_params.get("Mode_IonPolarity") 
        polarity_string = polarity_map.get(str(final_polarity_raw_val)) 

        parsed_values = self._parse_parameters_for_scope( 
            param_scope_element, 
            instrument_scope_element, 
            self.config.all_definitions, 
            polarity_string,
            ion_source=None 
        ) 
        unfiltered_params.update(parsed_values)
        
        all_defs_map = {p['permname']: p for p in self.config.all_definitions}
        ime_x_mode_to_index = {'0': 0, '1': 1, '2': 2, '3': 3, '4': 4}
        
        for permname, value in list(unfiltered_params.items()):
            if isinstance(value, list):
                param_config = all_defs_map.get(permname)
                if param_config:
                    driver_permname = param_config.get("lookup_driven_by")
                    if driver_permname:
                        driver_value = unfiltered_params.get(driver_permname)
                        if driver_value is not None:
                            try:
                                index = ime_x_mode_to_index.get(str(driver_value))
                                if index is not None and index < len(value):
                                    unfiltered_params[permname] = value[index]
                            except (ValueError, IndexError):
                                self.logger.warning(f"Could not resolve dependent parameter {permname} using driver {driver_permname} with value {driver_value}.")
        
        scan_mode_val = unfiltered_params.get("Mode_ScanMode") 
        workflow_name = scan_mode_map.get(str(scan_mode_val))
        
        if workflow_name is None: 
            raise UnsupportedScanModeError(f"Unsupported Scan Mode: '{scan_mode_val}' found in segment starting at {new_segment.start_time:.2f} min.") 

        new_segment.workflow_name = workflow_name
        
        try: 
            new_segment.scan_mode_id = int(scan_mode_val) 
        except (ValueError, TypeError): 
            new_segment.scan_mode_id = None 

        new_segment.parameters = unfiltered_params
        
        self._perform_calculations(new_segment, folder_path, polarity_map) 
        self._apply_conditional_logic(new_segment) 
        
        allowed_permnames = set(self.config.parameter_definitions.get('__GENERAL__', []))
        workflow_specific_params = self.config.parameter_definitions.get(workflow_name, [])
        allowed_permnames.update(workflow_specific_params)

        filtered_params = {}
        for permname, value in new_segment.parameters.items():
            if permname in allowed_permnames or permname.startswith("calc_"):
                filtered_params[permname] = value
        
        new_segment.parameters = filtered_params
        
        calibration_value = unfiltered_params.get("Calibration_MarkSegment")
        if calibration_value == "1":
            new_segment.is_calibration_segment = True

        return unfiltered_params

    def _perform_calculations(self, segment: Segment, folder_path: str, polarity_map: Dict): 
        for key in list(segment.parameters.keys()): 
            if key.startswith("calc_"): 
                del segment.parameters[key] 

        segment.parameters["calc_scan_mode"] = segment.workflow_name 
        final_polarity_val = segment.parameters.get("Mode_IonPolarity") 
        segment.ion_polarity = polarity_map.get(str(final_polarity_val), "Unknown").lower() 
        segment.parameters["calc_segment_start_time"] = f"{segment.start_time:.2f} min" 
        segment.parameters["calc_segment_end_time"] = segment.end_time_display 

        self._calculate_energy_ramping_params(segment)
        self._calculate_msms_stepping_params(segment)
        
        if segment.scan_mode_id == 6: # PASEF
            self._process_pasef_data(segment) 
        elif segment.scan_mode_id == 9: # dia-PASEF
            self._process_dia_pasef_data(segment, folder_path) 
        elif segment.scan_mode_id == 11: # diagonal-PASEF
            self._process_diagonal_pasef_data(segment, folder_path) 

    def _apply_conditional_logic(self, segment: Segment): 
        duty_cycle_lock = segment.parameters.get("IMS_imeX_DutyCycleLock") 
        if duty_cycle_lock == "1": 
            ramp_time_value = segment.parameters.get("IMS_imeX_RampTime") 
            if ramp_time_value is not None: 
                segment.parameters["IMS_imeX_AccumulationTime"] = ramp_time_value 

        icc_mode = segment.parameters.get("IMSICC_Mode")
        if icc_mode and icc_mode != '0':
            if "IMS_imeX_AccumulationTime" in segment.parameters:
                segment.parameters["IMS_imeX_AccumulationTime"] = "variable"
            if "IMS_imeX_DutyCycleLock" in segment.parameters:
                segment.parameters["IMS_imeX_DutyCycleLock"] = "variable"
            if "calc_cycle_time" in segment.parameters:
                segment.parameters["calc_cycle_time"] = "variable"

    def _get_value_from_element(self, element: Optional[ET.Element], config: Dict) -> Optional[Any]: 
        if element is None: 
            return None 
        entry_index = config.get("entry_index") 
        if entry_index is not None: 
            try: 
                return list(element)[int(entry_index)].get('value') 
            except (IndexError, TypeError, ValueError): 
                return None 
        if len(list(element)) > 0: 
            if list(element)[0].get('value') is not None: 
                 return [entry.get('value') for entry in element] 
            else: 
                 return [entry.text for entry in element] 
        return element.attrib.get("value") 

    def _parse_parameters_for_scope(self, method_scope_element: ET.Element, 
                                     instrument_scope_element: Optional[ET.Element], 
                                     param_info: List[Dict], 
                                     ion_polarity: Optional[str], 
                                     ion_source: Optional[str] = None) -> Dict:
        results = {} 
        all_param_defs_map = {p['permname']: p for p in self.config.all_definitions} 
        ime_x_mode_to_index = {'0': 0, '1': 1, '2': 2, '3': 3, '4': 4} 

        def find_and_get_value(p_config: Dict, current_results: Dict) -> Optional[Any]: 
            permname = p_config.get('permname') 
            if not permname: 
                return None 
                
            full_config = all_param_defs_map.get(permname, {}) 
            search_config = p_config.copy() 
            
            driver_permname = full_config.get("lookup_driven_by") 
            if driver_permname: 
                driver_value = current_results.get(driver_permname) 
                if driver_value is not None: 
                    dynamic_index = ime_x_mode_to_index.get(str(driver_value)) 
                    if dynamic_index is not None: 
                        search_config['entry_index'] = dynamic_index 

            location = full_config.get("location", "method") 
            search_root = instrument_scope_element if location == 'instrument' else method_scope_element 
            
            if search_root is None: return None 
            
            found_element = None 
            
            dependent_scopes = []
            for dep_element in search_root.iter('dependent'):
                pol_attr = dep_element.get('polarity')
                src_attr = dep_element.get('source')
                
                pol_match = pol_attr and ion_polarity and pol_attr.lower() == ion_polarity.lower()
                src_match = src_attr and ion_source and src_attr.lower() == ion_source.lower()

                if pol_match and src_match:
                    dependent_scopes.insert(0, (3, dep_element)) # Priority 1 (most specific)
                elif pol_match:
                    dependent_scopes.append((2, dep_element)) # Priority 2
                elif src_match:
                    dependent_scopes.append((1, dep_element)) # Priority 3
            
            dependent_scopes.sort(key=lambda x: x[0], reverse=True)
            for _, scope in dependent_scopes:
                target = scope.find(f".//*[@permname='{permname}']")
                if target is not None:
                    found_element = target
                    break

            if found_element is None: 
                found_element = search_root.find(f".//*[@permname='{permname}']") 

            if found_element is None and location == 'method' and instrument_scope_element is not None: 
                found_element = instrument_scope_element.find(f".//*[@permname='{permname}']") 

            return self._get_value_from_element(found_element, search_config) 

        dependent_params = [] 
        independent_params = [] 
        for p in param_info: 
            permname = p.get('permname') 
            if permname and all_param_defs_map.get(permname, {}).get('lookup_driven_by'): 
                dependent_params.append(p) 
            else: 
                independent_params.append(p) 
        
        for p_config in independent_params: 
            value = find_and_get_value(p_config, results) 
            if value is not None: 
                results[p_config['permname']] = value 
                
        for p_config in dependent_params: 
            value = find_and_get_value(p_config, results) 
            if value is not None: 
                results[p_config['permname']] = value 
                
        return results 
    
    def get_parameter_value_for_source(self, dataset: Dataset, permname: str, ion_source: str) -> Any:
        try:
            active_segment = dataset.segments[dataset.active_segment_index]
            param_config = next((p for p in self.config.all_definitions if p['permname'] == permname), {'permname': permname})
            
            instrument_scope = dataset.xml_root.find('instrument') if dataset.xml_root else None
            
            values = self._parse_parameters_for_scope(
                method_scope_element=active_segment.xml_scope_element,
                instrument_scope_element=instrument_scope,
                param_info=[param_config],
                ion_polarity=active_segment.ion_polarity,
                ion_source=ion_source
            )
            return values.get(permname)
        except (IndexError, StopIteration) as e:
            self.logger.warning(f"Could not get parameter value for source '{ion_source}': {e}")
            return None

# In services.py -> DataLoaderService

    def _calculate_energy_ramping_params(self, segment: Segment):
        self.logger = logging.getLogger(__name__) # Ensure logger is available
        
        is_advanced_str = segment.parameters.get("Energy_Ramping_Advanced_Settings_Active") 
        is_advanced = (is_advanced_str == '1') 
        segment.parameters["calc_advanced_ce_ramping_display_list"] = None 

        if not is_advanced: 
            all_defs_map = {p['permname']: p for p in self.config.all_definitions} 
            ce_config = all_defs_map.get("Energy_Ramping_Collision_Energy_StartEnd", {}) 
            mobility_config = all_defs_map.get("Energy_Ramping_Mobility_StartEnd", {}) 
            
            ce_values = segment.parameters.get("Energy_Ramping_Collision_Energy_StartEnd") 
            mobility_values = segment.parameters.get("Energy_Ramping_Mobility_StartEnd") 
            
            ce_start_val, ce_end_val = (ce_values[0], ce_values[1]) if isinstance(ce_values, list) and len(ce_values) >= 2 else (None, None) 
            mob_start_val, mob_end_val = (mobility_values[0], mobility_values[1]) if isinstance(mobility_values, list) and len(mobility_values) >= 2 else (None, None) 

            if ce_start_val is not None and mob_start_val is not None: 
                formatted_ce_start = format_parameter_value(ce_start_val, ce_config) 
                formatted_mob_start = format_parameter_value(mob_start_val, mobility_config) 
                segment.parameters["calc_ce_ramping_start"] = f"{formatted_ce_start} @ {formatted_mob_start}" 
            else: 
                segment.parameters["calc_ce_ramping_start"] = "N/A" 

            if ce_end_val is not None and mob_end_val is not None: 
                formatted_ce_end = format_parameter_value(ce_end_val, ce_config) 
                formatted_mob_end = format_parameter_value(mob_end_val, mobility_config) 
                segment.parameters["calc_ce_ramping_end"] = f"{formatted_ce_end} @ {formatted_mob_end}" 
            else: 
                segment.parameters["calc_ce_ramping_end"] = "N/A" 
        else: 
            advanced_mobility_values_str = segment.parameters.get("Energy_Ramping_Advanced_ListMobilityValues") 
            advanced_ce_values_str = segment.parameters.get("Energy_Ramping_Advanced_ListCollisionEnergyValues") 
            advanced_entry_types_str = segment.parameters.get("Energy_Ramping_Advanced_ListEntryType") 
            formatted_entries = []
            
            # --- MODIFICATION START: Add logging and robust fallback ---
            self.logger.debug("Calculating Advanced CE Ramping:")
            self.logger.debug(f"  - Found Mobility Values: {advanced_mobility_values_str}")
            self.logger.debug(f"  - Found CE Values: {advanced_ce_values_str}")
            self.logger.debug(f"  - Found Entry Types: {advanced_entry_types_str}")

            if advanced_mobility_values_str and advanced_ce_values_str:
                try: 
                    mobility_values = [float(v) for v in advanced_mobility_values_str] 
                    ce_values = [float(v) for v in advanced_ce_values_str] 
                    
                    # If entry types are not defined, assume default type '0' (base) for all entries.
                    if advanced_entry_types_str:
                        entry_types = [int(v) for v in advanced_entry_types_str]
                    else:
                        self.logger.debug("  - EntryType list not found. Assuming default type '0' (base).")
                        entry_types = [0] * len(mobility_values)

                    if not (len(mobility_values) == len(ce_values) == len(entry_types)): 
                        raise ValueError("Mismatch in lengths of advanced ramping lists.") 

                    for i in range(len(mobility_values)): 
                        entry_type_str = "base" if entry_types[i] == 0 else "fixed" if entry_types[i] == 1 else str(entry_types[i]) 
                        formatted_entries.append(f"{entry_type_str} {ce_values[i]:.2f} eV @ {mobility_values[i]:.2f}") 
                    
                    self.logger.debug(f"  - Successfully generated advanced CE list: {formatted_entries}")
                    segment.parameters["calc_advanced_ce_ramping_display_list"] = formatted_entries 
                except (ValueError, TypeError) as e: 
                    self.logger.error(f"  - Error parsing advanced ramping values: {e}")
                    segment.parameters["calc_advanced_ce_ramping_display_list"] = [f"Error parsing advanced values: {e}"] 
            else: 
                self.logger.warning("  - Calculation skipped: Missing Mobility or CE value lists.")
                segment.parameters["calc_advanced_ce_ramping_display_list"] = ["No advanced values found"]
            # --- MODIFICATION END ---
            
            segment.parameters["calc_ce_ramping_start"] = "N/A" 
            segment.parameters["calc_ce_ramping_end"] = "N/A"

    def _calculate_msms_stepping_params(self, segment: Segment):
        if segment.parameters.get("Ims_Stepping_Active") != '1':
            segment.parameters['calc_msms_stepping_display_list'] = None
            return

        stepping_details = []
        all_defs_map = {p['permname']: p for p in self.config.all_definitions}

        ce_step1 = segment.parameters.get("Energy_Ramping_Collision_Energy_StartEnd")
        ce_step2 = segment.parameters.get("Energy_Ramping_Collision_Energy_StartEnd_Tims_Step_2")
        
        if ce_step1 and isinstance(ce_step1, list) and len(ce_step1) == 2:
            try:
                stepping_details.append(f"CE (Scan #1): {float(ce_step1[0]):.1f} - {float(ce_step1[1]):.1f} eV")
            except (ValueError, TypeError): pass
        if ce_step2 and isinstance(ce_step2, list) and len(ce_step2) == 2:
            try:
                stepping_details.append(f"CE (Scan #2): {float(ce_step2[0]):.1f} - {float(ce_step2[1]):.1f} eV")
            except (ValueError, TypeError): pass

        vector_params_map = [
            {"label": "Collision RF", "permname": "Ims_CollisionCellRF_Steps"},
            {"label": "Transfer Time", "permname": "Ims_TransferTimeSteps"},
            {"label": "Pre-Pulse Storage", "permname": "Ims_PrePulseStorageTimeSteps"}
        ]

        for param_map in vector_params_map:
            values = segment.parameters.get(param_map["permname"])
            if values is None and "alias" in param_map:
                values = segment.parameters.get(param_map["alias"])

            if isinstance(values, list):
                unit = all_defs_map.get(param_map["permname"], {}).get("unit", "")
                unit_str = f" {unit}" if unit else ""
                
                for i, value in enumerate(values):
                    try:
                        formatted_value = f"{float(value):.1f}"
                        stepping_details.append(f"{param_map['label']} (Scan #{i+1}): {formatted_value}{unit_str}")
                    except (ValueError, TypeError):
                        continue
        
        if stepping_details:
            segment.parameters['calc_msms_stepping_display_list'] = stepping_details
        else:
            segment.parameters['calc_msms_stepping_display_list'] = None

    def _process_pasef_data(self, segment: Segment): 
        mass_values_str = segment.parameters.get("IMS_PolygonFilter_Mass") 
        mobility_values_str = segment.parameters.get("IMS_PolygonFilter_Mobility") 
        
        segment.pasef_polygon_data = None 

        if mass_values_str is not None and mobility_values_str is not None: 
            try: 
                mass_values = [float(v) for v in mass_values_str if v is not None] 
                mobility_values = [float(v) for v in mobility_values_str if v is not None] 
                if mass_values and mobility_values: 
                    segment.pasef_polygon_data = (mass_values, mobility_values) 
            except (TypeError, ValueError): 
                segment.pasef_polygon_data = None 
        
        try: 
            num_ramps = int(segment.parameters.get("MSMS_Pasef_NumRampsPerCycle") or 0) 
            ramp_time = float(segment.parameters.get("IMS_imeX_RampTime") or 0) 
            quench_time = float(segment.parameters.get("Collision_QuenchTime_Set") or 0) 
            total_scans = num_ramps + 1 
            cycle_time_s = total_scans * (ramp_time + quench_time) / 1000 
            segment.parameters["calc_cycle_time"] = f"{cycle_time_s:.2f} s" 
        except (ValueError, TypeError): 
            segment.parameters["calc_cycle_time"] = "N/A" 
            
    def _process_dia_pasef_data(self, segment: Segment, search_path: str): 
        sqlite_file = self._find_file(search_path, ["diasettings.diasqlite"]) 
        if not sqlite_file:  
            self._initialize_dia_params_as_na(segment) 
            return 
        df = pd.DataFrame() 
        try: 
            conn = sqlite3.connect(f'file:{sqlite_file}?mode=ro', uri=True) 
            query = "SELECT Id, Type, CycleId, OneOverK0Start, OneOverK0End, IsolationMz, IsolationWidth FROM DiaWindowsSpecification" 
            df = pd.read_sql_query(query, conn) 
            conn.close() 
        except Exception: 
            self._initialize_dia_params_as_na(segment) 
            return 
        if df.empty: 
            segment.dia_windows_data = pd.DataFrame() 
            self._initialize_dia_params_as_na(segment) 
            return 
        if 'Type' not in df.columns or not pd.api.types.is_numeric_dtype(df['Type']): 
            segment.dia_windows_data = pd.DataFrame() 
            self._initialize_dia_params_as_na(segment) 
            return 
        pasef_scans_df = df[df['Type'] == 1].copy() 
        ms1_scans = len(df[df['Type'] == 0]) 
        segment.parameters["calc_ms1_scans"] = ms1_scans 
        if not pasef_scans_df.empty: 
            num_ramps = pasef_scans_df['CycleId'].max() 
            segment.parameters["calc_ramps"] = num_ramps 
            segment.parameters["calc_steps"] = pasef_scans_df['CycleId'].value_counts().max() 
            unique_widths = pasef_scans_df['IsolationWidth'].nunique() 
            segment.parameters["calc_mz_width"] = f"static ({pasef_scans_df['IsolationWidth'].iloc[0]:.1f})" if unique_widths == 1 else "variable" 
            min_mz_row = pasef_scans_df.loc[pasef_scans_df['IsolationMz'].idxmin()] 
            max_mz_row = pasef_scans_df.loc[pasef_scans_df['IsolationMz'].idxmax()] 
            segment.parameters["calc_scan_area_mz"] = f"{min_mz_row['IsolationMz'] - min_mz_row['IsolationWidth'] / 2:.2f} m/z - {max_mz_row['IsolationMz'] + max_mz_row['IsolationWidth'] / 2:.2f} m/z" 
            segment.parameters["calc_scan_area_im"] = f"{pasef_scans_df['OneOverK0Start'].min():.4f} - {pasef_scans_df['OneOverK0End'].max():.4f}" 
            try: 
                ramp_time_ms = float(segment.parameters.get("IMS_imeX_RampTime") or 0) 
                quench_time = float(segment.parameters.get("Collision_QuenchTime_Set") or 0) 
                total_scans = num_ramps + ms1_scans 
                cycle_time_s = total_scans * (ramp_time_ms + quench_time) / 1000 
                segment.parameters["calc_cycle_time"] = f"{cycle_time_s:.2f} s" 
            except (ValueError, TypeError): 
                segment.parameters["calc_cycle_time"] = "N/A" 
        else: 
            self._initialize_dia_params_as_na(segment, ms1_scans_only=True) 
        ramp_start_val = segment.parameters.get("IMS_imeX_RampStart") 
        ramp_end_val = segment.parameters.get("IMS_imeX_RampEnd") 
        global_ramp_start, global_ramp_end, use_global_limits = 0.0, 0.0, False 
        try: 
            global_ramp_start, global_ramp_end = float(ramp_start_val), float(ramp_end_val) 
            use_global_limits = True 
        except (ValueError, TypeError, AttributeError): pass 
        df_prepared = df.copy() 
        df_prepared['x_start'] = df_prepared['IsolationMz'] - (df_prepared['IsolationWidth'] / 2) 
        if use_global_limits and not df.empty: 
            min_k0_in_data, max_k0_in_data = df['OneOverK0Start'].min(), df['OneOverK0End'].max() 
            df_prepared['plot_y_start'] = df_prepared.apply(lambda r: global_ramp_start if r['OneOverK0Start'] == min_k0_in_data else r['OneOverK0Start'], axis=1) 
            df_prepared['plot_y_end'] = df_prepared.apply(lambda r: global_ramp_end if r['OneOverK0End'] == max_k0_in_data else r['OneOverK0End'], axis=1) 
        else: 
            df_prepared['plot_y_start'] = df_prepared['OneOverK0Start'] 
            df_prepared['plot_y_end'] = df_prepared['OneOverK0End'] 
        segment.dia_windows_data = df_prepared 

    def _initialize_dia_params_as_na(self, segment: Segment, ms1_scans_only=False): 
        if not ms1_scans_only: segment.parameters["calc_ms1_scans"] = "N/A" 
        segment.parameters["calc_ramps"] = "N/A" 
        segment.parameters["calc_steps"] = "N/A" 
        segment.parameters["calc_mz_width"] = "N/A" 
        segment.parameters["calc_scan_area_mz"] = "N/A" 
        segment.parameters["calc_scan_area_im"] = "N/A" 
        segment.parameters["calc_cycle_time"] = "N/A" 

    def _process_diagonal_pasef_data(self, segment: Segment, search_path: str): 
        sqlite_file = self._find_file(search_path, ["synchroSettings.syncsqlite"]) 
        if not sqlite_file: return 
        try: 
            conn = sqlite3.connect(f'file:{sqlite_file}?mode=ro', uri=True) 
            diag_df = pd.read_sql_query("SELECT * FROM Template", conn) 
            conn.close() 
            if not diag_df.empty: 
                p = diag_df.iloc[0].to_dict() 
                segment.diagonal_pasef_data = p 
                ms1_scans = int(p.get('insert_ms_scan', 0)) 
                num_ramps = int(p.get('number_of_slices', 0)) 
                isolation_mz = p.get('isolation_mz', 0.0) 
                segment.parameters["calc_ms1_scans"] = ms1_scans 
                segment.parameters["calc_ramps"] = num_ramps 
                segment.parameters["calc_mz_width"] = f"{isolation_mz:.1f}" 
                start_im, end_im = None, None 
                try: 
                    start_im = float(segment.parameters.get("IMS_imeX_RampStart")) 
                    end_im = float(segment.parameters.get("IMS_imeX_RampEnd")) 
                    segment.parameters["calc_scan_area_im"] = f"{start_im:.2f} - {end_im:.2f}" 
                    segment.parameters["calc_im_start"], segment.parameters["calc_im_end"] = start_im, end_im 
                except (ValueError, TypeError, AttributeError): 
                    segment.parameters["calc_scan_area_im"] = "N/A" 
                if start_im is not None and end_im is not None: 
                    try: 
                        if p.get('slope') is None or p.get('origin') is None or p.get('width_mz') is None: 
                            raise ValueError("Missing required diagonal-PASEF parameters (slope, origin, or width_mz).") 
                        if p['slope'] == 0: raise ZeroDivisionError("Slope cannot be zero.") 
                        
                        center_mz1 = (start_im - p['origin']) / p['slope'] 
                        center_mz2 = (end_im - p['origin']) / p['slope'] 
                        pattern_start1 = center_mz1 - (p['width_mz'] / 2) 
                        pattern_start2 = center_mz2 - (p['width_mz'] / 2) 
                        step = p['width_mz'] / num_ramps if num_ramps > 0 else 0 
                        mz_start_first_slice = pattern_start1 
                        mz_start_last_slice = pattern_start2 + ((num_ramps - 1) * step) 
                        mz_end_last_slice = mz_start_last_slice + isolation_mz 
                        segment.parameters["calc_scan_area_mz"] = f"{mz_start_first_slice:.2f} m/z - {mz_end_last_slice:.2f} m/z" 
                    except (ValueError, TypeError, ZeroDivisionError, AttributeError, KeyError) as e: 
                        self.logger.debug("Could not calculate diagonal-PASEF scan area m/z: %s", e) 
                        segment.parameters["calc_scan_area_mz"] = "N/A"     
                        
                try: 
                    ramp_time_ms = float(segment.parameters.get("IMS_imeX_RampTime") or 0) 
                    quench_time = float(segment.parameters.get("Collision_QuenchTime_Set") or 0) 
                    total_scans = ms1_scans + num_ramps 
                    cycle_time_s = total_scans * (ramp_time_ms + quench_time) / 1000 
                    segment.parameters["calc_cycle_time"] = f"{cycle_time_s:.2f} s" 
                except (ValueError, TypeError, AttributeError): 
                    segment.parameters["calc_cycle_time"] = "N/A" 
        except Exception as e: 
            self.logger.debug("Failed to process diagonal-PASEF data: %s", e) 
    
    def _find_file(self, start_folder: str, file_patterns: List[str]) -> Optional[str]: 
        for root, _, files in os.walk(start_folder): 
            for file in files: 
                for pattern in file_patterns: 
                    if file.lower() == pattern.lower(): 
                        return os.path.join(root, file) 
        return None 
    
    def parse_additional_parameters(self, dataset: Dataset, additional_params_info: List[Dict], ion_source: Optional[str] = None): 
        if not hasattr(dataset, 'xml_root') or not additional_params_info: 
            return 
        instrument_scope_element = dataset.xml_root.find('instrument') 
        
        all_defs_map = {p['permname']: p for p in self.config.all_definitions} 
        polarity_map = all_defs_map.get("Mode_IonPolarity", {}).get("value_map", {}) 
        
        last_segment_params = {} 
        for segment in dataset.segments: 
            final_polarity_raw_val = last_segment_params.get("Mode_IonPolarity") 
            
            current_polarity_el = segment.xml_scope_element.find(f".//*[@permname='Mode_IonPolarity']") 
            polarity_val_current = self._get_value_from_element(current_polarity_el, {}) 
            
            if polarity_val_current is not None: 
                final_polarity_raw_val = polarity_val_current 
            polarity_string = polarity_map.get(str(final_polarity_raw_val)) 
            
            all_params_to_check = dataset.default_params + additional_params_info 
            
            new_values = self._parse_parameters_for_scope( 
                method_scope_element=segment.xml_scope_element, 
                instrument_scope_element=instrument_scope_element, 
                param_info=all_params_to_check, 
                ion_polarity=polarity_string,
                ion_source=ion_source 
            ) 
            segment.parameters.update(last_segment_params) 
            segment.parameters.update(new_values) 
            last_segment_params = segment.parameters.copy() 


class PlottingService: #
    def generate_plot_as_buffer(self, dataset: Dataset, width_px: int, height_px: int, bg_color: str = "#E4EFF7", for_report: bool = False, dpi: int = 100, show_filename: bool = True) -> Optional[io.BytesIO]: 
        try: 
            active_segment = dataset.segments[dataset.active_segment_index] 
        except IndexError: 
            return None 

        if len(dataset.segments) > 1: 
            segment_info = f"Segment {dataset.active_segment_index + 1}" 
            title = f"{dataset.display_name} ({segment_info})" if show_filename else segment_info 
        else: 
            title = dataset.display_name if show_filename else "Scan Geometry" 

        fig = None 
        
        scan_mode_id = active_segment.scan_mode_id 
        if scan_mode_id == 9 and active_segment.dia_windows_data is not None: # dia-PASEF 
            fig, _ = self._draw_dia_plot_figure(active_segment, title, width_px, height_px, bg_color, for_report, is_vector=False) 
        elif scan_mode_id == 11 and active_segment.diagonal_pasef_data is not None: # diagonal-PASEF 
            fig, _ = self._draw_diagonal_plot_figure(active_segment, title, width_px, height_px, bg_color, for_report, is_vector=False) 
        elif scan_mode_id == 6 and active_segment.pasef_polygon_data: # PASEF 
            fig, _ = self._draw_pasef_plot_figure(active_segment, title, width_px, height_px, bg_color, for_report, is_vector=False) 
        
        if fig: 
            if for_report: 
                fig.subplots_adjust(left=0.15, right=0.95, bottom=0.22, top=0.85) 
            return self._render_figure_to_buffer(fig, dpi, 'png') 
        return None 
        
    def create_plot_image(self, dataset: Dataset, width_px: int, height_px: int) -> Optional[ctk.CTkImage]: 
        plot_buffer = self.generate_plot_as_buffer(dataset, width_px, height_px) 
        if plot_buffer: 
            image = Image.open(plot_buffer) 
            image.load() 
            plot_buffer.close() 
            return ctk.CTkImage(light_image=image, dark_image=image, size=(image.width, image.height)) 
        return None 

    def _setup_plot(self, width: float, height: float, title: str, bg_color: str, for_report: bool = False, is_vector: bool = False) -> Tuple[plt.Figure, plt.Axes]: 
        if for_report: 
            title_fs, label_fs, tick_fs = 14, 12, 10 
        else: 
            title_fs, label_fs, tick_fs = 9, 8, 7 
        
        figsize = (width, height) 
        dpi = 100 
        if not is_vector: 
            figsize = (width / dpi, height / dpi) 

        fig, ax = plt.subplots(figsize=figsize, dpi=dpi) 
        
        fig.set_facecolor(bg_color) 
        ax.set_facecolor(bg_color) 

        ax.set_xlabel('m/z', color='#04304D', fontsize=label_fs) 
        ax.set_ylabel('1/K0', color='#04304D', fontsize=label_fs) 
        
        max_len = int(width * 10) if is_vector else int(width / (label_fs * 0.8)) 
        final_title = self._truncate_middle(title, max_len) 
        ax.set_title(final_title, color='#04304D', fontsize=title_fs, pad=10 if for_report else 5) 
        
        ax.tick_params(axis='both', colors='#04304D', labelcolor='#04304D', labelsize=tick_fs, pad=5) 
        for spine in ax.spines.values(): 
            spine.set_edgecolor('#04304D') 
            spine.set_linewidth(1.0 if for_report else 0.8) 
            
        fig.subplots_adjust(left=0.18, bottom=0.22, right=0.98, top=0.85) 
        return fig, ax 

    def _render_figure_to_buffer(self, fig: plt.Figure, dpi: int, fmt: str) -> io.BytesIO: 
        buf = io.BytesIO() 
        fig.savefig(buf, format=fmt, facecolor=fig.get_facecolor(), dpi=dpi, bbox_inches='tight') 
        buf.seek(0) 
        plt.close(fig) 
        return buf 

    def _truncate_middle(self, text: str, max_len: int) -> str: 
        if len(text) <= max_len or max_len < 5:  
            return text 
        part_len = (max_len - 3) // 2 
        return f"{text[:part_len]}...{text[-part_len:]}" 

    def _draw_dia_plot_figure(self, segment: Segment, title: str, width: float, height: float, bg_color: str, for_report: bool = False, is_vector: bool = False) -> Optional[Tuple[plt.Figure, plt.Axes]]: 
        df_prepared = segment.dia_windows_data 
        if df_prepared is None or df_prepared.empty or 'CycleId' not in df_prepared.columns: 
            return None 
        fig, ax = self._setup_plot(width, height, title, bg_color, for_report, is_vector) 
        unique_cycles = df_prepared['CycleId'].unique() 
        colors = plt.cm.viridis_r(np.linspace(0, 1, len(unique_cycles))) 
        cycle_color_map = dict(zip(unique_cycles, colors)) 
        for _, row in df_prepared.iterrows(): 
            rect_height = row['plot_y_end'] - row['plot_y_start'] 
            rect = patches.Rectangle( 
                (row['x_start'], row['plot_y_start']), row['IsolationWidth'], rect_height, 
                linewidth=1, edgecolor='#04304D', facecolor=cycle_color_map[row['CycleId']], alpha=0.7) 
            ax.add_patch(rect) 
        ax.autoscale_view() 
        return fig, ax 

    def _draw_diagonal_plot_figure(self, segment: Segment, title: str, width: float, height: float, bg_color: str, for_report: bool = False, is_vector: bool = False) -> Optional[Tuple[plt.Figure, plt.Axes]]: 
        p = segment.diagonal_pasef_data 
        if p is None: return None 
        slope, origin = p['slope'], p['origin'] 
        total_pattern_width_mz, slice_isolation_width_mz = p['width_mz'], p['isolation_mz'] 
        num_slices = int(p['number_of_slices']) 
        measured_mobility_start = segment.parameters.get("calc_im_start") 
        measured_mobility_end = segment.parameters.get("calc_im_end") 
        if measured_mobility_start is None or measured_mobility_end is None: return None 
        if slope == 0: return None 
        fig, ax = self._setup_plot(width, height, title, bg_color, for_report, is_vector) 
        colors = plt.cm.viridis_r(np.linspace(0, 1, num_slices)) 
        center_mz1, center_mz2 = (measured_mobility_start - origin) / slope, (measured_mobility_end - origin) / slope 
        pattern_start1, pattern_start2 = center_mz1 - (total_pattern_width_mz / 2), center_mz2 - (total_pattern_width_mz / 2) 
        step_mz = total_pattern_width_mz / num_slices if num_slices > 0 else 0 
        for i in range(num_slices): 
            slice_start_mz_bottom = pattern_start1 + (i * step_mz) 
            slice_start_mz_top = pattern_start2 + (i * step_mz) 
            slice_end_mz_bottom = slice_start_mz_bottom + slice_isolation_width_mz 
            slice_end_mz_top = slice_start_mz_top + slice_isolation_width_mz 
            vertices = [ 
                (slice_start_mz_bottom, measured_mobility_start), (slice_end_mz_bottom,   measured_mobility_start), 
                (slice_end_mz_top,      measured_mobility_end), (slice_start_mz_top,    measured_mobility_end) 
            ] 
            polygon = patches.Polygon(vertices, linewidth=1, edgecolor='#04304D', facecolor=colors[i], alpha=0.7) 
            ax.add_patch(polygon) 
        ax.autoscale_view() 
        xlim, ylim = ax.get_xlim(), ax.get_ylim() 
        x_buffer, y_buffer = (xlim[1] - xlim[0]) * 0.05, (ylim[1] - ylim[0]) * 0.05 
        ax.set_xlim(xlim[0] - x_buffer, xlim[1] + x_buffer) 
        ax.set_ylim(ylim[0] - y_buffer, ylim[1] + y_buffer) 
        return fig, ax 

    def _draw_pasef_plot_figure(self, segment: Segment, title: str, width: float, height: float, bg_color: str, for_report: bool = False, is_vector: bool = False) -> Optional[Tuple[plt.Figure, plt.Axes]]: 
        if not segment.pasef_polygon_data: return None 
        mass_coords, mobility_coords = segment.pasef_polygon_data 
        if not mass_coords or not mobility_coords or len(mass_coords) != len(mobility_coords): return None 
        polygon_points = list(zip(mass_coords, mobility_coords)) 
        fig, ax = self._setup_plot(width, height, title, bg_color, for_report, is_vector) 
        polygon = patches.Polygon(polygon_points, linewidth=1, edgecolor='#04304D', facecolor='#0071BC', alpha=0.7) 
        ax.add_patch(polygon) 
        ax.autoscale_view() 
        return fig, ax 

    def generate_plot_as_svg_buffer(self, dataset: Dataset, width_in: float, height_in: float, bg_color: str = "white", show_filename: bool = True) -> Optional[io.BytesIO]: 
        try: 
            active_segment = dataset.segments[dataset.active_segment_index] 
        except IndexError: 
            return None 

        if len(dataset.segments) > 1: 
            segment_info = f"Segment {dataset.active_segment_index + 1}" 
            title = f"{dataset.display_name} ({segment_info})" if show_filename else segment_info 
        else: 
            title = dataset.display_name if show_filename else "Scan Geometry" 

        fig = None 
        
        scan_mode_id = active_segment.scan_mode_id 
        if scan_mode_id == 9 and active_segment.dia_windows_data is not None: 
            fig, _ = self._draw_dia_plot_figure(active_segment, title, width_in, height_in, bg_color, True, True) 
        elif scan_mode_id == 11 and active_segment.diagonal_pasef_data is not None: 
            fig, _ = self._draw_diagonal_plot_figure(active_segment, title, width_in, height_in, bg_color, True, True) 
        elif scan_mode_id == 6 and active_segment.pasef_polygon_data: 
            fig, _ = self._draw_pasef_plot_figure(active_segment, title, width_in, height_in, bg_color, True, True) 
        
        if fig: 
            fig.subplots_adjust(left=0.15, right=0.95, bottom=0.22, top=0.85) 
            return self._render_figure_to_buffer(fig, 0, 'svg') 
        return None 

class ReportGeneratorService: 
    def __init__(self, plotting_service: PlottingService, config: AppConfig, loader_service: DataLoaderService): 
        self.plotting_service = plotting_service 
        self.config = config 
        self.loader = loader_service 
        self.logger = logging.getLogger(__name__) 

    def generate_report(self, dataset: Dataset, selected_segment_indices: List[int], params_to_include: List[Dict],  
                        export_format: str, file_path: str, show_filename: bool, include_plot: bool, 
                        progress_callback: Optional[Callable] = None): 
        
        permnames_in_report = {p['permname'] for p in params_to_include} 
        if "calc_scan_mode" in permnames_in_report and "Mode_ScanMode" in permnames_in_report: 
            params_to_include = [p for p in params_to_include if p['permname'] != "Mode_ScanMode"] 

        if export_format == 'csv': 
            if progress_callback: progress_callback(1, "Preparing data for CSV...") 
            self._generate_csv(dataset, selected_segment_indices, params_to_include, file_path) 
            if progress_callback: progress_callback(1, "CSV export complete.") 
        elif export_format == 'pdf': 
            self._generate_pdf(dataset, selected_segment_indices, params_to_include, file_path, show_filename, include_plot, progress_callback) 

    def _get_default_param_configs_for_dataset(self, dataset: Dataset) -> List[Dict]: 
        if not dataset or not dataset.segments: 
            return [] 

        has_multisegment_file = len(dataset.segments) > 1 
        has_advanced_ce = any(s.parameters.get("Energy_Ramping_Advanced_Settings_Active") == '1' for s in dataset.segments) 
        has_standard_ce = any(s.parameters.get("Energy_Ramping_Advanced_Settings_Active") != '1' for s in dataset.segments) 
        has_icc_mode1 = any(s.parameters.get("IMSICC_Mode") == '1' for s in dataset.segments) 
        has_icc_mode2 = any(s.parameters.get("IMSICC_Mode") == '2' for s in dataset.segments) 

        all_workflows_in_dataset = {s.workflow_name for s in dataset.segments if s.workflow_name} 
        default_params_by_workflow = self.config.parameter_definitions 

        default_permnames_ordered = [] 
        seen_permnames = set() 

        def add_unique(permnames): 
            for pname in permnames: 
                if pname not in seen_permnames: 
                    seen_permnames.add(pname) 
                    default_permnames_ordered.append(pname) 

        add_unique(default_params_by_workflow.get('__GENERAL__', [])) 
        for wf in sorted(list(all_workflows_in_dataset)): 
            add_unique(default_params_by_workflow.get(wf, [])) 
        
        if "calc_scan_mode" in seen_permnames and "Mode_ScanMode" in seen_permnames: 
            default_permnames_ordered.remove("Mode_ScanMode") 

        all_definitions_map = {p['permname']: p for p in self.config.all_definitions} 
        default_param_configs = [] 

        for pname in default_permnames_ordered: 
            if pname in ["calc_segment_start_time", "calc_segment_end_time"] and not has_multisegment_file: continue 
            if pname in ["calc_ce_ramping_start", "calc_ce_ramping_end"] and not has_standard_ce: continue 
            if pname == "calc_advanced_ce_ramping_display_list" and not has_advanced_ce: continue 
            if pname == 'IMSICC_Target' and not has_icc_mode1: continue 
            
            mode2_params = ["IMSICC_ICC2_MaxTicTargetPercent", "IMSICC_ICC2_MinAccuTime", "IMSICC_ICC2_ReferenceTicCapacity", "IMSICC_ICC2_SmoothingFactor"] 
            if pname in mode2_params and not has_icc_mode2: continue 

            param_config = all_definitions_map.get(pname) 
            if not param_config and pname.startswith("calc_"): 
                label_map = {"calc_scan_area_mz": "Window Scan Area", "calc_ramps": "Ramps per Cycle", "calc_ms1_scans": "MS1 Scans per Cycle", "calc_steps": "Isolation Steps per Cycle", "calc_mz_width": "Isolation Window Width", "calc_ce_ramping_start": "CE Ramping Start", "calc_ce_ramping_end": "CE Ramping End"} 
                label = label_map.get(pname, pname.replace("calc_", "").replace("_", " ").title()) 
                category = "Mode" if "Scan Mode" in label else "Calculated Parameters" 
                param_config = {"permname": pname, "label": label, "category": category} 
            
            if param_config: 
                default_param_configs.append(param_config) 
        
        return default_param_configs 

    def _prepare_data_for_segment(self, dataset: Dataset, segment_index: int, params_to_include: List[Dict]) -> pd.DataFrame: 
        report_data = [] 
        segment = dataset.segments[segment_index] 
        
        for param_config in params_to_include: 
            permname = param_config['permname'] 
            final_value = "" 
            
            if permname == "calc_scan_mode": 
                final_value = segment.workflow_name or "N/A" 
            elif permname == "calc_segment_start_time": 
                final_value = f"{segment.start_time:.2f} min" 
            elif permname == "calc_segment_end_time": 
                final_value = segment.end_time_display 
            else: #
                original_active_index = dataset.active_segment_index 
                dataset.active_segment_index = segment_index 
                raw_value = dataset.get_parameter_value(permname) 
                dataset.active_segment_index = original_active_index 
                final_value = raw_value if isinstance(raw_value, list) else format_parameter_value(raw_value, param_config) 

            report_data.append({ 
                "Parameter": param_config.get('label', permname), 
                "Category": param_config.get('category', "General"), 
                "Value": final_value 
            }) 

        return pd.DataFrame(report_data) 


    def _generate_csv(self, dataset: Dataset, selected_segment_indices: List[int], params_to_include: List[Dict], file_path: str): 
        all_data = [] 
        for index in selected_segment_indices: 
            df = self._prepare_data_for_segment(dataset, index, params_to_include) 
            if not df.empty: 
                df['Segment'] = f"Segment {index + 1}" 
                all_data.append(df) 
            
        if not all_data: 
            return 

        final_df = pd.concat(all_data, ignore_index=True) 
        final_df['Value'] = final_df['Value'].apply( 
            lambda x: '; '.join(map(str, x)) if isinstance(x, list) else x 
        ) 
        final_df = final_df[['Segment', 'Category', 'Parameter', 'Value']] 
        final_df.to_csv(file_path, index=False, encoding='utf-8') 

    def _generate_pdf(self, dataset: Dataset, selected_segment_indices: List[int], params_to_include: List[Dict],  
                      file_path: str, show_filename: bool, include_plot: bool, progress_callback: Optional[Callable] = None): 
        
        class ReportPDF(FPDF): 
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.set_auto_page_break(auto=True, margin=15)
                self.dataset_name = ""
                self.segment_info = ""
                self.page_width = 0
                self.col_width = 0
                self.gutter = 5
                self.col_y = [0, 0]
                self.current_col = 0
                
                self.font_name = "Helvetica" # Default fallback font
                try:
                    font_regular_path = resource_path("assets/DejaVuSans.ttf")
                    font_bold_path = resource_path("assets/DejaVuSans-Bold.ttf")
                    font_italic_path = resource_path("assets/DejaVuSans-Oblique.ttf")

                    self.add_font("DejaVu", "", font_regular_path)
                    self.add_font("DejaVu", "B", font_bold_path)
                    self.add_font("DejaVu", "I", font_italic_path)
                    
                    self.font_name = "DejaVu" 
                except RuntimeError:
                    logging.getLogger(__name__).warning(
                        "DejaVu font files not found in assets/. PDF report will fall back to Helvetica."
                        " Special characters may not render correctly."
                    )

            def header(self):
                self.set_font(self.font_name, "I", 8)
                self.cell(0, 10, self.dataset_name, 0, 0, "L")
                self.cell(0, 10, self.segment_info, 0, 0, "R")
                self.ln(12) 

            def footer(self):
                self.set_y(-15)
                self.set_font(self.font_name, "I", 8)
                self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", 0, 0, "R")

            def start_page_setup(self): 
                self.page_width = self.w - self.l_margin - self.r_margin 
                self.col_width = (self.page_width - self.gutter) / 2 
            
            def start_columns(self): 
                self.col_y = [self.get_y(), self.get_y()] 
                self.current_col = 0 
            
            def draw_table(self, data: pd.DataFrame): 
                self.current_col = 0 
                self.col_y = [self.get_y(), self.get_y()] 

                for category_name, group in data.groupby('Category', sort=False): 
                    if group.empty: 
                        continue 
                    self._draw_group(category_name, group.reset_index(drop=True)) 

            def _draw_group(self, category_name: str, group: pd.DataFrame): 
                header_h = 7 
                
                if self.col_y[self.current_col] + header_h + 10 > self.page_break_trigger: 
                    self._switch_column() 
                
                self._draw_header(category_name) 
                
                for i, (_, row) in enumerate(group.iterrows()): 
                    self._draw_row(row, i, category_name) 
            
            def _switch_column(self): 
                self.current_col = 1 - self.current_col 
                if self.current_col == 0: 
                    self.add_page() 
                    self.start_columns() 
            
            def _draw_header(self, text): 
                header_h = 7 
                x_pos = self.l_margin if self.current_col == 0 else self.l_margin + self.col_width + self.gutter 
                y_pos = self.col_y[self.current_col] 

                if y_pos > self.t_margin + 5: 
                    self.set_y(y_pos + 2) 
                else: 
                    self.set_y(y_pos) 
                
                self.set_x(x_pos) 
                self.set_font(self.font_name, "B", 10)
                self.set_fill_color(4, 48, 77) 
                self.set_text_color(255, 255, 255) 
                self.cell(self.col_width, header_h, f" {text}", 0, 0, "L", fill=True) 
                
                self.col_y[self.current_col] = self.get_y() + header_h 

            def _get_line_count(self, text: str, width: float) -> int: 
                self.set_font(self.font_name, "", 8)
                words = str(text).split(' ') 
                if not words: return 1 
                
                lines = 1 
                current_line = words[0] 
                effective_width = width - 2 * self.c_margin 
                for word in words[1:]: 
                    if self.get_string_width(current_line + " " + word) > effective_width: 
                        lines += 1 
                        current_line = word 
                    else: 
                        current_line += " " + word 
                return lines 

            def _get_row_height(self, row: pd.Series, param_w: float, value_w: float, line_h: float = 5) -> float: 
                param_lines = self._get_line_count(f" {row['Parameter']}", param_w) 
                value_lines = self._get_line_count(f" {row['Value']}", value_w) 
                return max(param_lines, value_lines) * line_h 

            def _draw_row(self, row_data: pd.Series, row_index: int, category_name: str): 
                line_h = 5 
                param_col_w = self.col_width * 0.6 
                value_col_w = self.col_width * 0.4 

                row_height = self._get_row_height(row_data, param_col_w, value_col_w, line_h) 
                if self.col_y[self.current_col] + row_height > self.page_break_trigger: 
                    self._switch_column() 
                    self._draw_header(f"{category_name} (continued)") 
                
                x_pos = self.l_margin if self.current_col == 0 else self.l_margin + self.col_width + self.gutter 
                start_y = self.col_y[self.current_col] 

                self.set_font(self.font_name, "", 8)
                self.set_text_color(0, 0, 0) 
                self.set_draw_color(211, 211, 211) 
                
                is_striped = (row_index % 2 == 1) 
                fill_color = (240, 240, 240) if is_striped else (255, 255, 255) 
                self.set_fill_color(*fill_color) 
                self.rect(x_pos, start_y, self.col_width, row_height, "F") 
                self.rect(x_pos, start_y, self.col_width, row_height) 
                self.line(x_pos + param_col_w, start_y, x_pos + param_col_w, start_y + row_height) 

                self.set_xy(x_pos, start_y) 
                self.multi_cell(param_col_w, line_h, f" {str(row_data['Parameter'])}", 0, "L") 
                self.set_xy(x_pos + param_col_w, start_y) 
                self.multi_cell(value_col_w, line_h, f" {str(row_data['Value'])}", 0, "L") 

                self.col_y[self.current_col] = start_y + row_height 
                self.set_y(self.col_y[self.current_col]) 
        
        if progress_callback: progress_callback(1, "Initializing PDF...") 
        pdf = ReportPDF() 
        pdf.alias_nb_pages() 
        pdf.add_page() 
        pdf.start_page_setup() 

        pdf.set_font(pdf.font_name, "B", 20)
        pdf.cell(0, 10, "timsCompare Method Report", 0, 1, "C") 
        if show_filename: 
            pdf.dataset_name = f"File: {dataset.display_name}" 
            pdf.set_font(pdf.font_name, "", 12)
            pdf.cell(0, 10, pdf.dataset_name, 0, 1, "C") 
        pdf.ln(5) 

        for i, index in enumerate(selected_segment_indices): 
            segment = dataset.segments[index] 
            segment_title = "" 
            if len(dataset.segments) > 1: 
                segment_title = f"Segment {index + 1} ({segment.start_time:.2f} - {segment.end_time_display})" 
            
            pdf.segment_info = segment_title 

            if i > 0: 
                pdf.add_page() 
                pdf.start_page_setup() 
            
            if segment_title: 
                pdf.set_font(pdf.font_name, "B", 16)
                pdf.cell(0, 10, segment_title, 0, 1, "L") 
                pdf.ln(2) 
            
            if include_plot: 
                if progress_callback: progress_callback(0, f"Generating plot for segment {index+1}...") 
                
                original_active_index = dataset.active_segment_index 
                dataset.active_segment_index = index 
                
                page_width_mm = pdf.w - pdf.l_margin - pdf.r_margin 
                plot_width_in = page_width_mm / 25.4 
                plot_height_in = plot_width_in * 0.4 

                png_buffer = self.plotting_service.generate_plot_as_buffer( 
                    dataset, 
                    width_px=int(plot_width_in * 300), 
                    height_px=int(plot_height_in * 300), 
                    show_filename=show_filename, 
                    for_report=True, 
                    dpi=300, 
                    bg_color="white" 
                ) 
                
                dataset.active_segment_index = original_active_index 

                if progress_callback: progress_callback(1, "Embedding plot...") 
                if png_buffer: 
                    try: 
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".png", mode='wb') as temp_png: 
                            temp_png.write(png_buffer.getvalue()) 
                            temp_png_path = temp_png.name 
                        
                        pdf.image(temp_png_path, w=page_width_mm) 
                        pdf.ln(5) 
                        
                    finally: 
                        png_buffer.close() 
                        if 'temp_png_path' in locals() and os.path.exists(temp_png_path): 
                            os.remove(temp_png_path) 
            
            if progress_callback: progress_callback(1, f"Drawing table for segment {index+1}...") 
            pdf.start_columns() 
            data_df = self._prepare_data_for_segment(dataset, index, params_to_include) 
            
            expanded_rows = [] 
            for _, row in data_df.iterrows(): 
                if isinstance(row['Value'], list): 
                    parent_row = row.copy() 
                    parent_row['Value'] = f"List ({len(row['Value'])} items)" 
                    expanded_rows.append(parent_row) 
                    for item_index, item_value in enumerate(row['Value']): 
                        child_row = row.copy() 
                        child_row['Parameter'] = f"    -> Item {item_index + 1}" 
                        child_row['Value'] = item_value 
                        expanded_rows.append(child_row) 
                else: 
                    expanded_rows.append(row) 
            
            if expanded_rows: 
                data_df = pd.DataFrame(expanded_rows) 

            pdf.draw_table(data_df) 
            pdf.set_y(max(pdf.col_y)) 

        if progress_callback: progress_callback(1, "Saving final PDF...") 
        pdf.output(file_path)