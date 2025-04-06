# -*- coding: utf-8 -*-
"""
Interactive components for IntuitiveDirTree, using the 'pick' library
for user selections (directory, filters). Also includes the main interactive
setup workflow.
"""

import sys
import os
import traceback
from pathlib import Path
from collections import Counter
from typing import Optional, List, Tuple, Dict, Any, Set, Counter as CounterType, Callable

# --- Optional Dependency: pick ---
pick: Optional[Any] = None
pick_available: bool = False
try:
    import pick
    pick_available = True
    # Basic check for curses compatibility (might not catch all issues)
    if sys.platform != 'win32':
        import curses
        curses.setupterm()
except ImportError:
    print("Warning: 'pick' library not found. Interactive selection features will be disabled.", file=sys.stderr)
    print("         Install it using: pip install pick", file=sys.stderr)
except Exception as e:
    print(f"Warning: Failed to initialize 'pick' (potential curses issue): {e}", file=sys.stderr)
    print("         Interactive selection features might be unstable or disabled.", file=sys.stderr)
    print("         On Windows, ensure 'windows-curses' is installed: pip install windows-curses", file=sys.stderr)

# --- Imports from other modules ---
try:
    from .dirtree_config import COMMON_EXCLUDES, get_default_dir, set_default_dir, DEFAULT_LLM_EXCLUDED_EXTENSIONS
    from .dirtree_scanner import scan_directory
    from .dirtree_styling import Colors, DEFAULT_FILETYPE_COLORS # For prompts
    from .dirtree_utils import format_bytes, log_message, parse_size_string # Utilities
    from . import __version__
except ImportError:
    # Fallback for direct execution or testing (less ideal)
    print("Warning: Running interactive module potentially outside of package context.", file=sys.stderr)
    # Define dummy fallbacks if needed, or rely on caller to provide them
    class Colors: RESET = ""; YELLOW = ""; GREEN = ""; CYAN = ""; BOLD = ""; RED = ""
    COMMON_EXCLUDES = []
    DEFAULT_LLM_EXCLUDED_EXTENSIONS = set()
    DEFAULT_FILETYPE_COLORS = {}
    def get_default_dir(): return None
    def set_default_dir(d): pass
    def scan_directory(*args, **kwargs): return Counter()
    def format_bytes(b): return str(b)
    def log_message(*args, **kwargs): pass
    __version__ = "?.?.?"


