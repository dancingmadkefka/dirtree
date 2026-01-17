# DirTree

A directory tree generator with smart filtering and LLM-friendly export.

## Features

- **Smart filtering** - Automatically excludes `.git`, `node_modules`, and other clutter
- **LLM export** - Generate markdown files with directory structure and file contents for AI assistants
- **Multiple styles** - Unicode, ASCII, bold, rounded, emoji, and minimal tree formats
- **File size display** - See file sizes at a glance
- **Pattern filtering** - Include/exclude files with glob patterns
- **Interactive mode** - Browse and select directories visually

## Requirements

- Python 3.8 or higher

## Installation

```bash
git clone https://github.com/dancingmadkefka/dirtree.git
cd dirtree
pip install -e .
```

On Windows, also install `windows-curses` for interactive mode:
```bash
pip install windows-curses
```

## Quick Start

```bash
# Interactive mode (recommended)
dirtree -i

# Basic tree
dirtree

# Limit depth
dirtree -d 2

# Show file sizes
dirtree --size

# Show hidden files
dirtree -H

# Export for LLM (Python and Markdown files only)
dirtree --llm --llm-ext py,md
```

For all options:
```bash
dirtree --help
```

## LLM Export

Generate a markdown file with your directory structure and file contents, ready for AI assistants:

```bash
# Export with default settings
dirtree --llm

# Limit file size
dirtree --llm --llm-max-size 50k

# Only include specific extensions
dirtree --llm --llm-ext py,js,ts
```

Upload the generated `.md` file to ChatGPT, Claude, or your preferred AI assistant.

## License

MIT
