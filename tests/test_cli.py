"""
Tests for the CLI interface.

This module tests the command-line interface functionality including
argument parsing, version handling, and error cases.
"""

import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from pipedoc.cli import main


class TestCliVersion:
    """Test CLI version command functionality."""

    def test_version_matches_pyproject(self):
        """Test that __version__ matches pyproject.toml version."""
        # Read version from pyproject.toml
        import tomllib
        with open("pyproject.toml", "rb") as f:
            pyproject = tomllib.load(f)
        expected_version = pyproject["project"]["version"]

        # Import package version
        from pipedoc import __version__
        assert __version__ == expected_version

    def test_version_option_standalone(self):
        """Test that --version works without docs directory."""
        runner = CliRunner()
        result = runner.invoke(main, ['--version'])

        assert result.exit_code == 0
        assert "pipedoc version 2.0.0" in result.output
        assert "docs_directory" not in result.output.lower()  # No error about missing argument

    def test_version_option_output_format(self):
        """Test that --version outputs correct format."""
        runner = CliRunner()
        result = runner.invoke(main, ['--version'])

        assert result.exit_code == 0
        assert result.output.strip() == "pipedoc version 2.0.0"

    def test_version_bypasses_directory_validation(self):
        """Test that --version doesn't validate directory existence."""
        runner = CliRunner()
        # This should work even with non-existent directory in args
        result = runner.invoke(main, ['--version', '/nonexistent/path'])

        assert result.exit_code == 0
        assert "pipedoc version 2.0.0" in result.output
        assert "does not exist" not in result.output

    def test_normal_operation_still_requires_directory(self, temp_dir):
        """Test that normal operation still validates directory."""
        runner = CliRunner()
        result = runner.invoke(main, ['/nonexistent/path'])

        assert result.exit_code != 0
        assert "does not exist" in result.output or "No such file or directory" in result.output

    def test_help_shows_correct_version_usage(self):
        """Test that help text shows version option correctly."""
        runner = CliRunner()
        result = runner.invoke(main, ['--help'])

        assert result.exit_code == 0
        assert "--version" in result.output
        assert "Show version and exit" in result.output

    def test_version_integration(self):
        """Test version command in realistic scenarios."""
        # Test via actual CLI entry point
        result = subprocess.run(["pipedoc", "--version"],
                              capture_output=True, text=True)

        assert result.returncode == 0
        assert "pipedoc version 2.0.0" in result.stdout
        assert result.stderr == ""

    def test_version_with_other_options(self):
        """Test that --version works with other global options."""
        runner = CliRunner()
        result = runner.invoke(main, ['--verbose', '--version'])

        assert result.exit_code == 0
        assert "pipedoc version 2.0.0" in result.output


class TestCliBasic:
    """Test basic CLI functionality."""

    def test_cli_requires_directory_normally(self):
        """Test that CLI requires directory argument for normal operation."""
        runner = CliRunner()
        result = runner.invoke(main, [])

        assert result.exit_code != 0
        assert "Missing argument" in result.output or "Usage:" in result.output
