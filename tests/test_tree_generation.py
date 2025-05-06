# tests/test_tree_generation.py
import pytest
from pathlib import Path

from .conftest import base_test_structure, run_dirtree_and_capture # Import fixture
# Must import AFTER sys.path manipulation in conftest
try:
    from dirtree_lib.dirtree_core import IntuitiveDirTree
    from dirtree_lib.dirtree_utils import format_bytes
except ImportError:
     pytest.skip("Skipping tree generation tests, import failed.", allow_module_level=True)


def assert_tree_output_contains(output: str, items: list[str]):
    """Checks if items appear in the tree output, order/prefix agnostic."""
    for item in items:
        assert item in output, f"Expected '{item}' in tree output.\nOutput:\n{output}"

def assert_tree_output_not_contains(output: str, items: list[str]):
    """Checks if items DO NOT appear in the tree output."""
    for item in items:
        assert item not in output, f"Unexpected '{item}' in tree output.\nOutput:\n{output}"


# === Test Cases for Tree Display ===

def test_tree_default_smart_exclude_on(base_test_structure, run_dirtree_and_capture):
    """Smart Exclude ON: Common clutter dirs shown as '[excluded]', content hidden."""
    root_dir = base_test_structure
    config = {'root_dir': str(root_dir), 'use_smart_exclude': True}
    out, _, _, _, _ = run_dirtree_and_capture(config)

    # Regular files/dirs should be present
    assert_tree_output_contains(out, ["test_proj", "src", "main.py", "README.md"])
    
    # Smart excluded dirs should be listed with the [excluded] marker, and contents not shown
    assert_tree_output_contains(out, ["node_modules [excluded]", ".git [excluded]", "build [excluded]"])
    # Verify content of smart excluded dirs is NOT in tree
    assert_tree_output_not_contains(out, ["package_a", "index.js"]) # Inside node_modules
    assert_tree_output_not_contains(out, ["config"]) # Inside .git
    assert_tree_output_not_contains(out, ["output.bin"]) # Inside build

    # __pycache__ can be nested, check both
    assert "src" in out # Ensure src is there to check its child __pycache__
    if "src" in out and "__pycache__ [excluded]" in out: # This checks generic presence
        # More specific: find __pycache__ under src
        src_block_index = out.find("src")
        if src_block_index != -1:
            next_prompt_index = out.find("test_proj", src_block_index + 1) # Look for next root dir if any, or end
            src_content_block = out[src_block_index : next_prompt_index if next_prompt_index != -1 else len(out)]
            assert "__pycache__ [excluded]" in src_content_block
            assert "cache.pyc" not in src_content_block # Content of __pycache__

    # Hidden files are not shown by default (unless -H)
    assert_tree_output_not_contains(out, [".env"])
    # package-lock.json is a file, smart excluded for LLM, but should appear in tree
    assert_tree_output_contains(out, ["package-lock.json"])


def test_tree_smart_exclude_off(base_test_structure, run_dirtree_and_capture):
    """Smart Exclude OFF: Common clutter dirs and their content ARE shown in tree."""
    root_dir = base_test_structure
    config = {'root_dir': str(root_dir), 'use_smart_exclude': False}
    out, _, _, _, _ = run_dirtree_and_capture(config)

    # Formerly smart-excluded items should now be fully listed
    assert_tree_output_contains(out, [
        "node_modules", "package_a", "index.js",
        # ".git", "config", # .git is hidden, still not shown without -H
        "build", "output.bin", "report.txt",
        "__pycache__", # Top-level __pycache__
        "main.cpython-39.pyc",
        "src", "__pycache__", # Nested __pycache__ under src
        "test_cache.pyc" # Content of tests/__pycache__
    ])
    # Hidden files still not shown
    assert_tree_output_not_contains(out, [".env", ".git"])


def test_tree_cli_exclude_patterns(base_test_structure, run_dirtree_and_capture):
    """Items matching CLI --exclude patterns are completely absent from tree."""
    root_dir = base_test_structure
    config = {
        'root_dir': str(root_dir),
        'cli_exclude_patterns': ["*.py", "docs", "src/utils"], # Exclude all .py, 'docs' dir, 'src/utils' dir
        'use_smart_exclude': False # Isolate CLI exclude effect
    }
    out, _, _, _, _ = run_dirtree_and_capture(config)

    assert_tree_output_contains(out, ["test_proj", "src", "feature", "component.js", "README.md"]) # Non-excluded
    
    assert_tree_output_not_contains(out, [
        "main.py", "helpers.py", "test_main.py", # *.py files
        "docs", "index.md", "api.md",             # 'docs' dir and its content
        "src/utils", "data.json"                  # 'src/utils' dir and its content
    ])


