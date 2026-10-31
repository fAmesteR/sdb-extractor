# Label audit

The `test` labels were made by AI agents, so the project owner checked a sample by hand before the extractor was scored against them.

## Sheets checked

| Sheet | Why | Fields checked | Fields changed, all reversed after scoring |
|---|---|---|---|
| S022 | Random | 13 | 1: `respiratory` |
| S033 | Random | 13 | 1: `revision_date` |
| S040 | Random | 13 | 1: `respiratory` |
| S050 | Random | 13 | 0 |
| S053 | Random | 13 | 1: `respiratory` |
| S021 | Targeted: the agent was unsure of 7 fields | 13 | 0 |

The five random sheets come from `random.Random(20261030).sample(...)` over the test ids in `manifest.csv` order, and they give the audit figure. S021 was picked because it looked risky, so counting it would skew the result.

## Result

The audit first changed 4 of the 65 fields on the five random sheets. The owner also reviewed the 51 fields the agents marked as uncertain, and only two of them changed, both already counted above: S033 `revision_date` and S040 `respiratory`. In total a person reviewed 117 of the 650 test fields.

Comparing the four changes with the PDFs after the first scoring found all four conflicted with the guide, so they were reversed on the owner's decision. S033's page footers all print `23.08.2018`, which the date rule accepts. On S022, S040 and S053 the text ties respiratory protection to conditions, so `conditional` stands. The test labels now match the agents' originals. The first scoring used the four changed labels and gave 614 of 650. The second used the final labels and gave 616 of 650.

That leaves no confirmed label errors on the sampled sheets, but it isn't a fully independent check, because the reversals came from an AI comparison that the owner approved.

## How each sheet was checked

1. The PDF was compared with the `test` tab of `labels.xlsx`, field by field, using `LABELLING_GUIDE.md`. The `notes` cell explains hard calls.
2. Any field judged wrong was corrected in the workbook.
3. `python -m tools.check_labels` checked the format of every label.

The session writing the extractor saw only the names of the changed fields, plus S033's `-`, which the label checker printed.

S033 needed extra care across Sections 2, 3 and 8. The labelling agents' text aid could drop part of a section, as it did on dev sheet S035. An automatic comparison found no gaps on 48 test sheets but couldn't cover S006 or S033. A fresh agent re-derived all 13 S006 fields from the PDF and changed none. S033 was left for this audit, because rechecking a sampled sheet first would have biased the figure.

## Fields the agents marked as uncertain

The agents flagged 51 of the 650 test fields, on 31 sheets, and the owner reviewed them.

| Sheet | Fields |
|---|---|
| S001 | h_codes, respiratory |
| S007 | body |
| S009 | hand |
| S010 | supplier |
| S011 | revision_date |
| S012 | body |
| S019 | revision_date |
| S021 | product_name, supplier, cas_numbers, signal_word, h_codes, p_codes, pictograms |
| S028 | h_codes, p_codes |
| S029 | respiratory |
| S030 | supplier |
| S033 | revision_date |
| S036 | product_name |
| S038 | body |
| S039 | p_codes, eye, product_name |
| S040 | respiratory |
| S043 | revision_date |
| S044 | h_codes |
| S045 | supplier, p_codes, body |
| S047 | eye, body |
| S048 | h_codes |
| S050 | h_codes, respiratory, body |
| S055 | product_name |
| S056 | supplier |
| S058 | h_codes |
| S060 | respiratory |
| S061 | supplier |
| S065 | h_codes |
| S067 | h_codes, respiratory |
| S068 | p_codes, hand, respiratory, body |
| S070 | h_codes, eye |
