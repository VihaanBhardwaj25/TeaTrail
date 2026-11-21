"""TeaTrail Store Support: chat with Tara, hand off to a person, track open tickets."""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
import uuid
from html import escape

import streamlit as st

import config
import faq_loader
import styles
import tickets
from agent import GREETING, Tara, format_transcript

MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 30
SUGGESTIONS = [
    ("🚚", "How much does delivery cost?"),
    ("↩️", "What is your return policy?"),
    ("📦", "Track my order"),
    ("🍵", "Are your teas fresh?"),
    ("🎁", "Do you sell gift hampers?"),
]

authed = st.session_state.get("authenticated", False)
st.set_page_config(
    page_title="TeaTrail Store Support",
    page_icon="🍃",
    layout="centered",
    initial_sidebar_state="expanded" if authed else "collapsed",
    menu_items={"Get help": None, "Report a bug": None, "About": "TeaTrail Store Support"},
)
st.html(styles.CSS)


# ==========================================================================
# Passcode gate
# ==========================================================================
def _check_passcode(entered: str) -> bool:
    expected = config.passcode_sha256()
    if not expected:  # no passcode configured: stay locked
        return False
    digest = hashlib.sha256(entered.encode("utf-8")).hexdigest()
    return hmac.compare_digest(digest, expected)


def render_lock_screen() -> None:
    st.html(styles.LOCK_CSS)
    st.markdown(styles.lock_html(), unsafe_allow_html=True)

    if not config.passcode_sha256():
        st.warning(
            "No passcode is configured yet. Add `APP_PASSCODE` to the app's Secrets "
            "(or a local `.env` file) to unlock TeaTrail Support.",
            icon="🔐",
        )
        return

    locked_for = int(st.session_state.get("lock_until", 0) - time.time())
    with st.form("unlock", clear_on_submit=True, border=False):
        code = st.text_input(
            "Passcode", type="password", placeholder="Enter passcode", disabled=locked_for > 0
        )
        submitted = st.form_submit_button(
            "Unlock", type="primary", use_container_width=True, disabled=locked_for > 0
        )

    if locked_for > 0:
        st.warning(f"Too many attempts. Please wait {locked_for}s and try again.", icon="⏳")
    elif submitted:
        if _check_passcode(code):
            st.session_state.update(authenticated=True, failed_attempts=0)
            st.rerun()
        time.sleep(0.8)  # slow down brute-force attempts (each new session resets the lockout)
        attempts = st.session_state.get("failed_attempts", 0) + 1
        st.session_state.failed_attempts = attempts
        if attempts >= MAX_ATTEMPTS:
            st.session_state.update(lock_until=time.time() + LOCKOUT_SECONDS, failed_attempts=0)
            st.warning(f"Too many attempts. Please wait {LOCKOUT_SECONDS}s and try again.", icon="⏳")
        else:
            st.error("That passcode didn't match. Please try again.", icon="🔒")

    st.markdown('<div class="tt-lock-foot">🔒 Protected access · TeaTrail Store</div>', unsafe_allow_html=True)


if not authed:
    render_lock_screen()
    st.stop()


# ==========================================================================
# State & resources
# ==========================================================================
def _greeting_message() -> dict:
    return {"id": uuid.uuid4().hex[:10], "role": "assistant", "kind": "greeting", "content": GREETING}


st.session_state.setdefault("messages", [_greeting_message()])


@st.cache_data(show_spinner=False)
def _svg_data_uri(path: str) -> str:
    with open(path, "rb") as fh:
        return "data:image/svg+xml;base64," + base64.b64encode(fh.read()).decode("ascii")


def save_ticket(message: str, reason: str, priority: str, conversation: list[dict]) -> dict:
    """Tickets are created by code (never by the model), so IDs never repeat."""
    return tickets.create_ticket(message=message, reason=reason, priority=priority,
                                 transcript=format_transcript(conversation))


kb = faq_loader.load_knowledge_base(config.faq_sheet_url())
llm = config.llm_settings()
tara = Tara(kb.faqs, llm, ticket_fn=save_ticket, typing_delay=0.012)


def _history() -> list[dict]:
    return [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages
        if m.get("kind") != "greeting"
    ]


def _queue_prompt(prompt: str) -> None:
    st.session_state.pending_prompt = prompt


def _open_contact(ticket_id: str) -> None:
    st.session_state.contact_ticket = ticket_id


