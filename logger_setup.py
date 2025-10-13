# logger_setup.py

import logging
import os
from logging.handlers import RotatingFileHandler
from settings import ENABLE_DEBUG_LOGGING

def setup_logging() -> str | None:
    log_level = logging.DEBUG if ENABLE_DEBUG_LOGGING else logging.INFO
    
    log_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    logger = logging.getLogger()
    logger.setLevel(log_level)

    logging.getLogger("matplotlib").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)
    
    if logger.hasHandlers():
        logger.handlers.clear()

    try:
        log_dir = os.path.join(os.path.expanduser('~'), '.timsCompare')
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, 'timsCompare.log')
        
        file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8')
        file_handler.setFormatter(log_formatter)
        logger.addHandler(file_handler)
    except (IOError, PermissionError) as e:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(log_formatter)
        logger.addHandler(console_handler)
        
        error_message = (f"Could not create log file at:\n{log_file}\n\n"
                         f"Reason: {e}\n\n"
                         "Logging to file will be disabled for this session.")
        logging.warning(error_message)
        return error_message

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    logger.addHandler(console_handler)
    
    logging.info("Logging configured successfully. Application log level: %s", logging.getLevelName(log_level))
    return None