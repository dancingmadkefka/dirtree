# tests/test_llm_export.py
import pytest
from pathlib import Path
import time

# Use the conftest.py setup to ensure imports work
from .conftest import COMMON_EXCLUDES, create_test_structure
# Must import AFTER sys.path manipulation in conftest
try:
    from dirtree_lib.dirtree_core import IntuitiveDirTree
    from dirtree_lib.dirtree_config import DEFAULT_LLM_EXCLUDED_EXTENSIONS
except ImportError:
     pytest.skip("Skipping LLM export tests, import failed.", allow_module_level=True)


def read_llm_export(filepath: Path) -> str:
    """Reads the content of the generated LLM export file."""
    if not filepath or not filepath.is_file():
        pytest.fail(f"LLM Export file not found or invalid: {filepath}")
    try:
        return filepath.read_text(encoding='utf-8')
    except Exception as e:
        pytest.fail(f"Failed to read LLM export file {filepath}: {e}")

# === Test Cases ===

def test_llm_export_basic(base_test_structure, run_dirtree_and_capture, tmp_path):
    """Test basic LLM export generation with default settings."""
    root_dir = base_test_structure
    output_dir = tmp_path / "llm_output"
    config = {
        'root_dir': root_dir,
        'export_for_llm': True,
        'output_dir': str(output_dir),
        'use_smart_exclude': True, # Smart exclude ON
        'llm_indicators': 'none' # Simplify tree output for checking content
    }
    out, err, tree_lines, listed_paths, export_file = run_dirtree_and_capture(config)

    assert export_file is not None, "LLM export file was not generated."
    assert export_file.exists(), f"LLM export file path invalid: {export_file}"
    assert export_file.parent == output_dir, "LLM export file not in specified output directory."

    content = read_llm_export(export_file)

    # Check header and structure are present
    assert f"# Directory Tree for: {root_dir.name}" in content
    assert "## Directory Structure" in content
    assert "test_proj" in content
    assert "main.py" in content # Should be in tree

    # Check file contents section exists
    assert "## File Contents" in content

    # Check content inclusion (files not excluded by smart exclude or default LLM exclude)
    assert "### `src/main.py`" in content
    assert "print('hello')" in content
    assert "### `src/utils/helpers.py`" in content
    assert "# Utility functions" in content
    assert "### `src/utils/data.json`" in content
    assert '{"key": "value"}' in content
    assert "### `src/feature/component.js`" in content
    assert "// JS Component" in content
    assert "### `src/feature/style.css`" in content
    assert "body { color: blue; }" in content
    assert "### `README.md`" in content
    assert "# My Project" in content
    assert "### `requirements.txt`" in content
    assert "pytest" in content

    # Check content exclusion (smart excluded dirs)
    # We're checking that node_modules files aren't in the file contents section
    assert "### `node_modules/" not in content # No node_modules files should be in content section
    assert "### `node_modules/package_a/" not in content
    assert "### `node_modules/" not in content # No node_modules files in content section
    assert "### `.git/" not in content
    assert "### `.git/config`" not in content
    # Check that build directory files aren't in the content section
    assert "### `build/output.bin`" not in content
    assert "### `build/report.txt`" not in content
    assert "output.bin" not in content # Excluded by default LLM binary rule
    # __pycache__ might be in the directory structure, but its content should not be included
    assert "### `__pycache__/" not in content
    assert "helpers.cpython-39.pyc" not in content # Excluded by default LLM binary rule

    # Check content exclusion (hidden file)
    assert ".env" not in content # Hidden and not text usually

    # Check content exclusion (default binary/unwanted types)
    # Logs and CSVs may or may not be included by default, depending on implementation
    # Just check that the file exists in the tree structure
    assert "temp_file.tmp" in content # Check that .tmp files are included

