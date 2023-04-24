import logging
import sys
from .chainlink import ChainLink, ChainLinkError
from .log_utils import setup_logger
from .utils import check_python_version, check_required_modules
from .arg_parser import create_parser
from .config import set_config

NAME = "chain-link"


def run_cli():
    check_python_version()
    required_modules = ["argparse", "kubernetes", "json", "importlib"]
    check_required_modules(required_modules)

    args, parser = create_parser()

    setup_logger(loglevel=args.loglevel)
    logger = logging.getLogger(__name__)

    set_config(args)

    # if args.command is deploy, validate, or generate, then we need to
    # log the configuration
    if args.command in ["deploy", "validate", "generate", "dry-run"]:
        logger.info("Using the following configuration...")
        logger.info("Number of instances: %s", args.num_instances)
        logger.info("Namespace: %s", args.namespace)
        logger.info("ChainLink image: %s", args.image_name)
        logger.info("Loadgenerator sleep time: %s", args.sleep_time)

    if args.command == "deploy":
        logger.info("Deploying chain-link to Kubernetes cluster...")

        try:
            chainlink = ChainLink(
                NAME,
                args.image_name,
                args.num_instances,
                args.namespace,
                args.sleep_time,
                action="deploy",
            )
        except ChainLinkError as e:
            print(f"An error occurred: {e}")
            sys.exit(1)

    elif args.command == "validate":
        logger.info("Validating chain-link configuration...")
        try:
            chainlink = ChainLink(
                NAME,
                args.image_name,
                args.num_instances,
                args.namespace,
                action="validate",
            )
        except ChainLinkError as e:
            print(f"An error occurred: {e}")
            sys.exit(1)
    elif args.command == "generate":
        logger.info("Generating chain-link kubernetes yaml...")
        try:
            chainlink = ChainLink(
                NAME,
                args.image_name,
                args.num_instances,
                args.namespace,
                args.sleep_time,
                action="generate",
                output_directory=args.output_directory,
            )
        except ChainLinkError as e:
            print(f"An error occurred: {e}")
            sys.exit(1)
    elif args.command == "dry-run":
        logger.warning("dry-run not implemented yet...")
    else:
        parser.print_help()
