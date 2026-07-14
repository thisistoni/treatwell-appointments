# Confirmation and idempotency protocol

A WhatsApp message can be delivered twice, an agent can resume after a timeout, and a browser click can succeed even when its result is not observed. Treat the final booking as a distributed side effect.

## State machine

```text
prepared ──explicit customer confirmation──▶ confirmed
    │                                         │
    └──────────── abort ──────────────────────┘
                                              │ atomic claim
                                              ▼
                                          submitting
                                       /       |       \
                              success   ambiguous   definitive rejection
                                 ▼          ▼                 ▼
                               booked   submission_unknown   rejected
```

`submission_unknown` is terminal for automation until an approved lookup or human review reconciles it. `rejected` means the provider definitively reported that no booking was created.

## Confirmation binding

The bundled ledger generates `confirmation_id` from a canonical non-PII summary containing:

- opaque conversation ID;
- venue URL;
- exact service/variant;
- local date and time;
- timezone;
- staff/any-staff;
- duration;
- displayed price and currency;
- payment method and amount due now;
- cancellation and no-show terms;
- card-protection state.

Changing any field creates a different confirmation ID and requires a new customer confirmation. Customer name, email, and phone are deliberately excluded from the ledger; the protected runtime must still invalidate confirmation if customer identity changes.

## Commands

Set a private database path outside the source repository:

```bash
DB=/var/lib/agent/treatwell-bookings.sqlite3
```

### Prepare

```bash
python3 scripts/booking_ledger.py prepare \
  --db "$DB" \
  --conversation-id wa_opaque_123 \
  --venue-url https://www.treatwell.at/ort/cs-beauty-4/ \
  --service 'Handmassage' \
  --date 2026-07-15 \
  --time 16:00 \
  --timezone Europe/Vienna \
  --staff any \
  --duration-minutes 10 \
  --price 10.00 \
  --currency EUR \
  --payment pay_at_venue \
  --due-now 0 \
  --cancellation-terms '24h' \
  --no-show-terms 'full_price_may_apply' \
  --card-protection none
```

The command returns JSON with `confirmation_id`, `status`, and the customer-safe non-PII summary. Repeating the identical command returns the same record rather than creating a duplicate.

### Confirm

Run only after the customer explicitly confirms the unchanged final summary:

```bash
python3 scripts/booking_ledger.py confirm --db "$DB" --confirmation-id <id>
```

### Claim

Run immediately before the single provider-side final action:

```bash
python3 scripts/booking_ledger.py claim --db "$DB" --confirmation-id <id>
```

`claim` uses a SQLite immediate transaction. Only the first worker can transition `confirmed` to `submitting`; duplicate workers receive a non-zero exit and must not click.

### Complete

After definitive Treatwell confirmation:

```bash
python3 scripts/booking_ledger.py complete \
  --db "$DB" --confirmation-id <id> --booking-reference <reference>
```

### Ambiguous result

When a timeout/disconnect occurs after submission begins:

```bash
python3 scripts/booking_ledger.py unknown \
  --db "$DB" --confirmation-id <id> \
  --reason browser_disconnected_after_submit
```

Do not run `prepare`, `confirm`, and `claim` again to bypass this record. Reconcile first.

### Definitive rejection

When Treatwell definitively reports that no booking was created, record the rejection:

```bash
python3 scripts/booking_ledger.py reject \
  --db "$DB" --confirmation-id <id> --reason slot_unavailable
```

Use `rejected` only for an authoritative response, never for a timeout or lost browser connection. Search again and request a new customer confirmation before preparing another slot.

### Inspect

```bash
python3 scripts/booking_ledger.py status --db "$DB" --confirmation-id <id>
```

## Production notes

- The SQLite ledger is suitable for one host with multiple local workers.
- For multiple hosts, implement these same state transitions in a shared transactional database and use Treatwell's provider idempotency key if the approved API offers one.
- Restrict database file permissions and retention even though the bundled schema contains no direct customer PII.
- Use an opaque/hardened conversation ID rather than a raw phone number.
- Never make a failed browser tool call the reason to bypass the claim.
- An operator may resolve `submission_unknown` only after checking Treatwell's authoritative booking record or confirmation email.
