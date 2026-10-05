# API documentation (D8)
All device/interop endpoints need header `X-API-Key: <INTEROP_API_KEY>` (from `.env`). Browser pages use session login + CSRF.

## Health
`GET /health` -> `{"status":"ok","version":"1.0.0","database":"ok",...}` (no login)

## RFID middleware (JSON)
| Endpoint | Body | Purpose |
|---|---|---|
| `POST /rfid/api/tag` | `{"accession_no":"ACC000001","tag_uid":"E20000000000009A","retag":false}` | Validate record and link tag |
| `POST /rfid/api/gate` | `{"event_id":"E1","tag_uid":"E200000000000002","lms_online":true}` or `{"event_id":"F1","kind":"FOOTFALL"}` | Gate event (idempotent on `event_id`) |
| `POST /rfid/api/inventory` | `{"shelf":"A-01","tags":["E200000000000001","..."]}` | Shelf inventory report |
| `GET /rfid/api/gate-cache` | - | Download security-bit cache for offline gates |

Errors: `401` bad key, `400` malformed JSON, `422` business rule (`{"error":"ITEM_NOT_FOUND","message":"..."}`).

## NCIP 2.0 (subset, mock) `POST /interop/ncip` (XML)
Supported: `LookupUser`, `LookupItem`, `CheckOutItem`, `CheckInItem`, `RenewItem`. Failures return `<Problem><ProblemType>CODE</ProblemType>...`.
```xml
<NCIPMessage xmlns="http://www.niso.org/2008/ncip"><CheckOutItem>
 <UserId><UserIdentifierValue>M0001</UserIdentifierValue></UserId>
 <ItemId><ItemIdentifierValue>BC000001</ItemIdentifierValue></ItemId></CheckOutItem></NCIPMessage>
```
## SIP2 boundary (subset, mock) `POST /interop/sip2` (text)
Messages `11` checkout, `09` checkin, `29` renew; fields `AO AA AB` separated by `|`. Responses `12/10/30`. Unsupported messages return `96`.

**Not certified.** Do not claim NCIP/SIP2 conformance without authorised testing.

Example (Windows):
`curl -X POST http://127.0.0.1:8000/rfid/api/gate -H "X-API-Key: dev-interop-key-change-me" -d "{\"event_id\":\"E1\",\"tag_uid\":\"E200000000000002\"}"`
