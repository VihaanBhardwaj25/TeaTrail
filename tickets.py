"""Support tickets and response feedback, persisted as small JSON files.

Writes go through a temp file + ``os.replace`` (atomic on POSIX and Windows)
under a process-wide lock, because Streamlit serves every browser session
from threads in the same process.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import config

FIRST_TICKET_NUMBER = 1042
TICKET_CATEGORIES = [
    "Delivery & Shipping",
    "Payments",
    "Returns",
    "Refunds",
    "Tea & Coffee Freshness",
    "Gift Hampers",
    "Order Issue",
    "Other",
]
# Map FAQ categories to ticket categories for auto-suggestion.
FAQ_TO_TICKET_CATEGORY = {
    "delivery": "Delivery & Shipping",
    "payments": "Payments",
    "offers": "Payments",
    "orders": "Order Issue",
    "account": "Order Issue",
    "returns": "Returns",
    "refunds": "Refunds",
    "tea freshness": "Tea & Coffee Freshness",
    "gift hampers": "Gift Hampers",
    "products": "Other",
}

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
_ORDER_RE = re.compile(r"^[A-Za-z0-9#\-_/ ]{3,30}$")
_LOCK = threading.Lock()

MAX_SUMMARY_CHARS = 2000
MAX_TRANSCRIPT_CHARS = 8000
MAX_STORED_TICKETS = 2000
MAX_FEEDBACK_ENTRIES = 5000


def _tickets_path() -> Path:
    return config.data_dir() / "tickets.json"


def _feedback_path() -> Path:
    return config.data_dir() / "feedback.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        # Keep the unreadable file for inspection and start fresh.
        backup = path.with_suffix(path.suffix + f".corrupt-{int(datetime.now().timestamp())}")
        try:
            path.replace(backup)
        except OSError:
            pass
        return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


# --------------------------------------------------------------------------
# Tickets
# --------------------------------------------------------------------------
def validate_ticket(name: str, email: str, order_id: str, category: str, summary: str) -> list[str]:
    errors = []
    if not name.strip():
        errors.append("Please share your name so our team knows who to reply to.")
    elif len(name.strip()) > 80:
        errors.append("Name should be 80 characters or fewer.")
    if not _EMAIL_RE.match(email.strip()):
        errors.append("Please enter a valid email address (e.g. you@example.com).")
    if order_id.strip() and not _ORDER_RE.match(order_id.strip()):
        errors.append("Order ID can only contain letters, numbers, #, - or / (3–30 characters).")
    if category not in TICKET_CATEGORIES:
        errors.append("Please choose an issue category.")
    if len(summary.strip()) < 10:
        errors.append("Please add a short description of the issue (at least 10 characters).")
    return errors


def create_ticket(
    name: str,
    email: str,
    category: str,
    summary: str,
    order_id: str = "",
    transcript: str = "",
    source: str = "manual",
) -> dict[str, Any]:
    """Validate, persist and return a new ticket. Raises ValueError on bad input."""
    errors = validate_ticket(name, email, order_id, category, summary)
    if errors:
        raise ValueError(" ".join(errors))

    with _LOCK:
        tickets = _read_json(_tickets_path(), [])
        numbers = [
            int(t["id"].split("-")[1])
            for t in tickets
            if isinstance(t, dict) and re.fullmatch(r"TT-\d+", str(t.get("id", "")))
        ]
        next_number = max(numbers) + 1 if numbers else FIRST_TICKET_NUMBER
        ticket = {
            "id": f"TT-{next_number}",
            "created_at": _now(),
            "status": "Open",
            "name": name.strip(),
            "email": email.strip(),
            "order_id": order_id.strip(),
            "category": category,
            "summary": summary.strip()[:MAX_SUMMARY_CHARS],
            "transcript": transcript.strip()[-MAX_TRANSCRIPT_CHARS:],
            "source": source,  # "tara" (suggested by Tara) or "manual" (button)
        }
        tickets.append(ticket)
        _write_json(_tickets_path(), tickets[-MAX_STORED_TICKETS:])
    return ticket


def list_tickets() -> list[dict[str, Any]]:
    """All tickets, newest first."""
    tickets = _read_json(_tickets_path(), [])
    tickets = [t for t in tickets if isinstance(t, dict) and "id" in t]
    return list(reversed(tickets))


def suggest_category(faq_category: str | None) -> str:
    if not faq_category:
        return "Other"
    return FAQ_TO_TICKET_CATEGORY.get(faq_category.strip().lower(), "Other")


# --------------------------------------------------------------------------
# Feedback
# --------------------------------------------------------------------------
def _empty_feedback() -> dict[str, Any]:
    return {"counts": {"up": 0, "down": 0}, "log": []}


def record_feedback(message_id: str, rating: str, question: str = "", answer: str = "") -> dict[str, int]:
    """Record or update a thumbs rating for one of Tara's replies.

    Re-rating the same message replaces the earlier vote instead of
    double-counting it. Returns the updated counts.
    """
    if rating not in {"up", "down"}:
        raise ValueError("rating must be 'up' or 'down'")

    with _LOCK:
        data = _read_json(_feedback_path(), _empty_feedback())
        if not isinstance(data, dict) or "log" not in data:
            data = _empty_feedback()
        existing = next((e for e in data["log"] if e.get("message_id") == message_id), None)
        if existing:
            existing.update(rating=rating, updated_at=_now())
        else:
            data["log"].append(
                {
                    "message_id": message_id,
                    "rating": rating,
                    "question": question[:500],
                    "answer": answer[:1000],
                    "created_at": _now(),
                }
            )
        data["log"] = data["log"][-MAX_FEEDBACK_ENTRIES:]
        data["counts"] = {
            "up": sum(1 for e in data["log"] if e.get("rating") == "up"),
            "down": sum(1 for e in data["log"] if e.get("rating") == "down"),
        }
        _write_json(_feedback_path(), data)
        return dict(data["counts"])


def feedback_counts() -> dict[str, int]:
    data = _read_json(_feedback_path(), _empty_feedback())
    counts = data.get("counts", {}) if isinstance(data, dict) else {}
    return {"up": int(counts.get("up", 0)), "down": int(counts.get("down", 0))}
