"""List every field the extractor got wrong on the dev tab, for debugging.

Usage: python -m tools.show_errors   Dev only: printing test mistakes would leak test labels into the code.
"""
import json
from pathlib import Path

from sdb.schema import FIELDS
from tools.check_labels import load_labels
from tools.score import field_correct, flatten

ROOT = Path(__file__).resolve().parent.parent


def main():
    labels = load_labels("dev")
    wrong = 0
    for sheet_id, truth in labels.items():
        predicted = flatten(json.loads((ROOT / "output" / "dev" / f"{sheet_id}.json").read_text(encoding="utf-8")))
        for field in FIELDS:
            if not field_correct(field, truth[field], predicted[field]):
                wrong += 1
                print(f"{sheet_id} {field}\n  truth {truth[field]!r}\n  got   {predicted[field]!r}")
    print(f"{wrong} wrong fields of {len(labels) * len(FIELDS)}")


if __name__ == "__main__":
    main()
