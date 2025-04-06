# -*- coding: utf-8 -*-
"""
Filtering logic for IntuitiveDirTree. Determines which items are included/excluded
from the final tree based on patterns and settings.
"""

import fnmatch
import re
from pathlib import Path
from typing import List, Optional, Callable, Set, Dict, Any, Pattern

# Regex patterns for complex pattern matching
_COMPILED_REGEX_CACHE: Dict[str, Pattern[str]] = {}

def _compile_pattern(pattern: str) -> Pattern[str]:
    """Compile a glob pattern to regex for more efficient matching."""
    if pattern in _COMPILED_REGEX_CACHE:
        return _COMPILED_REGEX_CACHE[pattern]

    # Handle special ** glob pattern for recursive matches
    if '**' in pattern:
        # Convert ** to a regex that matches any number of path segments
        regex_pattern = fnmatch.translate(pattern).replace('.*.*', '.*')
    else:
        regex_pattern = fnmatch.translate(pattern)

    compiled = re.compile(regex_pattern)
    _COMPILED_REGEX_CACHE[pattern] = compiled
    return compiled

def passes_filters(
    path: Path,
    root_dir: Path,
    patterns_to_include: List[str],
    patterns_to_exclude: List[str],
    show_hidden: bool,
    log_func: Optional[Callable] = None, # Optional logging function
    is_recursion_check: bool = False # Flag to indicate if we're checking for recursion
) -> bool:
    """
    Checks if a path passes the final filtering rules for display in the tree.

    Args:
        path: The Path object to check.
        root_dir: The root directory of the tree generation.
        patterns_to_include: List of glob patterns for files to include.
        patterns_to_exclude: List of glob patterns for files/dirs to exclude.
        show_hidden: Whether to show hidden files/directories (starting with '.').
        log_func: Optional function for logging filter decisions.
        is_recursion_check: If True, we're checking whether to recurse into this directory.

    Returns:
        True if the item should be listed, False otherwise.
    """
    name = path.name
    is_root = (path == root_dir)
    relative_path_str = None

    # Helper for logging
    def _log(msg, level="debug"):
        if log_func:
            log_func(msg, level)

    # 1. Handle Hidden Files/Directories
    if not show_hidden and name.startswith(".") and not is_root:
        _log(f"Filter: Excluding hidden item '{name}'")
        return False

    # 2. Get relative path for pattern matching
    try:
        # Use Path.relative_to for robust relative path calculation
        relative_path = path.relative_to(root_dir)
        # Convert to string with forward slashes for consistent matching across OS
        relative_path_str = relative_path.as_posix()
    except ValueError:
        # This can happen if path is not under root_dir (e.g., symlink target outside)
        # Fallback to using just the name for matching in this edge case
        relative_path_str = name
        _log(f"Filter: Path '{path}' not relative to root '{root_dir}', using name '{name}' for matching.", "warning")

    # 3. Check for recursion into excluded directories
    if is_recursion_check and path.is_dir():
        # Special case: always allow recursion into the root directory
        if is_root:
            return True

        for pattern in patterns_to_exclude:
            regex = _compile_pattern(pattern)

            # For directories, we want to block recursion but still show the directory itself
            # Use search() instead of match() to find the pattern anywhere in the string, not just at the beginning
            if (regex.search(name) is not None) or (relative_path_str and regex.search(relative_path_str) is not None):
                _log(f"Filter: Blocking recursion into '{relative_path_str}' (matches exclude pattern: '{pattern}')")
                return False
        # If we're just checking recursion and it passed, allow it
        return True

    # 4. For normal display filtering (not recursion check):
    # Files are always subject to include/exclude patterns
    # Directories are included by default, but their contents may be filtered

    # Check exclusions first for both files and directories
    for pattern in patterns_to_exclude:
        regex = _compile_pattern(pattern)

        # Check if the pattern matches the path name or any parent directory
        if (regex.search(name) is not None):
            _log(f"Filter: Excluding '{relative_path_str}' (name matches exclude pattern: '{pattern}')")
            return False

        # Special handling for .git and other hidden directories
        if name.startswith('.') and path.is_dir() and not show_hidden:
            _log(f"Filter: Excluding hidden directory '{name}'")
            return False

        # Check if the pattern matches the relative path
        if relative_path_str:
            # Special handling for **/__pycache__ pattern
            if pattern == '**/__pycache__' and '__pycache__' in relative_path_str:
                _log(f"Filter: Excluding '{relative_path_str}' (matches __pycache__ pattern)")
                return False

            # Special handling for directory patterns without wildcards
            if '/' not in pattern and '*' not in pattern and path.is_file():
                # For simple directory name patterns (like 'node_modules'), check if any parent dir matches
                parent_parts = Path(relative_path_str).parts
                if len(parent_parts) > 1 and pattern in parent_parts[:-1]:
                    _log(f"Filter: Excluding '{relative_path_str}' (parent dir matches exclude pattern: '{pattern}')")
                    return False

            # Check the full path
            if regex.search(relative_path_str) is not None:
                _log(f"Filter: Excluding '{relative_path_str}' (path matches exclude pattern: '{pattern}')")
                return False

    # If it's a file, apply include patterns
    if path.is_file():
        # If include patterns are specified, file must match one of them
        if patterns_to_include:
            for pattern in patterns_to_include:
                regex = _compile_pattern(pattern)

                # Use search() instead of match() to find the pattern anywhere in the string, not just at the beginning
                if (regex.search(name) is not None) or (relative_path_str and regex.search(relative_path_str) is not None):
                    _log(f"Filter: Including file '{relative_path_str}' (matches include pattern: '{pattern}')")
                    return True

            # If no include pattern matched, exclude the file
            _log(f"Filter: Excluding file '{relative_path_str}' (no include patterns matched)")
            return False

    # For directories, we always include them in the display, but may not recurse into them
    # This ensures excluded dirs like node_modules show up in the tree

    # 5. If it passed all checks (or is a directory), include it in display
    _log(f"Filter: Allowing '{relative_path_str}' in tree display")
    return True


def should_recurse_into(
    path: Path,
    root_dir: Path,
    patterns_to_exclude: List[str],
    show_hidden: bool,
    log_func: Optional[Callable] = None
) -> bool:
    """
    Determines if the directory tree generator should recurse into this directory.

    Args:
        path: The directory path to check
        root_dir: The root directory of the tree
        patterns_to_exclude: Exclude patterns to apply
        show_hidden: Whether to show hidden files
        log_func: Optional logging function

    Returns:
        True if we should recurse into directory, False otherwise
    """
    if not path.is_dir():
        return False

    # Use passes_filters with the recursion flag to determine if we should recurse
    return passes_filters(
        path, root_dir, [], patterns_to_exclude, show_hidden, log_func,
        is_recursion_check=True
    )


def match_extension(path: Path, extensions: Set[str]) -> bool:
    """
    Check if a file matches any of the specified extensions.

    Args:
        path: The file path to check
        extensions: Set of extensions (without dots) to match against

    Returns:
        True if the file extension is in the set, False otherwise
    """
    if not path.is_file():
        return False

    ext = path.suffix.lower().lstrip(".")
    return ext in extensions