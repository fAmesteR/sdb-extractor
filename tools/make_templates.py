"""Build sdb/sign_templates.json from dev sheets and spare candidates. Never touches test sheets.

Usage: python -m tools.make_templates <folder for a contact sheet of the crops>

Dev diamonds are named by their labels, read left to right. Candidates only count when the sheet prints the codes
itself and there are as many codes as diamonds. A candidate whose file hash is in manifest.csv is skipped.
"""
import csv
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import pymupdf

from sdb.extract import find_sections, label_regions, read_lines
from sdb.signs import SIZE, TEMPLATE_FILE, grey_cells, sign_rects
from tools.check_labels import load_labels

ROOT = Path(__file__).resolve().parent.parent


def diamonds(doc, sections):
    return [(number, rect) for number, clip in label_regions(doc, sections) for rect in sign_rects(doc[number], clip)]


def spare_sheets():
    with open(ROOT / "manifest.csv", newline="", encoding="utf-8") as handle:
        used = {row["sha256"] for row in csv.DictReader(handle)}
    for path in sorted((ROOT / "corpus" / "_candidates").glob("*/sheet.pdf")):
        if hashlib.sha256(path.read_bytes()).hexdigest() not in used:
            yield path


def main():
    pymupdf.TOOLS.mupdf_display_errors(False)
    crops = defaultdict(list)
    labels = load_labels("dev")
    for sheet_id, truth in labels.items():
        with pymupdf.open(ROOT / "corpus" / sheet_id / "sheet.pdf") as doc:
            found = diamonds(doc, find_sections(read_lines(doc)))
            print(sheet_id, "labels", len(truth["pictograms"]), "found", len(found))
            if len(found) == len(truth["pictograms"]):
                for code, (number, rect) in zip(truth["pictograms"], found):
                    crops[code].append(grey_cells(doc[number], rect))
    spare_used = 0
    for path in spare_sheets():
        try:
            doc = pymupdf.open(path)
            sections = find_sections(read_lines(doc))
            if 2 not in sections:
                continue
            codes = re.findall(r"GHS0[1-9]", "\n".join(line.text for line in sections[2]))
            codes = list(dict.fromkeys(codes))
            found = diamonds(doc, sections)
            if codes and len(found) == len(codes):
                spare_used += 1
                for code, (number, rect) in zip(codes, found):
                    crops[code].append(grey_cells(doc[number], rect))
        except Exception as error:  # a broken spare file only costs a template source
            print(path.parent.name, "skipped:", error)
    print("spare sheets used:", spare_used)

    templates = {code: [sum(column) // len(cells) for column in zip(*cells)] for code, cells in sorted(crops.items())}
    TEMPLATE_FILE.write_text(json.dumps(templates), encoding="utf-8")
    print({code: len(cells) for code, cells in sorted(crops.items())})

    output = Path(sys.argv[1])
    output.mkdir(parents=True, exist_ok=True)
    board = pymupdf.Pixmap(pymupdf.csGRAY, pymupdf.IRect(0, 0, SIZE * 12, SIZE * len(crops)), False)
    board.clear_with(255)
    for row, (code, cells) in enumerate(sorted(crops.items())):
        for column, cell in enumerate(cells[:12]):
            for index, value in enumerate(cell):
                y, x = divmod(index, SIZE)
                board.set_pixel(column * SIZE + x, row * SIZE + y, (value,))
    board.save(output / "crops.png")


if __name__ == "__main__":
    main()
