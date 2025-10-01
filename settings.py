# settings.py

# --- Centralized Debug Flag ---
# Set to True to print detailed parsing and discovery steps to the console.
# Set to False for production release.
ENABLE_DEBUG_LOGGING = False

# --- Developer Logging Configuration ---
# Controls the behavior of the application's logging system.
LOGGING_ENABLED = False
LOGGING_LEVEL = 'DEBUG'
LOGGING_OUTPUT = ['console', 'file']
LOG_FILE_NAME = 'timsCompare.log'