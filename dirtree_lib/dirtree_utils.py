# -*- coding: utf-8 -*-
"""
Utility functions for IntuitiveDirTree, including formatting, logging, and error handling.
"""

import sys
import traceback
import textwrap
from pathlib import Path
from datetime import datetime
from typing import Tuple, Callable, TYPE_CHECKING, Optional

# Import Colors from the styling module
try:
    # Use relative import if running as part of the package
    from .dirtree_styling import Colors
    from .dirtree_config import get_terminal_width
except ImportError:
    # Fallback for direct execution or testing
    try: # For development when running utils directly or from sibling test
        from dirtree_styling import Colors
        from dirtree_config import get_terminal_width
    except ImportError:
        # Define a dummy Colors class if import fails completely
        class Colors:
            RESET = ""; BOLD = ""; BLACK = ""; RED = ""; GREEN = ""; YELLOW = ""
            BLUE = ""; MAGENTA = ""; CYAN = ""; WHITE = ""; GRAY = ""
        def get_terminal_width(): return 80

# --- Formatting ---
def format_bytes(size_bytes: int) -> str:
    """Helper function to format bytes into KB, MB, GB."""
    if not isinstance(size_bytes, (int, float)) or size_bytes < 0: return "N/A"
    if size_bytes < 1024: return f"{size_bytes} B"
    elif size_bytes < 1024**2: return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024**3: return f"{size_bytes / 1024**2:.1f} MB"
    else: return f"{size_bytes / 1024**3:.2f} GB"

def parse_size_string(size_str: str, default: int = 100 * 1024) -> int:
    """
    Parses size strings like '50k', '1.5m', '2g' into bytes.
    """
    size_str_orig = size_str # Keep original for warning message
    size_str = size_str.strip().lower()
    if not size_str: return default
    
    multiplier = 1
    if size_str.endswith('k') or size_str.endswith('kb'):
        multiplier = 1024
        size_str = size_str[:-1] if size_str.endswith('k') else size_str[:-2]
    elif size_str.endswith('m') or size_str.endswith('mb'):
        multiplier = 1024 * 1024
        size_str = size_str[:-1] if size_str.endswith('m') else size_str[:-2]
    elif size_str.endswith('g') or size_str.endswith('gb'):
        multiplier = 1024 * 1024 * 1024
        size_str = size_str[:-1] if size_str.endswith('g') else size_str[:-2]
    elif size_str.endswith('b'): # Explicit bytes
        size_str = size_str[:-1]
        
    try:
        value = float(size_str)
        return int(value * multiplier)
    except ValueError:
        print(f"{Colors.YELLOW}Warning: Invalid size string '{size_str_orig}'. Using default {format_bytes(default)}.{Colors.RESET}")
        return default

def format_wrapped_text(text: str, indent: int = 0, width: Optional[int] = None) -> str:
    """
    Format text with proper wrapping and indentation for terminal display.
    """
    if width is None:
        width = get_terminal_width()
    
    wrap_width = max(width - indent, 40)
    indent_str = ' ' * indent
    wrapped_lines = textwrap.wrap(text, width=wrap_width, subsequent_indent=indent_str)
    # First line might not need initial indent if textwrap handles it all with subsequent_indent
    # But usually, we want all lines indented if indent > 0
    if indent > 0 and wrapped_lines:
        return '\n'.join(indent_str + line.lstrip() for line in wrapped_lines) # lstrip to handle subsequent_indent
    elif wrapped_lines: # No indent, just join
        return '\n'.join(wrapped_lines)
    return ""


