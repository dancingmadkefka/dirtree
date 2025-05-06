# -*- coding: utf-8 -*-
"""
Configuration settings, constants, and default directory handling for IntuitiveDirTree.
"""

import os
import json
from pathlib import Path
from typing import Optional, List, Set, Dict, Any

# --- Default Directory Functions ---
def get_default_dir() -> Optional[str]:
    """Get stored default directory from user config"""
    config_file = Path.home() / ".dirtree_config.json"
    try:
        if config_file.exists():
            config = json.loads(config_file.read_text(encoding='utf-8'))
            return config.get('default_dir')
    except Exception:
        pass # Ignore errors reading config
    return None

def get_saved_config() -> Dict[str, Any]:
    """Get all saved configuration options"""
    config_file = Path.home() / ".dirtree_config.json"
    try:
        if config_file.exists():
            return json.loads(config_file.read_text(encoding='utf-8'))
    except Exception:
        pass # Ignore errors reading config
    return {}

def set_default_dir(directory: str) -> None:
    """Store default directory in user config"""
    config_file = Path.home() / ".dirtree_config.json"
    try:
        # Load existing config if it exists
        config_data = {}
        if config_file.exists():
            try:
                config_data = json.loads(config_file.read_text(encoding='utf-8'))
            except Exception:
                pass  # Start fresh if the file is corrupted

        # Update with new default directory
        config_data['default_dir'] = str(Path(directory).resolve())

        # Write back to file
        config_file.write_text(json.dumps(config_data, indent=2), encoding='utf-8')
    except Exception as e:
        print(f"Warning: Error saving default directory: {e}")

def save_config(config_to_save: Dict[str, Any]) -> None:
    """Save configuration settings for future use"""
    config_file = Path.home() / ".dirtree_config.json"
    try:
        # Load existing config if it exists
        existing_config = {}
        if config_file.exists():
            try:
                existing_config = json.loads(config_file.read_text(encoding='utf-8'))
            except Exception:
                pass  # Start fresh if the file is corrupted

        # Filter out unwanted keys (like root_dir which changes per run)
        # Also filter out specific CLI patterns as they are context-dependent
        save_keys = {
            'style', 'max_depth', 'show_hidden', 'colorize', 'show_size',
            'use_smart_exclude', 'export_for_llm', 'max_llm_file_size',
            'llm_content_extensions', 'llm_indicators', 'verbose', 'skip_errors', 'add_file_marker',
            # Interactive selections for LLM can be saved
            'interactive_file_type_includes_for_llm',
            'interactive_dir_excludes_for_llm'
        }
        # Update only allowed keys
        for key in save_keys:
            if key in config_to_save:
                existing_config[key] = config_to_save[key]

        # Write back to file
        config_file.write_text(json.dumps(existing_config, indent=2), encoding='utf-8')
    except Exception as e:
        print(f"Warning: Error saving configuration: {e}")

# --- Constants ---

# Common directories to automatically exclude from tree recursion (Smart Exclude)
# These will be shown as `[excluded]` in the tree.
COMMON_DIR_EXCLUDES: List[str] = [
    # Version control
    ".git", ".svn", ".hg",
    # Node.js
    "node_modules",
    # Python
    "__pycache__", "__tests__", "__mocks__", "venv", "env", ".venv",
    "dist", "build", "htmlcov", ".pytest_cache", ".mypy_cache",
    # IDE and editor files (often directories)
    ".idea", ".vscode", ".vs",
    # Common build/cache directories
    ".next", "out", "coverage", "bin", "obj", "target", ".cache", ".npm",
    # Temp and log directories (if they are just names)
    "logs", "tmp", "temp",
    # Special marker for dirtree generated files
    "*dirtree_export_*.md", # To exclude previously generated reports
]

