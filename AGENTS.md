# AGENTS.md

> **AI Agent Reference Guide** — Context for AI agents working on this codebase.

## Related Documents
- [CLAUDE.md](CLAUDE.md) - Technical reference for all AI agents
- [README.md](README.md) - User-facing documentation

---

## Project Context

**What**: Directory tree generator with advanced filtering and LLM-friendly export
**Stack**: Python 3.8+, argparse, pick (optional)
**Purpose**: Visualize project structures and prepare code for AI assistants

---

## Architecture

```
dirtree.py → dirtree_cli.py → IntuitiveDirTree (dirtree_core.py)
                                    ↓
                        ┌───────────┼───────────┐
                        ↓           ↓           ↓
                  filters      styling      LLM export
```

**Key concept**: Dual filtering - tree display filters (what shows visually) are separate from LLM content filters (what file content gets exported).

---

## Key Files

| File | Purpose |
|------|---------|
| `dirtree/dirtree_core.py` | `IntuitiveDirTree` - main orchestrator |
| `dirtree/dirtree_filters.py` | `passes_tree_filters()` - core filtering logic |
| `dirtree/dirtree_llm.py` | `LlmExporter` - markdown generation |
| `dirtree/dirtree_config.py` | Smart exclude patterns |
| `tests/conftest.py` | Test fixtures |

---

## Quick Troubleshooting

| Issue | Solution |
|-------|----------|
| Pick library errors | `pip install pick` |
| Windows interactive broken | `pip install windows-curses` |
| Import errors | `pip install -e .` |

---

**Last updated**: 2025-01-18
