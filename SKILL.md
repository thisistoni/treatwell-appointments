---
name: treatwell-appointments
description: "Operate authorized Treatwell appointment workflows for messaging agents: explain and match venue services, find live availability, suggest slots, collect required guest details, and book only after explicit customer confirmation with pay-at-venue selected. Use for WhatsApp or chat-based salon scheduling when an approved Treatwell API, widget, or licensed browser workflow is available."
license: MIT
compatibility: Requires network access and either an approved Treatwell API/widget integration or an authorized browser tool. Python 3.9+ is optional for the bundled idempotency ledger.
metadata:
  author: thisistoni
  version: "1.1.0"
  standard: agentskills.io
---

# Treatwell Appointments

## Purpose

Run a reliable customer conversation from service discovery through appointment confirmation while keeping the booking side effect explicit, reviewable, and idempotent. This skill is channel-agnostic; WhatsApp supplies messages, while an approved Treatwell API/widget or browser tool supplies live booking data.

## Authorization gate

Before accessing Treatwell, identify the deployment's configured integration mode:

1. **Official API or Pay Later Widget** — preferred. Use credentials and documentation supplied by Treatwell to the salon.
2. **Licensed browser workflow** — use only when the salon or operator has written authorization covering automated access.
3. **No documented authorization** — do not automate service extraction, availability lookup, or checkout. Explain that Treatwell authorization is required and offer the venue's normal Treatwell booking link instead.

Do not reverse-engineer private endpoints, replay captured requests, bypass anti-bot controls, or treat `robots.txt` as contractual permission. Treatwell's public website terms prohibit automated content/data extraction without a written license; its partner terms describe APIs and Pay Later Widgets but also restrict third-party booking software. See [references/treatwell-evidence.md](references/treatwell-evidence.md).

## Required runtime capabilities

Use the best authorized adapter available:

| Priority | Adapter | Needed capabilities |
| --- | --- | --- |
| 1 | Official API/tool | `list_services`, `search_slots`, `create_booking`, `get_booking` or equivalent |
| 2 | Pay Later Widget | Approved widget URL or integration surfaced as a browser flow |
| 3 | Browser | Navigate, inspect DOM/accessibility tree, click, type, and verify page state |

For the normalized tool contract, read [references/tool-contract.md](references/tool-contract.md). For browser operation, read [references/browser-workflow.md](references/browser-workflow.md).

If the host has no compatible tool, stop before claiming live prices, times, or booking success.

## Conversation state

Maintain one state object per customer conversation:

```text
conversation_id
venue_url
service: {name, variant, duration, displayed_price}
staff_preference
slot: {local_date, local_time, timezone, staff, displayed_price, fetched_at}
payment: {method = pay_at_venue, due_now = 0, card_protection = none}
terms: {cancellation, no_show}
customer: {full_name, email, phone}
status = collecting | proposing | awaiting_confirmation | confirmed |
         submitting | booked | submission_unknown | rejected | aborted
confirmation_id
booking_reference
```

Keep customer PII in the channel's protected runtime state, not in prompts, logs, source control, screenshots, or the bundled ledger. The optional `scripts/booking_ledger.py` stores only non-PII booking facts and submission state.

## Workflow

### 1. Resolve the request

Collect only what is needed to search:

- requested service or goal;
- acceptable date or date range;
- preferred time window;
- staff preference, if any.

Ask one concise question when a missing choice materially changes the search. Do not collect email or full name before a service and slot are plausible.

**Complete when:** venue, service intent, date window, and time preference are known.

### 2. Read current services

Use the authorized adapter. For a browser:

1. Open the configured venue URL.
2. Locate **All services / Alle Services** rather than relying only on popular services.
3. Read visible service names, variants, durations, current displayed prices, and relevant details.
4. Match by meaning, not by position. If two services have the same label, preserve their distinct variant/details.
5. Never promise a starting price (`ab`, `from`) as the final price.

Offer at most five relevant choices in the customer's language. Include duration and displayed price/range.

**Complete when:** the customer has selected one exact service/variant available on the live page.

### 3. Search live availability

1. Select the exact service and any required option.
2. Open availability through the normal approved flow.
3. Apply the requested staff preference or retain **Any staff / Beliebiger Mitarbeiter**.
4. Search the requested date range and time window.
5. Record the page's timezone; for the Austrian venue use `Europe/Vienna` unless the live integration reports otherwise.
6. Capture 3–5 useful slots with exact local date, time, staff/any-staff, and slot-specific price.
7. Record `fetched_at`. Treat results as volatile.

Suggest a small ranked set, for example earliest match plus two alternatives. Say that availability is live and may change until booked.

**Complete when:** the customer has chosen one exact live slot.

### 4. Collect booking details

For guest checkout, collect exactly:

- full name;
- email address;
- phone number.

Use the phone number from the authenticated WhatsApp sender only when the deployment policy allows it and the customer knows it will be used for the booking. Ask for missing details. Read back masked values when clarification is needed; do not echo the full phone or email unnecessarily.

Do not opt the customer into Treatwell or salon marketing. Marketing consent is separate from consent to book and must remain unchecked unless the customer explicitly opts in to each specific checkbox.

**Complete when:** all required guest fields are present and syntactically plausible.

### 5. Revalidate and request explicit confirmation

Immediately before asking for confirmation, re-open or refresh availability. If the slot or price changed, present the change and obtain a new selection.

Send one final summary containing:

