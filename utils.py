from typing import Any, Dict

def format_parameter_value(value: Any, param_config: Dict) -> str:
    """
    Centralized function to format a raw parameter value into a user-friendly string.
    Applies rounding and appends units based on the parameter's configuration.
    """
    if value is None or value == '':
        return "N/A"

    # Handle special string mappings first (e.g., from VALUETEXT)
    value_map = param_config.get("value_map")
    if value_map and str(value) in value_map:
        return value_map[str(value)]

    permname = param_config.get("permname")

    # Handle boolean types
    param_type = param_config.get("type")
    if (param_type == "boolean") or (permname and permname.endswith("Switch")):
        return "On" if str(value) in ["1", "true", "True"] else "Off"
            
    # Handle special list displays
    if permname == "calc_advanced_ce_ramping_display_list" and isinstance(value, list):
        return f"List ({len(value)} items)"
    if permname in ["IMS_PolygonFilter_Mass", "IMS_PolygonFilter_Mobility"] and isinstance(value, list):
        return f"Polygon ({len(value)} points)"
    if isinstance(value, list):
        return f"List ({len(value)} items)"
        
    # Apply rounding and unit logic
    formatted_string = ""
    try:
        numeric_value = float(value)
        round_to = param_config.get("round_to")
        if round_to is not None:
            formatted_string = f"{numeric_value:.{int(round_to)}f}"
        else:
            # Default for floats that don't specify rounding
            formatted_string = str(value)
    except (ValueError, TypeError):
        # Value is not a number, use as is
        formatted_string = str(value)

    # Append unit if it exists
    unit = param_config.get("unit")
    if unit and formatted_string != "N/A":
        return f"{formatted_string} {unit}"
    else:
        return formatted_string