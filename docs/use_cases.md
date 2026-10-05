# Use cases (D1)
| ID | Actor | Flow | Acceptance |
|---|---|---|---|
| UC-01 | Librarian | Import spreadsheet (dry run, commit, reconcile, rollback) | AC01 |
| UC-02 | Librarian | Catalogue title, add copy, tag it (RFID console) | AC02 |
| UC-03 | Circulation staff | Check out / renew / check in, or via NCIP/SIP2 client | AC03 |
| UC-04 | Circulation staff | Attempt blocked loan (reference, blocked member, fines > limit) | AC04 |
| UC-05 | Librarian | Shelf inventory with handheld mock | AC05 |
| UC-06 | Security | Unauthorised removal at gate: alarm, CCTV, email | AC06 |
| UC-07 | Staff | Smart-card login; role limits | AC07 |
| UC-08 | Manager | Dashboard and filtered reports/CSV | AC08 |
| UC-09 | Administrator | Offline install, update, rollback | AC09 |
| UC-10 | Administrator | Restore after failed migration | AC10 |
Data dictionary: see model files (`*/models.py`) - field names are self-describing; ERD summary in architecture.md.
