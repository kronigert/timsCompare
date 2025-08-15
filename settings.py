"""
Centralizes global constants and feature flags for the application.

This module is intended to hold simple, static configuration values that can
be accessed from anywhere in the application to control its behavior,
particularly for debugging and development purposes.
"""

# --- Centralized Debug Flag ---
# This is the primary flag used throughout the application to enable detailed
# logging and other debug-related functionalities. It is currently the only
# setting used by logger_setup.py to determine the log level.
ENABLE_DEBUG_LOGGING = True