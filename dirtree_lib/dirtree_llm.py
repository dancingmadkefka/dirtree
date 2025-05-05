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

# --- Imports from other modules ---
try:
    from .dirtree_config import DEFAULT_LLM_EXCLUDED_EXTENSIONS
    from .dirtree_utils import log_message, format_bytes
except ImportError:
    # Fallback for direct execution or testing
    print("Warning: Running llm module potentially outside of package context.", file=sys.stderr)
    DEFAULT_LLM_EXCLUDED_EXTENSIONS = set()
    def log_message(*args, **kwargs): pass
    def format_bytes(b): return str(b)

# --- Content Filtering ---

def should_include_content_for_llm(
    path: Path,
    file_size: int,
    max_llm_file_size: int,
    llm_content_extensions_set: Optional[Set[str]], # None means use default logic
    log_func: Callable
) -> bool:
    """
    Determines if a file's content should be included in the LLM export.

    Args:
        path: The file path.
        file_size: The size of the file in bytes.
        max_llm_file_size: Maximum allowed size for included content.
        llm_content_extensions_set: Specific set of extensions to include, or None for default logic.
        log_func: Logging function.

    Returns:
        True if content should be included, False otherwise.
    """
    if not path.is_file():
        return False # Only include content for files

    # Exclude __pycache__ directories and .pyc files
    if "__pycache__" in str(path) or path.suffix.lower() == ".pyc":
        log_func(f"LLM Export: Skipping content for '{path.name}' (Python cache file).", "debug")
        return False

    if file_size < 0:
        log_func(f"LLM Export: Skipping content for '{path.name}' (could not get size).", "debug")
        return False # Cannot determine size

    if file_size > max_llm_file_size:
        log_func(f"LLM Export: Skipping content for '{path.name}' (size {format_bytes(file_size)} > max {format_bytes(max_llm_file_size)}).", "debug")
        return False

    ext = path.suffix.lower().lstrip(".") if path.suffix else ""

    # If specific extensions are provided, only include those
    if llm_content_extensions_set is not None:
        if ext in llm_content_extensions_set:
            log_func(f"LLM Export: Including content for '{path.name}' (matches specified extension '{ext}').", "debug")
            return True
        else:
            log_func(f"LLM Export: Skipping content for '{path.name}' (extension '{ext}' not in specified list).", "debug")
            return False

    # Default logic: Exclude known binary/non-text extensions
    if ext in DEFAULT_LLM_EXCLUDED_EXTENSIONS:
        log_func(f"LLM Export: Skipping content for '{path.name}' (default exclusion for extension '{ext}').", "debug")
        return False

    # If not excluded by default rules, include it
    log_func(f"LLM Export: Including content for '{path.name}' (passed default checks).", "debug")
    return True

# --- Content Reading ---

def read_file_content(path: Path, max_size: int, log_func: Callable) -> Tuple[Optional[str], int]:
    """
    Safely reads the content of a file, respecting size limits and handling encoding errors.

    Args:
        path: The file path.
        max_size: The maximum number of bytes to read.
        log_func: Logging function.

    Returns:
        A tuple containing:
        - The file content as a string, or None if reading fails or is skipped.
        - The actual size of the content in bytes, or 0 if reading fails.
    """
    try:
        # Try reading with UTF-8 first, the most common encoding
        with path.open('r', encoding='utf-8') as f:
            content = f.read(max_size + 1) # Read one extra byte to check if truncated
            if len(content) > max_size:
                 log_func(f"LLM Export: Content truncated for '{path.name}' (read > {format_bytes(max_size)}).", "warning")
                 content = content[:max_size] + "\n... [TRUNCATED]"
            content_size = len(content.encode('utf-8'))
            return content, content_size
    except UnicodeDecodeError:
        log_func(f"LLM Export: UTF-8 decoding failed for '{path.name}'. Trying fallback encoding.", "debug")
        try:
            # Fallback to latin-1 or system default if UTF-8 fails
            # Using 'replace' to avoid crashing on remaining errors
            with path.open('r', encoding='latin-1', errors='replace') as f: # Or sys.getdefaultencoding()
                content = f.read(max_size + 1)
                if len(content) > max_size:
                    log_func(f"LLM Export: Content truncated for '{path.name}' (read > {format_bytes(max_size)}).", "warning")
                    content = content[:max_size] + "\n... [TRUNCATED]"
                log_func(f"LLM Export: Successfully read '{path.name}' with fallback encoding.", "debug")
                content_size = len(content.encode('latin-1', errors='replace'))
                return content, content_size
        except Exception as e_fallback:
            log_func(f"LLM Export: Error reading '{path.name}' with fallback encoding: {e_fallback}", "error")
            return None, 0 # Indicate failure to read
    except Exception as e:
        log_func(f"LLM Export: Error reading file '{path.name}': {e}", "error")
        return None, 0 # Indicate failure to read

# --- Clean Tree Generation for Markdown ---

def create_clean_tree_for_markdown(tree_lines: List[str]) -> List[str]:
    """
    Creates a clean version of the tree lines suitable for markdown display.
    Removes ANSI color codes and other terminal-specific formatting.

    Args:
        tree_lines: The original tree lines with ANSI color codes

    Returns:
        A list of clean tree lines suitable for markdown
    """
    # Regular expression to match ANSI escape sequences
    ansi_escape = re.compile(r'\033\[[0-9;]*[a-zA-Z]')

    # Create clean tree lines
    clean_lines = []
    for line in tree_lines:
        # Remove ANSI color codes
        clean_line = ansi_escape.sub('', line)
        # Replace any other terminal-specific characters if needed
        clean_lines.append(clean_line)

    return clean_lines

