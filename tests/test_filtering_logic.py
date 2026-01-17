# tests/test_filtering_logic.py
import pytest
from pathlib import Path

# Use the conftest.py setup to ensure imports work
from .conftest import COMMON_DIR_EXCLUDES, COMMON_FILE_EXCLUDES # Updated
# Must import AFTER sys.path manipulation in conftest
try:
    from dirtree.dirtree_filters import passes_tree_filters, should_recurse_for_tree, _compile_pattern
    from dirtree.dirtree_utils import log_message
except ImportError:
     pytest.skip("Skipping filtering logic tests, import failed.", allow_module_level=True)


def dummy_log(msg, level="debug"):
    # print(f"LOG [{level.upper()}]: {msg}") # Uncomment for debugging filter tests
    pass

@pytest.fixture
def filter_test_root(tmp_path):
    d = tmp_path / "filter_root"
    d.mkdir()
    (d / "file.py").touch()
    (d / "file.txt").touch()
    (d / ".hiddenfile").touch()
    (d / "subdir").mkdir()
    (d / "subdir" / "subfile.py").touch()
    (d / "subdir" / "another.log").touch()
    (d / ".hiddendir").mkdir()
    (d / ".hiddendir" / "inside_hidden_dir.txt").touch()
    (d / "node_modules").mkdir() # Smart Dir Exclude for tree
    (d / "node_modules" / "lib.js").touch()
    # Use a directory NOT in COMMON_DIR_EXCLUDES for "interactive LLM exclude" simulation
    (d / "test_results").mkdir()
    (d / "test_results" / "report.html").touch()
    (d / "src").mkdir()
    (d / "src" / "__pycache__").mkdir() # Smart Dir Exclude for tree
    (d / "src" / "__pycache__" / "cache.pyc").touch()
    (d / "src" / "main.ts").touch()
    (d / "package-lock.json").touch() # Smart File Exclude for LLM
    return d

# === Tests for passes_tree_filters (determines if item *appears* in tree) ===

@pytest.mark.parametrize("path_name, show_hidden, expected_pass, expected_reason_contains", [
    ("file.py", False, True, None),
    (".hiddenfile", False, False, "hidden item"),
    (".hiddenfile", True, True, None),
    ("subdir", False, True, None),
    (".hiddendir", False, False, "hidden item"),
    (".hiddendir", True, True, None),
    ("node_modules", False, True, None), # node_modules dir itself should pass to be shown as [excluded]
    ("node_modules/lib.js", False, False, "inside Smart Excluded directory"), # Content inside should not pass
    ("src/__pycache__", False, True, None), # __pycache__ dir itself should pass
    ("src/__pycache__/cache.pyc", False, False, "inside Smart Excluded directory"),
    ("test_results", False, True, None), # Directory not in COMMON_DIR_EXCLUDES, appears in tree
    ("test_results/report.html", False, True, None), # Files inside non-excluded dirs appear
])
def test_passes_tree_filters_hidden_and_smart_dir_contents(filter_test_root, path_name, show_hidden, expected_pass, expected_reason_contains):
    root = filter_test_root
    path = root / path_name
    path.parent.mkdir(parents=True, exist_ok=True)
    if '.' in path.name and not path.exists(): path.touch() # Create file if not a dir
    elif not path.exists(): path.mkdir(exist_ok=True) # Create dir

    # Smart excludes for tree (only dir part)
    smart_dir_tree_excludes = COMMON_DIR_EXCLUDES 

    passes, reason = passes_tree_filters(path, root, [], [], smart_dir_tree_excludes, show_hidden, dummy_log)
    assert passes == expected_pass
    if not expected_pass and expected_reason_contains:
        assert reason is not None and expected_reason_contains in reason

@pytest.mark.parametrize("path_name, cli_includes, cli_excludes, expected_pass, reason_contains", [
    ("file.py", [], [], True, None),
    ("file.py", [], ["*.py"], False, "matches CLI exclude pattern '*.py'"),
    ("file.txt", ["*.py"], [], False, "does not match any CLI include pattern"), # file.txt is not .py
    ("file.py", ["*.py"], [], True, None),
    ("subdir/subfile.py", ["*.py"], ["subdir/*"], False, "matches CLI exclude pattern 'subdir/*'"), # subfile.py is under subdir/
    ("subdir", [], ["subdir"], False, "matches CLI exclude pattern 'subdir'"), # Exclude dir by name
    ("src/main.ts", ["src/*.ts"], [], True, None),
    ("src/main.ts", ["src/*.js"], [], False, "does not match"),
])
def test_passes_tree_filters_cli_patterns(filter_test_root, path_name, cli_includes, cli_excludes, expected_pass, reason_contains):
    root = filter_test_root
    path = root / path_name
    path.parent.mkdir(parents=True, exist_ok=True)
    if '.' in path.name and not path.exists(): path.touch()
    elif not path.exists(): path.mkdir(exist_ok=True)
    
    passes, reason = passes_tree_filters(path, root, cli_includes, cli_excludes, [], True, dummy_log)
    assert passes == expected_pass
    if not expected_pass and reason_contains:
        assert reason is not None and reason_contains in reason


# === Tests for should_recurse_for_tree (determines if tree builder descends) ===

@pytest.mark.parametrize("dir_name, cli_excludes, smart_dir_tree_excludes, show_hidden, expected_recurse", [
    ("subdir", [], [], False, True),
    (".hiddendir", [], [], False, False), # No recurse if hidden and not show_hidden
    (".hiddendir", [], [], True, True),   # Recurse if hidden and show_hidden
    ("node_modules", [], COMMON_DIR_EXCLUDES, False, False), # No recurse due to smart exclude
    ("src/__pycache__", [], COMMON_DIR_EXCLUDES, False, False), # No recurse due to smart exclude
    ("test_results", [], [], False, True), # Directory not in COMMON_DIR_EXCLUDES: YES recurse
    ("subdir", ["subdir"], [], False, False), # No recurse due to CLI exclude
    ("subdir", ["otherdir"], [], False, True),
])
def test_should_recurse_for_tree_logic(filter_test_root, dir_name, cli_excludes, smart_dir_tree_excludes, show_hidden, expected_recurse):
    root = filter_test_root
    path = root / dir_name
    path.mkdir(exist_ok=True)

    # cli_includes are not directly used by should_recurse_for_tree in the simplified model,
    # recursion happens and then children are filtered by passes_tree_filters.
    # A more complex pruning based on includes could be added but is not current.
    cli_includes = [] 
    
    assert should_recurse_for_tree(path, root, cli_includes, cli_excludes, smart_dir_tree_excludes, show_hidden, dummy_log) == expected_recurse

# Removed test_should_recurse_for_tree_root_dir - it tested behavior that doesn't exist
# (root directory is not special-cased in should_recurse_for_tree implementation)