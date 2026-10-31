"""Run with: python test_rules.py. Fails loudly if the label, scoring or extraction rules break."""
import pymupdf

from sdb.extract import (Line, cas_numbers, glove_materials, parse_dates, ppe_blocks, ppe_level, reconcile_pictograms,
                         review_reasons)
from sdb.schema import FIELDS, cas_valid
from sdb.signs import sign_rects, similarity
from tools.check_labels import row_problems, split_list
from tools.score import field_correct, score, wilson

assert cas_valid("64-17-5") and cas_valid("7664-93-9") and cas_valid("68442-22-8")
assert not cas_valid("64-17-6") and not cas_valid("6417-5")

low, high = wilson(48, 50)
assert round(low, 3) == 0.865 and round(high, 3) == 0.989

assert split_list("P210; P305 + P351 + P338;") == ["P210", "P305+P351+P338"]

assert field_correct("product_name", "Schneidöl", "SCHNEIDOEL")
assert field_correct("supplier", "LIQUI MOLY GmbH", "Liqui Moly GmbH & Co. KG")
assert not field_correct("supplier", "LIQUI MOLY GmbH", "")
assert field_correct("h_codes", ["H222", "H229"], ["H229", "H222"])
assert not field_correct("h_codes", ["H222", "H304"], ["H222"])
assert field_correct("signal_word", None, None)

good = dict.fromkeys(FIELDS, "-")
good.update(product_name="X", supplier="Y", revision_date="2023-11-08", eye="required", hand="required",
            respiratory="conditional", body="not_stated", h_codes="H222;EUH066", p_codes="P410+P412",
            pictograms="GHS02", cas_numbers="64-17-5", glove_materials="NBR;FKM")
assert row_problems(good) == []
assert len(row_problems({**good, "h_codes": "H302+H332", "cas_numbers": "64-17-6", "revision_date": "08.11.2023"})) == 3

truth = {"A": {**{f: None for f in FIELDS}, "h_codes": ["H222", "H304"], "cas_numbers": [], "p_codes": [],
               "pictograms": [], "glove_materials": []}}
result = {row["field"]: row for row in score(truth, {"A": {"h_codes": ["H222", "H999"]}})}
assert result["h_codes"]["precision"] == 0.5 and result["h_codes"]["recall"] == 0.5
assert result["h_codes"]["correct"] == 0

assert {row["field"]: row for row in score(truth, {})}["signal_word"]["correct"] == 0  # no output is never right

assert cas_numbers([Line("64-\n17-5 64-17-6 200-578-6", 0, 0, [])]) == ["64-17-5"]
assert [date.isoformat() for date in parse_dates("8. November 2023, 2023-11-08, 31.02.2023")] == ["2023-11-08"] * 2

assert ppe_level("hand", "Schutzhandschuhe tragen.") == "required"
assert ppe_level("hand", "Bei der Arbeit Schutzhandschuhe tragen.") == "required"
assert ppe_level("respiratory", "Bei unzureichender Belüftung Atemschutz tragen.") == "conditional"
assert ppe_level("eye", "Nicht erforderlich.") == "not_required"
assert ppe_level("eye", "") == ppe_level("eye", "Siehe Abschnitt 7.") == "not_stated"
assert ppe_level("body", "Es ist keine besondere Schutzausrüstung erforderlich.") == "not_required"
assert ppe_level("respiratory", "Liegt die Konzentration über dem AGW, so muss Atemschutz getragen werden.") == "conditional"
assert ppe_level("respiratory", "Wo eine Exposition eintreten kann, wird Atemschutz empfohlen.") == "conditional"
assert ppe_level("hand", "Bei bestimmungsgemäßer Verwendung sind Schutzhandschuhe zu tragen.") == "required"

numbered = [Line(text, 0, 0, []) for text in ("8.2 Persönliche Schutzausrüstung", "8.3.2\tHandschutz\tSchutzhandschuhe tragen.")]
assert "Schutzhandschuhe" in ppe_blocks(numbered)[0]["hand"]
skin = [Line(text, 0, 0, []) for text in ("8.2 Persönliche Schutzausrüstung", "Hautschutz", "Handschuhe tragen.")]
assert "Handschuhe" in ppe_blocks(skin)[0]["hand"]  # a plain skin heading covers gloves

assert glove_materials("Handschuhe aus Nitril. Nr. 12.", "") == ["NBR"]  # Nr. is not natural rubber
assert glove_materials("Latex ist ungeeignet. Butyl.", "") == ["IIR"]
assert glove_materials("Handschuhe aus Polyethylen.", "Handschuhe aus Polyethylen.") == ["OTHER"]
assert glove_materials("Schuhe aus Leder.", "") == []  # leather only counts in the hand text

assert reconcile_pictograms(["GHS02"], ["H225"]) == (["GHS02"], False)
assert reconcile_pictograms(["GHS06"], ["H301", "H315"]) == (["GHS06"], False)  # GHS07 gives way to GHS06
assert reconcile_pictograms([], ["H280"]) == (["GHS04"], True)  # no template, so the H-code supplies it
assert reconcile_pictograms(["GHS02"], ["H272"]) == (["GHS03"], True)  # a flame over a circle reads as a flame
assert reconcile_pictograms(["GHS07"], []) == (["GHS07"], True)

sheet = {"substance": {"product_name": "X", "supplier": "Y", "revision_date": "2023-11-08", "cas_numbers": []},
         "hazards": {"signal_word": "Gefahr", "pictograms": ["GHS02"]},
         "protection": {"eye": "not_stated", "hand": "required"}}
some = [Line("x", 0, 0, [])]
assert review_reasons(sheet, {2: some, 3: some, 8: some}, False) == ["eye_not_stated"]
assert review_reasons({**sheet, "hazards": {"signal_word": None, "pictograms": ["GHS09"]}}, {2: some, 3: some, 8: some},
                      False) == ["eye_not_stated"]  # GHS09 can appear without a signal word
assert "section_3_not_found" in review_reasons(sheet, {2: some, 8: some}, False)

page = pymupdf.open().new_page()
red = {"color": (1, 0, 0), "width": 2}
page.draw_polyline([(50, 20), (80, 50), (50, 80), (20, 50), (50, 20)], **red)
page.draw_polyline([(150, 20), (180, 50), (150, 80), (120, 50), (150, 20)], **red)
page.draw_polyline([(210, 20), (240, 50), (210, 80), (180, 50), (210, 20)], **red)  # touches the one before it
page.draw_rect((200, 200, 240, 240), color=(1, 0, 0), fill=(1, 0, 0))  # solid red is not a diamond
page.draw_line((300, 300), (400, 300), **red)  # nor is a rule
assert len(sign_rects(page, page.rect)) == 3
assert sign_rects(page, pymupdf.Rect(0, 0, 10, 10)) == []
assert round(similarity([0, 1, 2, 3], [0, 2, 4, 6]), 3) == 1
print("ok")
