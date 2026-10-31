"""Turn German safety data sheet PDFs into structured JSON.

Usage: python -m sdb.extract dev   or   python -m sdb.extract test   or   python -m sdb.extract S004
       python -m sdb.extract any_sheet.pdf

A .pdf path prints its JSON. Otherwise each sheet's result goes to output/<split>/<id>.json, in the shape tools.score reads.
"""
import csv
import datetime
import html
import json
import re
import sys
from collections import Counter, namedtuple
from pathlib import Path

import pymupdf

from sdb.schema import H_CODES, cas_valid
from sdb.signs import name_signs

ROOT = Path(__file__).resolve().parent.parent
COLUMN_GAP = 12  # points between words before they count as separate table columns

Line = namedtuple("Line", "text page top columns")

TITLES = {
    1: r"bezeichnung des (stoff|unternehmens)|stoff\s*/\s*zubereitungs",
    2: r"m.gliche gefahren|gefahrenidentifizierung",
    3: r"zusammensetzung",
    4: r"erste[- ]?hilfe",
    8: r"begrenzung und .berwachung der exposition|expositionsbegrenzung",
    9: r"physikalische und chemische",
}
MONTHS = ("jan", "feb", "m", "apr", "mai", "jun", "jul", "aug", "sep", "okt", "nov", "dez")
DATE = re.compile(r"(?<!\d)(?:(\d{4})-(\d{1,2})-(\d{1,2})|(\d{1,2})[./-](\d{1,2})[./-](\d{4})"
                  r"|(\d{1,2})[.\- ]+\s*(jan|feb|m.r|mrz|apr|mai|jun|jul|aug|sep|okt|nov|dez)[a-z]*[.\- ]+\s*(\d{4}))(?!\d)",
                  re.I)
DATE_TIERS = (r".berarbeitet(?:\s+am)?|.berarbeitungsdatum|bearbeitungsdatum|revisionsdatum|\bstand",
              r"erstellt(?:\s+am)?|erstellungsdatum|ausgabedatum|datum der erstellung",
              r"druckdatum")
COMPANY = re.compile(r"\b(gmbh|mbh|ag|kg|ohg|ug|s\.?l\.?|s\.?a\.?|b\.?v\.?|ltd|limited|inc|e\.\s?k\.|sohn|s.hne)(?=\W|$)", re.I)
COMPANY_LABEL = re.compile(r"hersteller|lieferant|firma|anschrift|adresse", re.I)

EQUIPMENT = {
    "eye": r"brille|augenschutz|gesichtsschutz|visier|schutzschirm|en\s*166",
    "hand": r"handschuh|en\s*(iso\s*)?374|nitril|kautschuk|latex|viton",
    "respiratory": r"atemschutz|maske|filter|atemger.t|isolierger.t|atemfilter",
    "body": r"kleidung|kittel|sch.rze|anzug|overall|schuhe|stiefel|k.rperschutz",
}
HEADINGS = {
    "eye": r"(geeigneter\s+)?(augen|gesichts)[-\s/]*(und\s+)?(gesichts)?(schutz)?",
    "hand": r"(haut[-\s]*(und\s+)?|hautschutz\W*)?hand(e|-)?schutz(?!creme)|handschutz",
    "respiratory": r"atemschutz",
    "body": r"(haut[-\s]*(und\s+)?)?k.rperschutz|hautschutz\W+sonstige schutzma.nahmen|sonstige schutzma.nahmen|hautschutz",
}
OTHER_HEADINGS = r"thermische gefahren|begrenzung und .berwachung der umwelt|allgemeine (schutz|hygiene)|8\.[3-9]|hygienema"
CONDITION = re.compile(r"\b(bei|beim|falls|wenn|wo|liegt|soweit|sobald|sofern|ggf|gegebenenfalls|n.tigenfalls|im falle"
                       r"|in ausnahme\w*)\b", re.I)
NOT_A_CONDITION = re.compile(r"\bbei(m)? (der )?(bestimmungsgem\w+ )?(arbeit|umgang|handhabung|verwendung|gebrauch)\b"
                             r"|\bbei beabsichtigter wiederverwendung|\bwenn sie anzeichen"
                             r"|\bbei der (l.sung|vermischung)\b|\bbei von der en\b", re.I)
