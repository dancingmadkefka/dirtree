# -*- coding: utf-8 -*-
"""
Interactive components for IntuitiveDirTree, using the 'pick' library
for user selections (directory, filters). Also includes the main interactive
setup workflow.
"""

import sys
import os
import fnmatch
import traceback
from pathlib import Path
from collections import Counter
from typing import Optional, List, Tuple, Dict, Any, Set, Counter as CounterType, Callable

# --- Optional Dependency: pick ---
pick_module: Optional[Any] = None # Renamed to avoid conflict with function name
pick_available: bool = False
try:
    import pick as pick_lib # Import with an alias
    pick_module = pick_lib
    pick_available = True
    if sys.platform != 'win32': # Basic curses check
        import curses
        curses.setupterm()
except ImportError:
    print("Warning: 'pick' library not found. Interactive selection features will be disabled.", file=sys.stderr)
    print("         Install it using: pip install pick", file=sys.stderr)
except Exception as e: # Broad exception for curses issues
    print(f"Warning: Failed to initialize 'pick' (potential curses issue): {e}", file=sys.stderr)
    print("         Interactive selection features might be unstable or disabled.", file=sys.stderr)
    if sys.platform == 'win32':
        print("         On Windows, ensure 'windows-curses' is installed: pip install windows-curses", file=sys.stderr)

# --- Imports from other modules ---
try:
    from .dirtree_config import COMMON_DIR_EXCLUDES, COMMON_FILE_EXCLUDES, get_default_dir, set_default_dir, save_config, DEFAULT_LLM_INCLUDE_EXTENSIONS, DEFAULT_LLM_EXCLUDED_EXTENSIONS
    from .dirtree_scanner import scan_directory
    from .dirtree_styling import Colors, DEFAULT_FILETYPE_COLORS, TreeStyle
    from .dirtree_utils import format_bytes, log_message, parse_size_string
    from . import __version__
except ImportError:
    print("Warning: Running interactive module potentially outside of package context.", file=sys.stderr)
    class Colors: RESET = ""; YELLOW = ""; GREEN = ""; CYAN = ""; BOLD = ""; RED = ""; MAGENTA = ""
    class TreeStyle:
        AVAILABLE = {"ascii": {}, "unicode": {}, "bold": {}, "rounded": {}, "emoji": {}, "minimal": {}}
    DEFAULT_LLM_INCLUDE_EXTENSIONS = set()
    DEFAULT_LLM_EXCLUDED_EXTENSIONS = set()
    DEFAULT_FILETYPE_COLORS = {}
    COMMON_DIR_EXCLUDES = []
    COMMON_FILE_EXCLUDES = []
    def get_default_dir(): return None
    def set_default_dir(d): pass
    def save_config(c): pass
    def scan_directory(*args, **kwargs): return Counter()
    def format_bytes(b): return str(b)
    def log_message(*args, **kwargs): pass
    def parse_size_string(s, default): return default
    __version__ = "?.?.?"


# --- Interactive Directory Selection ---
def select_directory_interactive(start_dir: Optional[str] = None) -> Optional[str]:
    if not pick_available or pick_module is None: # Check pick_module
        print("Interactive directory selection unavailable ('pick' library missing or failed to load).")
        return None

    current_path = Path(start_dir).resolve() if start_dir and Path(start_dir).exists() else Path.cwd()
    visited_paths: List[Path] = []

    print(f"\n{Colors.CYAN}Directory Browser Instructions:{Colors.RESET}")
    print(f"- Use {Colors.BOLD}arrow keys{Colors.RESET} to navigate, {Colors.BOLD}Enter{Colors.RESET} to select/go into dir.")
    print(f"- Select {Colors.BOLD}'✅ Select Current...'{Colors.RESET} to confirm.")
    print(f"- Press {Colors.BOLD}Ctrl+C{Colors.RESET} to cancel.\n")

    try:
        while True:
            options = []
            title_parts = [f"Directory Browser - Current: {Colors.CYAN}{current_path}{Colors.RESET}"]

            # Parent directory option
            if current_path.parent != current_path: # Not at root
                options.append(("⬆️  .. (Parent Directory)", str(current_path.parent)))

            # Back option if history exists
            if visited_paths:
                options.append(("⏪ Back (Previous Directory)", "__BACK__"))

            try:
                # List directories
                dirs_in_current = sorted(
                    [(f"📂 {d.name}", str(d)) for d in current_path.iterdir() if d.is_dir()],
                    key=lambda x: x[0].lower()
                )
                options.extend(dirs_in_current)

                file_count = sum(1 for _ in current_path.iterdir() if _.is_file())
                title_parts.append(f"({len(dirs_in_current)} dirs, {file_count} files)")
            except Exception as e:
                title_parts.append(f"{Colors.RED}(Error listing: {e}){Colors.RESET}")

            options.append((f"✅ Select Current: '{current_path.name}'", str(current_path)))
            options.append(("❌ Cancel Selection", "__CANCEL__"))

            title = " ".join(title_parts)

            picker = pick_module.Picker(options, title, indicator='=>', min_selection_count=1)
            selected_option_tuple, _ = picker.start() # Can raise KeyboardInterrupt

            selected_text, selected_value = selected_option_tuple

            if selected_value == "__CANCEL__": return None
            if selected_value == str(current_path): return str(current_path) # ✅ Select Current

            new_path_candidate = Path(selected_value)
            if selected_value == "__BACK__":
                if visited_paths:
                    current_path = visited_paths.pop()
            elif new_path_candidate.is_dir(): # Navigating into a dir or parent
                if selected_value != str(current_path.parent): # If not going up, add to history
                     visited_paths.append(current_path)
                current_path = new_path_candidate
            else: # Should not happen with current options
                print(f"{Colors.RED}Invalid selection state.{Colors.RESET}")

    except (KeyboardInterrupt, Exception) as e:
        print("\nDirectory selection cancelled or failed.")
        if not isinstance(e, KeyboardInterrupt): print(f"Error: {e}")
        return None


