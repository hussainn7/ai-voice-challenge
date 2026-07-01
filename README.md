# PrettyGood AI Voice Bot

Automated patient simulator that calls the PGAI test line (+1-805-439-8008) and evaluates the AI agent's responses across a range of medical office scenarios.

## How it works

The bot uses Twilio to place outbound calls and OpenAI's Realtime API (`gpt-4o-realtime-preview`) to simulate realistic patient conversations. Audio flows directly between Twilio and OpenAI — mulaw 8kHz in both directions, no format conversion needed. After each call, GPT-4o reviews the transcript and automatically flags agent bugs.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for a full explanation.

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Fill in `.env` with your credentials:

- `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` — from [console.twilio.com](https://console.twilio.com)
- `TWILIO_PHONE_NUMBER` — a US number you bought in Twilio (E.164 format)
- `OPENAI_API_KEY` — your OpenAI key with Realtime API access
- `PUBLIC_URL` — your public HTTPS URL (see step 3)

### 3. Expose the server publicly

```bash
ngrok http 8000
```

Copy the `https://xxxx.ngrok-free.app` URL into `PUBLIC_URL` in your `.env`.

### 4. Run

Single scenario:

```bash
python main.py call schedule_basic
```

Full batch (all 12 scenarios):

```bash
python main.py batch
```

List available scenarios:

```bash
python main.py list-scenarios
```

## Output

Each call produces three files in `calls/`:

| File | Contents |
|---|---|
| `call-NN.mp3` | Audio recording (both sides) |
| `call-NN.txt` | Human-readable transcript |
| `call-NN.json` | Raw transcript + metadata |

Bug findings are appended to `bug-report.md` automatically after each call.

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `TWILIO_ACCOUNT_SID` | Yes | Twilio account SID |
| `TWILIO_AUTH_TOKEN` | Yes | Twilio auth token |
| `TWILIO_PHONE_NUMBER` | Yes | Your Twilio number (E.164) |
| `OPENAI_API_KEY` | Yes | OpenAI API key |
| `TARGET_NUMBER` | No | Override test number (default: +18054398008) |
| `PUBLIC_URL` | Yes | Public HTTPS URL for Twilio webhooks |
