"""Download candidate sheets, reject unusable ones, and lock the dev/test split.

Run once. It refuses to run again if manifest.csv exists, because re-drawing the
split after seeing results would quietly invalidate the held-out test set.
"""
import csv
import hashlib
import random
import re
import shutil
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit

import pymupdf
import requests

ROOT = Path(__file__).resolve().parent.parent
CANDIDATES = ROOT / "corpus" / "_candidates"
MANIFEST = ROOT / "manifest.csv"
SEED = 20261030
TOTAL = 70
DEV_SLOTS = (0, 3)  # 2 in every 7 sorted sheets = 20 dev, 50 test, stratified by category
HOST_CAP = 5
MIN_CHARS_PER_PAGE = 100
MAX_BYTES = 30_000_000
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; sdb-extractor/0.1)"}


def download(url, dest):
    if dest.exists():
        return None
    try:
        response = requests.get(url, headers=HEADERS, timeout=45)
    except requests.RequestException as error:
        return f"network: {type(error).__name__}"
    if response.status_code != 200:
        return f"http {response.status_code}"
    if not response.content.startswith(b"%PDF"):
        return "not a pdf"
    if len(response.content) > MAX_BYTES:
        return "too large"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(response.content)
    return None


def inspect(path):
    """Return (pages, is_scan, reject_reason). Reads text only to accept or reject."""
    try:
        with pymupdf.open(path) as doc:
            pages = doc.page_count
            text = "\n".join(page.get_text() for page in doc)
    except Exception as error:
        return 0, False, f"unreadable: {type(error).__name__}"
    if pages < 3:
        return pages, False, "too short to be a full sheet"
    is_scan = len(text) / pages < MIN_CHARS_PER_PAGE
    if is_scan:
        return pages, True, None
    if not re.search(r"(?i)sicherheitsdatenblatt|erste-hilfe", text):
        return pages, False, "not a German sheet"
    if not re.search(r"(?i)\babschnitt\b|erste-hilfe-ma", text):
        return pages, False, "no section structure"
    if not re.search(r"\bH[2-4]\d\d\b", text) and re.search(r"R-S[äa]tze", text):
        return pages, False, "pre-CLP format"
    return pages, False, None


def host_family(url):
    parts = urlsplit(url).hostname.lower().split(".")
    return parts[-2] if len(parts) > 1 else parts[0]


def main():
    if MANIFEST.exists():
        sys.exit("manifest.csv already exists. The split is locked; delete it only to restart from nothing.")

    rows = list(csv.DictReader(open(ROOT / "sources.tsv", encoding="utf-8"), delimiter="\t"))
    usable, rejected, seen = [], Counter(), set()
    for number, row in enumerate(rows, 1):
        path = CANDIDATES / f"{number:03d}" / "sheet.pdf"
        problem = download(row["url"], path)
        time.sleep(0.5)
        if problem:
            rejected[problem] += 1
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest in seen:
            rejected["duplicate"] += 1
            continue
        seen.add(digest)
        pages, is_scan, problem = inspect(path)
        if problem:
            rejected[problem] += 1
            continue
        usable.append({**row, "path": path, "sha256": digest, "pages": pages, "scan": int(is_scan)})

    # Round-robin over categories so no product type dominates.
    rng = random.Random(SEED)
    by_category = defaultdict(list)
    for row in usable:
        by_category[row["category"]].append(row)
    for group in by_category.values():
        rng.shuffle(group)

    selected, hosts = [], Counter()
    while len(selected) < TOTAL and any(by_category.values()):
        for category in sorted(by_category):
            group = by_category[category]
            while group and len(selected) < TOTAL:
                row = group.pop()
                family = host_family(row["url"])
                if hosts[family] < HOST_CAP:
                    hosts[family] += 1
                    selected.append(row)
                    break
    if len(selected) < TOTAL:
        sys.exit(f"Only {len(selected)} sheets passed; add sources.tsv rows and rerun.")

    rng.shuffle(selected)
    for index, row in enumerate(sorted(selected, key=lambda r: r["category"])):
        row["split"] = "dev" if index % 7 in DEV_SLOTS else "test"

    with open(MANIFEST, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["id", "split", "category", "pages", "scan", "sha256", "url"])
        for number, row in enumerate(selected, 1):
            sheet_id = f"S{number:03d}"
            target = ROOT / "corpus" / sheet_id / "sheet.pdf"
            target.parent.mkdir(parents=True)
            shutil.move(row["path"], target)
            writer.writerow([sheet_id, row["split"], row["category"], row["pages"], row["scan"], row["sha256"], row["url"]])

    print(f"candidates: {len(rows)}  usable: {len(usable)}  selected: {len(selected)}")
    print("rejected:", dict(rejected))
    print("split:", dict(Counter(r["split"] for r in selected)))
    print("category:", dict(Counter(r["category"] for r in selected)))
    print("scans:", sum(r["scan"] for r in selected))
    print("hosts:", dict(hosts))


if __name__ == "__main__":
    main()
