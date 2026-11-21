import json

import pytest

import config
import tickets


def _make(**overrides):
    data = dict(name="Asha Rao", email="asha@example.com", category="Refunds",
                summary="Refund for order not received yet", order_id="TT-48213", transcript="Customer: hi")
    data.update(overrides)
    return tickets.create_ticket(**data)


def test_ticket_ids_start_at_1042_and_increment():
    first, second = _make(), _make(name="Ravi")
    assert first["id"] == "TT-1042" and second["id"] == "TT-1043"
    assert first["status"] == "Open"


def test_tickets_persist_to_json_newest_first():
    _make(); _make(name="Ravi K")
    saved = json.loads((config.data_dir() / "tickets.json").read_text())
    assert [t["id"] for t in saved] == ["TT-1042", "TT-1043"]
    assert [t["id"] for t in tickets.list_tickets()] == ["TT-1043", "TT-1042"]


@pytest.mark.parametrize("field, value", [("name", " "), ("email", "not-an-email"),
                                          ("category", "Nope"), ("summary", "short"),
                                          ("order_id", "<script>")])
def test_invalid_tickets_are_rejected(field, value):
    with pytest.raises(ValueError):
        _make(**{field: value})
    assert tickets.list_tickets() == []


def test_order_id_is_optional():
    assert _make(order_id="")["order_id"] == ""


def test_corrupt_ticket_file_is_backed_up_and_replaced():
    path = config.data_dir() / "tickets.json"
    path.write_text("{not json")
    assert tickets.list_tickets() == []
    assert _make()["id"] == "TT-1042"
    assert list(config.data_dir().glob("tickets.json.corrupt-*"))


def test_feedback_counts_and_rerating_does_not_double_count():
    assert tickets.record_feedback("m1", "up", "q", "a") == {"up": 1, "down": 0}
    assert tickets.record_feedback("m2", "down") == {"up": 1, "down": 1}
    assert tickets.record_feedback("m1", "down") == {"up": 0, "down": 2}
    assert tickets.feedback_counts() == {"up": 0, "down": 2}
    log = json.loads((config.data_dir() / "feedback.json").read_text())["log"]
    assert len(log) == 2


def test_feedback_rejects_unknown_rating():
    with pytest.raises(ValueError):
        tickets.record_feedback("m1", "meh")


def test_category_suggestion():
    assert tickets.suggest_category("Gift Hampers") == "Gift Hampers"
    assert tickets.suggest_category("Tea Freshness") == "Tea & Coffee Freshness"
    assert tickets.suggest_category(None) == "Other"
