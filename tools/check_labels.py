"""Check labels.xlsx for format mistakes and report progress. It never judges whether a label is right."""
import datetime
import re
import sys
from pathlib import Path

from openpyxl import load_workbook

from sdb.schema import (FIELDS, GLOVE_MATERIALS, H_CODES, LIST_FIELDS, NONE, P_CODE, PICTOGRAMS, PPE_FIELDS,
                        PPE_LEVELS, SIGNAL_WORDS, cas_valid)

ROOT = Path(__file__).resolve().parent.parent


def clean(value):
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.strftime("%Y-%m-%d")
    return "" if value is None else str(value).strip()


def split_list(text):
    return [re.sub(r"\s+", "", item) for item in text.split(";") if item.strip()]


def load_rows(split):
    try:
        sheet = load_workbook(ROOT / "labels.xlsx", data_only=True)[split]
    except PermissionError:
        sys.exit("Excel is holding labels.xlsx. Close it, then run this again.")
    rows = list(sheet.iter_rows(values_only=True))
    header = [clean(name) for name in rows[0]]
    return [dict(zip(header, map(clean, row))) for row in rows[1:] if row[0]]


def load_labels(split):
    """Return {sheet id: label} for fully labelled rows, with lists split and NONE turned into empty."""
    labels = {}
    for row in load_rows(split):
        if any(not row[field] for field in FIELDS):
            continue
        labels[row["id"]] = {
            field: ([] if row[field] == NONE else split_list(row[field])) if field in LIST_FIELDS
            else (None if row[field] == NONE else row[field])
            for field in FIELDS
        }
    return labels


def row_problems(row):
    problems = [f"{field} is blank (use {NONE} if the sheet has nothing)" for field in FIELDS if not row[field]]

    def items(field):
        return [] if row[field] in ("", NONE) else split_list(row[field])

    if row["revision_date"] and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", row["revision_date"]):
        problems.append(f"revision_date '{row['revision_date']}' must look like 2023-11-08")
    if row["signal_word"] not in ("", NONE, *SIGNAL_WORDS):
        problems.append(f"signal_word '{row['signal_word']}' must be {', '.join(SIGNAL_WORDS)} or {NONE}")
    problems += [f"CAS '{cas}' fails its check digit; recheck it against the PDF"
                 for cas in items("cas_numbers") if not cas_valid(cas)]
    problems += [f"h_codes: '{code}' is not a known code; write combined codes separately"
                 for code in items("h_codes") if code not in H_CODES]
    problems += [f"p_codes: '{code}' should look like P210 or P305+P351+P338"
                 for code in items("p_codes") if not P_CODE.fullmatch(code)]
    problems += [f"pictograms: '{code}' must be GHS01 to GHS09" for code in items("pictograms")
                 if code not in PICTOGRAMS]
    problems += [f"glove_materials: '{code}' must be one of {', '.join(GLOVE_MATERIALS)}"
                 for code in items("glove_materials") if code not in GLOVE_MATERIALS]
    problems += [f"{field} '{row[field]}' must be one of {', '.join(PPE_LEVELS)}" for field in PPE_FIELDS
                 if row[field] and row[field] not in PPE_LEVELS]
    return problems


def main():
    failed = 0
    for split in ("dev", "test"):
        rows = load_rows(split)
        started = [row for row in rows if any(row[field] for field in FIELDS)]
        complete = 0
        for row in started:
            problems = row_problems(row)
            complete += not problems
            failed += len(problems)
            for problem in problems:
                print(f"{split} {row['id']}: {problem}")
        print(f"{split}: {complete} of {len(rows)} sheets complete and valid")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
