"""
Utility functions for the CLI
"""

import importlib
import sys
from .log_utils import setup_logger
import logging

setup_logger(loglevel="INFO")
logger = logging.getLogger(__name__)


def check_python_version():
    """
    Check the python version is 3.11 or greater
    """
    major, minor = sys.version_info[:2]
    if major < 3 or (major == 3 and minor < 11):
        logger.warning("This is tested with Python 3.11")


def check_required_modules(modules):
    """
    Check that the required modules are installed
    """
    missing_modules = []
    for module in modules:
        try:
            importlib.import_module(module)
        except ImportError:
            missing_modules.append(module)

    if missing_modules:
        logger.error("Missing required modules: %s", missing_modules)
        sys.exit(1)
