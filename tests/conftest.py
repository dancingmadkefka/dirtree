# tests/conftest.py
import pytest
import sys
import os
import traceback
from pathlib import Path
from typing import List, Dict, Any

# Make sure the main library path is available
package_root = Path(__file__).parent.parent
sys.path.insert(0, str(package_root))
# Ensure the library modules can be imported
sys.path.insert(0, str(package_root / 'dirtree'))

# Now attempt the imports
try:
    from dirtree.dirtree_core import IntuitiveDirTree
    from dirtree.dirtree_config import COMMON_DIR_EXCLUDES, COMMON_FILE_EXCLUDES # Updated
    from dirtree.dirtree_cli import parse_args
except ImportError as e:
    pytest.fail(f"Failed to import dirtree components: {e}\n"
                f"Ensure the package is installed correctly (e.g., 'pip install -e .') "
                f"or PYTHONPATH is set up.\n"
                f"Current sys.path: {sys.path}")


def create_test_structure(base_path: Path, structure: Dict[str, Any]):
    """Recursively creates a directory structure from a dictionary."""
    base_path.mkdir(parents=True, exist_ok=True)

    for name, content in structure.items():
        path = base_path / name
        if isinstance(content, dict): # Directory
            path.mkdir(parents=True, exist_ok=True)
            create_test_structure(path, content)
        elif isinstance(content, str): # File with text content
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
        elif isinstance(content, bytes): # File with binary content
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        elif content is None: # Empty file
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
                "main.py": "print('hello from main.py')",
                "utils": {
                    "helpers.py": "# Utility functions from helpers.py",
                    "data.json": '{"key": "value from data.json"}',
                },
                "feature": {
                    "component.js": "// JS Component from component.js",
                    "style.css": "/* CSS from style.css */",
                }
            },
            "tests": { # Often excluded for LLM content by user
                "test_main.py": "import pytest # from test_main.py",
                "test_helpers.py": "import pytest # from test_helpers.py",
                "__pycache__": { # Smart excluded dir
                    "test_cache.pyc": b"test pyc content"
                }
            },
            "node_modules": { # Smart excluded dir
                "package_a": {
                    "index.js": "// Package A from index.js",
                    "readme.md": "Package A Readme from readme.md"
                }
            },
            ".git": { # Smart excluded dir
                "config": "[core]\nrepositoryformatversion = 0",
            },
            ".env": "SECRET_KEY=12345 # from .env", # Hidden file
            "docs": {
                "index.md": "# Documentation from index.md",
                "api.md": "## API Reference from api.md",
            },
            "coverage": { # Often excluded for LLM content by user
                "report.html": "<html>Coverage Report</html>",
                "clover.xml": "<xml>Clover</xml>"
            },
            "build": { # Smart excluded dir
                "output.bin": b"binarydata from output.bin",
                "report.txt": "Build report from report.txt"
            },
            "__pycache__": { # Smart excluded dir (top level)
                "main.cpython-39.pyc": b"main pyc content"
            },
            "README.md": "# My Project from README.md",
            "package-lock.json": "{ \"name\": \"project\" }", # Smart file exclude for LLM
            "requirements.txt": "pytest\npick # from requirements.txt",
        }
    }
    root = tmp_path / "test_proj" # This is the actual root passed to dirtree
    create_test_structure(root, structure["project_root"])
    return root

@pytest.fixture
def run_dirtree_and_capture(capsys):
    """Fixture to run IntuitiveDirTree and capture output."""
    def _run(config_overrides: Dict[str, Any]):
        if 'root_dir' not in config_overrides:
            raise ValueError("run_dirtree_and_capture requires 'root_dir'")
        root_dir_path = Path(config_overrides['root_dir'])
        if not root_dir_path.is_dir():
             raise FileNotFoundError(f"Test root_dir '{root_dir_path}' not found.")

        config = {
            'style': 'ascii', 'max_depth': None, 'show_hidden': False,
            'colorize': False, 'show_size': False,
            'cli_include_patterns': None, 'cli_exclude_patterns': None,
            'use_smart_exclude': True,
            'interactive_file_type_includes_for_llm': None,
            'interactive_dir_excludes_for_llm': None,
            'export_for_llm': False, 'max_llm_file_size': 100 * 1024,
            'llm_content_extensions': None, 'llm_indicators': 'included',
            'verbose': False, 'interactive_prompts': False, 'skip_errors': True,
            'output_dir': None, 'add_file_marker': False,
            **config_overrides # Apply overrides
        }
        
        # Ensure output_dir is a Path if specified, for consistency
        if config['output_dir'] and isinstance(config['output_dir'], str):
            config['output_dir'] = Path(config['output_dir'])


        valid_args = { k: v for k, v in config.items() if k in IntuitiveDirTree.__init__.__code__.co_varnames }
        
        try:
            tree_generator = IntuitiveDirTree(**valid_args)
            tree_generator.run()
            captured = capsys.readouterr()

            tree_lines = tree_generator._cached_tree_lines or []
            listed_paths = tree_generator._cached_listed_paths_in_tree or []
            
            llm_export_file_path = None
            if config.get('export_for_llm') and tree_generator.llm_files_included_content > 0:
                 # Attempt to find the export file based on naming convention
                 save_dir = config.get('output_dir') or Path.cwd()
                 # Glob for files matching the export pattern, sort by creation time, take newest
                 # This is a bit fragile if multiple tests run very close together.
                 # A more robust way would be if tree_generator returned the path.
                 # For now, this is a common approach.
                 export_pattern = f"dirtree_export_{root_dir_path.name.replace(' ', '_')}_*.md"
                 
                 # Ensure save_dir is a Path object
                 if isinstance(save_dir, str): save_dir = Path(save_dir)

                 found_exports = sorted(
                     save_dir.glob(export_pattern), 
                     key=os.path.getmtime, 
                     reverse=True
                 )
                 if found_exports:
                     llm_export_file_path = found_exports[0]

            return captured.out, captured.err, tree_lines, listed_paths, llm_export_file_path

        except Exception as e:
            pytest.fail(f"IntuitiveDirTree failed with config {valid_args}: {e}\n{traceback.format_exc()}")

    return _run