"""
This module contains the argument parser for the chain-link cli
"""
import argparse
from .log_utils import setup_logger
import logging

setup_logger(loglevel="INFO")
logger = logging.getLogger(__name__)


def create_parser():
    """
    Create the argument parser for the chain-link cli
    """
    parser = argparse.ArgumentParser(
        description="Deploy the chain-link application to a Kubernetes cluster"
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("deploy", help="Deploy chain-link to Kubernetes")
    subparsers.add_parser("validate", help="Validate chain-link configuration")
    generate_parser = subparsers.add_parser(
        "generate", help="Generate chain-link kubernetes yaml"
    )
    subparsers.add_parser("dry-run", help="Generate chain-link kubernetes yaml")

    generate_parser.add_argument(
        "--output-directory",
        type=str,
        help="Directory to output the kubernetes yaml",
        required=False,
        dest="output_directory",
        default="~/.config/chain-link/manifests",
    )

    parser.add_argument(
        "--instances",
        type=int,
        help="Number of instances to deploy",
        required=False,
        dest="num_instances",
        default=3,
    )
    parser.add_argument(
        "--namespace",
        type=str,
        help="Namespace to deploy to",
        required=False,
        dest="namespace",
        default="chain-link",
    )
    parser.add_argument(
        "--chain-link-image",
        type=str,
        help="ChainLink image to deploy",
        required=False,
        dest="image_name",
        default="ghcr.io/ccollicutt/chain-link:latest",
    )
    parser.add_argument(
        "--sleep-time",
        type=int,
        help="Time to sleep between loadgenerator requests",
        required=False,
        dest="sleep_time",
        default=60,
    )

    parser.add_argument(
        "-d",
        "--info",
        help="Print lots of infoging statements",
        action="store_const",
        dest="loglevel",
        const="DEBUG",
        default="INFO",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        help="Be verbose",
        action="store_const",
        dest="loglevel",
        const=logging.INFO,
    )
    parser.add_argument(
        "--config-file",
        type=str,
        help="Specify the path to the config file",
        required=False,
        dest="config_file",
    )
    args = parser.parse_args()

    return args, parser
