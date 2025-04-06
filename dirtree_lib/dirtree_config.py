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
        config = {}
        if config_file.exists():
            try:
                config = json.loads(config_file.read_text(encoding='utf-8'))
            except Exception:
                pass  # Start fresh if the file is corrupted
        
        # Update with new default directory
        config['default_dir'] = str(Path(directory).resolve())
        
        # Write back to file
        config_file.write_text(json.dumps(config, indent=2), encoding='utf-8')
    except Exception as e:
        print(f"Warning: Error saving default directory: {e}")

def save_config(config: Dict[str, Any]) -> None:
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
        save_keys = {
            'style', 'max_depth', 'show_hidden', 'colorize', 'show_size',
            'use_smart_exclude', 'export_for_llm', 'max_llm_file_size',
            'llm_content_extensions', 'verbose', 'skip_errors'
        }
        # Update only allowed keys
        for key in save_keys:
            if key in config:
                existing_config[key] = config[key]
        
        # Write back to file
        config_file.write_text(json.dumps(existing_config, indent=2), encoding='utf-8')
    except Exception as e:
        print(f"Warning: Error saving configuration: {e}")

# --- Constants ---

# Common directories and files to automatically ignore (Smart Exclude)
COMMON_EXCLUDES: List[str] = [
    # Version control
    ".git", ".svn", ".hg", ".gitignore", ".gitattributes", ".gitmodules",
    # Node.js
    "node_modules", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    # Python
    "__pycache__", "*.pyc", "*.pyo", "venv", "env", ".venv", ".env",
    "*.egg-info", "dist", "build", "htmlcov", ".pytest_cache", ".mypy_cache",
    # IDE and editor files
    ".idea", ".vscode", ".vs", ".DS_Store", "Thumbs.db",
    # Common build directories
    ".next", "out", "coverage", "bin", "obj", "target",
    # Temporary and log files
    "data", "*.log", "logs", "tmp", "temp", ".env.*", ".envrc", "__MACOSX",
]

# File extensions generally considered "binary" or not useful for LLM text context.
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
    "iso", "img", "swf", "dat", "pickle", "pkl", "model", "pt", "onnx", "lock",
}

# Default extensions to include in LLM exports (common code and text files)
DEFAULT_LLM_INCLUDE_EXTENSIONS: Set[str] = {
    # Programming languages
    "py", "pyw", "js", "jsx", "ts", "tsx", "java", "c", "cpp", "h", "hpp", 
    "cs", "go", "rb", "php", "swift", "kt", "rs", "sh", "bash", "zsh",
    "ps1", "bat", "cmd", 
    # Config and data formats
    "json", "yaml", "yml", "xml", "toml", "ini", "cfg", "conf", "csv",
    # Markup and documentation
    "md", "markdown", "rst", "txt", "html", "htm", "css", "scss", "sass",
    # SQL and database
    "sql",
    # Other text formats
    "log", "gitignore",
}

# Get user's preferred terminal width
def get_terminal_width() -> int:
    """Get the current terminal width, with fallback to 80 columns"""
    try:
        width = os.get_terminal_size().columns
        return max(width, 80)  # Minimum of 80 columns
    except (OSError, AttributeError):
        return 80  # Default fallback