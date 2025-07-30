"""
Command-line interface for pipedoc using Click.

This module provides a clean, extensible CLI interface that can be easily
extended with additional commands and options in the future.
"""

import sys
from pathlib import Path

import click

from .server import MarkdownPipeServer
from .logging_config import (
    LoggingConfig,
    HandlerConfig,
    LogHandler,
    LogFormat,
    VerbosityLevel,
    ConfigurableAppLogger,
)
from .app_logger import set_default_logger


def _configure_logging(
    verbose: int,
    quiet: bool,
    log_level: str,
    log_format: str,
    log_file: str,
    log_handlers: str,
    log_exclude: str,
    log_include_only: str,
) -> None:
    """Configure logging based on CLI options."""
    config = LoggingConfig()

    # Determine verbosity level
    if quiet:
        config.verbosity = VerbosityLevel.QUIET
    elif verbose == 0:
        config.verbosity = VerbosityLevel.NORMAL
    elif verbose == 1:
        config.verbosity = VerbosityLevel.VERBOSE
    elif verbose >= 2:
        config.verbosity = VerbosityLevel.VERY_VERBOSE

    # Override with explicit log level if provided
    if log_level:
        config.global_level = log_level.upper()

    # Set format
    format_map = {
        "json": LogFormat.STRUCTURED,
        "simple": LogFormat.SIMPLE,
        "detailed": LogFormat.DETAILED,
    }
    config.global_format = format_map.get(log_format, LogFormat.SIMPLE)

    # Configure handlers
    if log_handlers:
        handler_configs = []
        for handler_name in log_handlers.split(","):
            handler_name = handler_name.strip().lower()
            if handler_name == "console":
                handler_configs.append(HandlerConfig(type=LogHandler.CONSOLE))
            elif handler_name == "file":
                filename = log_file or "logs/pipedoc.log"
                handler_configs.append(
                    HandlerConfig(type=LogHandler.FILE, filename=filename)
                )
            elif handler_name == "rotating":
                filename = log_file or "logs/pipedoc.log"
                handler_configs.append(
                    HandlerConfig(type=LogHandler.ROTATING_FILE, filename=filename)
                )
            elif handler_name == "syslog":
                handler_configs.append(HandlerConfig(type=LogHandler.SYSLOG))

        if handler_configs:
            config.handlers = handler_configs
    elif log_file:
        # Add file handler in addition to console
        config.handlers = [
            HandlerConfig(type=LogHandler.CONSOLE),
            HandlerConfig(type=LogHandler.ROTATING_FILE, filename=log_file),
        ]

    # Component filtering
    if log_exclude:
        config.exclude_components = [c.strip() for c in log_exclude.split(",")]

    if log_include_only:
        config.include_only_components = [
            c.strip() for c in log_include_only.split(",")
        ]

    # Create and set the configured logger as default
    logger = ConfigurableAppLogger(config)
    set_default_logger(logger)


def version_callback(ctx, _, value):
    """Callback for the version option that prints the version and exits."""
    if not value or ctx.resilient_parsing:
        return
    from . import __version__

    click.echo(f"pipedoc version {__version__}")
    ctx.exit()


