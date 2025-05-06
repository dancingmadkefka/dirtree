# tests/test_cli.py
import pytest
import sys
from pathlib import Path

# Use the conftest.py setup to ensure imports work
# from .conftest import COMMON_DIR_EXCLUDES # Not directly used here
# Must import AFTER sys.path manipulation in conftest
try:
    from dirtree_lib.dirtree_cli import parse_args
    from dirtree_lib.dirtree_utils import parse_size_string # Used by main()
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
    """Test CLI parse_args allows directory=None; main() handles error if not interactive."""
    args = run_parse_args([])
    assert args.directory is None

def test_cli_basic_dir(tmp_path):
    test_dir = tmp_path / "mydir"
    test_dir.mkdir()
    args = run_parse_args([str(test_dir)])
    assert args.directory == str(test_dir)
    assert args.use_smart_exclude is True # Default
    assert args.style == 'unicode'
    assert args.export_for_llm is False

def test_cli_filtering_args(tmp_path):
    args = run_parse_args([
        str(tmp_path),
        "-I", "*.py", "--include=src/**/*.js", # Renamed dest to cli_include_patterns
        "-E", "temp/", "--exclude", "*.log",   # Renamed dest to cli_exclude_patterns
        "-H",
        "--no-smart-exclude"
    ])
    assert args.directory == str(tmp_path)
    assert args.cli_include_patterns == ["*.py", "src/**/*.js"]
    assert args.cli_exclude_patterns == ["temp/", "*.log"]
    assert args.hidden is True
    assert args.use_smart_exclude is False

def test_cli_display_args(tmp_path):
    args = run_parse_args([
        str(tmp_path),
        "-s", "emoji", "-d", "3", "--size", "--no-color"
    ])
    assert args.style == "emoji"
    assert args.max_depth == 3
    assert args.size is True
    assert args.colorize is False # --no-color

def test_cli_llm_args(tmp_path):
    args = run_parse_args([
        str(tmp_path),
        "--llm", # Changed from -L
        "--llm-max-size", "50k",
        "--llm-ext", "py", "--llm-ext", "json", # Renamed dest
        "--llm-output-dir", str(tmp_path / "exports"),
        "--llm-indicators", "all"
    ])
    assert args.export_for_llm is True
    assert args.llm_max_size == "50k" 
    assert args.llm_content_extensions == ["py", "json"]
    assert args.llm_output_dir == str(tmp_path / "exports")
    assert args.llm_indicators == "all"

def test_cli_behavior_args(tmp_path):
    args_verbose_skip = run_parse_args([str(tmp_path), "-v", "--skip-errors"])
    assert args_verbose_skip.verbose is True
    assert args_verbose_skip.skip_errors is True

    args_ask = run_parse_args([str(tmp_path), "--ask-errors"])
    assert args_ask.skip_errors is False

@pytest.mark.parametrize("size_str, expected_bytes", [
    ("100k", 100 * 1024), ("100kb", 100 * 1024),
    ("1.5m", int(1.5 * 1024 * 1024)), ("1.5mb", int(1.5 * 1024 * 1024)),
    ("2g", 2 * 1024 * 1024 * 1024), ("2gb", 2 * 1024 * 1024 * 1024),
    ("512", 512), ("512b", 512),
    ("", 50 * 1024), # Test default value
    ("invalid", 50 * 1024), # Test default on error
])
def test_parse_size_string_util(size_str, expected_bytes):
    assert parse_size_string(size_str, default=50 * 1024) == expected_bytes