# --- Export Generation ---

def generate_llm_export(
    root_dir: Path,
    tree_lines: List[str],
    listed_paths: List[Path], # Paths corresponding to items actually listed in tree_lines
    max_llm_file_size: int,
    llm_content_extensions_set: Optional[Set[str]],
    log_func: Callable,
    output_dir: Optional[Path] = None, # Directory to save the export file
    add_file_marker: bool = False # Whether to add a special marker to the generated file
) -> Optional[Path]:
    """
    Generates a Markdown file containing the directory structure and selected file contents.

    Args:
        root_dir: The root directory that was processed.
        tree_lines: The pre-generated list of strings representing the visual tree.
        listed_paths: A list of Path objects for items included in the tree_lines.
        max_llm_file_size: Max size for included file content.
        llm_content_extensions_set: Specific extensions to include content for, or None for default.
        log_func: Logging function.
        output_dir: Directory to save the export file (defaults to CWD).

    Returns:
        The Path to the generated export file, or None if export failed or no content was included.
    """
    log_func("Starting LLM export generation...", "info")
    export_content: List[str] = []
    llm_export_data: List[Dict[str, Any]] = [] # Store data for structured export
    total_content_size = 0
    files_with_content = 0
    files_checked = 0

    # 1. Add Header
    # Add a special marker if requested (invisible character sequence that can be detected by filters)
    if add_file_marker:
        # Add a special marker at the beginning of the file (zero-width space + special comment)
        export_content.append("\u200B<!-- DIRTREE_GENERATED_FILE -->")
        log_func("Added special marker to generated file for future exclusion", "debug")

    export_content.append(f"# Directory Tree for: {root_dir.name}")
    export_content.append(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    export_content.append("\n## Directory Structure")
    export_content.append("```")
    # Create a clean version of the tree lines for markdown
    clean_tree_lines = create_clean_tree_for_markdown(tree_lines)
    export_content.extend(clean_tree_lines) # Add the clean visual tree
    export_content.append("```\n")

    # 2. Process listed files for content inclusion
    content_added = False
    export_content.append("## File Contents\n")

    # 2.1 Add a summary of what's being included
    if llm_content_extensions_set is not None:
        export_content.append(f"*Content included for file extensions: {', '.join(sorted(llm_content_extensions_set))}*\n")
    else:
        export_content.append("*Content included for all non-binary files (excluding common binary formats).*\n")
    export_content.append(f"*Maximum file size for inclusion: {format_bytes(max_llm_file_size)}*\n")

    for item_path in listed_paths:
        if not item_path.is_file():
            continue # Skip directories

        try:
            file_size = item_path.stat().st_size
            files_checked += 1
        except Exception as e:
            log_func(f"LLM Export: Could not stat file '{item_path}' for size check: {e}", "warning")
            file_size = -1 # Indicate unknown size

        if should_include_content_for_llm(item_path, file_size, max_llm_file_size, llm_content_extensions_set, log_func):
            log_func(f"LLM Export: Reading content for '{item_path.name}'...", "debug")
            content, content_size = read_file_content(item_path, max_llm_file_size, log_func)

            if content is not None:
                # Use forward slashes for consistent path formatting in LLM export
                relative_path_str = str(item_path.relative_to(root_dir)).replace("\\", "/")
                export_content.append(f"### `{relative_path_str}`\n")
                # Determine file type for code block hint
                ext = item_path.suffix.lower().lstrip(".")
                lang_hint = ext if ext else ""
                export_content.append(f"```{lang_hint}")
                export_content.append(content)
                export_content.append("```\n")
                llm_export_data.append({
                    "path": relative_path_str,
                    "content": content,
                    "size": content_size
                })
                total_content_size += content_size
                files_with_content += 1
                content_added = True
            else:
                 log_func(f"LLM Export: Skipping content for '{item_path.name}' due to read error.", "warning")

    if not content_added:
        export_content.append("*No file content included based on current settings (size, type, or errors).*\n")
        export_content.append("*Possible reasons:*")
        export_content.append("* *All found files exceed the maximum size limit*")
        export_content.append("* *No files match the extension criteria*")
        export_content.append("* *Only binary files were found*")
        export_content.append("\n*Try adjusting the LLM export settings to include more content.*")

    # Add content summary
    if content_added:
        summary = f"\n## Summary\n\n* Files with content included: {files_with_content}/{files_checked}"
        summary += f"\n* Total content size: {format_bytes(total_content_size)}"
        export_content.append(summary)

    # 3. Write to file
    export_filename = f"dirtree_export_{root_dir.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    save_dir = output_dir if output_dir else Path.cwd()
    try:
        save_dir.mkdir(parents=True, exist_ok=True) # Ensure output directory exists
    except Exception as e:
        log_func(f"LLM Export: Could not create output directory '{save_dir}': {e}", "error")
        save_dir = Path.cwd()
        log_func(f"LLM Export: Falling back to current working directory.", "warning")

    export_filepath = save_dir / export_filename

    try:
        with export_filepath.open("w", encoding="utf-8") as f:
            f.write("\n".join(export_content))
        log_func(f"LLM export successfully created: {export_filepath}", "success")
        return export_filepath
    except Exception as e:
        log_func(f"Error writing LLM export file '{export_filepath}': {e}", "error")
        return None