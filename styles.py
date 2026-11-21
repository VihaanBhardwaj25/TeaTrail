"""TeaTrail design system: CSS tokens, global styles and HTML snippets.

Every dynamic value inserted into HTML goes through ``html.escape`` because
ticket fields and FAQ text come from customers / a public spreadsheet.
"""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from pathlib import Path

ASSETS = Path(__file__).resolve().parent / "assets"
TARA_AVATAR = str(ASSETS / "tara.svg")
USER_AVATAR = str(ASSETS / "user.svg")

LEAF_SVG = (
    '<svg viewBox="0 0 24 24" width="{s}" height="{s}" aria-hidden="true">'
    '<path d="M5 19c0-8 5.5-13.5 15-14-.5 9.5-6 15-14 15" fill="none" stroke="currentColor" '
    'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>'
    '<path d="M5 19c3-4 6-6.5 10-8.5" fill="none" stroke="currentColor" stroke-width="1.8" '
    'stroke-linecap="round"/></svg>'
)

LOGO_SVG = (
    '<svg viewBox="0 0 48 48" width="{s}" height="{s}" aria-hidden="true">'
    '<rect width="48" height="48" rx="14" fill="#2D4F3E"/>'
    '<path d="M13 22h18v5a9 9 0 0 1-9 9h0a9 9 0 0 1-9-9z" fill="#FAF7F2"/>'
    '<path d="M31 24h2.5a3.5 3.5 0 0 1 0 7H31.5" fill="none" stroke="#FAF7F2" stroke-width="2.2" stroke-linecap="round"/>'
    '<path d="M22.5 19.5c-4-1.6-5.2-6.4-2.8-10.4 4.8 1.2 6.7 5.4 2.8 10.4z" fill="#C86D44"/>'
    "</svg>"
)

