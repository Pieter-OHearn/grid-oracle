"""APScheduler entry point for the pipeline service."""

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    logger.info("Pipeline scheduler starting — no jobs configured yet.")


if __name__ == "__main__":
    main()
