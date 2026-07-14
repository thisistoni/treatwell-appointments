# Normalized Treatwell adapter contract

This contract lets the skill work with an official Treatwell API, a Pay Later Widget, or an authorized browser implementation without binding the agent to one vendor-specific tool name.

An adapter may expose native function tools, an MCP/tool server, CLI commands, or browser actions. Normalize their results to these concepts in agent state.

## 1. `list_services`

Read current bookable services for one configured venue.

### Input

```json
{
  "venue_url": "https://www.treatwell.at/ort/cs-beauty-4/",
  "locale": "de-AT"
}
```

### Output

```json
{
  "venue": {
    "name": "CS - Beauty",
    "url": "https://www.treatwell.at/ort/cs-beauty-4/",
    "timezone": "Europe/Vienna"
  },
  "services": [
    {
      "service_key": "adapter-stable-opaque-id",
      "name": "Handmassage",
      "variant": null,
      "duration_minutes": 10,
      "displayed_price": {
        "kind": "from_or_range",
        "amount": "10.00",
        "currency": "EUR",
        "display_text": "ab 10 €"
      },
      "staff": ["any", "opaque-staff-key"]
    }
  ],
  "fetched_at": "RFC3339 timestamp"
}
```

### Requirements

- Return only services currently visible/bookable through the approved integration.
- Keep identifiers opaque. Never guess or derive private endpoint IDs.
- Preserve duplicate service names as separate records when variants differ.
- Preserve whether the price is exact, starting, or a range.

## 2. `search_slots`

Read live slots for one exact service and date/time window.

### Input

```json
{
  "venue_key": "configured-venue",
  "service_key": "adapter-stable-opaque-id",
  "staff_key": "any",
  "date_from": "2026-07-15",
  "date_to": "2026-07-17",
  "time_from": "14:00",
  "time_to": "19:00",
  "timezone": "Europe/Vienna",
  "limit": 20
}
```

### Output

```json
{
  "slots": [
    {
      "slot_key": "opaque-one-time-slot-id-or-session-handle",
      "local_date": "2026-07-15",
      "local_time": "16:00",
      "timezone": "Europe/Vienna",
      "staff_key": "any",
      "staff_display": "Beliebiger Mitarbeiter",
      "duration_minutes": 10,
      "displayed_price": {
        "amount": "10.00",
        "currency": "EUR",
        "display_text": "10 €"
      }
    }
  ],
  "fetched_at": "RFC3339 timestamp"
}
```

### Requirements

- Slots are observations, not reservations.
- Return exact local date/time plus timezone.
- Return the price tied to the slot, not only the venue-page starting price.
- Support re-querying the exact chosen slot immediately before checkout.

## 3. `prepare_booking`

Build or navigate to checkout without final submission.

### Input

```json
{
  "slot_key": "opaque-slot-handle",
  "service_key": "opaque-service-id",
  "customer": {
    "full_name": "runtime-only",
    "email": "runtime-only",
    "phone": "runtime-only"
  },
  "payment_method": "pay_at_venue",
  "marketing_consents": {
    "treatwell": false,
    "venue": false
  }
}
```

### Output

```json
{
  "checkout_key": "opaque-session-handle",
  "summary": {
    "venue": "CS - Beauty",
    "service": "Handmassage",
    "local_date": "2026-07-15",
    "local_time": "16:00",
    "timezone": "Europe/Vienna",
    "staff": "any",
    "duration_minutes": 10,
    "price": {"amount": "10.00", "currency": "EUR"},
    "payment_method": "pay_at_venue"
  },
  "final_action_ready": true
}
```

### Requirements

- Must not execute the final booking side effect.
- Verify pay-at-venue is actually available.
- Keep marketing consents false by default.
- Return enough data to compare checkout with the customer's confirmed summary.

## 4. `create_booking`

Perform exactly one confirmed final submission.

### Input

```json
{
  "checkout_key": "opaque-checkout-handle",
  "confirmation_id": "ledger-generated-id",
  "idempotency_key": "ledger-generated-id"
}
```

### Output: definitive success

```json
{
  "status": "booked",
  "booking_reference": "provider-reference",
  "summary": {
    "local_date": "2026-07-15",
    "local_time": "16:00",
    "timezone": "Europe/Vienna",
    "payment_method": "pay_at_venue"
  }
}
```

### Output: definitive rejection

```json
{
  "status": "rejected",
  "code": "slot_unavailable",
  "message": "Safe customer-facing reason"
}
```

### Output: ambiguous result

```json
{
  "status": "submission_unknown",
  "message": "Submission started but confirmation could not be verified"
}
```

### Requirements

- Call only after explicit confirmation bound to the unchanged summary.
- Pass a provider-supported idempotency key when the official API accepts one.
- Never map a transport timeout to `rejected`; use `submission_unknown`.
- Never retry `submission_unknown` without reconciliation.

## 5. `get_booking`

Reconcile an ambiguous submission or retrieve definitive booking state.

### Input

Use the strongest approved identifier available:

```json
{
  "confirmation_id": "ledger-generated-id",
  "booking_reference": "optional-provider-reference",
  "conversation_id": "opaque-runtime-id"
}
```

### Output

```json
{
  "status": "booked | not_found | cancelled | unknown",
  "booking_reference": "provider-reference-or-null",
  "summary": {}
}
```

A `not_found` result is safe for retry only when the integration documents that lookup as authoritative for the attempted submission window. Otherwise require human review.

## Adapter rules

- Validate all required fields; do not invent missing service, staff, slot, price, or customer data.
- Treat amounts as decimal strings plus ISO currency, never binary floats.
- Use RFC 3339 timestamps and explicit IANA timezones.
- Exclude customer PII from routine logs and ledger records.
- Return machine-readable state plus a concise diagnostic; do not leak credentials or raw HTML.
- Browser adapters should implement the same states even if their “keys” are in-memory handles rather than API IDs.
