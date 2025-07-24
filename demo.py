#!/usr/bin/env python3
"""
Demo script showing pipedoc functionality.

This script demonstrates how pipedoc works by creating sample documentation
and showing the output that would be served through the named pipe.
"""

import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from pipedoc.server import MarkdownPipeServer


def create_demo_docs(temp_dir: Path):
    """Create demo documentation files."""
    print("Creating demo documentation structure...")
    
    # Project README
    readme = temp_dir / "README.md"
    readme.write_text("""# My Awesome Project

Welcome to my awesome project! This is a demonstration of how pipedoc
can serve multiple markdown files through a named pipe.

## What is this project?

This project showcases:
- Markdown file processing
- Named pipe communication
- Multi-client serving
- SOLID architecture principles

## Getting Started

See the user guide for detailed instructions.
""")
    
    # Create docs directory
    docs_dir = temp_dir / "docs"
    docs_dir.mkdir()
    
    # Installation guide
    install = docs_dir / "installation.md"
    install.write_text("""# Installation Guide

## Prerequisites

- Python 3.8 or higher
- Unix-like operating system
- Basic command line knowledge

## Installation Steps

1. **Download the package**
   ```bash
   git clone https://github.com/user/project.git
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**
   ```bash
   python main.py
   ```

## Verification

To verify the installation worked:
```bash
python -c "import myproject; print('Success!')"
```
""")
    
    # User guide
    guide = docs_dir / "user-guide.markdown"
    guide.write_text("""# User Guide

## Basic Usage

The application is designed to be simple and intuitive.

### Starting the Application

```bash
myproject start --config config.yaml
```

### Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `--port` | Server port | 8080 |
| `--host` | Server host | localhost |
| `--debug` | Debug mode | false |

### Common Tasks

#### Task 1: Processing Data
1. Load your data file
2. Run the processor
3. Check the output

#### Task 2: Generating Reports
1. Configure report settings
2. Run the generator
3. View results in browser

## Troubleshooting

### Common Issues

**Issue**: Application won't start
**Solution**: Check that all dependencies are installed

**Issue**: Port already in use
**Solution**: Use a different port with `--port` option
""")
    
    # API documentation
    api_dir = docs_dir / "api"
    api_dir.mkdir()
    
    api = api_dir / "reference.mdown"
    api.write_text("""# API Reference

## Core Classes

### DataProcessor

Handles data processing operations.

```python
from myproject import DataProcessor

processor = DataProcessor()
result = processor.process(data)
```

#### Methods

##### `process(data: dict) -> dict`

Process input data and return results.

**Parameters:**
- `data`: Input data dictionary

**Returns:**
- Processed data dictionary

**Example:**
```python
data = {"input": "hello world"}
result = processor.process(data)
print(result)  # {"output": "HELLO WORLD"}
```

### ReportGenerator

Generates reports from processed data.

```python
from myproject import ReportGenerator

generator = ReportGenerator()
report = generator.generate(data, template="default")
```

#### Methods

##### `generate(data: dict, template: str = "default") -> str`

Generate a report from data.

**Parameters:**
- `data`: Data to include in report
- `template`: Report template name

**Returns:**
- Generated report as string

## Utility Functions

### `validate_config(config: dict) -> bool`

Validate configuration dictionary.

### `load_data(filepath: str) -> dict`

Load data from file.
""")
    
    print("✓ Demo documentation created")
    return [readme, install, guide, api]


def main():
    """Run the demo."""
    print("=== Pipedoc Demo ===\n")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create demo documentation
        create_demo_docs(temp_path)
        
        # Create and run server (content preparation only)
        print("\nInitializing pipedoc server...")
        server = MarkdownPipeServer(str(temp_path))
        
        print("Validating setup...")
        server.validate_setup()
        
        print("Preparing content...")
        content = server.prepare_content()
        
        print("\n" + "="*80)
        print("DEMO: This is what would be served through the named pipe:")
        print("="*80)
        
        # Show first 2000 characters of the content
        preview = content[:2000]
        print(preview)
        
        if len(content) > 2000:
            print(f"\n... (truncated, full content is {len(content)} characters)")
        
        print("\n" + "="*80)
        
        # Show statistics
        stats = server.get_content_stats()
        print(f"\nContent Statistics:")
        print(f"  Total length: {stats['total_length']} characters")
        print(f"  Lines: {stats['line_count']}")
        print(f"  Words: {stats['word_count']}")
        print(f"  Characters (no whitespace): {stats['character_count']}")
        
        print(f"\nIn a real scenario:")
        print(f"1. The server would create a named pipe (e.g., /tmp/pipedoc_12345)")
        print(f"2. Multiple processes could read from this pipe simultaneously")
        print(f"3. Each reader would get the complete concatenated content")
        print(f"4. The server would handle multiple clients with threading")
        
        print(f"\nTo use this in practice:")
        print(f"  Terminal 1: pipedoc {temp_path}")
        print(f"  Terminal 2: cat /tmp/pipedoc_12345")
        print(f"  Terminal 3: less /tmp/pipedoc_12345")
        
        server.cleanup()
        
        print(f"\n🎉 Demo completed successfully!")


if __name__ == "__main__":
    main()
