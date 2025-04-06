# tests/conftest.py
import pytest
import sys
import os
from pathlib import Path
from typing import List, Dict, Any

# Make sure the main library path is available
package_root = Path(__file__).parent.parent
sys.path.insert(0, str(package_root))
# Ensure the library modules can be imported
sys.path.insert(0, str(package_root / 'dirtree_lib'))

# Now attempt the imports
try:
    from dirtree_lib.dirtree_core import IntuitiveDirTree
    from dirtree_lib.dirtree_config import COMMON_EXCLUDES
    from dirtree_lib.dirtree_cli import parse_args
except ImportError as e:
    pytest.fail(f"Failed to import dirtree_lib components: {e}\n"
                f"Ensure the package is installed correctly (e.g., 'pip install -e .') "
                f"or PYTHONPATH is set up.\n"
                f"Current sys.path: {sys.path}")


def create_test_structure(base_path: Path, structure: Dict[str, Any]):
    """Recursively creates a directory structure from a dictionary."""
    # Ensure the base path exists
    base_path.mkdir(parents=True, exist_ok=True)

    for name, content in structure.items():
        path = base_path / name
        if isinstance(content, dict):
            path.mkdir(parents=True, exist_ok=True)
            create_test_structure(path, content)
        elif isinstance(content, str): # File content
            # Ensure parent directory exists
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
        elif content is None: # Empty file
            # Ensure parent directory exists
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
        else:
            raise TypeError(f"Unsupported structure type for {name}: {type(content)}")

@pytest.fixture
def base_test_structure(tmp_path):
    """Provides a standard complex directory structure for testing."""
    structure = {
        "project_root": {
            "src": {
                "main.py": "print('hello')",
                "utils": {
                    "helpers.py": "# Utility functions",
                    "data.json": '{"key": "value"}',
                },
                "feature": {
                    "component.js": "// JS Component",
                    "style.css": "body { color: blue; }",
                }
            },
            "tests": {
                "test_main.py": "import pytest",
                "test_helpers.py": "import pytest",
            },
            "node_modules": { # Common exclude target
                "package_a": {
                    "index.js": "// Package A",
                    "readme.md": "Package A Readme"
                },
                "package_b": {
                    "main.js": "// Package B",
                }
            },
            ".git": { # Common exclude target
                "config": "[core]\nrepositoryformatversion = 0",
                "HEAD": "ref: refs/heads/main",
            },
            ".env": "SECRET_KEY=12345", # Hidden file
            "docs": {
                "index.md": "# Documentation",
                "api.md": "## API Reference",
            },
            "data": { # Sometimes excluded
                "input.csv": "col1,col2\n1,2",
                "temp_output.log": "Log line 1", # Excludable by pattern
            },
            "build": { # Common exclude target
                "output.bin": b"binarydata".decode('latin-1'), # Use compatible string for write_text
                "report.txt": "Build report"
            },
            "__pycache__": { # Common exclude target
                "helpers.cpython-39.pyc": "# pyc content"
            },
            "README.md": "# My Project",
            "requirements.txt": "pytest\npick",
            "temp_file.tmp": "Temporary data" # Excludable by pattern
        }
    }
    root = tmp_path / "test_proj"
    create_test_structure(root, structure["project_root"])
    return root

@pytest.fixture
def run_dirtree_and_capture(capsys):
    """Fixture to run IntuitiveDirTree and capture output."""
    def _run(config_overrides: Dict[str, Any]):
        # Ensure root_dir exists and is valid
        if 'root_dir' not in config_overrides:
            raise ValueError("run_dirtree_and_capture requires 'root_dir' in config_overrides")
        root_dir = Path(config_overrides['root_dir'])
        if not root_dir.is_dir():
             raise FileNotFoundError(f"Test setup error: root_dir '{root_dir}' does not exist or is not a directory.")

        # Default config values that can be overridden
        config = {
            'style': 'ascii', # Use predictable ASCII for tests
            'max_depth': None,
            'show_hidden': False,
            'colorize': False, # Disable color for easier assertion
            'show_size': False,
            'include_patterns': None,
            'exclude_patterns': None,
            'use_smart_exclude': True,
            'export_for_llm': False,
            'max_llm_file_size': 100 * 1024,
            'llm_content_extensions': None,
            'llm_indicators': 'included',
            'verbose': False,
            'interactive_prompts': False, # Non-interactive for tests
            'skip_errors': True, # Skip errors during tests
            'output_dir': None
        }
        config.update(config_overrides)

        # Filter config to only include valid arguments for IntuitiveDirTree constructor
        valid_args = {
            k: v for k, v in config.items()
            if k in IntuitiveDirTree.__init__.__code__.co_varnames
        }

        try:
            # Clear cache before run if needed (optional, usually instance is new)
            # IntuitiveDirTree._cached_tree_lines = None
            # IntuitiveDirTree._cached_listed_paths = None

            tree_generator = IntuitiveDirTree(**valid_args)
            tree_generator.run() # This includes generate_tree and print_results
            captured = capsys.readouterr()

            # Also return the generated tree lines and paths for finer checks
            tree_lines = tree_generator._cached_tree_lines or []
            listed_paths = tree_generator._cached_listed_paths or []
            llm_export_file = None
            if config.get('export_for_llm'):
                 # Construct potential filename (might need refinement based on actual naming)
                 export_filename_pattern = f"dirtree_export_{root_dir.name}_*.md"
                 save_dir = Path(config.get('output_dir') or Path.cwd())
                 found_exports = list(save_dir.glob(export_filename_pattern))
                 if found_exports:
                     llm_export_file = found_exports[0] # Assume newest if multiple match

            return captured.out, captured.err, tree_lines, listed_paths, llm_export_file

        except Exception as e:
            pytest.fail(f"IntuitiveDirTree failed to run with config {valid_args}: {e}")

    return _run