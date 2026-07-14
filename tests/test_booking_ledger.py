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

    def prepare(self, **overrides: str) -> dict:
        values = {
            "conversation_id": "wa_opaque_123",
            "venue_url": "https://www.treatwell.at/ort/cs-beauty-4/",
            "service": "Handmassage",
            "date": "2026-07-15",
            "time": "16:00",
            "timezone": "Europe/Vienna",
            "staff": "any",
            "price": "10.00",
            "currency": "EUR",
            "payment": "pay_at_venue",
        }
        values.update(overrides)
        args = ["prepare", "--db", str(self.db)]
        for key, value in values.items():
            args.extend(("--" + key.replace("_", "-"), value))
        return self.run_cli(*args)[0]

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

    def test_prepare_is_deterministic_and_price_change_requires_new_confirmation(self) -> None:
        first = self.prepare(price="10.00")
        same = self.prepare(price="10.0")
        changed = self.prepare(price="7.50")
        self.assertEqual(first["confirmation_id"], same["confirmation_id"])
        self.assertNotEqual(first["confirmation_id"], changed["confirmation_id"])

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
            "--price",
            "10",
            "--currency",
            "EUR",
            "--payment",
            "card",
            expected=2,
        )
        self.assertIn("only payment=pay_at_venue", error["error"])

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
