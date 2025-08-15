"""
Configures the centralized logging system for the application.

This module provides a single function, `setup_logging`, which should be called
once upon application startup. It establishes a consistent logging format and
configures handlers for both file-based and console-based output.

Key features:
- Creates rotating log files in a dedicated `.timsCompare` directory in the
  user's home folder.
- Sets the application's log level based on a global setting.
- Suppresses verbose logging from noisy third-party libraries like Matplotlib
  and PIL to keep the application log focused and clean.
"""
import logging
import os
from logging.handlers import RotatingFileHandler

from settings import ENABLE_DEBUG_LOGGING


def setup_logging():
    """
    Configures the application-wide root logger.

    This function performs the following setup actions:
    1. Sets the global log level based on the `ENABLE_DEBUG_LOGGING` setting.
    2. Defines a standard format for all log messages.
    3. Clears any pre-existing handlers to prevent log duplication.
    4. Creates a rotating file handler that saves logs to `~/.timsCompare/timsCompare.log`.
    5. Creates a console stream handler to output logs to the terminal.
    6. Sets the log level for noisy third-party libraries to WARNING.
    """
    log_level = logging.DEBUG if ENABLE_DEBUG_LOGGING else logging.INFO
    
    # --- Define a consistent format for log messages ---
    log_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # --- Get the root logger to configure it for the entire application ---
    logger = logging.getLogger()
    logger.setLevel(log_level)

    # --- Suppress verbose output from third-party libraries ---
    # This prevents the application logs from being cluttered with debug/info
    # messages from libraries like Matplotlib during plotting.
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)
    
    # --- Clear any existing handlers to prevent duplicate log entries ---
    # This is a safeguard in case this function is ever called more than once.
    if logger.hasHandlers():
        logger.handlers.clear()

    # --- Configure File Handler ---
    # This handler writes logs to a file that rotates to prevent it from
    # growing indefinitely.
    log_file = "timsCompare.log"  # Default filename
    try:
        # Create a dedicated log directory in the user's home folder.
        log_dir = os.path.join(os.path.expanduser('~'), '.timsCompare')
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, 'timsCompare.log')
        
        # Configure log rotation: keep up to 5 log files, each up to 5MB in size.
        file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8')
        file_handler.setFormatter(log_formatter)
        logger.addHandler(file_handler)
    except (IOError, PermissionError) as e:
        # Fallback in case log file creation fails (e.g., due to permissions).
        print(f"Warning: Could not create log file at '{log_file}'. Logging to file is disabled. Error: {e}")

    # --- Configure Console Handler ---
    # This handler prints log messages to the standard output (the console).
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    logger.addHandler(console_handler)
    
    logging.info("Logging configured successfully. Application log level: %s", logging.getLevelName(log_level))