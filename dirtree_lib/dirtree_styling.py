# -*- coding: utf-8 -*-
"""
Styling definitions (colors, tree styles, emojis) for IntuitiveDirTree.
"""

from typing import Dict

# --- Styling ---

class Colors:
    """ANSI color codes for terminal output."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    GRAY = "\033[90m"

class TreeStyle:
    """Definitions for different tree drawing styles."""
    ASCII: Dict[str, str] = {"branch": "|   ", "tee": "|-- ", "last_tee": "`-- ", "empty": "    "}
    UNICODE: Dict[str, str] = {"branch": "│   ", "tee": "├── ", "last_tee": "└── ", "empty": "    "}
    BOLD: Dict[str, str] = {"branch": "┃   ", "tee": "┣━━ ", "last_tee": "┗━━ ", "empty": "    "}
    ROUNDED: Dict[str, str] = {"branch": "│   ", "tee": "├── ", "last_tee": "╰── ", "empty": "    "}
    # Updated EMOJI style - make sure all necessary keys are present
    EMOJI: Dict[str, str] = {
        "branch": "┃   ", 
        "tee": "├── ", 
        "last_tee": "└── ", 
        "empty": "    ", 
        "dir_tee": "📂 ",  # for directories that aren't last
        "dir_last_tee": "📂 "  # for directories that are last
    }
    MINIMAL: Dict[str, str] = {"branch": "  ", "tee": "- ", "last_tee": "- ", "empty": "  "}

    AVAILABLE: Dict[str, Dict[str, str]] = {
        "ascii": ASCII,
        "unicode": UNICODE,
        "bold": BOLD,
        "rounded": ROUNDED,
        "emoji": EMOJI,
        "minimal": MINIMAL
    }

    @staticmethod
    def get_style(style_name: str) -> Dict[str, str]:
        """Gets the style config, defaulting to unicode."""
        default_style = TreeStyle.UNICODE
        selected_style = TreeStyle.AVAILABLE.get(style_name.lower(), default_style)
        
        # Ensure all styles have the basic required keys
        required_keys = ["branch", "tee", "last_tee", "empty"] 
        for key in required_keys:
            if key not in selected_style:
                # Copy from the default style if missing
                selected_style[key] = default_style[key]
                
        return selected_style

# --- Default Colors/Emojis ---
# Moved from IntuitiveDirTree class to be module-level constants

DEFAULT_FILETYPE_COLORS: Dict[str, str] = {
    "dir": Colors.BLUE + Colors.BOLD,
    "py": Colors.GREEN, 
    "pyw": Colors.GREEN,
    "js": Colors.YELLOW, 
    "jsx": Colors.YELLOW,
    "ts": Colors.BLUE, 
    "tsx": Colors.BLUE,
    "html": Colors.MAGENTA, 
    "htm": Colors.MAGENTA,
    "css": Colors.CYAN, 
    "scss": Colors.CYAN, 
    "sass": Colors.CYAN,
    "java": Colors.RED, 
    "class": Colors.RED,
    "c": Colors.BLUE, 
    "h": Colors.BLUE,
    "cpp": Colors.BLUE, 
    "hpp": Colors.BLUE, 
    "hxx": Colors.BLUE,
    "cs": Colors.GREEN,
    "go": Colors.CYAN,
    "rb": Colors.RED,
    "php": Colors.MAGENTA,
    "swift": Colors.YELLOW,
    "kt": Colors.MAGENTA, 
    "kts": Colors.MAGENTA,
    "rs": Colors.YELLOW,
    "sh": Colors.GREEN, 
    "bash": Colors.GREEN, 
    "zsh": Colors.GREEN,
    "ps1": Colors.BLUE, 
    "psm1": Colors.BLUE,
    "bat": Colors.BLUE, 
    "cmd": Colors.BLUE,
    "json": Colors.YELLOW,
    "yaml": Colors.YELLOW, 
    "yml": Colors.YELLOW,
    "xml": Colors.MAGENTA,
    "toml": Colors.YELLOW,
    "ini": Colors.WHITE,
    "cfg": Colors.WHITE, 
    "conf": Colors.WHITE,
    "csv": Colors.CYAN,
    "sql": Colors.BLUE,
    "md": Colors.YELLOW, 
    "markdown": Colors.YELLOW,
    "rst": Colors.YELLOW,
    "txt": Colors.WHITE,
    "log": Colors.GRAY,
    "zip": Colors.RED, 
    "rar": Colors.RED, 
    "7z": Colors.RED,
    "tar": Colors.RED, 
    "gz": Colors.RED, 
    "bz2": Colors.RED, 
    "xz": Colors.RED,
    "exe": Colors.GREEN + Colors.BOLD, 
    "msi": Colors.GREEN,
    "deb": Colors.RED, 
    "rpm": Colors.RED,
    "png": Colors.MAGENTA, 
    "jpg": Colors.MAGENTA, 
    "jpeg": Colors.MAGENTA,
    "gif": Colors.MAGENTA, 
    "bmp": Colors.MAGENTA, 
    "ico": Colors.MAGENTA,
    "svg": Colors.MAGENTA, 
    "webp": Colors.MAGENTA,
    "mp3": Colors.CYAN, 
    "wav": Colors.CYAN, 
    "ogg": Colors.CYAN,
    "mp4": Colors.MAGENTA, 
    "avi": Colors.MAGENTA, 
    "mkv": Colors.MAGENTA, 
    "mov": Colors.MAGENTA,
    "pdf": Colors.RED,
    "doc": Colors.BLUE, 
    "docx": Colors.BLUE,
    "xls": Colors.GREEN, 
    "xlsx": Colors.GREEN,
    "ppt": Colors.YELLOW, 
    "pptx": Colors.YELLOW,
    "iso": Colors.RED, 
    "img": Colors.RED,
    "dockerfile": Colors.BLUE, 
    "tf": Colors.MAGENTA,
}

DEFAULT_FILETYPE_EMOJIS: Dict[str, str] = {
    "py": "🐍", 
    "pyw": "🐍",
    "js": "📜", 
    "jsx": "⚛️",
    "ts": "📜", 
    "tsx": "⚛️",
    "html": "🌐", 
    "htm": "🌐",
    "css": "🎨", 
    "scss": "🎨", 
    "sass": "🎨",
    "java": "☕", 
    "class": "☕",
    "c": "🔧", 
    "h": "🔧",
    "cpp": "🔧", 
    "hpp": "🔧", 
    "hxx": "🔧",
    "cs": "✨",
    "go": "🐹",
    "rb": "💎",
    "php": "🐘",
    "swift": "🐦",
    "kt": "💜", 
    "kts": "💜",
    "rs": "🦀",
    "sh": "⚙️", 
    "bash": "⚙️", 
    "zsh": "⚙️",
    "ps1": "💻", 
    "psm1": "💻",
    "bat": "💻", 
    "cmd": "💻",
    "json": "📦",
    "yaml": "📦", 
    "yml": "📦",
    "xml": "📰",
    "toml": "🔩",
    "ini": "🔩",
    "cfg": "🔩", 
    "conf": "🔩",
    "csv": "📊",
    "sql": "🗃️",
    "db": "🗃️", 
    "sqlite": "🗃️",
    "md": "📝", 
    "markdown": "📝",
    "rst": "📝",
    "txt": "📄",
    "pdf": "📕",
    "log": "📜",
    "zip": "📦", 
    "rar": "📦", 
    "7z": "📦",
    "tar": "📦", 
    "gz": "📦", 
    "bz2": "📦", 
    "xz": "📦",
    "exe": "🚀", 
    "msi": "🚀",
    "deb": "📦", 
    "rpm": "📦",
    "png": "🖼️", 
    "jpg": "🖼️", 
    "jpeg": "🖼️",
    "gif": "🖼️", 
    "bmp": "🖼️", 
    "ico": "🖼️",
    "svg": "🎨", 
    "webp": "🖼️",
    "mp3": "🎵", 
    "wav": "🎵", 
    "ogg": "🎵",
    "mp4": "🎬", 
    "avi": "🎬", 
    "mkv": "🎬", 
    "mov": "🎬",
    "doc": "📄", 
    "docx": "📄",
    "xls": "📊", 
    "xlsx": "📊",
    "ppt": "📊", 
    "pptx": "📊",
    "iso": "📀", 
    "img": "📀",
    "lock": "🔒",
    "key": "🔑",
    "dockerfile": "🐳", 
    "tf": "🏗️",
}