CSS = """
<style>
:root {
  --tt-cream: #FAF7F2;
  --tt-parchment: #F2ECE1;
  --tt-green: #2D4F3E;
  --tt-green-2: #3C6650;
  --tt-green-ink: #1F3A2C;
  --tt-green-tint: #E6EDE7;
  --tt-sage: #EEF1EA;
  --tt-chai: #C86D44;
  --tt-chai-dark: #A9552F;
  --tt-chai-tint: #F7E7DC;
  --tt-espresso: #241E1A;
  --tt-muted: #6E625A;
  --tt-line: #E6DDCF;
  --tt-shadow: 0 1px 2px rgba(36,30,26,.04), 0 8px 24px -12px rgba(36,30,26,.18);
  --tt-serif: "Fraunces", Georgia, "Times New Roman", serif;
}

/* ---------- Chrome: make it feel like a standalone web app ---------- */
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stStatusWidget"], .stDeployButton, [data-testid="stAppDeployButton"] { display: none !important; }
header[data-testid="stHeader"] { background: transparent; }
.stApp {
  background:
    radial-gradient(1200px 500px at 85% -10%, rgba(200,109,68,.07), transparent 60%),
    radial-gradient(900px 500px at -10% 10%, rgba(45,79,62,.06), transparent 60%),
    var(--tt-cream);
}
.block-container { max-width: 860px; padding-top: 2.2rem; padding-bottom: 7rem; }
h1, h2, h3 { font-family: var(--tt-serif) !important; letter-spacing: -0.01em; color: var(--tt-espresso); }

/* ---------- Hero header ---------- */
.tt-hero {
  position: relative; overflow: hidden;
  background: linear-gradient(135deg, var(--tt-green) 0%, var(--tt-green-2) 100%);
  color: var(--tt-cream); border-radius: 22px; padding: 26px 28px 22px;
  box-shadow: var(--tt-shadow); margin-bottom: 18px;
}
.tt-hero::after {
  content: ""; position: absolute; right: -60px; top: -60px; width: 240px; height: 240px;
  border-radius: 50%; background: radial-gradient(circle, rgba(200,109,68,.35), transparent 70%);
}
.tt-hero .tt-leaf-deco { position: absolute; right: 26px; bottom: 14px; color: rgba(250,247,242,.12); }
.tt-hero-top { display: flex; align-items: center; justify-content: space-between; gap: 12px; position: relative; z-index: 1; }
.tt-brand { display: flex; align-items: center; gap: 10px; font-family: var(--tt-serif); font-size: 1.05rem; font-weight: 600; letter-spacing: .01em; }
.tt-brand small { font-family: inherit; opacity: .7; font-weight: 400; }
.tt-status { display: inline-flex; align-items: center; gap: 8px; font-size: .78rem; font-weight: 600;
  background: rgba(250,247,242,.12); border: 1px solid rgba(250,247,242,.2); padding: 5px 11px; border-radius: 999px; white-space: nowrap; }
.tt-dot { width: 8px; height: 8px; border-radius: 50%; background: #8FD19E; box-shadow: 0 0 0 3px rgba(143,209,158,.25); }
.tt-dot.offline { background: #F2C37A; box-shadow: 0 0 0 3px rgba(242,195,122,.25); }
.tt-hero-body { display: flex; gap: 16px; align-items: center; margin-top: 20px; position: relative; z-index: 1; }
.tt-hero-body img { width: 58px; height: 58px; border-radius: 50%; border: 3px solid rgba(250,247,242,.25); flex-shrink: 0; }
.tt-hero h1 { color: var(--tt-cream) !important; font-size: 1.9rem !important; margin: 0 !important; padding: 0 !important; line-height: 1.15; }
.tt-hero p { margin: 4px 0 0; opacity: .88; font-size: .95rem; line-height: 1.5; }
.tt-meta { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; position: relative; z-index: 1; }
.tt-pill { font-size: .75rem; font-weight: 600; padding: 4px 10px; border-radius: 999px;
  background: rgba(250,247,242,.14); color: var(--tt-cream); }
.tt-pill.chai { background: var(--tt-chai); }

/* ---------- Welcome state & suggestion chips ---------- */
.tt-section-label { font-size: .74rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase;
  color: var(--tt-muted); margin: 6px 0 2px; }
.st-key-chips button {
  border-radius: 999px !important; border: 1px solid var(--tt-line) !important; background: #fff !important;
  color: var(--tt-espresso) !important; font-weight: 500 !important; padding: 6px 14px !important;
  min-height: 0 !important; box-shadow: 0 1px 2px rgba(36,30,26,.04); transition: all .15s ease;
}
.st-key-chips button:hover { border-color: var(--tt-chai) !important; color: var(--tt-chai-dark) !important;
  background: var(--tt-chai-tint) !important; transform: translateY(-1px); }
.tt-welcome { background: #fff; border: 1px solid var(--tt-line); border-radius: 18px; padding: 18px 20px; margin: 4px 0 10px; box-shadow: var(--tt-shadow); }
.tt-welcome h3 { margin: 0 0 4px !important; padding: 0 !important; font-size: 1.15rem !important; }
.tt-welcome p { margin: 0; color: var(--tt-muted); font-size: .92rem; }

/* ---------- Chat messages ---------- */
[data-testid="stChatMessage"] { background: transparent !important; padding: 4px 0 !important; gap: 12px; }
[data-testid="stChatMessage"] img { border-radius: 50%; }
[data-testid="stChatMessage"]:has(.tt-role-assistant) [data-testid="stChatMessageContent"] {
  background: #fff; border: 1px solid var(--tt-line); border-radius: 4px 18px 18px 18px;
  padding: 12px 18px 8px; box-shadow: var(--tt-shadow); max-width: 640px;
}
[data-testid="stChatMessage"]:has(.tt-role-user) { flex-direction: row-reverse; }
[data-testid="stChatMessage"]:has(.tt-role-user) [data-testid="stChatMessageContent"] {
  background: var(--tt-green); color: var(--tt-cream); border-radius: 18px 4px 18px 18px;
  padding: 12px 18px; margin-left: auto; max-width: 560px; flex-grow: 0;
}
[data-testid="stChatMessage"]:has(.tt-role-user) [data-testid="stChatMessageContent"] * { color: var(--tt-cream) !important; }
[data-testid="stChatMessageContent"] p { line-height: 1.6; }
.tt-role-user, .tt-role-assistant { display: none; }
[data-testid="stElementContainer"]:has(.tt-role-user), [data-testid="stElementContainer"]:has(.tt-role-assistant) { display: none !important; }

.tt-sources { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin: 2px 0 2px; font-size: .74rem; color: var(--tt-muted); }
.tt-source { background: var(--tt-sage); color: var(--tt-green-ink); border-radius: 999px; padding: 2px 9px; font-weight: 600; }
.tt-note { font-size: .74rem; color: var(--tt-muted); margin-top: 2px; }

/* Typing indicator */
.tt-typing { display: inline-flex; gap: 5px; padding: 6px 2px; }
.tt-typing span { width: 7px; height: 7px; border-radius: 50%; background: var(--tt-green-2); opacity: .35; animation: tt-blink 1.2s infinite; }
.tt-typing span:nth-child(2) { animation-delay: .2s; } .tt-typing span:nth-child(3) { animation-delay: .4s; }
@keyframes tt-blink { 0%, 80%, 100% { opacity: .25; transform: translateY(0); } 40% { opacity: 1; transform: translateY(-3px); } }

/* Hand-off card */
.tt-handoff { display: flex; gap: 12px; align-items: center; background: var(--tt-chai-tint);
  border: 1px solid #EFD3C1; border-radius: 14px; padding: 10px 14px; margin: 8px 0 4px; color: var(--tt-espresso); font-size: .88rem; }
.tt-handoff b { color: var(--tt-chai-dark); }
[class*="st-key-handoff_"] button, .st-key-sb_human button {
  background: var(--tt-chai) !important; border-color: var(--tt-chai) !important; color: #fff !important; font-weight: 600 !important;
}
[class*="st-key-handoff_"] button:hover, .st-key-sb_human button:hover { background: var(--tt-chai-dark) !important; border-color: var(--tt-chai-dark) !important; }

/* Ticket confirmation */
.tt-ticket { border: 1px solid #CFE0D3; background: linear-gradient(180deg, #F3F8F3, #fff); border-radius: 16px; padding: 16px 18px; }
.tt-ticket-top { display: flex; justify-content: space-between; align-items: center; gap: 10px; }
.tt-ticket-id { font-family: var(--tt-serif); font-size: 1.6rem; font-weight: 700; color: var(--tt-green); letter-spacing: .02em; }
.tt-badge { font-size: .7rem; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; padding: 3px 9px; border-radius: 999px; background: var(--tt-green-tint); color: var(--tt-green-ink); }
.tt-badge.high { background: var(--tt-chai-tint); color: var(--tt-chai-dark); }
.tt-queue-item.normal { border-left-color: var(--tt-green-2); }
.tt-queue-item.normal .cat { background: var(--tt-green-tint); color: var(--tt-green-ink); }
[class*="st-key-offer_"] button { border-radius: 999px !important; }
[class*="st-key-offer_"] [class*="st-key-yes_"] button { background: var(--tt-chai) !important; border-color: var(--tt-chai) !important; color: #fff !important; }
.tt-ticket dl { display: grid; grid-template-columns: max-content 1fr; gap: 4px 14px; margin: 10px 0 0; font-size: .86rem; }
.tt-ticket dt { color: var(--tt-muted); } .tt-ticket dd { margin: 0; font-weight: 600; }

/* ---------- Chat input ---------- */
[data-testid="stBottomBlockContainer"] { background: linear-gradient(180deg, rgba(250,247,242,0), var(--tt-cream) 30%); max-width: 860px; }
[data-testid="stChatInput"] { border-radius: 16px !important; border: 1px solid var(--tt-line) !important; background: #fff !important; box-shadow: var(--tt-shadow); }
[data-testid="stChatInput"]:focus-within { border-color: var(--tt-green) !important; }
[data-testid="stChatInputSubmitButton"] { background: var(--tt-green) !important; color: #fff !important; border-radius: 10px !important; }

/* ---------- Sidebar ---------- */
section[data-testid="stSidebar"] { border-right: 1px solid var(--tt-line); }
section[data-testid="stSidebar"] .block-container { padding-top: 1.5rem; }
.tt-sb-brand { display: flex; align-items: center; gap: 10px; margin-bottom: 4px; }
.tt-sb-brand b { font-family: var(--tt-serif); font-size: 1.2rem; color: var(--tt-espresso); }
.tt-sb-brand span { display: block; font-size: .75rem; color: var(--tt-muted); }
.tt-card { background: #fff; border: 1px solid var(--tt-line); border-radius: 14px; padding: 12px 14px; font-size: .84rem; margin-bottom: 8px; }
.tt-card .k { color: var(--tt-muted); font-size: .72rem; font-weight: 700; text-transform: uppercase; letter-spacing: .07em; }
.tt-card .v { font-weight: 600; color: var(--tt-espresso); margin-top: 2px; }
.tt-card .s { color: var(--tt-muted); font-size: .76rem; margin-top: 2px; }
.tt-queue-item { background: #fff; border: 1px solid var(--tt-line); border-left: 3px solid var(--tt-chai); border-radius: 10px; padding: 9px 11px; margin-bottom: 8px; font-size: .8rem; }
.tt-queue-item .row { display: flex; justify-content: space-between; align-items: center; gap: 6px; }
.tt-queue-item .id { font-weight: 700; color: var(--tt-green); }
.tt-queue-item .cat { font-size: .68rem; font-weight: 700; background: var(--tt-chai-tint); color: var(--tt-chai-dark); padding: 1px 7px; border-radius: 999px; }
.tt-queue-item .who { color: var(--tt-muted); margin-top: 3px; font-size: .74rem; }
.tt-queue-item .sum { margin-top: 4px; color: var(--tt-espresso); line-height: 1.4; }
.tt-fb { display: flex; gap: 10px; font-size: .82rem; color: var(--tt-muted); margin-bottom: 14px; }
.tt-fb b { color: var(--tt-espresso); }
.tt-faq-q { font-weight: 600; font-size: .82rem; margin-top: 8px; color: var(--tt-espresso); }
.tt-faq-a { font-size: .78rem; color: var(--tt-muted); line-height: 1.45; }
.st-key-sb_lock button { color: var(--tt-muted) !important; }

/* ---------- Buttons & forms ---------- */
.stButton button[kind="primary"], .stFormSubmitButton button[kind="primaryFormSubmit"], [data-testid="stBaseButton-primaryFormSubmit"] {
  background: var(--tt-green) !important; border-color: var(--tt-green) !important; font-weight: 600 !important;
}
.stButton button[kind="primary"]:hover, [data-testid="stBaseButton-primaryFormSubmit"]:hover { background: var(--tt-green-ink) !important; }
div[role="dialog"] h2 { font-family: var(--tt-serif) !important; }
@media (max-width: 640px) {
  .tt-hero { padding: 20px 18px; border-radius: 18px; }
  .tt-hero h1 { font-size: 1.5rem !important; }
  .tt-status { display: none; }
}
</style>
"""

