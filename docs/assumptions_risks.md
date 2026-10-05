# Stage 1 (D0) - Assumptions, risks, dependencies, exclusions
All data and credentials in this repository are **synthetic**. No production system, database or personal data is used.

## Assumptions
1. Spreadsheet columns: accession_no, title, author, isbn, call_number, publisher, year, shelf_location, is_reference (one row = one title + one copy).
2. Accession number is the unique key and is also used as the barcode for imported rows.
3. Reference restriction is per copy (`Item.is_reference`). Fine limit, loan days, renewals are configurable.
4. "Security bit" = `RFIDTag.security_bit` (True = secured; set False on check-out, True on check-in).
5. Smart-card UID maps to one staff user (`StaffCard`).
6. Net cataloguing = metadata fetch by ISBN from an external catalogue (mock provider).
7. Virtual bookshelf = browsable per-shelf spine view.

## Risks
| Risk | Impact | Mitigation |
|---|---|---|
| Vendor SDK/device behaviour differs from mocks | Rework of adapters | Abstract classes isolate vendor code |
| NCIP/SIP2 subset incomplete | Interop gaps | Documented as boundary only; conformance testing in backlog |
| Stale gate cache while LMS offline | Missed/false alarms | Scheduled `export_gate_cache`; cache timestamp |
| SQLite concurrency limits | Slow under many writers | PostgreSQL path documented |
| Migration data quality | Rejected rows | Error CSV + dry-run + rollback |

## Dependencies
Python 3.10+, Django 5.2.4, openpyxl 3.1.5 (see `requirements.lock`, `docs/sbom.json`).

## Excluded work
Hardware manufacture/installation, production systems/data, certification claims (NCIP, SIP2, ISO, OEM).