# --- Interactive Directory Selection ---
def select_directory_interactive(start_dir: Optional[str] = None) -> Optional[str]:
    """
    Enhanced interactive selection of a directory using the 'pick' library.
    Allows navigation up and down the directory tree with improved user guidance.

    Args:
        start_dir: The initial directory to start browsing from. Defaults to CWD.

    Returns:
        The selected directory path as a string, or None if cancelled.
    """
    if not pick_available:
        print("Interactive directory selection unavailable ('pick' library missing or failed to load).")
        return None

    try:
        current_dir = Path(start_dir).resolve() if start_dir else Path.cwd()
    except Exception as e:
        print(f"Error resolving start directory '{start_dir or 'CWD'}': {e}")
        return None

    # Remember visited paths to allow quick navigation back
    visited_paths = []
    
    # Show initial help message
    print(f"\n{Colors.CYAN}Directory Browser Instructions:{Colors.RESET}")
    print(f"- Use {Colors.BOLD}arrow keys{Colors.RESET} to navigate the list")
    print(f"- Press {Colors.BOLD}Enter{Colors.RESET} to go into a directory or select an option")
    print(f"- Select {Colors.BOLD}'✅ Select Current...'{Colors.RESET} when you've found the directory you want")
    print(f"- Press {Colors.BOLD}Ctrl+C{Colors.RESET} to cancel at any time\n")
    
    try:
        while True:
            parent_option = ("⬆️ .. (Parent Directory)", str(current_dir.parent))
            
            # Add quick navigation options if we have history
            history_options = []
            if visited_paths:
                history_options.append(("⏪ Back (Previous Directory)", "BACK"))
            
            try:
                # List directories, handling potential errors
                dirs = sorted(
                    [(f"📂 {d.name}", str(d)) for d in current_dir.iterdir() if d.is_dir()],
                    key=lambda x: x[0].lower() # Case-insensitive sort
                )
            except Exception as e:
                print(f"\n{Colors.RED}Error listing directory '{current_dir}': {e}{Colors.RESET}")
                options = [parent_option] + history_options + [("❌ Cancel Selection", None)]
                title = f"Error listing '{current_dir.name}'. Go up, back, or cancel?"
                picker = pick.Picker(options, title, indicator='=>', min_selection_count=1)
                selected = picker.start() # Returns (option, index)
                if not selected or selected[0][1] is None: 
                    return None # Cancel
                elif selected[0][1] == "BACK" and visited_paths:
                    current_dir = visited_paths.pop() # Go back
                else:
                    # Add current to history before going up
                    visited_paths.append(current_dir)
                    current_dir = Path(selected[0][1]) # Go up
                continue

            options = [parent_option] + history_options + dirs
            options.append((f"✅ Select Current: '{current_dir.name}'", str(current_dir)))
            
            # Count files to provide info
            try:
                file_count = sum(1 for _ in current_dir.glob('*') if _.is_file())
                dir_count = sum(1 for _ in current_dir.glob('*') if _.is_dir())
                size_info = f"({dir_count} directories, {file_count} files)"
            except Exception:
                size_info = ""

            title = f"Directory Browser - Currently In: {current_dir} {size_info}\n" \
                    f"Controls: ↑/↓: Navigate | Enter: Select | Esc/Ctrl+C: Cancel\n" \
                    f"Select '✅ Select Current...' when you've found the directory you want"

            picker = pick.Picker(options, title, indicator='=>', min_selection_count=1)
            selected_option, _ = picker.start() # Throws exception on ESC/Ctrl+C

            selected_text, selected_path_str = selected_option

            if selected_text.startswith("⬆️"):
                # Add current to history before going up
                visited_paths.append(current_dir)
                current_dir = Path(selected_path_str) # Navigate up
            elif selected_text.startswith("⏪") and selected_path_str == "BACK":
                current_dir = visited_paths.pop()  # Go back to previous directory
            elif selected_text.startswith("✅"):
                return selected_path_str # Confirm current directory
            else:
                # Add current to history before navigating into subdirectory
                visited_paths.append(current_dir)
                # Navigate into selected directory
                current_dir = Path(selected_path_str)

    except (KeyboardInterrupt, Exception) as e:
        print("\nDirectory selection cancelled.")
        if not isinstance(e, KeyboardInterrupt):
            print(f"Error: {e}")
        return None


