# tests/test_cli.py
import pytest
import sys
from pathlib import Path

# Use the conftest.py setup to ensure imports work
from .conftest import COMMON_EXCLUDES
# Must import AFTER sys.path manipulation in conftest
try:
    from dirtree_lib.dirtree_cli import parse_args
    from dirtree_lib.dirtree_utils import parse_size_string
except ImportError:
     pytest.skip("Skipping CLI tests, import failed.", allow_module_level=True)


def run_parse_args(argv: list[str]):
    """Helper to run parse_args with specific argv."""
    original_argv = sys.argv
    try:
        sys.argv = ["dirtree.py"] + argv # Simulate script name + args
        args = parse_args()
        return args
    finally:
        sys.argv = original_argv

# === Test Cases ===

def test_cli_no_args(tmp_path):
    """Test CLI fails without directory if not interactive."""
    # This needs to test the main() function behavior, not just parse_args
    # parse_args allows directory=None, main() handles the error.
    # Testing main() directly is complex due to potential sys.exit.
    # We'll focus on parse_args mapping here.
    # parse_args itself won't exit, so we just check the directory is None
    args = run_parse_args([])
    assert args.directory is None

def test_cli_basic_dir(tmp_path):
    """Test providing just a directory."""
    test_dir = tmp_path / "mydir"
    test_dir.mkdir()
    args = run_parse_args([str(test_dir)])
    assert args.directory == str(test_dir)
    # Check defaults
    assert args.use_smart_exclude is True
    assert args.style == 'unicode'
    assert args.max_depth is None
    assert args.hidden is False
    assert args.export_for_llm is False
    assert args.verbose is False
    assert args.skip_errors is False # Default is interactive prompts

def test_cli_filtering_args(tmp_path):
    """Test include, exclude, hidden, and smart exclude args."""
    args = run_parse_args([
        str(tmp_path),
        "-I", "*.py",
        "--include=src/**/*.js",
        "-E", "temp/",
        "--exclude", "*.log",
        "-H",
        "--no-smart-exclude"
    ])
    assert args.directory == str(tmp_path)
    assert args.include == ["*.py", "src/**/*.js"]
    assert args.exclude == ["temp/", "*.log"]
    assert args.hidden is True
    assert args.use_smart_exclude is False # Explicitly disabled

def test_cli_display_args(tmp_path):
    """Test style, depth, size, color args."""
    args = run_parse_args([
        str(tmp_path),
        "-s", "emoji",
        "-d", "3",
        "--size",
        "--no-color"
    ])
    assert args.style == "emoji"
    assert args.max_depth == 3
    assert args.size is True
    assert args.colorize is False

def test_cli_llm_args(tmp_path):
    """Test LLM related arguments."""
    args = run_parse_args([
        str(tmp_path),
        "-L",
        "--llm-max-size", "50k",
        "--llm-ext", "py",
        "--llm-ext", "json",
        "--llm-output-dir", str(tmp_path / "exports"),
        "--llm-indicators", "all"
    ])
    assert args.export_for_llm is True
    assert args.llm_max_size == "50k" # parse_size_string happens later in main()
    assert args.llm_ext == ["py", "json"]
    assert args.llm_output_dir == str(tmp_path / "exports")
    assert args.llm_indicators == "all"

def test_cli_behavior_args(tmp_path):
    """Test verbose and error handling args."""
    args = run_parse_args([
        str(tmp_path),
        "-v",
        "--skip-errors"
    ])
    assert args.verbose is True
    assert args.skip_errors is True

    args_ask = run_parse_args([str(tmp_path), "--ask-errors"])
    assert args_ask.skip_errors is False

def test_cli_smart_exclude_default_on(tmp_path):
     args = run_parse_args([str(tmp_path)])
     assert args.use_smart_exclude is True

def test_cli_mutually_exclusive_groups(tmp_path):
     # Smart exclude flags
     with pytest.raises(SystemExit):
         run_parse_args([str(tmp_path), "--smart-exclude", "--no-smart-exclude"])
     # Color flags
     with pytest.raises(SystemExit):
         run_parse_args([str(tmp_path), "--color", "--no-color"])
     # Error flags
     with pytest.raises(SystemExit):
         run_parse_args([str(tmp_path), "--skip-errors", "--ask-errors"])

# Test parse_size_string utility used by main()
@pytest.mark.parametrize("size_str, expected", [
    ("100k", 100 * 1024),
    ("1.5m", int(1.5 * 1024 * 1024)),
    ("2G", 2 * 1024 * 1024 * 1024),
    ("512", 512),
    ("512b", 512),
    ("", 100 * 1024), # Default
    ("invalid", 100 * 1024), # Default on error
])
def test_parse_size_string_util(size_str, expected):
    assert parse_size_string(size_str, default=100 * 1024) == expected