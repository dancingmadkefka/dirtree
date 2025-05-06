# tests/test_llm_export.py
import pytest
from pathlib import Path
import time

from .conftest import base_test_structure, run_dirtree_and_capture # Import fixture
# Must import AFTER sys.path manipulation in conftest
try:
    from dirtree_lib.dirtree_core import IntuitiveDirTree
    from dirtree_lib.dirtree_config import DEFAULT_LLM_EXCLUDED_EXTENSIONS, COMMON_DIR_EXCLUDES, COMMON_FILE_EXCLUDES
except ImportError:
     pytest.skip("Skipping LLM export tests, import failed.", allow_module_level=True)


def read_llm_export_file(filepath: Path) -> str:
    """Reads the content of the generated LLM export file."""
    if not filepath or not filepath.is_file():
        pytest.fail(f"LLM Export file not found or invalid: {filepath}")
    return filepath.read_text(encoding='utf-8')

def assert_llm_content_present(llm_text: str, file_rel_path: str, expected_substring: str):
    """Checks if specific content for a file is present in the LLM export."""
    header = f"### `{file_rel_path}`"
    assert header in llm_text, f"Header for '{file_rel_path}' not found in LLM export."
    # Rough check: find content between this header and the next '### `' or end of text
    start_idx = llm_text.find(header)
    assert start_idx != -1
    content_block_start = start_idx + len(header)
    next_header_idx = llm_text.find("### `", content_block_start)
    content_block = llm_text[content_block_start : (next_header_idx if next_header_idx != -1 else len(llm_text))]
    assert expected_substring in content_block, f"Substring '{expected_substring}' not found in content for '{file_rel_path}'."

def assert_llm_content_absent(llm_text: str, file_rel_path: str):
    """Checks if content for a file is absent (no header for it)."""
    header = f"### `{file_rel_path}`"
    assert header not in llm_text, f"Header for '{file_rel_path}' unexpectedly found in LLM export."


# === Test Cases for LLM Export Content ===

def test_llm_export_with_smart_exclude_on(base_test_structure, run_dirtree_and_capture, tmp_path):
    root_dir = base_test_structure
    config = {
        'root_dir': str(root_dir), 'export_for_llm': True, 'output_dir': str(tmp_path),
        'use_smart_exclude': True, # Default, but explicit
        'llm_indicators': 'none' # Simplify tree output for checks
    }
    out_tree, _, _, _, export_file = run_dirtree_and_capture(config)
    assert export_file is not None
    llm_content = read_llm_export_file(export_file)

    # Tree should show smart excluded dirs like node_modules, but with [excluded] marker
    assert "node_modules [excluded]" in out_tree
    assert ".git [excluded]" in out_tree
    assert "__pycache__ [excluded]" in out_tree # Both top-level and nested
    assert "build [excluded]" in out_tree

    # LLM Content Checks:
    assert_llm_content_present(llm_content, "src/main.py", "hello from main.py")
    assert_llm_content_present(llm_content, "src/utils/helpers.py", "Utility functions")
    assert_llm_content_present(llm_content, "src/utils/data.json", "value from data.json")
    assert_llm_content_present(llm_content, "README.md", "My Project from README.md")
    
    # Smart Excluded Dirs: Content should NOT be in LLM export
    assert_llm_content_absent(llm_content, "node_modules/package_a/index.js")
    assert_llm_content_absent(llm_content, ".git/config")
    assert_llm_content_absent(llm_content, "build/report.txt") # build is smart dir exclude
    assert_llm_content_absent(llm_content, "__pycache__/main.cpython-39.pyc") # __pycache__ is smart dir exclude
    assert_llm_content_absent(llm_content, "tests/__pycache__/test_cache.pyc")

    # Smart Excluded Files (for LLM): package-lock.json content should NOT be in LLM export
    assert_llm_content_absent(llm_content, "package-lock.json")
    # .env is hidden and also typically not LLM content (binary-like or sensitive)
    assert_llm_content_absent(llm_content, ".env")