# --- Simpler Alternative Without Using mark_index ---
def simple_interactive_selection(
    items_counter: CounterType[str],
    item_type_label: str,
    prompt_title: str,
    include_mode: bool = True,
    preselected: Optional[List[str]] = None
) -> List[str]:
    """An improved version of interactive selection that adds more user guidance."""
    if not pick_available:
        print(f"Interactive {item_type_label} selection unavailable ('pick' library missing or failed to load).")
        return []
    if not items_counter:
        print(f"No {item_type_label}s found to select.")
        return []

    preselected = preselected or []
    preselected_set = set(preselected)

    # Sort items by count (most common first), then alphabetically
    sorted_items = sorted(items_counter.items(), key=lambda item: (-item[1], item[0]))

    # Add preselection indicator to options
    options = []
    for name, count in sorted_items:
        is_preselected = name in preselected_set
        prefix = "✓ " if is_preselected else "  "
        options.append((f"{prefix}{name} ({count})", name))

    # Add "Select All" / "Select None" options based on mode
    action_word = "Include" if include_mode else "Exclude"
    options.insert(0, (f"✅ Select ALL {item_type_label}s", "__ALL__"))
    options.insert(1, (f"❌ Select NONE ({action_word} nothing)", "__NONE__"))
    
    # Add recommended/common types option if we're including
    if include_mode and item_type_label == "file type":
        # Create a set of common code and text extensions
        common_code_exts = {"py", "js", "ts", "jsx", "tsx", "java", "c", "cpp", "cs", "go", 
                           "rb", "php", "html", "css", "scss", "json", "yaml", "yml", 
                           "xml", "md", "txt", "rst", "toml", "ini", "sh", "bat"}
        
        # Only offer this option if some common types were found
        found_common = any(name in common_code_exts for name, _ in sorted_items)
        if found_common:
            options.insert(2, (f"🔍 Select COMMON code/text types (recommended)", "__COMMON__"))

    # Enhanced title with instructions
    enhanced_title = f"{prompt_title}\n\nControls: ↑/↓: Navigate | Space: Toggle Selection | Enter: Confirm\n\nTip: Selecting '✅ ALL', '❌ NONE', or '🔍 COMMON' can save time."

    # Run the picker without manual preselection
    try:
        picker = pick.Picker(
            options,
            enhanced_title,
            indicator='*',
            multiselect=True,
            default_index=0
        )
        selected = picker.start()
    except (KeyboardInterrupt, Exception) as e:
        print(f"\n{item_type_label.capitalize()} selection cancelled or failed.")
        if not isinstance(e, KeyboardInterrupt):
            print(f"Error: {e}")
        return preselected  # Return original preselection on cancellation/error

    # Process selections
    selected_names = []
    has_all = any(option[1] == "__ALL__" for option in selected)
    has_none = any(option[1] == "__NONE__" for option in selected)
    has_common = any(option[1] == "__COMMON__" for option in selected)
    
    # Extract regular selections
    for option_info in selected:
        option_tuple = option_info[0]  # Get the tuple from the selection
        option_value = option_tuple[1]  # Get the second element (value)
        if option_value not in ("__ALL__", "__NONE__", "__COMMON__"):
            selected_names.append(option_value)
    
    # Handle special cases
    if has_all and has_none:
        print(f"Warning: Both 'Select ALL' and 'Select NONE' chosen. Interpreting as 'Select ALL'.")
        has_none = False
        
    if has_all:
        selected_names = [name for name, _ in sorted_items]
        print(f"Selected ALL {len(selected_names)} {item_type_label}s.")
    elif has_none:
        selected_names = []
        print(f"Selected NONE.")
    elif has_common and item_type_label == "file type":
        common_code_exts = {"py", "js", "ts", "jsx", "tsx", "java", "c", "cpp", "cs", "go", 
                           "rb", "php", "html", "css", "scss", "json", "yaml", "yml", 
                           "xml", "md", "txt", "rst", "toml", "ini", "sh", "bat"}
        selected_names = [name for name, _ in sorted_items if name in common_code_exts]
        if not selected_names:
            selected_names = [name for name, _ in sorted_items 
                             if name not in DEFAULT_LLM_EXCLUDED_EXTENSIONS][:10]
        print(f"Selected {len(selected_names)} common code/text {item_type_label}s:")
        print(f"  {', '.join(selected_names[:10])}{' and more...' if len(selected_names) > 10 else ''}")
    else:
        print(f"Selected {len(selected_names)} {item_type_label}s: {', '.join(selected_names[:10]) if selected_names else 'None'}{' and more...' if len(selected_names) > 10 else ''}")
        
    return selected_names