@click.command()
@click.argument(
    "docs_directory",
    type=click.Path(
        exists=True, file_okay=False, dir_okay=True, readable=True, path_type=Path
    ),
    metavar="DOCS_DIRECTORY",
)
@click.option(
    "--verbose",
    "-v",
    count=True,
    help="Increase verbosity (use -v, -vv for more verbose)",
)
@click.option(
    "--quiet", "-q", is_flag=True, help="Reduce output to warnings and errors only"
)
@click.option(
    "--log-level",
    type=click.Choice(
        ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], case_sensitive=False
    ),
    help="Set explicit log level (overrides verbose/quiet)",
)
@click.option(
    "--log-format",
    type=click.Choice(["json", "simple", "detailed"], case_sensitive=False),
    default="simple",
    help="Log output format",
)
@click.option(
    "--json",
    "json_format",
    is_flag=True,
    help="Use JSON log format (alias for --log-format json)",
)
@click.option(
    "--log-file", type=click.Path(), help="Write logs to file (in addition to console)"
)
@click.option(
    "--log-handlers",
    help="Comma-separated list of log handlers (console,file,syslog,rotating)",
)
@click.option(
    "--log-exclude", help="Comma-separated list of components to exclude from logging"
)
@click.option(
    "--log-include-only",
    help="Comma-separated list of components to include in logging (excludes all others)",
)
@click.option(
    "--version",
    is_flag=True,
    expose_value=False,
    is_eager=True,
    callback=version_callback,
    help="Show version and exit",
)
@click.help_option("--help", "-h")
def main(
    docs_directory: Path,
    verbose: int,
    quiet: bool,
    log_level: str,
    log_format: str,
    log_file: str,
    log_handlers: str,
    log_exclude: str,
    log_include_only: str,
    json_format: bool,
) -> None:
    """
    Serve concatenated markdown files through a named pipe.

    DOCS_DIRECTORY is the path to the directory containing markdown files.
    The script will recursively find all Markdown files (.md, .markdown, .mdown, .mkd),
    concatenate them with clear file separators, and serve the content through a named pipe
    that multiple processes can read from simultaneously.

    Examples:

        pipedoc ~/my-documentation

        pipedoc /path/to/docs --verbose

        pipedoc ~/docs --log-level DEBUG --log-file pipedoc.log

        pipedoc ~/docs --log-handlers console,rotating --log-format detailed

        pipedoc ~/docs --json

        pipedoc ~/docs --log-format json --verbose
    """
    # Handle --json alias
    if json_format:
        log_format = "json"

    # Configure logging first
    _configure_logging(
        verbose,
        quiet,
        log_level,
        log_format,
        log_file,
        log_handlers,
        log_exclude,
        log_include_only,
    )

    # Convert Path to string for compatibility with existing code
    docs_directory_str = str(docs_directory.resolve())

    try:
        # Create and run the server
        server = MarkdownPipeServer(docs_directory_str)
        exit_code = server.run()

        sys.exit(exit_code)

    except KeyboardInterrupt:
        if verbose:
            click.echo("\nReceived interrupt signal, shutting down...")
        sys.exit(0)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        if verbose:
            import traceback

            click.echo(traceback.format_exc(), err=True)
        sys.exit(1)


@click.group()
def cli():
    """Pipedoc - Markdown file serving utility."""
    pass


@cli.command()
@click.argument(
    "docs_directory",
    type=click.Path(
        exists=True, file_okay=False, dir_okay=True, readable=True, path_type=Path
    ),
)
def serve(docs_directory: Path) -> None:
    """Serve markdown files from the specified directory."""
    main.callback(docs_directory, verbose=False, version=False)


@cli.command()
@click.argument(
    "docs_directory",
    type=click.Path(
        exists=True, file_okay=False, dir_okay=True, readable=True, path_type=Path
    ),
)
def info(docs_directory: Path) -> None:
    """Show information about Markdown files in the directory."""
    from .content_processor import ContentProcessor
    from .file_finder import MarkdownFileFinder

    try:
        finder = MarkdownFileFinder(str(docs_directory))
        processor = ContentProcessor(str(docs_directory))

        files = finder.find_markdown_files()

        if not files:
            click.echo(f"No markdown files found in {docs_directory}")
            return

        click.echo(f"Found {len(files)} markdown files in {docs_directory}:")
        for file_path in files:
            relative_path = finder.get_relative_path(file_path)
            click.echo(f"  - {relative_path}")

        # Get content statistics
        content = processor.concatenate_files(files)
        stats = processor.get_content_stats(content)

        click.echo("\nContent Statistics:")
        click.echo(f"  Total length: {stats['total_length']} characters")
        click.echo(f"  Lines: {stats['line_count']}")
        click.echo(f"  Words: {stats['word_count']}")
        click.echo(f"  Characters (no whitespace): {stats['character_count']}")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
