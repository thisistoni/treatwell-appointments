#!/usr/bin/env python3
"""Non-PII SQLite ledger for exactly-once Treatwell booking submission."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
from datetime import date as Date
from datetime import datetime, time as Time, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

SCHEMA = """
CREATE TABLE IF NOT EXISTS bookings (
    confirmation_id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    venue_url TEXT NOT NULL,
    service TEXT NOT NULL,
    local_date TEXT NOT NULL,
    local_time TEXT NOT NULL,
    timezone TEXT NOT NULL,
    staff TEXT NOT NULL,
    duration_minutes INTEGER NOT NULL,
    price TEXT NOT NULL,
    currency TEXT NOT NULL,
    payment TEXT NOT NULL,
    due_now TEXT NOT NULL,
    cancellation_terms TEXT NOT NULL,
    no_show_terms TEXT NOT NULL,
    card_protection TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN (
        'prepared', 'confirmed', 'submitting', 'booked',
        'submission_unknown', 'rejected', 'aborted'
    )),
    created_at TEXT NOT NULL,
    confirmed_at TEXT,
    submitting_at TEXT,
    completed_at TEXT,
    booking_reference TEXT,
    unknown_reason TEXT,
    rejected_at TEXT,
    rejection_reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_bookings_conversation
ON bookings(conversation_id, created_at);
"""

MIGRATION_COLUMNS = {
    "duration_minutes": "INTEGER NOT NULL DEFAULT 0",
    "due_now": "TEXT NOT NULL DEFAULT '0'",
    "cancellation_terms": "TEXT NOT NULL DEFAULT 'legacy_unknown'",
    "no_show_terms": "TEXT NOT NULL DEFAULT 'legacy_unknown'",
    "card_protection": "TEXT NOT NULL DEFAULT 'legacy_unknown'",
}

FIELDS = (
    "conversation_id",
    "venue_url",
    "service",
    "local_date",
    "local_time",
    "timezone",
    "staff",
    "duration_minutes",
    "price",
    "currency",
    "payment",
    "due_now",
    "cancellation_terms",
    "no_show_terms",
    "card_protection",
)


class LedgerError(Exception):
    """An expected protocol or input error."""


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def clean_text(value: str, field: str, max_length: int = 500) -> str:
    value = " ".join(value.split())
    if not value:
        raise LedgerError(f"{field} must not be empty")
    if len(value) > max_length:
        raise LedgerError(f"{field} exceeds {max_length} characters")
    return value


def normalize_url(value: str) -> str:
    value = clean_text(value, "venue_url", 2048)
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise LedgerError("venue_url must be an absolute HTTP(S) URL")
    return value


def normalize_date(value: str) -> str:
    try:
        return Date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise LedgerError("date must use YYYY-MM-DD") from exc


def normalize_time(value: str) -> str:
    try:
        parsed = Time.fromisoformat(value)
    except ValueError as exc:
        raise LedgerError("time must use HH:MM") from exc
    if parsed.second or parsed.microsecond or parsed.tzinfo is not None:
        raise LedgerError("time must be a local HH:MM value without seconds or offset")
    return parsed.strftime("%H:%M")


def normalize_timezone(value: str) -> str:
    value = clean_text(value, "timezone", 128)
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise LedgerError("timezone must be a valid IANA timezone") from exc
    return value


def normalize_price(value: str) -> str:
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise LedgerError("price must be a decimal amount") from exc
    if not amount.is_finite() or amount < 0:
        raise LedgerError("price must be a finite non-negative amount")
    return format(amount.normalize(), "f")


def normalize_duration(value: str) -> int:
    try:
        minutes = int(value)
    except ValueError as exc:
        raise LedgerError("duration_minutes must be an integer") from exc
    if not 1 <= minutes <= 1440:
        raise LedgerError("duration_minutes must be between 1 and 1440")
    return minutes


def normalize_currency(value: str) -> str:
    value = value.upper()
    if not re.fullmatch(r"[A-Z]{3}", value):
        raise LedgerError("currency must be a three-letter ISO code")
    return value


def canonicalize(args: argparse.Namespace) -> dict[str, Any]:
    payment = clean_text(args.payment, "payment", 64)
    if payment != "pay_at_venue":
        raise LedgerError("this ledger accepts only payment=pay_at_venue")
    due_now = normalize_price(args.due_now)
    if due_now != "0":
        raise LedgerError("pay-at-venue confirmation requires due_now=0")
    card_protection = clean_text(args.card_protection, "card_protection", 64)
    if card_protection != "none":
        raise LedgerError("this ledger does not authorize card protection or card collection")
    cancellation_terms = clean_text(args.cancellation_terms, "cancellation_terms")
    no_show_terms = clean_text(args.no_show_terms, "no_show_terms")
    if "legacy_unknown" in {cancellation_terms, no_show_terms}:
        raise LedgerError("current cancellation and no-show terms are required")
    return {
        "conversation_id": clean_text(args.conversation_id, "conversation_id", 256),
        "venue_url": normalize_url(args.venue_url),
        "service": clean_text(args.service, "service"),
        "local_date": normalize_date(args.date),
        "local_time": normalize_time(args.time),
        "timezone": normalize_timezone(args.timezone),
        "staff": clean_text(args.staff, "staff", 256),
        "duration_minutes": normalize_duration(args.duration_minutes),
        "price": normalize_price(args.price),
        "currency": normalize_currency(args.currency),
        "payment": payment,
        "due_now": due_now,
        "cancellation_terms": cancellation_terms,
        "no_show_terms": no_show_terms,
        "card_protection": card_protection,
    }


def confirmation_id(summary: dict[str, Any]) -> str:
    payload = json.dumps(summary, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "tw_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def connect(db_path: str) -> sqlite3.Connection:
    path = Path(db_path).expanduser()
    if path.exists() and path.is_dir():
        raise LedgerError("database path points to a directory")
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path), timeout=10, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 10000")
    connection.executescript(SCHEMA)
    connection.execute("BEGIN IMMEDIATE")
    try:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(bookings)")
        }
        for name, definition in MIGRATION_COLUMNS.items():
            if name not in columns:
                connection.execute(f"ALTER TABLE bookings ADD COLUMN {name} {definition}")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    if os.name != "nt":
        os.chmod(path, 0o600)
    return connection


def fetch(connection: sqlite3.Connection, cid: str) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM bookings WHERE confirmation_id = ?", (cid,)
    ).fetchone()
    if row is None:
        raise LedgerError(f"unknown confirmation_id: {cid}")
    return row


def public_record(row: sqlite3.Row) -> dict[str, Any]:
    summary = {field: row[field] for field in FIELDS if field != "conversation_id"}
    result: dict[str, Any] = {
        "ok": True,
        "confirmation_id": row["confirmation_id"],
        "status": row["status"],
        "summary": summary,
        "created_at": row["created_at"],
    }
    for key in (
        "confirmed_at",
        "submitting_at",
        "completed_at",
        "booking_reference",
        "unknown_reason",
        "rejected_at",
        "rejection_reason",
    ):
        if row[key] is not None:
            result[key] = row[key]
    return result


def command_prepare(connection: sqlite3.Connection, args: argparse.Namespace) -> dict[str, Any]:
    summary = canonicalize(args)
    cid = confirmation_id(summary)
    created = now_utc()
    columns = ", ".join(("confirmation_id", *FIELDS, "status", "created_at"))
    placeholders = ", ".join("?" for _ in range(len(FIELDS) + 3))
    values = (cid, *(summary[field] for field in FIELDS), "prepared", created)
    connection.execute("BEGIN IMMEDIATE")
    try:
        connection.execute(
            f"INSERT OR IGNORE INTO bookings ({columns}) VALUES ({placeholders})", values
        )
        row = fetch(connection, cid)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return public_record(row)


def transition(
    connection: sqlite3.Connection,
    cid: str,
    expected: str,
    target: str,
    timestamp_column: str | None = None,
    extras: dict[str, str] | None = None,
    idempotent_targets: tuple[str, ...] = (),
) -> dict[str, Any]:
    connection.execute("BEGIN IMMEDIATE")
    try:
        row = fetch(connection, cid)
        if row["status"] in idempotent_targets:
            connection.commit()
            return public_record(row)
        if row["status"] != expected:
            raise LedgerError(
                f"cannot transition {row['status']} to {target}; expected {expected}"
            )
        updates = {"status": target}
        if timestamp_column:
            updates[timestamp_column] = now_utc()
        if extras:
            updates.update(extras)
        assignment = ", ".join(f"{key} = ?" for key in updates)
        params = (*updates.values(), cid, expected)
        cursor = connection.execute(
            f"UPDATE bookings SET {assignment} WHERE confirmation_id = ? AND status = ?",
            params,
        )
        if cursor.rowcount != 1:
            raise LedgerError("concurrent state transition refused")
        row = fetch(connection, cid)
        connection.commit()
        return public_record(row)
    except Exception:
        connection.rollback()
        raise


def ensure_current_confirmation(row: sqlite3.Row) -> None:
    if (
        row["duration_minutes"] == 0
        or row["cancellation_terms"] == "legacy_unknown"
        or row["no_show_terms"] == "legacy_unknown"
        or row["card_protection"] == "legacy_unknown"
    ):
        raise LedgerError(
            "legacy confirmation lacks material terms; run prepare again and obtain a new confirmation"
        )


def command_confirm(connection: sqlite3.Connection, cid: str) -> dict[str, Any]:
    ensure_current_confirmation(fetch(connection, cid))
    return transition(
        connection, cid, "prepared", "confirmed", "confirmed_at", idempotent_targets=("confirmed",)
    )


def command_claim(connection: sqlite3.Connection, cid: str) -> dict[str, Any]:
    ensure_current_confirmation(fetch(connection, cid))
    return transition(connection, cid, "confirmed", "submitting", "submitting_at")


def command_complete(
    connection: sqlite3.Connection, cid: str, reference: str
) -> dict[str, Any]:
    reference = clean_text(reference, "booking_reference", 256)
    connection.execute("BEGIN IMMEDIATE")
    try:
        row = fetch(connection, cid)
        if row["status"] == "booked" and row["booking_reference"] == reference:
            connection.commit()
            return public_record(row)
        if row["status"] != "submitting":
            raise LedgerError(
                f"cannot transition {row['status']} to booked; expected submitting"
            )
        connection.execute(
            """UPDATE bookings
               SET status = 'booked', completed_at = ?, booking_reference = ?
               WHERE confirmation_id = ? AND status = 'submitting'""",
            (now_utc(), reference, cid),
        )
        row = fetch(connection, cid)
        connection.commit()
        return public_record(row)
    except Exception:
        connection.rollback()
        raise


def command_unknown(connection: sqlite3.Connection, cid: str, reason: str) -> dict[str, Any]:
    reason = clean_text(reason, "reason", 500)
    return transition(
        connection,
        cid,
        "submitting",
        "submission_unknown",
        extras={"unknown_reason": reason},
        idempotent_targets=("submission_unknown",),
    )


def command_reject(connection: sqlite3.Connection, cid: str, reason: str) -> dict[str, Any]:
    reason = clean_text(reason, "reason", 500)
    return transition(
        connection,
        cid,
        "submitting",
        "rejected",
        "rejected_at",
        extras={"rejection_reason": reason},
        idempotent_targets=("rejected",),
    )


def command_abort(connection: sqlite3.Connection, cid: str) -> dict[str, Any]:
    connection.execute("BEGIN IMMEDIATE")
    try:
        row = fetch(connection, cid)
        if row["status"] == "aborted":
            connection.commit()
            return public_record(row)
        if row["status"] not in {"prepared", "confirmed"}:
            raise LedgerError(f"cannot abort a booking in status {row['status']}")
        connection.execute(
            "UPDATE bookings SET status = 'aborted' WHERE confirmation_id = ?",
            (cid,),
        )
        row = fetch(connection, cid)
        connection.commit()
        return public_record(row)
    except Exception:
        connection.rollback()
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="create or return a prepared booking")
    prepare.add_argument("--db", required=True)
    prepare.add_argument("--conversation-id", required=True)
    prepare.add_argument("--venue-url", required=True)
    prepare.add_argument("--service", required=True)
    prepare.add_argument("--date", required=True)
    prepare.add_argument("--time", required=True)
    prepare.add_argument("--timezone", required=True)
    prepare.add_argument("--staff", required=True)
    prepare.add_argument("--duration-minutes", required=True)
    prepare.add_argument("--price", required=True)
    prepare.add_argument("--currency", required=True)
    prepare.add_argument("--payment", default="pay_at_venue")
    prepare.add_argument("--due-now", required=True)
    prepare.add_argument("--cancellation-terms", required=True)
    prepare.add_argument("--no-show-terms", required=True)
    prepare.add_argument("--card-protection", required=True)

    for name in ("confirm", "claim", "status", "abort"):
        command = subparsers.add_parser(name)
        command.add_argument("--db", required=True)
        command.add_argument("--confirmation-id", required=True)

    complete = subparsers.add_parser("complete")
    complete.add_argument("--db", required=True)
    complete.add_argument("--confirmation-id", required=True)
    complete.add_argument("--booking-reference", required=True)

    unknown = subparsers.add_parser("unknown")
    unknown.add_argument("--db", required=True)
    unknown.add_argument("--confirmation-id", required=True)
    unknown.add_argument("--reason", required=True)

    reject = subparsers.add_parser("reject")
    reject.add_argument("--db", required=True)
    reject.add_argument("--confirmation-id", required=True)
    reject.add_argument("--reason", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        connection = connect(args.db)
        with connection:
            if args.command == "prepare":
                result = command_prepare(connection, args)
            elif args.command == "confirm":
                result = command_confirm(connection, args.confirmation_id)
            elif args.command == "claim":
                result = command_claim(connection, args.confirmation_id)
            elif args.command == "complete":
                result = command_complete(
                    connection, args.confirmation_id, args.booking_reference
                )
            elif args.command == "unknown":
                result = command_unknown(connection, args.confirmation_id, args.reason)
            elif args.command == "reject":
                result = command_reject(connection, args.confirmation_id, args.reason)
            elif args.command == "abort":
                result = command_abort(connection, args.confirmation_id)
            else:
                result = public_record(fetch(connection, args.confirmation_id))
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (LedgerError, sqlite3.Error, OSError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
