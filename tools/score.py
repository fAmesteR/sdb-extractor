"""Score extractor output against labels.xlsx. Written before the extractor, so its rules are fixed in advance.

Usage: python -m tools.score dev   or   python -m tools.score test

Each sheet's output is output/<split>/<id>.json. Every run on the test set is appended to
reports/test_runs.log, so the number of attempts stays visible.
"""
import datetime
import hashlib
import json
import math
import re
import sys
from pathlib import Path

from sdb.schema import FIELDS, GROUPS, LIST_FIELDS
from tools.check_labels import load_labels

ROOT = Path(__file__).resolve().parent.parent
LEGAL_FORMS = r"\b(gmbh|mbh|ag|kg|ohg|ug|se|co|bv|nv|ltd|limited|inc|llc|sa|srl|spa)\b"


def fold(text):
    text = text.casefold()
    for umlaut, plain in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        text = text.replace(umlaut, plain)
    return text


def norm_text(text):
    return re.sub(r"[^a-z0-9]", "", fold(text or ""))


def norm_supplier(text):
    return norm_text(re.sub(LEGAL_FORMS, " ", fold(text or "")))


def field_correct(field, truth, predicted):
    if field in LIST_FIELDS:
        return set(truth) == set(predicted or [])
    if field == "product_name":
        return norm_text(truth) == norm_text(predicted)
    if field == "supplier":
        a, b = norm_supplier(truth), norm_supplier(predicted)
        return bool(a and b) and (a == b or a in b or b in a)
    return truth == predicted


def wilson(correct, total, z=1.96):
    """95% Wilson interval for a proportion; sensible at small n and near 100%."""
    if total == 0:
        return 0.0, 0.0
    p = correct / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return max(0.0, centre - half), min(1.0, centre + half)


def flatten(document):
    flat = {field: document.get(group, {}).get(field) for group, fields in GROUPS.items() for field in fields}
    flat["needs_review"] = bool(document.get("needs_review"))
    return flat


def score(labels, predictions):
    """Return one result row per field. A sheet with no output counts as wrong on every field."""
    results = []
    for field in FIELDS:
        correct = found = extra = missed = 0
        for sheet_id, truth in labels.items():
            predicted = predictions.get(sheet_id, {}).get(field)
            correct += sheet_id in predictions and field_correct(field, truth[field], predicted)
            if field in LIST_FIELDS:
                true_set, predicted_set = set(truth[field]), set(predicted or [])
                found += len(true_set & predicted_set)
                extra += len(predicted_set - true_set)
                missed += len(true_set - predicted_set)
        low, high = wilson(correct, len(labels))
        row = {"field": field, "correct": correct, "total": len(labels), "accuracy": correct / len(labels) if labels else 0.0,
               "low": low, "high": high}
        if field in LIST_FIELDS:
            row["precision"] = found / (found + extra) if found + extra else 1.0
            row["recall"] = found / (found + missed) if found + missed else 1.0
        results.append(row)
    return results


def render(results, heading):
    lines = [f"## {heading}", "", "| Field | Correct | Accuracy | 95% CI | Precision | Recall |", "|---|---:|---:|---:|---:|---:|"]
    for row in results:
        precision = f"{row['precision']:.3f}" if "precision" in row else ""
        recall = f"{row['recall']:.3f}" if "recall" in row else ""
        lines.append(f"| {row['field']} | {row['correct']}/{row['total']} | {row['accuracy']:.1%} | "
                     f"{row['low']:.1%}–{row['high']:.1%} | {precision} | {recall} |")
    return "\n".join(lines) + "\n"


def log_test_run():
    digest = hashlib.sha256()
    for path in sorted((ROOT / "sdb").glob("*.*")):  # the sign templates are part of the extractor too
        digest.update(path.read_bytes())
    stamp = datetime.datetime.now().isoformat(timespec="seconds")
    with open(ROOT / "reports" / "test_runs.log", "a", encoding="utf-8") as log:
        log.write(f"{stamp} sdb_code_sha256={digest.hexdigest()[:16]}\n")


def main():
    split = sys.argv[1] if len(sys.argv) > 1 else ""
    if split not in ("dev", "test"):
        sys.exit("Usage: python -m tools.score dev|test")
    labels = load_labels(split)
    if not labels:
        sys.exit(f"No complete labels in the {split} tab yet.")
    predictions = {}
    for sheet_id in labels:
        path = ROOT / "output" / split / f"{sheet_id}.json"
        if path.exists():
            predictions[sheet_id] = flatten(json.loads(path.read_text(encoding="utf-8")))

    (ROOT / "reports").mkdir(exist_ok=True)
    if split == "test":
        log_test_run()
    flagged = sum(row["needs_review"] for row in predictions.values())
    clean_ids = [sheet_id for sheet_id, row in predictions.items() if not row["needs_review"]]
    text = render(score(labels, predictions), f"All {len(labels)} {split} sheets")
    text += f"\nSent to human review: {flagged} of {len(labels)} sheets.\n\n"
    if clean_ids:
        text += render(score({i: labels[i] for i in clean_ids}, predictions), f"The {len(clean_ids)} sheets not sent to review")
    (ROOT / "reports" / f"{split}.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
