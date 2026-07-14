# Authorized browser workflow

Use this reference only when the deployment owner has documented permission for automated Treatwell browser access. Prefer an official API or Pay Later Widget when available.

## Browser capability adapter

Map the host's browser tools to these operations:

| Capability | Examples of equivalent host actions |
| --- | --- |
| Navigate | open URL, `browser_navigate`, goto |
| Inspect | accessibility snapshot, DOM query, page text, screenshot |
| Activate | click semantic element by role/name |
| Enter text | fill/type into labeled field |
| Wait | wait for URL, heading, or page state |
| Verify | fresh snapshot plus visible summary comparison |

Do not require a particular tool name. If DOM/accessibility inspection exists, prefer it over coordinate clicking.

## Observed CS Beauty flow

Venue URL:

```text
https://www.treatwell.at/ort/cs-beauty-4/
```

Labels observed on 2026-07-14; Treatwell may change them:

| Stage | German labels seen |
| --- | --- |
| Venue | `Termin buchen`, `Beliebte Services`, `Alle Services`, `Auswählen`, `Ausgewählt` |
| Availability | `Zeit auswählen`, `Beliebiger Mitarbeiter`, date buttons, time buttons |
| Checkout | `Kasse`, `Als Gast buchen`, `Vollständiger Name`, `E-Mail`, `Telefonnummer` |
| Payment | `Vor Ort zahlen`, `Zahlung mit PayPal`, `Mit Karte zahlen` |
| Final action | `Buchung abschließen` |

The venue page also showed `Zahlungsmöglichkeiten Barzahlung`, but that venue information is not sufficient proof that the checkout option exists. Verify `Vor Ort zahlen` on the actual checkout.

## Service discovery

1. Navigate to the configured venue URL.
2. Inspect the page and locate `Alle Services`.
3. Read each relevant service card's:
   - category;
   - exact service label;
   - option/variant, if shown;
   - duration;
   - price or price range;
   - details relevant to the customer's request.
4. Preserve duplicate labels as separate choices when their options or internal cards differ.
5. Never target a service solely by list position or generic `Auswählen` text. Anchor the action to the nearest service name and duration.
6. After activation, take a fresh snapshot and verify the exact card says `Ausgewählt` or that the cart contains it.

Treat `ab 10 €` as “from €10,” not as the checkout total.

## Availability

1. Continue through the service card's normal booking flow.
2. Verify the page heading means `Zeit auswählen` / choose time.
3. Set `Beliebiger Mitarbeiter` or the customer-requested employee.
4. Select the requested local date.
5. Read visible time buttons and their slot-specific prices.
6. When moving to another date, wait for the slot list to refresh and take a fresh snapshot.
7. Return only slots matching the customer's stated time range.

Availability is volatile. Store the lookup time and recheck after the customer chooses.

## Checkout

After selecting the confirmed slot, checkout was observed to offer guest booking with:

- `Vollständiger Name`;
- `E-Mail`;
- `Telefonnummer`;
- payment radios including `Vor Ort zahlen`;
- optional Treatwell and salon marketing checkboxes;
- a final `Buchung abschließen` button.

Procedure:

1. Verify the cart summary before typing PII.
2. Fill the three guest fields from protected conversation state.
3. Select `Vor Ort zahlen`, even when it is already selected by default.
4. Verify the selected radio state after clicking.
5. Leave both marketing boxes unchecked unless the customer explicitly opted in to the corresponding sender.
6. Compare venue, service, date, time, duration, staff, and price to the confirmed summary.
7. Stop before `Buchung abschließen` until the idempotency claim succeeds.
8. Activate `Buchung abschließen` exactly once.
9. Verify a confirmation heading/reference or approved booking lookup before announcing success.

## Selector strategy

Preferred order:

1. role + accessible name;
2. associated label + input role;
3. stable visible text scoped to a service card;
4. stable test attribute if Treatwell exposes one and permission covers its use;
5. coordinates only as a last resort with a fresh screenshot.

Do not hardcode ephemeral element reference numbers. They are valid only for one snapshot.

## Stop and hand off

Stop automated operation when:

- a CAPTCHA or anti-bot challenge appears;
- the browser requires login, password, or 2FA not provided by the deployment owner;
- no pay-at-venue option exists;
- the checkout summary differs from the confirmed summary;
- the website redesign makes the final action ambiguous;
- a browser/network error occurs after the final click.

For a post-click ambiguity, preserve the browser context, mark `submission_unknown`, and reconcile before any retry.
