# Data Science Copilot Enterprise

> **AI-powered CSV analytics platform — Material Design SaaS UI + Pro DAG execution engine**

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/flask-3.0-green.svg)](https://flask.palletsprojects.com/)
[![React](https://img.shields.io/badge/react-18-61DAFB.svg)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/typescript-5-3178C6.svg)](https://www.typescriptlang.org/)

---

## What It Does

Upload a CSV, ask questions in plain English, get instant interactive results.

| Mode | What It Handles |
|------|----------------|
| **Normal** | Single-step queries — chat interface, interactive tables, charts, undo |
| **Pro** | Multi-step pipelines — DAG plan you approve, live step-by-step execution, inline results |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Flask 3.0, SQLAlchemy, SQLite |
| **Auth** | JWT Bearer tokens + bcrypt |
| **AI** | Groq API, OpenRouter API (OpenAI-compatible) |
| **Models** | Llama 3.1 8B (light) · Llama 3.3 70B (mid) · DeepSeek R1 (heavy) |
| **Data** | Pandas, NumPy, Matplotlib, Seaborn |
| **Frontend** | React 18 + TypeScript + Vite + TailwindCSS v4 |
| **UI** | AG Grid (tables) · Plotly (charts) · React Flow (DAG) · Zustand (state) |

---

## Quick Start

### 1 — Backend (Flask)

```bash
pip install -r requirements.txt

# Set API keys
set GROQ_API_KEY=gsk_...
set OPENROUTER_API_KEY=sk-or-...
set SECRET_KEY=your-secret-key

python run.py          # → http://localhost:5000
```

### 2 — Frontend (React)

```bash
cd frontend
npm install
npm run dev            # → http://localhost:5173
```

The React dev server proxies `/api/*` requests to Flask at port 5000.

> **First time:** Go to `http://localhost:5173` → Register → Upload CSV → Analyze.

---

## Usage

### Normal Mode (`/normal`)

```
"Show first 10 rows"
"Plot histogram of price"
"Fill missing values with 0"
"What insights can you give me?"
"Undo"
```

Results appear instantly in the right panel as interactive AG Grid tables or Plotly charts.

### Pro Mode (`/pro`)

```
"Check for missing data, compute correlations, visualize the heatmap, and summarize"
```

**What happens:**
1. Engine classifies as complex → routes to Pro
2. DAG plan appears (3–10 nodes) — review each step
3. Click **⚡ Approve & Execute**
4. Each step renders its output live as it completes
5. AI summary appears when done

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | Yes (or OpenRouter) | [console.groq.com](https://console.groq.com) |
| `OPENROUTER_API_KEY` | Yes (or Groq) | [openrouter.ai](https://openrouter.ai) |
| `SECRET_KEY` | Recommended | JWT signing key |

At least one of `GROQ_API_KEY` / `OPENROUTER_API_KEY` is required. Both enables automatic fallback.

---

## Project Layout

```
v4.7 UI Transformation/
├── run.py                    # Flask entry point → localhost:5000
├── app.py                    # App factory (slim, 50 lines)
├── routes/                   # Blueprint modules (auth, dataset, normal, pro, profile)
├── engines_normal/           # Normal Mode AI engine
├── engines_pro/              # Pro DAG engine (planner, executor, validator)
├── core/                     # Dataset profiler, execution context, Pro config
├── models_api/               # Model router (Groq + OpenRouter + fallback)
├── database/                 # SQLAlchemy models (User, Session, Message)
├── frontend/                 # React + Vite app → localhost:5173
│   └── src/
│       ├── components/       # 16 Material Design components
│       ├── layouts/          # NormalLayout, ProLayout
│       ├── pages/            # Login, Register, NormalMode, ProWorkspace, Settings
│       ├── store/            # Zustand: authStore, sessionStore, proStore
│       └── services/         # Axios API client with Bearer token interceptor
└── PROJECT_GUIDE.md          # Full developer reference
```

---

## Pro Mode Limits

| Resource | Default |
|----------|---------|
| Max dataset rows | 100,000 (soft warn + override) |
| Max nodes per plan | 20 |
| Execution timeout per node | 300 s |
| Retry on node failure | 1× |
| Max auto-replans | 2× |
| Max artifact size | 5 MB |

All limits configurable in `core/config.py`.

---

## Full Documentation

See **[PROJECT_GUIDE.md](PROJECT_GUIDE.md)** for complete architecture, API reference, developer guide, and deployment checklist.

---

*v4.7 · March 2026 · React + Flask + Material Design*
