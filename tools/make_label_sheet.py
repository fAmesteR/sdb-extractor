"""Create labels.xlsx from manifest.csv. Refuses to overwrite, because that would erase labels."""
import csv
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

from sdb.schema import FIELDS, GLOVE_MATERIALS, NONE, PPE_FIELDS, PPE_LEVELS, SIGNAL_WORDS

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "labels.xlsx"
COLUMNS = ("id", "pages", *FIELDS, "notes")
WORKED_EXAMPLE = {
    "S002": {
        "product_name": "Schneidoel",
        "supplier": "LIQUI MOLY GmbH",
        "revision_date": "2023-11-08",
        "cas_numbers": "68442-22-8",
        "signal_word": "Gefahr",
        "h_codes": "H222;H229;H304",
        "p_codes": "P102;P210;P211;P251;P410+P412",
        "pictograms": "GHS02",
        "eye": "required",
        "hand": "required",
        "respiratory": "conditional",
        "body": "required",
        "glove_materials": "NBR",
        "notes": "Worked example from LABELLING_GUIDE.md",
    }
}
WIDTHS = {"id": 8, "pages": 7, "product_name": 34, "supplier": 28, "revision_date": 13, "cas_numbers": 26,
          "h_codes": 30, "p_codes": 44, "pictograms": 20, "glove_materials": 16, "notes": 40}


def add_dropdown(sheet, column, choices, last_row):
    letter = sheet.cell(1, column).column_letter
    rule = DataValidation(type="list", formula1='"' + ",".join(choices) + '"', allow_blank=True)
    rule.error = "Pick a value from the list."
    sheet.add_data_validation(rule)
    rule.add(f"{letter}2:{letter}{last_row}")


def build_tab(book, title, rows):
    sheet = book.create_sheet(title)
    sheet.append(COLUMNS)
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F4E78")
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    for row in rows:
        example = WORKED_EXAMPLE.get(row["id"], {})
        sheet.append([row["id"], int(row["pages"]), *(example.get(c) for c in COLUMNS[2:])])
        number = sheet.max_row
        for column in range(3, len(COLUMNS) + 1):
            sheet.cell(number, column).number_format = "@"  # stops Excel turning codes into dates
    last_row = sheet.max_row
    position = {name: index for index, name in enumerate(COLUMNS, 1)}
    add_dropdown(sheet, position["signal_word"], (*SIGNAL_WORDS, NONE), last_row)
    for field in PPE_FIELDS:
        add_dropdown(sheet, position[field], PPE_LEVELS, last_row)
    for name, index in position.items():
        sheet.column_dimensions[sheet.cell(1, index).column_letter].width = WIDTHS.get(name, 14)
    sheet.freeze_panes = "C2"


def main():
    if OUTPUT.exists():
        sys.exit("labels.xlsx already exists; refusing to overwrite your labels.")
    rows = list(csv.DictReader(open(ROOT / "manifest.csv", encoding="utf-8")))
    book = Workbook()
    book.remove(book.active)
    for split in ("dev", "test"):
        build_tab(book, split, [row for row in rows if row["split"] == split])
    book.save(OUTPUT)
    print(f"Wrote {OUTPUT.name}: glove codes allowed = {', '.join(GLOVE_MATERIALS)}")


if __name__ == "__main__":
    main()