# --- Interactive Setup Workflow ---
def run_interactive_setup() -> Dict[str, Any]:
    """
    Guides the user through setting up the directory tree generation options interactively.

    Returns:
        A dictionary containing the configured options, compatible with IntuitiveDirTree constructor.
        Returns an empty dict if setup is cancelled.
    """
    print(f"\n--- {Colors.BOLD}IntuitiveDirTree v{__version__} Interactive Setup{Colors.RESET} ---")

    config: Dict[str, Any] = {}
    current_dir = Path.cwd()
    default_dir = get_default_dir()

    # --- 1. Directory Selection ---
    print(f"\n{Colors.BOLD}Step 1: Directory Selection{Colors.RESET}")
    current_dir = Path.cwd()
    default_dir = get_default_dir()
    
    # Show available directories
    print(f"Available directories:")
    print(f"  1) Current directory: {Colors.CYAN}{current_dir}{Colors.RESET}")
    
    if default_dir:
        print(f"  2) Default directory: {Colors.CYAN}{default_dir}{Colors.RESET}")
        print(f"  3) Select interactively (browse file system)")
        print(f"  4) Enter a path manually")
        prompt = f"Choose option [1-4]: "
        
        valid_choice = False
        while not valid_choice:
            choice = input(prompt).strip()
            if choice == '1' or not choice:  # Current dir as fallback
                config['root_dir'] = str(current_dir)
                print(f"Using current directory: {Colors.CYAN}{config['root_dir']}{Colors.RESET}")
                valid_choice = True
            elif choice == '2':  # Default dir
                config['root_dir'] = default_dir
                print(f"Using default directory: {Colors.CYAN}{config['root_dir']}{Colors.RESET}")
                valid_choice = True
            elif choice == '3':  # Interactive
                print(f"\nLaunching interactive directory browser...")
                print(f"Use arrow keys to navigate, Enter to select directory, Space to confirm selection")
                selected_dir_str = select_directory_interactive(start_dir=str(default_dir or current_dir))
                if selected_dir_str is None:
                    print("Setup cancelled during directory selection.")
                    return {}
                config['root_dir'] = selected_dir_str
                print(f"Selected directory: {Colors.CYAN}{config['root_dir']}{Colors.RESET}")
                valid_choice = True
                
                # Ask to set as default only if a new dir was selected
                if str(Path(config['root_dir']).resolve()) != str(default_dir):
                    prompt = f"Set '{config['root_dir']}' as default for future runs? [y/{Colors.GREEN}N{Colors.RESET}]: "
                    if input(prompt).strip().lower() in ['y', 'yes']:
                        set_default_dir(config['root_dir'])
                        print("Default directory saved.")
            elif choice == '4':  # Manual entry
                manual_path = input("Enter directory path: ").strip()
                try:
                    path_obj = Path(manual_path).resolve(strict=True)
                    if not path_obj.is_dir():
                        print(f"{Colors.RED}Error: Not a directory{Colors.RESET}")
                        continue
                    config['root_dir'] = str(path_obj)
                    print(f"Using directory: {Colors.CYAN}{config['root_dir']}{Colors.RESET}")
                    valid_choice = True
                    
                    # Ask to set as default
                    prompt = f"Set '{config['root_dir']}' as default for future runs? [y/{Colors.GREEN}N{Colors.RESET}]: "
                    if input(prompt).strip().lower() in ['y', 'yes']:
                        set_default_dir(config['root_dir'])
                        print("Default directory saved.")
                except (FileNotFoundError, NotADirectoryError):
                    print(f"{Colors.RED}Error: Directory does not exist{Colors.RESET}")
                except Exception as e:
                    print(f"{Colors.RED}Error: {e}{Colors.RESET}")
            else:
                print(f"{Colors.RED}Invalid choice. Please enter 1-4.{Colors.RESET}")
    else:
        # No default directory available
        print(f"  2) Select interactively (browse file system)")
        print(f"  3) Enter a path manually")
        prompt = f"Choose option [1-3]: "
        
        valid_choice = False
        while not valid_choice:
            choice = input(prompt).strip()
            if choice == '1' or not choice:  # Current dir as fallback
                config['root_dir'] = str(current_dir)
                print(f"Using current directory: {Colors.CYAN}{config['root_dir']}{Colors.RESET}")
                valid_choice = True
            elif choice == '2':  # Interactive
                print(f"\nLaunching interactive directory browser...")
                print(f"Use arrow keys to navigate, Enter to select directory, Space to confirm selection")
                selected_dir_str = select_directory_interactive(start_dir=str(current_dir))
                if selected_dir_str is None:
                    print("Setup cancelled during directory selection.")
                    return {}
                config['root_dir'] = selected_dir_str
                print(f"Selected directory: {Colors.CYAN}{config['root_dir']}{Colors.RESET}")
                valid_choice = True
                
                # Ask to set as default
                prompt = f"Set '{config['root_dir']}' as default for future runs? [y/{Colors.GREEN}N{Colors.RESET}]: "
                if input(prompt).strip().lower() in ['y', 'yes']:
                    set_default_dir(config['root_dir'])
                    print("Default directory saved.")
            elif choice == '3':  # Manual entry
                manual_path = input("Enter directory path: ").strip()
                try:
                    path_obj = Path(manual_path).resolve(strict=True)
                    if not path_obj.is_dir():
                        print(f"{Colors.RED}Error: Not a directory{Colors.RESET}")
                        continue
                    config['root_dir'] = str(path_obj)
                    print(f"Using directory: {Colors.CYAN}{config['root_dir']}{Colors.RESET}")
                    valid_choice = True
                    
                    # Ask to set as default
                    prompt = f"Set '{config['root_dir']}' as default for future runs? [y/{Colors.GREEN}N{Colors.RESET}]: "
                    if input(prompt).strip().lower() in ['y', 'yes']:
                        set_default_dir(config['root_dir'])
                        print("Default directory saved.")
                except (FileNotFoundError, NotADirectoryError):
                    print(f"{Colors.RED}Error: Directory does not exist{Colors.RESET}")
                except Exception as e:
                    print(f"{Colors.RED}Error: {e}{Colors.RESET}")
            else:
                print(f"{Colors.RED}Invalid choice. Please enter 1-3.{Colors.RESET}")


    # --- 2. Filtering ---
    print(f"\n{Colors.BOLD}Step 2: Filtering Options{Colors.RESET}")
    print("This step determines which files and directories appear in the tree visualization.")
    
    # Smart Exclude
    print(f"\n{Colors.BOLD}Smart Exclude:{Colors.RESET} Automatically hide common non-essential directories")
    print(f"Examples: .git, node_modules, __pycache__, etc.")
    prompt = f"Use Smart Exclude? (Recommended) [{Colors.GREEN}Y{Colors.RESET}/n]: "
    use_smart = input(prompt).strip().lower() not in ['n', 'no']
    config['use_smart_exclude'] = use_smart
    print(f"  Smart Exclude: {'ON' if use_smart else 'OFF'}")

    # Show Hidden
    print(f"\n{Colors.BOLD}Hidden Items:{Colors.RESET} Files and directories that start with a dot (.)")
    prompt = f"Show hidden items? [y/{Colors.GREEN}N{Colors.RESET}]: "
    show_hidden = input(prompt).strip().lower() in ['y', 'yes']
    config['show_hidden'] = show_hidden
    print(f"  Show Hidden: {'Yes' if show_hidden else 'No'}")

    # Interactive Scan & Filter
    final_include_patterns: List[str] = []
    final_exclude_patterns: List[str] = list(COMMON_EXCLUDES) if use_smart else [] # Start with smart excludes if enabled

    print(f"\n{Colors.BOLD}Interactive Filtering:{Colors.RESET} Scan directory to select specific file types/directories")
    print("This helps you control which files appear in the tree visualization and LLM export.")
    prompt = f"Use interactive filtering? [y/{Colors.GREEN}N{Colors.RESET}]: "
    if input(prompt).strip().lower() in ['y', 'yes']:
            scan_max = 20000 # Increased max items to scan for discovery
            
            # Create a verbose logger for the scan function
            verbose_log = lambda msg, lvl: log_message(msg, level=lvl, verbose=True, colorize=True)
            current_excludes = config.get('exclude_patterns', []) # Get current excludes from config
            
            print("\n--- Scanning Directory Contents ---")
            print(f"Scanning for file types in '{config['root_dir']}'...")
            print(f"This will help you select which file types to include in the tree and export.")
            print(f"Scanning will analyze up to {scan_max} items.")
            print(f"{Colors.YELLOW}Note: When the file type selection screen appears, use:{Colors.RESET}")
            print(f"  {Colors.CYAN}↑/↓ arrow keys{Colors.RESET} to navigate")
            print(f"  {Colors.CYAN}Space{Colors.RESET} to select/deselect items")
            print(f"  {Colors.CYAN}Enter{Colors.RESET} to confirm your selection")
            print(f"Press Ctrl+C to skip this step if scanning takes too long.")
            
            try:
                file_types = scan_directory(Path(config['root_dir']), "file", scan_max, show_hidden, verbose_log, initial_exclude_patterns=current_excludes)
                print(f"\rScan complete. Found {len(file_types)} unique file types.")
                
                if file_types:
                    print(f"\nFound file types with counts:")
                    for ext, count in sorted(file_types.items(), key=lambda x: (-x[1], x[0]))[:15]:
                        # Use color coding from the filetype colors if available
                        color = DEFAULT_FILETYPE_COLORS.get(ext, Colors.WHITE)
                        print(f"  {color}{ext}{Colors.RESET}: {count} files")
                    if len(file_types) > 15:
                        print(f"  ... and {len(file_types) - 15} more types")
                        
                    print(f"\n{Colors.BOLD}File Type Selection:{Colors.RESET}")
                    print(f"The selection interface will now open.")
                    print(f"It's recommended to select the 'COMMON code/text types' option for most use cases.")
                    input(f"Press Enter to continue to selection screen...")
                    
                    # Use the simpler selection function
                    selected_includes = simple_interactive_selection(
                        file_types, "file type",
                        "Select File Types to INCLUDE (Space toggles, Enter confirms):",
                        include_mode=True
                    )
                    # Convert selected extensions to glob patterns
                    final_include_patterns.extend([f"*.{ext}" for ext in selected_includes if ext != "(no ext)"])
                    if "(no ext)" in selected_includes:
                        final_include_patterns.append("*") # Or a more specific pattern if desired
            except KeyboardInterrupt:
                print("\nFile type scanning skipped.")
    
            try:
                print("\n--- Directory Scan ---")
                print(f"Scanning for directory names in '{config['root_dir']}'...")
                print(f"This will help you select directories to exclude from the tree and export.")
                print(f"When the selection screen appears, use the same controls as before.")
                input(f"Press Enter to continue scanning...")
                
                # Use the same excludes fetched before
                dir_names = scan_directory(Path(config['root_dir']), "dir", scan_max, show_hidden, verbose_log, initial_exclude_patterns=current_excludes)
                print(f"\rScan complete. Found {len(dir_names)} unique directory names.")
                
                if dir_names:
                    print(f"\nFound directory names with counts:")
                    for name, count in sorted(dir_names.items(), key=lambda x: (-x[1], x[0]))[:15]:
                        print(f"  {name}: {count} occurrences")
                    if len(dir_names) > 15:
                        print(f"  ... and {len(dir_names) - 15} more directories")
                        
                    # Preselect common directories to exclude
                    common_dirs_to_exclude = {'node_modules', 'dist', 'build', '__pycache__', '.git', 'venv', '.venv'}
                    preselected = [name for name in dir_names if name in common_dirs_to_exclude]
                    
                    print(f"\n{Colors.BOLD}Directory Exclusion Selection:{Colors.RESET}")
                    print(f"Select directories to EXCLUDE from the tree visualization.")
                    print(f"Common build and cache directories are pre-selected for exclusion.")
                    input(f"Press Enter to continue to selection screen...")
                    
                    # Use the simpler selection function
                    selected_excludes = simple_interactive_selection(
                        dir_names, "directory name",
                        "Select Directory Names to EXCLUDE (Space toggles, Enter confirms):",
                        include_mode=False,
                        preselected=preselected
                    )
                    # Add selected directory names directly as exclude patterns
                    final_exclude_patterns.extend(selected_excludes)
            except KeyboardInterrupt:
                print("\nDirectory scanning skipped.")

    # --- 3. Display Style ---
    print(f"\n{Colors.BOLD}Step 3: Display Style{Colors.RESET}")
    print("Choose how the directory tree will be displayed in the terminal.")
    
    available_styles = ["unicode", "ascii", "bold", "rounded", "emoji", "minimal"]
    
    print(f"\n{Colors.BOLD}Style Options:{Colors.RESET}")
    print(f"  unicode: │   ├── └── (Standard tree, works on most terminals)")
    print(f"  ascii:   |   |-- `-- (Compatible with all terminals)")
    print(f"  bold:    ┃   ┣━━ ┗━━ (Thicker lines)")
    print(f"  rounded: │   ├── ╰── (Rounded corners)")
    print(f"  emoji:   ┃   📄  📂  (With file/folder emojis)")
    print(f"  minimal: -   -   -   (Simple, clean format)")
    
    style = input(f"Enter desired style [{Colors.GREEN}unicode{Colors.RESET}]: ").strip().lower()
    if style not in available_styles:
        print(f"Invalid style, using default: unicode.")
        style = "unicode"
    config['style'] = style

    print(f"\n{Colors.BOLD}Tree Depth:{Colors.RESET} Maximum directory depth to display")
    print("(Use a number to limit depth, or leave empty for unlimited)")
    max_depth_str = input(f"Max display depth [{Colors.GREEN}unlimited{Colors.RESET}]: ").strip()
    config['max_depth'] = int(max_depth_str) if max_depth_str.isdigit() else None

    print(f"\n{Colors.BOLD}File Size Display:{Colors.RESET} Show size of each file in the tree")
    show_size = input(f"Show file sizes? [y/{Colors.GREEN}N{Colors.RESET}]: ").strip().lower() in ['y', 'yes']
    config['show_size'] = show_size

    print(f"\n{Colors.BOLD}Color Output:{Colors.RESET} Use ANSI colors in the tree display")
    use_colors = input(f"Use colors in output? [{Colors.GREEN}Y{Colors.RESET}/n]: ").strip().lower() not in ['n', 'no']
    config['colorize'] = use_colors

    # --- 4. LLM Export ---
    print(f"\n{Colors.BOLD}Step 4: LLM Export Settings{Colors.RESET}")
    print("The LLM export creates a Markdown file with the directory structure and file contents.")
    print("This is useful for uploading to an LLM (like Claude) to discuss your codebase.")
    
    export_llm = input(f"Generate LLM export? [y/{Colors.GREEN}N{Colors.RESET}]: ").strip().lower() in ['y', 'yes']
    config['export_for_llm'] = export_llm
    
    if export_llm:
        print(f"\n{Colors.BOLD}Content Size Limit:{Colors.RESET} Maximum size per file in the export")
        print("Large files will be truncated to this size. Default: 100k (~100KB)")
        max_size_str = input(f"Max content size per file (e.g., 50k, 1m) [{Colors.GREEN}100k{Colors.RESET}]: ").strip().lower()
        max_size = parse_size_string(max_size_str) if max_size_str else 100*1024
        config['max_llm_file_size'] = max_size
        print(f"  Max content size set to: {format_bytes(config['max_llm_file_size'])}")

        print(f"\n{Colors.BOLD}File Types for Content:{Colors.RESET} Which file types to include content for")
        print("  (1) Default (common text/code files, skip binaries like images/zips) [Recommended]")
        print("  (2) Specify allowed extensions manually")
        print("  (3) Use the same file types selected for tree display (if any)")
        
        choice = input(f"Choice (1-3, default: 1): ").strip()
        
        if choice == '2':
            ext_str = input("  Enter allowed extensions (comma-separated, e.g., py,js,txt): ").strip().lower()
            config['llm_content_extensions'] = [e.strip().lstrip('.') for e in ext_str.split(',') if e.strip()]
            print(f"  Using specified extensions: {config['llm_content_extensions']}")
        elif choice == '3' and final_include_patterns:
            # Extract extensions from include patterns that look like *.ext
            extensions = []
            for pattern in final_include_patterns:
                if pattern.startswith('*.'):
                    ext = pattern[2:].strip()
                    if ext:
                        extensions.append(ext)
            if extensions:
                config['llm_content_extensions'] = extensions
                print(f"  Using extensions from tree include patterns: {extensions}")
            else:
                config['llm_content_extensions'] = None
                print("  No valid extensions found in tree patterns, using default filtering.")
        else:
            config['llm_content_extensions'] = None # Use default logic in main class
            print("  Using default LLM content filtering (common text/code files).")
            
        print(f"\n{Colors.BOLD}Export Location:{Colors.RESET} Where to save the generated file")
        custom_dir = input(f"Custom output directory (leave empty for current dir): ").strip()
        if custom_dir:
            config['output_dir'] = custom_dir
            print(f"  Export will be saved to: {custom_dir}")
        else:
            config['output_dir'] = None
            print(f"  Export will be saved to the current directory")

        print(f"\n{Colors.BOLD}LLM Export Indicators:{Colors.RESET} Control how LLM file inclusion is shown in the tree")
        print("  (1) Show indicators only for included files [LLM✓] (Default)")
        print("  (2) Show indicators for both included [LLM✓] and excluded [LLM✗] files")
        print("  (3) Don't show any LLM indicators")
        
        choice = input(f"Choice (1-3, default: 1): ").strip()
        
        if choice == '2':
            config['llm_indicators'] = 'all'
            print("  Showing all LLM inclusion indicators")
        elif choice == '3':
            config['llm_indicators'] = 'none'
            print("  Hiding all LLM indicators")
        else:
            config['llm_indicators'] = 'included'
            print("  Showing indicators only for included files")

    # --- 5. Behavior ---
    print(f"\n{Colors.BOLD}Step 5: Behavior{Colors.RESET}")
    print("Configure additional behavior options for the tool.")
    
    verbose = input(f"Show verbose logs during generation? [y/{Colors.GREEN}N{Colors.RESET}]: ").strip().lower() in ['y', 'yes']
    config['verbose'] = verbose

    print(f"\n{Colors.BOLD}Error Handling:{Colors.RESET} How to handle errors like permission denied")
    skip_errors = input(f"Auto-skip errors without asking? [y/{Colors.GREEN}N{Colors.RESET}]: ").strip().lower() in ['y', 'yes']
    config['skip_errors'] = skip_errors
    # Interactive prompts are implicitly True unless skip_errors is True
    config['interactive_prompts'] = not skip_errors

    # --- Summary ---
    print(f"\n--- {Colors.BOLD}Summary{Colors.RESET} ---")
    print(f"Directory: {Colors.CYAN}{config['root_dir']}{Colors.RESET}")
    print("Filters:")
    inc_p = config.get('include_patterns')
    print(f"  Include Patterns: {inc_p if inc_p else '*(All files not excluded)'}")
    exc_p = config.get('exclude_patterns')
    print(f"  Exclude Patterns: {exc_p if exc_p else 'None'}")
    print(f"  (Smart Exclude: {'ON' if config.get('use_smart_exclude') else 'OFF'})")
    print(f"  Show Hidden: {'Yes' if config.get('show_hidden') else 'No'}")
    print("Display:")
    print(f"  Style: {config.get('style', 'unicode')}")
    print(f"  Max Depth: {config.get('max_depth') or 'Unlimited'}")
    print(f"  Show Size: {'Yes' if config.get('show_size') else 'No'}")
    print(f"  Color: {'Yes' if config.get('colorize') else 'No'}")
    if config.get('export_for_llm'):
        print("LLM Export: Yes")
        print(f"  Max Content Size: {format_bytes(config.get('max_llm_file_size', 100*1024))}")
        llm_ext = config.get('llm_content_extensions')
        print(f"  Content File Types: {llm_ext if llm_ext is not None else 'Default (non-binary)'}")
        print(f"  Output Directory: {config.get('output_dir') or 'Current directory'}")
        llm_ind = config.get('llm_indicators', 'included')
        print(f"  Indicators: {'All (included & excluded)' if llm_ind == 'all' else 'Included files only' if llm_ind == 'included' else 'None'}")
    else:
        print("LLM Export: No")
    print("Behavior:")
    print(f"  Verbose Logging: {'Yes' if config.get('verbose') else 'No'}")
    print(f"  Handle Errors: {'Skip automatically' if config.get('skip_errors') else 'Ask interactively'}")

    # --- Confirmation ---
    confirm = input("\nPress Enter to generate the tree with these settings, or 'q' to quit: ").strip().lower()
    if confirm == 'q':
        print("Setup cancelled.")
        return {}

    return config