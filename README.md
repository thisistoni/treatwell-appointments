# Treatwell Appointments Agent Skill

[![CI](https://github.com/thisistoni/treatwell-appointments/actions/workflows/ci.yml/badge.svg)](https://github.com/thisistoni/treatwell-appointments/actions/workflows/ci.yml)
[![Agent Skills](https://img.shields.io/badge/Agent%20Skills-compatible-4f46e5)](https://agentskills.io/)

A portable [Agent Skills](https://agentskills.io/) package for authorized salon agents that:

- explains and matches Treatwell services;
- checks live staff/date/time availability;
- suggests useful slots in WhatsApp or another chat channel;
- collects the guest details Treatwell requires;
- books only after an explicit final confirmation;
- enforces **pay at venue / Vor Ort zahlen**;
- requires an atomic idempotency claim before submission; a bundled SQLite ledger implements it for one-host deployments.

The skill is agent- and channel-agnostic. Your WhatsApp gateway handles messages; this skill defines the booking behavior; an approved Treatwell API, Pay Later Widget, or licensed browser tool performs the live actions.

## Important Treatwell integration constraint

Treatwell's Austrian website terms prohibit automated extraction of website/app content or data (“Screen Scraping”) without a written license. Treatwell's partner terms describe partner APIs and Pay Later Widgets, while also restricting third-party booking software. Therefore:

- **Production recommendation:** ask Treatwell to enable/document the salon's API or **Pay Later Widget** use for this WhatsApp agent.
- **Browser mode:** use only when the salon has written authorization that covers the automation.
- This repository intentionally does **not** ship an unofficial scraper or reverse-engineered private API client.

Primary-source links and the exact observed CS Beauty flow are documented in [`references/treatwell-evidence.md`](references/treatwell-evidence.md).

## Repository layout

```text
treatwell-appointments/
├── SKILL.md                         # portable agent instructions
├── references/
│   ├── browser-workflow.md          # browser adapter and observed labels
│   ├── idempotency.md               # exactly-once submission protocol
│   ├── tool-contract.md             # normalized API/browser tool contract
│   ├── treatwell-evidence.md        # sources, constraints, live-flow findings
│   └── whatsapp-conversation.md     # customer conversation templates
├── scripts/
│   ├── booking_ledger.py            # bundled SQLite side-effect ledger
│   ├── install.py                   # cross-agent installer
│   └── validate_skill.py            # Agent Skills validator
├── tests/
│   ├── test_booking_ledger.py
│   └── test_install.py
└── .github/workflows/ci.yml
```

## Install

### Universal installer

Clone the repository, then copy the skill into your agent's global skill directory:

```bash
git clone https://github.com/thisistoni/treatwell-appointments.git
cd treatwell-appointments
python3 scripts/install.py --agent codex
```

Supported targets:

```bash
python3 scripts/install.py --agent hermes
python3 scripts/install.py --agent codex
python3 scripts/install.py --agent claude
python3 scripts/install.py --agent opencode
python3 scripts/install.py --target /custom/agent/skills
```

The installer copies only runtime files (`SKILL.md`, `references/`, the ledger, and `LICENSE`). It refuses to overwrite by default; `--force` updates only known runtime files in a directory carrying the exact installer-owned manifest and preserves unknown files.

### Manual installation

Copy this repository (or at least `SKILL.md`, `references/`, `scripts/booking_ledger.py`, and `LICENSE`) into a directory named `treatwell-appointments` under your agent's skills directory:

| Agent | Global location |
| --- | --- |
| Hermes Agent | `~/.hermes/skills/treatwell-appointments/` |
| OpenAI Codex | `~/.agents/skills/treatwell-appointments/` |
| Claude Code | `~/.claude/skills/treatwell-appointments/` |
| OpenCode | `~/.config/opencode/skills/treatwell-appointments/` |

OpenCode also discovers the `.agents/skills/` and `.claude/skills/` locations. For a project-only installation, use the corresponding skill path inside the project.

## Configure the deployment

Give the agent these deployment facts in its normal secure configuration—not in the public skill:

```yaml
venue_url: https://www.treatwell.at/ort/cs-beauty-4/
timezone: Europe/Vienna
integration_mode: official_api # official_api | pay_later_widget | licensed_browser
authorization_reference: internal-contract-or-approval-id
ledger_path: /var/lib/your-agent/treatwell-bookings.sqlite3
```

Never commit API credentials, customer details, WhatsApp tokens, or Treatwell session cookies.

## Recommended production architecture

```text
Customer on WhatsApp
        │
        ▼
Your WhatsApp gateway / agent runtime
        │
        ├── loads this Agent Skill
        ├── conversation state + protected PII store
        └── exactly-once ledger (SQLite or your production DB)
        │
        ▼
Approved Treatwell adapter
  1. Official Treatwell API, or
  2. Pay Later Widget, or
  3. Licensed browser session
        │
        ▼
Treatwell booking confirmation
```

A skill is not the WhatsApp transport. For Hermes Agent, WhatsApp can be connected through the gateway; other runtimes can use Meta's WhatsApp Business Cloud API, Twilio, or their existing channel adapter.

## Exactly-once ledger

The ledger intentionally has no customer name, email, or phone columns. It stores a pseudonymous conversation key plus controlled booking facts and machine-readable outcome codes. The conversation key must be `conv_` plus a 64-character lowercase **HMAC-SHA256** digest generated by the protected gateway with a deployment secret; never pass a phone number, email, unsalted hash, or other direct channel identifier. Pseudonymous identifiers can still be personal data, so protect the database and apply a retention policy.

The confirmation binds a monotonically increasing `intent_version` plus duration, due-now amount, cancellation/no-show terms, and card-protection state. Start at `1` for a conversation and increment whenever a changed summary is prepared; replays of an older version cannot supersede the current intent. Preparing a higher-version summary atomically aborts any older `prepared` or `confirmed` intent, while an unresolved `submitting` or `submission_unknown` record blocks a new intent. Existing databases are migrated automatically, but pre-`intent_version` prepared/confirmed records remain readable and cannot be submitted.

```bash
DB=/secure/runtime/treatwell-bookings.sqlite3

python3 scripts/booking_ledger.py prepare \
  --db "$DB" --conversation-id conv_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa \
  --intent-version 1 \
  --venue-url https://www.treatwell.at/ort/cs-beauty-4/ \
  --service Handmassage --date 2026-07-15 --time 16:00 \
  --timezone Europe/Vienna --staff any --duration-minutes 10 \
  --price 10.00 --currency EUR --payment pay_at_venue --due-now 0 \
  --cancellation-terms '24h' --no-show-terms 'full_price_may_apply' \
  --card-protection none

python3 scripts/booking_ledger.py confirm --db "$DB" --confirmation-id <id>
python3 scripts/booking_ledger.py claim   --db "$DB" --confirmation-id <id>
# Activate Treatwell's final booking button exactly once here.
python3 scripts/booking_ledger.py complete --db "$DB" \
  --confirmation-id <id> --booking-reference <reference>
```

If the final click returns an ambiguous result:

```bash
python3 scripts/booking_ledger.py unknown --db "$DB" \
  --confirmation-id <id> --reason browser_disconnected_after_submit
```

Do not retry until a human or approved `get_booking` call proves no booking exists.

For a definitive provider response that says no booking was created:

```bash
python3 scripts/booking_ledger.py reject --db "$DB" \
  --confirmation-id <id> --reason slot_unavailable
```

## Validate and test

The runtime uses only Python's standard library. Python's `zoneinfo` also requires an IANA timezone database: this is normally supplied by Linux/macOS, while Windows or minimal containers may need the `tzdata` package.

```bash
python3 scripts/validate_skill.py .
python3 -m unittest discover -s tests -v
```

## What was verified

On 2026-07-14, the CS Beauty flow was exercised safely up to—but not including—the final booking action:

1. the venue page exposed services, duration, price, staff, and venue information;
2. availability showed live date and staff controls plus time-specific prices;
3. selecting a slot opened guest checkout;
4. checkout required full name, email, and phone;
5. **Vor Ort zahlen** was selected and card/PayPal were alternatives;
6. the final side-effect button was **Buchung abschließen**;
7. no customer data was entered and no appointment was submitted.

## License

MIT. Treatwell is a trademark of its respective owner. This project is independent and is not endorsed by Treatwell.
