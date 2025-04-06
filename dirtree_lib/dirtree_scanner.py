# -*- coding: utf-8 -*-
"""
Directory scanning functionality for IntuitiveDirTree.
Used to discover file types or directory names for interactive filtering.
"""

import sys
import time
import shutil
import os
import fnmatch
from pathlib import Path
from collections import Counter
from typing import List, Set, Counter as CounterType, Callable, Optional

# Import Colors for potential warnings within the scanner itself
try:
    from .dirtree_styling import Colors
    from .dirtree_config import COMMON_EXCLUDES
except ImportError:
    try:
        from dirtree_styling import Colors
        from dirtree_config import COMMON_EXCLUDES
    except ImportError:
        class Colors: RESET = ""; YELLOW = "" # Dummy
        COMMON_EXCLUDES = []

def scan_directory(
    root_dir: Path,
    scan_type: str, # "file" or "dir"
    max_items: int,
    show_hidden: bool,
    log_func: Callable, # Function for logging messages
    initial_exclude_patterns: Optional[List[str]] = None # Patterns to exclude during the scan
) -> CounterType[str]:
    """
    Scans directory to find file extensions or directory names, respecting filters.
    This scan is primarily for *discovery* to populate interactive selection lists.
    It uses minimal filtering (currently only 'show_hidden') to find potential items.

    Args:
        root_dir: The directory to start scanning from.
        scan_type: 'file' to scan for file extensions, 'dir' for directory names.
        max_items: Maximum number of filesystem items to inspect.
        show_hidden: Whether to include hidden items (starting with '.') in the scan.
        log_func: A callable for logging messages (e.g., log_func(message, level)).
        initial_exclude_patterns: Patterns to exclude during the scan (e.g., from smart exclude).

    Returns:
        A Counter object mapping found items (extensions or dir names) to their counts.
    """
    log_func(f"Starting {scan_type} scan in '{root_dir}' (max: {max_items}, hidden: {show_hidden})", "info")
    item_counter: CounterType[str] = Counter()
    scanned_count = 0
    scan_label = "file types" if scan_type == "file" else "directory names"

    # --- Spinner setup ---
    spinner = ["/", "-", "\\", "|"] if sys.stdout.isatty() else [""] # No spinner if not TTY
    spinner_idx = 0
    term_width = shutil.get_terminal_size((80, 20)).columns
    last_status_len = 0
    start_time = time.monotonic()

    # --- Setup high-performance scan exclusions ---
    # These directories are always excluded from *recursion*
    # but will still be counted in the directory name scan
    scan_exclude_dirs = {
        "node_modules", "__pycache__", ".git", ".venv", "venv", "env",
        "build", "dist", ".cache", ".npm", ".next", "out"
    }
    
    # Combine with any user-provided patterns
    exclude_patterns = list(initial_exclude_patterns or [])
    
    log_func(f"Scanner using exclude patterns: {exclude_patterns}", "debug")
    log_func(f"Scanner will not recurse into: {scan_exclude_dirs}", "debug")

    # --- Scan Setup ---
    dirs_to_scan: List[Path] = []
    seen_dirs: Set[Path] = set()
    try:
        # Resolve root to handle symlinks properly in seen set and start scan
        resolved_root = root_dir.resolve()
        seen_dirs.add(resolved_root)
        dirs_to_scan.append(root_dir) # Start with the original path
        log_func(f"Resolved root for scan: '{resolved_root}'", "debug")
    except Exception as e:
         # Non-fatal error, proceed with unresolved root but log it
         print(f"\n{Colors.YELLOW}Warning: Could not resolve root dir '{root_dir}' for scan: {e}{Colors.RESET}")
         log_func(f"Could not resolve root '{root_dir}' for scan: {e}", "warning")
         seen_dirs.add(root_dir) # Add unresolved path to seen set
         dirs_to_scan.append(root_dir)

    # --- BFS Directory Traversal ---
    try:
        while dirs_to_scan and scanned_count < max_items:
            current_dir = dirs_to_scan.pop(0) # BFS - pop from start
            log_func(f"Scanning dir: '{current_dir}'", "debug")

            # Update spinner less frequently for performance
            if spinner and (scanned_count % 50 == 0 or scanned_count < 10 or time.monotonic() - start_time > 0.5):
                elapsed = time.monotonic() - start_time
                status = f"{spinner[spinner_idx % len(spinner)]} Scanned {scanned_count}/{max_items} items... Found {len(item_counter)} unique {scan_label} ({elapsed:.1f}s)"
                # Pad with spaces to clear previous line remnants
                padded_status = status.ljust(last_status_len)
                print(f"\r{padded_status}", end="", flush=True)
                last_status_len = len(status) # Store current length
                spinner_idx += 1
                start_time = time.monotonic() # Reset timer for next update interval

            try:
                # Using scandir is generally faster than iterdir+stat
                for entry in os.scandir(current_dir):
                    if scanned_count >= max_items: break

                    entry_path = Path(entry.path) # Create Path object once

                    # --- FILTERING ---
                    # Filter hidden files
                    is_hidden = entry.name.startswith('.')
                    if is_hidden and not show_hidden:
                        log_func(f"Scan Filter: Skipping hidden '{entry.name}' during discovery", "debug")
                        continue # Skip hidden if show_hidden is False
                    
                    # Apply explicit exclude patterns
                    is_excluded = False
                    for pattern in exclude_patterns:
                        if fnmatch.fnmatch(entry.name, pattern):
                            log_func(f"Scan Filter: Skipping '{entry.name}' matching exclude pattern '{pattern}'", "debug")
                            is_excluded = True
                            break
                    if is_excluded:
                        continue
                    # --- END FILTERING ---

                    # Increment only if passing minimal filters
                    scanned_count += 1

                    try:
                        # Use cached stat from scandir if possible
                        # Follow symlinks for dirs to scan into them, but not for files/type checking
                        is_dir = entry.is_dir() # Checks if it's a directory (or symlink to one)
                        is_file = entry.is_file() # Checks if it's a file (or symlink to one)
                    except OSError as stat_error:
                         log_func(f"Scan: Could not stat '{entry.path}', skipping. Error: {stat_error}", "warning")
                         continue # Skip items we can't stat

                    # Process Files for Type Scan
                    if scan_type == "file" and is_file:
                        # Don't follow symlinks for file type check
                        ext = entry_path.suffix.lower().lstrip(".") if entry_path.suffix else "(no ext)"
                        item_counter[ext] += 1
                        log_func(f"Scan Found File: '{entry.name}' (ext: {ext})", "debug")

                    # Process Directories for Name Scan and Queueing
                    elif is_dir: # Intentionally includes symlinks to directories
                        dir_name = entry.name # Get dir name once

                        # If scanning for directory names, add its name to the counter
                        if scan_type == "dir":
                            item_counter[dir_name] += 1
                            log_func(f"Scan Found Dir Name: '{dir_name}'", "debug")
                            
                        # Check if we should recurse into this directory during scanning
                        should_recurse = True
                        
                        # Don't recurse into directories in the high-performance exclude list
                        if dir_name in scan_exclude_dirs:
                            should_recurse = False
                            log_func(f"Scan Skip Recurse: '{dir_name}' is in performance exclude list", "debug")
                        
                        # Only add directory to scan queue if we should recurse
                        if should_recurse:
                            try:
                                # Resolve directory to avoid cycles
                                real_path = entry_path.resolve()
                                if real_path not in seen_dirs:
                                    seen_dirs.add(real_path)
                                    dirs_to_scan.append(entry_path) # Add original path to scan queue
                                    log_func(f"Scan Queue Add: '{entry_path}' (resolves to '{real_path}')", "debug")
                                else:
                                    log_func(f"Scan Dir Seen: '{entry_path}' resolves to '{real_path}'", "debug")
                            except Exception as e_resolve:
                                # Non-fatal, just don't scan into it
                                log_func(f"Scan: Could not resolve dir '{entry_path}', not adding to queue: {e_resolve}", "warning")

                if scanned_count >= max_items:
                    log_func(f"Scan reached max items ({max_items}).", "info")
                    break

            except PermissionError:
                log_func(f"Scan: Permission denied for '{current_dir}', skipping.", "warning")
            except FileNotFoundError:
                log_func(f"Scan: Directory '{current_dir}' not found (possibly removed during scan?), skipping.", "warning")
            except Exception as e_scan:
                log_func(f"Scan: Unexpected error scanning '{current_dir}': {e_scan}", "error")

    except KeyboardInterrupt:
        print("\nScan interrupted by user.")
        log_func("Scan interrupted by user.", "warning")
        # Allow partial results to be returned
    finally:
        if spinner: # Clear spinner line
            print("\r" + " " * last_status_len + "\r", end="", flush=True)

    log_func(f"Scan finished. Found {len(item_counter)} unique {scan_label} from {scanned_count} items scanned.", "info")
    return item_counter