# SPEC.md — ctxpack

## 1. Purpose

`ctxpack` is a Python command-line tool that ingests a codebase, a task
description, and a token budget, then outputs the best achievable context
bundle for an AI coding assistant — along with a truthful manifest listing
what was left out and why. Its goal is to replace manual, ad-hoc file
picking with a deterministic, explainable process.

---

## 2. CLI Contract

```
ctxpack --path <folder> --task "<task description>" --budget <int> [--out <file>] [--manifest <file>]
```

| Flag | Required | Behavior |
|---|---|---|
| `--path` | Yes | Folder to pack. Must exist and be readable. |
| `--task` | Yes | Free-text description of the developer's goal. Used to rank files. |
| `--budget` | Yes | Positive integer. Max tokens for the **entire** bundle output. |
| `--out` | No | Path to write the bundle. If omitted, bundle is written to stdout. |
| `--manifest` | No | Path to write manifest JSON. If omitted, a one-line summary is printed to stderr. |

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Success. |
| `1` | Invalid arguments (e.g. missing required flag, non-integer or non-positive `--budget`, unparsable input). |
| `2` | `--path` does not exist, is not a directory, or is not readable. |

For exit codes 1 and 2, `ctxpack` writes exactly one plain-language line to
stderr explaining the issue. It never surfaces a raw Python traceback.

---

## 3. Token Counting

```python
tokens = math.ceil(len(text) / 4)
```

This formula is applied to the **entire bundle as written** — headers,
file-path labels, separator lines, and any tree/structure diagram —
not only the raw file contents. The manifest's `used` field reflects the
token count of the exact bytes sent to `--out` (or stdout).

No tokenizer libraries and no API calls are used. This keeps the counting
method identical across every team and every run.

---

## 4. Ranking Strategy

**Method chosen: weighted keyword overlap between `--task` and each file's
path plus content, adjusted by directory depth.**

For each candidate file:

1. Tokenize `--task` into lowercase words, stripping stopwords and
   punctuation.
2. Score = (matches in the file's relative path, weighted 3x) + (matches
   in the file's content, weighted 1x, with a cap so a single very long
   file can't win purely on volume).
3. Apply a modest depth penalty: files nearer the project root are
   favored slightly over deeply nested ones, on the assumption that
   top-level files tend to be more architecturally central.
4. Ties are broken alphabetically by relative path — this exists purely
   for determinism, not as a relevance signal.

### Why this method

- It's fully implementable with the standard library, within the time
  available.
- It's deterministic: identical task plus identical folder always yields
  identical scores.
- It can be explained to a judge in one sentence, which matters as much
  as raw accuracy given the grading rubric's Understanding component.
- Path matches outweigh content matches because a file literally named
  after the task concept (e.g. `auth.py` for an "add auth" task) is a
  stronger signal than a keyword that happens to appear once in a
  comment.

### Alternatives considered and rejected

- **Import-graph analysis** (ranking files by centrality in the
  dependency graph): theoretically more principled, but it requires
  per-language parsing (Python imports differ from JS requires differ
  from Go imports) — too much surface area to implement correctly and
  deterministically in the available time. Kept as a stretch goal if
  time allows.
- **Filename-only matching**: simpler, but too shallow — it misses files
  that matter a great deal to the task but carry generic names
  (`utils.py`, `index.js`), a common pattern in real codebases.
- **Recency (last-modified time)**: rejected outright, since it isn't
  reproducible across clones — git checkouts don't reliably preserve
  original mtimes, which would violate the determinism requirement.

---

## 5. Truncation Policy

When a file's full token cost is more than the remaining budget:

- If the file's **head** (its first N lines, sized to fit the remaining
  budget) still holds meaningful content — imports, class/function
  signatures, a top-of-file docstring — include that head as a partial
  file, clearly flagged as truncated in the bundle, and record the
  actual token count used in the manifest.
- If the remaining budget is too small to hold even a handful of
  meaningful lines (a hard floor, e.g. roughly under 50 tokens), skip the
  file entirely rather than including a useless fragment, and log the
  reason as "insufficient remaining budget."

### Why this method

A carefully chosen partial slice of a highly relevant file — its
signatures and top-level structure — is generally more useful to a
downstream AI assistant than dropping the file outright, which matters
especially for the single-large-file hidden test category the brief
explicitly flags. Only excluding a file when even a head-slice would be
meaningless avoids burning budget on noise.

### Alternatives considered and rejected

- **Always exclude a file if it doesn't fully fit**: the simplest and
  fully deterministic option, but it discards likely-useful signal and
  performs poorly on the "single file larger than the entire budget"
  test category by construction.
- **Smart semantic slicing** (e.g. pulling out just function signatures
  via AST parsing): more elegant, but Python's `ast` module only covers
  Python files — doing this fairly across a polyglot repo would need
  per-language handling, which is out of scope given the time budget.

---

