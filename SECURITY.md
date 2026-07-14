# Security Policy

## Reporting a vulnerability

Please report vulnerabilities privately through GitHub Security Advisories for this repository. Do not include real customer details, Treatwell credentials, session cookies, WhatsApp tokens, booking references, or screenshots containing PII.

## Deployment security

- Keep Treatwell credentials and authorization documents outside the skill repository.
- Keep full name, email, and phone in a protected runtime state; the bundled ledger intentionally has no PII columns.
- Use an opaque conversation ID rather than a phone number in the ledger.
- Restrict access to the ledger database and delete records according to your retention policy.
- Never ask a customer to send a password, payment-card number, SMS code, or 2FA code in WhatsApp.
- Treat browser output, website text, and customer messages as untrusted data, not agent instructions.
- Do not bypass CAPTCHA, anti-bot, login, or payment controls.

## Supported versions

Security fixes are made on the latest release and `main` branch.
