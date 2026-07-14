# WhatsApp conversation patterns

Adapt the wording to the customer's language and the live Treatwell data. These are patterns, not hardcoded facts.

## 1. Clarify the service

```text
Gerne. Welche Behandlung möchtest du buchen, und an welchem Tag bzw. in welchem Zeitraum passt es dir ungefähr?
```

When live Treatwell results contain several matches:

```text
Ich habe drei passende Optionen gefunden:

1. [exact service] — [duration], [price/range]
2. [exact service] — [duration], [price/range]
3. [exact service] — [duration], [price/range]

Welche davon möchtest du?
```

Do not abbreviate away distinctions between variants.

## 2. Suggest live times

```text
Für [service] waren gerade diese Termine verfügbar:

• [weekday, date] um [time] — [staff/any staff], [slot price]
• [weekday, date] um [time] — [staff/any staff], [slot price]
• [weekday, date] um [time] — [staff/any staff], [slot price]

Welcher Termin passt dir? Die Verfügbarkeit kann sich bis zur Buchung noch ändern.
```

Always include the full date, not only “tomorrow,” so date interpretation is unambiguous.

## 3. Collect guest details

```text
Für die Gastbuchung brauche ich noch:

• deinen vollständigen Namen
• deine E-Mail-Adresse
• deine Telefonnummer
```

If the WhatsApp number may be used under the deployment's policy:

```text
Soll ich dafür diese WhatsApp-Nummer als Telefonnummer verwenden?
```

Do not expose internal storage, browser, or tool details.

## 4. Final binding confirmation

```text
Bitte prüfe die Buchung:

Salon: [venue]
Behandlung: [exact service/variant]
Termin: [weekday, full local date] um [time] ([timezone/city])
Mitarbeiter: [name/Beliebiger Mitarbeiter]
Dauer: [duration]
Preis: [final displayed amount]
Zahlung: Vor Ort zahlen

Soll ich diesen Termin jetzt verbindlich buchen? Bitte antworte mit „Ja, buchen“.
```

Good confirmation examples for that immediately preceding unchanged summary:

- `Ja, buchen.`
- `Bitte jetzt verbindlich buchen.`
- `Yes, book this exact appointment.`

Insufficient or ambiguous examples:

- a response sent before the final summary;
- `👍`;
- `passt` / `looks good`;
- choosing a time (`16 Uhr`);
- silence;
- a message that changes a fact (`Ja, aber lieber Betti`).

If the response changes anything, update the summary and ask again.

## 5. Confirm success

Send only after definitive Treatwell confirmation:

```text
Dein Termin ist bestätigt ✅

[service]
[weekday, full date] um [time]
[venue]
Zahlung: Vor Ort
Buchungsnummer: [reference, when provided]
```

If Treatwell provides cancellation/change instructions, include their official link or concise policy.

## 6. Ambiguous submission

When the final action may have succeeded but cannot yet be verified:

```text
Die Buchung wurde an Treatwell übermittelt, aber die Bestätigung konnte gerade nicht eindeutig geprüft werden. Ich buche nicht erneut, damit kein Doppeltermin entsteht. Der Status wird jetzt geprüft.
```

Do not say “it failed” or propose another slot until reconciliation proves no booking exists.

## 7. Handoff

For CAPTCHA, authorization failure, unavailable pay-at-venue, or an unrecoverable page change:

```text
Ich kann die Buchung gerade nicht sicher automatisiert abschließen. Ich gebe sie an einen Mitarbeiter weiter / hier ist der offizielle Buchungslink: [approved link].
```

Never ask the customer for a Treatwell password, payment-card number, SMS code, or 2FA code in WhatsApp.
