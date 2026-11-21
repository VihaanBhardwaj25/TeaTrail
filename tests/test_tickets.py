import csv

import pytest

import tickets


def _make(**overrides):
    data = dict(message="My order arrived broken", reason="Damaged or wrong item", priority="high")
    data.update(overrides)
    return tickets.create_ticket(**data)


def test_ticket_ids_start_at_tkt_1001_and_never_repeat():
    ids = [_make()["ticket_id"] for _ in range(3)]
    assert ids == ["TKT-1001", "TKT-1002", "TKT-1003"]


def test_tickets_csv_has_the_brief_columns():
    _make(); _make(message="Let me talk to a real person.", reason="Customer asked for a person", priority="normal")
    with tickets.tickets_path().open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert list(rows[0])[:6] == ["ticket_id", "time", "message", "reason", "priority", "status"]
    assert [r["ticket_id"] for r in rows] == ["TKT-1001", "TKT-1002"]
    assert rows[0]["status"] == "open" and rows[0]["priority"] == "high" and rows[1]["priority"] == "normal"
    assert [t["ticket_id"] for t in tickets.list_tickets(status="open")] == ["TKT-1002", "TKT-1001"]


def test_unknown_priority_becomes_normal():
    assert _make(priority="urgent!!")["priority"] == "normal"


@pytest.mark.parametrize("field", ["message", "reason"])
def test_ticket_needs_message_and_reason(field):
    with pytest.raises(ValueError):
        _make(**{field: "  "})


def test_contact_details_can_be_added_later():
    ticket = _make()
    updated = tickets.update_contact(ticket["ticket_id"], "Asha Rao", "asha@example.com", "458812")
    assert updated["email"] == "asha@example.com"
    assert tickets.get_ticket("tkt-1001")["name"] == "Asha Rao"
    with pytest.raises(ValueError):
        tickets.update_contact(ticket["ticket_id"], "Asha", "not-an-email")
    with pytest.raises(ValueError):
        tickets.update_contact("TKT-9999", "Asha", "asha@example.com")


def test_messages_with_commas_quotes_and_newlines_round_trip():
    msg = 'Refund of ₹3,500 — "urgent"\nsecond line'
    _make(message=msg)
    assert tickets.list_tickets()[0]["message"] == msg


def test_corrupt_ticket_file_is_backed_up_and_replaced():
    tickets.tickets_path().write_bytes(b"\xff\xfe\x00bad")
    assert tickets.list_tickets() == []
    assert _make()["ticket_id"] == "TKT-1001"
    assert list(tickets.tickets_path().parent.glob("tickets.csv.corrupt-*"))


def test_feedback_csv_counts_and_rerating_does_not_double_count():
    assert tickets.record_feedback("m1", "up", "q", "a") == {"up": 1, "down": 0}
    assert tickets.record_feedback("m2", "down") == {"up": 1, "down": 1}
    assert tickets.record_feedback("m1", "down") == {"up": 0, "down": 2}
    assert tickets.feedback_path().name == "feedback.csv"
    with pytest.raises(ValueError):
        tickets.record_feedback("m1", "meh")
