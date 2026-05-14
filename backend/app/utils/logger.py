"""
Centralized Logger Class

Simple logging utility that provides file-based logger names.
"""

import logging
from pathlib import Path


class AppLogger:
    """
    Centralized logger class for the application.
    Handles all logging configuration.
    """

    _configured = False

    @classmethod
    def configure(cls, log_level: str = "INFO", log_dir: str = "logs") -> None:
        """
        Configure the global logging settings once.

        Args:
            log_level (str): Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_dir (str): Directory to store log files
        """
        if cls._configured:
            return

        # Create log directory if it doesn't exist
        Path(log_dir).mkdir(exist_ok=True)

        # Simple log format
        log_format = (
            "%(asctime)s | %(levelname)-8s | %(message)s | %(name)s | "
            "%(funcName)s:%(lineno)d"
        )

        # Configure logging
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format=log_format,
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(f"{log_dir}/app.log")
            ]
        )

        cls._configured = True

    @classmethod
    def get_logger(cls, file_path: str) -> logging.Logger:
        """
        Get a logger for a specific file.

        Args:
            file_path (str): File path (use __file__)

        Returns:
            logging.Logger: Configured logger
        """
        # Ensure logging is configured
        if not cls._configured:
            cls.configure()

        # Extract filename as logger name
        filename = Path(file_path).stem
        return logging.getLogger(filename)