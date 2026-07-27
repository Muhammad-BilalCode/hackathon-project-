import argparse
import json
import math
import os
import sys

from ranking import tokenize, rank_files

NOISE_DIRS = frozenset(
    {".git", "node_modules", "__pycache__", ".venv", "venv",
     "dist", "build", ".next", "target"}
)

NOISE_PATTERNS = frozenset({".lock", "-lock.json", ".min.js", ".min.css"})

NOISE_BASENAMES = frozenset(
    {"package-lock.json", "yarn.lock", "Pipfile.lock",
     "Cargo.lock", "poetry.lock"}
)

STRUCTURAL_REASON = "excluded as noise — structural directory exclusion"
PATTERN_REASON = "excluded as noise — lockfile or generated file"
HEURISTIC_REASON = "excluded as noise — binary or non-text content"
TRUNCATION_FLOOR_TOKENS = 50
TREE_OVERVIEW_TOKEN_CAP = 200


def exit_error(code, message):
    print(message, file=sys.stderr)
    sys.exit(code)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Pack a codebase context bundle for an AI coding assistant."
    )
    parser.add_argument("--path", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--budget", required=True)
    parser.add_argument("--out", default=None)
    parser.add_argument("--manifest", default=None)
    args = parser.parse_args()

    try:
        args.budget = int(args.budget)
    except (ValueError, TypeError):
        exit_error(1, "Error: --budget must be a positive integer.")

    if args.budget <= 0:
        exit_error(1, "Error: --budget must be a positive integer.")

    return args


def classify_noise(rel_path):
    basename = os.path.basename(rel_path)
    parts = rel_path.split("/")

    for part in parts:
        if part in NOISE_DIRS:
            return True, STRUCTURAL_REASON

    if basename in NOISE_BASENAMES:
        return True, PATTERN_REASON

    for ext in NOISE_PATTERNS:
        if basename.endswith(ext):
            return True, PATTERN_REASON

    return False, None


def is_binary_file(full_path):
    try:
        with open(full_path, "rb") as f:
            chunk = f.read(8192)
        if b"\x00" in chunk:
            return True
        text = chunk.decode("utf-8", errors="replace")
        printable = sum(1 for ch in text if ch.isprintable() or ch in "\n\r\t")
        total = len(text)
        if total > 0 and (total - printable) / total > 0.30:
            return True
        return False
    except OSError:
        return True


def walk_files(root_path):
    candidates = []
    for dirpath, dirnames, filenames in os.walk(root_path):
        dirnames.sort()
        rel_dir = os.path.relpath(dirpath, root_path)
        if rel_dir == ".":
            rel_dir = ""

        for filename in sorted(filenames):
            rel_path = (
                os.path.join(rel_dir, filename) if rel_dir else filename
            )
            rel_path = rel_path.replace(os.sep, "/")

            noisy, reason = classify_noise(rel_path)
            if noisy:
                candidates.append(
                    {"path": rel_path, "content": None, "reason": reason}
                )
                continue

            full_path = os.path.join(dirpath, filename)
            if is_binary_file(full_path):
                candidates.append(
                    {"path": rel_path, "content": None, "reason": HEURISTIC_REASON}
                )
                continue

            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()
                candidates.append(
                    {"path": rel_path, "content": content, "reason": None}
                )
            except (OSError, UnicodeDecodeError):
                candidates.append(
                    {"path": rel_path, "content": None, "reason": HEURISTIC_REASON}
                )

    return candidates


def count_tokens(text):
    return math.ceil(len(text) / 4)


def compute_reason(rel_path, content, task_tokens):
    path_hits = sum(1 for t in task_tokens if t in rel_path.lower()) * 3
    cap = len(task_tokens) * 2
    content_hits = 0
    content_lower = content.lower()
    for t in task_tokens:
        content_hits += content_lower.count(t)
        if content_hits >= cap:
            content_hits = cap
            break

    if path_hits > 0 and content_hits > 0:
        return "high task-keyword overlap in path and content"
    if path_hits > 0:
        return "task-keyword overlap in path"
    if content_hits > 0:
        return "task-keyword overlap in content"
    return "included — no task-keyword overlap found"

def file_section_cost(rel_path, content, truncated):
    """Return the exact token cost of this file's markdown section
    inside the bundle, including blank-line separators and the section header."""
    parts = ["## " + rel_path]
    if truncated:
        parts.append("<!-- truncated -->")
    parts.append("")
    parts.append(content)
    section_text = "\n\n" + "\n".join(parts)
    return count_tokens(section_text)


def build_bundle(included_files, task, tree_overview):
    parts = []
    parts.append("# Context Bundle")
    parts.append("**Task:** " + task)

    for entry in included_files:
        path = entry["path"]
        if path == "":
            continue
        parts.append("")
        parts.append("## " + path)
        if entry.get("truncated"):
            parts.append("<!-- truncated -->")
        parts.append("")
        parts.append(entry["content"])

    if tree_overview:
        parts.append("")
        parts.append(tree_overview)

    return "\n".join(parts) + "\n"


def header_cost(task):
    """Return the token cost of the bundle header (not including any file entries)."""
    return count_tokens("# Context Bundle\n**Task:** " + task + "\n\n")


def build_tree_overview(included_paths, budget_remaining):
    if not included_paths or budget_remaining <= 0:
        return None

    lines = ["# Project Structure"]
    for p in sorted(included_paths):
        depth = p.count("/")
        indent = "  " * depth
        lines.append(f"{indent}- {os.path.basename(p)}")

    tree_text = "\n".join(lines) + "\n"
    if count_tokens(tree_text) > budget_remaining:
        return None
    if count_tokens(tree_text) > TREE_OVERVIEW_TOKEN_CAP:
        return None
    return tree_text


def compute_head(content, remaining_budget, rel_path):
    """Return (head_text, head_tokens) for truncation policy.
    Accounts for section overhead ('## path', '<!-- truncated -->',
    separators) so the final section stays within budget."""
    overhead = count_tokens(
        "\n\n## " + rel_path + "\n\n<!-- truncated -->\n\n"
    )
    content_budget = max(0, remaining_budget - overhead)
    lines = content.split("\n")
    head_lines = []
    head_tokens = 0
    for line in lines:
        line_tokens = count_tokens(line)
        if head_tokens + line_tokens > content_budget:
            break
        head_lines.append(line)
        head_tokens += line_tokens
    if head_lines and head_tokens > 0:
        return "\n".join(head_lines), head_tokens
    return None, 0


def main():
    args = parse_args()

    if not os.path.isdir(args.path) or not os.access(args.path, os.R_OK):
        exit_error(
            2,
            "Error: --path does not exist, is not a directory, or is not readable.",
        )

    candidates = walk_files(args.path)

    readable = [c for c in candidates if c["content"] is not None]
    excluded = [c for c in candidates if c["content"] is None]

    task_tokens = tokenize(args.task)
    readable_with_content = [
        (e["path"], e["content"]) for e in readable
    ]
    ranked_paths = rank_files(readable_with_content, args.task)

    content_by_path = {e["path"]: e["content"] for e in readable}

    included = []
    remaining = args.budget - header_cost(args.task)

    if remaining < 0:
        remaining = 0

    for rel_path in ranked_paths:
        content = content_by_path[rel_path]

        full_cost = file_section_cost(rel_path, content, False)
        if full_cost <= remaining:
            content_tokens = count_tokens(content)
            included.append(
                {
                    "path": rel_path,
                    "tokens": content_tokens,
                    "content": content,
                    "truncated": False,
                    "reason": compute_reason(rel_path, content, task_tokens),
                }
            )
            remaining -= full_cost
            continue

        if remaining < TRUNCATION_FLOOR_TOKENS:
            excluded.append(
                {"path": rel_path, "content": None, "reason": "insufficient remaining budget"}
            )
            continue

        head_content, head_tokens = compute_head(content, remaining, rel_path)
        if head_content is not None:
            truncated_cost = file_section_cost(rel_path, head_content, True)
            if truncated_cost <= remaining:
                included.append(
                    {
                        "path": rel_path,
                        "tokens": head_tokens,
                        "content": head_content,
                        "truncated": True,
                        "reason": compute_reason(rel_path, content, task_tokens),
                    }
                )
                remaining -= truncated_cost
            else:
                excluded.append(
                    {"path": rel_path, "content": None,
                     "reason": "insufficient remaining budget"}
                )
        else:
            excluded.append(
                {"path": rel_path, "content": None,
                 "reason": "insufficient remaining budget"}
            )

    tree_overview = None
    if remaining > 0 and included:
        tree_overview = build_tree_overview(
            [e["path"] for e in included], remaining
        )

    bundle_text = build_bundle(included, args.task, tree_overview)
    used = count_tokens(bundle_text)

    manifest_included = [
        {"path": e["path"], "tokens": e["tokens"], "reason": e["reason"]}
        for e in included
    ]

    manifest_excluded = sorted(
        [{"path": e["path"], "reason": e["reason"]} for e in excluded],
        key=lambda x: x["path"],
    )

    manifest = {
        "budget": args.budget,
        "used": used,
        "included": manifest_included,
        "excluded": manifest_excluded,
    }

    if args.out:
        with open(args.out, "wb") as f:
            f.write(bundle_text.encode("utf-8"))
    else:
        sys.stdout.write(bundle_text)

    if args.manifest:
        with open(args.manifest, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, sort_keys=True)
    else:
        inc_count = len(manifest_included)
        exc_count = len(manifest_excluded)
        print(
            f"Bundle: {used}/{args.budget} tokens. "
            f"Included {inc_count} files, excluded {exc_count}.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        exit_error(1, "Error: " + str(e))