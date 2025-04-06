# -*- coding: utf-8 -*-
"""
Command-line interface (CLI) for IntuitiveDirTree.
Handles argument parsing and orchestrates the tree generation process.
"""

import sys
import argparse
from pathlib import Path
import traceback

# --- Imports from other modules ---
try:
    # Use relative imports assuming execution via the main script or as a package
    from . import __version__
    from .dirtree_core import IntuitiveDirTree
    from .dirtree_interactive import run_interactive_setup, pick_available
    from .dirtree_config import COMMON_EXCLUDES # Needed for argparse help
    from .dirtree_styling import TreeStyle, Colors # For help messages
    from .dirtree_utils import format_bytes, parse_size_string # Utilities
except ImportError as e:
    print(f"Error importing dirtree modules: {e}", file=sys.stderr)
    print("Please ensure you are running this from the correct directory or have installed the package.", file=sys.stderr)
    # Define dummy fallbacks to allow argparse setup at least
    __version__ = "?.?.?"
    class IntuitiveDirTree: pass
    def run_interactive_setup(): return {}
    pick_available = False
    COMMON_EXCLUDES = []
    class TreeStyle: AVAILABLE = {}
    class Colors: RESET = ""; BOLD = ""; GREEN = ""; YELLOW = ""; RED = ""
    # Exit if imports fail, as the script cannot function
    sys.exit(1)

