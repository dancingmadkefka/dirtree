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
    try:
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
    if size_bytes < 0: return "N/A"
    if size_bytes < 1024: return f"{size_bytes} B"
    elif size_bytes < 1024**2: return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024**3: return f"{size_bytes / 1024**2:.1f} MB"
    else: return f"{size_bytes / 1024**3:.2f} GB"

def parse_size_string(size_str: str, default: int = 100 * 1024) -> int:
    """
    Parses size strings like '50k', '1.5m', '2g' into bytes.
    
    Args:
        size_str: String with optional suffix k, m, g for KB, MB, GB
        default: Default value if parsing fails
        
    Returns:
        Size in bytes
    """
    size_str = size_str.strip().lower()
    if not size_str: return default
    
    # Handle decimal values like "1.5m"
    try:
        if size_str.endswith('k'):
            return int(float(size_str[:-1]) * 1024)
        elif size_str.endswith('m'):
            return int(float(size_str[:-1]) * 1024 * 1024)
        elif size_str.endswith('g'):
            return int(float(size_str[:-1]) * 1024 * 1024 * 1024)
        elif size_str.endswith('b'): # Explicit bytes
            return int(float(size_str[:-1]))
        else:
            # Try parsing as a plain number (bytes)
            return int(float(size_str))
    except ValueError:
        # Use format_bytes for the warning message
        print(f"Warning: Invalid size string '{size_str}'. Using default {format_bytes(default)}.")
        return default

def format_wrapped_text(text: str, indent: int = 0, width: Optional[int] = None) -> str:
    """
    Format text with proper wrapping and indentation for terminal display.
    
    Args:
        text: The text to format
        indent: Number of spaces to indent each line
        width: Terminal width (auto-detected if None)
        
    Returns:
        Formatted text with wrapping and indentation
    """
    if width is None:
        width = get_terminal_width()
    
    # Account for indentation in wrapping width
    wrap_width = max(width - indent, 40)  # Don't go below 40 chars width
    
    # Wrap text and add indentation
    indent_str = ' ' * indent
    wrapped_lines = textwrap.wrap(text, width=wrap_width)
    return '\n'.join(indent_str + line for line in wrapped_lines)

# --- Logging ---
def log_message(message: str, level: str = "info", verbose: bool = False, colorize: bool = False):
    """Logs a message to stderr if verbose is enabled."""
    if not verbose:
        return
    color_map = {
        "error": Colors.RED,
        "warning": Colors.YELLOW,
        "success": Colors.GREEN,
        "info": Colors.CYAN,
        "debug": Colors.GRAY
    }
    color = color_map.get(level, Colors.RESET) if colorize else ""
    reset = Colors.RESET if colorize else ""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] {color}[{level.upper()}] {message}{reset}", file=sys.stderr)

# --- Error Handling ---
def handle_error(
    path: Path,
    error: Exception,
    log_func: Callable, # Pass the log_message function configured by the caller
    colorize: bool,
    skip_errors: bool, # Current state
    interactive_prompts: bool, # Current state
    phase: str = "processing"
) -> Tuple[bool, bool]:
    """
    Handles errors encountered during processing.

    Args:
        path: The path where the error occurred.
        error: The exception raised.
        log_func: The logging function to use.
        colorize: Whether to use colors in output.
        skip_errors: Current setting for skipping all errors.
        interactive_prompts: Current setting for interactive prompts.
        phase: Description of where the error occurred (e.g., "processing", "reading").

    Returns:
        A tuple (should_skip_item, should_set_skip_all_future):
        - should_skip_item (bool): True if the item should be skipped.
        - should_set_skip_all_future (bool): True if the user chose to skip all future errors.
    """
    color_red = Colors.RED if colorize else ""
    color_yellow = Colors.YELLOW if colorize else ""
    color_reset = Colors.RESET if colorize else ""

    error_message = f"Error {phase} '{path}': {error.__class__.__name__}: {error}"
    log_func(error_message, level="error")
    
    # Provide more specific guidance based on error type
    guidance = ""
    if isinstance(error, PermissionError):
        guidance = f"This is a {color_yellow}permission error{color_reset}. You might need administrator/root privileges."
    elif isinstance(error, FileNotFoundError):
        guidance = f"The file or directory no longer exists or was moved."
    elif isinstance(error, OSError) and hasattr(error, 'winerror') and getattr(error, 'winerror') == 32:
        guidance = f"The file is being used by another process and cannot be accessed."
        
    # Note: The caller is responsible for adding the item to skipped_items list.
    if skip_errors:
        log_func(f"Auto-skipping {path} due to previous choice or --skip-errors.", "warning")
        return True, False # Skip this item, don't change skip_all setting

    if not interactive_prompts:
         print(f"{color_red}Error: {error_message}{color_reset}", file=sys.stderr)
         if guidance:
             print(f"{color_yellow}{guidance}{color_reset}", file=sys.stderr)
         print(f"{color_yellow}Skipping this item (non-interactive mode)...{color_reset}", file=sys.stderr)
         return True, False # Skip this item, don't change skip_all setting

    # Interactive prompt
    print(f"\n{color_red}--- Problem Encountered ---{color_reset}")
    print(f"Path: {path}\nReason: {error.__class__.__name__}: {error}")
    if guidance:
        print(f"{color_yellow}{guidance}{color_reset}")
    print(f"{color_red}---------------------------{color_reset}")
    
    while True:
        prompt = (f"{color_yellow}Action? (1=Skip item, 2=Skip all future errors, 3=Abort script, 4=Show details): {color_reset}")
        choice = input(prompt).strip()
        if choice == '1':
            return True, False # Skip item, don't change skip_all
        elif choice == '2':
            print(f"{color_yellow}Will skip all subsequent errors.{color_reset}")
            return True, True # Skip item, DO change skip_all
        elif choice == '3':
            print(f"{color_red}Aborting.{color_reset}")
            return False, False # Don't skip (abort), don't change skip_all
        elif choice == '4':
            print(f"\n{color_yellow}--- Error Details ---{color_reset}")
            traceback.print_exc(file=sys.stderr)
            print(f"{color_yellow}------------------{color_reset}\n")
        else:
            print(f"{color_red}Invalid choice.{color_reset}")