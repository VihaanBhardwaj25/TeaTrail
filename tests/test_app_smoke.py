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
    assert "How much does delivery cost?" in labels and "Talk to a person" in labels
    assert at.session_state["messages"][0]["content"] == "Hi, I'm Tara from TeaTrail! How can I help with your order today?"


def test_chip_sends_question_and_tara_answers():
    at = _unlocked()
    chip = next(b for b in at.button if b.label == "Do you sell gift hampers?")
    chip.click().run()
    assert not at.exception
    msgs = at.session_state["messages"]
    assert msgs[1]["content"] == "Do you sell gift hampers?"
    assert "₹799" in msgs[2]["content"] and msgs[2]["content"].endswith("(Source: Products)")


def test_uncovered_question_offers_a_person_and_yes_raises_a_ticket():
    at = _unlocked()
    at.chat_input[0].set_value("Do you have a physical store in Goa?").run()
    assert not at.exception
    assert at.session_state["messages"][-1]["kind"] == "offer"
    next(b for b in at.button if b.label == "Yes, connect me").click().run()
    last = at.session_state["messages"][-1]
    assert last["ticket"]["ticket_id"] == "TKT-1001" and "TKT-1001" in last["content"]


def test_angry_message_shows_ticket_in_sidebar():
    at = _unlocked()
    at.chat_input[0].set_value("My order arrived broken and I'm really angry!").run()
    assert not at.exception
    assert "TKT-1001" in at.session_state["messages"][-1]["content"]
    sidebar_html = " ".join(m.value for m in at.sidebar.markdown)
    assert "TKT-1001" in sidebar_html and "Open tickets · 1" in sidebar_html


def test_app_stays_locked_without_a_passcode(monkeypatch):
    monkeypatch.delenv("APP_PASSCODE")
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    assert not at.text_input  # no passcode box to brute-force
    assert at.warning and "No passcode is configured" in at.warning[0].value
