# Known limitations and production-completion backlog (D9)
- Devices, ILMS, e-mail/SMS are mocks; implement vendor adapters and test on real hardware.
- NCIP/SIP2 are partial subsets; run conformance tests before any compliance claim.
- Acquisitions and serials are minimal; add full workflows (claims, binding, budgets).
- SQLite is for demo scale; move to PostgreSQL + external search for multi-user production.
- No login lockout/MFA; add password policy tooling and TLS reverse proxy.
- Gate cache refresh is scheduled, not event-pushed; define staleness SLA.
- Member-card RFID tagging, hold/reservation queue, MARC import not implemented.
- Formal load/performance test and security review (pen-test) pending.
- UAT sign-off, training delivery and operational handover pending.
