"""FAQ knowledge base: Google Sheet CSV loader, sample fallback and retrieval.

The sheet only needs two columns, ``question`` and ``answer`` (``category``
is optional). Header names are matched case-insensitively and a few common
aliases are accepted (``Q``/``A``, ``Topic``, ...).
"""

from __future__ import annotations

import io
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pandas as pd
import requests
import streamlit as st

SAMPLE_CSV = Path(__file__).resolve().parent / "sample_faqs.csv"
MAX_FAQS = 200
FETCH_TIMEOUT_S = 10
UNKNOWN_TERM_WEIGHT = 0.45
MAX_CSV_BYTES = 2_000_000

_QUESTION_ALIASES = ["question", "questions", "q", "faq", "faq question", "customer question"]
_ANSWER_ALIASES = ["answer", "answers", "a", "response", "faq answer", "reply"]
_CATEGORY_ALIASES = ["category", "topic", "section", "type", "tag"]


@dataclass(frozen=True)
class FAQ:
    id: int
    category: str
    question: str
    answer: str


@dataclass
class KnowledgeBase:
    faqs: list[FAQ]
    source: str  # "sheet" | "sample"
    fetched_at: str
    url: str = ""
    warning: str | None = None
    categories: list[str] = field(default_factory=list)

    @property
    def source_label(self) -> str:
        return "Google Sheet (live)" if self.source == "sheet" else "Built-in sample FAQs"


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------
def sheet_csv_urls(url: str) -> list[str]:
    """CSV URLs to try for a sheet link, best first.

    Google Sheets share/edit links become the ``gviz`` CSV endpoint (served
    straight from docs.google.com), with the ``export`` endpoint as a backup.
    "Publish to web" links and any other CSV URL are used as they are.
    """
    url = url.strip()
    parsed = urlparse(url)
    if "docs.google.com" not in parsed.netloc or "/spreadsheets/" not in parsed.path:
        return [url]

    query = parse_qs(parsed.query)
    if "/pub" in parsed.path:  # File → Share → Publish to web link
        base = url.split("?")[0].replace("/pubhtml", "/pub")
        gid = query.get("gid", [None])[0]
        return [f"{base}?output=csv" + (f"&gid={gid}" if gid else "")]

    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", parsed.path)
    if not match:
        return [url]
    sheet = f"https://docs.google.com/spreadsheets/d/{match.group(1)}"
    gid_match = re.search(r"gid=(\d+)", url)
    gid = f"&gid={gid_match.group(1)}" if gid_match else ""
    return [f"{sheet}/gviz/tq?tqx=out:csv&headers=1{gid}", f"{sheet}/export?format=csv{gid}"]


def normalize_sheet_url(url: str) -> str:
    """The preferred CSV URL for a sheet link (see ``sheet_csv_urls``)."""
    return sheet_csv_urls(url)[0]


def _short_reason(exc: Exception) -> str:
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return f"HTTP {exc.response.status_code}"
    if isinstance(exc, requests.Timeout):
        return "timed out"
    if isinstance(exc, requests.ConnectionError):
        return "couldn't connect"
    text = str(exc).splitlines()[0] if str(exc) else exc.__class__.__name__
    return text[:120]


def _find_column(columns: dict[str, str], aliases: list[str]) -> str | None:
    for alias in aliases:
        if alias in columns:
            return columns[alias]
    return None


def parse_faq_frame(df: pd.DataFrame) -> list[FAQ]:
    """Validate and normalise a FAQ dataframe into FAQ records."""
    columns = {str(c).strip().lower(): c for c in df.columns}
    q_col = _find_column(columns, _QUESTION_ALIASES)
    a_col = _find_column(columns, _ANSWER_ALIASES)
    c_col = _find_column(columns, _CATEGORY_ALIASES)
    if q_col is None or a_col is None:
        raise ValueError("the sheet needs 'question' and 'answer' columns")

    faqs: list[FAQ] = []
    for _, row in df.iterrows():
        question = str(row[q_col]).strip() if pd.notna(row[q_col]) else ""
        answer = str(row[a_col]).strip() if pd.notna(row[a_col]) else ""
        if not question or not answer:
            continue
        category = "General"
        if c_col is not None and pd.notna(row[c_col]) and str(row[c_col]).strip():
            category = str(row[c_col]).strip()
        faqs.append(FAQ(len(faqs) + 1, category, question, answer))
        if len(faqs) >= MAX_FAQS:
            break
    return faqs


def _load_sample() -> list[FAQ]:
    return parse_faq_frame(pd.read_csv(SAMPLE_CSV))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _build(faqs: list[FAQ], source: str, url: str = "", warning: str | None = None) -> KnowledgeBase:
    categories = list(dict.fromkeys(f.category for f in faqs))
    return KnowledgeBase(faqs, source, _now(), url, warning, categories)