# --- Logging ---
def log_message(message: str, level: str = "info", verbose: bool = False, colorize: bool = False):
    """Logs a message to stderr if verbose is enabled."""
    if not verbose and level not in ["error", "warning", "success"]: # Always show critical messages if not verbose
        if verbose is False and level in ["info", "debug"]: # Explicit verbose=False hides these
             return
    
    color_map = {
        "error": Colors.RED, "warning": Colors.YELLOW, "success": Colors.GREEN,
        "info": Colors.CYAN, "debug": Colors.GRAY
    }
    color = color_map.get(level.lower(), Colors.RESET) if colorize else ""
    reset = Colors.RESET if colorize else ""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3] # Milliseconds
    
    # Ensure message is string and handle multi-line messages correctly for logging
    message_str = str(message)
    log_prefix = f"[{timestamp}] {color}[{level.upper():<7}] {reset}" # Padded level
    
    # Indent subsequent lines of a multi-line message
    lines = message_str.splitlines()
    if not lines: return

    print(f"{log_prefix}{lines[0]}", file=sys.stderr)
    for line in lines[1:]:
        print(f"{' ' * (len(log_prefix) - len(color) - len(reset) +1)}{line}", file=sys.stderr) # Align subsequent lines


# --- Error Handling ---
def handle_error(
    path: Path,
    error: Exception,
    log_func: Callable,
    colorize: bool,
    current_skip_all_errors: bool, # Current state of "skip all"
    interactive_prompts: bool,
    phase: str = "processing"
) -> Tuple[bool, bool]: # Returns (should_skip_this_item, new_skip_all_setting)
    """
    Handles errors, returns if item should be skipped and if "skip all" was chosen.
    """
    color_red = Colors.RED if colorize else ""
    color_yellow = Colors.YELLOW if colorize else ""
    color_reset = Colors.RESET if colorize else ""

    error_name = error.__class__.__name__
    error_details = str(error)
    full_error_message = f"Error {phase} '{path}': {error_name}: {error_details}"
    log_func(full_error_message, level="error")
    
    guidance = ""
    if isinstance(error, PermissionError):
        guidance = f"This is a {color_yellow}permission error{color_reset}. Try running with administrator/root privileges if appropriate."
    elif isinstance(error, FileNotFoundError):
        guidance = "The file or directory may have been moved or deleted during execution."
    elif isinstance(error, OSError) and hasattr(error, 'winerror') and getattr(error, 'winerror') == 32: # Windows specific: file in use
        guidance = "The file might be locked or in use by another process."
        
    if current_skip_all_errors:
        log_func(f"Auto-skipping '{path}' due to --skip-errors or previous choice.", "warning")
        return True, True # Skip this item, keep skip_all as True

    if not interactive_prompts: # Non-interactive, e.g. output piped or TTY not available
         print(f"{color_red}Error: {full_error_message}{color_reset}", file=sys.stderr)
         if guidance: print(f"{color_yellow}{guidance}{color_reset}", file=sys.stderr)
         print(f"{color_yellow}Skipping this item (non-interactive mode)...{color_reset}", file=sys.stderr)
         return True, False # Skip item, don't change skip_all setting

    # Interactive prompt
    print(f"\n{color_red}--- Problem Encountered ---{color_reset}")
    print(f"Path: {Colors.CYAN}{path}{color_reset}\nReason: {error_name}: {error_details}")
    if guidance: print(f"{color_yellow}{guidance}{color_reset}")
    print(f"{color_red}---------------------------{color_reset}")
    
    while True:
        prompt_text = (f"{color_yellow}Action? (1=Skip item, 2=Skip ALL future errors, 3=Abort script, 4=Show details): {color_reset}")
        choice = input(prompt_text).strip().lower()
        if choice == '1' or choice == 's': return True, False # Skip item, don't change skip_all
        elif choice == '2' or choice == 'a':
            print(f"{color_yellow}Will skip all subsequent errors this session.{color_reset}")
            return True, True # Skip item, and set skip_all to True for future
        elif choice == '3' or choice == 'q':
            print(f"{color_red}Aborting script execution.{color_reset}")
            return False, False # Don't skip (caller should abort), don't change skip_all
        elif choice == '4' or choice == 'd':
            print(f"\n{color_yellow}--- Error Details (Traceback) ---{color_reset}")
            traceback.print_exc(file=sys.stderr)
            print(f"{color_yellow}---------------------------------{color_reset}\n")
            # Loop again for new action choice
        else:
            print(f"{color_red}Invalid choice. Please enter 1, 2, 3, or 4.{color_reset}")