LOCK_CSS = """
<style>
section[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="stExpandSidebarButton"] { display: none !important; }
.block-container { max-width: 460px !important; padding-top: 9vh !important; }
.tt-lock { text-align: center; margin-bottom: 18px; }
.tt-lock .logo { display: inline-flex; filter: drop-shadow(0 10px 18px rgba(45,79,62,.28)); }
.tt-lock h1 { font-size: 2.5rem !important; margin: 14px 0 0 !important; padding: 0 !important; color: var(--tt-espresso) !important; }
.tt-lock .sub { font-family: var(--tt-serif); font-style: italic; color: var(--tt-chai); font-size: 1.05rem; margin-top: 2px; }
.tt-lock p { color: var(--tt-muted); font-size: .92rem; margin: 14px auto 0; max-width: 340px; line-height: 1.55; }
[data-testid="stForm"] { background: #fff; border: 1px solid var(--tt-line) !important; border-radius: 20px; padding: 22px 22px 18px; box-shadow: var(--tt-shadow); }
.tt-lock-foot { text-align: center; font-size: .76rem; color: var(--tt-muted); margin-top: 16px; }
</style>
"""


# --------------------------------------------------------------------------
# HTML snippets
# --------------------------------------------------------------------------
def hero_html(provider_label: str, online: bool, faq_count: int, kb_label: str, avatar_uri: str) -> str:
    dot = "tt-dot" if online else "tt-dot offline"
    status = f"{escape(provider_label)} · online" if online else "Offline FAQ mode"
    return f"""
<div class="tt-hero">
  <div class="tt-leaf-deco">{LEAF_SVG.format(s=120)}</div>
  <div class="tt-hero-top">
    <div class="tt-brand">{LOGO_SVG.format(s=30)} TeaTrail Store <small>· Support</small></div>
    <div class="tt-status"><span class="{dot}"></span>{status}</div>
  </div>
  <div class="tt-hero-body">
    <img src="{avatar_uri}" alt="Tara"/>
    <div>
      <h1>Hi, I'm Tara</h1>
      <p>Your TeaTrail helper for products, orders, delivery, payments, returns and refunds.</p>
    </div>
  </div>
  <div class="tt-meta">
    <span class="tt-pill">📚 {faq_count} FAQs · {escape(kb_label)}</span>
    <span class="tt-pill">🎫 A person replies within 24 hours</span>
    <span class="tt-pill chai">🍃 Fresh from the estate</span>
  </div>
</div>"""


