# This file makes the dirtree_lib directory a Python package.# -*- coding: utf-8 -*-
"""
IntuitiveDirTree Package - A User-Friendly Directory Tree Visualizer with LLM Export

This package provides tools for:
- Visualizing directory structures as customizable trees
- Interactive filtering of files and directories
- Exporting file content in formats suitable for Large Language Models (LLMs)
- Customizable styling and display options

Usage:
    from dirtree_lib import IntuitiveDirTree
    tree = IntuitiveDirTree(root_dir="path/to/directory")
    tree.run()
"""

# Package version
__version__ = "2.3.0"

# Import public classes and functions for direct access
from .dirtree_core import IntuitiveDirTree
from .dirtree_config import COMMON_EXCLUDES, DEFAULT_LLM_EXCLUDED_EXTENSIONS
from .dirtree_cli import main

# Define what gets imported with 'from dirtree_lib import *'
__all__ = ['IntuitiveDirTree', 'COMMON_EXCLUDES', 'DEFAULT_LLM_EXCLUDED_EXTENSIONS', 'main']