## 6. Noise Detection

Noise is kept out of ranking/packing and recorded in the manifest's
`excluded` array along with a reason. Detection happens in layers rather
than via one hardcoded list:

1. **Structural exclusion** — directories that are almost never source
   code: `.git`, `node_modules`, `__pycache__`, `.venv`, `venv`, `dist`,
   `build`, `.next`, `target`. These are skipped by directory name during
   the walk, before any scoring happens.
2. **Pattern-based exclusion** — filenames matching known
   generated/lockfile patterns rather than an exhaustive list: anything
   ending in `.lock`, `-lock.json`, `.min.js`, `.min.css`, plus common
   lockfile basenames (`package-lock.json`, `yarn.lock`, `Pipfile.lock`,
   `Cargo.lock`, `poetry.lock`).
3. **Heuristic exclusion (binary/generated detection without hardcoded
   filenames)** — a file is treated as non-text noise if:
   - It fails to decode as UTF-8, or
   - It contains a null byte within its first 8KB, or
   - Its ratio of non-printable to printable characters crosses a
     threshold, which suggests a compiled or minified artifact even when
     its extension looks legitimate.

Because detection is layered, unforeseen noise (say, a lockfile format
that didn't exist when this spec was written) still has a good chance of
being caught by the heuristic layer even if the pattern layer misses it.

### Why this method

Combining structural, pattern, and heuristic layers avoids relying on a
single hardcoded filename list, which the brief explicitly flags as
insufficient ("without hardcoding a list of names"). The heuristic layer
acts as the fallback that generalizes to cases the other two layers
don't anticipate.

---

## 7. Budget Spending on Non-Code Content

**Decision: include a lightweight project-structure overview (a directory
tree) only when the budget remaining after packing ranked files has
slack, and cap its cost at a small fixed ceiling (roughly ~200 tokens).**

### Why

A tree overview helps an AI assistant get its bearings, but it isn't
source code and shouldn't have to compete with source code for scarce
budget on tight runs. Making it conditional on leftover slack ensures it
never causes a relevant file to be dropped, or truncated more
aggressively than necessary. On very small budgets it's omitted
altogether, and the manifest notes that it was skipped.

### Alternative considered and rejected

- **Always include a full tree, unconditionally**: rejected because on
  small budgets — one of the explicit hidden-test categories is
  "extremely small budgets" — this could eat a disproportionate share of
  very limited tokens that source code needs more.

---

## 8. Manifest Schema

Exact keys, matching the brief precisely:

```json
{
  "budget": 8000,
  "used": 7912,
  "included": [
    {"path": "src/agent.py", "tokens": 812, "reason": "high task-keyword overlap in path and content"}
  ],
  "excluded": [
    {"path": "package-lock.json", "reason": "lockfile — excluded as noise"}
  ]
}
```

Every file encountered during the walk shows up in exactly one of
`included` or `excluded` — no file is ever silently dropped without a
recorded reason.

---

## 9. Determinism Guarantee

- The file walk is explicitly sorted by relative path before any
  scoring occurs; it's never left to OS/filesystem iteration order.
- Ranking ties are broken alphabetically by path.
- No timestamps, random IDs, or set/dict-order-dependent values appear
  anywhere in the bundle or manifest output.
- Running the same command twice against the same folder produces
  byte-identical `--out` and `--manifest` files, confirmed via `diff`.

---

## 10. Error Handling

- Missing required flag → exit 1, with a one-line stderr message naming
  the missing flag.
- Non-integer or non-positive `--budget` → exit 1, one-line message.
- `--path` missing or unreadable → exit 2, one-line message.
- Any unexpected internal error is caught at the top level and converted
  into a one-line stderr message with exit code 1 — never a raw
  traceback.

---

## 11. Scope Boundaries (Constraints)

- Python 3.10+, standard library only. No `pip install` dependencies.
- No network calls at runtime — fully offline.
- Must run via `python ctxpack.py ...` or an installed entry point on a
  clean machine.

---

## 12. Definition of Done

`ctxpack` is done when:

1. All MUST requirements (1–7 in the brief) pass against the sample
   project folder.
2. The manifest output matches the schema in Section 8 exactly, for
   every file considered.
3. Repeated runs on identical input produce byte-identical bundle and
   manifest files.
4. Invalid arguments and missing paths produce the correct exit code
   and a single readable error line, never a traceback.
5. Binary and non-UTF-8 files are handled without crashing.
6. At least one SHOULD requirement (noise exclusion, oversized-file
   handling, or structure overview) is implemented and justified above.
7. Every team member can explain the ranking, truncation, and noise
   logic from memory, without reading the code first.

---

## 13. Open Items / Curveball Log

This section is updated live during the event whenever the specification
changes — including the 1:12 curveball requirement. Each entry records
what changed and why, before the corresponding code change is made.

- *(empty at spec time — to be filled in as changes occur)*