# --- Argument Parsing ---
def parse_args() -> argparse.Namespace:
    """Parses command-line arguments."""
    parser = argparse.ArgumentParser(
        description=f"IntuitiveDirTree v{__version__} - Generate directory trees with advanced filtering and LLM export.",
        formatter_class=argparse.RawTextHelpFormatter # Preserve formatting in help
    )

    # --- Positional Argument ---
    parser.add_argument(
        'directory',
        nargs='?', # Optional: If not provided, interactive setup or default might be used
        default=None, # Default to None, handle logic in main()
        help="The root directory to generate the tree from.\nIf omitted, attempts interactive selection or uses the current directory."
    )

    # --- Interactive Mode ---
    parser.add_argument(
        '-i', '--interactive',
        action='store_true',
        help=f"Force interactive setup mode, even if a directory is provided.\n({Colors.YELLOW}Recommended for first-time users{Colors.RESET})" if pick_available else f"Force interactive setup mode.\n({Colors.RED}Requires 'pick' library - NOT FOUND{Colors.RESET})"
    )

    # --- Filtering Group ---
    filter_group = parser.add_argument_group('Filtering Options')
    filter_group.add_argument(
        '-I', '--include',
        action='append',
        metavar='PATTERN',
        default=[],
        help="Glob patterns for files to include (e.g., '*.py', 'src/**/*.js').\nCan be used multiple times. If omitted, all non-excluded files are listed."
    )
    filter_group.add_argument(
        '-E', '--exclude',
        action='append',
        metavar='PATTERN',
        default=[],
        help="Glob patterns for files/directories to exclude (e.g., '*.log', 'temp/').\nCan be used multiple times. Applied after smart excludes."
    )
    smart_exclude_parser = filter_group.add_mutually_exclusive_group()
    smart_exclude_parser.add_argument(
        '--smart-exclude',
        action='store_true',
        dest='use_smart_exclude', # Set dest explicitly
        default=True, # Default is ON
        help="Automatically exclude common clutter like .git, node_modules, etc. (Default: ON)"
    )
    smart_exclude_parser.add_argument(
        '--no-smart-exclude',
        action='store_false',
        dest='use_smart_exclude', # Set dest explicitly
        help="Disable automatic exclusion of common clutter."
    )
    filter_group.add_argument(
        '-H', '--hidden',
        action='store_true',
        default=False,
        help="Show hidden files and directories (those starting with '.')."
    )

    # --- Display Group ---
    display_group = parser.add_argument_group('Display Options')
    display_group.add_argument(
        '-s', '--style',
        default='unicode',
        choices=list(TreeStyle.AVAILABLE.keys()),
        help=f"Tree drawing style (Default: unicode).\nAvailable: {', '.join(TreeStyle.AVAILABLE.keys())}"
    )
    display_group.add_argument(
        '-d', '--max-depth',
        type=int,
        metavar='N',
        default=None,
        help="Maximum depth to display (Default: unlimited)."
    )
    display_group.add_argument(
        '--size',
        action='store_true',
        default=False,
        help="Show file sizes."
    )
    color_parser = display_group.add_mutually_exclusive_group()
    color_parser.add_argument(
        '--color',
        action='store_true',
        dest='colorize', # Explicit dest
        default=sys.stdout.isatty(), # Default based on TTY
        help="Force colorized output (Default: auto-detect based on TTY)."
    )
    color_parser.add_argument(
        '--no-color',
        action='store_false',
        dest='colorize', # Explicit dest
        help="Disable colorized output."
    )

    # --- LLM Export Group ---
    llm_group = parser.add_argument_group('LLM Export Options')
    llm_group.add_argument(
        '-L', '--llm',
        action='store_true',
        dest='export_for_llm',
        default=False,
        help="Generate a Markdown export with structure and file content suitable for LLMs."
    )
    llm_group.add_argument(
        '--llm-max-size',
        type=str, # Parse as string first
        metavar='SIZE',
        default='100k',
        help="Maximum content size per file for LLM export (e.g., 50k, 1m). (Default: 100k)"
    )
    llm_group.add_argument(
        '--llm-indicators',
        choices=['all', 'included', 'none'],
        default='included',
        help="Control LLM inclusion indicators: 'all' shows both included/excluded, 'included' only shows included files, 'none' hides all indicators (Default: included)"
    )
    llm_group.add_argument(
        '--llm-ext',
        action='append',
        metavar='EXT',
        default=None, # None means use default logic
        help="Specify file extensions (without '.') to include content for in LLM export.\nOverrides default logic. Can be used multiple times (e.g., --llm-ext py --llm-ext js)."
    )
    llm_group.add_argument(
        '--llm-output-dir',
        type=str,
        metavar='DIR',
        default=None,
        help="Directory to save the LLM export file (Default: current directory)."
    )

    # --- Behavior Group ---
    behavior_group = parser.add_argument_group('Behavior Options')
    behavior_group.add_argument(
        '-v', '--verbose',
        action='store_true',
        default=False,
        help="Show verbose logging messages during processing."
    )
    error_parser = behavior_group.add_mutually_exclusive_group()
    error_parser.add_argument(
        '--skip-errors',
        action='store_true',
        dest='skip_errors', # Explicit dest
        default=False,
        help="Automatically skip filesystem errors (like permission denied) without prompting."
    )
    error_parser.add_argument(
        '--ask-errors', # More explicit than relying on default
        action='store_false',
        dest='skip_errors', # Explicit dest
        help="Prompt user interactively when filesystem errors occur (Default)."
    )

    # --- Other ---
    parser.add_argument(
        '--version',
        action='version',
        version=f'IntuitiveDirTree v{__version__}'
    )

    # Hidden debug option
    parser.add_argument(
        '--debug',
        action='store_true',
        help=argparse.SUPPRESS  # Hide from help
    )

    return parser.parse_args()

