#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
IntuitiveDirTree - A User-Friendly Directory Tree Printer with LLM Export

Version: 2.3.0

This script generates a tree representation of a directory structure with advanced
filtering options and can export file content in a format suitable for Large Language Models.

Features:
- Interactive directory and filter selection
- Customizable tree styles and visualization options
- Smart exclusion of common directories like .git, node_modules, etc.
- LLM-friendly export with file content
- Support for multiple output formats and styles

Usage:
    python dirtree.py [directory] [options]
    python dirtree.py -i  # For interactive setup (recommended)
    python dirtree.py -h  # For help on all options
"""

import sys
from pathlib import Path

# Ensure the 'dirtree_lib' directory is in the Python path
# This allows running the script directly from its location
script_dir = Path(__file__).parent.resolve()
lib_dir = script_dir / 'dirtree_lib'

if lib_dir.exists() and lib_dir.is_dir():
    if str(lib_dir) not in sys.path:
        sys.path.insert(0, str(lib_dir.parent))  # Add the parent directory to sys.path
else:
    # Try for development setup - if we're running from the source directory
    # where all modules are in the same directory as this script
    if script_dir not in sys.path:
        sys.path.insert(0, str(script_dir))

try:
    # Try to import normally from package first
    try:
        from dirtree_lib import __version__, main
    except ImportError:
        # If that fails, try relative import for development version
        from dirtree_cli import main, __version__
        
    # Show initialization message
    print(f"IntuitiveDirTree v{__version__} - Starting up...")
    
except ImportError as e:
    print(f"Error: Could not import required modules.", file=sys.stderr)
    print(f"Details: {e}", file=sys.stderr)
    print(f"Please ensure the package is correctly installed or the 'dirtree_lib' directory exists.", file=sys.stderr)
    print(f"You may need to run: pip install -e .", file=sys.stderr)
    sys.exit(1)

if __name__ == "__main__":
    # Execute the main command-line interface logic
    main()