NOT_NEEDED = re.compile(r"nicht erforderlich|nicht notwendig|nicht n.tig|nicht ben.tigt|entf.llt"
                        r"|\bkein\w*\b[^.]{0,40}(erforderlich|notwendig|n.tig)", re.I)
SIGN_MATCH = 0.75  # on left-out dev sheets real diamonds scored 0.82 or more, a sign with no template 0.66, logos 0.2
H_PICTOGRAMS = {  # the pictogram CLP Annex I gives each hazard statement
    "GHS01": r"H20[0-5]|H24[01]",
    "GHS02": r"H22[02-68]|H24[12]|H25[0-2]|H26[01]",
    "GHS03": r"H27[0-2]",
    "GHS04": r"H28[01]",
    "GHS05": r"H290|H314|H318",
    "GHS06": r"H3[013][01]",
    "GHS07": r"H302|H312|H315|H317|H319|H332|H33[56]",
    "GHS08": r"H304|H334|H34[01]|H35[01]|H36[01]|H37[0-3]",
    "GHS09": r"H400|H41[01]",
}
GLOVES = {
    "NBR": r"nitril|(?-i:\bNBR\b)",
    "IIR": r"butyl",
    "FKM": r"viton|fluorkautschuk|(?-i:\bFKM\b)",
    "CR": r"chloropren|neopren|(?-i:\bCR\b)",
    "NR": r"naturkautschuk|naturlatex|\blatex\b|(?-i:\bNR\b)",
    "PVC": r"polyvinylchlorid|\bpvc\b",
    "PVA": r"polyvinylalkohol|\bpva\b",
}
OTHER_GLOVES = r"polyethylen|polyurethan|laminat|\bleder"  # only read in the hand text, as these also describe clothing


def page_lines(page, number):
    """Rebuild visual lines from word positions, because PDF text order often ignores the layout."""
    rows = []
    for word in sorted(page.get_text("words"), key=lambda word: word[1] + word[3]):
        middle, height = (word[1] + word[3]) / 2, word[3] - word[1]
        if rows and abs(middle - rows[-1][0]) < height / 2:
            rows[-1][1].append(word)
        else:
            rows.append((middle, [word]))
    lines = []
    for middle, words in rows:
        columns, end = [], None
        for word in sorted(words, key=lambda word: word[0]):
            text = html.unescape(word[4])  # some exports leave entities such as &uuml; in the PDF text
            if end is None or word[0] - end > COLUMN_GAP:
                columns.append([word[0], text])
            else:
                columns[-1][1] += " " + text
            end = word[2]
        lines.append(Line("\t".join(text for _, text in columns), number, middle, columns))
    return lines


def read_lines(doc):
    """Return all lines in order, dropping running headers and footers after page 1."""
    pages = [page_lines(page, number) for number, page in enumerate(doc)]

    def shape(line):
        return re.sub(r"\s|\d", "", line.text)

    seen = Counter(text for lines in pages for text in {shape(line) for line in lines})
    keep = pages[0][:]
    for lines in pages[1:]:
        keep += [line for line in lines if len(pages) < 3 or seen[shape(line)] <= len(pages) / 2]
    return keep


def find_sections(lines):
    """Return {number: lines}, searching in order so that 'siehe Abschnitt 8' can't start a section."""
    starts, position = {}, 0
    for number, title in TITLES.items():
        numbered = re.compile(rf"^\W*(abschnitt\s*)?0?{number}\b.{{0,20}}({title})", re.I)
        bare = re.compile(rf"^\W*({title})", re.I)
        for index in range(position, len(lines)):
            text = lines[index].text
            two_lines = joined(lines[index:index + 2]).replace("\n", " ").replace("\t", " ")
            if numbered.search(two_lines) or (bare.search(text) and len(text) < 100):
                starts[number] = position = index
                break
    starts[1] = 0  # the page header above the title can hold the product name
    ordered = sorted(starts.items(), key=lambda item: item[1])
    ends = [start for _, start in ordered[1:]] + [len(lines)]
    return {number: lines[start:end] for (number, start), end in zip(ordered, ends)}


def between(lines, start, end):
    """Return the lines from the first match of start up to the next match of end, or [] if start is absent."""
    for first, line in enumerate(lines):
        if re.search(start, line.text, re.I):
            for last in range(first + 1, len(lines)):
                if re.search(end, lines[last].text, re.I):
                    return lines[first:last]
            return lines[first:]
    return []


def joined(lines):
    return "\n".join(line.text for line in lines)


