# ctxpack Plan

## File layout

```
ctxpack.py        # CLI entry point, argparse, pipeline orchestration
ranking.py        # Isolated ranking function (swappable algorithm)
```

Two files keep things reviewable and let us swap ranking without touching the rest of the pipeline. Noise detection and truncation live as separate, testable functions inside `ctxpack.py` — not buried in a class.

## Function list

| Function | Module | Purpose |
|---|---|---|
| `parse_args()` | `ctxpack.py` | argparse setup + validation; exits cleanly on bad input |
| `walk_files(path)` | `ctxpack.py` | Sorted recursive walk, returns relative paths |
| `is_noise(rel_path)` | `ctxpack.py` | Layered noise detection (structural → pattern → heuristic); returns `(bool, reason)` |
| `read_file_content(path)` | `ctxpack.py` | UTF-8 decode with binary/fallback handling |
| `count_tokens(text)` | `ctxpack.py` | `math.ceil(len(text) / 4)` |
| `rank_files(files, task)` | `ranking.py` | Weighted keyword overlap + depth penalty + alphabetical tie-break |
| `pack_files(ranked, task, budget)` | `ctxpack.py` | Greedy selection with truncation policy and budget enforcement |
| `build_tree_overview(files)` | `ctxpack.py` | Lightweight directory tree for leftover slack |
| `build_bundle(included, task, tree)` | `ctxpack.py` | Assemble the final markdown string |
| `write_outputs(bundle, manifest, out, manifest_out)` | `ctxpack.py` | Write files or stdout/stderr |
| `main()` | `ctxpack.py` | Orchestrate pipeline; top-level exception guard |

## Pipeline order

1. Parse args → validate
2. Walk + filter noise
3. Read file contents
4. Rank files
5. Pack files into budget (greedy selection with truncation policy)
6. If slack remains, optionally add tree overview (capped at 200 tokens)
7. Build final bundle string
8. Count actual tokens of bundle (hard constraint — must not exceed budget)
9. Write outputs + manifest

## Design decisions (judgment calls where SPEC was vague)

1. **Truncation hard floor** — SPEC says "roughly under 50 tokens." Using exactly **50** as the floor. A fragment smaller than that is unusable, and SPEC says to skip instead.
2. **Depth penalty formula** — SPEC says "modest." Using `1 / (1 + depth)` which is gentle (root=1.0, depth 1=0.5, depth 2=0.33, etc.) and never goes to zero.
3. **Content score cap** — SPEC says so a long file can't win purely on volume. Capping content score at `len(task_tokens) * 2` (twice the number of task keywords). A file can at most get credit for matching each task keyword twice in its content.
4. **Tree overview token cap** — SPEC says "roughly ~200 tokens." Using exactly **200** as the ceiling.
5. **Stopwords** — SPEC says "stripping stopwords and punctuation" but does not define the list. Using a minimal hardcoded set of ~30 common English stopwords. This is a judgment call because SPEC leaves it open.
6. **Manifest `reason` for included files** — SPEC gives an example reason `"high task-keyword overlap in path and content"`. Generating one of a few predefined reason strings based on match type (path-only, content-only, both). A judgment call on granularity vs. simplicity.
7. **Non-UTF-8 files** — SPEC says skip with a reason. Excluding them with reason `"binary or non-UTF-8 encoding (decoded failed)"`. Heuristic layer also catches files with null bytes or high non-printable ratio.
8. **Tree overview inclusion** — SPEC Section 7 says to include a directory tree only when slack remains after packing, capped at ~200 tokens. Implemented as conditional inclusion after all ranked files are packed.

## Ranking strategy details (spec §4)

- Tokenize `--task` into lowercase words, stripping stopwords and punctuation.
- Score = (path_matches × 3) + (content_matches, capped), minus depth penalty.
- PathMatches: count of task tokens found as substrings of the file's relative path (case-insensitive).
- ContentMatches: count of task tokens found in the file's text content, capped at `len(task_tokens) * 2` so a very long file doesn't dominate.
- DepthPenalty: `1 / (1 + depth)` multiplier applied to the total score.
- Sort by score descending, then alphabetically by path for ties.

## Truncation policy details (spec §5)

- If a file's full token cost ≤ remaining budget, include it whole.
- If full file doesn't fit but remaining budget ≥ 50 tokens, include the first N lines that fit, flag as truncated in the bundle, record actual token count.
- If remaining budget < 50 tokens, skip the file entirely with reason "insufficient remaining budget".

## Noise detection layers (spec §6)

1. **Structural**: skip directories named `.git`, `node_modules`, `__pycache__`, `.venv`, `venv`, `dist`, `build`, `.next`, `target`.
2. **Pattern-based**: skip files ending in `.lock`, `-lock.json`, `.min.js`, `.min.css`, plus basenames `package-lock.json`, `yarn.lock`, `Pipfile.lock`, `Cargo.lock`, `poetry.lock`.
3. **Heuristic**: skip files that fail UTF-8 decode, contain a null byte in first 8KB, or have a non-printable/printable ratio above a threshold (0.30).

Each layer runs in order and a file excluded at any layer gets the reason from the first matching layer.
