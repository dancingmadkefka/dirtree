# -*- coding: utf-8 -*-
"""
Core logic for IntuitiveDirTree, including the main class that orchestrates
directory traversal, filtering, styling, and output generation.
"""

import sys
import os
import traceback
from pathlib import Path
from typing import List, Optional, Dict, Tuple, Set, Any, Callable

# --- Imports from other modules ---
try:
    from .dirtree_styling import TreeStyle, Colors, DEFAULT_FILETYPE_COLORS, DEFAULT_FILETYPE_EMOJIS
    from .dirtree_filters import passes_filters, should_recurse_into
    from .dirtree_utils import format_bytes, log_message, handle_error
    from .dirtree_llm import generate_llm_export, should_include_content_for_llm
except ImportError:
    # Fallback for direct execution or testing
    print("Warning: Running core module potentially outside of package context.", file=sys.stderr)
    # Define dummy fallbacks if needed
    class TreeStyle:
        @staticmethod
        def get_style(s): return {"branch": "| ", "tee": "|-", "last_tee": "`-", "empty": "  "}
    class Colors: RESET = ""; BOLD = ""; BLUE = ""; WHITE = ""; GRAY = ""; RED = ""; YELLOW = ""
    DEFAULT_FILETYPE_COLORS = {}
    DEFAULT_FILETYPE_EMOJIS = {}
    def passes_filters(*args, **kwargs): return True
    def should_recurse_into(*args, **kwargs): return True
    def format_bytes(b): return str(b)
    def log_message(*args, **kwargs): pass
    def handle_error(*args, **kwargs): return True, False # Skip item, don't skip all
    def generate_llm_export(*args, **kwargs): return None
    def should_include_content_for_llm(*args, **kwargs): return True


# --- Main Class ---

