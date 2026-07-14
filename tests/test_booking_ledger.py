from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "booking_ledger.py"

LEGACY_SCHEMA = """
CREATE TABLE bookings (
    confirmation_id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    venue_url TEXT NOT NULL,
    service TEXT NOT NULL,
    local_date TEXT NOT NULL,
    local_time TEXT NOT NULL,
    timezone TEXT NOT NULL,
    staff TEXT NOT NULL,
    price TEXT NOT NULL,
    currency TEXT NOT NULL,
    payment TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    confirmed_at TEXT,
    submitting_at TEXT,
    completed_at TEXT,
    booking_reference TEXT,
    unknown_reason TEXT,
    rejected_at TEXT,
    rejection_reason TEXT
);
"""


class BookingLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "ledger.sqlite3"

    def run_cli(self, *args: str, expected: int = 0) -> tuple[dict, subprocess.CompletedProcess[str]]:
        process = subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(
            process.returncode,
            expected,
            msg=f"stdout={process.stdout}\nstderr={process.stderr}",
        )
        stream = process.stdout if expected == 0 else process.stderr
        return json.loads(stream), process

    def prepare_args(self, **overrides: str) -> list[str]:
        values = {
            "conversation_id": "wa_opaque_123",
            "venue_url": "https://www.treatwell.at/ort/cs-beauty-4/",
            "service": "Handmassage",
            "date": "2026-07-15",
            "time": "16:00",
            "timezone": "Europe/Vienna",
            "staff": "any",
            "duration_minutes": "10",
            "price": "10.00",
            "currency": "EUR",
            "payment": "pay_at_venue",
            "due_now": "0",
            "cancellation_terms": "24h",
            "no_show_terms": "full_price_may_apply",
            "card_protection": "none",
        }
        values.update(overrides)
        args = ["prepare", "--db", str(self.db)]
        for key, value in values.items():
            args.extend(("--" + key.replace("_", "-"), value))
        return args

    def prepare(self, **overrides: str) -> dict:
        return self.run_cli(*self.prepare_args(**overrides))[0]

    def command(self, name: str, cid: str, *extra: str, expected: int = 0) -> dict:
        return self.run_cli(
            name,
            "--db",
            str(self.db),
            "--confirmation-id",
            cid,
            *extra,
            expected=expected,
        )[0]

    def test_full_lifecycle(self) -> None:
        prepared = self.prepare()
        cid = prepared["confirmation_id"]
        self.assertEqual(prepared["status"], "prepared")
        self.assertNotIn("conversation_id", prepared["summary"])

        self.assertEqual(self.command("confirm", cid)["status"], "confirmed")
        self.assertEqual(self.command("claim", cid)["status"], "submitting")
        completed = self.command(
            "complete", cid, "--booking-reference", "TW-TEST-123"
        )
        self.assertEqual(completed["status"], "booked")
        self.assertEqual(completed["booking_reference"], "TW-TEST-123")
        self.assertEqual(self.command("status", cid)["status"], "booked")

    def test_prepare_is_deterministic_and_material_change_requires_new_confirmation(self) -> None:
        first = self.prepare(price="10.00")
        same = self.prepare(price="10.0")
        changed_price = self.prepare(price="7.50")
        changed_duration = self.prepare(duration_minutes="15")
        changed_terms = self.prepare(cancellation_terms="48h")
        changed_no_show = self.prepare(no_show_terms="no_fee")
        self.assertEqual(first["confirmation_id"], same["confirmation_id"])
        self.assertNotEqual(first["confirmation_id"], changed_price["confirmation_id"])
        self.assertNotEqual(first["confirmation_id"], changed_duration["confirmation_id"])
        self.assertNotEqual(first["confirmation_id"], changed_terms["confirmation_id"])
        self.assertNotEqual(first["confirmation_id"], changed_no_show["confirmation_id"])

    def test_claim_before_confirmation_is_refused(self) -> None:
        cid = self.prepare()["confirmation_id"]
        error = self.command("claim", cid, expected=2)
        self.assertFalse(error["ok"])
        self.assertIn("expected confirmed", error["error"])
        self.assertEqual(self.command("status", cid)["status"], "prepared")

    def test_second_claim_is_refused(self) -> None:
        cid = self.prepare()["confirmation_id"]
        self.command("confirm", cid)
        self.command("claim", cid)
        error = self.command("claim", cid, expected=2)
        self.assertIn("cannot transition submitting", error["error"])

    def test_ambiguous_submission_blocks_claim_and_completion(self) -> None:
        cid = self.prepare()["confirmation_id"]
        self.command("confirm", cid)
        self.command("claim", cid)
        unknown = self.command(
            "unknown", cid, "--reason", "browser_disconnected_after_submit"
        )
        self.assertEqual(unknown["status"], "submission_unknown")
        self.assertEqual(
            self.command("claim", cid, expected=2)["ok"], False
        )
        self.assertEqual(
            self.command(
                "complete",
                cid,
                "--booking-reference",
                "UNVERIFIED",
                expected=2,
            )["ok"],
            False,
        )

    def test_only_pay_at_venue_is_accepted(self) -> None:
        error, _ = self.run_cli(
            "prepare",
            "--db",
            str(self.db),
            "--conversation-id",
            "opaque",
            "--venue-url",
            "https://example.test/venue",
            "--service",
            "Service",
            "--date",
            "2026-07-15",
            "--time",
            "16:00",
            "--timezone",
            "Europe/Vienna",
            "--staff",
            "any",
            "--duration-minutes",
            "10",
            "--price",
            "10",
            "--currency",
            "EUR",
            "--payment",
            "card",
            "--due-now",
            "0",
            "--cancellation-terms",
            "24h",
            "--no-show-terms",
            "full_price_may_apply",
            "--card-protection",
            "none",
            expected=2,
        )
        self.assertIn("only payment=pay_at_venue", error["error"])

    def test_pay_at_venue_rejects_due_now_and_card_protection(self) -> None:
        due_now_args = self.prepare_args(due_now="5")
        due_error, _ = self.run_cli(*due_now_args, expected=2)
        self.assertIn("requires due_now=0", due_error["error"])

        card_args = self.prepare_args(card_protection="required")
        card_error, _ = self.run_cli(*card_args, expected=2)
        self.assertIn("does not authorize card protection", card_error["error"])

    def test_legacy_empty_schema_is_migrated(self) -> None:
        connection = sqlite3.connect(self.db)
        connection.executescript(LEGACY_SCHEMA)
        connection.execute(
            """INSERT INTO bookings (
                   confirmation_id, conversation_id, venue_url, service,
                   local_date, local_time, timezone, staff, price, currency,
                   payment, status, created_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "tw_legacy",
                "opaque",
                "https://example.test/venue",
                "Service",
                "2026-07-15",
                "16:00",
                "Europe/Vienna",
                "any",
                "10",
                "EUR",
                "pay_at_venue",
                "prepared",
                "2026-07-14T12:00:00+00:00",
            ),
        )
        connection.execute(
            """INSERT INTO bookings (
                   confirmation_id, conversation_id, venue_url, service,
                   local_date, local_time, timezone, staff, price, currency,
                   payment, status, created_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "tw_legacy_confirmed",
                "opaque",
                "https://example.test/venue",
                "Service",
                "2026-07-15",
                "16:00",
                "Europe/Vienna",
                "any",
                "10",
                "EUR",
                "pay_at_venue",
                "confirmed",
                "2026-07-14T12:00:00+00:00",
            ),
        )
        connection.commit()
        connection.close()
        self.prepare()
        legacy_error = self.command("confirm", "tw_legacy", expected=2)
        self.assertIn("legacy confirmation lacks material terms", legacy_error["error"])
        legacy_claim = self.command("claim", "tw_legacy_confirmed", expected=2)
        self.assertIn("legacy confirmation lacks material terms", legacy_claim["error"])
        connection = sqlite3.connect(self.db)
        columns = {row[1] for row in connection.execute("PRAGMA table_info(bookings)")}
        connection.close()
        self.assertTrue(
            {"duration_minutes", "due_now", "cancellation_terms", "no_show_terms", "card_protection"}
            <= columns
        )

    def test_concurrent_first_open_migrates_legacy_schema_once(self) -> None:
        race_db = Path(self.temp.name) / "legacy-race.sqlite3"
        connection = sqlite3.connect(race_db)
        connection.executescript(LEGACY_SCHEMA)
        connection.close()

        args = self.prepare_args()
        args[2] = str(race_db)
        command = [sys.executable, str(SCRIPT), *args]
        first = subprocess.Popen(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        second = subprocess.Popen(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        first_stdout, first_stderr = first.communicate(timeout=15)
        second_stdout, second_stderr = second.communicate(timeout=15)
        self.assertEqual(first.returncode, 0, first_stderr)
        self.assertEqual(second.returncode, 0, second_stderr)
        self.assertEqual(
            json.loads(first_stdout)["confirmation_id"],
            json.loads(second_stdout)["confirmation_id"],
        )

        connection = sqlite3.connect(race_db)
        columns = {row[1] for row in connection.execute("PRAGMA table_info(bookings)")}
        connection.close()
        self.assertTrue(set(("duration_minutes", "due_now", "card_protection")) <= columns)

    def test_definitive_rejection_is_distinct_and_terminal(self) -> None:
        cid = self.prepare()["confirmation_id"]
        self.command("confirm", cid)
        self.command("claim", cid)
        rejected = self.command("reject", cid, "--reason", "slot_unavailable")
        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(rejected["rejection_reason"], "slot_unavailable")
        self.assertEqual(self.command("claim", cid, expected=2)["ok"], False)
        self.assertEqual(
            self.command(
                "complete",
                cid,
                "--booking-reference",
                "UNVERIFIED",
                expected=2,
            )["ok"],
            False,
        )

    def test_schema_contains_no_customer_pii_columns(self) -> None:
        self.prepare()
        connection = sqlite3.connect(self.db)
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(bookings)")
        }
        connection.close()
        self.assertTrue({"confirmation_id", "status", "service"} <= columns)
        self.assertTrue({"full_name", "email", "phone"}.isdisjoint(columns))

    def test_concurrent_claim_has_one_winner(self) -> None:
        cid = self.prepare()["confirmation_id"]
        self.command("confirm", cid)
        command = [
            sys.executable,
            str(SCRIPT),
            "claim",
            "--db",
            str(self.db),
            "--confirmation-id",
            cid,
        ]
        first = subprocess.Popen(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        second = subprocess.Popen(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        first.communicate(timeout=10)
        second.communicate(timeout=10)
        self.assertEqual(sorted((first.returncode, second.returncode)), [0, 2])
        self.assertEqual(self.command("status", cid)["status"], "submitting")


if __name__ == "__main__":
    unittest.main()
