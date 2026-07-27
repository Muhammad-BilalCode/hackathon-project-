import os
import string

STOPWORDS = frozenset(
    "a an and are as at be by for from has have he her his how i if in into it its"
    " me my no not of on or our out s so she t than that the their them then there"
    " they this to was we will what when where which who why you your"
    .split()
)


def tokenize(task):
    tokens = task.lower().translate(str.maketrans("", "", string.punctuation)).split()
    return [t for t in tokens if t and t not in STOPWORDS]


def score_file(rel_path, content, task_tokens):
    path_score = sum(1 for t in task_tokens if t in rel_path.lower()) * 3

    cap = len(task_tokens) * 2
    content_hits = 0
    content_lower = content.lower()
    for t in task_tokens:
        count = content_lower.count(t)
        content_hits += count
        if content_hits >= cap:
            content_hits = cap
            break

    depth = rel_path.count(os.sep)
    depth_penalty = 1.0 / (1.0 + depth)

    return (path_score + content_hits) * depth_penalty


def rank_files(candidates, task):
    task_tokens = tokenize(task)
    if not task_tokens:
        return sorted(candidates, key=lambda x: x)

    scored = []
    for rel_path, content in candidates:
        score = score_file(rel_path, content, task_tokens)
        scored.append((rel_path, score))

    scored.sort(key=lambda x: (-x[1], x[0]))

    return [rel_path for rel_path, _ in scored]