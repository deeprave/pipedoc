"""
Tests for the MarkdownFileFinder class.

This module tests the file discovery functionality, ensuring that
markdown files are correctly found and filtered.
"""

from pathlib import Path
from typing import List

import pytest

from pipedoc.file_finder import MarkdownFileFinder


class TestMarkdownFileFinder:
    """Test cases for MarkdownFileFinder class."""

    def test_init_with_valid_directory(self, temp_dir: Path):
        """Test initialisation with a valid directory."""
        finder = MarkdownFileFinder(str(temp_dir))
        assert finder.base_directory == temp_dir.resolve()

    def test_init_with_home_directory_expansion(self):
        """Test initialisation with home directory expansion."""
        finder = MarkdownFileFinder("~/")
        assert finder.base_directory == Path.home().resolve()

    def test_find_markdown_files_with_samples(
        self, temp_dir: Path, sample_markdown_files: List[Path]
    ):
        """Test finding markdown files with sample files."""
        finder = MarkdownFileFinder(str(temp_dir))
        found_files = finder.find_markdown_files()

        # Should find all markdown files
        assert len(found_files) == 3

        # Files should be sorted
        assert found_files == sorted(found_files)

        # Check that all sample files are found
        found_basenames = [Path(f).name for f in found_files]
        expected_basenames = [f.name for f in sample_markdown_files]
        assert set(found_basenames) == set(expected_basenames)

    def test_find_markdown_files_empty_directory(self, empty_dir: Path):
        """Test finding markdown files in an empty directory."""
        finder = MarkdownFileFinder(str(empty_dir))
        found_files = finder.find_markdown_files()
        assert found_files == []

    def test_find_markdown_files_nonexistent_directory(self, non_existent_dir: Path):
        """Test finding markdown files in a non-existent directory."""
        finder = MarkdownFileFinder(str(non_existent_dir))

        with pytest.raises(FileNotFoundError):
            finder.find_markdown_files()

    def test_find_markdown_files_file_instead_of_directory(self, temp_dir: Path):
        """Test finding markdown files when path is a file, not directory."""
        # Create a file
        test_file = temp_dir / "test.txt"
        test_file.write_text("test content")

        finder = MarkdownFileFinder(str(test_file))

        with pytest.raises(NotADirectoryError):
            finder.find_markdown_files()

    def test_get_relative_path(self, temp_dir: Path, sample_markdown_files: List[Path]):
        """Test getting relative paths from absolute paths."""
        finder = MarkdownFileFinder(str(temp_dir))

        for file_path in sample_markdown_files:
            relative_path = finder.get_relative_path(str(file_path))
            expected_relative = str(file_path.relative_to(temp_dir))
            assert relative_path == expected_relative

    def test_validate_directory_valid(self, temp_dir: Path):
        """Test directory validation with valid directory."""
        finder = MarkdownFileFinder(str(temp_dir))
        # Should not raise any exception
        finder.validate_directory()

    def test_validate_directory_nonexistent(self, non_existent_dir: Path):
        """Test directory validation with non-existent directory."""
        finder = MarkdownFileFinder(str(non_existent_dir))

        with pytest.raises(FileNotFoundError):
            finder.validate_directory()

    def test_validate_directory_file_instead_of_dir(self, temp_dir: Path):
        """Test directory validation when path is a file."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("test content")

        finder = MarkdownFileFinder(str(test_file))

        with pytest.raises(NotADirectoryError):
            finder.validate_directory()

    def test_markdown_extensions_coverage(self, temp_dir: Path):
        """Test that all supported markdown extensions are found."""
        # Create files with different extensions
        extensions = ["md", "markdown", "mdown", "mkd"]
        created_files = []

        for ext in extensions:
            file_path = temp_dir / f"test.{ext}"
            file_path.write_text(f"# Test {ext}")
            created_files.append(file_path)

        finder = MarkdownFileFinder(str(temp_dir))
        found_files = finder.find_markdown_files()

        assert len(found_files) == len(extensions)

        # Check that all extensions are represented
        found_extensions = {Path(f).suffix[1:] for f in found_files}
        assert found_extensions == set(extensions)

    def test_recursive_search(self, temp_dir: Path):
        """Test that files are found recursively in subdirectories."""
        # Create nested directory structure
        level1 = temp_dir / "level1"
        level1.mkdir()
        level2 = level1 / "level2"
        level2.mkdir()
        level3 = level2 / "level3"
        level3.mkdir()

        # Create files at different levels
        (temp_dir / "root.md").write_text("# Root")
        (level1 / "level1.md").write_text("# Level 1")
        (level2 / "level2.md").write_text("# Level 2")
        (level3 / "level3.md").write_text("# Level 3")

        finder = MarkdownFileFinder(str(temp_dir))
        found_files = finder.find_markdown_files()

        assert len(found_files) == 4

        # Check that files from all levels are found
        found_names = {Path(f).name for f in found_files}
        expected_names = {"root.md", "level1.md", "level2.md", "level3.md"}
        assert found_names == expected_names