def lock_html() -> str:
    return f"""
<div class="tt-lock">
  <div class="logo">{LOGO_SVG.format(s=68)}</div>
  <h1>TeaTrail</h1>
  <div class="sub">Support Studio</div>
  <p>This preview is passcode-protected. Enter the team passcode to chat with Tara, our support assistant.</p>
</div>"""


def welcome_html() -> str:
    return '<div class="tt-section-label">Popular questions</div>'

def sources_html(sources: list[dict]) -> str:
    if not sources:
        return ""
    chips = "".join(f'<span class="tt-source">{escape(s["question"])}</span>' for s in sources[:3])
    return f'<div class="tt-sources">📖 From our FAQs: {chips}</div>'


def handoff_html() -> str:
    return (
        '<div class="tt-handoff">🧑‍🍳 <div><b>Need a human touch?</b> A TeaTrail teammate can pick this up '
        "and reply by email. Your chat is attached automatically.</div></div>"
    )


def ticket_html(ticket: dict) -> str:
    priority = ticket.get("priority", "normal")
    rows = [("Reason", ticket.get("reason", "")), ("Priority", priority.title()), ("Status", ticket.get("status", "open").title())]
    if ticket.get("email"):
        rows.append(("Reply to", ticket["email"]))
    items = "".join(f"<dt>{escape(k)}</dt><dd>{escape(v)}</dd>" for k, v in rows)
    return f"""
<div class="tt-ticket">
  <div class="tt-ticket-top"><div class="tt-ticket-id">{escape(ticket["ticket_id"])}</div>
  <span class="tt-badge {escape(priority)}">{escape(priority)} priority</span></div>
  <dl>{items}</dl>
</div>"""