# --- Main Execution Logic ---
def main():
    """Main function to run the directory tree generator."""
    try:
        args = parse_args()
        config = {}
        
        # Show version info
        if args.debug:
            print(f"IntuitiveDirTree v{__version__}")
            print(f"Python: {sys.version}")
            print(f"Interactive mode available: {pick_available}")

        # --- Determine Configuration (Interactive vs. Args) ---
        # Force interactive if -i is used, or if no directory is given and pick is available
        use_interactive = args.interactive or (args.directory is None and pick_available)

        if use_interactive:
            if not pick_available:
                 print(f"{Colors.RED}Error: Interactive mode requires the 'pick' library, which is not installed or failed to load.{Colors.RESET}", file=sys.stderr)
                 print("Please install it: pip install pick", file=sys.stderr)
                 if sys.platform == 'win32':
                     print("On Windows, also ensure 'windows-curses' is installed: pip install windows-curses", file=sys.stderr)
                 sys.exit(1)

            print("Launching interactive setup...")
            try:
                config = run_interactive_setup()
                if not config: # Setup was cancelled
                    sys.exit(0)
            except Exception as e_interactive:
                print(f"\n{Colors.RED}An error occurred during interactive setup:{Colors.RESET}")
                print(traceback.format_exc())
                sys.exit(1)

        else:
            # --- Use Command-Line Arguments ---
            if args.directory is None:
                # No directory given, interactive not forced, and pick not available/chosen
                print(f"{Colors.RED}Error: No directory specified.{Colors.RESET}", file=sys.stderr)
                print("Provide a directory path or use interactive mode (-i).", file=sys.stderr)
                sys.exit(1)

            config['root_dir'] = args.directory
            config['style'] = args.style
            config['max_depth'] = args.max_depth
            config['show_hidden'] = args.hidden
            config['colorize'] = args.colorize
            config['show_size'] = args.size

            # Combine smart excludes and manual excludes
            exclude_patterns = list(args.exclude) # Start with manual excludes
            if args.use_smart_exclude:
                # Append smart excludes
                exclude_patterns.extend(COMMON_EXCLUDES)
            config['include_patterns'] = args.include
            config['exclude_patterns'] = exclude_patterns
            config['use_smart_exclude'] = args.use_smart_exclude # Store the setting

            config['export_for_llm'] = args.export_for_llm
            if config['export_for_llm']:
                try:
                    config['max_llm_file_size'] = parse_size_string(args.llm_max_size)
                except ValueError as e_size:
                     print(f"{Colors.RED}Error: Invalid LLM max size format '{args.llm_max_size}'. {e_size}{Colors.RESET}", file=sys.stderr)
                     sys.exit(1)
                config['llm_content_extensions'] = args.llm_ext # Pass list or None
                config['llm_indicators'] = args.llm_indicators # Pass LLM indicators setting
                
                # Set output directory if specified
                if args.llm_output_dir:
                    output_dir = Path(args.llm_output_dir)
                    if not output_dir.exists():
                        try:
                            output_dir.mkdir(parents=True, exist_ok=True)
                            print(f"Created output directory: {output_dir}")
                        except Exception as e:
                            print(f"{Colors.YELLOW}Warning: Could not create output directory '{output_dir}': {e}{Colors.RESET}")
                            print(f"{Colors.YELLOW}Using current directory instead.{Colors.RESET}")
                    elif not output_dir.is_dir():
                        print(f"{Colors.YELLOW}Warning: Output path '{output_dir}' exists but is not a directory.{Colors.RESET}")
                        print(f"{Colors.YELLOW}Using current directory instead.{Colors.RESET}")
                    else:
                        config['output_dir'] = args.llm_output_dir

            config['verbose'] = args.verbose
            config['skip_errors'] = args.skip_errors
            # Determine interactive prompts based on skip_errors flag
            config['interactive_prompts'] = not args.skip_errors


        # --- Instantiate and Run ---
        try:
            # Filter config to only include valid arguments for IntuitiveDirTree constructor
            valid_args = {
                k: v for k, v in config.items()
                if k in IntuitiveDirTree.__init__.__code__.co_varnames
            }
            tree_generator = IntuitiveDirTree(**valid_args)
            tree_generator.run() # Generate, export (if enabled), and print

        except (FileNotFoundError, NotADirectoryError, ValueError) as e_init:
             print(f"{Colors.RED}Initialization Error: {e_init}{Colors.RESET}", file=sys.stderr)
             sys.exit(1)
        except SystemExit: # Catch explicit exits (like abort from error handling)
            # Message should already be printed by the handler
            sys.exit(1) # Ensure non-zero exit code on abort
        except Exception as e_run:
            print(f"\n{Colors.RED}An unexpected error occurred during execution:{Colors.RESET}")
            print(traceback.format_exc())
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(130)  # Standard exit code for SIGINT

if __name__ == '__main__':
    # This allows running the CLI module directly for testing,
    # but standard execution should be via the main dirtree.py script.
    print("Running dirtree_cli directly...")
    main()