# --- Generic Interactive Selection (for file types, dir names) ---
def general_interactive_selection(
    items_counter: CounterType[str],
    item_type_label: str, # e.g., "file type", "directory name"
    prompt_title: str,
    mode_action_word: str, # e.g., "INCLUDE" (for file types), "EXCLUDE" (for dir names)
    preselected_items: Optional[List[str]] = None,
    common_items_suggestion: Optional[Set[str]] = None, # e.g. common code extensions
    common_suggestion_label: str = "COMMON items"
) -> List[str]:
    if not pick_available or pick_module is None:
        print(f"Interactive {item_type_label} selection unavailable ('pick' library missing or failed to load).")
        return []
    if not items_counter:
        print(f"No {item_type_label}s found to select.")
        return []

    actual_preselected = set(preselected_items or [])
    sorted_items = sorted(items_counter.items(), key=lambda item: (-item[1], item[0]))

    options = []
    for name, count in sorted_items:
        # Don't show pre-selection ticks as they're confusing
        # Instead, mark smart-excluded directories with a special indicator
        if name in COMMON_DIR_EXCLUDES or name.startswith("__"):
            prefix = "🔒 "  # Lock symbol to indicate these are always excluded
        else:
            prefix = "  "
        options.append((f"{prefix}{name} ({count} occurrences)", name))

    options.insert(0, (f"✅ Select ALL {item_type_label}s", "__ALL__"))
    options.insert(1, (f"❌ Select NONE ({mode_action_word} nothing)", "__NONE__"))

    if common_items_suggestion:
        found_common = any(name in common_items_suggestion for name, _ in sorted_items)
        if found_common:
            options.insert(2, (f"🔍 Select {common_suggestion_label}", "__COMMON__"))

    full_title = f"{prompt_title}\nControls: ↑/↓ Navigate | Space Toggle | Enter Confirm\nTip: 'ALL'/'NONE'/'COMMON' can save time.\nNote: 🔒 items are always excluded regardless of selection."

    try:
        # Pre-select items by marking them in the options list for display
        # The actual selection happens via user interaction.
        picker = pick_module.Picker(options, full_title, indicator='*', multiselect=True, default_index=0)

        # Mark preselected items in the picker instance if library supports it
        # (This is tricky with `pick`; usually selection is purely interactive)
        # For now, visual indication in option text is the main preselection cue.

        selected_options_tuples = picker.start() # List of (option_data, index)
    except (KeyboardInterrupt, Exception) as e:
        print(f"\n{item_type_label.capitalize()} selection cancelled or failed.")
        if not isinstance(e, KeyboardInterrupt): print(f"Error: {e}")
        return list(actual_preselected) # Return original preselection on error

    selected_names = []
    explicitly_selected_values = {item[0][1] for item in selected_options_tuples} # (('text', value), index)

    if "__ALL__" in explicitly_selected_values:
        selected_names = [name for name, _ in sorted_items]
    elif "__NONE__" in explicitly_selected_values:
        selected_names = []
    elif "__COMMON__" in explicitly_selected_values and common_items_suggestion:
        selected_names = [name for name, _ in sorted_items if name in common_items_suggestion]
        # Fallback if common results in empty (e.g. no common items found in project)
        if not selected_names and item_type_label == "file type":
            selected_names = [name for name, _ in sorted_items if name in DEFAULT_LLM_INCLUDE_EXTENSIONS][:10]
    else: # Regular selection
        selected_names = [val for val in explicitly_selected_values if val not in ("__ALL__", "__NONE__", "__COMMON__")]

    print(f"{Colors.GREEN}Selected {len(selected_names)} {item_type_label}s to {mode_action_word}:{Colors.RESET} "
          f"{', '.join(selected_names[:10]) if selected_names else 'None'}"
          f"{' and more...' if len(selected_names) > 10 else ''}")
    return selected_names


