# 🍃 TeaTrail Store · Support Agent "Tara"

A passcode-protected Streamlit support app for **TeaTrail Store** (artisanal tea, coffee & snacks).
Tara answers customer questions **strictly from a 20-FAQ knowledge base** (live from a public Google
Sheet), politely deflects off-topic or prompt-injection attempts, and hands complex or unanswered
questions to a human via an in-app ticket form with a live **Support Queue (Demo View)**.

It works out of the box with **no API key** (offline FAQ-matching mode) and with **no Google Sheet**
(built-in `sample_faqs.csv`).

## Deploy on Streamlit Community Cloud (3 steps)

1. **Push this folder to a GitHub repo** (`.env`, `secrets.toml` and `data/*.json` are git-ignored).
2. At **[share.streamlit.io](https://share.streamlit.io) → Create app**, pick the repo, branch and `app.py`
   as the main file.
3. Under **Advanced settings → Secrets**, paste your settings (see `.streamlit/secrets.toml.example`)
   and click **Deploy**:
   ```toml
   APP_PASSCODE = "your-passcode"
   ANTHROPIC_API_KEY = "sk-ant-..."     # or OPENAI_API_KEY / GEMINI_API_KEY, or none for offline mode
   ```

## Run locally

```bash
pip install -r requirements.txt
```

```bash
streamlit run app.py
```

Set a passcode first: the app stays locked until `APP_PASSCODE` is configured (it is never stored in
the repository). Copy
`.env.example` to `.env`, or `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`, to configure keys.

## Connect your Google Sheet

1. Make a sheet with the columns **`category`, `question`, `answer`** (one FAQ per row; `category` is optional).
2. Click **Share → General access → Anyone with the link (Viewer)**.
3. The app already points at the TeaTrail FAQ sheet; to use another, paste its normal link into `FAQ_SHEET_CSV_URL`. Edit, share and "Publish to web" links all
   work (the app reads the sheet's CSV feed, falling back to the export link).

FAQs are cached for 5 minutes. Use **🔄 Refresh FAQs** in the sidebar to pull changes immediately. If the
sheet is unreachable or private, the app shows a warning and falls back to the built-in FAQs.

## Configuration

| Setting | Default | Purpose |
|---|---|---|
| `APP_PASSCODE` / `APP_PASSCODE_SHA256` | *(none: app stays locked)* | Lock-screen passcode (plain text or SHA-256 hex) |
| `FAQ_SHEET_CSV_URL` | the TeaTrail FAQ sheet | Public Google Sheet or any CSV URL (`sample` = built-in FAQs only) |
| `LLM_PROVIDER` | `auto` | `auto` uses the first key found: Anthropic → OpenAI → Gemini → offline |
| `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY` | – | Provider keys |
| `LLM_MODEL` | `claude-opus-5-5` / `gpt-5-mini` / `gemini-2.5-flash` | Override the provider's model |
| `LLM_EFFORT` | `low` | Claude effort level (`none` to omit it for older Claude models) |
| `ANTHROPIC_FALLBACKS` | `on` | Server-side refusal fallback on Claude (auto-retries without it if rejected) |
| `DATA_DIR` | `./data` | Where `tickets.json` and `feedback.json` are written |

Settings are read from Streamlit secrets first, then environment variables / `.env`.

## How Tara works

```
customer message
  ├─ local guardrails (instant, no API call)
  │    prompt injection · politics / coding / trivia · competitor comparisons → warm deflection
  │    "talk to a human" → hand-off card + Raise a ticket
  ├─ LLM with the full FAQ base in a cached system prompt
  │    rules: FAQ facts only, never invent prices/timelines/policies; say "I don't have that exact
  │    detail" + [[HANDOFF]] when uncovered, order-specific or the customer is upset; cite [[FAQ: n]]
  └─ offline / error fallback: keyword retrieval answers from the best-matching FAQ, or admits it
       doesn't know and offers a ticket
```

The control tokens are hidden while the reply streams and turn into UI: FAQ source chips, and a
**Raise a ticket** button that opens a form (name, email, optional Order ID, a suggested category, and an
auto-filled summary plus transcript). Tickets get IDs like `TT-1042`, are saved to `data/tickets.json`,
and appear live in the sidebar **Support Queue (Demo View)**, which you can download as JSON. 👍/👎
feedback under each reply is saved to `data/feedback.json`.

> Streamlit Community Cloud storage is ephemeral: `data/*.json` resets when the app restarts. That's fine
> for a demo; use a database or a Sheets/CRM integration for production.

## Run Tara in Google ADK Web (optional)

The same agent, guardrails, live FAQ sheet and ticket queue also run in Google's
[Agent Development Kit](https://google.github.io/adk-docs/) developer UI, where you can see each tool call.

```bash
pip install -r adk_agents/requirements.txt
```

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

```bash
adk web adk_agents
```

Open http://localhost:8000 and pick **tara**. Claude (`claude-opus-5-5`, effort `low`) runs through ADK's built-in
Anthropic model class; if only `GOOGLE_API_KEY` is set, it uses Gemini instead. Tara has two tools:
`raise_ticket` (writes to the same `data/tickets.json`, with the chat transcript attached) and `check_ticket`.
Off-topic and prompt-injection messages are answered by a guardrail callback without calling the model.
ADK Web is a developer tool: the Streamlit app remains the customer-facing site.

## Project layout

| File | Role |
|---|---|
| `app.py` | UI: lock screen, hero, chat with streaming, suggestion chips, feedback, ticket dialog, sidebar |
| `agent.py` | Tara: guardrails, system prompt, Claude/OpenAI/Gemini streaming wrappers, offline answers |
| `faq_loader.py` | Google Sheet → CSV loader, header normalisation, sample fallback, keyword retrieval |
| `tickets.py` | Ticket validation + `TT-####` IDs, feedback log; atomic, lock-protected JSON writes |
| `styles.py` | Design system: palette, Fraunces + Plus Jakarta Sans, chat bubbles, cards, escaped HTML snippets |
| `config.py` | One place to read settings from secrets → env → defaults |
| `adk_agents/tara/` | The same agent for Google ADK Web (`adk web adk_agents`) |
| `sample_faqs.csv` | Offline copy of the TeaTrail FAQ sheet (20 FAQs), used if Google is unreachable |
| `.streamlit/config.toml` | Theme (colours, fonts, radii) and minimal toolbar |

## Tests

```bash
pip install -r requirements-dev.txt
```

```bash
python -m pytest -q
```

The 109 tests (2 need `google-adk`) cover the FAQ loader (URL normalisation, aliases, fallbacks, retrieval), guardrails,
tickets and feedback, the agent (offline answers, streamed control tokens, error/refusal fallback), the
real Anthropic/OpenAI SDKs against a local fake API (request shape and streaming), an end-to-end
Streamlit `AppTest` smoke test (lock screen → chips → hand-off), and the ADK agent run through ADK's runner
against a fake Anthropic API (answer, blocked injection, `raise_ticket` tool call).
