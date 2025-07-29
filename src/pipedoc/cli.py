"""
Command-line interface for pipedoc using Click.

This module provides a clean, extensible CLI interface that can be easily
extended with additional commands and options in the future.
"""

import sys
from pathlib import Path

import click

from .server import MarkdownPipeServer


def version_callback(ctx, param, value):
    """Callback for the version option that prints version and exits."""
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
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option(
    "--version",
    is_flag=True,
    expose_value=False,
    is_eager=True,
    callback=version_callback,
    help="Show version and exit"
)
@click.help_option("--help", "-h")
def main(docs_directory: Path, verbose: bool) -> None:
    """
    Serve concatenated markdown files through a named pipe.

    DOCS_DIRECTORY is the path to the directory containing markdown files.
    The script will recursively find all markdown files (.md, .markdown, .mdown, .mkd),
    concatenate them with clear file separators, and serve the content through a named pipe
    that multiple processes can read from simultaneously.

    Examples:

        pipedoc ~/my-documentation

        pipedoc /path/to/docs --verbose
    """
    if verbose:
        click.echo(f"Starting pipedoc with directory: {docs_directory}")
        click.echo("Verbose mode enabled")

    # Convert Path to string for compatibility with existing code
    docs_directory_str = str(docs_directory.resolve())

    try:
        # Create and run the server
        server = MarkdownPipeServer(docs_directory_str)
        exit_code = server.run()

        if verbose and exit_code == 0:
            click.echo("Server shutdown successfully")

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
    """Show information about markdown files in the directory."""
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