- venue;
- exact service and variant;
- local date, time, and timezone;
- staff or any-staff;
- duration;
- final displayed price and amount due now;
- payment: **pay at venue / Vor Ort zahlen**;
- whether card/no-show protection is required;
- live cancellation and no-show terms;
- the exact customer fields that will be shared with Treatwell and the venue.

End with an explicit question such as:

> Soll ich diesen Termin jetzt verbindlich mit „Vor Ort zahlen“ buchen? Bitte antworte mit **Ja, buchen**.

Accept only an unambiguous affirmative response to that exact summary. Silence, emojis, “looks good,” a previous generic “yes,” or choosing a slot is not booking authorization. Any change to service, slot, staff, price, customer identity, or payment invalidates the confirmation.

If using the ledger, run `prepare`, then `confirm` only after receiving the affirmative reply. See [references/idempotency.md](references/idempotency.md).

**Complete when:** a fresh, explicit confirmation is bound to the unchanged summary.

### 6. Prepare checkout

Using the same authorized session:

1. Select the confirmed slot.
2. Confirm the checkout page still shows the same venue, service, date, time, duration, staff, and price.
3. Fill the required guest fields.
4. Select **Pay at venue / Vor Ort zahlen**. Verify it is selected, the amount due now is zero, and no card-protection/card-collection step is required; do not infer this from venue metadata.
5. Read and compare the live cancellation and no-show terms with the confirmed summary.
6. Leave optional marketing checkboxes unchecked unless separately authorized.
7. Inspect the final action label and stop before activating it.

If any confirmed fact or term differs, return to step 5. If pay-at-venue without card protection is unavailable, do not switch to card or PayPal; tell the customer and stop under this skill's no-card policy.

**Complete when:** checkout matches the confirmed summary and the next action is the single final booking submission.

### 7. Submit exactly once

1. Atomically claim the confirmation in the ledger, if available.
2. Activate the final booking button exactly once.
3. Wait for a definitive confirmation page, booking reference, or confirmed booking record.
4. Record the reference and mark the ledger `booked`.
5. Send the customer the confirmed service, date/time, venue, payment method, and reference.

Never announce success from a click alone.

If the browser times out, disconnects, or shows an ambiguous response after the final click:

- mark the state `submission_unknown`;
- do **not** click again;
- reconcile through `get_booking`, the Treatwell account/confirmation email, or a human operator;
- tell the customer the booking result is being verified, not that it failed.

If Treatwell definitively rejects the submission and confirms that no booking was created:

- mark the ledger `rejected` with the provider's safe reason;
- tell the customer the appointment was not booked;
- search again only with the customer's approval and obtain a new confirmation.

**Complete when:** Treatwell provides definitive confirmation or rejection, or the run is safely parked as `submission_unknown` for reconciliation.

## Browser reliability rules

- Prefer accessibility/DOM labels and semantic roles over coordinates.
- Refresh the page snapshot after every state-changing action; never reuse stale element references.
- Match service names plus duration/variant, not “the third Select button.”
- Read visible page state after clicks; a successful tool response does not prove the page changed.
- Do not construct or call undocumented private API requests. Internal URLs may be used only as page state observed during an authorized browser session, not as an API contract.
- Stop on CAPTCHA, anti-bot challenge, login/2FA prompt, unexpected payment request, or material redesign.
- Keep one browser context per conversation. Do not mix carts or customer details between chats.

## Customer communication rules

Read [references/whatsapp-conversation.md](references/whatsapp-conversation.md) for message templates.

- Reply in the customer's language; preserve service names as Treatwell displays them.
- Present 3–5 choices, not a page dump.
- Distinguish “available when checked” from “booked.”
- Never claim a discount, exact price, employee, or cancellation policy not shown live.
- Keep operational details, selectors, IDs, and tool errors out of customer messages.

## Failure handling

| Failure | Required action |
| --- | --- |
| Service missing or ambiguous | Offer live alternatives or ask which variant; do not guess. |
| No matching slots | Expand only within the customer's stated flexibility; otherwise ask. |
| Slot disappears before confirmation | Search again and request a new confirmation. |
| Price changes | Show the new amount and request a new confirmation. |
| Pay at venue absent, amount due now nonzero, or card protection required | Stop; this skill never silently crosses into payment/card handling. |
| Required PII missing | Ask for the missing field; do not invent it. |
| CAPTCHA / access block | Stop automation and hand off to a human or approved API. |
| Error before final click | Safely retry from a fresh snapshot if no side effect occurred. |
| Error after final click | Mark `submission_unknown`; reconcile, never resubmit blindly. |
| Definite rejection/no booking created | Explain the failure and search again only with customer approval. |

## Verification checklist

Before final submission:

- [ ] Deployment is authorized for the selected Treatwell adapter.
- [ ] Exact service/variant, duration, and current price are live.
- [ ] Slot was revalidated after the customer chose it.
- [ ] Full name, email, and phone came from the customer or approved profile data.
- [ ] Summary includes venue, service, date, time, timezone, staff, duration, price, due-now amount, pay-at-venue, cancellation/no-show terms, card-protection state, and customer-data disclosure.
- [ ] Customer explicitly confirmed that unchanged summary.
- [ ] Checkout still matches the summary.
- [ ] **Vor Ort zahlen** is visibly selected, amount due now is zero, and no card protection/card collection is required.
- [ ] Optional marketing checkboxes are unchecked unless separately authorized.
- [ ] Idempotency state allows exactly one submission.

After submission:

- [ ] A definitive Treatwell confirmation or booking record exists.
- [ ] Booking reference is recorded when provided.
- [ ] Customer received the final confirmed details.
- [ ] No PII or credentials were written to logs or source control.
