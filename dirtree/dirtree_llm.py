# -*- coding: utf-8 -*-
"""
LLM Export functionality for IntuitiveDirTree.
Handles reading file content and generating a Markdown export suitable for LLMs.
"""

import sys
import os
import re
from pathlib import Path
from datetime import datetime
from typing import List, Set, Optional, Dict, Any, Callable, Tuple
import fnmatch

# --- Imports from other modules ---
try:
    from .dirtree_config import DEFAULT_LLM_EXCLUDED_EXTENSIONS, DEFAULT_LLM_INCLUDE_EXTENSIONS
    from .dirtree_utils import log_message, format_bytes
except ImportError:
    # Fallback for direct execution or testing
    print("Warning: Running llm module potentially outside of package context.", file=sys.stderr)
    DEFAULT_LLM_EXCLUDED_EXTENSIONS = set()
    DEFAULT_LLM_INCLUDE_EXTENSIONS = set()
    def log_message(*args, **kwargs): pass
    def format_bytes(b): return str(b)

# --- Content Filtering ---

def should_include_content_for_llm(
    file_path: Path,
    root_dir: Path, # Needed to check relative path for dir exclusions
    file_size: int,
    max_llm_file_size: int,
    llm_content_extensions_set: Optional[Set[str]], # Specific extensions to include, or None for default
    cli_exclude_patterns: List[str], # Patterns from --exclude
    smart_dir_excludes: List[str],   # e.g., "node_modules"
    smart_file_excludes_for_llm: List[str], # e.g., "package-lock.json"
    interactive_dir_excludes_llm: Set[str], # Set of directory names like "coverage"
    log_func: Callable
) -> bool:
    """
    Determines if a file's content should be included in the LLM export.
    This is the ultimate gatekeeper for LLM content.
    """
    if not file_path.is_file():
        return False

    relative_path_str = file_path.relative_to(root_dir).as_posix()
    file_name = file_path.name

    # 1. Check CLI --exclude patterns
    for pattern in cli_exclude_patterns:
        if fnmatch.fnmatch(file_name, pattern) or fnmatch.fnmatch(relative_path_str, pattern):
            log_func(f"LLM Content: SKIP '{relative_path_str}' (matches CLI exclude pattern '{pattern}')", "debug")
            return False

    # 2. Check if inside a Smart Excluded Directory
    current_parent = file_path.parent
    while current_parent != root_dir and current_parent.parent != current_parent :
        # Check against smart exclude patterns
        for smart_dir_pattern in smart_dir_excludes:
            if fnmatch.fnmatch(current_parent.name, smart_dir_pattern):
                log_func(f"LLM Content: SKIP '{relative_path_str}' (inside smart excluded dir '{current_parent.name}' matching '{smart_dir_pattern}')", "debug")
                return False

        # Also exclude directories starting with double underscores (like __tests__, __mocks__)
        if current_parent.name.startswith("__"):
            log_func(f"LLM Content: SKIP '{relative_path_str}' (inside double-underscore dir '{current_parent.name}')", "debug")
            return False

        if current_parent == root_dir: break # Stop if we hit root
        current_parent = current_parent.parent

    # 3. Check if inside an Interactively Excluded Directory (for LLM)
    current_parent = file_path.parent
    while current_parent != root_dir and current_parent.parent != current_parent:
        if current_parent.name in interactive_dir_excludes_llm:
            log_func(f"LLM Content: SKIP '{relative_path_str}' (inside interactively LLM-excluded dir '{current_parent.name}')", "debug")
            return False
        if current_parent == root_dir: break
        current_parent = current_parent.parent

    # 4. Check Smart File Excludes (for LLM content)
    for smart_file_pattern in smart_file_excludes_for_llm:
        if fnmatch.fnmatch(file_name, smart_file_pattern):
            log_func(f"LLM Content: SKIP '{relative_path_str}' (matches smart file LLM exclude pattern '{smart_file_pattern}')", "debug")
            return False

    # 5. Check file size
    if file_size < 0: # Unknown size
        log_func(f"LLM Content: SKIP '{relative_path_str}' (unknown size).", "debug")
        return False
    if file_size > max_llm_file_size:
        log_func(f"LLM Content: SKIP '{relative_path_str}' (size {format_bytes(file_size)} > max {format_bytes(max_llm_file_size)}).", "debug")
        return False

    # 6. Check file extension
    ext = file_path.suffix.lower().lstrip(".") if file_path.suffix else ""
    if llm_content_extensions_set is not None: # Specific extensions provided
        if ext in llm_content_extensions_set:
            log_func(f"LLM Content: INCLUDE '{relative_path_str}' (matches specified extension '{ext}').", "debug")
            return True
        else:
            log_func(f"LLM Content: SKIP '{relative_path_str}' (extension '{ext}' not in specified list).", "debug")
            return False
    else: # Default logic: include common text, exclude known binary
        if ext in DEFAULT_LLM_EXCLUDED_EXTENSIONS and ext not in DEFAULT_LLM_INCLUDE_EXTENSIONS:
             log_func(f"LLM Content: SKIP '{relative_path_str}' (default exclusion for extension '{ext}').", "debug")
             return False
        # If it's in include list OR not in exclude list (implicit include for text files)
        if ext in DEFAULT_LLM_INCLUDE_EXTENSIONS or ext not in DEFAULT_LLM_EXCLUDED_EXTENSIONS :
             log_func(f"LLM Content: INCLUDE '{relative_path_str}' (passed default extension checks).", "debug")
             return True

        log_func(f"LLM Content: SKIP '{relative_path_str}' (failed default extension checks, ext: '{ext}').", "debug")
        return False # Fallback if not explicitly included by default logic

