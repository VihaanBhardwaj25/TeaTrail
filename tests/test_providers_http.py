"""Run the real Anthropic / OpenAI SDKs against a local fake API server.

No API key or network needed: this checks the exact request each provider
wrapper sends and that streamed replies (including refusals and a rejected
``fallbacks`` parameter) are handled end to end.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from agent import Tara
from config import LLMSettings
from faq_loader import fetch_faqs

FAQS = fetch_faqs(None).faqs


def _sse(events):
    return "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events).encode()


def _anthropic_stream(text_parts, stop_reason="end_turn"):
    events = [
        {"type": "message_start", "message": {"id": "msg_1", "type": "message", "role": "assistant",
         "model": "claude-opus-5-5", "content": [], "stop_reason": None, "stop_sequence": None,
         "usage": {"input_tokens": 10, "output_tokens": 1}}},
        {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
        *[{"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": t}} for t in text_parts],
        {"type": "content_block_stop", "index": 0},
        {"type": "message_delta", "delta": {"stop_reason": stop_reason, "stop_sequence": None},
         "usage": {"output_tokens": 12}},
        {"type": "message_stop"},
    ]
    return _sse(events)


class FakeAPI:
    def __init__(self):
        self.requests = []  # (path, headers, body)
        self.responses = []  # queue of (status, content_type, bytes)
        api = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                api.requests.append((self.path, dict(self.headers), body))
                status, ctype, payload = api.responses.pop(0)
                self.send_response(status)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("x-should-retry", "false")
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()


@pytest.fixture
def fake_api(monkeypatch):
    api = FakeAPI()
    monkeypatch.setenv("ANTHROPIC_BASE_URL", api.url)
    monkeypatch.setenv("OPENAI_BASE_URL", api.url + "/v1")
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
    yield api
    api.server.shutdown()


def _reply(tara, text):
    stream = tara.respond(text, [])
    chunks = list(stream)
    return stream.reply, chunks


def test_anthropic_request_shape_and_streaming(fake_api):
    fake_api.responses.append((200, "text/event-stream",
                               _anthropic_stream(["Shipping is free on orders of ₹999+ 🍃", "\n[[FAQ: 2]]"])))
    tara = Tara(FAQS, LLMSettings("anthropic", "claude-opus-5-5", "sk-ant-test"))
    reply, chunks = _reply(tara, "How much is shipping?")

    assert reply.text == "Shipping is free on orders of ₹999+ 🍃\n\n(Source: Delivery)"
    assert [s.id for s in reply.sources] == [2] and not reply.degraded
    assert "[[" not in "".join(c for c in chunks if c)

    path, headers, body = fake_api.requests[0]
    assert path.startswith("/v1/messages")
    assert body["model"] == "claude-opus-5-5"
    assert body["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in headers.get("anthropic-beta", "")
    assert body["output_config"] == {"effort": "low"}
    assert body["stream"] is True
    assert body["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert body["system"][0]["text"].count("<faq id=") == 20
    assert body["messages"] == [{"role": "user", "content": "How much is shipping?"}]
    assert "temperature" not in body and "thinking" not in body


def test_anthropic_retries_without_fallbacks_on_400(fake_api):
    error = json.dumps({"type": "error", "error": {"type": "invalid_request_error",
                                                   "message": "fallbacks: not enabled"}}).encode()
    fake_api.responses += [(400, "application/json", error),
                           (200, "text/event-stream", _anthropic_stream(["Yes! [[FAQ: 19]]"]))]
    tara = Tara(FAQS, LLMSettings("anthropic", "claude-opus-5-5", "sk-ant-test"))
    reply, _ = _reply(tara, "Do you have gift hampers?")
    assert reply.text == "Yes!\n\n(Source: Products)" and not reply.degraded
    assert "fallbacks" in fake_api.requests[0][2] and "fallbacks" not in fake_api.requests[1][2]


def test_anthropic_refusal_falls_back_to_faq(fake_api):
    fake_api.responses.append((200, "text/event-stream", _anthropic_stream(["Partial"], stop_reason="refusal")))
    tara = Tara(FAQS, LLMSettings("anthropic", "claude-opus-5-5", "sk-ant-test"))
    reply, chunks = _reply(tara, "Are your teas fresh?")
    assert None in chunks and reply.degraded and "harvest" in reply.text


def test_anthropic_fallbacks_can_be_disabled(fake_api):
    fake_api.responses.append((200, "text/event-stream", _anthropic_stream(["Hi! 🍵"])))
    tara = Tara(FAQS, LLMSettings("anthropic", "claude-opus-5-5", "sk-ant-test", anthropic_fallbacks=False))
    _reply(tara, "Are your teas fresh?")
    _, headers, body = fake_api.requests[0]
    assert "fallbacks" not in body and "server-side-fallback" not in headers.get("anthropic-beta", "")


def test_openai_request_shape_and_streaming(fake_api):
    def chunk(content):
        return {"id": "c1", "object": "chat.completion.chunk", "created": 1, "model": "gpt-5-mini",
                "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}]}

    payload = "".join(f"data: {json.dumps(chunk(t))}\n\n" for t in ["We accept UPI ", "and cards. [[FAQ: 6]]"])
    fake_api.responses.append((200, "text/event-stream", (payload + "data: [DONE]\n\n").encode()))
    tara = Tara(FAQS, LLMSettings("openai", "gpt-5-mini", "sk-test"))
    reply, _ = _reply(tara, "Which payment options do you have?")
    assert reply.text.startswith("We accept UPI and cards.") and [s.id for s in reply.sources] == [6]
    path, _, body = fake_api.requests[0]
    assert path == "/v1/chat/completions"
    assert body["messages"][0]["role"] == "system" and body["stream"] is True


def test_auth_error_degrades_gracefully(fake_api):
    error = json.dumps({"type": "error", "error": {"type": "authentication_error", "message": "bad key"}}).encode()
    fake_api.responses += [(401, "application/json", error)]
    tara = Tara(FAQS, LLMSettings("anthropic", "claude-opus-5-5", "sk-ant-bad"))
    reply, _ = _reply(tara, "What is your return policy?")
    assert reply.degraded and "7 days" in reply.text