def _download(csv_url: str) -> list[FAQ]:
    resp = requests.get(csv_url, timeout=FETCH_TIMEOUT_S, headers={"User-Agent": "TeaTrailSupport/1.0"})
    resp.raise_for_status()
    if len(resp.content) > MAX_CSV_BYTES:
        raise ValueError("the CSV is larger than 2 MB")
    if "text/html" in resp.headers.get("content-type", ""):
        raise ValueError("the link returned a web page, not CSV (is the sheet shared publicly?)")
    faqs = parse_faq_frame(pd.read_csv(io.StringIO(resp.content.decode("utf-8-sig"))))
    if not faqs:
        raise ValueError("the sheet has no complete question/answer rows")
    return faqs


def fetch_faqs(url: str | None) -> KnowledgeBase:
    """Fetch FAQs from a public sheet/CSV URL, falling back to the bundled copy."""
    if not url:
        return _build(_load_sample(), "sample")

    reasons = []
    for csv_url in sheet_csv_urls(url):
        try:
            return _build(_download(csv_url), "sheet", url)
        except Exception as exc:  # network error, bad CSV, private sheet, ...
            reasons.append(_short_reason(exc))
    reason = reasons[0] if len(set(reasons)) == 1 else "; ".join(dict.fromkeys(reasons))
    warning = f"Couldn't load the Google Sheet ({reason}). Using the built-in FAQs for now."
    return _build(_load_sample(), "sample", url, warning)


@st.cache_data(ttl=300, show_spinner="Steeping the latest FAQs…")
def load_knowledge_base(url: str | None) -> KnowledgeBase:
    """Cached loader used by the app (5-minute TTL, cleared by 'Refresh FAQs')."""
    return fetch_faqs(url)


# --------------------------------------------------------------------------
# Retrieval (no external dependencies; used for grounding hints, source
# chips and the offline mode)
# --------------------------------------------------------------------------
_PHRASES = {
    r"cash on delivery": " cod ",
    r"money back": " refund ",
    r"send (it )?back": " return ",
    r"shelf[- ]life": " shelf ",
    r"same[- ]day": " express ",
    r"net ?banking": " pay ",
    r"how long": " time ",
    r"refund polic(y|ies)": " refund ",
    r"\b\d{6}\b": " pincode ",
    r"(physical|offline|retail|your|a) (store|shop|outlet)|\bshowroom\b|\boutlet\b": " shop ",
    r"sign ?in|log ?in": " password ",
    r"customer (care|service|support)|support team": " support ",
    r"opened (pack|packet|box|tea|item)": " open_pack ",
    r"where('?s| is) my": " track ",
    r"(has ?n'?t|not|never|didn'?t|did not) (yet )?(arrived?|come|reached|been delivered)": " track ",
    r"(get|getting|receive) (my |the )?money": " refund ",
    r"credit card|debit card": " pay ",
}

_SYNONYMS = {
    # delivery & shipping
    "ship": "deliver", "shipping": "deliver", "shipped": "deliver", "shipment": "deliver",
    "delivery": "deliver", "delivered": "deliver", "deliveri": "deliver", "courier": "deliver",
    "dispatch": "deliver", "dispatched": "deliver", "arrive": "deliver", "arrival": "deliver",
    "postage": "deliver",
    "when": "time", "soon": "time", "long": "time",
    "came": "deliver", "receive": "deliver", "received": "deliver", "reach": "deliver",
    "parcel": "order", "package": "order", "packag": "order", "purchase": "order",
    "fast": "express", "faster": "express", "quick": "express", "urgent": "express",
    "tracking": "track", "status": "track", "trace": "track",
    "abroad": "international", "overseas": "international", "worldwide": "international",
    "usa": "international", "uk": "international", "country": "international", "countri": "international",
    # money
    "price": "cost", "fee": "cost", "charge": "cost", "charges": "cost", "much": "cost", "free": "cost",
    "payment": "pay", "paying": "pay", "paid": "pay", "upi": "pay", "gpay": "pay", "phonepe": "pay",
    "paytm": "pay", "wallet": "pay", "visa": "pay", "mastercard": "pay", "rupay": "pay", "amex": "pay",
    "cash": "cod", "card": "pay",
    "option": "method", "options": "method", "mode": "method", "modes": "method", "way": "method", "ways": "method",
    "secure": "safe", "security": "safe", "fraud": "safe", "scam": "safe",
    "refunded": "refund", "reimburse": "refund", "reimbursement": "refund",
    "returning": "return", "returned": "return", "exchange": "return",
    "cancellation": "cancel", "cancelled": "cancel", "canceled": "cancel",
    # product quality
    "freshness": "fresh", "stale": "fresh", "expiry": "fresh", "expire": "fresh",
    "expiration": "fresh", "old": "fresh",
    "storage": "store", "keep": "store",
    "roast": "coffee", "roasted": "coffee", "beans": "coffee", "bean": "coffee",
    "broken": "damage", "damaged": "damage", "wrong": "damage", "leaking": "damage",
    "defective": "damage", "spoiled": "damage", "torn": "damage", "missing": "damage",
    # gifting
    "hamper": "gift", "hampers": "gift", "gifting": "gift", "gifts": "gift", "basket": "gift",
    "present": "gift", "giftbox": "gift",
    "bulk": "corporate", "company": "corporate", "office": "corporate", "employees": "corporate",
    "wholesale": "corporate", "client": "corporate", "clients": "corporate",
    "note": "message", "personalised": "message", "personalized": "message",
    # orders, account & offers
    "pincode": "pincode", "pin": "pincode", "zip": "pincode", "postcode": "pincode", "area": "pincode",
    "city": "pincode", "town": "pincode", "village": "pincode", "location": "pincode",
    "coupon": "coupon", "coupons": "coupon", "promo": "coupon", "voucher": "coupon", "discount": "coupon",
    "discounts": "coupon", "offer": "coupon", "offers": "coupon",
    "password": "password", "login": "password", "log": "password", "signin": "password", "forgot": "password",
    "account": "password",
    "hours": "hour", "timing": "hour", "timings": "hour", "open": "hour", "available": "hour",
    "veg": "vegetarian", "eggless": "vegetarian", "allergen": "vegetarian", "allergy": "vegetarian",
    "allergies": "vegetarian", "ingredients": "vegetarian",
    "opened": "open_pack", "unsealed": "open_pack", "used": "unused",
}

