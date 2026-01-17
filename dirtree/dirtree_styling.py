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
    GRAY = "\033[90m" # Bright black, often used for gray

class TreeStyle:
    """Definitions for different tree drawing styles."""
    ASCII: Dict[str, str] = {"branch": "|   ", "tee": "|-- ", "last_tee": "`-- ", "empty": "    "}
    UNICODE: Dict[str, str] = {"branch": "│   ", "tee": "├── ", "last_tee": "└── ", "empty": "    "}
    BOLD: Dict[str, str] = {"branch": "┃   ", "tee": "┣━━ ", "last_tee": "┗━━ ", "empty": "    "}
    ROUNDED: Dict[str, str] = {"branch": "│   ", "tee": "├── ", "last_tee": "╰── ", "empty": "    "}
    # EMOJI style uses standard connectors but prepends emojis based on file/dir type
    EMOJI: Dict[str, str] = {
        "branch": "│   ", "tee": "├── ", "last_tee": "└── ", "empty": "    ",
        # Special dir_tee/dir_last_tee can be used if a style wants different connectors for dirs
        # For emoji style, they are typically the same as tee/last_tee as emoji is prepended.
        "dir_tee": "├── ", 
        "dir_last_tee": "└── "
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
        """Gets the style config, defaulting to unicode, ensuring all keys exist."""
        default_style = TreeStyle.UNICODE.copy() # Use a copy
        selected_style_template = TreeStyle.AVAILABLE.get(style_name.lower())

        if selected_style_template:
            # Merge selected style with default to ensure all keys are present
            # Selected style's values take precedence
            final_style = default_style.copy()
            final_style.update(selected_style_template)
            return final_style
        else:
            return default_style


# --- Default Colors/Emojis ---
DEFAULT_FILETYPE_COLORS: Dict[str, str] = {
    "dir": Colors.BLUE + Colors.BOLD,
    "py": Colors.GREEN, "pyw": Colors.GREEN,
    "js": Colors.YELLOW, "jsx": Colors.YELLOW, "mjs": Colors.YELLOW,
    "ts": Colors.CYAN, "tsx": Colors.CYAN, # Changed TS to Cyan for distinctness
    "html": Colors.MAGENTA, "htm": Colors.MAGENTA,
    "css": Colors.BLUE, "scss": Colors.BLUE, "sass": Colors.BLUE, # Changed CSS to Blue
    "java": Colors.RED, "class": Colors.RED,
    "c": Colors.GREEN, "h": Colors.GREEN, # Changed C to Green
    "cpp": Colors.GREEN, "hpp": Colors.GREEN, "hxx": Colors.GREEN,
    "cs": Colors.MAGENTA, # Changed C# to Magenta
    "go": Colors.CYAN,
    "rb": Colors.RED,
    "php": Colors.MAGENTA,
    "swift": Colors.YELLOW,
    "kt": Colors.MAGENTA, "kts": Colors.MAGENTA,
    "rs": Colors.YELLOW,
    "sh": Colors.GREEN, "bash": Colors.GREEN, "zsh": Colors.GREEN,
    "ps1": Colors.BLUE, "psm1": Colors.BLUE,
    "bat": Colors.GRAY, "cmd": Colors.GRAY,
    "json": Colors.YELLOW,
    "yaml": Colors.YELLOW, "yml": Colors.YELLOW,
    "xml": Colors.MAGENTA,
    "toml": Colors.YELLOW,
    "ini": Colors.WHITE, "cfg": Colors.WHITE, "conf": Colors.WHITE,
    "csv": Colors.CYAN,
    "sql": Colors.BLUE,
    "md": Colors.YELLOW, "markdown": Colors.YELLOW,
    "rst": Colors.YELLOW,
    "txt": Colors.WHITE,
    "log": Colors.GRAY,
    "zip": Colors.RED, "rar": Colors.RED, "7z": Colors.RED,
    "tar": Colors.RED, "gz": Colors.RED, "bz2": Colors.RED, "xz": Colors.RED,
    "exe": Colors.GREEN + Colors.BOLD, "msi": Colors.GREEN,
    "deb": Colors.RED, "rpm": Colors.RED,
    "png": Colors.MAGENTA, "jpg": Colors.MAGENTA, "jpeg": Colors.MAGENTA,
    "gif": Colors.MAGENTA, "bmp": Colors.MAGENTA, "ico": Colors.MAGENTA,
    "svg": Colors.MAGENTA, "webp": Colors.MAGENTA,
    "mp3": Colors.CYAN, "wav": Colors.CYAN, "ogg": Colors.CYAN,
    "mp4": Colors.MAGENTA, "avi": Colors.MAGENTA, "mkv": Colors.MAGENTA, "mov": Colors.MAGENTA,
    "pdf": Colors.RED,
    "doc": Colors.BLUE, "docx": Colors.BLUE,
    "xls": Colors.GREEN, "xlsx": Colors.GREEN,
    "ppt": Colors.YELLOW, "pptx": Colors.YELLOW,
    "iso": Colors.RED, "img": Colors.RED,
    "dockerfile": Colors.BLUE, 
    "tf": Colors.MAGENTA,
}

DEFAULT_FILETYPE_EMOJIS: Dict[str, str] = {
    "py": "🐍", "pyw": "🐍",
    "js": "📜", "jsx": "⚛️", "mjs": "📜",
    "ts": "📜", "tsx": "⚛️",
    "html": "🌐", "htm": "🌐",
    "css": "🎨", "scss": "🎨", "sass": "🎨",
    "java": "☕", "class": "☕",
    "c": "🔧", "h": "🔧",
    "cpp": "🔧", "hpp": "🔧", "hxx": "🔧",
    "cs": "✨",
    "go": "🐹",
    "rb": "💎",
    "php": "🐘",
    "swift": "🐦",
    "kt": "💜", "kts": "💜",
    "rs": "🦀",
    "sh": "⚙️", "bash": "⚙️", "zsh": "⚙️",
    "ps1": "💻", "psm1": "💻",
    "bat": "💻", "cmd": "💻",
    "json": "📦",
    "yaml": "📦", "yml": "📦",
    "xml": "📰",
    "toml": "🔩", "ini": "🔩", "cfg": "🔩", "conf": "🔩",
    "csv": "📊",
    "sql": "🗃️", "db": "🗃️", "sqlite": "🗃️",
    "md": "📝", "markdown": "📝", "rst": "📝",
    "txt": "📄", "pdf": "📕", "log": "📜",
    "zip": "📦", "rar": "📦", "7z": "📦", "tar": "📦", "gz": "📦", "bz2": "📦", "xz": "📦",
    "exe": "🚀", "msi": "🚀", "deb": "📦", "rpm": "📦",
    "png": "🖼️ ", "jpg": "🖼️ ", "jpeg": "🖼️ ", "gif": "🖼️ ", "bmp": "🖼️ ", "ico": "🖼️ ", "svg": "🎨", "webp": "🖼️ ", # Note space for image emojis
    "mp3": "🎵", "wav": "🎵", "ogg": "🎵",
    "mp4": "🎬", "avi": "🎬", "mkv": "🎬", "mov": "🎬",
    "doc": "📄", "docx": "📄", "xls": "📊", "xlsx": "📊", "ppt": "📊", "pptx": "📊",
    "iso": "📀", "img": "📀", "lock": "🔒", "key": "🔑",
    "dockerfile": "🐳", "tf": "🏗️ ",
}