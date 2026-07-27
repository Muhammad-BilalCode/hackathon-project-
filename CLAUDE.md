# CLAUDE.md

## Project Overview

`ctxpack` is a Python CLI tool that ingests a codebase, a task description, and a token budget, then outputs the best achievable context bundle for an AI coding assistant — along with a truthful manifest listing what was left out and why. The repository is in **spec/implementation phase**; `SPEC.md` is the authoritative specification and `ctxpack.py` contains the working implementation.

## Tech Stack

- **Python 3.10+**, standard library only — no `pip install`, no third-party packages, no network calls.
- Two source files: `ctxpack.py` (CLI entry point, bundle assembly, noise detection) and `ranking.py` (tokenization, scoring, ranking).

## Commands

| Command | Description |
|---|---|
| `python ctxpack.py --path <folder> --task "<task>" --budget <int>` | Pack a context bundle |
| `python ctxpack.py --path <folder> --task "<task>" --budget <int> --out <file>` | Write bundle to file |
| `python ctxpack.py --path <folder> --task "<task>" --budget <int> --manifest <file>` | Write manifest JSON to file |

Flags: `--path` (required, folder to pack), `--task` (required, task description), `--budget` (required, positive integer), `--out` (optional, output file), `--manifest` (optional, manifest JSON file).

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Invalid arguments |
| `2` | `--path` does not exist, is not a directory, or is not readable |

All errors produce exactly one plain-language line to stderr — never a raw traceback.

## Coding Standards

- **Modular functions** with clear single responsibilities; each function does one thing and is named descriptively.
- **Constants** in `SCREAMING_SNAKE_CASE` (e.g. `NOISE_DIRS`, `TRUNCATION_FLOOR_TOKENS`).
- **Determinism everywhere**: file walks are sorted before scoring; ranking ties are broken alphabetically by path. No timestamps, random IDs, or set/dict-order-dependent values.
- **Token counting**: `math.ceil(len(text) / 4)` — no tokenizer libraries.
- **Imports**: stdlib `argparse`, `json`, `math`, `os`, `sys` at the top of `ctxpack.py`; `ranking.py` imports `os` and `string`.

## Key Architecture

- **Noise detection** is layered: structural (directory names like `.git`, `__pycache__`, `node_modules`), pattern-based (lockfiles, `.min.js`, `.min.css`), and heuristic (UTF-8 decode failure, null bytes, non-printable ratio). Files are excluded at the walk stage before scoring.
- **Ranking**: weighted keyword overlap between `--task` and each file's path (3x) plus content (1x, capped), adjusted by a depth penalty favoring root-level files. Ties broken alphabetically.
- **Truncation**: oversized files may be included as a head slice (first N lines fitting the remaining budget) rather than dropped entirely. Files are skipped entirely if remaining budget is below the floor (~50 tokens).
- **Budget spending**: a lightweight project-structure tree overview is included only when budget slack remains after packing ranked files, capped at ~200 tokens.
- **Manifest schema**: `{ budget, used, included: [{path, tokens, reason}], excluded: [{path, reason}] }` — every file appears in exactly one list with a recorded reason.

## File Roles

| File | Role |
|---|---|
| `ctxpack.py` | CLI entry point, argument parsing, walking, noise detection, bundle assembly, manifest output |
| `ranking.py` | Tokenization, scoring function, ranking logic |
| `SPEC.md` | Single source of truth for `ctxpack` behavior |
| `AGENTS.md` | Agent instructions for this repo |
| `.agents/skills/` | OpenCode skills (e.g. `dataverse-python-production-code`) |

## Error Handling

- Missing required flags or non-positive `--budget` → exit 1, one-line stderr message.
- Bad `--path` → exit 2, one-line stderr message.
- Unexpected internal errors are caught at the top level (`if __name__ == "__main__"` try/except) and converted to exit 1 with a one-line stderr message — never a raw traceback.

## Workspace Notes

- The workspace path contains spaces (`D:\hackathon class work`). Always quote paths in shell commands.
- `README.md` is an empty placeholder — do not treat it as spec.
- No `opencode.json` exists at the repo root.