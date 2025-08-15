"""cli entry point for embodyfile.

Parse command line arguments, invoke methods based on arguments.
"""

import argparse
import logging
import sys
from pathlib import Path

from . import __version__
from .embodyfile import analyse_ppg
from .embodyfile import process_file
from .parser import read_data


def main(args=None):
    """Entry point for embody-file cli.

    The .toml entry_point wraps this in sys.exit already so this effectively
    becomes sys.exit(main()).
    The __main__ entry point similarly wraps sys.exit().
    """
    if args is None:
        args = sys.argv[1:]

    parsed_args = __get_args(args)
    logging.basicConfig(
        level=getattr(logging, parsed_args.log_level.upper(), logging.INFO),
        format="%(asctime)s:%(levelname)s:%(message)s",
        datefmt="%H:%M:%S",
    )

    if not parsed_args.src_file.exists():
        logging.error(f"Source file not found: {parsed_args.src_file}. Exiting.")
        sys.exit(-1)
    output_base = parsed_args.src_file.with_suffix("")

    __check_if_destination_files_exist(output_base, parsed_args)

    if parsed_args.print_stats:
        __print_stats(parsed_args)
        sys.exit(0)

    if parsed_args.analyse_ppg:
        __analyse_ppg(parsed_args)
        sys.exit(0)

    # Process the file with the specified output formats
    try:
        process_file(
            parsed_args.src_file,
            output_base,  # Pass base path without extension
            parsed_args.output_format,
            parsed_args.strict,
        )
    except ValueError as e:
        logging.error(str(e))
        sys.exit(-1)


def __analyse_ppg(parsed_args: argparse.Namespace) -> None:
    with open(parsed_args.src_file, "rb") as f:
        try:
            data = read_data(f, parsed_args.strict, parsed_args.samplerate)
            logging.info(f"Loaded data from: {parsed_args.src_file}")
            analyse_ppg(data)
        except (OSError, ValueError, LookupError) as e:
            logging.error(f"Reading file failed: {e}", exc_info=True)
            sys.exit(-1)


def __print_stats(parsed_args: argparse.Namespace) -> None:
    with open(parsed_args.src_file, "rb") as f:
        try:
            read_data(f, parsed_args.strict, parsed_args.samplerate)
            logging.info(f"Loaded data from: {parsed_args.src_file}")
        except (OSError, ValueError, LookupError) as e:
            logging.error(f"Reading file failed: {e}", exc_info=True)
            sys.exit(-1)
    logging.info(f"Stats printed for file: {parsed_args.src_file}")


def __check_if_destination_files_exist(output_base: Path, parsed_args: argparse.Namespace) -> None:
    for format_name in parsed_args.output_format:
        dst_file = output_base.with_suffix(f".{format_name.lower()}")
        if dst_file.exists() and not parsed_args.force:
            logging.error(f"Destination exists: {dst_file}. Use --force to force parsing to destination anyway.")
            sys.exit(-1)


def __get_args(args) -> argparse.Namespace:
    """Parse arguments passed in from shell."""
    return __get_parser().parse_args(args)


def __get_parser():
    """Return ArgumentParser for pypyr cli."""
    parser = argparse.ArgumentParser(
        allow_abbrev=True,
        description="EmBody CLI application",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("src_file", help="Location of the binary source file", type=Path)
    log_levels = ["CRITICAL", "WARNING", "INFO", "DEBUG"]
    parser.add_argument(
        "-l",
        "--log-level",
        help=f"Log level ({log_levels})",
        choices=log_levels,
        default="INFO",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        help="Echo version number.",
        version=f"{__version__}",
    )
    parser.add_argument(
        "-f",
        "--force",
        help="Force decoding if output files exist",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "-s",
        "--strict",
        help="Fail on any parse errors",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "-o",
        "--output-format",
        help="Output format(s) for decoded data (CSV, HDF_LEGACY, HDF, PARQUET). Can specify multiple formats: -o CSV HDF",
        choices=["CSV", "HDF_LEGACY", "HDF", "PARQUET"],
        nargs="+",
        default=["HDF_LEGACY"],
    )
    parser.add_argument(
        "-p",
        "--print-stats",
        help="Print stats (without outputting anything)",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "-a",
        "--analyse-ppg",
        help="Analyse PPG data",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "-r",
        "--samplerate",
        help="Samplerate <float>. If not selected, a samplerate will be calculated from the data.",
        type=float,
    )

    return parser


if __name__ == "__main__":
    main()
