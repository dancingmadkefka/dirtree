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
    from .dirtree_config import COMMON_DIR_EXCLUDES # Use specific smart dir excludes for scanning
except ImportError:
    try: # For direct execution for testing scanner
        from dirtree_styling import Colors
        from dirtree_config import COMMON_DIR_EXCLUDES
    except ImportError:
        class Colors: RESET = ""; YELLOW = ""; CYAN = "" # Dummy
        COMMON_DIR_EXCLUDES = []

def scan_directory(
    root_dir: Path,
    scan_type: str, # "file" or "dir"
    max_items: int,
    show_hidden: bool,
    log_func: Callable, # Function for logging messages
    # For scanning, we primarily care about not recursing into very large common junk folders.
    # Other exclude patterns are less relevant for simple discovery.
    initial_scan_recursion_excludes: Optional[List[str]] = None 
) -> CounterType[str]:
    """
    Scans directory to find file extensions or directory names for interactive selection lists.
    Uses minimal filtering (show_hidden and recursion excludes) for broad discovery.
    """
    log_func(f"Starting {scan_type} scan in '{root_dir}' (max: {max_items}, hidden: {show_hidden})", "info")
    item_counter: CounterType[str] = Counter()
    scanned_count = 0
    scan_label = "file types" if scan_type == "file" else "directory names"

    spinner_chars = ["/", "-", "\\", "|"] if sys.stdout.isatty() else [""]
    spinner_idx = 0
    term_width = shutil.get_terminal_size((80, 20)).columns
    last_status_len = 0
    last_update_time = time.monotonic()

    # Performance exclude for scan recursion (these are not user patterns, but hardcoded for scan speed)
    # We combine this with any passed `initial_scan_recursion_excludes` which might come from smart excludes.
    hardcoded_scan_perf_excludes = {
        "node_modules", "__pycache__", ".git", ".venv", "venv", "env",
        "build", "dist", ".cache", ".npm", ".next", "out", "target", "obj",
        # Add others if they are known to be huge and slow down scans
    }
    final_recursion_excludes = hardcoded_scan_perf_excludes.copy()
    if initial_scan_recursion_excludes:
        final_recursion_excludes.update(initial_scan_recursion_excludes)
    
    log_func(f"Scanner will not recurse into (for perf): {final_recursion_excludes}", "debug")

    dirs_to_scan_queue: List[Path] = []
    seen_physical_dirs: Set[Path] = set() # To avoid symlink loops by resolved path

    try:
        resolved_root = root_dir.resolve()
        seen_physical_dirs.add(resolved_root)
        dirs_to_scan_queue.append(root_dir) # Start with original path
        log_func(f"Resolved root for scan: '{resolved_root}'", "debug")
    except Exception as e_resolve_root:
         print(f"\n{Colors.YELLOW}Warning: Could not resolve root dir '{root_dir}' for scan: {e_resolve_root}{Colors.RESET}")
         log_func(f"Could not resolve root '{root_dir}' for scan: {e_resolve_root}", "warning")
         # Add unresolved path to seen set to prevent trying to resolve it again if encountered
         # This doesn't fully prevent loops if symlinks point back to unresolved paths, but helps.
         try: seen_physical_dirs.add(root_dir.absolute()) 
         except: pass # If absolute also fails
         dirs_to_scan_queue.append(root_dir)

    try:
        while dirs_to_scan_queue and scanned_count < max_items:
            current_dir_to_scan = dirs_to_scan_queue.pop(0) # BFS
            log_func(f"Scanning dir: '{current_dir_to_scan}'", "debug")

            current_time = time.monotonic()
            if spinner_chars[0] and (scanned_count % 100 == 0 or scanned_count < 20 or (current_time - last_update_time) > 0.2):
                elapsed = current_time - last_update_time # This is interval, not total
                status = f"{spinner_chars[spinner_idx % len(spinner_chars)]} Scanned {scanned_count}/{max_items} items... Found {len(item_counter)} unique {scan_label} ({elapsed:.1f}s since last update)"
                padded_status = status.ljust(last_status_len)
                print(f"\r{padded_status}", end="", flush=True)
                last_status_len = len(status)
                spinner_idx += 1
                last_update_time = current_time

            try:
                for entry in os.scandir(current_dir_to_scan):
                    if scanned_count >= max_items: break
                    entry_path_obj = Path(entry.path)

                    is_hidden_entry = entry.name.startswith('.')
                    if is_hidden_entry and not show_hidden:
                        log_func(f"Scan Filter: Skipping hidden '{entry.name}' during discovery", "debug")
                        continue
                    
                    # Note: We do NOT apply complex exclude patterns during this discovery scan,
                    # only the `final_recursion_excludes` for performance.

                    scanned_count += 1 # Count an item if it passes basic hidden check

                    try:
                        is_dir_type = entry.is_dir() # Follows symlinks for type check by default
                        is_file_type = entry.is_file()
                    except OSError as e_stat:
                         log_func(f"Scan: Could not stat '{entry.path}', skipping. Error: {e_stat}", "warning")
                         continue

                    if scan_type == "file" and is_file_type:
                        ext = entry_path_obj.suffix.lower().lstrip(".") if entry_path_obj.suffix else "(no ext)"
                        item_counter[ext] += 1
                        log_func(f"Scan Found File: '{entry.name}' (ext: {ext})", "debug")

                    elif is_dir_type:
                        dir_name_str = entry.name
                        if scan_type == "dir":
                            item_counter[dir_name_str] += 1
                            log_func(f"Scan Found Dir Name: '{dir_name_str}'", "debug")
                        
                        # Recursion decision for scan performance
                        if dir_name_str not in final_recursion_excludes:
                            try:
                                resolved_entry_path = entry_path_obj.resolve()
                                if resolved_entry_path not in seen_physical_dirs:
                                    seen_physical_dirs.add(resolved_entry_path)
                                    dirs_to_scan_queue.append(entry_path_obj) # Add original path
                                    log_func(f"Scan Queue Add: '{entry_path_obj}' (resolves to '{resolved_entry_path}')", "debug")
                                else:
                                    log_func(f"Scan Dir Already Seen (resolved): '{entry_path_obj}' -> '{resolved_entry_path}'", "debug")
                            except Exception as e_resolve_entry:
                                log_func(f"Scan: Could not resolve dir '{entry_path_obj}', not queueing: {e_resolve_entry}", "warning")
                        else:
                             log_func(f"Scan Skip Recurse (perf): '{dir_name_str}' is in perf exclude list", "debug")
                
                if scanned_count >= max_items:
                    log_func(f"Scan reached max items ({max_items}).", "info")
                    break
            except PermissionError:
                log_func(f"Scan: Permission denied for '{current_dir_to_scan}', skipping.", "warning")
            except FileNotFoundError: # Can happen if dir is deleted during scan
                log_func(f"Scan: Directory '{current_dir_to_scan}' not found, skipping.", "warning")
            except Exception as e_inner_scan:
                log_func(f"Scan: Unexpected error scanning '{current_dir_to_scan}': {e_inner_scan}", "error")

    except KeyboardInterrupt:
        print("\nScan interrupted by user.")
        log_func("Scan interrupted by user.", "warning")
    finally:
        if spinner_chars[0]: # Clear spinner line
            print("\r" + " " * (last_status_len + 5) + "\r", end="", flush=True)

    log_func(f"Scan finished. Found {len(item_counter)} unique {scan_label} from {scanned_count} items processed.", "info")
    return item_counter