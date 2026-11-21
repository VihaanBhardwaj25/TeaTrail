# 🍃 TeaTrail Store · Support Agent "Tara"

A passcode-protected Streamlit support app for **TeaTrail Store** (artisanal tea, coffee & snacks).
Tara answers customer questions **strictly from a 20-FAQ knowledge base** (live from a public Google
Sheet), politely deflects off-topic or prompt-injection attempts, and hands complex or unanswered
questions to a person by raising a `TKT-####` ticket (saved to `tickets.csv`) that shows up live in the sidebar.

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
   ANTHROPIC_API_KEY = "sk-ant-..."     # or GOOGLE_API_KEY (Gemini) / OPENAI_API_KEY, or none for offline mode
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
| `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY` (or `GEMINI_API_KEY`), `OPENAI_API_KEY` | – | Provider keys |
| `LLM_MODEL` | `claude-opus-5-5` / `gemini-2.5-flash-lite` / `gpt-5-mini` | Override the provider's model |
| `LLM_EFFORT` | `low` | Claude effort level (`none` to omit it for older Claude models) |
| `ANTHROPIC_FALLBACKS` | `on` | Server-side refusal fallback on Claude (auto-retries without it if rejected) |
| `DATA_DIR` | `./data` | Where `tickets.csv` and `feedback.csv` are written |

Settings are read from Streamlit secrets first, then environment variables / `.env`.

## How Tara works

```
customer message
  ├─ 1. rules in code (same with or without an AI model; tricky messages never reach it)
  │    guardrails: "ignore your rules", other customers' details, card numbers / OTPs / passwords,
  │                discount or freebie requests, off-topic (politics, homework, coding, competitors)
  │    hand-offs → ticket raised at once, ID from code, "a person will reply within 24 hours":
  │                asks for a person · damaged or wrong item · refund/return over ₹2,000 ·
  │                angry or upset customer · "yes" to Tara's offer to connect them to a person
  │    greeting:   "Hi, I'm Tara from TeaTrail! How can I help with your order today?"
  ├─ 2. FAQ sheet: the LLM answers from all 20 rows (or, with no key, the best-matching row);
  │    facts are never changed and every answer ends with (Source: Category)
  └─ 3. not in the sheet: "I don't know that yet. Would you like me to connect you to a person?"
```

Tickets go to `data/tickets.csv` with the columns `ticket_id, time, message, reason, priority (normal/high),
status (open)`, plus optional name, email and order ID that the customer can add from the ticket card, and
the chat transcript. Open tickets show live in the sidebar and can be downloaded. "Was this helpful?"
Yes/No ratings under each reply are saved to `data/feedback.csv`.

Run the brief's tricky-message check any time:

```bash
python test_tricky.py
```

> Streamlit Community Cloud storage is ephemeral: `data/*.csv` resets when the app restarts. That's fine
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
Anthropic model class; if only `GOOGLE_API_KEY` is set, it uses Gemini Flash-Lite instead. Tara has two tools:
`create_ticket(message, reason, priority)` (writes to the same `data/tickets.csv`, with the chat transcript attached) and `check_ticket`. The rules in code run first, before the model.
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

The 133 tests (2 need `google-adk`) cover every row of the project brief's check tables
(`tests/test_brief_checks.py`), the FAQ loader (URL normalisation, aliases, fallbacks, retrieval), guardrails,
tickets and feedback, the agent (offline answers, streamed control tokens, error/refusal fallback), the
real Anthropic/OpenAI SDKs against a local fake API (request shape and streaming), an end-to-end
Streamlit `AppTest` smoke test (lock screen → chips → hand-off), and the ADK agent run through ADK's runner
against a fake Anthropic API (rules, FAQ answer, `create_ticket` tool call).