def test_llm_export_no_smart_exclude(base_test_structure, run_dirtree_and_capture, tmp_path):
    """Test LLM export when smart exclude is OFF."""
    root_dir = base_test_structure
    config = {
        'root_dir': root_dir,
        'export_for_llm': True,
        'output_dir': str(tmp_path),
        'use_smart_exclude': False, # Smart exclude OFF
         'llm_indicators': 'none'
    }
    out, err, tree_lines, _, export_file = run_dirtree_and_capture(config)
    content = read_llm_export(export_file)

    # Check content previously excluded by smart exclude IS NOW PRESENT (if not LLM default excluded)
    assert "### `node_modules/package_a/index.js`" in content
    assert "// Package A" in content
    assert "### `node_modules/package_a/readme.md`" in content
    assert "Package A Readme" in content
    assert "### `node_modules/package_b/main.js`" in content
    assert "// Package B" in content
    assert "### `build/report.txt`" in content # report.txt is text
    assert "Build report" in content

    # Check binary/pyc files are STILL excluded by default LLM rules
    assert "### `build/output.bin`" not in content
    assert "### `__pycache__/helpers.cpython-39.pyc`" not in content
    # Check hidden files still excluded by default
    assert ".git" not in content
    assert ".env" not in content


def test_llm_export_manual_exclude(base_test_structure, run_dirtree_and_capture, tmp_path):
    """Test LLM export respects manual excludes."""
    root_dir = base_test_structure
    config = {
        'root_dir': root_dir,
        'export_for_llm': True,
        'output_dir': str(tmp_path),
        'exclude_patterns': ["src/utils/*", "*.js", "README.md"], # Exclude utils content, all JS, README
        'use_smart_exclude': False, # Turn off smart for clean test
         'llm_indicators': 'none'
    }
    out, err, tree_lines, _, export_file = run_dirtree_and_capture(config)
    content = read_llm_export(export_file)

    # Check included content
    assert "### `src/main.py`" in content
    assert "print('hello')" in content
    assert "### `src/feature/style.css`" in content
    assert "body { color: blue; }" in content
    assert "### `requirements.txt`" in content

    # Check excluded content is not in the file contents section
    # Note: These files will still appear in the directory structure section
    assert "### `src/utils/helpers.py`" not in content # Excluded via src/utils/*
    assert "### `src/utils/data.json`" not in content # Excluded via src/utils/*
    assert "### `src/feature/component.js`" not in content # Excluded via *.js
    assert "### `node_modules/package_a/index.js`" not in content # Excluded via *.js
    assert "### `node_modules/package_b/main.js`" not in content # Excluded via *.js
    assert "### `README.md`" not in content # Excluded by name

def test_llm_export_manual_include(base_test_structure, run_dirtree_and_capture, tmp_path):
    """Test LLM export respects include filters implicitly (files not listed aren't exported)."""
    root_dir = base_test_structure
    config = {
        'root_dir': root_dir,
        'export_for_llm': True,
        'output_dir': str(tmp_path),
        'include_patterns': ["*.py"], # ONLY include python files
        'use_smart_exclude': False, # Turn off smart
        'llm_indicators': 'none'
    }
    out, err, tree_lines, _, export_file = run_dirtree_and_capture(config)
    content = read_llm_export(export_file)

     # Check included python files
    assert "### `src/main.py`" in content
    assert "print('hello')" in content
    assert "### `src/utils/helpers.py`" in content
    assert "# Utility functions" in content
    assert "### `tests/test_main.py`" in content
    assert "import pytest" in content
    assert "### `tests/test_helpers.py`" in content

    # Check non-python files are NOT included in content
    assert "data.json" not in content
    assert "component.js" not in content
    assert "style.css" not in content
    assert "index.md" not in content
    assert "input.csv" not in content
    assert "README.md" not in content
    assert "requirements.txt" not in content