def queue_item_html(ticket: dict) -> str:
    message = ticket.get("message", "")
    message = message[:110] + ("…" if len(message) > 110 else "")
    when = relative_time(ticket.get("time", ""))
    priority = ticket.get("priority", "normal")
    who = f" · {ticket['name']}" if ticket.get("name") else ""
    return f"""
<div class="tt-queue-item {escape(priority)}">
  <div class="row"><span class="id">{escape(ticket["ticket_id"])}</span><span class="cat">{escape(priority)}</span></div>
  <div class="who">{escape(ticket.get("reason", ""))} · {escape(when)}{escape(who)}</div>
  <div class="sum">"{escape(message)}"</div>
</div>"""

def card_html(label: str, value: str, sub: str = "") -> str:
    sub_html = f'<div class="s">{escape(sub)}</div>' if sub else ""
    return f'<div class="tt-card"><div class="k">{escape(label)}</div><div class="v">{escape(value)}</div>{sub_html}</div>'


def sidebar_brand_html() -> str:
    return (
        f'<div class="tt-sb-brand">{LOGO_SVG.format(s=36)}<div><b>TeaTrail</b>'
        "<span>Support Studio</span></div></div>"
    )


def typing_html() -> str:
    return '<div class="tt-typing"><span></span><span></span><span></span></div>'


def relative_time(iso: str) -> str:
    try:
        then = datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return ""
    seconds = int((datetime.now(timezone.utc) - then).total_seconds())
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{seconds // 60} min ago"
    if seconds < 86400:
        return f"{seconds // 3600} h ago"
    return then.strftime("%d %b")