def first_column_after(line, match):
    return line.text[match.end():].lstrip(" :\t-–").split("\t")[0].strip()


def value_below(lines, index, x):
    """Return the cell under a table header, which is how some sheets lay out label and value."""
    if index + 1 >= len(lines):
        return ""
    cells = [text for left, text in lines[index + 1].columns if abs(left - x) < 30]
    return cells[0].strip() if cells else ""


def labelled_value(lines, index, column, end):
    """Return what belongs to a label ending at `end`: the rest of its cell, the next cell, or the cell below."""
    columns = lines[index].columns
    x, text = columns[column]
    next_cell = columns[column + 1][1] if column + 1 < len(columns) else ""
    for value in (text[end:], next_cell, value_below(lines, index, x)):
        value = value.strip(" -–\t").lstrip(":").strip()
        if value and not value.endswith(":") and not COMPANY_LABEL.fullmatch(value):  # that cell is another label
            return value
    return ""


def product_name(section):
    part = between(section, r"produktidentifikator|angaben zum produkt", r"^\W*1\W*2\b|relevante identifizierte") or section
    for label in (r"handelsname(\s*(/|oder|bzw\.?)\s*bezeichnung( des \w+)?)?",
                  r"produktname|produktbezeichnung|stoffname|bezeichnung des stoffs", r"\bname\b"):
        for index, line in enumerate(part):
            match = re.search(rf"({label})\s*:?", line.text, re.I)
            if match:
                value = first_column_after(line, match)
                below = part[index + 1].columns if index + 1 < len(part) else []
                if not value and below:
                    value = below[0][1].strip()
                elif len(line.columns) == 2 and len(below) == 1 and abs(below[0][0] - line.columns[1][0]) < 5:
                    value += " " + below[0][1].strip()  # a long name wraps under its own cell
                if value:
                    return value
    return part[1].text.split("\t")[0].strip() if len(part) > 1 else None


def supplier(section):
    part = between(section, r"einzelheiten zum lieferanten", r"^\W*1\W*4\b|notruf")[1:] or section
    for label in (r"\blieferant\b", r"hersteller|firmenname|\bfirma\b|bezeichnung des unternehmens"):
        for index, line in enumerate(part):
            for column, (_, text) in enumerate(line.columns):
                match = re.search(rf"({label})(\s*\([^)]*\))?\s*:?", text, re.I)
                value = match and labelled_value(part, index, column, match.end())
                if value:
                    return value.split(",")[0]  # the address often follows on the same line
    for line in part:
        for _, text in line.columns:
            if COMPANY.search(text):
                return text.split(",")[0].strip()
    return part[0].text.split("\t")[0].split(",")[0].strip() if part else None


def parse_dates(text):
    dates = []
    for match in DATE.finditer(text):
        year, month, day = match.group(1, 2, 3)
        if not year:
            day, month, year = match.group(4, 5, 6)
        if not year:
            day, name, year = match.group(7, 8, 9)
            month = next(number for number, stem in enumerate(MONTHS, 1) if name.lower().startswith(stem))
        try:
            dates.append(datetime.date(int(year), int(month), int(day)))
        except ValueError:
            pass
    return dates


def revision_date(lines):
    for tier in DATE_TIERS:
        for index, line in enumerate(lines):
            for x, text in line.columns:
                label = re.search(rf"({tier})\W*", text, re.I)
                if not label:
                    continue
                following = line.columns[line.columns.index([x, text]) + 1:]
                dates = (parse_dates(text[label.end():]) or parse_dates(following[0][1] if following else "")
                         or parse_dates(value_below(lines, index, x)))
                if dates:
                    return max(dates).isoformat()
    dates = parse_dates(joined(lines[:40]))
    return dates[0].isoformat() if dates else None


def cas_candidates(section):
    text = re.sub(r"(\d-)\s*\n\s*(\d)", r"\1\2", joined(section))  # a number can break across lines
    return list(dict.fromkeys(re.findall(r"(?<![\d-])\d{2,7}-\d{2}-\d(?![\d-])", text)))


def cas_numbers(section):
    return [cas for cas in cas_candidates(section) if cas_valid(cas)]


def signal_word(section):
    text = joined(label_part(section))
    match = re.search(r"signalw.rt[^\n]*?\b(gefahr|achtung|entf.llt)\b", text, re.I) or \
        re.search(r"signalw.rt\W*\n\W*(gefahr|achtung)\b", text, re.I) or \
        re.search(r"^\W*(gefahr|achtung)\W*$", text, re.I | re.M)
    if not match or match.group(1).lower().startswith("entf"):
        return None
    return match.group(1).capitalize()