# --- Content Reading ---
def read_file_content(path: Path, max_size_to_read: int, log_func: Callable) -> Tuple[Optional[str], int]:
    """
    Safely reads file content, respecting size limits, handling encodings.
    Returns (content_string_or_None, actual_bytes_of_string_or_0).
    """
    try:
        # Read as bytes first to correctly handle truncation before decoding
        file_bytes = path.read_bytes()
        actual_file_size = len(file_bytes)

        if actual_file_size == 0:
            return "", 0 # Empty file

        truncated = False
        if actual_file_size > max_size_to_read:
            file_bytes = file_bytes[:max_size_to_read]
            truncated = True
            log_func(f"LLM Export: Content for '{path.name}' was truncated to {format_bytes(max_size_to_read)} (original {format_bytes(actual_file_size)}).", "warning")

        content_str = None
        # Try common encodings
        encodings_to_try = ['utf-8', 'latin-1', sys.getdefaultencoding()]
        for enc in encodings_to_try:
            try:
                content_str = file_bytes.decode(enc)
                log_func(f"LLM Export: Read '{path.name}' with encoding '{enc}'.", "debug")
                break
            except UnicodeDecodeError:
                log_func(f"LLM Export: Decoding '{path.name}' with '{enc}' failed.", "debug")
                continue

        if content_str is None: # All decodes failed
            content_str = file_bytes.decode('utf-8', errors='replace') # Force decode with replacements
            log_func(f"LLM Export: Force decoded '{path.name}' with UTF-8 (replacing errors).", "warning")

        if truncated:
            content_str += "\n... [TRUNCATED]"

        # Return the string and its byte size after potential truncation and encoding
        return content_str, len(content_str.encode('utf-8', errors='replace'))

    except Exception as e:
        log_func(f"LLM Export: Error reading file '{path.name}': {e}", "error")
        return None, 0

# --- Clean Tree Generation for Markdown ---
def create_clean_tree_for_markdown(tree_lines: List[str]) -> List[str]:
    ansi_escape = re.compile(r'\033\[[0-9;]*[a-zA-Z]')
    # Also remove LLM indicators from the tree structure in markdown
    llm_indicator_pattern = re.compile(r'\s*\[LLM[✓✗]\]')

    clean_lines = []
    for line in tree_lines:
        clean_line = ansi_escape.sub('', line)
        clean_line = llm_indicator_pattern.sub('', clean_line) # Remove LLM indicators
        clean_lines.append(clean_line)
    return clean_lines

