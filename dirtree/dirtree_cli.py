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
    from .dirtree_config import COMMON_DIR_EXCLUDES, COMMON_FILE_EXCLUDES # Updated import
    from .dirtree_styling import TreeStyle, Colors # For help messages, but not for fallbacks
    from .dirtree_utils import parse_size_string # Utilities, but not for fallbacks
except ImportError as e:
    print(f"Error importing dirtree modules: {e}", file=sys.stderr)
    print("Please ensure you are running this from the correct directory or have installed the package.", file=sys.stderr)
    # Define dummy fallbacks to allow argparse setup at least, but not for fallbacks
    __version__ = "?.?.?"
    # Use different names for fallback classes to avoid type conflicts
    class _DummyIntuitiveDirTree:
        def __init__(self, **kwargs): pass
        def run(self): pass
    # Assign the dummy class to the expected name
    IntuitiveDirTree = _DummyIntuitiveDirTree
    def run_interactive_setup(): return {}
    pick_available = False
    COMMON_DIR_EXCLUDES = []
    COMMON_FILE_EXCLUDES = []
    class _DummyTreeStyle:
        AVAILABLE = {}
    TreeStyle = _DummyTreeStyle
    class _DummyColors:
        RESET = ""; BOLD = ""; GREEN = ""; YELLOW = ""; RED = ""
    Colors = _DummyColors
    def parse_size_string(s, default): return default
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
    filter_group = parser.add_argument_group('Filtering Options (for Tree Display and LLM Export)')
    filter_group.add_argument(
        '-I', '--include',
        action='append',
        metavar='PATTERN',
        default=[],
        dest='cli_include_patterns',
        help="Glob patterns for files/directories to include in the tree (e.g., '*.py', 'src/**').\nIf used, only matching items (and their parents) are shown. Affects LLM export."
    )
    filter_group.add_argument(
        '-E', '--exclude',
        action='append',
        metavar='PATTERN',
        default=[],
        dest='cli_exclude_patterns',
        help="Glob patterns for files/directories to exclude from the tree (e.g., '*.log', 'temp/').\nApplied after smart excludes. Affects LLM export."
    )
    smart_exclude_parser = filter_group.add_mutually_exclusive_group()
    smart_exclude_parser.add_argument(
        '--smart-exclude',
        action='store_true',
        dest='use_smart_exclude', # Set dest explicitly
        default=True, # Default is ON
        help="Automatically apply common excludes (e.g., .git, node_modules) for tree display and LLM export. (Default: ON)"
    )
    smart_exclude_parser.add_argument(
        '--no-smart-exclude',
        action='store_false',
        dest='use_smart_exclude', # Set dest explicitly
        help="Disable automatic common excludes."
    )
    filter_group.add_argument(
        '-H', '--hidden',
        action='store_true',
        default=False,
        help="Show hidden files and directories (those starting with '.') in the tree."
    )

    # --- Display Group ---
    display_group = parser.add_argument_group('Display Options (for Tree Display)')
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
        help="Maximum depth to display in the tree (Default: unlimited)."
    )
    display_group.add_argument(
        '--size',
        action='store_true',
        default=False,
        help="Show file sizes in the tree."
    )
    color_parser = display_group.add_mutually_exclusive_group()
    color_parser.add_argument(
        '--color',
        action='store_true',
        dest='colorize', # Explicit dest
        default=sys.stdout.isatty(), # Default based on TTY
        help="Force colorized output for the tree (Default: auto-detect based on TTY)."
    )
    color_parser.add_argument(
        '--no-color',
        action='store_false',
        dest='colorize', # Explicit dest
        help="Disable colorized output for the tree."
    )

    # --- LLM Export Group ---
    llm_group = parser.add_argument_group('LLM Export Options (for LLM Content Generation)')
    llm_group.add_argument(
        '--llm', # Changed from -L to avoid conflict with a common 'Level' option for depth
        action='store_true',
        dest='export_for_llm',
        default=False,
        help="Generate a Markdown export with structure and selected file content suitable for LLMs."
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
        help="Control LLM inclusion indicators in the tree: 'all' [LLM✓/✗], 'included' [LLM✓], 'none' (Default: included)"
    )
    llm_group.add_argument(
        '--llm-ext',
        action='append',
        metavar='EXT',
        default=None, # None means use default logic
        dest='llm_content_extensions',
        help="File extensions (e.g., py, js) to include content for in LLM export.\nOverrides default logic. Can be used multiple times."
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
        '--dry-run',
        action='store_true',
        default=False,
        help="Scan and calculate statistics without generating output.\nUseful for previewing before full export."
    )
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
                config = run_interactive_setup() # This will populate config with all necessary keys
                if not config: # Setup was cancelled
                    sys.exit(0)
            except Exception:
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

            config['cli_include_patterns'] = args.cli_include_patterns
            config['cli_exclude_patterns'] = args.cli_exclude_patterns
            config['use_smart_exclude'] = args.use_smart_exclude

            # Interactive selections are not made in CLI mode, so these would be empty or None
            config['interactive_file_type_includes_for_llm'] = [] # Not set via CLI directly
            config['interactive_dir_excludes_for_llm'] = []      # Not set via CLI directly

            config['export_for_llm'] = args.export_for_llm
            if config['export_for_llm']:
                try:
                    config['max_llm_file_size'] = parse_size_string(args.llm_max_size, default=100 * 1024)
                except ValueError as e_size:
                     print(f"{Colors.RED}Error: Invalid LLM max size format '{args.llm_max_size}'. {e_size}{Colors.RESET}", file=sys.stderr)
                     sys.exit(1)
                config['llm_content_extensions'] = args.llm_content_extensions # Pass list or None
                config['llm_indicators'] = args.llm_indicators

                if args.llm_output_dir:
                    output_dir_path = Path(args.llm_output_dir)
                    try:
                        output_dir_path.mkdir(parents=True, exist_ok=True)
                        config['output_dir'] = str(output_dir_path.resolve())
                        print(f"LLM export will be saved to: {config['output_dir']}")
                    except Exception as e_dir:
                        print(f"{Colors.YELLOW}Warning: Could not create/use output directory '{output_dir_path}': {e_dir}{Colors.RESET}")
                        print(f"{Colors.YELLOW}Using current directory for LLM export instead.{Colors.RESET}")
                        config['output_dir'] = None # Fallback
                else:
                    config['output_dir'] = None
                config['add_file_marker'] = True # Default to True, can be made configurable if needed

            config['verbose'] = args.verbose
            config['skip_errors'] = args.skip_errors
            config['interactive_prompts'] = not args.skip_errors
            config['dry_run'] = args.dry_run

            # If dry-run, disable output file generation
            if config['dry_run']:
                print(f"{Colors.CYAN}Dry run mode: scanning without generating output.{Colors.RESET}")
                config['export_for_llm'] = False


        # --- Instantiate and Run ---
        try:
            # Filter config to only include valid arguments for IntuitiveDirTree constructor
            # This is important as run_interactive_setup might add other temp keys
            valid_constructor_args = {
                k: v for k, v in config.items()
                if k in IntuitiveDirTree.__init__.__code__.co_varnames
            }
            tree_generator = IntuitiveDirTree(**valid_constructor_args)
            tree_generator.run()

        except (FileNotFoundError, NotADirectoryError, ValueError) as e_init:
             print(f"{Colors.RED}Initialization Error: {e_init}{Colors.RESET}", file=sys.stderr)
             sys.exit(1)
        except SystemExit:
            sys.exit(1) # Already handled by error handler or user abort
        except Exception:
            print(f"\n{Colors.RED}An unexpected error occurred during execution:{Colors.RESET}")
            print(traceback.format_exc())
            sys.exit(1)

    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(130)  # Standard exit code for SIGINT

if __name__ == '__main__':
    main()
