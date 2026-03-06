# Browser Automation Agent 🤖

A production-grade backend agent that automates browser interactions with chat interfaces.  
Send a prompt via REST API → the agent drives a real browser → returns the response as JSON.

## Architecture

```
┌─────────────────────────────────────────┐
│         APPLICATION LAYER               │
│  FastAPI Server  (POST /chat)           │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│        COMMUNICATION LAYER              │
│  Session Manager (auth, concurrency)    │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│         AUTOMATION LAYER                │
│  Playwright Browser Agent               │
│  (navigate → type → submit → extract)   │
└─────────────────────────────────────────┘
```

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Initialize a login session

```bash
# Start the server
python main.py --headed

# In another terminal, trigger interactive login:
curl -X POST http://localhost:8000/session/init
```

A browser window opens — log in to the target site, then close the window.  
Your session is saved to `data/storage_state.json`.

### 3. Send a chat request

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Explain quantum computing in simple terms."}'
```

Response:
```json
{
  "success": true,
  "prompt": "Explain quantum computing in simple terms.",
  "response": "Quantum computing uses quantum bits (qubits)...",
  "duration_ms": 18432
}
```

## CLI Options

```bash
python main.py                  # default: headless, port 8000
python main.py --headed         # see the browser in action
python main.py --port 9000      # custom port
python main.py --reload         # auto-reload on code changes
```

## API Endpoints

| Method | Endpoint         | Description                      |
|--------|-----------------|----------------------------------|
| POST   | `/chat`         | Send prompt, get response        |
| POST   | `/session/init` | Open browser for manual login    |
| GET    | `/health`       | Health check                     |
| GET    | `/docs`         | Interactive Swagger UI           |

## Configuration

All settings can be overridden via environment variables (prefix: `AGENT_`):

| Variable                       | Default   | Description                     |
|-------------------------------|-----------|---------------------------------|
| `AGENT_HEADLESS`              | `true`    | Run browser headlessly          |
| `AGENT_TARGET_URL`            | `https://chat.openai.com` | Target chat URL   |
| `AGENT_RESPONSE_TIMEOUT_MS`  | `120000`  | Max wait for response (ms)      |
| `AGENT_MAX_CONCURRENT_SESSIONS` | `3`    | Parallel session limit          |
| `AGENT_RETRY_ATTEMPTS`       | `3`       | Retries on failure              |

## Project Structure

```
browser-agent/
├── app/
│   ├── models.py          # Pydantic request/response schemas
│   └── server.py          # FastAPI endpoints
├── core/
│   ├── browser_agent.py   # The automation engine
│   ├── selectors.py       # DOM selectors (centralized)
│   └── session_manager.py # Browser lifecycle & auth
├── data/                  # Session storage (gitignored)
├── logs/                  # Log files (gitignored)
├── config.py              # Settings
├── utils.py               # Retry, timer, helpers
├── main.py                # Entry point
└── requirements.txt
```

## How Response Detection Works

No fixed `sleep()` calls. The agent uses a two-phase strategy:

1. **Streaming indicator** — watches for the "Stop generating" button to appear (response started) then disappear (response finished).
2. **Text stabilization fallback** — if no indicator is found, polls the DOM until the text stops changing for 3 consecutive checks.

## Adapting to Other Sites

Edit `core/selectors.py` to change the DOM selectors for your target site. The rest of the code is site-agnostic.

## ⚠️ Disclaimer

Automating interactions with third-party websites may violate their Terms of Service. This tool is provided for **educational and internal automation purposes only**. Use responsibly.
