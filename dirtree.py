#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IntuitiveDirTree - A User-Friendly Directory Tree Visualizer with LLM Export

This script generates a tree representation of a directory structure with advanced
filtering options and can export file content in a format suitable for Large Language Models.
"""

import sys
from pathlib import Path

# Ensure 'dirtree' is in sys.path for correct module resolution.
# This handles running the script from various locations (e.g., project root, or if installed).
script_dir = Path(__file__).resolve().parent
lib_parent_dir = script_dir # If running from project root where dirtree.py and dirtree/ are siblings
lib_dir_as_subdir = script_dir / 'dirtree' # If dirtree is a subdirectory

# Scenario 1: dirtree.py is in project root, dirtree is a subdir.
# Add project_root to path so `from dirtree import ...` works.
if lib_dir_as_subdir.is_dir():
    if str(script_dir) not in sys.path:
        sys.path.insert(0, str(script_dir))
# Scenario 2: dirtree.py is inside dirtree (e.g. during development/testing if run directly)
# Add parent of dirtree (project root) to path.
elif script_dir.name == 'dirtree' and script_dir.parent.is_dir():
    project_root = script_dir.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
# Scenario 3: Potentially installed, rely on standard Python path.

try:
    from dirtree import __version__ # Get version from package
    from dirtree.dirtree_cli import main # Get main CLI function
except ImportError as e:
    print(f"Error: Could not import IntuitiveDirTree components.", file=sys.stderr)
    print(f"Details: {e}", file=sys.stderr)
    print(f"Current sys.path: {sys.path}", file=sys.stderr)
    print("Please ensure the package is correctly installed (e.g., 'pip install -e .') "
          "or run from the project root directory.", file=sys.stderr)
    sys.exit(1)

if __name__ == "__main__":
    # print(f"IntuitiveDirTree v{__version__} - Initializing...") # Optional: moved to CLI main
    main()