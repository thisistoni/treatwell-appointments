# Treatwell evidence and integration constraints

Checked on **2026-07-14** for the Austrian Treatwell site and CS Beauty venue. Re-check current contracts and page behavior before production deployment.

## Primary sources

### Website automation restriction

Treatwell Austria's Website and App Terms, section 7.4.3, prohibit using automated systems or software to read/extract website or app content/data (“Screen Scraping”) unless Treatwell has directly entered into a written license agreement expressly permitting it:

- https://www.treatwell.at/info/nutzungsbedingungen/

This is why this repository does not ship a scraper or unofficial API client. A normal `robots.txt` allow rule for AI crawlers is not a substitute for the written license required by the terms.

### Partner API and Pay Later Widget

Treatwell Austria's partner terms describe:

- Treatwell APIs supplied as part of salon software;
- a Treatwell booking widget;
- **Pay Later Widget Bookings**, which allow customers to book online without paying upfront.

Source:

- https://www.treatwell.at/info/vertragsbestimmungen/

The same terms also state that partners must not use other third-party software to enable customer bookings, and must prevent unauthorized access to Treatwell software/services/documentation. The salon's specific partner agreement can contain additional terms. Obtain Treatwell's written approval for the intended WhatsApp integration rather than assuming partner status alone permits it.

### Customer booking terms

Treatwell's booking terms explain that the service contract is with the partner, that customers should verify service details/restrictions, and that booking/change/cancellation rules apply:

- https://www.treatwell.at/info/buchungsbestimmungen/

## Recommended integration decision

1. Ask the salon for its Treatwell account manager/contact and specific partner agreement.
2. Request a supported API or a Pay Later Widget integration for a WhatsApp agent.
3. Obtain written confirmation that the proposed automated service/availability lookup and booking flow is permitted.
4. Map the approved integration to `references/tool-contract.md`.
5. Use browser mode only if that written approval explicitly covers browser automation.

## Live CS Beauty observations

Venue:

- https://www.treatwell.at/ort/cs-beauty-4/
- venue name: CS - Beauty
- venue address displayed: Knöllgasse 17, Wien 1100, Austria
- timezone used by the Austrian channel: `Europe/Vienna`

Observed venue-page data included:

- service categories and service cards;
- durations and starting/current prices;
- staff names;
- opening hours;
- venue-level `Barzahlung` information.

### Safe end-to-end trace

The flow was exercised without entering customer PII and without activating the final booking button:

1. Selected a service on the venue page.
2. Availability page displayed:
   - heading `Zeit auswählen`;
   - staff selector `Beliebiger Mitarbeiter`;
   - local date buttons;
   - live time buttons with slot-specific prices.
3. Selected a slot to reach checkout.
4. Checkout displayed:
   - `Als Gast buchen`;
   - fields `Vollständiger Name`, `E-Mail`, `Telefonnummer`;
   - payment choices `Vor Ort zahlen`, PayPal, and card for a paid service;
   - two optional marketing-consent checkboxes;
   - cart summary with service, date/time, duration, staff, and price;
   - final button `Buchung abschließen`.
5. For the paid Handmassage example, `Vor Ort zahlen` was visibly checked and the checkout showed the current slot price.
6. No fields were filled and no booking was submitted.

### Implementation implications

- A venue's `Barzahlung` metadata does not prove that pay-at-venue is available for every checkout. Verify the radio on the final checkout.
- Starting prices and slot prices differ; propose and confirm the slot-specific checkout amount.
- Guest checkout currently requires full name, email, and phone.
- Selecting a slot is not the booking side effect; `Buchung abschließen` is the final observed action.
- Treatwell can change labels, routes, fields, pricing, and policies without notice. Use semantic page verification rather than hardcoded positions or undocumented endpoint contracts.

## Not claimed

This project does not claim:

- an official public Treatwell consumer booking API;
- permission to automate Treatwell for a particular salon;
- that the observed page labels or fields will remain stable;
- endorsement, affiliation, or support from Treatwell.