# --- Interactive Setup Workflow ---
def run_interactive_setup() -> Dict[str, Any]:
    """
    Guides the user through setting up the directory tree generation options interactively.
    Returns a dictionary of options compatible with IntuitiveDirTree constructor, or empty if cancelled.
    """
    print(f"\n--- {Colors.BOLD}IntuitiveDirTree v{__version__} Interactive Setup{Colors.RESET} ---")
    config: Dict[str, Any] = {}
    current_dir_path = Path.cwd()
    default_dir_path_str = get_default_dir()

    # Step 1: Directory Selection
    print(f"\n{Colors.BOLD}Step 1: Directory Selection{Colors.RESET}")
    dir_options = [
        (f"1) Current directory: {Colors.CYAN}{current_dir_path}{Colors.RESET}", str(current_dir_path)),
    ]
    if default_dir_path_str:
        dir_options.append((f"2) Default directory: {Colors.CYAN}{default_dir_path_str}{Colors.RESET}", default_dir_path_str))
    dir_options.extend([
        (f"{len(dir_options)+1}) Select interactively (browse file system)", "__SELECT__"),
        (f"{len(dir_options)+2}) Enter a path manually", "__MANUAL__"),
        (f"{len(dir_options)+3}) Cancel setup", "__CANCEL__")
    ])

    dir_choice_idx = 0 # Default to current directory
    if pick_available and pick_module:
        picker = pick_module.Picker([opt[0] for opt in dir_options], "Choose directory source:", indicator="=>")
        _, dir_choice_idx = picker.start()
    else: # Fallback to text input
        for opt_text, _ in dir_options: print(opt_text)
        choice_num_str = input(f"Choose option [1-{len(dir_options)}]: ").strip()
        dir_choice_idx = int(choice_num_str) -1 if choice_num_str.isdigit() and 0 < int(choice_num_str) <= len(dir_options) else 0

    chosen_dir_action = dir_options[dir_choice_idx][1]

    if chosen_dir_action == "__CANCEL__": return {}
    elif chosen_dir_action == "__SELECT__":
        selected_dir_str = select_directory_interactive(start_dir=str(default_dir_path_str or current_dir_path))
        if selected_dir_str is None: return {}
        config['root_dir'] = selected_dir_str
    elif chosen_dir_action == "__MANUAL__":
        manual_path_str = input("Enter directory path: ").strip()
        try:
            p = Path(manual_path_str).resolve(strict=True)
            if not p.is_dir(): raise NotADirectoryError
            config['root_dir'] = str(p)
        except (FileNotFoundError, NotADirectoryError):
            print(f"{Colors.RED}Error: Invalid path or not a directory. Aborting.{Colors.RESET}"); return {}
    else: # Direct path choice (current or default)
        config['root_dir'] = chosen_dir_action

    print(f"Using directory: {Colors.CYAN}{config['root_dir']}{Colors.RESET}")
    if config['root_dir'] != default_dir_path_str and chosen_dir_action not in [str(current_dir_path), default_dir_path_str]:
        if input(f"Set '{config['root_dir']}' as default for future runs? [y/{Colors.GREEN}N{Colors.RESET}]: ").lower() == 'y':
            set_default_dir(config['root_dir'])
            print("Default directory saved.")

    # Step 2: Filtering Options
    print(f"\n{Colors.BOLD}Step 2: Filtering Options{Colors.RESET}")
    print("Configure what appears in the tree and what content is exported for LLMs.")

    # Smart Exclude (affects tree and LLM)
    config['use_smart_exclude'] = input(f"Use Smart Exclude (hides common clutter like .git, node_modules)? [{Colors.GREEN}Y{Colors.RESET}/n]: ").lower() not in ['n', 'no']
    print(f"  Smart Exclude for tree display and LLM export: {'ON' if config['use_smart_exclude'] else 'OFF'}")

    # Show Hidden (affects tree display)
    config['show_hidden'] = input(f"Show hidden files/dirs (starting with '.') in tree? [y/{Colors.GREEN}N{Colors.RESET}]: ").lower() == 'y'
    print(f"  Show Hidden in tree: {'Yes' if config['show_hidden'] else 'No'}")

    # Initialize filter lists
    config['cli_include_patterns'] = [] # Not set interactively, from CLI only
    config['cli_exclude_patterns'] = [] # Not set interactively, from CLI only

    initial_scan_excludes = list(COMMON_DIR_EXCLUDES) if config['use_smart_exclude'] else []

    # Interactive Filtering for LLM Content
    print(f"\n{Colors.BOLD}Interactive Filtering for LLM Content:{Colors.RESET}")
    if input(f"Scan directory to select file types/directories for LLM export? [y/{Colors.GREEN}N{Colors.RESET}]: ").lower() == 'y':
        scan_max = 20000
        verbose_log_scan = lambda msg, lvl="debug": log_message(msg, level=lvl, verbose=True, colorize=True)

        # Scan for file types (for LLM content inclusion)
        print(f"\n--- Scanning for File Types (for LLM Content Inclusion) ---")
        input("Press Enter to start scan...")
        file_types_counts = scan_directory(Path(config['root_dir']), "file", scan_max, config['show_hidden'], verbose_log_scan, initial_scan_excludes)
        if file_types_counts:
            config['interactive_file_type_includes_for_llm'] = general_interactive_selection(
                file_types_counts, "file type", "Select File Types to INCLUDE in LLM Export Content:", "INCLUDE",
                common_items_suggestion=DEFAULT_LLM_INCLUDE_EXTENSIONS, common_suggestion_label="COMMON code/text types"
            )
        else:
            config['interactive_file_type_includes_for_llm'] = []

        # Scan for directory names (for LLM content exclusion)
        print(f"\n--- Scanning for Directory Names (for LLM Content Exclusion) ---")
        input("Press Enter to start scan...")
        dir_names_counts = scan_directory(Path(config['root_dir']), "dir", scan_max, config['show_hidden'], verbose_log_scan, initial_scan_excludes)
        if dir_names_counts:
            # We no longer pre-select items as it's confusing, but we still show which ones are always excluded
            # The user's selections will be added to the automatic exclusions
            user_selected_dirs = general_interactive_selection(
                dir_names_counts, "directory name", "Select ADDITIONAL Directory Names to EXCLUDE from LLM Export Content:", "EXCLUDE"
            )

            # Store the user's selections in the config
            config['interactive_dir_excludes_for_llm'] = user_selected_dirs
        else:
            config['interactive_dir_excludes_for_llm'] = []
    else:
        config['interactive_file_type_includes_for_llm'] = []
        config['interactive_dir_excludes_for_llm'] = []


    # Step 3: Display Style (Tree)
    print(f"\n{Colors.BOLD}Step 3: Tree Display Style{Colors.RESET}")
    styles = TreeStyle.AVAILABLE.keys()
    style_options_display = [f"{idx+1}) {s.capitalize()}" for idx, s in enumerate(styles)]
    print("Available styles: " + ", ".join(style_options_display))
    choice = input(f"Choose style number or name [{Colors.GREEN}unicode{Colors.RESET}]: ").strip().lower()
    if choice.isdigit() and 0 < int(choice) <= len(styles):
        config['style'] = list(styles)[int(choice)-1]
    elif choice in styles:
        config['style'] = choice
    else:
        config['style'] = 'unicode'
    print(f"  Tree Style: {config['style']}")

    # Tree Depth
    max_depth_str = input(f"Max tree display depth (number, or empty for unlimited) [{Colors.GREEN}unlimited{Colors.RESET}]: ").strip()
    config['max_depth'] = int(max_depth_str) if max_depth_str.isdigit() else None

    # Show Size in Tree
    config['show_size'] = input(f"Show file sizes in tree? [y/{Colors.GREEN}N{Colors.RESET}]: ").lower() == 'y'
    config['colorize'] = input(f"Use colors in tree output? [{Colors.GREEN}Y{Colors.RESET}/n]: ").lower() not in ['n', 'no']

    # Step 4: LLM Export Specifics
    print(f"\n{Colors.BOLD}Step 4: LLM Export Configuration{Colors.RESET}")
    config['export_for_llm'] = input(f"Generate LLM export file? [y/{Colors.GREEN}N{Colors.RESET}]: ").lower() == 'y'
    if config['export_for_llm']:
        max_size_str = input(f"Max content size per file for LLM export (e.g., 50k, 1m) [{Colors.GREEN}100k{Colors.RESET}]: ").strip().lower()
        config['max_llm_file_size'] = parse_size_string(max_size_str, default=100 * 1024) if max_size_str else 100 * 1024
        print(f"  LLM Max File Size: {format_bytes(config['max_llm_file_size'])}")

        # LLM Content Extensions (CLI --llm-ext, not set interactively here beyond file type scan)
        # If user did interactive file type scan, those are in interactive_file_type_includes_for_llm
        # Otherwise, llm_content_extensions from CLI would be used, or default.
        # For interactive setup, we rely on interactive_file_type_includes_for_llm.
        config['llm_content_extensions'] = None # CLI arg, not set here

        config['output_dir'] = input(f"Directory to save LLM export (empty for current dir): ").strip() or None
        config['add_file_marker'] = input(f"Add exclusion marker to LLM export file? [{Colors.GREEN}Y{Colors.RESET}/n]: ").lower() not in ['n', 'no']

        print("LLM inclusion indicators in tree:")
        print("  (1) Show only included [LLM✓] (Default)")
        print("  (2) Show all [LLM✓/✗]")
        print("  (3) Show none")
        ind_choice = input("Choice (1-3) [1]: ").strip()
        config['llm_indicators'] = {'2': 'all', '3': 'none'}.get(ind_choice, 'included')
        print(f"  LLM Indicators: {config['llm_indicators']}")

    # Step 5: Behavior
    print(f"\n{Colors.BOLD}Step 5: Behavior Options{Colors.RESET}")
    config['verbose'] = input(f"Show verbose logs? [y/{Colors.GREEN}N{Colors.RESET}]: ").lower() == 'y'
    config['skip_errors'] = input(f"Auto-skip filesystem errors? [y/{Colors.GREEN}N{Colors.RESET}]: ").lower() == 'y'
    config['interactive_prompts'] = not config['skip_errors']

    # Summary
    print(f"\n{Colors.MAGENTA}--- Configuration Summary ---{Colors.RESET}")
    print(f"{Colors.BOLD}Directory:{Colors.RESET} {Colors.CYAN}{config['root_dir']}{Colors.RESET}")
    print(f"{Colors.BOLD}Tree Display:{Colors.RESET}")
    print(f"  Style: {config['style']}, Max Depth: {config['max_depth'] or 'Unlimited'}")
    print(f"  Show Hidden: {'Yes' if config['show_hidden'] else 'No'}, Show Sizes: {'Yes' if config['show_size'] else 'No'}, Colors: {'Yes' if config['colorize'] else 'No'}")
    print(f"{Colors.BOLD}Filtering (Tree & LLM):{Colors.RESET}")
    print(f"  Smart Exclude: {'ON' if config['use_smart_exclude'] else 'OFF'}")
    # CLI patterns are not set interactively, so they'd be empty here
    print(f"  CLI Include Patterns: {config.get('cli_include_patterns', []) or 'None'}")
    print(f"  CLI Exclude Patterns: {config.get('cli_exclude_patterns', []) or 'None'}")

    if config['export_for_llm']:
        print(f"{Colors.BOLD}LLM Export Content:{Colors.RESET}")
        print(f"  Enabled: Yes, Max File Size: {format_bytes(config['max_llm_file_size'])}")
        llm_ext_final = config.get('llm_content_extensions') # From CLI
        if not llm_ext_final and config.get('interactive_file_type_includes_for_llm'): # From interactive
            llm_ext_final = config['interactive_file_type_includes_for_llm']
        print(f"  File Types for Content: {llm_ext_final or 'Default (non-binary)'}")
        print(f"  Interactive Dir Excludes for LLM Content: {config.get('interactive_dir_excludes_for_llm', []) or 'None'}")
        print(f"  Output Directory: {config.get('output_dir') or 'Current directory'}")
        print(f"  LLM Indicators in Tree: {config['llm_indicators']}")
    else:
        print(f"{Colors.BOLD}LLM Export:{Colors.RESET} No")

    print(f"{Colors.BOLD}Behavior:{Colors.RESET}")
    print(f"  Verbose: {'Yes' if config['verbose'] else 'No'}, Skip Errors: {'Yes' if config['skip_errors'] else 'No (ask)'}")

    if input("\nPress Enter to generate with these settings, or 'q' to quit: ").lower() == 'q':
        print("Setup cancelled.")
        return {}

    save_config_choice = input(f"Save these settings (excluding directory) for future defaults? [y/{Colors.GREEN}N{Colors.RESET}]: ").lower()
    if save_config_choice == 'y':
        save_config(config) # save_config should filter what it saves
        print("Configuration saved.")

    return config