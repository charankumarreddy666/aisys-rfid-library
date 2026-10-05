"""Net cataloguing adapter: fetch bibliographic metadata by ISBN from an external catalogue.
The MOCK below is the offline stand-in for a real Z39.50/SRU/Open-data provider."""

_MOCK = {
    "9780132350884": {"title": "Clean Code", "author": "Robert C. Martin", "publisher": "Prentice Hall", "year": 2008, "call_number": "005.1 MAR"},
    "9780596007126": {"title": "Head First Design Patterns", "author": "Eric Freeman", "publisher": "O'Reilly", "year": 2004, "call_number": "005.12 FRE"},
    "9780262033848": {"title": "Introduction to Algorithms", "author": "Thomas H. Cormen", "publisher": "MIT Press", "year": 2009, "call_number": "005.1 COR"},
}


def lookup(isbn):
    return _MOCK.get("".join(ch for ch in (isbn or "") if ch.isdigit()))
