"""Structured logging for vault operations (ingest/query)."""
import logging
import pathlib
from datetime import datetime
from functools import wraps
from typing import Any, Callable, TypeVar

T = TypeVar("T")

# Create log directory
LOG_DIR = pathlib.Path("log")
LOG_DIR.mkdir(exist_ok=True)

# Track log file per run type (so all methods in one run use same file)
_log_files: dict[str, pathlib.Path] = {}


def _get_log_file(run_type: str) -> pathlib.Path:
    """Get log file path for a run type (ingest or query) with timestamp.
    Creates one file per run type, reuses it for subsequent calls in same run.
    """
    if run_type not in _log_files:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        _log_files[run_type] = LOG_DIR / f"vault_{run_type}_{timestamp}.log"
    return _log_files[run_type]


# Track which loggers have been set up to avoid duplicates
_loggers_setup: set[str] = set()


def _setup_file_logger(run_type: str, logger_name: str) -> logging.Logger:
    """Set up a file logger for a specific run."""
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    
    # Only set up once per logger name to avoid duplicates
    if logger_name not in _loggers_setup:
        logger.handlers.clear()
        
        # File handler
        log_file = _get_log_file(run_type)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.INFO)
        file_formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
        # Also log to console (with RichHandler if available)
        try:
            from rich.logging import RichHandler
            console_handler = RichHandler(rich_tracebacks=True)
            console_handler.setLevel(logging.INFO)
            logger.addHandler(console_handler)
        except ImportError:
            # Fallback to basic StreamHandler
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            logger.addHandler(console_handler)
        
        _loggers_setup.add(logger_name)
        logger.info(f"Log file created: {log_file}")
    
    return logger


def get_vault_logger(run_type: str = "query") -> logging.Logger:
    """
    Get the logger instance for custom logging within vault operations.
    
    Usage:
        logger = get_vault_logger(run_type="ingest")
        logger.info("Custom log message")
        logger.warning("Something happened")
        logger.error("Error occurred")
    
    Args:
        run_type: 'ingest' or 'query' - determines log file name
    
    Returns:
        Logger instance configured for the specified run type
    """
    logger_name = f"vault_{run_type}"
    logger = _setup_file_logger(run_type, logger_name)
    return logger


def log_method_entry(run_type: str = "query"):
    """
    Decorator to log method entry with format: 'module:method is entered'.
    
    Args:
        run_type: 'ingest' or 'query' - determines log file name
    
    The logger is available inside the decorated function via get_vault_logger().
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            module_name = func.__module__.split(".")[-1]  # e.g., 'vault_store' or 'retriever'
            method_name = func.__name__
            logger_name = f"vault_{run_type}"
            
            # Set up logger for this run
            logger = _setup_file_logger(run_type, logger_name)
            
            # Log method entry
            entry_msg = f"{module_name}:{method_name} is entered"
            logger.info(entry_msg)
            
            # Log method arguments (excluding sensitive data)
            if args or kwargs:
                safe_kwargs = {k: v for k, v in kwargs.items() if "password" not in k.lower() and "key" not in k.lower()}
                if safe_kwargs:
                    logger.info(f"{module_name}:{method_name} called with kwargs: {safe_kwargs}")
            
            try:
                result = func(*args, **kwargs)
                
                # Log method exit
                exit_msg = f"{module_name}:{method_name} is exited"
                logger.info(exit_msg)
                
                return result
            except Exception as exc:
                logger.error(f"{module_name}:{method_name} failed with error: {exc}", exc_info=True)
                raise
        
        return wrapper
    return decorator
