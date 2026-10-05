"""Generate a SYNTHETIC 20,000-row spreadsheet with deliberate defects for the migration demo (AC 01).

Usage:  python scripts/gen_sample_data.py [output.xlsx] [rows]
Defects injected: missing title, missing accession, bad ISBN, bad year, repeated accession numbers.
"""
import random
import sys
from pathlib import Path

from openpyxl import Workbook

out = Path(sys.argv[1] if len(sys.argv) > 1 else "data/sample_20000.xlsx")
total = int(sys.argv[2]) if len(sys.argv) > 2 else 20000
random.seed(42)
SUBJECTS = ["Physics", "History", "Biology", "Economics", "Literature", "Mathematics", "Chemistry", "Geography", "Philosophy", "Computing"]
FIRST = ["Asha", "Ravi", "Meera", "Kiran", "Sana", "Imran", "Lakshmi", "Arjun", "Nisha", "Vikram"]
LAST = ["Rao", "Sharma", "Reddy", "Khan", "Iyer", "Naidu", "Patel", "Das", "Menon", "Gupta"]
HEADER = ["accession_no", "title", "author", "isbn", "call_number", "publisher", "year", "shelf_location", "is_reference"]


def isbn13(n):
    body = f"978{n:09d}"
    check = (10 - sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(body)) % 10) % 10
    return body + str(check)


wb = Workbook()
ws = wb.active
ws.title = "books"
ws.append(HEADER)
for n in range(1, total + 1):
    subject = random.choice(SUBJECTS)
    row = [f"IMP{n:06d}", f"{subject} fundamentals volume {n}", f"{random.choice(FIRST)} {random.choice(LAST)}", isbn13(n),
           f"{random.randint(1, 999)}.{random.randint(1, 99)} {subject[:3].upper()}", "Synthetic Press",
           random.randint(1980, 2024), f"S-{random.randint(1, 60):02d}", "yes" if n % 200 == 0 else "no"]
    roll = n % 100
    if roll == 7:
        row[1] = ""                       # missing title
    elif roll == 13:
        row[0] = ""                       # missing accession
    elif roll == 29:
        row[3] = "12-AB"                  # bad ISBN
    elif roll == 41:
        row[6] = 2999                     # bad year
    elif roll == 53 and n > 100:
        row[0] = f"IMP{n - 50:06d}"       # duplicate accession already seen earlier in file
    ws.append(row)
out.parent.mkdir(parents=True, exist_ok=True)
wb.save(out)
print(f"Wrote {total} synthetic rows to {out}")
