# AGENTS.md

## Repo Overview

Hackathon/class workspace. Contains `SPEC.md` (the spec for `ctxpack`, a Python CLI context-bundler) but **no implementation yet** — just the specification. Also ships an OpenCode skill (`dataverse-python-production-code`) under `.agents/skills/` tracked in `skills-lock.json`.

## Key Constraints from SPEC.md

- Python 3.10+ **stdlib only** — no `pip install`, no third-party packages, no network calls.
- Entry point: `python ctxpack.py ...` or an installed console script.
- Deterministic output is required: sorted walk, alphabetical tie-breaking, no timestamps/randomness.
- Token counting: `math.ceil(len(text) / 4)` — no tokenizer libraries.
- Exit codes: `0` success, `1` invalid args, `2` bad path. Never expose raw tracebacks.
- Noise detection must be layered (structural + pattern + heuristic), not just a hardcoded list.

## Workspace Path

The workspace path contains spaces (`D:\hackathon class work`). Always quote paths in shell commands, e.g.:

```powershell
Get-Content "D:\hackathon class work\SPEC.md"
```

## OpenCode Skills

- Skills are registered in `skills-lock.json` and live under `.agents/skills/`.
- Currently installed: `dataverse-python-production-code` (from `github/awesome-copilot`).
- See `.agents/skills/dataverse-python-production-code/SKILL.md` for the skill's instructions.

## Authoritative Sources

- Spec: `SPEC.md` — this is the single source of truth for `ctxpack` behavior.
- No `opencode.json` exists at the repo root.
- `README.md` is an empty placeholder — do not treat it as spec.