def test_tree_cli_include_patterns(base_test_structure, run_dirtree_and_capture):
    """If CLI --include used, only matching items and their parents appear in tree."""
    root_dir = base_test_structure
    config = {
        'root_dir': str(root_dir),
        'cli_include_patterns': ["*.md", "src/feature/component.js"],
        'use_smart_exclude': False
    }
    out, _, _, _, _ = run_dirtree_and_capture(config)

    # Expected in tree: *.md files, component.js, and their necessary parent directories
    assert_tree_output_contains(out, [
        "test_proj", "README.md",
        "docs", "index.md", "api.md", # .md files and parent 'docs'
        "src", "feature", "component.js", # component.js and parents 'src', 'feature'
        "node_modules", "package_a", "readme.md" # .md file and parents
    ])

    # Items not matching includes (and not parents of included) should be absent
    assert_tree_output_not_contains(out, [
        "main.py", "data.json", "style.css", "requirements.txt", "coverage"
    ])


def test_tree_show_hidden_flag(base_test_structure, run_dirtree_and_capture):
    """-H flag shows hidden files/dirs, unless smart/CLI excluded."""
    root_dir = base_test_structure
    config_hidden_smart_on = {
        'root_dir': str(root_dir), 'show_hidden': True, 'use_smart_exclude': True
    }
    out_smart_on, _, _, _, _ = run_dirtree_and_capture(config_hidden_smart_on)
    
    assert_tree_output_contains(out_smart_on, [".env"]) # .env is hidden, now shown
    # .git is hidden AND smart_dir_excluded, so it appears as .git [excluded]
    assert_tree_output_contains(out_smart_on, [".git [excluded]"])
    assert_tree_output_not_contains(out_smart_on, ["config"]) # Content of .git not shown

    config_hidden_smart_off = {
        'root_dir': str(root_dir), 'show_hidden': True, 'use_smart_exclude': False
    }
    out_smart_off, _, _, _, _ = run_dirtree_and_capture(config_hidden_smart_off)
    assert_tree_output_contains(out_smart_off, [".env", ".git", "config"]) # .git content now shown


def test_tree_max_depth_limit(base_test_structure, run_dirtree_and_capture):
    root_dir = base_test_structure
    config = {
        'root_dir': str(root_dir), 'max_depth': 1, # root (depth 0) + immediate children (depth 1)
        'use_smart_exclude': False # Simplify for depth check
    }
    out, _, _, _, _ = run_dirtree_and_capture(config)

    assert_tree_output_contains(out, ["test_proj", "src", "tests", "node_modules", "README.md"]) # Depth 0 and 1
    assert_tree_output_not_contains(out, ["main.py", "utils", "package_a", "index.md"]) # Depth 2+


def test_tree_show_size_flag(tmp_path, run_dirtree_and_capture):
    root_dir = tmp_path / "size_tree_test"
    (root_dir / "file_a.txt").write_text("12345") # 5 bytes
    (root_dir / "subdir").mkdir()
    (root_dir / "subdir" / "file_b.py").write_text("# " + "b" * 2000) # ~2KB
    
    config = {'root_dir': str(root_dir), 'show_size': True, 'use_smart_exclude': False}
    out, _, _, _, _ = run_dirtree_and_capture(config)

    assert "file_a.txt (5 B)" in out
    assert "file_b.py (2.0 KB)" in out # format_bytes might give 1.9 or 2.0 based on exact size
    assert "subdir" in out and "(" not in out.split("subdir")[1].split('\n')[0] # No size for dirs


def test_tree_empty_dir_display(tmp_path, run_dirtree_and_capture):
    root_dir = tmp_path / "empty_dir_root"
    (root_dir / "non_empty_dir").mkdir()
    (root_dir / "non_empty_dir" / "file.txt").touch()
    (root_dir / "completely_empty_dir").mkdir()
    
    config = {'root_dir': str(root_dir), 'use_smart_exclude': False}
    out, _, _, _, _ = run_dirtree_and_capture(config)

    assert_tree_output_contains(out, ["completely_empty_dir", "non_empty_dir", "file.txt"])