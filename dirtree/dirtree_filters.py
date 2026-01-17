# -*- coding: utf-8 -*-
"""
Filtering logic for IntuitiveDirTree. Determines which items are included/excluded
from the final tree based on patterns and settings.
"""

import fnmatch
import re
from pathlib import Path
from typing import List, Optional, Callable, Set, Dict, Any, Pattern, Tuple

# Regex patterns for complex pattern matching
_COMPILED_REGEX_CACHE: Dict[str, Pattern[str]] = {}

def _compile_pattern(pattern: str) -> Pattern[str]:
    """Compile a glob pattern to regex for more efficient matching."""
    if pattern in _COMPILED_REGEX_CACHE:
        return _COMPILED_REGEX_CACHE[pattern]

    if '**' in pattern:
        regex_pattern = fnmatch.translate(pattern).replace(re.escape(Path('**').as_posix()), '.*') # More robust **
    else:
        regex_pattern = fnmatch.translate(pattern)

    compiled = re.compile(regex_pattern)
    _COMPILED_REGEX_CACHE[pattern] = compiled
    return compiled

def _is_path_or_parent_excluded_by_patterns(
    path: Path, root_dir: Path, patterns: List[str], log_func: Callable
) -> Tuple[bool, Optional[str]]:
    """Checks if path or any parent (up to root_dir) matches exclude patterns."""
    if not patterns:
        return False, None

    current = path
    while current != root_dir and current.parent != current: # Stop if we reach root or above
        relative_to_root = current.relative_to(root_dir).as_posix()
        for pattern_str in patterns:
            regex = _compile_pattern(pattern_str)
            # Check against current segment name
            if regex.fullmatch(current.name): # Use fullmatch for exact segment name
                log_func(f"Path '{path}' (via segment '{current.name}') excluded by CLI pattern '{pattern_str}'", "debug")
                return True, f"segment '{current.name}' excluded by CLI pattern '{pattern_str}'"
            # Check against relative path from root
            if regex.fullmatch(relative_to_root): # Use fullmatch for paths
                log_func(f"Path '{path}' (relative path '{relative_to_root}') excluded by CLI pattern '{pattern_str}'", "debug")
                return True, f"relative path '{relative_to_root}' excluded by CLI pattern '{pattern_str}'"
        if current == root_dir: # Avoid going above root
            break
        current = current.parent
    return False, None


def passes_tree_filters(
    path: Path,
    root_dir: Path,
    cli_include_patterns: List[str],
    cli_exclude_patterns: List[str],
    smart_dir_excludes_for_tree: List[str], # Only dir patterns from smart exclude
    show_hidden: bool,
    log_func: Callable
) -> Tuple[bool, Optional[str]]: # Returns (passes, reason_if_failed)
    """
    Checks if a path should appear in the tree display.

    Args:
        path: The Path object to check.
        root_dir: The root directory of the tree generation.
        cli_include_patterns: Glob patterns from --include.
        cli_exclude_patterns: Glob patterns from --exclude.
        smart_dir_excludes_for_tree: Directory names/patterns from smart exclude (e.g., "node_modules").
        show_hidden: Whether to show hidden files/directories.
        log_func: Logging function.

    Returns:
        Tuple (bool, Optional[str]): (True if item should be listed, Reason if False else None)
    """
    name = path.name
    is_root = (path == root_dir)
    relative_path_str = path.relative_to(root_dir).as_posix() if path != root_dir else "."

    # 1. Handle Hidden Files/Directories
    if not show_hidden and name.startswith(".") and not is_root:
        return False, "hidden item"

    # 2. Check CLI --exclude patterns (strongest exclusion for tree)
    for pattern_str in cli_exclude_patterns:
        regex = _compile_pattern(pattern_str)
        if regex.fullmatch(name) or (relative_path_str != "." and regex.fullmatch(relative_path_str)):
            return False, f"matches CLI exclude pattern '{pattern_str}'"
    
    # Check if any parent is CLI excluded (only for items inside such dirs)
    # This is complex as `path` could be a dir itself.
    # If path is 'a/b/c' and 'a/b' is CLI excluded, then 'a/b/c' shouldn't appear.
    # This logic needs to be woven into the recursive build or `should_recurse_for_tree`.
    # For `passes_tree_filters` on an individual item, if its parent was CLI_EXCLUDED and thus not recursed, this item wouldn't even be checked.
    # So, we only need to check the item itself against CLI_EXCLUDE here.

    # 3. Check if inside a Smart Excluded Directory (e.g. file inside node_modules)
    # This prevents contents of smart_excluded_dirs from appearing.
    # The smart_excluded_dir itself will pass this check but fail `should_recurse_for_tree`.
    current_check_path = path.parent
    while current_check_path != root_dir and current_check_path.parent != current_check_path :
        for smart_pattern in smart_dir_excludes_for_tree:
            # Smart patterns are typically names like "node_modules"
            if fnmatch.fnmatch(current_check_path.name, smart_pattern):
                 return False, f"inside Smart Excluded directory '{current_check_path.name}' (matches '{smart_pattern}')"
        if current_check_path == root_dir: break
        current_check_path = current_check_path.parent


    # 4. Handle CLI --include patterns
    # If --include is used, an item must match one of them (or be a necessary parent dir).
    # This logic is tricky for a simple filter function. Usually, if includes are present,
    # only explicitly included items and their ancestors are shown.
    # The main recursion loop often handles building up parent dirs.
    # For this filter: if includes are given, the item itself must match.
    if cli_include_patterns:
        matched_include = False
        for pattern_str in cli_include_patterns:
            regex = _compile_pattern(pattern_str)
            if regex.fullmatch(name) or (relative_path_str != "." and regex.fullmatch(relative_path_str)):
                matched_include = True
                break
        if not matched_include and not path.is_dir(): # Files must match if includes are present
            return False, "does not match any CLI include pattern"
        # For directories, they can pass if they don't match, to allow children to match.
        # The final pruning of empty included dirs happens in the tree builder.

    return True, None


