# tests/test_filtering_logic.py
import pytest
from pathlib import Path

# Use the conftest.py setup to ensure imports work
from .conftest import COMMON_EXCLUDES
# Must import AFTER sys.path manipulation in conftest
try:
    from dirtree_lib.dirtree_filters import passes_filters, should_recurse_into, _compile_pattern
    from dirtree_lib.dirtree_utils import log_message
except ImportError:
     pytest.skip("Skipping filtering logic tests, import failed.", allow_module_level=True)


# Dummy logger
def dummy_log(msg, level="debug"):
    # print(f"LOG [{level}]: {msg}") # Uncomment for debugging tests
    pass

@pytest.fixture
def filter_test_structure(tmp_path):
    """Specific structure for filter tests"""
    d = tmp_path / "filter_root"
    d.mkdir()
    (d / "file.py").touch()
    (d / "file.txt").touch()
    (d / ".hiddenfile").touch()
    (d / "subdir").mkdir()
    (d / "subdir" / "subfile.py").touch()
    (d / "subdir" / "another.log").touch()
    (d / ".hiddendir").mkdir()
    (d / ".hiddendir" / "inside.txt").touch()
    (d / "node_modules").mkdir()
    (d / "node_modules" / "lib.js").touch()
    (d / "exclude_me").mkdir()
    (d / "exclude_me" / "important.dat").touch()
    (d / "nested").mkdir()
    (d / "nested" / "__pycache__").mkdir()
    (d / "nested" / "__pycache__" / "cache.pyc").touch()
    return d

# Test _compile_pattern helper (basic check)
def test_compile_pattern():
    regex = _compile_pattern("*.py")
    assert regex.match("test.py")
    assert not regex.match("test.pyc")
    regex_nodemod = _compile_pattern("node_modules")
    assert regex_nodemod.search("node_modules") # Use search as passes_filters does
    assert regex_nodemod.search("path/to/node_modules")
    regex_globstar = _compile_pattern("**/__pycache__")
    # fnmatch.translate creates regex that needs to match full string typically,
    # but our use in passes_filters uses search()
    assert regex_globstar.search("nested/__pycache__")
    assert regex_globstar.search("root/__pycache__")

# === Tests for passes_filters ===

@pytest.mark.parametrize("path_name, show_hidden, expected", [
    ("file.py", False, True),
    ("file.txt", False, True),
    (".hiddenfile", False, False),
    (".hiddenfile", True, True),
    ("subdir", False, True),
    (".hiddendir", False, False),
    (".hiddendir", True, True),
    ("node_modules", False, True), # Should be listed by default if not excluded
    ("__pycache__", False, True), # Should be listed by default if not excluded
])
def test_passes_filters_hidden(filter_test_structure, path_name, show_hidden, expected):
    root = filter_test_structure
    path = root / path_name
    assert passes_filters(path, root, [], [], show_hidden, dummy_log) == expected

@pytest.mark.parametrize("path_name, includes, excludes, expected", [
    # No filters
    ("file.py", [], [], True),
    ("subdir", [], [], True),
    # Simple include
    ("file.py", ["*.py"], [], True),
    ("file.txt", ["*.py"], [], False),
    ("subdir", ["*.py"], [], True), # Dirs always pass if no exclude matches
    ("subdir/subfile.py", ["*.py"], [], True), # Relative path check needed
    # Simple exclude
    ("file.py", [], ["*.py"], False),
    ("file.txt", [], ["*.py"], True),
    ("subdir", [], ["subdir"], False), # Exclude dir by name
    ("subdir/subfile.py", [], ["subdir/*"], False), # Exclude dir content
    ("subdir/subfile.py", [], ["*.py"], False), # Exclude file by ext
    ("node_modules/lib.js", [], ["node_modules"], False), # Exclude node_modules content
    ("node_modules", [], ["node_modules"], False), # Exclude node_modules dir itself
    # Include + Exclude
    ("file.py", ["*.py"], ["*.txt"], True),
    ("file.txt", ["*.py"], ["*.txt"], False),
    ("subdir/subfile.py", ["*.py"], ["subdir/*"], False), # Exclude takes precedence
    ("subdir/another.log", ["*.py", "*.log"], ["*.log"], False), # Exclude takes precedence
    # Path patterns
    ("exclude_me/important.dat", [], ["exclude_me/*"], False),
    ("exclude_me", [], ["exclude_me"], False),
    ("nested/__pycache__/cache.pyc", [], ["**/__pycache__"], False),
    ("nested/__pycache__", [], ["**/__pycache__"], False), # Directory itself matches
])
def test_passes_filters_patterns(filter_test_structure, path_name, includes, excludes, expected):
    root = filter_test_structure
    path = root / path_name
    # Ensure intermediate dirs exist if testing nested paths
    path.parent.mkdir(parents=True, exist_ok=True)
    if '.' in path.name and not path.exists(): # Create file if not exists
        path.touch()
    elif '.' not in path.name and not path.exists(): # Create dir if not exists
         path.mkdir()

    # Test filtering directly
    assert passes_filters(path, root, includes, excludes, True, dummy_log) == expected


# === Tests for should_recurse_into ===

@pytest.mark.parametrize("dir_name, excludes, show_hidden, expected", [
    # Basic cases
    ("subdir", [], False, True),
    (".hiddendir", [], False, False), # Don't recurse into hidden if show_hidden=False
    (".hiddendir", [], True, True),  # Recurse into hidden if show_hidden=True
    # Common excludes (simulate smart exclude)
    ("node_modules", COMMON_EXCLUDES, False, False),
    ("__pycache__", COMMON_EXCLUDES, False, False),
    (".git", COMMON_EXCLUDES, True, False), # Even if show_hidden=True, exclude pattern matches
    # Manual excludes
    ("subdir", ["subdir"], False, False), # Exclude by name
    ("exclude_me", ["exclude_me"], False, False),
    ("nested/__pycache__", ["**/__pycache__"], False, False), # Globstar exclude
    # Non-matching excludes
    ("subdir", ["other_dir"], False, True),
    ("node_modules", ["*.js"], False, True), # Pattern doesn't match dir name/path
])
def test_should_recurse_into(filter_test_structure, dir_name, excludes, show_hidden, expected):
    root = filter_test_structure
    path = root / dir_name

    # Ensure directory exists for the test
    path.mkdir(exist_ok=True)

    assert should_recurse_into(path, root, excludes, show_hidden, dummy_log) == expected

# Test edge case: root dir itself should always allow recursion start
def test_should_recurse_into_root(filter_test_structure):
    root = filter_test_structure
    assert should_recurse_into(root, root, COMMON_EXCLUDES, False, dummy_log) == True
    assert should_recurse_into(root, root, ["*"], False, dummy_log) == True # Even if excluded? Yes, start point.