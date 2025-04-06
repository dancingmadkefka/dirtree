# IntuitiveDirTree

A user-friendly directory tree generator with advanced filtering and LLM export capabilities.

## Features

- 📁 **Interactive directory selection** - Browse and select directories visually
- 🔍 **Smart filtering** - Automatically excludes common clutter like .git, node_modules
- 🎨 **Multiple tree styles** - Unicode, ASCII, Bold, Emoji and more
- 🤖 **LLM-friendly export** - Generate Markdown files with directory structure and file contents
- 🔧 **Customizable** - Control which files are included in the tree and export

## Installation

### Prerequisites

- Python 3.6 or higher
- The `pick` library (for interactive mode): `pip install pick`
- On Windows, also install `windows-curses` for interactive mode: `pip install windows-curses`

### Installation Options

1. **Clone and run:**
   ```bash
   git clone https://github.com/yourusername/intuitivedirtree.git
   cd intuitivedirtree
   # Run directly
   python dirtree.py -i
   ```

2. **Install as editable package:**
   ```bash
   git clone https://github.com/yourusername/intuitivedirtree.git
   cd intuitivedirtree
   pip install -e .
   # Now you can run from anywhere
   dirtree -i
   ```

## Quick Start

The easiest way to use IntuitiveDirTree is with interactive mode:

```bash
python dirtree.py -i
```

This will guide you through:
1. Selecting a directory
2. Filtering options
3. Display settings
4. LLM export settings

## Command Line Options

### Basic Usage

```bash
python dirtree.py [directory] [options]
```

### Common Options

- `-i, --interactive`: Use interactive setup (recommended)
- `-L, --llm`: Generate LLM-friendly export with file contents
- `--size`: Show file sizes in the tree
- `-H, --hidden`: Show hidden files (starting with '.')
- `-s, --style {unicode,ascii,bold,rounded,emoji,minimal}`: Choose tree style
- `-v, --verbose`: Show detailed logging

### Filtering Options

- `-I, --include PATTERN`: Include files matching glob pattern (can use multiple times)
- `-E, --exclude PATTERN`: Exclude files matching glob pattern (can use multiple times)
- `--no-smart-exclude`: Disable automatic exclusion of .git, node_modules, etc.

### LLM Export Options

- `--llm-max-size SIZE`: Maximum size per file, e.g., '50k', '1m' (default: 100k)
- `--llm-ext EXT`: Specific file extensions to include in LLM export (without '.')
- `--llm-output-dir DIR`: Directory to save the export file

For a complete list of options:
```bash
python dirtree.py --help
```

## Examples

### Generate tree for current directory:
```bash
python dirtree.py
```

### Interactive mode (recommended for first-time users):
```bash
python dirtree.py -i
```

### Generate tree with custom filtering:
```bash
python dirtree.py ~/projects/myproject --include "*.py" --include "*.js" --exclude "test_*"
```

### Generate tree with LLM export for Python files only:
```bash
python dirtree.py ~/projects/myproject -L --llm-ext py
```

### Show a minimal tree with file sizes:
```bash
python dirtree.py --style minimal --size
```

## Tips for Using with LLMs

1. **Filter effectively**: Use the interactive mode to select which file types to include.

2. **Mind the context limits**: Most LLMs have context limits. Use `--llm-max-size` to limit file sizes and be selective about which files to include.

3. **Upload the generated file**: After generating the LLM export, upload the Markdown file to your LLM of choice (Claude, ChatGPT, etc.) or copy and paste its contents.

4. **Ask good questions**: With your codebase loaded, you can ask the LLM questions like:
   - "Explain how this codebase works"
   - "What improvements would you suggest for this code?"
   - "Help me understand the relationship between these modules"

## Troubleshooting

- **'pick' not found errors**: Run `pip install pick` (and `pip install windows-curses` on Windows)
- **Permission errors**: Try running with admin/root privileges for protected directories
- **Export too large**: Use filtering options to limit which files are included
