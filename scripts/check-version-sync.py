#!/usr/bin/env python3
"""
Pre-commit hook to check that __version__ in __init__.py matches pyproject.toml version.

This ensures version consistency across the package and prevents deployment
of packages with mismatched version strings.
"""

import argparse
import re
import sys
import tomllib
from pathlib import Path


def get_pyproject_data() -> dict:
    """Read pyproject.toml data."""
    pyproject_path = Path("pyproject.toml")
    if not pyproject_path.exists():
        print("Error: pyproject.toml not found")
        return {}

    try:
        with open(pyproject_path, "rb") as f:
            return tomllib.load(f)
    except Exception as e:
        print(f"Error reading pyproject.toml: {e}")
        return {}


def get_pyproject_version() -> str:
    """Read version from pyproject.toml."""
    pyproject = get_pyproject_data()
    if not pyproject:
        return ""

    try:
        return pyproject["project"]["version"]
    except KeyError:
        print("Error: version not found in pyproject.toml")
        return ""


def discover_init_path() -> Path:
    """Discover __init__.py path based on project name from pyproject.toml."""
    pyproject = get_pyproject_data()
    if not pyproject:
        # Fallback to hardcoded path if no pyproject.toml
        return Path("src/pipedoc/__init__.py")

    try:
        project_name = pyproject["project"]["name"]

        # Try common patterns
        candidates = [
            Path(f"./{project_name}/__init__.py"),
            Path(f"./src/{project_name}/__init__.py"),
        ]

        for candidate in candidates:
            if candidate.exists():
                return candidate

        # If none found, return the first candidate for error reporting
        return candidates[-1]  # Prefer src/ layout

    except KeyError:
        print("Warning: project name not found in pyproject.toml, using default path")
        return Path("src/pipedoc/__init__.py")


def get_init_version(init_path: Path = None) -> str:
    """Read __version__ from __init__.py."""
    if init_path is None:
        init_path = discover_init_path()

    if not init_path.exists():
        print(f"Error: {init_path} not found")
        return ""

    try:
        content = init_path.read_text(encoding="utf-8")
        if match := re.search(
            r'^__version__\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE
        ):
            return match[1]
        print(f"Error: __version__ not found in {init_path}")
        return ""
    except Exception as e:
        print(f"Error reading {init_path}: {e}")
        return ""


def fix_init_version(target_version: str, init_path: Path = None) -> bool:
    """Update __version__ in __init__.py to match target version."""
    if init_path is None:
        init_path = discover_init_path()

    if not init_path.exists():
        print(f"Error: {init_path} not found")
        return False

    try:
        return _fix_version(init_path, target_version)
    except Exception as e:
        print(f"Error updating {init_path}: {e}")
        return False


def _fix_version(init_path, target_version):
    content = init_path.read_text(encoding="utf-8")

    # Replace __version__ = "old" with __version__ = "new"
    new_content = re.sub(
        r'^(__version__\s*=\s*)["\']([^"\']+)["\']',
        rf'\1"{target_version}"',
        content,
        flags=re.MULTILINE
    )

    if new_content == content:
        print(f"Error: Could not find __version__ to update in {init_path}")
        return False

    init_path.write_text(new_content, encoding="utf-8")
    print(f"✓ Updated {init_path} version to: {target_version}")
    return True


def main() -> int:
    """Check version synchronisation between pyproject.toml and __init__.py."""
    parser = argparse.ArgumentParser(
        description="Check and optionally fix version synchronisation between pyproject.toml and __init__.py"
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Autofix __init__.py version to match pyproject.toml"
    )
    parser.add_argument(
        "--init-path",
        type=Path,
        help="Path to __init__.py file (default: auto-discover from project name)"
    )
    args = parser.parse_args()

    # Use the provided path or auto-discover
    init_path = args.init_path

    pyproject_version = get_pyproject_version()
    init_version = get_init_version(init_path)

    if not pyproject_version or not init_version:
        return 1

    # Show which path was used for transparency
    actual_init_path = init_path or discover_init_path()

    if pyproject_version == init_version:
        print(f"✓ Version sync OK: {pyproject_version}")
        print(f"  pyproject.toml: {pyproject_version}")
        print(f"  {actual_init_path}: {init_version}")
        return 0
    else:
        print("✗ Version mismatch!")
        print(f"  pyproject.toml: {pyproject_version}")
        print(f"  {actual_init_path}: {init_version}")
        print()

        if args.fix:
            if fix_init_version(pyproject_version, init_path):
                print("Version synced successfully. Re-run again to verify the fix.")
            else:
                print("Failed to fix version.")
        else:
            print("Fix by updating __init__.py:")
            print(f'  __version__ = "{pyproject_version}"')
            print("Or run with --fix to automatically update:")
            print(f"  {sys.argv[0]} --fix")

        return 1


if __name__ == "__main__":
    sys.exit(main())
