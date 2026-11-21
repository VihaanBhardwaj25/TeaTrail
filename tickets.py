"""Support tickets and reply feedback, stored as CSV files.

tickets.csv columns (the first six are the ones the brief asks for):
    ticket_id, time, message, reason, priority, status,
    name, email, order_id, transcript, source

Ticket IDs (TKT-1001, TKT-1002, ...) are always made here, never by the model,
so they never repeat. Writes go through a temp file + ``os.replace`` under a
process-wide lock, because Streamlit serves every browser session from
threads in the same process.
"""

from __future__ import annotations

import csv
import io
import os
import re
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

import config

FIRST_TICKET_NUMBER = 1001
TICKET_FIELDS = [
    "ticket_id", "time", "message", "reason", "priority", "status",
    "name", "email", "order_id", "transcript", "source",
]
FEEDBACK_FIELDS = ["message_id", "time", "rating", "question", "answer"]
PRIORITIES = ("normal", "high")

MAX_MESSAGE_CHARS = 1000
MAX_TRANSCRIPT_CHARS = 8000
MAX_STORED_ROWS = 5000

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
_ORDER_RE = re.compile(r"^[A-Za-z0-9#\-_/ ]{3,30}$")
_LOCK = threading.Lock()


def tickets_path() -> Path:
    return config.data_dir() / "tickets.csv"


def feedback_path() -> Path:
    return config.data_dir() / "feedback.csv"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    try:
        with path.open(newline="", encoding="utf-8") as fh:
            return [dict(row) for row in csv.DictReader(fh)]
    except (csv.Error, UnicodeDecodeError, OSError):
        # Keep the unreadable file for inspection and start fresh.
        backup = path.with_suffix(path.suffix + f".corrupt-{int(datetime.now().timestamp())}")
        try:
            path.replace(backup)
        except OSError:
            pass
        return []


def _write_rows(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows[-MAX_STORED_ROWS:])
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(buffer.getvalue())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


# --------------------------------------------------------------------------
# Tickets
# --------------------------------------------------------------------------
def _next_id(rows: list[dict[str, str]]) -> str:
    numbers = [
        int(r["ticket_id"].split("-")[1])
        for r in rows
        if re.fullmatch(r"TKT-\d+", r.get("ticket_id") or "")
    ]
    return f"TKT-{max(numbers) + 1 if numbers else FIRST_TICKET_NUMBER}"


def validate_contact(name: str, email: str, order_id: str = "") -> list[str]:
    errors = []
    if not name.strip():
        errors.append("Please share your name so our team knows who to reply to.")
    elif len(name.strip()) > 80:
        errors.append("Name should be 80 characters or fewer.")
    if not _EMAIL_RE.match(email.strip()):
        errors.append("Please enter a valid email address (e.g. you@example.com).")
    if order_id.strip() and not _ORDER_RE.match(order_id.strip()):
        errors.append("Order ID can only contain letters, numbers, #, - or / (3–30 characters).")
    return errors


def create_ticket(
    message: str,
    reason: str,
    priority: str = "normal",
    transcript: str = "",
    source: str = "chat",
    name: str = "",
    email: str = "",
    order_id: str = "",
) -> dict[str, str]:
    """Save a new open ticket and return it. Raises ValueError on bad input."""
    if not message.strip():
        raise ValueError("A ticket needs the customer's message.")
    if not reason.strip():
        raise ValueError("A ticket needs a reason.")
    priority = priority.strip().lower()
    if priority not in PRIORITIES:
        priority = "normal"
    if email.strip() or name.strip():
        errors = validate_contact(name, email, order_id)
        if errors:
            raise ValueError(" ".join(errors))

    with _LOCK:
        rows = _read_rows(tickets_path())
        ticket = {
            "ticket_id": _next_id(rows),
            "time": _now(),
            "message": message.strip()[:MAX_MESSAGE_CHARS],
            "reason": reason.strip()[:200],
            "priority": priority,
            "status": "open",
            "name": name.strip(),
            "email": email.strip(),
            "order_id": order_id.strip(),
            "transcript": transcript.strip()[-MAX_TRANSCRIPT_CHARS:],
            "source": source,
        }
        rows.append(ticket)
        _write_rows(tickets_path(), TICKET_FIELDS, rows)
    return ticket


def update_contact(ticket_id: str, name: str, email: str, order_id: str = "") -> dict[str, str]:
    """Add the customer's contact details to an existing ticket."""
    errors = validate_contact(name, email, order_id)
    if errors:
        raise ValueError(" ".join(errors))
    with _LOCK:
        rows = _read_rows(tickets_path())
        for row in rows:
            if row.get("ticket_id") == ticket_id:
                row.update(name=name.strip(), email=email.strip(), order_id=order_id.strip())
                _write_rows(tickets_path(), TICKET_FIELDS, rows)
                return row
    raise ValueError(f"Ticket {ticket_id} was not found.")


def list_tickets(status: str | None = None) -> list[dict[str, str]]:
    """Tickets newest first, optionally only those with the given status."""
    rows = [r for r in _read_rows(tickets_path()) if r.get("ticket_id")]
    if status:
        rows = [r for r in rows if r.get("status") == status]
    return list(reversed(rows))


def get_ticket(ticket_id: str) -> dict[str, str] | None:
    wanted = ticket_id.strip().upper()
    return next((r for r in list_tickets() if r["ticket_id"].upper() == wanted), None)


def tickets_csv() -> str:
    path = tickets_path()
    return path.read_text(encoding="utf-8") if path.exists() else ",".join(TICKET_FIELDS) + "\n"


# --------------------------------------------------------------------------
# Feedback
# --------------------------------------------------------------------------
def record_feedback(message_id: str, rating: str, question: str = "", answer: str = "") -> dict[str, int]:
    """Record or update a Yes/No ("up"/"down") rating for one of Tara's replies.

    Re-rating the same reply replaces the earlier vote instead of double-counting.
    """
    if rating not in {"up", "down"}:
        raise ValueError("rating must be 'up' or 'down'")
    with _LOCK:
        rows = _read_rows(feedback_path())
        existing = next((r for r in rows if r.get("message_id") == message_id), None)
        if existing:
            existing.update(rating=rating, time=_now())
        else:
            rows.append({"message_id": message_id, "time": _now(), "rating": rating,
                         "question": question[:500], "answer": answer[:1000]})
        _write_rows(feedback_path(), FEEDBACK_FIELDS, rows)
    return feedback_counts()


def feedback_counts() -> dict[str, int]:
    rows = _read_rows(feedback_path())
    return {"up": sum(r.get("rating") == "up" for r in rows), "down": sum(r.get("rating") == "down" for r in rows)}