def _on_feedback(message_id: str) -> None:
    value = st.session_state.get(f"fb_{message_id}")
    if value is None:
        return
    msgs = st.session_state.messages
    idx = next((i for i, m in enumerate(msgs) if m["id"] == message_id), None)
    if idx is None:
        return
    question = next((m["content"] for m in reversed(msgs[:idx]) if m["role"] == "user"), "")
    tickets.record_feedback(message_id, "up" if value == 1 else "down", question, msgs[idx]["content"])
    st.toast("Thanks for the feedback! 🍃" if value == 1 else "Thanks, that helps us improve 🙏")


def _lock() -> None:
    for key in list(st.session_state.keys()):
        del st.session_state[key]


def _new_chat() -> None:
    st.session_state.messages = [_greeting_message()]


def _refresh_faqs() -> None:
    faq_loader.load_knowledge_base.clear()
    st.toast("FAQs refreshed from the sheet ✨")


# ==========================================================================
# Contact details for a ticket (optional)
# ==========================================================================
@st.dialog("Add your contact details", width="medium", icon="🎫")
def contact_dialog(ticket_id: str) -> None:
    st.caption(f"Ticket {ticket_id} is already open. Add your details so our team knows how to reach you.")
    with st.form("contact_form", border=False):
        c1, c2 = st.columns(2)
        name = c1.text_input("Name *", max_chars=80, placeholder="Your full name")
        email = c2.text_input("Email *", max_chars=120, placeholder="you@example.com", type="email")
        order_id = st.text_input("Order ID (optional)", max_chars=30, placeholder="e.g. 458812")
        submitted = st.form_submit_button("Save details", type="primary", use_container_width=True)
    if submitted:
        try:
            tickets.update_contact(ticket_id, name, email, order_id)
        except ValueError as exc:
            st.error(str(exc), icon="✋")
            return
        for msg in st.session_state.messages:
            if (msg.get("ticket") or {}).get("ticket_id") == ticket_id:
                msg["ticket"].update(name=name.strip(), email=email.strip(), order_id=order_id.strip())
        st.toast(f"Thanks! We'll reply to {email.strip()} about {ticket_id}.")
        st.rerun()


# ==========================================================================
# Sidebar
# ==========================================================================
with st.sidebar:
    st.markdown(styles.sidebar_brand_html(), unsafe_allow_html=True)
    st.write("")

    st.button(
        "Talk to a person",
        key="sb_human",
        icon="🙋",
        use_container_width=True,
        on_click=_queue_prompt,
        args=("Let me talk to a real person.",),
    )
    st.button("New chat", key="sb_new", icon="🧹", use_container_width=True, on_click=_new_chat)

    open_tickets = tickets.list_tickets(status="open")
    st.markdown(f"##### Open tickets · {len(open_tickets)}")
    if not open_tickets:
        st.caption("No open tickets. Tickets Tara raises appear here live.")
    for t in open_tickets[:6]:
        st.markdown(styles.queue_item_html(t), unsafe_allow_html=True)
    if len(open_tickets) > 6:
        st.caption(f"+ {len(open_tickets) - 6} more in tickets.csv")
    if open_tickets:
        st.download_button(
            "Download tickets.csv",
            data=tickets.tickets_csv(),
            file_name="tickets.csv",
            mime="text/csv",
            icon="⬇️",
            use_container_width=True,
        )

    st.markdown("##### Knowledge base")
    synced = styles.relative_time(kb.fetched_at)
    st.markdown(
        styles.card_html("Source", kb.source_label, f"{len(kb.faqs)} FAQs · synced {synced} · auto-refresh 5 min"),
        unsafe_allow_html=True,
    )
    if kb.warning:
        st.warning(kb.warning, icon="⚠️")
    st.button("Refresh FAQs", key="sb_refresh", icon="🔄", use_container_width=True, on_click=_refresh_faqs)

    engine_sub = llm.model if tara.online else "Answers straight from the FAQ sheet"
    st.markdown(styles.card_html("Assistant engine", llm.label, engine_sub), unsafe_allow_html=True)

    counts = tickets.feedback_counts()
    total = counts["up"] + counts["down"]
    rate = f"{round(100 * counts['up'] / total)}% helpful" if total else "No ratings yet"
    st.markdown("##### Was this helpful?")
    st.markdown(
        f'<div class="tt-fb"><span>👍 Yes <b>{counts["up"]}</b></span><span>👎 No <b>{counts["down"]}</b></span>'
        f"<span>· {rate}</span></div>",
        unsafe_allow_html=True,
    )

    with st.expander("📚 Browse the FAQs"):
        for category in kb.categories:
            st.markdown(f"**{category}**")
            for faq in [f for f in kb.faqs if f.category == category]:
                st.markdown(
                    f'<div class="tt-faq-q">{escape(faq.question)}</div>'
                    f'<div class="tt-faq-a">{escape(faq.answer)}</div>',
                    unsafe_allow_html=True,
                )

    st.divider()
    st.button("Lock app", key="sb_lock", icon="🔒", type="tertiary", on_click=_lock)


