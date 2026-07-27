# ctxpack

A deterministic, offline Python CLI tool that builds the single best context bundle for an LLM task — strictly within a token budget. Point it at a project folder, describe what you need, set a token limit, and ctxpack walks the tree, ranks every file by relevance, and assembles a Markdown bundle that fits.

## Key Features

- **Strict token budget** — The output never exceeds `--budget` tokens (counted as `math.ceil(len(text) / 4)`).
- **Deterministic ranking** — Files are scored by structural, pattern, and heuristic signal and tie-broken alphabetically. No randomness, no external model calls.
- **Standard library only** — Zero dependencies. Runs on Python 3.10+ with `pip install` unnecessary and network calls unnecessary.
- **Offline execution** — No API keys, no internet, no third-party tokenizers. Fully self-contained.
- **Manifest output** — A JSON manifest records every file considered, included or excluded, along with the reason for each decision.

## Installation & Requirements

- **Python** 3.10 or newer
- **No pip install required** — no third-party packages

```powershell
# Clone the repo
git clone <repo-url>
cd ctxpack

# Verify the tool runs
python ctxpack.py --help
```

## Usage & Examples

### Basic run (stdout)

```powershell
python ctxpack.py --path ./my_project --task "summarize the authentication module" --budget 2000
```

### Save bundle to a file

```powershell
python ctxpack.py --path ./my_project --task "summarize the auth module" --budget 2000 --out bundle.md
```

### Save a manifest JSON

```powershell
python ctxpack.py --path ./my_project --task "summarize the auth module" --budget 2000 --manifest manifest.json
```

### Combine output and manifest

```powershell
python ctxpack.py --path ./my_project --task "review error handling" --budget 5000 --out context.md --manifest context_manifest.json
```

### Exit codes

| Code | Meaning |
|------|---------|
| `0`  | Success |
| `1`  | Invalid arguments |
| `2`  | Path not found or unreadable |

## Manifest Schema

The manifest is a single-line JSON object (when written to stderr defaults; when written to file, pretty-printed):

```json
{
  "budget": 2000,
  "tokens_used": 1847,
  "within_budget": true,
  "files_included": [
    {
      "path": "src/auth.py",
      "tokens": 412,
      "rank_score": 0.93,
      "reason": "high keyword match & small file"
    }
  ],
  "files_excluded": [
    {
      "path": "tests/test_auth.py",
      "tokens": 320,
      "rank_score": 0.41,
      "reason": "low relevance to task description"
    }
  ]
}
```

## File & Folder Structure

```
ctxpack/
├── ctxpack.py          Main CLI entry point and bundle builder
├── ranking.py          Deterministic file-ranking logic
├── SPEC.md             Full specification and constraints
├── CLAUDE.md           Agent instructions for this repo
├── README.md           This file
├── .gitignore          Ignored files and directories
├── venv/               Virtual environment (gitignored)
├── out.md              Example generated bundle (gitignored)
└── manifest.json       Example manifest output (gitignored)
```

## Verification / Tests

Run a quick end-to-end check in under a minute:

```powershell
# 1. Basic pack — should exit 0 and print a Markdown bundle to stdout
python ctxpack.py --path . --task "show me the ranking logic" --budget 1000

# 2. Save to file and verify it exists
python ctxpack.py --path . --task "show me the ranking logic" --budget 1000 --out /tmp/test_bundle.md
Test-Path /tmp/test_bundle.md

# 3. Generate a manifest and check it is valid JSON
python ctxpack.py --path . --task "show me the ranking logic" --budget 1000 --manifest /tmp/test_manifest.json
python -c "import json; json.load(open('/tmp/test_manifest.json')); print('manifest OK')"
```