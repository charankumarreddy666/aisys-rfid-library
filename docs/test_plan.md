# Test plan (D6)
| Type | How | Evidence |
|---|---|---|
| Functional/integration/regression | `scripts\test.cmd` (28 tests) | `test_evidence\results.txt` |
| Migration | MigrationTests + `scripts\demo_ac01_migration.cmd` (20,000 rows; ~3 s dry run, ~7 s commit on dev machine) | `data\reports\` |
| Backup/restore (AC10) | `scripts\demo_ac10_restore.cmd` | console output (fingerprints match) |
| Offline update/rollback (AC09) | UpdateTests + `scripts\demo_ac09_offline_update.cmd` | console output |
| Security | RBAC, API key, DTD rejection, CSV injection, masking, tamper/unsafe-path tests; `pip-audit -r requirements.txt` | CI log |
| Performance | Time the 20k import and search; record in results | manual table |
| UAT | Run each AC in `docs/acceptance_map.csv` with a stakeholder | sign-off sheet |
Defect log columns: ID, severity, steps to reproduce, owner, status, fix version, retest evidence.
Requirement mapping: `docs/RTM.csv`.