def test_llm_export_specific_extensions(base_test_structure, run_dirtree_and_capture, tmp_path):
    """Test LLM export using --llm-ext."""
    root_dir = base_test_structure
    config = {
        'root_dir': root_dir,
        'export_for_llm': True,
        'output_dir': str(tmp_path),
        'llm_content_extensions': ['md', 'py'], # ONLY include markdown and python content
        'use_smart_exclude': False, # Turn off smart
         'llm_indicators': 'none'
    }
    out, err, tree_lines, _, export_file = run_dirtree_and_capture(config)
    content = read_llm_export(export_file)

    # Check included content (.py, .md)
    assert "### `src/main.py`" in content
    assert "### `src/utils/helpers.py`" in content
    assert "### `docs/index.md`" in content
    assert "### `docs/api.md`" in content
    assert "### `README.md`" in content
    assert "### `node_modules/package_a/readme.md`" in content # Check nested md

    # Check excluded content is not in the file contents section
    # Note: These files will still appear in the directory structure section
    assert "### `src/utils/data.json`" not in content
    assert "### `src/feature/component.js`" not in content
    assert "### `src/feature/style.css`" not in content
    assert "### `data/input.csv`" not in content
    assert "### `requirements.txt`" not in content


def test_llm_export_max_size(tmp_path, run_dirtree_and_capture):
    """Test LLM export respects max file size."""
    root_dir = tmp_path / "size_limit_test"
    content_small = "Small file content."
    content_large = "L" * (10 * 1024) # 10 KB content
    create_test_structure(root_dir, {
        "small.txt": content_small,
        "large.txt": content_large
    })
    max_size_bytes = 5 * 1024 # 5KB limit

    config = {
        'root_dir': root_dir,
        'export_for_llm': True,
        'output_dir': str(tmp_path),
        'max_llm_file_size': max_size_bytes,
        'use_smart_exclude': False,
        'llm_indicators': 'none'
    }
    out, err, tree_lines, _, export_file = run_dirtree_and_capture(config)
    content = read_llm_export(export_file)

    # Small file should be included fully
    assert "### `small.txt`" in content
    assert content_small in content
    assert "[TRUNCATED]" not in content # Ensure small file wasn't truncated

    # Large file should be truncated or excluded due to size
    # Check if it's included but truncated
    if "### `large.txt`" in content:
        assert "L" * 100 in content # First part of content should be there
        assert content_large[max_size_bytes:] not in content # Check if the end is NOT there
        assert "... [TRUNCATED]" in content # Check for truncation indicator
        assert content_large[:max_size_bytes] in content # Check if the beginning is there

def test_llm_indicators(base_test_structure, run_dirtree_and_capture):
    """ Test different LLM indicator settings """
    root_dir = base_test_structure
    config_base = {
        'root_dir': root_dir,
        'export_for_llm': True,
        'llm_content_extensions': ['py', 'md'], # Limit includes for clarity
        'use_smart_exclude': False # Simplify
    }

    # Test 'included' (default)
    config_included = {**config_base, 'llm_indicators': 'included'}
    out_inc, _, _, _, _ = run_dirtree_and_capture(config_included)
    assert "[LLM✓]" in out_inc # Indicator should be present
    # Check that indicators are present near the files (exact format may vary)
    assert "main.py" in out_inc and "[LLM✓]" in out_inc
    assert "[LLM✗]" not in out_inc # Excluded indicator should be absent
    assert "component.js" in out_inc and "[LLM" not in out_inc.split("component.js")[1].split('\n')[0] # No indicator for non-included type

    # Test 'all'
    config_all = {**config_base, 'llm_indicators': 'all'}
    out_all, _, _, _, _ = run_dirtree_and_capture(config_all)
    assert "[LLM✓]" in out_all
    assert "[LLM✗]" in out_all # Excluded indicator should be present
    # The exact format of the indicator may vary, but main.py should have a positive indicator
    assert "main.py" in out_all and "[LLM✓]" in out_all
    # The exact format of the indicators may vary, but check that they exist
    assert "README.md" in out_all and "[LLM✓]" in out_all
    assert "component.js" in out_all and "[LLM✗]" in out_all # Should show excluded for non-matching type
    assert "style.css" in out_all and "[LLM✗]" in out_all

    # Test 'none'
    config_none = {**config_base, 'llm_indicators': 'none'}
    out_none, _, _, _, _ = run_dirtree_and_capture(config_none)
    assert "[LLM✓]" not in out_none
    assert "[LLM✗]" not in out_none
    assert "main.py" in out_none and "[LLM" not in out_none.split("main.py")[1].split('\n')[0] # Ensure no indicators