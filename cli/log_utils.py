"""
This module is responsible for managing the logging for the CLI
"""
import colorlog


def setup_logger(loglevel):
    """Setup the logger"""
    log_format = (
        "%(log_color)s%(levelname)-8s" + "%(message_log_color)s%(message)s%(reset)s"
    )
    colorlog.basicConfig(level=loglevel, format=log_format)

    colorlog_format = {
        "info": "cyan",
        "INFO": "green",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "red,bg_white",
    }

    colorlog.root.handlers[0].formatter.log_colors.update(colorlog_format)
    colorlog.root.handlers[0].formatter.secondary_log_colors = {
        "message": colorlog_format
    }
