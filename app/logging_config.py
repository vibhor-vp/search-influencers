"""
Logging Configuration Module
Handles proper logging setup for both local development and production (systemd)
"""

import logging
import logging.handlers
import sys
import os
from typing import Optional


# def setup_logging(
#     app_name: str = "search-influencers",
#     log_level: str = "INFO",
#     log_file: Optional[str] = None,
#     use_systemd: bool = False
# ) -> None:
#     """
#     Configure logging for FastAPI application
    
#     Works with:
#     - Console output (development)
#     - Systemd journal (production)
#     - File output (optional)
    
#     Args:
#         app_name: Application name (appears in logs)
#         log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
#         log_file: Optional log file path
#         use_systemd: Force systemd journal handler
        
#     Example:
#         setup_logging(log_level="DEBUG")  # Development
#         setup_logging(log_level="INFO", use_systemd=True)  # Production
#     """
    
#     # Get root logger
#     root_logger = logging.getLogger()
#     root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
#     # Clear any existing handlers
#     root_logger.handlers.clear()
    
#     # Format for all handlers
#     formatter = logging.Formatter(
#         fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
#         datefmt='%Y-%m-%d %H:%M:%S'
#     )
    
#     # ==========================================
#     # 1. CONSOLE HANDLER (Always add)
#     # ==========================================
#     console_handler = logging.StreamHandler(sys.stdout)
#     console_handler.setFormatter(formatter)
#     root_logger.addHandler(console_handler)
    
#     # ==========================================
#     # 2. SYSTEMD JOURNAL HANDLER (if available)
#     # ==========================================
#     if use_systemd or _is_running_under_systemd():
#         try:
#             from systemd.journal import JournalHandler
            
#             journal_handler = JournalHandler(
#                 SYSLOG_IDENTIFIER=app_name,
#                 SYSLOG_FACILITY=logging.handlers.SysLogHandler.LOG_LOCAL0
#             )
#             journal_handler.setFormatter(formatter)
#             root_logger.addHandler(journal_handler)
            
#             logging.getLogger(__name__).debug(
#                 "✅ Systemd journal handler configured"
#             )
#         except ImportError:
#             logging.getLogger(__name__).debug(
#                 "⚠️ systemd.journal not available, using console only"
#             )
#         except Exception as e:
#             logging.getLogger(__name__).warning(
#                 f"⚠️ Failed to setup systemd handler: {e}"
#             )
    
#     # ==========================================
#     # 3. FILE HANDLER (if log_file specified)
#     # ==========================================
#     if log_file:
#         try:
#             # Create directory if it doesn't exist
#             os.makedirs(os.path.dirname(log_file), exist_ok=True)
            
#             # Create rotating file handler (max 10MB, keep 5 backups)
#             file_handler = logging.handlers.RotatingFileHandler(
#                 filename=log_file,
#                 maxBytes=10 * 1024 * 1024,  # 10MB
#                 backupCount=5
#             )
#             file_handler.setFormatter(formatter)
#             root_logger.addHandler(file_handler)
            
#             logging.getLogger(__name__).info(
#                 f"✅ File logging configured: {log_file}"
#             )
#         except Exception as e:
#             logging.getLogger(__name__).warning(
#                 f"⚠️ Failed to setup file handler: {e}"
#             )
    
#     # ==========================================
#     # 4. CONFIGURE APP-SPECIFIC LOGGERS
#     # ==========================================
#     # Set application module loggers
#     app_modules = [
#         'app.main',
#         'app.transcript_service',
#         'app.youtube_captions_service',
#         'app.youtube_service',
#         'app.llm_service',
#         'app.cache',
#         'app.config',
#         'uvicorn',
#         'uvicorn.access',
#     ]
    
#     for module in app_modules:
#         module_logger = logging.getLogger(module)
#         module_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
#     # ==========================================
#     # 5. INITIAL LOG MESSAGE
#     # ==========================================
#     logger = logging.getLogger(__name__)
#     logger.info(
#         f"🚀 Logging initialized - Level: {log_level}, "
#         f"Systemd: {_is_running_under_systemd()}"
#     )


# def _is_running_under_systemd() -> bool:
#     """
#     Detect if application is running under systemd
    
#     Returns:
#         True if running under systemd, False otherwise
#     """
#     # Check 1: INVOCATION_ID environment variable (set by systemd)
#     if os.getenv('INVOCATION_ID'):
#         return True
    
#     # Check 2: Check if journalctl can access the service
#     if os.path.exists('/run/systemd/journal.socket'):
#         return True
    
#     # Check 3: Check if parent process is systemd
#     try:
#         with open('/proc/1/comm', 'r') as f:
#             if 'systemd' in f.read():
#                 return True
#     except (FileNotFoundError, OSError):
#         pass
    
#     return False


# def get_logger(name: str) -> logging.Logger:
#     """
#     Get a logger instance for a module
    
#     Args:
#         name: Module name (typically __name__)
        
#     Returns:
#         Configured logger instance
        
#     Example:
#         logger = get_logger(__name__)
#         logger.info("Something happened")
#     """
#     return logging.getLogger(name)


# def log_startup_info(
#     app_name: str,
#     version: str = "1.0.0",
#     environment: str = "development"
# ) -> None:
#     """
#     Log application startup information
    
#     Args:
#         app_name: Application name
#         version: Application version
#         environment: Environment (development, production, etc.)
#     """
#     logger = get_logger(__name__)
    
#     logger.info("=" * 60)
#     logger.info(f"🚀 {app_name} v{version}")
#     logger.info(f"📍 Environment: {environment}")
#     logger.info(f"🖥️  Systemd: {_is_running_under_systemd()}")
#     logger.info(f"📊 PID: {os.getpid()}")
#     logger.info("=" * 60)


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ],
        force=True  # 🔥 THIS IS THE KEY
    )