def test_llm_export_with_smart_exclude_off(base_test_structure, run_dirtree_and_capture, tmp_path):
    root_dir = base_test_structure
    config = {
        'root_dir': str(root_dir), 'export_for_llm': True, 'output_dir': str(tmp_path),
        'use_smart_exclude': False, # Key change
        'llm_indicators': 'none'
    }
    out_tree, _, _, _, export_file = run_dirtree_and_capture(config)
    assert export_file is not None
    llm_content = read_llm_export_file(export_file)

    # Tree should now show contents of formerly smart-excluded dirs
    assert "node_modules" in out_tree and "package_a" in out_tree
    assert ".git" in out_tree # Still hidden by default for tree unless -H
    assert "build" in out_tree and "output.bin" in out_tree
    
    # LLM Content Checks:
    # Content from formerly smart-excluded dirs should now be present (if not binary)
    assert_llm_content_present(llm_content, "node_modules/package_a/index.js", "Package A from index.js")
    assert_llm_content_present(llm_content, "node_modules/package_a/readme.md", "Package A Readme")
    assert_llm_content_present(llm_content, "build/report.txt", "Build report from report.txt")
    # Content from formerly smart-excluded files should now be present
    assert_llm_content_present(llm_content, "package-lock.json", "project")

    # Binary files still excluded by default LLM rules
    assert_llm_content_absent(llm_content, "build/output.bin")
    assert_llm_content_absent(llm_content, "__pycache__/main.cpython-39.pyc")
    # Hidden files like .git/config and .env are still generally excluded from LLM content by default rules
    assert_llm_content_absent(llm_content, ".git/config")
    assert_llm_content_absent(llm_content, ".env")


def test_llm_export_with_cli_exclude(base_test_structure, run_dirtree_and_capture, tmp_path):
    root_dir = base_test_structure
    config = {
        'root_dir': str(root_dir), 'export_for_llm': True, 'output_dir': str(tmp_path),
        'cli_exclude_patterns': ["src/utils/*", "*.js", "README.md"], # CLI excludes
        'use_smart_exclude': False, # Test CLI excludes in isolation
        'llm_indicators': 'none'
    }
    out_tree, _, _, _, export_file = run_dirtree_and_capture(config)
    assert export_file is not None
    llm_content = read_llm_export_file(export_file)

    # Tree should NOT show items matching CLI exclude
    assert "src/utils" not in out_tree # Entire dir and its contents not in tree
    assert "component.js" not in out_tree # *.js files not in tree
    assert "README.md" not in out_tree # README.md not in tree

    # LLM Content Checks:
    assert_llm_content_present(llm_content, "src/main.py", "hello from main.py") # Not excluded
    
    assert_llm_content_absent(llm_content, "src/utils/helpers.py") # Excluded by src/utils/*
    assert_llm_content_absent(llm_content, "src/utils/data.json")  # Excluded by src/utils/*
    assert_llm_content_absent(llm_content, "src/feature/component.js") # Excluded by *.js
    assert_llm_content_absent(llm_content, "node_modules/package_a/index.js") # Excluded by *.js
    assert_llm_content_absent(llm_content, "README.md") # Excluded by name


def test_llm_export_with_cli_include(base_test_structure, run_dirtree_and_capture, tmp_path):
    root_dir = base_test_structure
    config = {
        'root_dir': str(root_dir), 'export_for_llm': True, 'output_dir': str(tmp_path),
        'cli_include_patterns': ["*.py", "docs/index.md"], # Only .py files and docs/index.md
        'use_smart_exclude': False,
        'llm_indicators': 'none'
    }
    out_tree, _, _, _, export_file = run_dirtree_and_capture(config)
    assert export_file is not None
    llm_content = read_llm_export_file(export_file)

    # Tree should only show .py files, docs/index.md, and their necessary parent dirs
    assert "main.py" in out_tree
    assert "helpers.py" in out_tree
    assert "docs/index.md" in out_tree
    assert "data.json" not in out_tree # Not .py or docs/index.md
    assert "component.js" not in out_tree
    assert "README.md" not in out_tree # Not docs/index.md (even though it's .md)

    # LLM Content Checks:
    assert_llm_content_present(llm_content, "src/main.py", "hello from main.py")
    assert_llm_content_present(llm_content, "src/utils/helpers.py", "Utility functions")
    assert_llm_content_present(llm_content, "tests/test_main.py", "from test_main.py")
    assert_llm_content_present(llm_content, "docs/index.md", "Documentation from index.md")

    assert_llm_content_absent(llm_content, "src/utils/data.json") # Not .py
    assert_llm_content_absent(llm_content, "README.md") # Not docs/index.md