def should_recurse_for_tree(
    dir_path: Path,
    root_dir: Path,
    cli_include_patterns: List[str],
    cli_exclude_patterns: List[str],
    smart_dir_excludes_for_tree: List[str],
    show_hidden: bool,
    log_func: Callable
) -> bool:
    """
    Determines if the tree generator should recurse into this directory for tree display.
    """
    if not dir_path.is_dir(): # Should not happen if called correctly
        return False

    name = dir_path.name
    relative_path_str = dir_path.relative_to(root_dir).as_posix() if dir_path != root_dir else "."

    # 1. Don't recurse into hidden directories if not showing hidden
    if not show_hidden and name.startswith(".") and dir_path != root_dir:
        log_func(f"Tree Recurse: NO into '{name}' (hidden)", "debug")
        return False

    # 2. Don't recurse if directory matches a CLI --exclude pattern
    for pattern_str in cli_exclude_patterns:
        regex = _compile_pattern(pattern_str)
        if regex.fullmatch(name) or (relative_path_str != "." and regex.fullmatch(relative_path_str)):
            log_func(f"Tree Recurse: NO into '{name}' (matches CLI exclude '{pattern_str}')", "debug")
            return False

    # 3. Don't recurse if directory matches a Smart Directory Exclude pattern
    # These are directories like "node_modules", ".git"
    for smart_pattern in smart_dir_excludes_for_tree:
        if fnmatch.fnmatch(name, smart_pattern): # Smart patterns are often simple names
            log_func(f"Tree Recurse: NO into '{name}' (matches smart dir exclude '{smart_pattern}')", "debug")
            return False
    
    # 4. If CLI --include patterns are present, recursion logic is more complex.
    #    We should recurse if the directory itself matches an include, OR
    #    if any potential child could match an include pattern.
    #    For simplicity here, if includes are present and the dir doesn't match,
    #    we might still recurse, and let the `passes_tree_filters` for children handle it.
    #    A more advanced version would prune branches that cannot lead to an included item.
    #    If the dir itself matches an include, definitely recurse (if not excluded).
    if cli_include_patterns:
        matched_include = False
        for pattern_str in cli_include_patterns:
            regex = _compile_pattern(pattern_str)
            # If dir matches an include, allow recursion unless excluded above.
            if regex.fullmatch(name) or (relative_path_str != "." and regex.fullmatch(relative_path_str)):
                matched_include = True
                break
            # If a pattern looks like it could match something *inside* this dir (e.g. "dir/*.py")
            if pattern_str.startswith(relative_path_str + '/') or pattern_str.startswith(name + '/'):
                matched_include = True # Potential for children to match
                break
        if not matched_include and relative_path_str != ".": # If root doesn't match, still scan its children
            # If dir itself doesn't match any include pattern, and no pattern suggests children might,
            # then don't recurse. This is a simplification.
            # A true check would be too complex here.
            # For now: if includes are specified, dir must match or have children that could.
            # If dir itself doesn't match, we assume children might.
            pass


    log_func(f"Tree Recurse: YES into '{name}'", "debug")
    return True


def match_extension(path: Path, extensions_to_match: Set[str]) -> bool:
    """
    Check if a file matches any of the specified extensions.
    """
    if not path.is_file():
        return False
    # Extension without dot, lowercase
    file_ext = path.suffix.lower().lstrip(".")
    return file_ext in extensions_to_match