class IntuitiveDirTree:
    """
    Generates directory trees with intuitive usage, filtering, styling, and LLM export.
    Orchestrates the process using functions and data from other modules.
    """

    def __init__(
            self,
            root_dir: str = ".",
            # Display
            style: str = "unicode", max_depth: Optional[int] = None, show_hidden: bool = False,
            colorize: bool = True, show_size: bool = False,
            # Filtering (final effective patterns)
            include_patterns: Optional[List[str]] = None,
            exclude_patterns: Optional[List[str]] = None,
            use_smart_exclude: bool = True, # Store the choice that led to exclude_patterns
            # LLM Export
            export_for_llm: bool = False, max_llm_file_size: int = 100 * 1024,
            llm_content_extensions: Optional[List[str]] = None, # List of extensions (without '.')
            # LLM Display options
            llm_indicators: str = "included", # Options: "all", "included", "none"
            # Behavior
            verbose: bool = False, interactive_prompts: bool = True, skip_errors: bool = False,
            # New options
            output_dir: Optional[str] = None,  # Directory to save LLM export
            add_file_marker: bool = False  # Whether to add a special marker to generated files
    ):
        try:
            self.root_dir = Path(root_dir).resolve(strict=True) # Strict check ensures exists
            if not self.root_dir.is_dir():
                 raise NotADirectoryError(f"Path is not a directory: '{self.root_dir}'")
        except FileNotFoundError:
            raise FileNotFoundError(f"Starting directory not found: '{root_dir}'")
        except NotADirectoryError as e:
             raise e # Re-raise specific error
        except Exception as e:
            # Catch other potential resolution errors (permissions, etc.)
            raise ValueError(f"Error accessing starting directory '{root_dir}': {e}")

        # --- Store settings ---
        self.style_name = style.lower()
        # Use the get_style method from the styling module
        self.style_config = TreeStyle.get_style(self.style_name)
        self.max_depth = max_depth
        self.show_hidden = show_hidden
        # Colorize based on flag AND if stdout is a TTY
        self.colorize = colorize and sys.stdout.isatty()
        self.show_size = show_size

        # Store LLM display settings
        self.llm_indicators = llm_indicators.lower()
        if self.llm_indicators not in ["all", "included", "none"]:
            self.llm_indicators = "included"  # Default to only showing included files

        # Store the final, effective patterns
        self.patterns_to_include = list(include_patterns or [])
        self.patterns_to_exclude = list(exclude_patterns or [])
        self.use_smart_exclude = use_smart_exclude # Store the setting itself

        # Import smart exclude patterns from config
        try:
            from .dirtree_config import COMMON_EXCLUDES
            self.smart_exclude_patterns = COMMON_EXCLUDES
        except ImportError:
            self.smart_exclude_patterns = [
                # Version control
                ".git", ".svn", ".hg",
                # Node.js
                "node_modules",
                # Python
                "__pycache__", "*.pyc", "venv", ".venv",
                # IDE files
                ".idea", ".vscode"
            ]

        self.export_for_llm = export_for_llm
        self.max_llm_file_size = max_llm_file_size
        # Convert list of extensions to a set for efficient lookup, handling leading '.'
        if llm_content_extensions is not None:
            self.llm_content_extensions_set = {ext.lower().lstrip('.') for ext in llm_content_extensions}
        else:
            self.llm_content_extensions_set = None # Use default logic in llm module

        self.verbose = verbose
        # Interactive prompts only work if not skipping errors and stdout is a TTY
        self.interactive_prompts = interactive_prompts and not skip_errors and sys.stdout.isatty()
        self.skip_errors = skip_errors # Initial state, can be changed by handle_error

        # Save output directory
        self.output_dir = Path(output_dir) if output_dir else None

        # Store file marker setting
        self.add_file_marker = add_file_marker

        # --- Internal State ---
        self.skipped_items = []
        self.total_items_scanned = 0
        self.items_listed = 0
        self._cached_tree_lines = None
        self._cached_listed_paths = None
        self._seen_paths_build = set()
        # Use defaults from styling module
        self._filetype_colors = DEFAULT_FILETYPE_COLORS.copy()
        self._filetype_emojis = DEFAULT_FILETYPE_EMOJIS.copy()

        # For LLM export stats
        self.llm_eligible_files = 0
        self.llm_included_files = 0
        self.llm_total_content_size = 0

        # Configure logging function for this instance
        self._log = lambda msg, level="info": log_message(msg, level, self.verbose, self.colorize)

        self._log(f"Initialized IntuitiveDirTree for: {self.root_dir}", "info")
        if self.verbose:
            self._log(f"  Style: {self.style_name}", "debug")
            self._log(f"  Max Depth: {self.max_depth}", "debug")
            self._log(f"  Show Hidden: {self.show_hidden}", "debug")
            self._log(f"  Colorize: {self.colorize} (Argument: {colorize}, TTY: {sys.stdout.isatty()})", "debug")
            self._log(f"  Show Size: {self.show_size}", "debug")
            self._log(f"  Include Patterns: {self.patterns_to_include}", "debug")
            self._log(f"  Exclude Patterns: {self.patterns_to_exclude}", "debug")
            self._log(f"  Use Smart Exclude: {self.use_smart_exclude}", "debug")
            self._log(f"  Export LLM: {self.export_for_llm}", "debug")
            if self.export_for_llm:
                self._log(f"    Max LLM File Size: {format_bytes(self.max_llm_file_size)}", "debug")
                self._log(f"    LLM Content Extensions: {self.llm_content_extensions_set or 'Default'}", "debug")
                self._log(f"    Output Directory: {self.output_dir or 'Current directory'}", "debug")
            self._log(f"  Verbose: {self.verbose}", "debug")
            self._log(f"  Skip Errors: {self.skip_errors}", "debug")
            self._log(f"  Interactive Prompts: {self.interactive_prompts}", "debug")


    # --- Styling Helpers (using instance config) ---
    def _get_color(self, path: Path) -> str:
        """Gets the color for a path based on its type and extension."""
        if not self.colorize: return ""
        if path.is_dir(): return self._filetype_colors.get("dir", Colors.BLUE + Colors.BOLD)
        # Use lowercase extension without dot for lookup
        ext = path.suffix.lower().lstrip(".") if path.suffix else ""
        return self._filetype_colors.get(ext, Colors.WHITE) # Default to white

    def _get_file_emoji(self, path: Path) -> str:
        """Gets the emoji for a path based on its type and extension."""
        if path.is_dir(): return "📂" # Standard folder emoji
        ext = path.suffix.lower().lstrip(".") if path.suffix else ""
        return self._filetype_emojis.get(ext, "📄") # Default document emoji

    # --- Core Tree Building Logic ---
    def _build_tree_recursive(
        self,
        current_path: Path,
        prefix: str = "",
        depth: int = 0
    ) -> Tuple[List[str], List[Path]]:
        """
        Recursively builds the directory tree structure.

        Args:
            current_path: The directory path to process.
            prefix: The string prefix for drawing tree lines.
            depth: The current recursion depth.

        Returns:
            A tuple containing:
            - list[str]: Lines representing the tree structure for this level.
            - list[Path]: Path objects corresponding to the items in the lines list.
        """
        tree_lines: List[str] = []
        listed_paths: List[Path] = []

        # Check recursion depth limit
        if self.max_depth is not None and depth >= self.max_depth:
            self._log(f"Max depth {self.max_depth} reached at '{current_path}', stopping recursion.", "debug")
            return tree_lines, listed_paths

        # Prevent infinite loops with symlinks during the build phase
        try:
            real_path = current_path.resolve()
            if real_path in self._seen_paths_build:
                self._log(f"Symlink loop detected or path already seen in build: '{current_path}' -> '{real_path}', skipping.", "warning")
                tree_lines.append(f"{prefix}...(skipped due to loop/seen path)")
                return tree_lines, listed_paths # Return immediately
            self._seen_paths_build.add(real_path)
        except Exception as e:
            self._log(f"Could not resolve path '{current_path}' during build: {e}. Skipping recursion.", "warning")
            # Decide how to handle this - skip or attempt to list with original path?
            # For safety, let's skip recursion but allow the directory itself to be listed if it passes filters.
            return tree_lines, listed_paths

        try:
            # Get directory contents, handling potential errors
            entries = sorted(list(os.scandir(current_path)), key=lambda e: e.name.lower())
            self.total_items_scanned += len(entries) # Count scanned items
        except Exception as e:
            # Use the centralized error handler
            should_skip, should_skip_all = handle_error(
                current_path, e, self._log, self.colorize, self.skip_errors, self.interactive_prompts, phase="listing directory"
            )
            self.skip_errors = self.skip_errors or should_skip_all # Update global skip state if needed
            self.interactive_prompts = self.interactive_prompts and not self.skip_errors # Update interactive state

            if should_skip:
                self.skipped_items.append((str(current_path), f"Error listing directory: {e}"))
                # Add a note in the tree about the skipped directory
                tree_lines.append(f"{prefix}{Colors.RED}! Error listing directory: {e}{Colors.RESET}")
                return tree_lines, listed_paths # Cannot proceed further down this branch
            else:
                 # User chose to abort
                 raise SystemExit("Aborted by user due to directory listing error.") from e

        # Separate directories and files for processing order (dirs often listed first)
        dir_entries = [entry for entry in entries if entry.is_dir(follow_symlinks=False)] # Check type without following
        file_entries = [entry for entry in entries if entry.is_file(follow_symlinks=False)]
        other_entries = [entry for entry in entries if not entry.is_dir(follow_symlinks=False) and not entry.is_file(follow_symlinks=False)]
        # Combine, ensuring consistent order (e.g., dirs first)
        ordered_entries = dir_entries + file_entries + other_entries

        # Get tree style pointers from style config
        pointers = {
            "tee": self.style_config["tee"],
            "last_tee": self.style_config["last_tee"],
            "branch": self.style_config["branch"],
            "empty": self.style_config["empty"]
        }

        # Add special pointers for emoji style directories, but only if they exist
        # This is what caused the KeyError
        if self.style_name == "emoji":
            # Only use dir_tee/dir_last_tee if they exist in the style config
            if "dir_tee" in self.style_config:
                pointers["dir_tee"] = self.style_config["dir_tee"]
            if "dir_last_tee" in self.style_config:
                pointers["dir_last_tee"] = self.style_config["dir_last_tee"]

        for i, entry in enumerate(ordered_entries):
            entry_path = Path(entry.path)
            is_last = (i == len(ordered_entries) - 1)
            # Determine if this is a directory early (needed for LLM indicator logic)
            is_dir = entry.is_dir() # Follow symlinks here to decide recursion

            # Apply display filtering rules
            if not passes_filters(entry_path, self.root_dir, self.patterns_to_include, self.patterns_to_exclude, self.show_hidden, self._log):
                continue # Skip items failing filters

            # Add LLM content indicator for files when export is enabled
            llm_indicator = ""
            if self.export_for_llm and not is_dir:
                try:
                    size_bytes = entry.stat(follow_symlinks=False).st_size
                    self.llm_eligible_files += 1
                    # Check if file should be included in LLM export
                    will_include = should_include_content_for_llm(
                        entry_path, size_bytes, self.max_llm_file_size,
                        self.llm_content_extensions_set, self._log
                    )

                    # Only show indicators based on user preference
                    if self.llm_indicators == "all":
                        # Show indicators for both included and excluded
                        if will_include:
                            llm_indicator = f" {Colors.GREEN}[LLM✓]{Colors.RESET}"
                            self.llm_included_files += 1
                        else:
                            llm_indicator = f" {Colors.GRAY}[LLM✗]{Colors.RESET}"
                    elif self.llm_indicators == "included" and will_include:
                        # Only show indicators for included files
                        llm_indicator = f" {Colors.GREEN}[LLM✓]{Colors.RESET}"
                        self.llm_included_files += 1
                    elif self.llm_indicators == "none":
                        # Don't show any indicators
                        if will_include:
                            self.llm_included_files += 1

                except Exception as e:
                    self._log(f"Could not check LLM inclusion for '{entry_path}': {e}", "warning")

            # Determine tree structure characters
            # is_dir is already defined above

            # Fixed logic for determining the pointer to use
            if is_dir:
                if self.style_name == "emoji" and "dir_last_tee" in self.style_config and "dir_tee" in self.style_config:
                    # Only use special dir pointers if they exist in emoji style
                    pointer = pointers["dir_last_tee"] if is_last else pointers["dir_tee"]
                else:
                    # Otherwise use regular pointers
                    pointer = pointers["last_tee"] if is_last else pointers["tee"]
            else:
                # For files, always use regular pointers
                pointer = pointers["last_tee"] if is_last else pointers["tee"]

            # Get display name, color, and emoji
            display_name = entry.name
            color = self._get_color(entry_path)
            reset = Colors.RESET if self.colorize else ""
            emoji = self._get_file_emoji(entry_path) + " " if self.style_name == "emoji" else ""

            # Add special indicators for excluded directories
            is_excluded_dir = False
            should_recurse = True
            if is_dir:
                # Check if we should recurse into this directory
                # For smart exclude, we need to check both the standard exclude patterns
                # and the smart exclude patterns
                exclude_patterns = self.patterns_to_exclude.copy()

                # Add smart exclude patterns if enabled
                if self.use_smart_exclude:
                    for smart_pattern in self.smart_exclude_patterns:
                        if smart_pattern not in exclude_patterns:
                            exclude_patterns.append(smart_pattern)

                should_recurse = should_recurse_into(
                    entry_path, self.root_dir, exclude_patterns, self.show_hidden, self._log
                )
                is_excluded_dir = not should_recurse
                self._log(f"Recursion check for {entry_path}: {'ALLOW' if should_recurse else 'BLOCK'}", "debug")
            exclude_indicator = f" {Colors.YELLOW}[excluded]{reset}" if is_excluded_dir else ""

            # Add size info if requested
            size_info = ""
            if self.show_size and not is_dir: # Only show size for files
                try:
                    size_bytes = entry.stat(follow_symlinks=False).st_size # Get size of file itself
                    size_info = f" ({Colors.GRAY}{format_bytes(size_bytes)}{reset})"
                except Exception as e:
                    self._log(f"Could not get size for '{entry_path}': {e}", "warning")
                    size_info = f" ({Colors.RED}Size N/A{reset})"

            # LLM indicator is already handled above

            # Construct the line
            line = f"{prefix}{pointer}{emoji}{color}{display_name}{reset}{size_info}{llm_indicator}{exclude_indicator}"
            tree_lines.append(line)
            listed_paths.append(entry_path) # Add corresponding path
            self.items_listed += 1

            # Recursively process subdirectories only if they pass the recursion filter
            if is_dir and not is_excluded_dir:
                # Calculate the prefix for the next level
                next_prefix = prefix + (pointers["empty"] if is_last else pointers["branch"])
                try:
                    sub_lines, sub_paths = self._build_tree_recursive(entry_path, next_prefix, depth + 1)
                    tree_lines.extend(sub_lines)
                    listed_paths.extend(sub_paths)
                except SystemExit: # Propagate abort signal upwards
                    raise
                except Exception as e_recurse:
                     # Handle errors during recursion using the centralized handler
                    should_skip, should_skip_all = handle_error(
                        entry_path, e_recurse, self._log, self.colorize, self.skip_errors, self.interactive_prompts, phase="recursing into directory"
                    )
                    self.skip_errors = self.skip_errors or should_skip_all
                    self.interactive_prompts = self.interactive_prompts and not self.skip_errors

                    if should_skip:
                        self.skipped_items.append((str(entry_path), f"Error recursing: {e_recurse}"))
                        tree_lines.append(f"{next_prefix}{Colors.RED}! Error processing subdirectory: {e_recurse}{Colors.RESET}")
                    else:
                        raise SystemExit(f"Aborted by user due to error recursing into {entry_path}.") from e_recurse


        # Clean up seen path for this level if it was resolved (allows revisiting via different symlink paths if needed)
        if 'real_path' in locals() and real_path in self._seen_paths_build:
             self._seen_paths_build.remove(real_path)

        return tree_lines, listed_paths

    # --- Public Methods ---
    def generate_tree(self) -> None:
        """Generates the directory tree lines and caches them."""
        if self._cached_tree_lines is not None:
            self._log("Using cached tree data.", "debug")
            return

        self._log("Starting tree generation...", "info")
        self.total_items_scanned = 0 # Reset scan count for build phase
        self.items_listed = 0
        self.skipped_items = []
        self.llm_eligible_files = 0
        self.llm_included_files = 0
        self.llm_total_content_size = 0
        self._seen_paths_build = set() # Reset seen paths for this run

        # Add the root directory itself
        root_color = self._get_color(self.root_dir)
        root_emoji = "🌳 " if self.style_name == "emoji" else "" # Special root emoji
        reset = Colors.RESET if self.colorize else ""
        root_line = f"{root_emoji}{root_color}{self.root_dir.name}{reset}"

        try:
            # Start recursive build
            sub_lines, sub_paths = self._build_tree_recursive(self.root_dir)
            self._cached_tree_lines = [root_line] + sub_lines
            # Store root path + sub paths
            self._cached_listed_paths = [self.root_dir] + sub_paths
            self._log(f"Tree generation complete. Scanned: {self.total_items_scanned}, Listed: {self.items_listed}, Skipped: {len(self.skipped_items)}", "info")
        except SystemExit: # Catch abort signal
             print(f"\n{Colors.RED}Tree generation aborted.{Colors.RESET}")
             # Set empty cache to indicate failure/abort
             self._cached_tree_lines = []
             self._cached_listed_paths = []
        except Exception as e:
             print(f"\n{Colors.RED}An unexpected error occurred during tree generation:{Colors.RESET}")
             print(f"{Colors.RED}{traceback.format_exc()}{Colors.RESET}")
             self._log(f"Unexpected error during generate_tree: {e}", "error")
             self._cached_tree_lines = [] # Indicate failure
             self._cached_listed_paths = []


    def print_results(self, llm_export_path: Optional[Path] = None):
        """Prints the generated tree and summary information."""
        if self._cached_tree_lines is None:
            print("Tree not generated yet. Call generate_tree() first.", file=sys.stderr)
            return
        if not self._cached_tree_lines:
             print("Tree generation failed or was aborted. No results to print.", file=sys.stderr)
             return

        print("\n" + "-"*80) # Separator
        for line in self._cached_tree_lines:
            print(line)
        print("-" * 80) # Separator

        # Print Summary
        summary = f"{self.items_listed} items listed"
        if self.total_items_scanned > 0:
             summary += f" (Total scanned during build: {self.total_items_scanned})"
        if self.skipped_items:
            summary += f", {Colors.YELLOW}{len(self.skipped_items)} skipped due to errors{Colors.RESET}"
        print(summary + ".")

        if self.export_for_llm:
            if self.llm_eligible_files > 0:
                llm_summary = f"LLM Export: {self.llm_included_files}/{self.llm_eligible_files} files included"
                if self.llm_total_content_size > 0:
                    llm_summary += f" ({format_bytes(self.llm_total_content_size)} total content)"
                print(llm_summary)
            else:
                print("No files eligible for LLM export were found.")

        if self.skipped_items and self.verbose:
            print("\nSkipped items:")
            for path, reason in self.skipped_items:
                print(f"  - {path}: {reason}")

        if llm_export_path:
            print(f"\n{Colors.GREEN}✅ LLM export created: {llm_export_path}{Colors.RESET}")
            print(f"   To use this export with an LLM, upload the file or copy its contents.")
        elif self.export_for_llm:
            print(f"\n{Colors.YELLOW}⚠️ LLM export was enabled but the export file could not be generated.{Colors.RESET}")


    def run(self) -> None:
        """Generates the tree, optionally creates LLM export, and prints results."""
        self.generate_tree()

        llm_export_file = None
        if self.export_for_llm and self._cached_tree_lines and self._cached_listed_paths:
            # Call the llm export function from the llm module
            llm_export_file = generate_llm_export(
                root_dir=self.root_dir,
                tree_lines=self._cached_tree_lines,
                listed_paths=self._cached_listed_paths,
                max_llm_file_size=self.max_llm_file_size,
                llm_content_extensions_set=self.llm_content_extensions_set,
                log_func=self._log,
                output_dir=self.output_dir, # Use configured output directory
                add_file_marker=self.add_file_marker # Add special marker if enabled
            )

            # Update content size stats
            if llm_export_file and hasattr(self, 'llm_total_content_size') and isinstance(self.llm_total_content_size, int):
                try:
                    self.llm_total_content_size = llm_export_file.stat().st_size
                except Exception:
                    pass  # Ignore errors calculating size

        self.print_results(llm_export_path=llm_export_file)