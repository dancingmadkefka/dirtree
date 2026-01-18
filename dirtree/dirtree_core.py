# -*- coding: utf-8 -*-
"""
Core logic for IntuitiveDirTree, including the main class that orchestrates
directory traversal, filtering, styling, and output generation.
"""
import fnmatch

import sys
import os
import traceback
from pathlib import Path
from typing import List, Optional, Tuple, Set

# --- Imports from other modules ---
try:
    from .dirtree_styling import TreeStyle, Colors, DEFAULT_FILETYPE_COLORS, DEFAULT_FILETYPE_EMOJIS
    from .dirtree_filters import passes_tree_filters, should_recurse_for_tree
    from .dirtree_utils import format_bytes, log_message, handle_error
    from .dirtree_llm import generate_llm_export, should_include_content_for_llm
    from .dirtree_config import COMMON_DIR_EXCLUDES, COMMON_FILE_EXCLUDES
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
    def passes_tree_filters(*args, **kwargs): return True
    def should_recurse_for_tree(*args, **kwargs): return True
    def format_bytes(b): return str(b)
    def log_message(*args, **kwargs): pass
    def handle_error(*args, **kwargs): return True, False # Skip item, don't skip all
    def generate_llm_export(*args, **kwargs): return None, 0, 0
    def should_include_content_for_llm(*args, **kwargs): return True
    COMMON_DIR_EXCLUDES = []
    COMMON_FILE_EXCLUDES = []


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
            # Tree Filtering specific patterns (from CLI or advanced interactive)
            cli_include_patterns: Optional[List[str]] = None,
            cli_exclude_patterns: Optional[List[str]] = None,
            use_smart_exclude: bool = True,
            # LLM Export specific patterns (from interactive)
            interactive_file_type_includes_for_llm: Optional[List[str]] = None, # list of extensions like 'py', 'js'
            interactive_dir_excludes_for_llm: Optional[List[str]] = None, # list of dir names like 'coverage'
            # LLM Export general settings
            export_for_llm: bool = False, max_llm_file_size: int = 100 * 1024,
            llm_content_extensions: Optional[List[str]] = None, # from --llm-ext CLI
            llm_indicators: str = "included",
            # Behavior
            verbose: bool = False, interactive_prompts: bool = True, skip_errors: bool = False,
            output_dir: Optional[str] = None,
            add_file_marker: bool = True,
            dry_run: bool = False
    ):
        try:
            self.root_dir = Path(root_dir).resolve(strict=True)
            if not self.root_dir.is_dir():
                 raise NotADirectoryError(f"Path is not a directory: '{self.root_dir}'")
        except FileNotFoundError:
            raise FileNotFoundError(f"Starting directory not found: '{root_dir}'") from None
        except NotADirectoryError as e:
             raise e
        except (PermissionError, OSError) as e:
            raise ValueError(f"Error accessing starting directory '{root_dir}': {e}") from e

        self.style_name = style.lower()
        self.style_config = TreeStyle.get_style(self.style_name)
        self.max_depth = max_depth
        self.show_hidden = show_hidden
        self.colorize = colorize and sys.stdout.isatty()
        self.show_size = show_size

        self.cli_include_patterns = list(cli_include_patterns or [])
        self.cli_exclude_patterns = list(cli_exclude_patterns or [])
        self.use_smart_exclude = use_smart_exclude

        self.interactive_ft_includes_llm = set(interactive_file_type_includes_for_llm or [])
        self.interactive_dir_excludes_llm = set(interactive_dir_excludes_for_llm or [])

        self.export_for_llm = export_for_llm
        self.max_llm_file_size = max_llm_file_size

        # Consolidate LLM content extensions
        if llm_content_extensions is not None: # CLI --llm-ext takes precedence
            self.llm_content_extensions_set = {ext.lower().lstrip('.') for ext in llm_content_extensions}
        elif self.interactive_ft_includes_llm: # Then interactive selection for LLM
            self.llm_content_extensions_set = {ext.lower().lstrip('.') for ext in self.interactive_ft_includes_llm}
        else: # Fallback to default logic (include non-binary)
            self.llm_content_extensions_set = None

        self.llm_indicators = llm_indicators.lower()
        if self.llm_indicators not in ["all", "included", "none"]:
            self.llm_indicators = "included"

        self.verbose = verbose
        self.interactive_prompts = interactive_prompts and not skip_errors and sys.stdout.isatty()
        self.skip_errors = skip_errors

        self.output_dir = Path(output_dir) if output_dir else Path.cwd()
        self.add_file_marker = add_file_marker
        self.dry_run = dry_run

        self.smart_dir_excludes = COMMON_DIR_EXCLUDES if self.use_smart_exclude else []
        self.smart_file_excludes_for_llm = COMMON_FILE_EXCLUDES if self.use_smart_exclude else []

        self.skipped_items: List[Tuple[str, str]] = []
        self.total_items_scanned = 0
        self.items_listed_in_tree = 0
        self._cached_tree_lines: Optional[List[str]] = None
        self._cached_listed_paths_in_tree: Optional[List[Path]] = None
        self._seen_paths_build: Set[Path] = set()

        self._filetype_colors = DEFAULT_FILETYPE_COLORS.copy()
        self._filetype_emojis = DEFAULT_FILETYPE_EMOJIS.copy()

        self.llm_files_considered = 0
        self.llm_files_included_content = 0
        self.llm_total_content_size_bytes = 0

        self._log = lambda msg, level="info": log_message(msg, level, self.verbose, self.colorize)
        self._log_config()

    def _log_config(self):
        self._log(f"Initialized IntuitiveDirTree for: {self.root_dir}", "info")
        if not self.verbose: return
        self._log(f"  Tree Style: {self.style_name}", "debug")
        self._log(f"  Max Depth: {self.max_depth}", "debug")
        self._log(f"  Show Hidden: {self.show_hidden}", "debug")
        self._log(f"  CLI Include Patterns: {self.cli_include_patterns}", "debug")
        self._log(f"  CLI Exclude Patterns: {self.cli_exclude_patterns}", "debug")
        self._log(f"  Use Smart Exclude: {self.use_smart_exclude}", "debug")
        if self.use_smart_exclude:
            self._log(f"    Smart Dir Excludes (tree): {self.smart_dir_excludes}", "debug")
            self._log(f"    Smart File Excludes (LLM): {self.smart_file_excludes_for_llm}", "debug")

        self._log(f"  Interactive Dir Excludes (LLM): {self.interactive_dir_excludes_llm}", "debug")
        self._log(f"  LLM Content Extensions (final): {self.llm_content_extensions_set or 'Default (non-binary)'}", "debug")

        self._log(f"  Export LLM: {self.export_for_llm}", "debug")
        if self.export_for_llm:
            self._log(f"    Max LLM File Size: {format_bytes(self.max_llm_file_size)}", "debug")
            self._log(f"    LLM Indicators: {self.llm_indicators}", "debug")
            self._log(f"    Output Dir: {self.output_dir}", "debug")


    def _get_color(self, path: Path) -> str:
        if not self.colorize: return ""
        if path.is_dir(): return self._filetype_colors.get("dir", Colors.BLUE + Colors.BOLD)
        ext = path.suffix.lower().lstrip(".") if path.suffix else ""
        return self._filetype_colors.get(ext, Colors.WHITE)

    def _get_file_emoji(self, path: Path) -> str:
        if path.is_dir(): return "📂"
        ext = path.suffix.lower().lstrip(".") if path.suffix else ""
        return self._filetype_emojis.get(ext, "📄")

    def _get_llm_indicator(self, is_included: bool) -> str:
        """Return the LLM indicator string based on inclusion status and settings."""
        if self.llm_indicators == "none":
            return ""
        if is_included:
            color = Colors.GREEN if self.colorize else ""
            reset = Colors.RESET if self.colorize else ""
            return f" {color}[LLM✓]{reset}"
        elif self.llm_indicators == "all":
            color = Colors.GRAY if self.colorize else ""
            reset = Colors.RESET if self.colorize else ""
            return f" {color}[LLM✗]{reset}"
        return ""

    def _build_tree_recursive(
        self,
        current_path: Path,
        prefix: str = "",
        depth: int = 0
    ) -> Tuple[List[str], List[Path]]:
        tree_lines: List[str] = []
        listed_paths_in_tree: List[Path] = []

        if self.max_depth is not None and depth >= self.max_depth:
            self._log(f"Max depth {self.max_depth} reached at '{current_path}', stopping tree recursion.", "debug")
            return tree_lines, listed_paths_in_tree

        real_path = None  # Initialize to track for cleanup
        try:
            real_path = current_path.resolve()
            if real_path in self._seen_paths_build:
                self._log(f"Symlink loop or already seen in build: '{current_path}' -> '{real_path}'.", "warning")
                tree_lines.append(f"{prefix}{Colors.YELLOW}...(skipped symlink loop){Colors.RESET}")
                return tree_lines, listed_paths_in_tree
            self._seen_paths_build.add(real_path)
        except (PermissionError, OSError) as e:
            self._log(f"Could not resolve '{current_path}' during build: {e}. Skipping recursion.", "warning")
            return tree_lines, listed_paths_in_tree

        try:
            entries = sorted(list(os.scandir(current_path)), key=lambda e: e.name.lower())
            self.total_items_scanned += len(entries)
        except (PermissionError, OSError) as e:
            should_skip, self.skip_errors = handle_error(
                current_path, e, self._log, self.colorize, self.skip_errors, self.interactive_prompts, phase="listing directory"
            )
            if should_skip:
                self.skipped_items.append((str(current_path), f"Error listing: {e}"))
                tree_lines.append(f"{prefix}{Colors.RED}! Error listing directory: {e}{Colors.RESET}")
                return tree_lines, listed_paths_in_tree
            else: # Abort
                 raise SystemExit("Aborted by user due to directory listing error.") from e

        dir_entries = [e for e in entries if e.is_dir(follow_symlinks=False)] # Use non-following for initial type check
        file_entries = [e for e in entries if e.is_file(follow_symlinks=False)]
        other_entries = [e for e in entries if not e.is_dir(follow_symlinks=False) and not e.is_file(follow_symlinks=False)]
        ordered_entries = dir_entries + file_entries + other_entries

        # Tree style elements
        style = self.style_config
        pointers = {
            "tee": style["tee"], "last_tee": style["last_tee"],
            "branch": style["branch"], "empty": style["empty"],
            "dir_tee": style.get("dir_tee", style["tee"]), # Fallback to regular tee
            "dir_last_tee": style.get("dir_last_tee", style["last_tee"]) # Fallback
        }

        for i, entry in enumerate(ordered_entries):
            entry_path = Path(entry.path)
            is_entry_dir = entry.is_dir() # Follow symlinks to determine if it's a dir for recursion/display

            # --- Tree Filtering ---
            # pass_tree determines if item itself is shown
            # recurse determines if we go inside for tree
            should_display_entry, tree_exclude_reason = passes_tree_filters(
                entry_path, self.root_dir,
                self.cli_include_patterns, self.cli_exclude_patterns,
                self.smart_dir_excludes, # Only dir part of smart excludes for tree structure
                self.show_hidden, self._log
            )
            if not should_display_entry:
                self._log(f"Tree Filter: '{entry_path.name}' HIDDEN from tree. Reason: {tree_exclude_reason}", "debug")
                continue

            self.items_listed_in_tree += 1

            is_smart_excluded_dir_type = any(fnmatch.fnmatch(entry.name, pattern) for pattern in self.smart_dir_excludes)

            should_recurse_for_tree_display = False
            if is_entry_dir:
                should_recurse_for_tree_display = should_recurse_for_tree(
                    entry_path, self.root_dir,
                    self.cli_include_patterns, self.cli_exclude_patterns, # CLI patterns can prevent recursion
                    self.smart_dir_excludes, # Smart excluded dirs are not recursed for tree
                    self.show_hidden, self._log
                )

            # --- LLM Indicator ---
            llm_indicator_str = ""
            is_llm_content_included = False
            if self.export_for_llm and not is_entry_dir: # Only files get LLM indicators for content
                self.llm_files_considered += 1
                try:
                    # Get size without following symlinks for files
                    size_bytes = entry.stat(follow_symlinks=False).st_size

                    # This function now considers all exclusion types
                    is_llm_content_included = should_include_content_for_llm(
                        entry_path, self.root_dir, size_bytes, self.max_llm_file_size,
                        self.llm_content_extensions_set,
                        self.cli_exclude_patterns, # CLI excludes affect LLM
                        self.smart_dir_excludes, self.smart_file_excludes_for_llm, # Smart excludes affect LLM
                        self.interactive_dir_excludes_llm, # Interactive dir excludes affect LLM
                        self._log
                    )

                    if is_llm_content_included:
                        self.llm_files_included_content += 1
                        # Size accumulation will happen in generate_llm_export after reading

                    llm_indicator_str = self._get_llm_indicator(is_llm_content_included)

                except OSError as e_llm_check:
                    self._log(f"Could not check LLM inclusion for '{entry_path}': {e_llm_check}", "warning")

            # --- Formatting for Tree Line ---
            is_last_entry = (i == len(ordered_entries) - 1)

            if is_entry_dir:
                pointer = pointers["dir_last_tee"] if is_last_entry else pointers["dir_tee"]
            else:
                pointer = pointers["last_tee"] if is_last_entry else pointers["tee"]

            display_name = entry.name
            color = self._get_color(entry_path)
            reset = Colors.RESET if self.colorize else ""
            emoji = self._get_file_emoji(entry_path) + " " if self.style_name == "emoji" else ""

            size_info_str = ""
            if self.show_size and not is_entry_dir:
                try:
                    size_bytes = entry.stat(follow_symlinks=False).st_size
                    if self.colorize:
                        size_info_str = f" ({Colors.GRAY}{format_bytes(size_bytes)}{reset})"
                    else:
                        size_info_str = f" ({format_bytes(size_bytes)})"
                except (PermissionError, OSError) as e_size:
                    self._log(f"Could not get size for '{entry_path}': {e_size}", "warning")
                    if self.colorize:
                        size_info_str = f" ({Colors.RED}Size N/A{reset})"
                    else:
                        size_info_str = f" (Size N/A)"

            # Smart excluded dirs get a special marker in the tree
            # This is different from manually excluded for LLM dirs, which show full structure.
            smart_exclude_indicator = ""
            if is_entry_dir and is_smart_excluded_dir_type and not should_recurse_for_tree_display:
                if self.colorize:
                    smart_exclude_indicator = f" {Colors.YELLOW}[excluded]{reset}"
                else:
                    smart_exclude_indicator = " [excluded]"


            line = f"{prefix}{pointer}{emoji}{color}{display_name}{reset}{size_info_str}{llm_indicator_str}{smart_exclude_indicator}"
            tree_lines.append(line)
            listed_paths_in_tree.append(entry_path)

            if is_entry_dir and should_recurse_for_tree_display:
                next_prefix = prefix + (pointers["empty"] if is_last_entry else pointers["branch"])
                try:
                    sub_lines, sub_paths = self._build_tree_recursive(entry_path, next_prefix, depth + 1)
                    tree_lines.extend(sub_lines)
                    listed_paths_in_tree.extend(sub_paths)
                except SystemExit:
                    raise
                except (PermissionError, OSError, RecursionError) as e_recurse:
                    should_skip, self.skip_errors = handle_error(
                        entry_path, e_recurse, self._log, self.colorize, self.skip_errors, self.interactive_prompts, phase="recursing"
                    )
                    if should_skip:
                        self.skipped_items.append((str(entry_path), f"Error recursing: {e_recurse}"))
                        tree_lines.append(f"{next_prefix}{Colors.RED}! Error in subdirectory: {e_recurse}{Colors.RESET}")
                    else:
                        raise SystemExit(f"Aborted by user due to error recursing into {entry_path}.") from e_recurse

        if real_path is not None and real_path in self._seen_paths_build:
            self._seen_paths_build.remove(real_path)
        return tree_lines, listed_paths_in_tree

    def generate_tree(self) -> None:
        if self._cached_tree_lines is not None:
            self._log("Using cached tree data.", "debug")
            return

        self._log("Starting tree generation...", "info")
        # Reset counters for this run
        self.total_items_scanned = 0
        self.items_listed_in_tree = 0
        self.skipped_items = []
        self.llm_files_considered = 0
        self.llm_files_included_content = 0
        self.llm_total_content_size_bytes = 0
        self._seen_paths_build = set()

        root_color = self._get_color(self.root_dir)
        root_emoji = "🌳 " if self.style_name == "emoji" else ""
        reset = Colors.RESET if self.colorize else ""
        root_line = f"{root_emoji}{root_color}{self.root_dir.name}{reset}"

        try:
            sub_lines, sub_paths = self._build_tree_recursive(self.root_dir)
            self._cached_tree_lines = [root_line] + sub_lines
            self._cached_listed_paths_in_tree = [self.root_dir] + sub_paths
            self._log(f"Tree generation complete. Scanned: {self.total_items_scanned}, Listed in tree: {self.items_listed_in_tree}, Skipped: {len(self.skipped_items)}", "info")
        except SystemExit:
             if self.colorize:
                 print(f"\n{Colors.RED}Tree generation aborted.{Colors.RESET}")
             else:
                 print("\nTree generation aborted.")
             self._cached_tree_lines = []
             self._cached_listed_paths_in_tree = []
        except Exception:
             if self.colorize:
                 print(f"\n{Colors.RED}An unexpected error occurred during tree generation:{Colors.RESET}")
                 print(f"{Colors.RED}{traceback.format_exc()}{Colors.RESET}")
             else:
                 print("\nAn unexpected error occurred during tree generation:")
                 print(traceback.format_exc())
             self._log(f"Unexpected error during generate_tree: {traceback.format_exc()}", "error")
             self._cached_tree_lines = []
             self._cached_listed_paths_in_tree = []


    def print_results(self, llm_export_path: Optional[Path] = None):
        if self._cached_tree_lines is None:
            print("Tree not generated yet. Call generate_tree() first.", file=sys.stderr)
            return
        if not self._cached_tree_lines:
             print("Tree generation failed or was aborted. No results to print.", file=sys.stderr)
             return

        print("\n" + "-"*80)
        for line in self._cached_tree_lines:
            print(line)
        print("-" * 80)

        summary = f"{self.items_listed_in_tree} items listed in tree"
        if self.total_items_scanned > 0:
             summary += f" (Total items scanned: {self.total_items_scanned})"
        if self.skipped_items:
            if self.colorize:
                summary += f", {Colors.YELLOW}{len(self.skipped_items)} skipped due to errors{Colors.RESET}"
            else:
                summary += f", {len(self.skipped_items)} skipped due to errors"
        print(summary + ".")

        if self.export_for_llm:
            if self.llm_files_considered > 0:
                llm_summary = f"LLM Export: {self.llm_files_included_content}/{self.llm_files_considered} files included in content"
                if self.llm_total_content_size_bytes > 0: # Updated from generate_llm_export
                    llm_summary += f" ({format_bytes(self.llm_total_content_size_bytes)} total content size)"
                print(llm_summary)
            else:
                print("No files were considered eligible for LLM content based on filters.")

        if self.skipped_items and self.verbose:
            print("\nSkipped items details:")
            for path, reason in self.skipped_items:
                print(f"  - {path}: {reason}")

        if llm_export_path:
            if self.colorize:
                print(f"\n{Colors.GREEN}✅ LLM export created: {llm_export_path}{Colors.RESET}")
            else:
                print(f"\n✅ LLM export created: {llm_export_path}")
            print(f"   To use this export with an LLM, upload the file or copy its contents.")
        elif self.export_for_llm: # If export was true but path is None
            if self.colorize:
                print(f"\n{Colors.YELLOW}⚠️ LLM export was enabled, but no content was included or an error occurred.{Colors.RESET}")
            else:
                print(f"\n⚠️ LLM export was enabled, but no content was included or an error occurred.")

    def run(self) -> None:
        self.generate_tree()

        if self.dry_run:
            self._print_dry_run_summary()
            return

        llm_export_file = None
        if self.export_for_llm and self._cached_tree_lines and self._cached_listed_paths_in_tree:
            llm_export_file, self.llm_total_content_size_bytes, self.llm_files_included_content = generate_llm_export(
                root_dir=self.root_dir,
                tree_lines=self._cached_tree_lines, # Pass the visual tree for the header
                # Paths that appeared in the tree are candidates for LLM content
                paths_in_tree_for_llm_check=self._cached_listed_paths_in_tree,
                max_llm_file_size=self.max_llm_file_size,
                llm_content_extensions_set=self.llm_content_extensions_set,
                cli_exclude_patterns=self.cli_exclude_patterns,
                smart_dir_excludes=self.smart_dir_excludes,
                smart_file_excludes_for_llm=self.smart_file_excludes_for_llm,
                interactive_dir_excludes_llm=self.interactive_dir_excludes_llm,
                log_func=self._log,
                output_dir=self.output_dir,
                add_file_marker=self.add_file_marker
            )
            # Update llm_files_considered as generate_llm_export might refine this
            # For simplicity, we'll rely on the stats from generate_llm_export for the final print.
            # The self.llm_files_considered from _build_tree_recursive is an initial estimate.
            # A more accurate 'considered' count would be inside generate_llm_export before should_include.

        self.print_results(llm_export_path=llm_export_file)

    def _print_dry_run_summary(self) -> None:
        """Print statistics summary without generating output."""
        print("\n" + "="*60)
        print("DRY RUN SUMMARY")
        print("="*60)
        print(f"Items scanned:    {self.total_items_scanned:,}")
        print(f"Items filtered:   {self.total_items_scanned - self.items_listed_in_tree:,}")
        print(f"Items listed:     {self.items_listed_in_tree:,}")
        if self.skipped_items:
            print(f"Errors skipped:   {len(self.skipped_items)}")
        if self.llm_files_considered > 0:
            print(f"\nLLM Export Estimates:")
            print(f"  Files considered:  {self.llm_files_considered:,}")
            print(f"  Files to include:  {self.llm_files_included_content:,}")
            if self.llm_files_included_content > 0:
                avg_size = self.max_llm_file_size // 2  # Rough estimate
                est_size = self.llm_files_included_content * avg_size
                print(f"  Est. export size:  {format_bytes(est_size)}")
        print("="*60)