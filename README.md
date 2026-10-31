# SDB extractor

Turns German safety data sheets (Sicherheitsdatenblätter) from PDF into structured JSON covering the substance, its hazards and the protective measures.

**Result:** on 50 held-out sheets, it got 616 of 650 fields right (94.8%). That includes 99% on hazard codes, dates and pictograms and 88% on free-text protection levels, against reference labels created with AI assistance and audited by the project owner. See [how this was measured](#how-accuracy-is-measured) and the [limitations](#limitations).

**How it was built:** Aditya Rhayakar set the goal, labelled one development sheet, audited the test labels and made the final decisions. Claude Code wrote the extractor, the tooling and the other labels.

## Try it

```bash
pip install -r requirements.txt
python -m sdb.extract path/to/sheet.pdf
```

The output has this shape (the values here are invented):

```json
{
  "substance": {
    "product_name": "Beispielreiniger 100",
    "supplier": "Muster Chemie GmbH",
    "revision_date": "2024-03-01",
    "cas_numbers": ["64-17-5"]
  },
  "hazards": {
    "signal_word": "Gefahr",
    "h_codes": ["H225", "H319"],
    "p_codes": ["P210", "P305+P351+P338"],
    "pictograms": ["GHS02", "GHS07"]
  },
  "protection": {
    "eye": "required",
    "hand": "required",
    "respiratory": "conditional",
    "body": "not_stated",
    "glove_materials": ["NBR"]
  },
  "needs_review": false,
  "review_reasons": []
}
```

Each protection level is `required`, `conditional`, `not_required` or `not_stated`.

## How it works

The extractor is rule-based and needs no API key or network.

1. **Reading:** it rebuilds visual lines from word positions, because the text order inside a PDF often ignores the layout. Table columns stay separated, and running headers and footers are dropped.
2. **Sections:** it splits the sheet by the headings of the 16 sections REACH requires, allowing for layouts such as `2.`, `ABSCHNITT 2:` and `02`.
3. **Fields:** it reads each field from its section and validates CAS numbers by check digit.
4. **Pictograms:** it trusts `GHS0x` codes printed in Section 2.2. Otherwise it renders the page, finds the red diamonds and matches each one against a template.
5. **Cross-check:** it compares pictograms with the H-codes on the label under CLP. An aerosol can be classified H304 in 2.1 without carrying it on the label, so only the codes in 2.2 count.
6. **Review routing:** `needs_review` is set when a sheet shows something a correct sheet shouldn't, such as a missing section, a failed CAS check digit or pictograms that disagree with the H-codes. `review_reasons` says why.

## How accuracy is measured

The evaluation was fixed before the extractor existed, so the result can't be tuned to the answer.

- **Corpus:** 70 sheets from 53 web hosts. They came from web searches, so this is a convenience sample, not a representative one.
- **Split:** a seeded draw, stratified by product category, locked 20 development and 50 test sheets. `manifest.csv` records each file's SHA-256, and `tools/collect.py` refuses to draw again.
- **Order of work:** labels were finished before any extractor code, and the scoring rules in `tools/score.py` were written first as well.
- **Blindness:** until the scored run, the session writing the extractor didn't read a test sheet or test label. One automated label check ran over the test PDFs and printed only sheet ids. It showed that the extractor can't find every section on two sheets, and no rule was changed in response. During the audit, a comparison listed the changed fields by name only, and the label checker printed one value, S033's `-`. The extractor wasn't changed after either.
- **One test run:** the extractor ran on test once. Every scoring is logged to `reports/test_runs.log` with a hash of the extractor.
- **Metrics:** exact accuracy per field with a 95% Wilson interval, plus precision and recall for list fields. Scores are also reported for the sheets not sent to review.

## Results

### Test set (50 sheets)

**616 of 650 fields are correct (94.8%).** The extractor ran once on these sheets, on 2026-10-31, with hash `10c0b1579f5eb757`. It hasn't changed since, and any fix made from these results would need new sheets to measure it. Scoring is logged twice, because four labels were reversed after the first scoring, as explained below.

| Field | Correct | Accuracy | 95% interval |
|---|---:|---:|---:|
| `product_name` | 48/50 | 96.0% | 86.5–98.9% |
| `supplier` | 46/50 | 92.0% | 81.2–96.8% |
| `revision_date` | 49/50 | 98.0% | 89.5–99.6% |
| `cas_numbers` | 49/50 | 98.0% | 89.5–99.6% |
| `signal_word` | 50/50 | 100.0% | 92.9–100.0% |
| `h_codes` | 49/50 | 98.0% | 89.5–99.6% |
| `p_codes` | 50/50 | 100.0% | 92.9–100.0% |
| `pictograms` | 50/50 | 100.0% | 92.9–100.0% |
| `eye` | 46/50 | 92.0% | 81.2–96.8% |
| `hand` | 46/50 | 92.0% | 81.2–96.8% |
| `respiratory` | 41/50 | 82.0% | 69.2–90.2% |
| `body` | 43/50 | 86.0% | 73.8–93.0% |
| `glove_materials` | 49/50 | 98.0% | 89.5–99.6% |

Precision and recall for the list fields are in `reports/test.md`.

- **Codes, dates and pictograms:** 297 of 300 fields are correct (99.0%). Two misses are on S006, where Section 3 wasn't found, and one is S033's date, printed only in the footer. Both sheets went to review.
- **Protection levels:** 176 of 200 fields are correct (88.0%). These depend on free-text wording, so this is the weak spot.
- **Review routing:** 6 sheets went to review. The other 44 score 546 of 572 fields (95.5%), only slightly better than all 50, because `needs_review` caught just 8 of the 34 wrong fields.

**Why scoring ran twice.** The first scoring gave 614 of 650 (94.5%, kept in `reports/test_first_run.md`). It used four labels the audit had just changed. A comparison with the PDFs after that scoring found all four conflicted with the guide:

- **S033 `revision_date`:** the audit set this to `-`, but every page footer prints `23.08.2018`, which the date rule accepts. Reversing this cost the extractor one field.
- **S022, S040 and S053 `respiratory`:** the audit changed these from `conditional` to `required`, but the sheets tie the protection to conditions, such as *erforderlich bei: hohen Konzentrationen*. Reversing these gained the extractor three fields.

All four were reversed on the project owner's decision, so the test labels now match the agents' originals. The reversals came after the results were known, which is why both figures are shown. Both scorings read the same extractor output.

### Where the test misses came from

| Cause | Wrong fields | Example |
|---|---:|---|
| Wording rules misjudged a protection level | 14 | *Bei jeglichen Arbeiten* reads as a condition, while *in schlecht belüfteter Umgebung* doesn't |
| Protection heading missed or its text misread | 8 | Glove text read as body protection |
| Supplier or product name took the wrong text | 6 | *Technische Auskunft* as the supplier |
| Blue signs | 2 | S033 asks for goggles and clothing with signs only |
| Section 3 not found | 2 | S006 |
| Date printed only in the footer | 1 | S033 |
| Glove materials missed | 1 | S027 |

### Development set (20 sheets)

259 of 260 fields are correct, and every field is at 95% or better. This is **not** a performance claim, because the rules were tuned on these sheets. With only 20 sheets, the interval on a perfect field still starts at 83.9%. The full table is in `reports/dev.md`.

The one miss is S004, whose eye protection exists only as a blue sign. That sheet is sent to review.

With each development sheet left out of the templates, 25 of 25 testable diamonds were named correctly. The real diamonds scored 0.82 or higher. A pictogram with no template scored 0.66 and logos about 0.2, which is why the cut-off is 0.75.

## Where the labels came from

| Sheets | Made by |
|---|---|
| S004 (dev) | The project owner, by hand |
| The other 19 dev sheets | Claude, in the session writing the extractor |
| 50 test sheets | Separate Claude agents that never saw the extractor |

The labels were created with AI assistance, so they aren't hand-labelled. `LABELLING_GUIDE.md` holds the rules.

**Audit status: finished.** The project owner reviewed six test sheets in full and the 51 fields the agents marked as uncertain, which is 117 of the 650 test fields. The other 533 weren't reviewed by a person. The audit first changed 4 of the 65 fields on the five random sheets, and all four were reversed after scoring, as explained under the test results. That leaves no confirmed label errors on those sheets, but the reversals came from an AI comparison that the owner approved, so this isn't a fully independent check. `LABEL_AUDIT.md` has the details.

The labelling agents used a text reading aid with a known fault: it could drop part of a section when a table ran onto the next page. The extractor exposed this on dev sheet S035, whose label was then corrected against the rendered page. An automatic comparison found no such gaps on 48 test sheets but couldn't cover the other two. A fresh agent re-derived S006 from its PDF and changed nothing, and S033 is covered by the audit. The tool has since been removed.

## Limitations

- **Protection wording:** levels come from word lists, so a condition phrased without those words is missed. This was the largest source of test errors.
- **Review flag:** `needs_review` catches structural failures, not misjudged wording. It caught 8 of the 34 wrong test fields, so a sheet that isn't flagged can still be wrong.
- **Unusual layouts:** rules only cover layouts like the ones they were built on. Running 18 spare, unlabelled sheets exposed misses the development set had hidden. Those are fixed, but others will remain.
- **Footer dates:** running footers are dropped, so a date printed only there is missed. The sheet is sent to review.
- **Spare sheets:** they served as extra development data, checked by reading the output, so they give no accuracy figure.
- **Rare pictograms:** no available sheet shows GHS01, GHS03 or GHS04, so these rely on printed codes or the H-codes, and a sheet relying on H-codes is sent to review. GHS06 has a template from one sheet only.
- **Blue signs:** blue PPE signs aren't read.
- **Inline headings:** a protection heading placed at the end of a line is missed.
- **Pre-CLP sheets:** older sheets with R-phrases come through with empty hazard fields and aren't flagged.
- **Scanned sheets:** there's no OCR. None of the 70 sheets is a scan, and a scan would be flagged because its sections can't be found.

## Reproducing it

Supplier PDFs aren't in this repository. Download them from the URLs in `manifest.csv` to `corpus/<id>/sheet.pdf`, and compare the hashes to confirm they're the same files.

```bash
python test_rules.py
python -m sdb.extract dev
python -m tools.score dev
```

## Layout

| Path | Purpose |
|---|---|
| `sdb/extract.py` | The extractor |
| `sdb/signs.py`, `sdb/sign_templates.json` | Diamond detection and templates |
| `sdb/schema.py` | Field definitions shared by the labels, scorer and extractor |
| `tools/score.py` | Scoring |
| `tools/show_errors.py` | Prints each wrong development field |
| `tools/check_labels.py` | Validates `labels.xlsx` |
| `tools/make_templates.py` | Rebuilds the templates from development and spare sheets |
| `tools/collect.py`, `tools/make_sheet_index.py`, `tools/make_label_sheet.py` | Corpus and labelling setup |
| `test_rules.py` | Checks for the label, scoring and extraction rules |
| `labels.xlsx`, `LABELLING_GUIDE.md`, `LABEL_AUDIT.md` | Reference labels, their rules and the audit |
| `manifest.csv`, `sources.tsv` | Corpus records, including the split, hashes and source URLs |
| `reports/` | Scores, and the log of every test scoring |

## Licence

The code is under the MIT licence. The supplier PDFs aren't part of this repository and aren't covered by it.
