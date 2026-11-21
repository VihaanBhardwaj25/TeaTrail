"""End-to-end smoke test of the Streamlit app using Streamlit's AppTest."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def _unlocked():
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.text_input[0].input("test-passcode")
    at.button[0].click().run()
    return at


def test_lock_screen_rejects_wrong_passcode():
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    assert at.text_input[0].label == "Passcode"
    at.text_input[0].input("wrong")
    at.button[0].click().run()
    assert at.error and "didn't match" in at.error[0].value
    assert not at.session_state["authenticated"] if "authenticated" in at.session_state else True


def test_unlock_shows_chat_and_chips():
    at = _unlocked()
    assert not at.exception
    assert at.session_state["authenticated"]
    labels = [b.label for b in at.button]
    assert "How fresh is your tea?" in labels and "Talk to a human" in labels


def test_chip_sends_question_and_tara_answers():
    at = _unlocked()
    chip = next(b for b in at.button if b.label == "Tell me about gift hampers")
    chip.click().run()
    assert not at.exception
    msgs = at.session_state["messages"]
    assert msgs[0]["content"] == "Tell me about gift hampers"
    assert "₹799" in msgs[1]["content"] and msgs[1]["kind"] == "answer"


def test_uncovered_question_offers_ticket_button():
    at = _unlocked()
    at.chat_input[0].set_value("Do you have a physical store in Goa?").run()
    assert not at.exception
    assert at.session_state["messages"][-1]["handoff"]
    assert any(b.label == "Raise a ticket" for b in at.button)


def test_app_stays_locked_without_a_passcode(monkeypatch):
    monkeypatch.delenv("APP_PASSCODE")
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    assert not at.text_input  # no passcode box to brute-force
    assert at.warning and "No passcode is configured" in at.warning[0].value
