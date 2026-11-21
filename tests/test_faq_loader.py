import pandas as pd
import pytest
import requests

import faq_loader
from agent import is_confident
from faq_loader import fetch_faqs, normalize_sheet_url, parse_faq_frame, search_faqs, sheet_csv_urls


def test_sample_has_20_faqs_covering_all_topics():
    kb = fetch_faqs(None)
    assert kb.source == "sample" and kb.warning is None
    assert len(kb.faqs) == 20
    assert set(kb.categories) == {"Delivery", "Payments", "Orders", "Returns", "Refunds", "Offers",
                                  "Account", "Support", "Products"}
    assert all(f.question and f.answer for f in kb.faqs)
    assert [f.id for f in kb.faqs] == list(range(1, 21))


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://docs.google.com/spreadsheets/d/AbC_123-x/edit#gid=456",
         "https://docs.google.com/spreadsheets/d/AbC_123-x/gviz/tq?tqx=out:csv&headers=1&gid=456"),
        ("https://docs.google.com/spreadsheets/d/AbC_123-x/edit?usp=sharing",
         "https://docs.google.com/spreadsheets/d/AbC_123-x/gviz/tq?tqx=out:csv&headers=1"),
        ("https://docs.google.com/spreadsheets/d/e/2PACX-1vXYZ/pubhtml",
         "https://docs.google.com/spreadsheets/d/e/2PACX-1vXYZ/pub?output=csv"),
        ("https://docs.google.com/spreadsheets/d/e/2PACX-1vXYZ/pub?gid=0&single=true&output=csv",
         "https://docs.google.com/spreadsheets/d/e/2PACX-1vXYZ/pub?output=csv&gid=0"),
        ("https://example.com/faqs.csv", "https://example.com/faqs.csv"),
    ],
)
def test_normalize_sheet_url(url, expected):
    assert normalize_sheet_url(url) == expected


def test_sheet_links_try_gviz_then_export():
    urls = sheet_csv_urls("https://docs.google.com/spreadsheets/d/AbC/edit")
    assert urls == ["https://docs.google.com/spreadsheets/d/AbC/gviz/tq?tqx=out:csv&headers=1",
                    "https://docs.google.com/spreadsheets/d/AbC/export?format=csv"]


def test_fetch_uses_export_when_gviz_fails(monkeypatch):
    csv = "Category,Question,Answer\nDelivery,Do you ship?,Yes within India\n"
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        if "gviz" in url:
            raise requests.ConnectionError("blocked")
        return _FakeResponse(csv)

    monkeypatch.setattr(faq_loader.requests, "get", fake_get)
    kb = fetch_faqs("https://docs.google.com/spreadsheets/d/abc/edit")
    assert kb.source == "sheet" and len(calls) == 2


def test_parse_accepts_header_aliases_and_skips_blank_rows():
    df = pd.DataFrame({"Topic": ["Delivery", None, "x"], " Q ": ["How fast?", "Empty answer", None],
                       "A": ["2-4 days", None, "orphan"]})
    faqs = parse_faq_frame(df)
    assert len(faqs) == 1
    assert faqs[0].category == "Delivery" and faqs[0].question == "How fast?"


def test_parse_rejects_sheet_without_required_columns():
    with pytest.raises(ValueError):
        parse_faq_frame(pd.DataFrame({"foo": [1], "bar": [2]}))


class _FakeResponse:
    def __init__(self, text, content_type="text/csv"):
        self.content = text.encode("utf-8")
        self.headers = {"content-type": content_type}

    def raise_for_status(self):
        pass


def test_fetch_from_sheet(monkeypatch):
    csv = "category,question,answer\nDelivery,Do you ship?,Yes within India\n"
    monkeypatch.setattr(faq_loader.requests, "get", lambda *a, **k: _FakeResponse(csv))
    kb = fetch_faqs("https://docs.google.com/spreadsheets/d/abc/edit")
    assert kb.source == "sheet" and len(kb.faqs) == 1 and kb.warning is None


def test_fetch_falls_back_when_sheet_unreachable(monkeypatch):
    def boom(*a, **k):
        raise requests.ConnectionError("network down")

    monkeypatch.setattr(faq_loader.requests, "get", boom)
    kb = fetch_faqs("https://docs.google.com/spreadsheets/d/abc/edit")
    assert kb.source == "sample" and len(kb.faqs) == 20
    assert "couldn't connect" in kb.warning and "http" not in kb.warning.lower()


def test_fetch_falls_back_when_sheet_is_private(monkeypatch):
    monkeypatch.setattr(faq_loader.requests, "get", lambda *a, **k: _FakeResponse("<html>", "text/html"))
    kb = fetch_faqs("https://docs.google.com/spreadsheets/d/abc/edit")
    assert kb.source == "sample" and "shared publicly" in kb.warning


@pytest.mark.parametrize(
    "query, expected_fragment",
    [
        ("How fresh is your tea?", "teas fresh"),
        ("how much is shipping", "delivery cost"),
        ("Tell me about gift hampers", "gift hampers"),
        ("my parcel came broken", "damaged"),
        ("how do I get my money back", "refund"),
        ("can I pay cash when it arrives", "cash on delivery"),
        ("do you deliver to 403001?", "pincode"),
        ("Which payment options do you have?", "payment methods"),
        ("Where is my order #458812? It still hasn't arrived", "track"),
        ("how do I apply a promo code?", "coupon"),
        ("I forgot my password", "password"),
        ("what time is customer support open?", "support hours"),
        ("are your snacks veg?", "vegetarian"),
        ("can I return an opened pack of tea?", "opened pack"),
    ],
)
def test_search_finds_the_right_faq(query, expected_fragment):
    kb = fetch_faqs(None)
    top = search_faqs(kb.faqs, query, k=1)[0]
    assert expected_fragment.lower() in top[0].question.lower()
    assert is_confident(top, query)


@pytest.mark.parametrize("query", [
    "Do you have a physical store in Goa?", "Do you sell matcha whisks?", "Are your teas organic?",
    "Do you ship to the USA?", "Do you have any vegan snacks?", "Do you sell coffee?",
    "What is the caffeine content of your Assam tea?", "do you have a loyalty program",
    "we need 40 hampers for our office party, any bulk discount?",
])
def test_uncovered_questions_are_not_confident(query):
    kb = fetch_faqs(None)
    matches = search_faqs(kb.faqs, query, k=1)
    assert not is_confident(matches[0] if matches else None, query)