# ==========================================================================
# Main column
# ==========================================================================
st.markdown(
    styles.hero_html(llm.label, tara.online, len(kb.faqs), kb.source_label, _svg_data_uri(styles.TARA_AVATAR)),
    unsafe_allow_html=True,
)

prompt = st.chat_input("Ask Tara about delivery, payments, returns, refunds…", max_chars=1000)
prompt = prompt or st.session_state.pop("pending_prompt", None)


def render_message(msg: dict, is_last: bool) -> None:
    if msg["role"] == "user":
        with st.chat_message("user", avatar=styles.USER_AVATAR):
            st.markdown('<span class="tt-role-user"></span>', unsafe_allow_html=True)
            st.markdown(msg["content"])
        return

    with st.chat_message("assistant", avatar=styles.TARA_AVATAR):
        st.markdown('<span class="tt-role-assistant"></span>', unsafe_allow_html=True)
        st.markdown(msg["content"])
        ticket = msg.get("ticket")
        if ticket:
            st.markdown(styles.ticket_html(ticket), unsafe_allow_html=True)
            if not ticket.get("email"):
                st.button(
                    "Add contact details (optional)",
                    key=f"contact_{msg['id']}",
                    icon="✉️",
                    type="tertiary",
                    on_click=_open_contact,
                    args=(ticket["ticket_id"],),
                )
        if msg.get("degraded"):
            st.markdown(
                '<div class="tt-note">Answered straight from our FAQ sheet while the AI service is unavailable.</div>',
                unsafe_allow_html=True,
            )
        if msg.get("kind") == "offer" and is_last:
            with st.container(key=f"offer_{msg['id']}", horizontal=True, gap="small"):
                st.button("Yes, connect me", key=f"yes_{msg['id']}", icon="🙋", on_click=_queue_prompt, args=("Yes",))
                st.button("No thanks", key=f"no_{msg['id']}", on_click=_queue_prompt, args=("No thanks",))
        if msg.get("kind") in {"answer", "offer", "ticket"}:
            st.feedback("thumbs", key=f"fb_{msg['id']}", on_change=_on_feedback, args=(msg["id"],))


messages = st.session_state.messages
for i, msg in enumerate(messages):
    render_message(msg, is_last=i == len(messages) - 1)

if len(messages) == 1 and not prompt:
    st.markdown(styles.welcome_html(), unsafe_allow_html=True)
    with st.container(key="chips", horizontal=True, gap="small"):
        for i, (icon, text) in enumerate(SUGGESTIONS):
            st.button(text, key=f"chip_{i}", icon=icon, on_click=_queue_prompt, args=(text,))

if prompt:
    history = _history()
    user_msg = {"id": uuid.uuid4().hex[:10], "role": "user", "kind": "text", "content": prompt}
    render_message(user_msg, is_last=False)

    with st.chat_message("assistant", avatar=styles.TARA_AVATAR):
        st.markdown('<span class="tt-role-assistant"></span>', unsafe_allow_html=True)
        placeholder = st.empty()
        placeholder.markdown(styles.typing_html(), unsafe_allow_html=True)
        stream = tara.respond(prompt, history)
        shown = ""
        for chunk in stream:
            shown = "" if chunk is None else shown + chunk
            if shown:
                placeholder.markdown(shown + " ▍")
        reply = stream.reply
        placeholder.markdown(reply.text)

    st.session_state.messages.extend(
        [
            user_msg,
            {
                "id": uuid.uuid4().hex[:10],
                "role": "assistant",
                "kind": reply.kind,
                "content": reply.text,
                "ticket": reply.ticket,
                "sources": [{"id": f.id, "question": f.question, "category": f.category} for f in reply.sources],
                "provider": reply.provider,
                "degraded": reply.degraded,
            },
        ]
    )
    st.rerun()

contact_for = st.session_state.pop("contact_ticket", None)
if contact_for:
    contact_dialog(contact_for)
