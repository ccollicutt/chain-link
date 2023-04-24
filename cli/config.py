"""
This module is responsible for managing the config file for the CLI
"""

import os
import configparser
from .log_utils import setup_logger
import logging
from pathlib import Path

setup_logger(loglevel="INFO")
logger = logging.getLogger(__name__)

NAME = "chain-link"


def set_config(args):
    """
    Get the config file and set the args to the config file values if they are
    not set
    """

    # default location of the config file
    if not args.config_file:
        HOME_DIR = str(Path.home())
        args.config_file = os.path.join(
            HOME_DIR, ".config", "chain-link", "chain-link-cli.conf"
        )

    if not os.path.exists(args.config_file):
        logger.warning("Config file does not exist, creating one now")
        create_config_file(args)
    else:
        logger.warning("Using existing config file: %s", args.config_file)
        config = read_config_file(args)
        args.num_instances = config.getint(
            "DEFAULT", "instances", fallback=args.num_instances
        )
        args.namespace = config.get("DEFAULT", "namespace", fallback=args.namespace)
        args.image_name = config.get(
            "DEFAULT", "chain_link_image", fallback=args.image_name
        )
        args.sleep_time = config.getint(
            "DEFAULT", "sleep_time", fallback=args.sleep_time
        )


def create_config_file(args):
    """
    Create the config file
    """

    config_settings = configparser.ConfigParser()
    config_settings["DEFAULT"] = {
        "instances": args.num_instances,
        "namespace": args.namespace,
        "chain_link_image": args.image_name,
        "sleep_time": args.sleep_time,
    }

    # if user specifies --config some.config then it won't have a directory
    config_dir = os.path.dirname(args.config_file)
    if config_dir and not os.path.exists(config_dir):
        try:
            os.makedirs(config_dir)
        except OSError:
            logger.error("Unable to create config directory: %s", config_dir)

    # write the config_settings to the config file
    with open(args.config_file, "w") as configfile:
        config_settings.write(configfile)

    logger.info("Created config file: %s", args.config_file)


def read_config_file(args):
    """
    Read the config file
    """
    read_config = configparser.ConfigParser()
    read_config.read(args.config_file)
    return read_config