def h_codes(section):
    found = re.findall(r"\b(EUH\s?\d{3}A?|H\s?\d{3}[A-Za-z]{0,2})\b", joined(section))
    codes = [re.sub(r"\s", "", code) for code in found]
    return list(dict.fromkeys(code for code in codes if code in H_CODES))


def p_codes(section):
    found = re.findall(r"\bP\s?\d{3}(?:\s*\+\s*P?\s?\d{3})*\b", joined(label_part(section)))
    codes = ["+".join("P" + number for number in re.findall(r"\d{3}", code)) for code in found]
    return list(dict.fromkeys(codes))


def ppe_blocks(section):
    """Split Section 8.2 into the text under each protective equipment heading."""
    part = between(section[1:], r"^\W*8\W*2\b|begrenzung und .berwachung der exposition|pers.nliche schutzausr.stung",
                   r"$^") or section
    starts = []
    for index, line in enumerate(part):
        text = line.text.lstrip(" ·•-–\t")
        unnumbered = text.lstrip("0123456789. \t")  # headings can be numbered, as in 8.3.1 Atemschutz
        for item, heading in HEADINGS.items():
            match = re.match(rf"({heading})\b\s*:?", unnumbered, re.I)
            if match and match.group(0).strip():
                starts.append((index, item, unnumbered[match.end():]))
                break
        else:
            if re.match(OTHER_HEADINGS, text, re.I):
                starts.append((index, None, ""))
    blocks = dict.fromkeys(EQUIPMENT, "")
    for (index, item, rest), (end, *_) in zip(starts, starts[1:] + [(len(part), None, "")]):
        if item:
            blocks[item] += " " + " ".join([rest] + [line.text for line in part[index + 1:end]])
    blocks["hand"] = blocks["hand"] or blocks["body"]  # a plain "Hautschutz" heading covers gloves too
    return blocks, joined(part)


def ppe_level(item, block):
    text = re.sub(r"\s+", " ", block).strip()
    if not text:
        return "not_stated"
    sentences = re.split(r"(?<=[a-zäöüß)])[.;]\s", text)
    if NOT_NEEDED.search(text):
        return "conditional" if CONDITION.search(text) else "not_required"
    if re.search(r"(kurzzeitig|gering).*(l.nger|intensiv)", text, re.I):
        return "required"
    first = next((index for index, sentence in enumerate(sentences) if re.search(EQUIPMENT[item], sentence, re.I)), None)
    if first is None:
        return "not_stated"
    lead_in = " ".join(sentences[:first + 1])  # the condition can sit in the sentence before the equipment
    return "conditional" if CONDITION.search(NOT_A_CONDITION.sub("", lead_in)) else "required"


def label_part(section):
    return between(section, r"kennzeichnungselemente|^\W*2\W*2\b", r"^\W*2\W*3\b|sonstige gefahren") or section


def label_regions(doc, sections):
    """Yield (page number, rectangle) for the Section 2.2 label, stopping at the start of Section 3."""
    part = label_part(sections.get(2, []))
    if not part:
        return
    first, last = part[0], sections[3][0] if sections.get(3) else part[-1]
    for number in range(first.page, last.page + 1):
        page = doc[number].rect
        top = first.top - 12 if number == first.page else 0
        bottom = last.top if number == last.page else page.height
        yield number, pymupdf.Rect(0, top, page.width, bottom)


def printed_pictograms(doc, sections):
    """Return the codes the sheet prints, or else the codes of the diamonds that match a template."""
    named = re.findall(r"GHS0[1-9]", joined(label_part(sections.get(2, []))))
    if named:
        return list(dict.fromkeys(named))
    signs = [sign for number, clip in label_regions(doc, sections) for sign in name_signs(doc[number], clip)]
    return list(dict.fromkeys(name for name, score in signs if score >= SIGN_MATCH))