_STOPWORDS = set(
    """a an the and or but if of to in on at for from by with about into over is are was were be
    been being do does did done doing have has had having i me my mine we our ours you your yours he
    she it its they them their this that these those what which who whom whose why how where can
    could would should will shall may might must just so than too very also any some all no not
    there here please hi hello hey thanks thank tell know want need get got am im ive id dont
    teatrail tara us one sell sells buy stock carry still
    many something anything thing things kind exactly really already yet ok okay sure everywhere guys
    unacceptable terrible horrible awful worst ridiculous disgusting pathetic useless angry
    furious upset annoyed frustrated seriously wtf""".split()
)


def _stem(word: str) -> str:
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 5 and word.endswith("ing"):
        return word[:-3]
    if len(word) > 4 and word.endswith("ed"):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def tokenize(text: str) -> set[str]:
    text = text.lower()
    for pattern, replacement in _PHRASES.items():
        text = re.sub(pattern, replacement, text)
    terms: set[str] = set()
    for word in re.findall(r"[a-z0-9]+", text):
        if word in _STOPWORDS or len(word) < 2:
            continue
        canon = _SYNONYMS.get(word) or _SYNONYMS.get(_stem(word)) or _stem(word)
        terms.add(canon)
    return terms


def search_faqs(faqs: list[FAQ], query: str, k: int = 3) -> list[tuple[FAQ, float]]:
    """Rank FAQs for ``query``. Scores are in [0, 1] (share of query terms covered).

    Terms matching an FAQ's question or category count fully; terms found only
    in the answer count 60%. Each term is weighted by IDF, so rare, specific
    words ("hamper", "cod") matter more than generic ones.
    """
    q_terms = tokenize(query)
    if not q_terms or not faqs:
        return []

    indexed = [
        (faq, tokenize(faq.question) | tokenize(faq.category), tokenize(faq.answer)) for faq in faqs
    ]
    n = len(indexed)
    df: dict[str, int] = {}
    for _, head, body in indexed:
        for term in head | body:
            df[term] = df.get(term, 0) + 1

    def idf(term: str) -> float:
        return math.log((n + 1) / (df.get(term, 0) + 0.5)) + 1.0

    # Words the knowledge base never uses still count against coverage, but at a
    # reduced weight, so natural phrasing ("for our office Diwali party") doesn't
    # drown out a clear match.
    known_max = max((idf(t) for t in df), default=1.0)

    def weight(term: str) -> float:
        return idf(term) if term in df else UNKNOWN_TERM_WEIGHT * known_max

    total = sum(weight(t) for t in q_terms)
    scored: list[tuple[FAQ, float]] = []
    for faq, head, body in indexed:
        hit = sum(idf(t) * (1.0 if t in head else 0.6 if t in body else 0.0) for t in q_terms)
        if hit > 0:
            scored.append((faq, round(hit / total, 3)))
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:k]


GENERIC_TERMS = {"tea", "coffee", "order", "item", "product", "snack", "method", "deliver"}


def specific_overlap(faq: FAQ, query: str) -> int:
    """How many specific (non-generic) query words appear in the FAQ's question or category."""
    return len((tokenize(query) & (tokenize(faq.question) | tokenize(faq.category))) - GENERIC_TERMS)
