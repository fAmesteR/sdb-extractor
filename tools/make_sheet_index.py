"""Write sheets.html, a local page that opens each PDF in the browser.

Excel can't follow links from a workbook it opened through OneDrive, so the page replaces them.
"""
import csv
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sheets to label</title>
<style>
  body {{ font: 16px/1.5 system-ui, sans-serif; margin: 24px auto; max-width: 760px; padding: 0 16px; }}
  section {{ margin-top: 24px; }}
  ul {{ columns: 2; list-style: none; padding: 0; }}
  li {{ break-inside: avoid; }}
  a {{ font-weight: 600; }}
</style>
</head>
<body>
<h1>Sheets to label</h1>
<p>Click an id to open its PDF in a tab, then keep that tab beside labels.xlsx.</p>
<section><h2>dev ({dev_count})</h2><ul>
{dev}
</ul></section>
<section><h2>test ({test_count})</h2><ul>
{test}
</ul></section>
</body>
</html>
"""


def items(rows):
    return "\n".join(
        f'<li><a href="corpus/{row["id"]}/sheet.pdf" target="sheet">{row["id"]}</a> '
        f'{escape(row["category"])}, {row["pages"]} pages</li>'
        for row in rows
    )


def main():
    rows = list(csv.DictReader(open(ROOT / "manifest.csv", encoding="utf-8")))
    dev = [row for row in rows if row["split"] == "dev"]
    test = [row for row in rows if row["split"] == "test"]
    (ROOT / "sheets.html").write_text(
        PAGE.format(dev_count=len(dev), dev=items(dev), test_count=len(test), test=items(test)), encoding="utf-8"
    )
    print(f"Wrote sheets.html with {len(rows)} sheets")


if __name__ == "__main__":
    main()