# --- Export Generation ---
def generate_llm_export(
    root_dir: Path,
    tree_lines: List[str], # Visual tree for header
    paths_in_tree_for_llm_check: List[Path], # Paths that appeared in the tree
    max_llm_file_size: int,
    llm_content_extensions_set: Optional[Set[str]],
    cli_exclude_patterns: List[str],
    smart_dir_excludes: List[str],
    smart_file_excludes_for_llm: List[str],
    interactive_dir_excludes_llm: Set[str],
    log_func: Callable,
    output_dir: Path, # Already resolved Path object
    add_file_marker: bool
) -> Tuple[Optional[Path], int, int]: # (filepath, total_content_bytes, files_included_count)
    """
    Generates a Markdown file with directory structure and selected file contents.
    """
    log_func("Starting LLM export generation...", "info")
    export_lines: List[str] = []
    total_content_bytes = 0
    files_with_content_included = 0

    if add_file_marker:
        export_lines.append("\u200B<!-- DIRTREE_GENERATED_FILE -->")

    export_lines.append(f"# Directory Tree for: {root_dir.name}")
    export_lines.append(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    export_lines.append("\n## Directory Structure")
    export_lines.append("```")
    export_lines.extend(create_clean_tree_for_markdown(tree_lines))
    export_lines.append("```\n")

    export_lines.append("## File Contents\n")
    if llm_content_extensions_set is not None:
        ext_list = sorted(list(llm_content_extensions_set))
        export_lines.append(f"*Content included for file extensions: {', '.join(ext_list) if ext_list else 'None specified'}*\n")
    else:
        export_lines.append("*Content included based on default logic (common text files, excluding binaries).*\n")
    export_lines.append(f"*Maximum file size for inclusion: {format_bytes(max_llm_file_size)}*\n")

    actual_content_added_to_export = False
    for item_path in paths_in_tree_for_llm_check: # Iterate over paths that were in the tree
        if not item_path.is_file():
            continue

        try:
            file_size = item_path.stat().st_size
        except Exception as e_stat:
            log_func(f"LLM Export: Could not stat '{item_path}' for LLM content: {e_stat}", "warning")
            continue # Skip if cannot stat

        if should_include_content_for_llm(
            item_path, root_dir, file_size, max_llm_file_size,
            llm_content_extensions_set, cli_exclude_patterns,
            smart_dir_excludes, smart_file_excludes_for_llm,
            interactive_dir_excludes_llm, log_func
        ):
            log_func(f"LLM Export: Reading content for '{item_path.name}'...", "debug")
            content_str, content_bytes_read = read_file_content(item_path, max_llm_file_size, log_func)

            if content_str is not None:
                relative_path_str = item_path.relative_to(root_dir).as_posix()
                export_lines.append(f"### `{relative_path_str}`\n")
                ext = item_path.suffix.lower().lstrip(".")
                lang_hint = ext if ext else ""
                export_lines.append(f"```{lang_hint}")
                export_lines.append(content_str)
                export_lines.append("```\n")

                total_content_bytes += content_bytes_read
                files_with_content_included += 1
                actual_content_added_to_export = True
            else:
                 log_func(f"LLM Export: Skipping content for '{item_path.name}' due to read error or it was empty.", "warning")

    if not actual_content_added_to_export:
        export_lines.append("*No file content was included in this export based on the current settings and file checks.*\n")

    export_filename = f"dirtree_export_{root_dir.name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    export_filepath = output_dir / export_filename

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        with export_filepath.open("w", encoding="utf-8") as f:
            f.write("\n".join(export_lines))
        log_func(f"LLM export successfully created: {export_filepath}", "success")
        return export_filepath, total_content_bytes, files_with_content_included
    except Exception as e_write:
        log_func(f"Error writing LLM export file '{export_filepath}': {e_write}", "error")
        return None, 0, 0