def reconcile_pictograms(found, codes):
    """Check pictograms against the H-codes. Return (pictograms, whether they disagreed).

    GHS01, GHS03 and GHS04 have no templates, so they come from here unless the sheet prints the code.
    GHS07 is never demanded, because CLP Article 26 lets stronger pictograms replace it.
    """
    implied = {name for name, pattern in H_PICTOGRAMS.items() if any(re.match(pattern, code) for code in codes)}
    missing, extra = implied - set(found) - {"GHS07"}, set(found) - implied
    if missing and extra:  # a flame over a circle reads as a flame, so trust the hazard statements
        found = [name for name in found if name not in extra]
    return sorted(set(found) | missing), bool(missing or extra)


def suitable_text(text):
    return " ".join(sentence for sentence in re.split(r"(?<=[a-zäöüß)])\.\s", text)
                    if not re.search(r"ungeeignet|nicht geeignet", sentence, re.I))


def glove_materials(ppe_text, hand_text):
    usable = suitable_text(ppe_text)
    found = [code for code, pattern in GLOVES.items() if re.search(pattern, usable, re.I)]
    return found + ["OTHER"] * bool(re.search(OTHER_GLOVES, suitable_text(hand_text), re.I))


def review_reasons(sheet, sections, pictograms_disagree):
    """Return why a person should check this sheet. Each reason is something a correct sheet should not show."""
    substance, hazards, protection = sheet["substance"], sheet["hazards"], sheet["protection"]
    reasons = [f"section_{number}_not_found" for number in (2, 3, 8) if not sections.get(number)]
    reasons += [f"{field}_missing" for field in ("product_name", "supplier", "revision_date") if not substance[field]]
    if len(cas_candidates(sections.get(3, []))) != len(substance["cas_numbers"]):
        reasons.append("cas_check_digit_failed")
    if pictograms_disagree:
        reasons.append("pictograms_disagree_with_h_codes")
    if bool(hazards["signal_word"]) != bool(set(hazards["pictograms"]) - {"GHS09"}) and \
            not (hazards["signal_word"] and hazards["pictograms"]):  # GHS09 can appear without a signal word
        reasons.append("signal_word_disagrees_with_pictograms")
    if hazards["pictograms"]:
        reasons += [f"{item}_not_stated" for item in ("eye", "hand") if protection[item] == "not_stated"]
    return reasons


def extract(path):
    with pymupdf.open(path) as doc:
        lines = read_lines(doc)
        sections = find_sections(lines)
        printed = printed_pictograms(doc, sections)
    section = lambda number: sections.get(number, [])  # noqa: E731
    blocks, ppe_text = ppe_blocks(section(8))
    # only the label's codes count: aerosols are classified H304 in 2.1 but CLP drops it from their label
    pictogram_codes, pictograms_disagree = reconcile_pictograms(printed, h_codes(label_part(section(2))))
    sheet = {
        "substance": {
            "product_name": product_name(section(1)),
            "supplier": supplier(section(1)),
            "revision_date": revision_date(lines),
            "cas_numbers": cas_numbers(section(3)),
        },
        "hazards": {
            "signal_word": signal_word(section(2)),
            "h_codes": h_codes(section(2)),
            "p_codes": p_codes(section(2)),
            "pictograms": pictogram_codes,
        },
        "protection": {
            **{item: ppe_level(item, block) for item, block in blocks.items()},
            "glove_materials": glove_materials(ppe_text, blocks["hand"]),
        },
    }
    reasons = review_reasons(sheet, sections, pictograms_disagree)
    return {**sheet, "needs_review": bool(reasons), "review_reasons": reasons}


def sheet_ids(target):
    with open(ROOT / "manifest.csv", newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    chosen = [row for row in rows if target in (row["split"], row["id"])]
    if not chosen:
        sys.exit("Usage: python -m sdb.extract dev|test|<sheet id>|<file.pdf>")
    return [(row["id"], row["split"]) for row in chosen]


def main():
    pymupdf.TOOLS.mupdf_display_errors(False)
    target = sys.argv[1] if len(sys.argv) > 1 else ""
    if target.lower().endswith(".pdf"):
        sys.stdout.reconfigure(encoding="utf-8")
        print(json.dumps(extract(target), ensure_ascii=False, indent=2))
        return
    for sheet_id, split in sheet_ids(target):
        try:
            result = extract(ROOT / "corpus" / sheet_id / "sheet.pdf")
        except Exception as error:  # one bad PDF must not stop the batch; the scorer counts a missing sheet as wrong
            print(sheet_id, "failed:", type(error).__name__)
            continue
        output = ROOT / "output" / split
        output.mkdir(parents=True, exist_ok=True)
        (output / f"{sheet_id}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
