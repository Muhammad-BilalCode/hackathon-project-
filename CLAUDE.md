# CLAUDE.md

## Project Overview

`ctxpack` is a Python CLI tool that produces a single best context bundle in Markdown format for an LLM task, strictly within a token budget. It walks a project folder, ranks files by relevance, and assembles the bundle deterministically. Built with Python 3.10+ standard library only — zero external dependencies.

## Build & Execution

### Run the CLI

```powershell
python ctxpack.py --path <folder> --task "<description>" --budget <int>
```

### Common Commands

```powershell
# Basic run (stdout)
python ctxpack.py --path ./my_project --task "summarize the auth module" --budget 2000

# Save bundle to file
python ctxpack.py --path ./my_project --task "summarize the auth module" --budget 2000 --out bundle.md

# Save manifest JSON
python ctxpack.py --path ./my_project --task "summarize the auth module" --budget 2000 --manifest manifest.json

# Verify token count manually (stdlib only)
python -c "import math; print(math.ceil(len(open('bundle.md').read()) / 4))"
```

### Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Invalid arguments |
| `2` | Path not found or unreadable |

## Code Style & Architectural Constraints

- **Standard library only** — No `pip install`, no third-party packages, no network calls.
- **Token counting** — Always use `math.ceil(len(text) / 4)`. Never use an external tokenizer.
- **Exit codes** — `0` success, `1` invalid args, `2` bad path. Never expose raw tracebacks.
- **Deterministic output** — Sorted walk, alphabetical tie-breaking, no timestamps or randomness.
- **Modular layers** — CLI parsing, file walking, ranking logic, bundling, and manifest creation must stay in separate modules/responsibilities.

## Key Files

| File | Role |
|------|------|
| `ctxpack.py` | CLI entry point, argument parsing, orchestration |
| `ranking.py` | Deterministic file-ranking logic |
| `README.md` | User-facing documentation |
| `SPEC.md` | Full specification and constraints |
| `CLAUDE.md` | This file |
| `.gitignore` | Ignored files and directories |

## Scope Rules

- Focus edits strictly on `ctxpack.py` and `ranking.py`.
- Do not generate or depend on non-standard files such as `AGENTS.md`, `PROMPTS.md`, or `JOURNAL.md`.
- Output files (`--out`, `--manifest`) must conform to the Markdown and JSON specification formats in `SPEC.md`.

## Verification

```powershell
# Quick end-to-end check
python ctxpack.py --path . --task "test" --budget 500 --out /tmp/test.md --manifest /tmp/test_manifest.json

# Verify manifest is valid JSON
python -c "import json; json.load(open('/tmp/test_manifest.json')); print('OK')"

# Verify token count of output
python -c "import math; text=open('/tmp/test.md').read(); print(f'Tokens: {math.ceil(len(text)/4)}')"
```