def test_llm_export_with_interactive_llm_dir_excludes(base_test_structure, run_dirtree_and_capture, tmp_path):
    root_dir = base_test_structure
    config = {
        'root_dir': str(root_dir), 'export_for_llm': True, 'output_dir': str(tmp_path),
        'interactive_dir_excludes_for_llm': {"tests", "coverage"}, # User chose to exclude these for LLM
        'use_smart_exclude': True, # Smart excludes still active for tree and LLM
        'llm_indicators': 'all' # To verify indicators
    }
    out_tree, _, _, _, export_file = run_dirtree_and_capture(config)
    assert export_file is not None
    llm_content = read_llm_export_file(export_file)

    # Tree should show "tests" and "coverage" directories and their content fully.
    # LLM indicators should mark them as [LLM✗]
    assert "tests" in out_tree and "test_main.py" in out_tree
    assert "test_main.py [LLM✗]" in out_tree # Files inside 'tests' dir are LLM excluded
    
    assert "coverage" in out_tree and "report.html" in out_tree
    # HTML is often binary for LLM, so it might be LLM✗ anyway, but explicit dir exclude reinforces this.
    # We need to check a file that would normally be included.
    (root_dir / "coverage" / "notes.txt").write_text("Coverage notes")
    # Rerun with the new file
    out_tree, _, _, _, export_file = run_dirtree_and_capture(config)
    llm_content = read_llm_export_file(export_file)
    assert "coverage/notes.txt [LLM✗]" in out_tree

    # LLM Content Checks:
    assert_llm_content_present(llm_content, "src/main.py", "hello from main.py") # Not in excluded dir

    assert_llm_content_absent(llm_content, "tests/test_main.py") # Content from 'tests' excluded for LLM
    assert_llm_content_absent(llm_content, "coverage/notes.txt") # Content from 'coverage' excluded for LLM


def test_llm_export_with_llm_ext_takes_precedence(base_test_structure, run_dirtree_and_capture, tmp_path):
    root_dir = base_test_structure
    config = {
        'root_dir': str(root_dir), 'export_for_llm': True, 'output_dir': str(tmp_path),
        'llm_content_extensions': ['md'], # CLI --llm-ext only wants .md
        'interactive_file_type_includes_for_llm': ['py', 'js', 'md'], # Interactive also selected py, js
        'use_smart_exclude': False,
        'llm_indicators': 'all'
    }
    out_tree, _, _, _, export_file = run_dirtree_and_capture(config)
    assert export_file is not None
    llm_content = read_llm_export_file(export_file)
    
    # LLM Content Checks: Only .md files due to CLI --llm-ext override
    assert_llm_content_present(llm_content, "README.md", "My Project from README.md")
    assert_llm_content_present(llm_content, "docs/index.md", "Documentation from index.md")
    
    assert_llm_content_absent(llm_content, "src/main.py") # .py not in --llm-ext
    assert_llm_content_absent(llm_content, "src/feature/component.js") # .js not in --llm-ext

    # Tree indicators should reflect this
    assert "README.md [LLM✓]" in out_tree
    assert "main.py [LLM✗]" in out_tree
    assert "component.js [LLM✗]" in out_tree


def test_llm_export_max_size_respected(tmp_path, run_dirtree_and_capture):
    root_dir = tmp_path / "llm_max_size_test"
    small_content = "s" * 500
    large_content = "l" * 2000
    (root_dir / "small.txt").write_text(small_content)
    (root_dir / "large.txt").write_text(large_content)
    max_size_bytes = 1024 # 1KB limit

    config = {
        'root_dir': str(root_dir), 'export_for_llm': True, 'output_dir': str(tmp_path),
        'max_llm_file_size': max_size_bytes,
        'use_smart_exclude': False, 'llm_indicators': 'all'
    }
    out_tree, _, _, _, export_file = run_dirtree_and_capture(config)
    assert export_file is not None
    llm_content = read_llm_export_file(export_file)

    assert "small.txt [LLM✓]" in out_tree
    assert_llm_content_present(llm_content, "small.txt", small_content)
    
    assert "large.txt [LLM✓]" in out_tree # Still included, but content truncated
    assert_llm_content_present(llm_content, "large.txt", large_content[:max_size_bytes])
    assert "... [TRUNCATED]" in llm_content.split("### `large.txt`")[1]