# Labelling guide

This is the answer key. The extractor is scored against these labels, so accuracy matters more than speed.

## Who made the labels

| Sheets | Made by |
|---|---|
| S004 (`dev`) | The project owner, by hand |
| S002 and the other 18 `dev` sheets | Claude, in the session that writes the extractor |
| 50 `test` sheets | Separate Claude agents that never see the extractor |

The accurate description is: reference labels created with AI assistance and audited by the project owner, as recorded in `LABEL_AUDIT.md`. Don't describe them as hand-labelled.

## Ground rules

1. **Copy from the PDF only.** Read each answer from the sheet itself, and look at the rendered pages as well as the text.
2. **Keep the test sheets blind.** Whoever writes the extractor doesn't read the test sheets or test labels. Whoever labels the test sheets doesn't see the extractor or its output.
3. **These rules are frozen.** They were settled on the `dev` tab and don't change for the `test` tab. If a test row turns out to be wrong later, fix it and record the fix in its `notes` cell.

## How to label one sheet

1. Open the PDF at `corpus/<id>/sheet.pdf`. `tools/make_sheet_index.py` builds `sheets.html`, a page that links to each one.
2. Fill in every field, using the rules below.
3. Write `-` if the sheet genuinely has nothing for a field. Leave a cell blank only if the sheet hasn't been done yet.
4. If a rule doesn't settle a case, write the best answer and explain it in `notes`.
5. If you edit `labels.xlsx`, save and close it, then run the checker. It can't read the file while Excel has it open.

```bash
python -m tools.check_labels
```

The checker catches typos and badly formatted codes. It can't tell whether an answer is correct.

## Field rules

| Column | Where to look | What to write |
|---|---|---|
| `product_name` | Section 1.1 | The name after *Handelsname*, *Produktname*, *Stoffname* or *Bezeichnung des Stoffs*, copied exactly, including any stray mark. *Handelsname* beats a plain *Name*. If there's no such word, use the name under *Produktidentifikator* or the product heading of Section 1. |
| `supplier` | Section 1.3 | Company name only, no address. If several companies are listed, use the one marked *Lieferant*, otherwise the first. |
| `revision_date` | Page 1 or the page header | The date of this version, as `YYYY-MM-DD`. See the date rule below. |
| `cas_numbers` | Section 3 only | Every CAS number in Section 3, separated by `;`. Skip `---` and components that show only an EC number. Write `-` if there are none. |
| `signal_word` | Section 2.2 | `Gefahr`, `Achtung`, or `-` if it says *entfällt* or the product isn't labelled. Use this spelling even if the sheet prints capitals. Sheets may print it without the word *Signalwort*. |
| `h_codes` | Sections 2.1 and 2.2 | Every H and EUH code from both parts, separated by `;`. That includes EUH codes under *Zusätzliche Angaben* or *ergänzende Kennzeichnungselemente*. Split combined codes: `H302+H332` becomes `H302;H332`. Write each code once. |
| `p_codes` | Section 2.2 | Every P code, separated by `;`. The list often runs onto the next page. Keep combined codes as one item, written without spaces: `P305+P351+P338`. Write `-` if the sheet prints none. |
| `pictograms` | Section 2.2 | Codes for the diamond symbols you can see, separated by `;`. See the key below. Write `-` if there are none. |
| `eye` | Section 8.2 | A level from the protective equipment table. Look for *Augenschutz* or *Augen-/Gesichtsschutz*. |
| `hand` | Section 8.2 | A level from the same table. Look for *Handschutz*. |
| `respiratory` | Section 8.2 | A level from the same table. Look for *Atemschutz*. |
| `body` | Section 8.2 | A level from the same table. Look for *Körperschutz*, or *Hautschutz* when it's about clothing. |
| `glove_materials` | Section 8.2 | Recommended materials, separated by `;`. See the glove table below. Write `-` if none are named. |

### Which date to use

Use the first of these that the sheet gives:

1. *Überarbeitet am*, *Überarbeitungsdatum*, *Bearbeitungsdatum*, *Revisionsdatum* or *Stand*
2. *Erstellt am*, *Erstellungsdatum*, *Ausgabedatum* or *Datum der Erstellung*
3. *Druckdatum* (print date) or a date with no word beside it, only if nothing else exists

If *Überarbeitet am* is empty, as in `Überarbeitet am: -`, move on to the next line of this list. If one entry gives two dates, use the later one.

Ignore *Ersetzt Fassung vom*, *Datum der letzten Ausgabe*, *Datum der ersten Ausgabe*, *Gültig ab* and *Tritt in Kraft ab*. Read dates day first, so `04/06/2026` is `2026-06-04`.

### Pictogram key

| Code | Symbol | Meaning |
|---|---|---|
| GHS01 | Exploding bomb | Explosive |
| GHS02 | Flame | Flammable |
| GHS03 | Flame over a circle | Oxidising |
| GHS04 | Gas cylinder | Gas under pressure |
| GHS05 | Liquid eating a hand and a metal bar | Corrosive |
| GHS06 | Skull and crossbones | Acutely toxic |
| GHS07 | Exclamation mark | Harmful or irritant |
| GHS08 | Person with a starburst on the chest | Serious health hazard |
| GHS09 | Dead tree and fish | Hazardous to the environment |

