"""TeaTrail Store support app: chat with Tara, hand off to a human, track tickets."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid
from html import escape

import streamlit as st

import config
import faq_loader
import styles
import tickets
from agent import Tara, build_ticket_summary, format_transcript

MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 30
SUGGESTIONS = [
    ("🍃", "How fresh is your tea?"),
    ("🚚", "Delivery time & shipping cost?"),
    ("🎁", "Tell me about gift hampers"),
    ("↩️", "What is your return policy?"),
    ("💳", "Which payment options do you have?"),
]

authed = st.session_state.get("authenticated", False)
st.set_page_config(
    page_title="TeaTrail Support · Tara",
    page_icon="🍃",
    layout="centered",
    initial_sidebar_state="expanded" if authed else "collapsed",
    menu_items={"Get help": None, "Report a bug": None, "About": "TeaTrail Store support assistant"},
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
st.session_state.setdefault("messages", [])
st.session_state.setdefault("queue_open", False)


@st.cache_data(show_spinner=False)
def _svg_data_uri(path: str) -> str:
    with open(path, "rb") as fh:
        return "data:image/svg+xml;base64," + base64.b64encode(fh.read()).decode("ascii")


kb = faq_loader.load_knowledge_base(config.faq_sheet_url())
llm = config.llm_settings()
tara = Tara(kb.faqs, llm, typing_delay=0.012)


def _history() -> list[dict]:
    return [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages
        if m.get("kind", "text") == "text"
    ]


def _queue_prompt(prompt: str) -> None:
    st.session_state.pending_prompt = prompt


def _request_ticket(source: str, category_hint: str | None = None) -> None:
    st.session_state.open_ticket = {"source": source, "hint": category_hint}


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
    st.session_state.messages = []


def _refresh_faqs() -> None:
    faq_loader.load_knowledge_base.clear()
    st.toast("FAQs refreshed from the source ✨")


# ==========================================================================
# Ticket dialog
# ==========================================================================
@st.dialog("Raise a support ticket", width="medium", icon="🎫")
def ticket_dialog(source: str, category_hint: str | None) -> None:
    history = _history()
    transcript = format_transcript(history)
    st.caption("A TeaTrail teammate will pick this up and reply by email. Fields marked * are required.")

    with st.form("ticket_form", border=False):
        c1, c2 = st.columns(2)
        name = c1.text_input("Name *", max_chars=80, placeholder="Your full name")
        email = c2.text_input("Email *", max_chars=120, placeholder="you@example.com", type="email")
        c3, c4 = st.columns(2)
        order_id = c3.text_input("Order ID (optional)", max_chars=30, placeholder="e.g. TT-48213")
        suggested = tickets.suggest_category(category_hint)
        category = c4.selectbox(
            "Issue category *", tickets.TICKET_CATEGORIES, index=tickets.TICKET_CATEGORIES.index(suggested)
        )
        summary = st.text_area(
            "Conversation summary *",
            value=build_ticket_summary(history),
            height=110,
            max_chars=tickets.MAX_SUMMARY_CHARS,
            placeholder="Tell us briefly what you need help with…",
        )
        if transcript:
            with st.expander(f"📎 Chat transcript attached ({len(history)} messages)"):
                st.text(transcript)
        submitted = st.form_submit_button("Submit ticket", type="primary", use_container_width=True)

    if submitted:
        try:
            ticket = tickets.create_ticket(
                name=name,
                email=email,
                category=category,
                summary=summary,
                order_id=order_id,
                transcript=transcript,
                source=source,
            )
        except ValueError as exc:
            st.error(str(exc), icon="✋")
            return
        st.session_state.messages.append(
            {
                "id": uuid.uuid4().hex[:10],
                "role": "assistant",
                "kind": "ticket",
                "content": f"Ticket {ticket['id']} raised",
                "ticket": ticket,
            }
        )
        st.session_state.queue_open = True
        st.rerun()


# ==========================================================================
# Sidebar
# ==========================================================================
with st.sidebar:
    st.markdown(styles.sidebar_brand_html(), unsafe_allow_html=True)
    st.write("")

    st.button(
        "Talk to a human",
        key="sb_human",
        icon="🙋",
        use_container_width=True,
        on_click=_request_ticket,
        args=("manual", None),
    )
    st.button("New chat", key="sb_new", icon="🧹", use_container_width=True, on_click=_new_chat)
    st.button("Refresh FAQs", key="sb_refresh", icon="🔄", use_container_width=True, on_click=_refresh_faqs)

    st.markdown("##### Knowledge base")
    synced = styles.relative_time(kb.fetched_at)
    st.markdown(
        styles.card_html("Source", kb.source_label, f"{len(kb.faqs)} FAQs · synced {synced} · auto-refresh 5 min"),
        unsafe_allow_html=True,
    )
    if kb.warning:
        st.warning(kb.warning, icon="⚠️")
    elif kb.source == "sample":
        st.caption("Add `FAQ_SHEET_CSV_URL` to secrets to load FAQs from your Google Sheet.")

    engine_sub = llm.model if tara.online else "Add an API key to enable AI answers"
    st.markdown(styles.card_html("Assistant engine", llm.label, engine_sub), unsafe_allow_html=True)

    all_tickets = tickets.list_tickets()
    with st.expander(f"📋 Support Queue (Demo View) · {len(all_tickets)}", expanded=st.session_state.queue_open):
        if not all_tickets:
            st.caption("No tickets yet. Raise one from the chat to see it appear here live.")
        for t in all_tickets[:8]:
            st.markdown(styles.queue_item_html(t), unsafe_allow_html=True)
        if len(all_tickets) > 8:
            st.caption(f"+ {len(all_tickets) - 8} older tickets")
        if all_tickets:
            st.download_button(
                "Download tickets.json",
                data=json.dumps(list(reversed(all_tickets)), indent=2, ensure_ascii=False),
                file_name="tickets.json",
                mime="application/json",
                icon="⬇️",
                use_container_width=True,
            )

    counts = tickets.feedback_counts()
    total = counts["up"] + counts["down"]
    rate = f"{round(100 * counts['up'] / total)}% helpful" if total else "No ratings yet"
    st.markdown("##### Reply feedback")
    st.markdown(
        f'<div class="tt-fb"><span>👍 <b>{counts["up"]}</b></span><span>👎 <b>{counts["down"]}</b></span>'
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

prompt = st.chat_input("Ask Tara about delivery, payments, returns, freshness…", max_chars=1000)
prompt = prompt or st.session_state.pop("pending_prompt", None)

if not st.session_state.messages and not prompt:
    st.markdown(styles.welcome_html(), unsafe_allow_html=True)
    with st.container(key="chips", horizontal=True, gap="small"):
        for i, (icon, text) in enumerate(SUGGESTIONS):
            st.button(text, key=f"chip_{i}", icon=icon, on_click=_queue_prompt, args=(text,))


def render_message(msg: dict, is_last: bool) -> None:
    if msg["role"] == "user":
        with st.chat_message("user", avatar=styles.USER_AVATAR):
            st.markdown('<span class="tt-role-user"></span>', unsafe_allow_html=True)
            st.markdown(msg["content"])
        return

    with st.chat_message("assistant", avatar=styles.TARA_AVATAR):
        st.markdown('<span class="tt-role-assistant"></span>', unsafe_allow_html=True)
        if msg.get("kind") == "ticket":
            ticket = msg["ticket"]
            first_name = (ticket["name"].split() or ["there"])[0]
            st.markdown(
                f"<p>All set, <b>{escape(first_name)}</b>! 🎉 I've passed this to the TeaTrail team. "
                f"A teammate will reply to <b>{escape(ticket['email'])}</b>. Here's your reference:</p>",
                unsafe_allow_html=True,
            )
            st.markdown(styles.ticket_html(ticket), unsafe_allow_html=True)
            st.caption("You can keep chatting with me in the meantime 🍵")
            return

        st.markdown(msg["content"])
        if msg.get("sources"):
            st.markdown(styles.sources_html(msg["sources"]), unsafe_allow_html=True)
        if msg.get("degraded"):
            st.markdown(
                '<div class="tt-note">Answered straight from our FAQs while the AI service is unavailable.</div>',
                unsafe_allow_html=True,
            )
        if msg.get("handoff") and is_last:
            st.markdown(styles.handoff_html(), unsafe_allow_html=True)
            st.button(
                "Raise a ticket",
                key=f"handoff_{msg['id']}",
                icon="🎫",
                on_click=_request_ticket,
                args=("tara", msg.get("category_hint")),
            )
        if msg.get("kind") in {"answer", "handoff"}:
            st.feedback("thumbs", key=f"fb_{msg['id']}", on_change=_on_feedback, args=(msg["id"],))


messages = st.session_state.messages
for i, msg in enumerate(messages):
    render_message(msg, is_last=i == len(messages) - 1)

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
                "handoff": reply.handoff,
                "sources": [{"id": f.id, "question": f.question, "category": f.category} for f in reply.sources],
                "provider": reply.provider,
                "degraded": reply.degraded,
                "category_hint": reply.category_hint,
            },
        ]
    )
    st.rerun()

# Open the ticket form last, so it can be requested from the sidebar or a chat bubble.
request = st.session_state.pop("open_ticket", None)
if request:
    ticket_dialog(request["source"], request.get("hint"))
