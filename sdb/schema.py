"""Field definitions shared by the label checker, the scorer and the extractor."""
import re

GROUPS = {
    "substance": ("product_name", "supplier", "revision_date", "cas_numbers"),
    "hazards": ("signal_word", "h_codes", "p_codes", "pictograms"),
    "protection": ("eye", "hand", "respiratory", "body", "glove_materials"),
}
FIELDS = tuple(field for group in GROUPS.values() for field in group)
LIST_FIELDS = frozenset({"cas_numbers", "h_codes", "p_codes", "pictograms", "glove_materials"})
PPE_FIELDS = ("eye", "hand", "respiratory", "body")

SIGNAL_WORDS = ("Gefahr", "Achtung")
PPE_LEVELS = ("required", "conditional", "not_required", "not_stated")
GLOVE_MATERIALS = ("NBR", "IIR", "FKM", "CR", "NR", "PVC", "PVA", "OTHER")
PICTOGRAMS = tuple(f"GHS0{number}" for number in range(1, 10))
NONE = "-"  # the sheet genuinely has nothing here; a blank cell means not labelled yet

H_CODES = frozenset("""
H200 H201 H202 H203 H204 H205 H206 H207 H208 H209 H210 H211
H220 H221 H222 H223 H224 H225 H226 H228 H229 H230 H231 H232
H240 H241 H242 H250 H251 H252 H260 H261 H270 H271 H272 H280 H281 H290
H300 H301 H302 H304 H310 H311 H312 H314 H315 H317 H318 H319
H330 H331 H332 H334 H335 H336 H340 H341 H350 H350i H351
H360 H360F H360D H360FD H360Fd H360Df H361 H361f H361d H361fd H362
H370 H371 H372 H373 H400 H410 H411 H412 H413 H420
EUH001 EUH006 EUH014 EUH018 EUH019 EUH029 EUH031 EUH032 EUH044 EUH059 EUH066 EUH070 EUH071
EUH201 EUH201A EUH202 EUH203 EUH204 EUH205 EUH206 EUH207 EUH208 EUH209 EUH209A
EUH210 EUH211 EUH212 EUH370 EUH371 EUH380 EUH381 EUH401 EUH430 EUH431 EUH440 EUH441 EUH450 EUH451
""".split())
P_CODE = re.compile(r"P\d{3}(\+P\d{3})*")


def cas_valid(cas):
    """Check the CAS format and its check digit."""
    if not re.fullmatch(r"\d{2,7}-\d{2}-\d", cas):
        return False
    digits = cas.replace("-", "")
    total = sum(place * int(digit) for place, digit in enumerate(reversed(digits[:-1]), 1))
    return total % 10 == int(digits[-1])
