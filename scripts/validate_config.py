"""Validate GridOracle settings without starting services or provider jobs."""

import argparse

from api.config import ConfigurationError as ApiConfigurationError
from api.config import load_api_settings
from pipeline.config import ConfigurationError as PipelineConfigurationError
from pipeline.config import load_pipeline_settings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode", choices=("api", "pipeline", "scheduler"), required=True
    )
    args = parser.parse_args()

    try:
        if args.mode == "api":
            load_api_settings()
        else:
            load_pipeline_settings(require_weather_key=args.mode == "scheduler")
    except (ApiConfigurationError, PipelineConfigurationError) as error:
        parser.error(str(error))

    print(f"{args.mode} configuration is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