# Common files to automatically exclude from LLM content export (Smart Exclude)
# These files WILL appear in the tree but their content won't be in LLM export by default.
COMMON_FILE_EXCLUDES: List[str] = [
    ".gitignore", ".gitattributes", ".gitmodules",
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "*.pyc", "*.pyo", "*.egg-info",
    ".DS_Store", "Thumbs.db",
    ".env", ".env.*", ".envrc",
    "*.log", # Individual log files
]


# File extensions generally considered "binary" or not useful for LLM text context.
# Used if no specific LLM extensions are provided.
DEFAULT_LLM_EXCLUDED_EXTENSIONS: Set[str] = {
    # Images
    "jpg", "jpeg", "png", "gif", "bmp", "ico", "webp", "tiff", "tif", "psd", "svg",
    # Audio/Video
    "mp3", "mp4", "wav", "avi", "mov", "wmv", "flv", "ogg", "webm", "mkv", "aac", "flac",
    # Archives
    "zip", "tar", "gz", "bz2", "xz", "rar", "7z", "jar", "war", "ear",
    # Executables/Binaries
    "exe", "dll", "so", "dylib", "bin", "o", "a", "lib", "class", "msi", "dmg", "pkg",
    # Documents (often binary or complex structure)
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "odt", "ods", "odp",
    # Databases
    "db", "sqlite", "sqlite3", "mdb", "accdb", "dump", "sqlitedb",
    # Fonts
    "ttf", "otf", "woff", "woff2", "eot",
    # Other
    "iso", "img", "swf", "dat", "pickle", "pkl", "model", "pt", "onnx", "lock", "bak",
}

# Default extensions to *include* in LLM exports if no specific list is given
# (common code and text files). Overrides DEFAULT_LLM_EXCLUDED_EXTENSIONS.
DEFAULT_LLM_INCLUDE_EXTENSIONS: Set[str] = {
    # Programming languages
    "py", "pyw", "js", "jsx", "ts", "tsx", "java", "c", "cpp", "h", "hpp", "cs",
    "go", "rb", "php", "swift", "kt", "kts", "rs", "lua", "pl", "pm", "dart", "fs", "fsx",
    "scala", "groovy", "clj", "cljs", "cljc", "ex", "exs", "elm", "purs", "hs", "erl", "hrl",
    "vb", "vbs", "r", "m", "mm", "f", "f90", "for", "ada", "pas", "d", "nim", "zig",
    "gd", # Godot script
    # Shell and scripting
    "sh", "bash", "zsh", "fish", "csh", "ksh", "ps1", "psm1", "bat", "cmd", "vbs", "applescript",
    # Config and data formats
    "json", "yaml", "yml", "xml", "toml", "ini", "cfg", "conf", "env", "editorconfig",
    "properties", "reg", "neon", "tfvars", "hcl", "cue",
    # Markup and documentation
    "md", "markdown", "rst", "txt", "html", "htm", "css", "scss", "sass", "less", "styl",
    "tex", "ltx", "bib", "textile", "asciidoc", "adoc", "org", "ipynb", "vue", "svelte",
    "graphql", "gql", "proto", "tf", "bicep", "hjson", "json5", "jsonc",
    # SQL and database related
    "sql", "ddl", "dml", "prisma",
    # Other text formats
    "log", "gitignore", "gitattributes", "gitmodules", "dockerfile", "compose.yaml", "compose.yml",
    "makefile", "mk", "cmake", "gradle", "pom.xml", "csproj", "vbproj", "sln", "vcxproj",
    "yaml-tml", "json-tml", "http", "rest", "openapi.yaml", "openapi.json", "asyncapi.yaml",
    "asyncapi.json", "patch", "diff", "srt", "vtt", "sub", "wgsl", "glsl", "hlsl", "metal",
    "rules", "webmanifest", "xml_clean",
}


# Get user's preferred terminal width
def get_terminal_width() -> int:
    """Get the current terminal width, with fallback to 80 columns"""
    try:
        width = os.get_terminal_size().columns
        return max(width, 80)  # Minimum of 80 columns
    except (OSError, AttributeError):
        return 80  # Default fallback