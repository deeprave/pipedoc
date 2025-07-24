# justfile for pipedoc development

# Show available commands
default:
    @just --list

# Show detailed help with recipe descriptions and usage examples
help:
    #!/usr/bin/env python3
    import re
    import sys
    from pathlib import Path
    
    def parse_justfile():
        """Parse the justfile and extract recipes with their comments."""
        justfile_path = Path("justfile")
        if not justfile_path.exists():
            print("❌ justfile not found!")
            return []
        
        recipes = []
        current_comment = ""
        
        with open(justfile_path, 'r') as f:
            lines = f.readlines()
        
        for i, line in enumerate(lines):
            line = line.rstrip()
            
            # Skip empty lines and the shebang
            if not line or line.startswith('#!'):
                continue
            
            # Collect comments
            if line.startswith('#') and not line.startswith('#!/'):
                comment = line[1:].strip()
                if comment:  # Only non-empty comments
                    current_comment = comment
                continue
            
            # Match recipe definitions (name followed by colon)
            recipe_match = re.match(r'^([a-zA-Z][a-zA-Z0-9_-]*)\s*:', line)
            if recipe_match:
                recipe_name = recipe_match.group(1)
                recipes.append({
                    'name': recipe_name,
                    'description': current_comment,
                    'line': i + 1
                })
                current_comment = ""  # Reset for next recipe
        
        return recipes
    
    def print_help():
        """Print formatted help information."""
        print("🔧 Pipedoc Development Commands")
        print("=" * 50)
        print()
        
        recipes = parse_justfile()
        if not recipes:
            print("❌ No recipes found!")
            return
        
        # Group recipes by category
        categories = {
            'Core': ['default', 'help'],
            'Setup': ['install', 'dev-install', 'setup'],
            'Testing': ['test', 'coverage', 'coverage-html'],
            'Code Quality': ['lint', 'lint-fix', 'format', 'format-check', 'quality'],
            'Build & Deploy': ['build', 'clean'],
            'Development': ['run', 'demo', 'status']
        }
        
        # Create reverse mapping
        recipe_to_category = {}
        for category, recipe_names in categories.items():
            for name in recipe_names:
                recipe_to_category[name] = category
        
        # Group recipes
        categorized = {}
        uncategorized = []
        
        for recipe in recipes:
            category = recipe_to_category.get(recipe['name'])
            if category:
                if category not in categorized:
                    categorized[category] = []
                categorized[category].append(recipe)
            else:
                uncategorized.append(recipe)
        
        # Print categorized recipes
        for category in ['Core', 'Setup', 'Testing', 'Code Quality', 'Build & Deploy', 'Development']:
            if category in categorized:
                print(f"📁 {category}")
                print("-" * (len(category) + 3))
                for recipe in categorized[category]:
                    desc = recipe['description'] or "No description available"
                    print(f"  {recipe['name']:<15} {desc}")
                print()
        
        # Print uncategorized recipes
        if uncategorized:
            print("📁 Other")
            print("-" * 8)
            for recipe in uncategorized:
                desc = recipe['description'] or "No description available"
                print(f"  {recipe['name']:<15} {desc}")
            print()
        
        # Print usage examples
        print("💡 Usage Examples")
        print("-" * 18)
        print("  just                    # Show all available recipes")
        print("  just help               # Show this detailed help")
        print("  just quality            # Run all quality checks")
        print("  just coverage           # Run tests with coverage")
        print("  just setup              # Setup development environment")
        print("  just clean build        # Clean and build package")
        print("  just --dry-run quality  # Preview what quality would do")
        print("  just --choose           # Interactive recipe selection")
        print()
        
        print("🔗 More Information")
        print("-" * 20)
        print("  just --help             # Show just command help")
        print("  just --list             # Simple recipe list")
        print("  just --show <recipe>    # Show recipe details")
        print()
    
    if __name__ == "__main__":
        print_help()

# Install the package
install:
    uv sync

# Install with development dependencies
dev-install:
    uv sync --dev

# Run tests
test:
    pytest tests/

# Run tests with coverage report
coverage:
    pytest tests/ --cov --cov-report=term-missing --cov-report=html
    @echo ""
    @echo "HTML coverage report: htmlcov/index.html"

# Open coverage HTML report in browser
coverage-html:
    open htmlcov/index.html

# Run linting with ruff
lint:
    ruff check src/ tests/

# Run linting with automatic fixes
lint-fix:
    ruff check src/ tests/ --fix

# Format code with ruff
format:
    ruff format src/ tests/

# Check if code is properly formatted
format-check:
    ruff format --check src/ tests/

# Run all quality checks (lint + format check + tests)
quality:
    ruff check src/ tests/
    ruff format --check src/ tests/
    pytest tests/

# Clean up generated files
clean:
    rm -rf htmlcov/
    rm -rf .pytest_cache/
    rm -rf .ruff_cache/
    rm -rf dist/
    rm -rf build/
    rm -rf *.egg-info/
    rm -f .coverage
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Build the package
build:
    uv build

# Run pipedoc on the current directory (for testing)
run:
    uv run pipedoc .

# Run the demo script
demo:
    python demo.py

# Show project status (dependencies, coverage, etc.)
status:
    @echo "=== Project Status ==="
    @echo "Dependencies:"
    @uv pip list --format=columns
    @echo ""
    @echo "=== Quick Quality Check ==="
    @ruff check src/ tests/ --quiet && echo "✓ Linting: PASS" || echo "✗ Linting: FAIL"
    @ruff format --check src/ tests/ --quiet && echo "✓ Formatting: PASS" || echo "✗ Formatting: FAIL"
    @pytest tests/ --quiet && echo "✓ Tests: PASS" || echo "✗ Tests: FAIL"

# Run development setup from scratch
setup:
    uv sync --dev
    @echo ""
    @echo "Development environment ready!"
    @echo "Run 'just quality' to verify everything works."
