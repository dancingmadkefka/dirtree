# DirTree 🌲

A simple, friendly directory tree tool I made to help visualize project structures and prepare code for AI assistants. Nothing fancy, but it gets the job done!

## What it does

- 📁 Shows directory trees in your terminal with different styles
- 🧠 Has a "smart mode" that automatically hides junk like node_modules and .git
- 🤖 Special LLM export mode that prepares your code for ChatGPT/Claude
- 🎨 Fun stuff like emoji style and file size display
- 🔍 Filter files with simple patterns like "*.py" or "!tests/*"

## Quick Start

```bash
# Basic usage
python dirtree.py

# Interactive mode (recommended for first-timers)
python dirtree.py -i

# Show hidden files
python dirtree.py -H

# Limit depth to 2 levels
python dirtree.py -L 2

# Show file sizes
python dirtree.py --size

# Use emoji style
python dirtree.py --emoji

# Export for AI assistants
python dirtree.py --llm --llm-ext py,md,js
```

## LLM Export Tips

The LLM export mode is great for getting help from AI assistants:

1. Run `python dirtree.py --llm` on your project
2. Upload the generated markdown file to ChatGPT/Claude
3. Ask questions about your code!

## Installation

### Basic Installation

```bash
# Clone it
git clone https://github.com/dancingmadkefka/dirtree.git
cd dirtree

# Install dependencies
pip install pick
# On Windows, also install:
pip install windows-curses
```

### System-wide Installation

To install DirTree so you can run it from anywhere:

```bash
# Clone the repository
git clone https://github.com/dancingmadkefka/dirtree.git
cd dirtree

# Install as an editable package
pip install -e .

# Now you can run from anywhere
dirtree -i
```

### Updating an Existing Installation

If you've already installed DirTree and want to update to the latest version:

```bash
# Navigate to your dirtree directory
cd path/to/dirtree

# Pull the latest changes
git pull

# If you installed as an editable package, no further steps needed!
# The changes are automatically available
```

## License

MIT License - do whatever you want with it! 😊