Label what the sheet shows or names. Don't work out a pictogram from the H-codes. Diamonds in Section 3 describe ingredients, so they don't count. A separate small-pack label (up to 125 ml) doesn't change the answer: use the main label.

### Protective equipment levels

Use Section 8.2 only. Ignore P280 in Section 2 and anything in Sections 5, 6 or 7.

| Level | Use it when the sheet says | Examples |
|---|---|---|
| `required` | Wear it, with no condition | *Schutzbrille tragen*, *Schutzhandschuhe*, *Geeigneten Atemschutz verwenden*, *Bei der Arbeit geeignete Schutzkleidung tragen*, *empfehlenswert* with no condition, or a blue safety sign |
| `conditional` | Wear it only in certain situations | *bei Spritzgefahr*, *bei längerem Kontakt*, *bei unzureichender Belüftung*, *bei Aerosolbildung*, *ggf.*, *bei Bedarf* |
| `not_required` | It isn't needed | *nicht erforderlich*, *entfällt* |
| `not_stated` | That type of protection isn't covered | No heading and no blue sign, or *keine Daten* |

If a sheet says "not needed normally, but use it if the limit is exceeded", choose `conditional`.

A blue round sign in Section 8.2 showing goggles, gloves, a mask or clothing counts as an instruction to wear it. Use `required`, unless the text for that item gives a condition.

*Bei der Arbeit* means "while working", so it isn't a condition. A table or sentence showing which filter or device suits which exposure level isn't a condition either, as long as every level needs one. It only tells you which to pick.

A heading with no condition still counts as `required` when what follows is only a standard number (*Augenschutz: EN 166*) or advice on choosing the item (*Das Handschuhmaterial muss undurchlässig sein*).

A heading whose text names no equipment and doesn't say whether it's needed is `not_stated`. Example: *Atemschutz: die Konzentration ist auf ein Minimum zu reduzieren*.

If one item has both an unconditional and a conditional instruction, use `required`. Example: *Schutzbrille verwenden* followed by a line about splashes.

`body` covers clothing, lab coats and safety shoes, including under *Sonstige Schutzmaßnahmen*. Skin cream and rest breaks don't count, so a *Hautschutz* section that covers only gloves and cream is `not_stated`.

### Glove materials

| Write | German words on the sheet |
|---|---|
| `NBR` | Nitril, Nitrilkautschuk, Acrylnitril-Butadien-Kautschuk, NBR |
| `IIR` | Butyl, Butylkautschuk |
| `FKM` | Viton, Fluorkautschuk, FKM |
| `CR` | Chloropren, Chloroprenkautschuk, Neopren |
| `NR` | Naturkautschuk, Naturlatex, Latex |
| `PVC` | Polyvinylchlorid, PVC |
| `PVA` | Polyvinylalkohol, PVA |
| `OTHER` | Any other named material |

Count every material the sheet recommends, including ones suited only to short contact. Skip materials listed as unsuitable (*ungeeignet*). *Gummi* alone isn't a material. An empty *Handschuhmaterial* or *Geeignetes Material* heading means `-`.

## Traps to watch for

- **Sections 3 and 16 describe the ingredients.** H-codes there don't count, unless they also appear in Section 2.
- **Classification and label can differ.** S002 lists H304 in 2.1 but not in 2.2. Include it, because `h_codes` covers both.
- **Pictograms are often images.** They won't appear if you search the PDF for text.
- **Protective equipment can be an image too.** S004 asks for eye protection only with a blue goggles sign, so check the page as well as the text. Section 8.2 often starts a page earlier than the gloves, so look at every page of it before you write `not_stated`.
- **Section 3 lists can be misleading.** S002 has a long footnote of EC numbers such as `309-877-7`. Those are not CAS numbers. The middle group tells them apart: EC numbers have three digits there (`309-877-7`) and CAS numbers have two (`64-17-5`).
- **Headings vary.** Some sheets use *1.* and *2.* instead of *ABSCHNITT 1* and *ABSCHNITT 2*.
- **Hazard-free products are valid.** A sheet may say the product isn't classified. Then `signal_word`, `h_codes`, `p_codes` and `pictograms` are all `-`.

## Worked example: S002

S002 is already filled in. Open it and compare the sheet with this row.

| Column | Value | Why |
|---|---|---|
| `product_name` | Schneidoel | Printed under 1.1 |
| `supplier` | LIQUI MOLY GmbH | First line under 1.3 |
| `revision_date` | 2023-11-08 | *Überarbeitet am*, not the print date of 09.11.2023 |
| `cas_numbers` | 68442-22-8 | The only CAS number. The base oil shows `---`. |
| `signal_word` | Gefahr | Printed under the flame, without the word *Signalwort* |
| `h_codes` | H222;H229;H304 | H304 comes from 2.1, the others from both parts |
| `p_codes` | P102;P210;P211;P251;P410+P412 | Section 2.2, with the combined code kept whole |
| `pictograms` | GHS02 | One flame |
| `eye` | required | *Schutzbrille dichtschließend*, no condition |
| `hand` | required | *Schutzhandschuhe*, no condition |
| `respiratory` | conditional | *Im Normalfall nicht erforderlich*, but a filter above the limit |
| `body` | required | *Ölbeständige Schutzkleidung* |
| `glove_materials` | NBR | *Schutzhandschuhe aus Nitril* |
