"""Code 39 barcode rendered as inline SVG (demo-grade; validate with your scanner before production)."""
from html import escape

# n = narrow, w = wide; order: bar, space, bar, space ... (9 elements per character)
_PATTERNS = {
    "0": "nnnwwnwnn", "1": "wnnwnnnnw", "2": "nnwwnnnnw", "3": "wnwwnnnnn", "4": "nnnwwnnnw",
    "5": "wnnwwnnnn", "6": "nnwwwnnnn", "7": "nnnwnnwnw", "8": "wnnwnnwnn", "9": "nnwwnnwnn",
    "A": "wnnnnwnnw", "B": "nnwnnwnnw", "C": "wnwnnwnnn", "D": "nnnnwwnnw", "E": "wnnnwwnnn",
    "F": "nnwnwwnnn", "G": "nnnnnwwnw", "H": "wnnnnwwnn", "I": "nnwnnwwnn", "J": "nnnnwwwnn",
    "K": "wnnnnnnww", "L": "nnwnnnnww", "M": "wnwnnnnwn", "N": "nnnnwnnww", "O": "wnnnwnnwn",
    "P": "nnwnwnnwn", "Q": "nnnnnnwww", "R": "wnnnnnwwn", "S": "nnwnnnwwn", "T": "nnnnwnwwn",
    "U": "wwnnnnnnw", "V": "nwwnnnnnw", "W": "wwwnnnnnn", "X": "nwnnwnnnw", "Y": "wwnnwnnnn",
    "Z": "nwwnwnnnn", "-": "nwnnnnwnw", ".": "wwnnnnwnn", " ": "nwwnnnwnn", "*": "nwnnwnwnn",
}


def svg(text, height=50):
    clean = "".join(c for c in str(text).upper() if c in _PATTERNS and c != "*")
    x, bars = 0, []
    for ch in f"*{clean}*":
        for i, el in enumerate(_PATTERNS[ch]):
            w = 3 if el == "w" else 1
            if i % 2 == 0:
                bars.append(f'<rect x="{x}" y="0" width="{w}" height="{height}" fill="#000"/>')
            x += w
        x += 1  # inter-character gap
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {x} {height}" width="{x * 1.6:.0f}" height="{height}" '
        f'role="img" aria-label="Barcode {escape(clean)}">{"".join(bars)}</svg>'
    )
