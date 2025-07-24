"""
Tests for the ContentProcessor class.

This module tests the content processing functionality, ensuring that
markdown files are correctly read, processed, and concatenated.
"""

from pathlib import Path
from typing import List

from pipedoc.content_processor import ContentProcessor


class TestContentProcessor:
    """Test cases for ContentProcessor class."""

    def test_init_with_valid_directory(self, temp_dir: Path):
        """Test initialization with a valid directory."""
        processor = ContentProcessor(str(temp_dir))
        assert processor.base_directory == temp_dir.resolve()

    def test_read_file_content_valid_file(self, temp_dir: Path, sample_content: str):
        """Test reading content from a valid file."""
        test_file = temp_dir / "test.md"
        test_file.write_text(sample_content)

        processor = ContentProcessor(str(temp_dir))
        content = processor.read_file_content(str(test_file))

        assert content == sample_content

    def test_read_file_content_nonexistent_file(self, temp_dir: Path):
        """Test reading content from a non-existent file."""
        processor = ContentProcessor(str(temp_dir))
        content = processor.read_file_content(str(temp_dir / "nonexistent.md"))

        assert content is None

    def test_read_file_content_binary_file(self, temp_dir: Path):
        """Test reading content from a binary file."""
        binary_file = temp_dir / "binary.bin"
        # Use invalid UTF-8 bytes that will definitely cause UnicodeDecodeError
        binary_file.write_bytes(b"\xff\xfe\x00\x00\x80\x81\x82\x83")

        processor = ContentProcessor(str(temp_dir))
        content = processor.read_file_content(str(binary_file))

        # Should return None due to UnicodeDecodeError
        assert content is None

    def test_create_file_separator(self, temp_dir: Path):
        """Test creating file separators."""
        processor = ContentProcessor(str(temp_dir))

        # Create a test file path
        test_file = temp_dir / "subdir" / "test.md"
        separator = processor.create_file_separator(str(test_file))

        expected_relative_path = "subdir/test.md"
        assert expected_relative_path in separator
        assert "=" * 60 in separator
        assert "FILE:" in separator

    def test_process_file_valid(self, temp_dir: Path, sample_content: str):
        """Test processing a valid file."""
        test_file = temp_dir / "test.md"
        test_file.write_text(sample_content)

        processor = ContentProcessor(str(temp_dir))
        result = processor.process_file(str(test_file))

        assert result is not None
        assert sample_content in result
        assert "FILE: test.md" in result
        assert "=" * 60 in result

    def test_process_file_invalid(self, temp_dir: Path):
        """Test processing an invalid file."""
        processor = ContentProcessor(str(temp_dir))
        result = processor.process_file(str(temp_dir / "nonexistent.md"))

        assert result is None

    def test_concatenate_files_empty_list(self, temp_dir: Path):
        """Test concatenating an empty list of files."""
        processor = ContentProcessor(str(temp_dir))
        result = processor.concatenate_files([])

        assert result == ""

    def test_concatenate_files_valid_files(
        self, temp_dir: Path, sample_markdown_files: List[Path]
    ):
        """Test concatenating valid markdown files."""
        processor = ContentProcessor(str(temp_dir))
        file_paths = [str(f) for f in sample_markdown_files]
        result = processor.concatenate_files(file_paths)

        assert result != ""

        # Check that all files are represented
        for file_path in sample_markdown_files:
            relative_path = file_path.relative_to(temp_dir)
            assert f"FILE: {relative_path}" in result

        # Check that content from all files is present
        assert "README" in result
        assert "User Guide" in result
        assert "Notes" in result

    def test_concatenate_files_mixed_valid_invalid(self, temp_dir: Path):
        """Test concatenating a mix of valid and invalid files."""
        # Create one valid file
        valid_file = temp_dir / "valid.md"
        valid_file.write_text("# Valid Content")

        # Include one invalid file path
        invalid_file = temp_dir / "invalid.md"

        processor = ContentProcessor(str(temp_dir))
        file_paths = [str(valid_file), str(invalid_file)]
        result = processor.concatenate_files(file_paths)

        # Should contain content from valid file only
        assert "Valid Content" in result
        assert "FILE: valid.md" in result

    def test_get_content_stats_empty_content(self, temp_dir: Path):
        """Test getting statistics for empty content."""
        processor = ContentProcessor(str(temp_dir))
        stats = processor.get_content_stats("")

        expected_stats = {
            "total_length": 0,
            "line_count": 0,
            "word_count": 0,
            "character_count": 0,
        }
        assert stats == expected_stats

    def test_get_content_stats_sample_content(
        self, temp_dir: Path, sample_content: str
    ):
        """Test getting statistics for sample content."""
        processor = ContentProcessor(str(temp_dir))
        stats = processor.get_content_stats(sample_content)

        assert stats["total_length"] == len(sample_content)
        assert stats["line_count"] == sample_content.count("\n")
        assert stats["word_count"] == len(sample_content.split())
        assert stats["character_count"] == len(
            sample_content.replace("\n", "").replace(" ", "")
        )

        # Verify specific values for our sample content
        assert stats["total_length"] > 0
        assert stats["line_count"] > 0
        assert stats["word_count"] > 0
        assert stats["character_count"] > 0

    def test_unicode_content_handling(self, temp_dir: Path):
        """Test handling of Unicode content in files."""
        unicode_content = (
            "# Unicode Test\n\n🚀 Rocket emoji\n\nChinese: 你好世界\n\nEmoji: 😀😃😄"
        )

        test_file = temp_dir / "unicode.md"
        test_file.write_text(unicode_content, encoding="utf-8")

        processor = ContentProcessor(str(temp_dir))
        content = processor.read_file_content(str(test_file))

        assert content == unicode_content
        assert "🚀" in content
        assert "你好世界" in content
        assert "😀😃😄" in content

    def test_large_file_handling(self, temp_dir: Path):
        """Test handling of large files."""
        # Create a large content string
        large_content = "# Large File\n\n" + "This is a line of text.\n" * 10000

        test_file = temp_dir / "large.md"
        test_file.write_text(large_content)

        processor = ContentProcessor(str(temp_dir))
        content = processor.read_file_content(str(test_file))

        assert content == large_content
        assert len(content) > 100000  # Should be quite large

    def test_file_separator_format(self, temp_dir: Path):
        """Test the format of file separators."""
        processor = ContentProcessor(str(temp_dir))

        test_file = temp_dir / "docs" / "guide.md"
        separator = processor.create_file_separator(str(test_file))

        lines = separator.split("\n")

        # Should start and end with empty lines
        assert lines[0] == ""
        assert lines[1] == ""

        # Should have separator line
        assert "=" * 60 in lines[2]

        # Should have file path
        assert "FILE: docs/guide.md" in lines[3]

        # Should have another separator line
        assert "=" * 60 in lines[4]

        # Should end with empty lines
        assert lines[5] == ""
        assert lines[6] == ""
